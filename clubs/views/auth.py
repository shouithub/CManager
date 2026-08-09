import json
import logging

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings
from django.contrib import messages
from ..models import UserProfile, Club, FormChannel, FormCycle, FormChannelClubState, FormSubmission, StaffClubRelation, Officer
from django.utils import timezone, translation
from django.db import transaction
from django.db.models import F, Q, Prefetch, Window
from django.db.models.functions import RowNumber
from django.core.paginator import Paginator
from django.core.cache import cache
import time
import uuid
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.exceptions import ObjectDoesNotExist
from ..lifecycle_utils import extend_inactive_account
from ..business_forms import externally_available_channels
from django.utils.translation import gettext as _
from ..identity import (
    IDENTITY_PRESIDENT,
    IDENTITY_PRIMARY,
    IDENTITY_SESSION_KEY,
    has_president_officer,
    is_president_mode,
)

# 登录限制配置
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes
logger = logging.getLogger(__name__)


def _client_ip(request):
    """返回用于限速的客户端 IP。

    反代链路中 X-Forwarded-For 由各层代理从左到右追加，最左侧才是真实客户端
    IP（例如 Cloudflare -> Nginx 时格式为“客户端IP, Cloudflare节点IP”）。
    因此取最左侧非空值；未开启代理头或没有该请求头时回退到 REMOTE_ADDR。
    """
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if getattr(settings, 'USE_X_FORWARDED_FOR', False) and forwarded:
        parts = [part.strip() for part in forwarded.split(',') if part.strip()]
        if parts:
            return parts[0]
    return request.META.get('REMOTE_ADDR', '')


def register(request):
    """用户注册 - 仅支持社长和干事"""
    if request.user.is_authenticated:
        return redirect('clubs:index')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        real_name = request.POST.get('real_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        role = request.POST.get('role', 'president')
        student_id = request.POST.get('student_id', '').strip()
        phone = request.POST.get('phone', '').strip()
        wechat = request.POST.get('wechat', '').strip()
        political_status = request.POST.get('political_status', 'non_member')
        
        errors = []
        
        # 基础验证
        if not username:
            errors.append('用户名不能为空')
        elif len(username) < 3 or len(username) > 30:
            errors.append('用户名长度应在3-30个字符之间')
        elif User.objects.filter(username=username).exists():
            errors.append('用户名已存在')
        
        if not real_name:
            errors.append('真实姓名不能为空')

        if not email:
            errors.append('邮箱不能为空')
        
        if not password:
            errors.append('密码不能为空')
        elif len(password) < 6:
            errors.append('密码至少6个字符')
        
        if password != password_confirm:
            errors.append('两次密码不一致')
        
        # 必填项验证
        if not student_id:
            errors.append('学号不能为空')
        elif UserProfile.objects.filter(student_id=student_id).exists():
            errors.append('学号已被使用')
        
        if not phone:
            errors.append('电话不能为空')
        if not wechat:
            errors.append('微信不能为空')
        
        # 角色验证
        valid_roles = ['president', 'staff']
        if role not in valid_roles:
            errors.append('无效的角色选择')
        
        # 部门验证（仅干事）
        department_obj = None
        if role == 'staff':
            department_id = request.POST.get('department', '').strip()
            if not department_id:
                errors.append('干事必须选择部门')
            else:
                from ..models import Department
                try:
                    department_obj = Department.objects.get(id=department_id)
                except (Department.DoesNotExist, ValueError):
                    errors.append('无效的部门选择')

        # 社长必须选择政治面貌
        if role == 'president':
            if not political_status or political_status == '':
                errors.append('社长必须选择政治面貌')
        
        if errors:
            from ..models import Department
            departments = Department.objects.all().order_by('order', 'name')
            return render(request, 'clubs/auth/register.html', {
                'errors': errors,
                'form_data': request.POST,
                'departments': departments,
            })
        
        # 创建用户账户
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # 确定用户状态
        if role == 'staff':
            status = 'pending'  # 干事需要审核
            message_text = '注册成功，您的账号正在审核中，请等待管理员批准！'
        else:
            status = 'approved'  # 社长直接批准
            message_text = '注册成功，请登录！'
        
        # 创建用户扩展信息
        UserProfile.objects.create(
            user=user,
            role=role,
            status=status,
            real_name=real_name,
            student_id=student_id,
            phone=phone,
            wechat=wechat,
            political_status=political_status if role == 'president' else 'non_member',
            department_link=department_obj  # 保存部门关联
        )
        
        messages.success(request, message_text)
        return redirect('clubs:login')
    
    from ..models import Department
    departments = Department.objects.all().order_by('order', 'name')
    return render(request, 'clubs/auth/register.html', {'departments': departments})


def user_login(request):
    """用户登录"""
    if request.user.is_authenticated:
        return redirect('clubs:index')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        client_ip = _client_ip(request)

        if not username or not password:
            messages.error(request, _('用户名和密码不能为空'))
            return render(request, 'clubs/auth/login.html')

        # 检查是否被锁定（按用户名或 IP）
        lock_key_user = f'login_lock:user:{username}'
        lock_key_ip = f'login_lock:ip:{client_ip}'
        if cache.get(lock_key_user) or cache.get(lock_key_ip):
            messages.error(request, _('登录尝试过多，请等待5分钟后再试，或联系管理员重置密码！'))
            return render(request, 'clubs/auth/login.html', {
                'username': username,
                'show_admin_reset_prompt': True,
            })

        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                # 成功登录：清理失败计数
                attempts_key_user = f'login_attempts:user:{username}'
                attempts_key_ip = f'login_attempts:ip:{client_ip}'
                cache.delete(attempts_key_user)
                cache.delete(attempts_key_ip)

                # 检查用户状态 - 干事需要审核通过才能登录
                profile = user.profile
                if profile.role == 'staff' and profile.status != 'approved':
                    messages.error(request, _('您的账号正在审核中，请等待管理员批准！'))
                    return render(request, 'clubs/auth/login.html', {
                        'username': username,
                    })

                login(request, user)
                messages.success(request, f'欢迎回来，{username}！')

                if getattr(profile, 'account_status', 'active') == 'inactive' and profile.role != 'admin':
                    request.session['show_inactive_prompt'] = True
                    messages.warning(
                        request,
                        _('您的账号当前为不活跃状态。您可以在“账户设置”中选择延期注销，延期后可继续保持1年活跃（支持多次延期）。')
                    )

                # 首次登录/重置后强制改密
                if getattr(user.profile, 'must_change_password', False):
                    messages.warning(request, _('为了账户安全，请先修改密码后再继续使用系统。'))
                    return redirect('clubs:edit_profile')

                # 根据角色跳转
                if user.profile.role == 'admin':
                    return redirect('clubs:admin_dashboard')
                elif user.profile.role == 'staff':
                    return redirect('clubs:index')  # 干事跳转首页
                elif user.profile.role == 'president':
                    return redirect('clubs:user_dashboard')
                else:
                    return redirect('clubs:index')  # 默认跳转首页
            except UserProfile.DoesNotExist:
                login(request, user)
                return redirect('clubs:index')
        else:
            # 登录失败：增加失败计数
            attempts_key_user = f'login_attempts:user:{username}'
            attempts_key_ip = f'login_attempts:ip:{client_ip}'

            user_attempts = cache.get(attempts_key_user) or 0
            ip_attempts = cache.get(attempts_key_ip) or 0

            user_attempts += 1
            ip_attempts += 1

            cache.set(attempts_key_user, user_attempts, LOGIN_WINDOW_SECONDS)
            cache.set(attempts_key_ip, ip_attempts, LOGIN_WINDOW_SECONDS)

            # 如果达到阈值，则设置锁定
            if user_attempts >= MAX_LOGIN_ATTEMPTS:
                cache.set(lock_key_user, True, LOGIN_WINDOW_SECONDS)
                cache.delete(attempts_key_user)
            if ip_attempts >= MAX_LOGIN_ATTEMPTS:
                cache.set(lock_key_ip, True, LOGIN_WINDOW_SECONDS)
                cache.delete(attempts_key_ip)

            # 如果已经被锁定，提示联系管理员重置密码
            if cache.get(lock_key_user) or cache.get(lock_key_ip):
                messages.error(request, _('登录尝试过多，请等待5分钟后再试，或联系管理员重置密码！'))
                from django.conf import settings
                return render(request, 'clubs/auth/login.html', {
                    'username': username,
                    'show_admin_reset_prompt': True,
                    'admin_contact_email': getattr(settings, 'ADMIN_CONTACT_EMAIL', ''),
                })

            messages.error(request, _('用户名或密码错误'))
            return render(request, 'clubs/auth/login.html', {
                'username': username,
            })
    
    return render(request, 'clubs/auth/login.html')


@login_required(login_url='clubs:login')
@require_http_methods(['POST'])
def extend_inactive_period(request):
    """用户主动延期注销：恢复活跃状态并顺延1年。"""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, _('用户档案不存在，无法延期'))
        return redirect('clubs:index')

    if profile.role == 'admin':
        messages.info(request, _('管理员账号不受自动注销策略影响，无需延期'))
        return redirect('clubs:edit_profile')

    if getattr(profile, 'account_status', 'active') != 'inactive':
        messages.info(request, _('当前账号不是不活跃状态，无需延期'))
        return redirect('clubs:edit_profile')

    new_until = extend_inactive_account(profile, days=365, reason='user_extend')
    request.session['show_inactive_prompt'] = False
    messages.success(request, f'延期成功，账号已恢复活跃状态，有效期至 {new_until.strftime("%Y-%m-%d")}。')
    return redirect('clubs:edit_profile')


def user_logout(request):
    """用户登出"""
    logout(request)
    messages.success(request, _('已登出'))
    return redirect('clubs:index')


def _identity_default_url(user, identity):
    if identity == IDENTITY_PRESIDENT:
        return reverse('clubs:user_dashboard')
    try:
        role = user.profile.role
    except UserProfile.DoesNotExist:
        return reverse('clubs:index')
    if role == 'admin':
        return reverse('clubs:admin_dashboard')
    return reverse('clubs:index')


@login_required(login_url='clubs:login')
@require_http_methods(['POST'])
def switch_identity(request):
    identity = request.POST.get('identity', IDENTITY_PRIMARY)

    if identity == IDENTITY_PRESIDENT:
        if not has_president_officer(request.user):
            messages.error(request, _('当前账号没有现任社长身份，无法切换'))
            return redirect(_identity_default_url(request.user, IDENTITY_PRIMARY))
        request.session[IDENTITY_SESSION_KEY] = IDENTITY_PRESIDENT
        messages.success(request, _('已切换到社长身份'))
        return redirect(_identity_default_url(request.user, IDENTITY_PRESIDENT))

    request.session[IDENTITY_SESSION_KEY] = IDENTITY_PRIMARY
    messages.success(request, _('已切换回主身份'))
    return redirect(_identity_default_url(request.user, IDENTITY_PRIMARY))



@login_required
@require_POST
def delete_account(request):
    """删除用户账户，根据不同角色执行差异化逻辑"""
    if request.method == 'POST':
        user = request.user
        
        # 获取并验证用户输入的确认用户名
        confirm_username = request.POST.get('confirm_username')
        
        # 检查确认用户名是否正确
        if confirm_username == user.username:
            # 保存用户名用于显示消息
            username = user.username

            try:
                role = user.profile.role
            except UserProfile.DoesNotExist:
                messages.error(request, _('用户档案不存在，无法注销账号'))
                return redirect('clubs:index')
            
            # 根据用户角色执行不同的删除逻辑
            if role == 'admin':
                # 管理员账户删除逻辑
                # 直接删除用户，Django会级联删除相关数据
                user.delete()
                messages.success(request, f'管理员账户 {username} 已成功删除！')
            
            elif role == 'president':
                # 社长账户删除逻辑
                # 1. 将该社长的 Officer 记录标记为离任，保留年审记录
                Officer.objects.filter(
                    user_profile=user.profile,
                    position='president',
                    is_current=True
                ).update(is_current=False, end_date=timezone.now().date())
                # 2. 删除用户账户
                user.delete()
                messages.success(request, f'社长账户 {username} 已成功删除！您的年审记录已被保留。')
            
            elif role == 'staff':
                # 干事账户删除逻辑 - 完整清除所有数据
                # 1. 先删除干事在所有社团中的角色关系
                # 删除干事在社团中的干部记录
                Officer.objects.filter(user_profile=user.profile).delete()
                
                # 删除干事的审核记录
                FormSubmission.objects.filter(reviewer=user).update(reviewer=None)
                
                # 2. 删除用户账户（级联删除profile等相关数据）
                user.delete()
                messages.success(request, f'干事账户 {username} 已成功删除！所有相关数据已被完整清除。')
            
            else:
                # 其他角色直接删除
                user.delete()
                messages.success(request, f'账户 {username} 已成功删除！')
            
            # 重定向到首页
            return redirect('clubs:index')
        else:
            # 显示错误消息
            messages.error(request, _('用户名输入错误，账户删除失败。'))
            
            # 重定向回修改账户设置页面
            return redirect('clubs:edit_profile')
    
    # 如果不是POST请求，重定向到修改账户设置页面
    return redirect('clubs:edit_profile')


@login_required(login_url='clubs:login')
def manage_staff_clubs(request):
    """干事管理负责的社团"""
    user = request.user
    
    # 检查用户是否为干事
    try:
        profile = user.profile
        if profile.role != 'staff' and profile.role != 'admin':
            messages.error(request, _('您没有权限访问此页面'))
            return redirect('clubs:user_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, _('用户角色未配置'))
        return redirect('clubs:login')
    
    if request.method == 'POST':
        # 干事只能查看页面，分配负责社团仅允许管理员操作，
        # 否则普通干事可自行把任意社团设为负责并取得该社团管理权限。
        if profile.role != 'admin':
            messages.error(request, _('仅管理员可以分配干事负责的社团'))
            return redirect('clubs:manage_staff_clubs')

        # 获取所有选中的社团ID
        selected_club_ids = request.POST.getlist('club_ids', [])
        
        # 更新StaffClubRelation
        from ..models import StaffClubRelation, Club
        
        valid_club_ids = set(
            Club.objects.filter(id__in=selected_club_ids).values_list('id', flat=True)
        )
        with transaction.atomic():
            relations = StaffClubRelation.objects.filter(staff=profile)
            existing_club_ids = set(relations.values_list('club_id', flat=True))
            relations.filter(is_active=True).update(is_active=False)
            relations.filter(club_id__in=valid_club_ids).update(is_active=True)
            StaffClubRelation.objects.bulk_create([
                StaffClubRelation(staff=profile, club_id=club_id, is_active=True)
                for club_id in valid_club_ids - existing_club_ids
            ])
        
        messages.success(request, _('负责社团设置成功'))
        return redirect('clubs:manage_staff_clubs')
    
    # 获取所有社团
    from ..models import Club, StaffClubRelation
    all_clubs = Club.objects.all().order_by('name')
    
    # 获取当前干事已选中的社团ID
    selected_club_ids = list(
        StaffClubRelation.objects.filter(staff=profile, is_active=True)
        .values_list('club_id', flat=True)
    )
    
    context = {
        'user': user,
        'all_clubs': all_clubs,
        'selected_club_ids': selected_club_ids,
        'is_admin': profile.role == 'admin',
    }
    
    return render(request, 'clubs/staff/manage_clubs.html', context)


@login_required(login_url='clubs:login')
def edit_profile(request):
    """用户修改个人信息 - 整合了信息修改、密码修改和头像上传"""
    user = request.user
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, _('用户档案不存在，请先联系管理员完善资料'))
        return redirect('clubs:index')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_info':
            # 获取表单数据
            real_name = request.POST.get('real_name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            phone = request.POST.get('phone', '').strip()
            wechat = request.POST.get('wechat', '').strip()
            student_id = request.POST.get('student_id', '').strip()
            political_status = request.POST.get('political_status', '')
            is_info_public = 'is_info_public' in request.POST
            
            errors = []
            
            # 验证
            if not real_name:
                errors.append(_('真实姓名不能为空'))
            if email:
                if '@' not in email:
                    errors.append(_('请输入有效的邮箱地址'))
                elif User.objects.filter(email__iexact=email).exclude(id=user.id).exists():
                    if user.email.lower() != email:
                        errors.append(_('邮箱已被其他用户注册'))
            if not phone:
                errors.append(_('电话不能为空'))
            if not wechat:
                errors.append(_('微信不能为空'))
            if not student_id:
                errors.append(_('学号不能为空'))
            if profile.role in ['president', 'staff', 'admin'] and not political_status:
                errors.append(_('政治面貌不能为空'))
            if UserProfile.objects.filter(student_id=student_id).exclude(id=profile.id).exists():
                errors.append(_('学号已被其他用户使用'))
            valid_political_statuses = {
                value for value, _label in UserProfile.POLITICAL_STATUS_CHOICES
            }
            if political_status and political_status not in valid_political_statuses:
                errors.append(_('政治面貌无效'))
            
            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                user.email = email
                user.save()
                profile.real_name = real_name
                profile.phone = phone
                profile.wechat = wechat
                profile.student_id = student_id
                profile.is_info_public = is_info_public
                if political_status:
                    profile.political_status = political_status
                profile.save()
                messages.success(request, _('个人信息已成功更新'))

        elif action == 'update_language':
            preferred_language = (request.POST.get('preferred_language') or '').strip()
            valid_languages = {code for code, _label in settings.LANGUAGES}
            if preferred_language and preferred_language not in valid_languages:
                messages.error(request, _('无效的语言选择'))
                return redirect(f"{reverse('clubs:edit_profile')}?tab=language")
            profile.preferred_language = preferred_language
            profile.save(update_fields=['preferred_language', 'updated_at'])
            # 语言选择已持久化到用户档案，不再依赖会话（Django 5.2 起
            # LANGUAGE_SESSION_KEY 已移除）。
            response = redirect(f"{reverse('clubs:edit_profile')}?tab=language")
            if preferred_language:
                # 同步写一次 Cookie，保证当前设备立即生效并覆盖旧选择。
                translation.activate(preferred_language)
                response.set_cookie(
                    settings.LANGUAGE_COOKIE_NAME,
                    preferred_language,
                    max_age=settings.LANGUAGE_COOKIE_AGE,
                    httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
                    secure=settings.LANGUAGE_COOKIE_SECURE,
                    samesite=settings.LANGUAGE_COOKIE_SAMESITE,
                )
                messages.success(request, _('语言偏好已保存，将在所有设备同步生效'))
            else:
                response.delete_cookie(
                    settings.LANGUAGE_COOKIE_NAME,
                    path=settings.LANGUAGE_COOKIE_PATH,
                    domain=settings.LANGUAGE_COOKIE_DOMAIN,
                )
                messages.success(request, _('已恢复为站点默认语言'))
            return response
                
        elif action == 'change_username':
            new_username = request.POST.get('new_username', '').strip()
            password = request.POST.get('password', '').strip()
            
            if not new_username:
                messages.error(request, _('新用户名不能为空'))
            elif len(new_username) < 3:
                messages.error(request, _('用户名至少3个字符'))
            elif len(new_username) > 30:
                messages.error(request, _('用户名不能超过30个字符'))
            elif User.objects.exclude(id=user.id).filter(username=new_username).exists():
                messages.error(request, _('用户名已被使用'))
            elif not password:
                messages.error(request, _('密码不能为空'))
            else:
                # 验证密码
                if not user.check_password(password):
                    messages.error(request, _('密码错误'))
                else:
                    old_username = user.username
                    user.username = new_username
                    user.save()
                    messages.success(request, f'用户名已从"{old_username}"更改为"{new_username}"')
                    
        elif action == 'change_password':
            old_password = request.POST.get('old_password', '').strip()
            new_password = request.POST.get('new_password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()
            
            if not user.check_password(old_password):
                messages.error(request, _('原密码错误'))
            elif new_password != confirm_password:
                messages.error(request, _('两次输入的新密码不一致'))
            elif len(new_password) < 6:
                messages.error(request, _('新密码长度至少为6位'))
            else:
                user.set_password(new_password)
                user.save()
                if getattr(profile, 'must_change_password', False):
                    profile.must_change_password = False
                    profile.save(update_fields=['must_change_password'])
                # 保持登录状态
                login(request, user)
                messages.success(request, _('密码已修改'))

        elif action == 'use_cravatar':
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            from ..avatar_utils import cravatar_exists, get_avatar_settings, normalize_avatar_email
            if not get_avatar_settings():
                messages.error(request, _('管理员暂未开放 Cravatar'))
                return redirect(f"{reverse('clubs:edit_profile')}?tab=avatar")
            avatar_email = normalize_avatar_email(request.POST.get('avatar_email'))
            if avatar_email:
                try:
                    validate_email(avatar_email)
                except ValidationError:
                    messages.error(request, _('请输入有效的 Cravatar 邮箱'))
                else:
                    exists = cravatar_exists(avatar_email)
                    if exists is True:
                        profile.avatar_email = avatar_email
                        profile.avatar_source = 'cravatar'
                        profile.save(update_fields=['avatar_email', 'avatar_source', 'updated_at'])
                        messages.success(request, _('已检测到 Cravatar 头像并启用'))
                    elif exists is False:
                        messages.error(request, _('该邮箱没有可用的 Cravatar 头像，请先在 Cravatar 绑定头像或继续使用本站上传'))
                    else:
                        messages.error(request, _('暂时无法连接 Cravatar，请稍后重试；当前头像未更改'))
            else:
                messages.error(request, _('请输入已绑定 Cravatar 头像的邮箱'))
            return redirect(f"{reverse('clubs:edit_profile')}?tab=avatar")

        elif action == 'use_local_avatar':
            profile.avatar_source = 'local'
            profile.save(update_fields=['avatar_source', 'updated_at'])
            messages.success(request, _('已切换为本站上传头像'))
            return redirect(f"{reverse('clubs:edit_profile')}?tab=avatar")
                
        elif action == 'upload_avatar':
            import base64
            avatar_base64 = request.POST.get('avatar_base64')
            avatar_file = request.FILES.get('avatar')
            # 反向代理可能移除 X-Requested-With；Accept 是标准协商头，保留它作为可靠兜底。
            is_async_upload = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('Accept', '')
            )

            def finish_avatar_upload(ok, message):
                if is_async_upload:
                    payload = {'ok': ok, 'message': message}
                    if ok:
                        from ..avatar_utils import get_profile_avatar_url
                        payload['avatar_url'] = get_profile_avatar_url(profile, request=request, size=256)
                    return JsonResponse(payload, status=200 if ok else 400)
                if ok:
                    messages.success(request, message)
                else:
                    messages.error(request, message)
                return redirect(f"{reverse('clubs:edit_profile')}?tab=avatar")
            
            if avatar_base64:
                try:
                    if len(avatar_base64) > 28 * 1024 * 1024:
                        raise ValueError('图片不能超过 20MB')
                    format, imgstr = avatar_base64.split(';base64,')
                    ext = format.split('/')[-1]
                    avatar_file = ContentFile(
                        base64.b64decode(imgstr, validate=True),
                        name=f'avatar_{user.id}_{int(time.time())}.{ext}',
                    )
                except Exception:
                    logger.exception('头像 Base64 数据处理失败')
                    return finish_avatar_upload(False, '头像数据无效，请重新选择图片')

            if avatar_file:
                try:
                    from ..upload_security import validate_upload
                    upload_error = validate_upload(
                        avatar_file,
                        field_name='头像',
                        allowed_extensions={'.jpg', '.jpeg', '.png', '.webp'},
                        max_bytes=20 * 1024 * 1024,
                    )
                    if upload_error:
                        return finish_avatar_upload(False, upload_error)
                    img = Image.open(avatar_file)
                    # 转换为RGB（处理PNG透明背景）
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                        
                    # 裁剪为正方形
                    width, height = img.size
                    new_size = min(width, height)
                    left = (width - new_size) / 2
                    top = (height - new_size) / 2
                    right = (width + new_size) / 2
                    bottom = (height + new_size) / 2
                    img = img.crop((left, top, right, bottom))
                    
                    # 缩放
                    img = img.resize((256, 256), Image.Resampling.LANCZOS)
                    
                    # 保存
                    thumb_io = BytesIO()
                    # 头像只用于小尺寸展示，适度压缩并移除原图元数据。
                    img.save(
                        thumb_io,
                        format='JPEG',
                        quality=82,
                        optimize=True,
                        progressive=True,
                    )
                    
                    # 生成文件名
                    # 每次上传使用唯一文件名，避免同秒内重复上传相互覆盖，也让浏览器缓存自然失效。
                    file_name = f'avatar_{user.id}_{uuid.uuid4().hex[:12]}.jpg'
                    old_avatar_name = ''
                    try:
                        old_avatar_name = profile.avatar.name or ''
                    except ValueError:
                        old_avatar_name = ''
                    profile.avatar.save(file_name, ContentFile(thumb_io.getvalue()), save=True)
                    if old_avatar_name and old_avatar_name != profile.avatar.name:
                        try:
                            profile.avatar.storage.delete(old_avatar_name)
                        except Exception:
                            logger.exception('删除旧头像文件失败: %s', old_avatar_name)
                    if profile.avatar_source != 'local':
                        profile.avatar_source = 'local'
                        profile.save(update_fields=['avatar_source', 'updated_at'])
                    return finish_avatar_upload(True, '头像已更新')
                except Exception:
                    logger.exception('头像处理失败')
                    return finish_avatar_upload(False, '头像处理失败，请稍后重试')
            else:
                return finish_avatar_upload(False, '请选择图片文件')
                
        return redirect('clubs:edit_profile')
    
    context = {
        'user': user,
        'profile': profile,
        'political_status_choices': UserProfile.POLITICAL_STATUS_CHOICES,
    }
    from ..avatar_utils import get_avatar_settings, get_profile_avatar_url
    context.update({
        'cravatar_enabled': get_avatar_settings(),
        'resolved_avatar_url': get_profile_avatar_url(profile, request=request, size=256),
    })
    return render(request, 'clubs/user/edit_profile.html', context)


@login_required(login_url=settings.LOGIN_URL)
def staff_management(request):
    """干事社团管理页面（干事和管理员可用）"""
    user = request.user
    
    # 检查用户角色
    try:
        profile = user.profile
        if profile.role != 'staff' and profile.role != 'admin':
            messages.error(request, _('您没有权限访问此页面'))
            return redirect('clubs:user_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, _('用户角色未配置'))
        return redirect('clubs:login')
    
    from ..models import Club, FormSubmission, StaffClubRelation, Officer

    active_cycles = Prefetch(
        'cycles',
        queryset=FormCycle.objects.filter(is_active=True).order_by('-sequence', '-starts_at'),
        to_attr='_active_cycles',
    )
    toggle_channels = list(
        FormChannel.objects.filter(allow_staff_toggle=True)
        .prefetch_related(active_cycles)
        .order_by('order', 'id')
    )
    for channel in toggle_channels:
        channel.needs_cycle = channel.cycle_type != 'none' or channel.submission_policy == 'once_per_cycle'
        channel.active_cycle = channel._active_cycles[0] if channel.needs_cycle and channel._active_cycles else None
        channel.global_enabled = bool(channel.active_cycle) if channel.needs_cycle else channel.is_active
    # 开启“未提交告警”的通道（不再写死内置动作，任何动态表单通道都可以开启）
    alert_channels = list(
        FormChannel.objects.filter(show_unsubmitted_alert=True)
        .prefetch_related(active_cycles)
        .order_by('order', 'id')
    )

    # 搜索 & 列表（分页）
    q = request.GET.get('q', '').strip()
    clubs_qs = Club.objects.prefetch_related(
        Prefetch(
            'officers',
            queryset=Officer.objects.filter(position='president', is_current=True).select_related('user_profile__user'),
            to_attr='_president_list',
        )
    ).all().order_by('name')
    if q:
        pres_club_ids = Officer.objects.filter(
            Q(user_profile__user__username__icontains=q) | Q(user_profile__real_name__icontains=q),
            position='president',
            is_current=True,
        ).values_list('club_id', flat=True)
        clubs_qs = clubs_qs.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(id__in=pres_club_ids)
        )

    paginator = Paginator(clubs_qs, 20)  # 每页20个
    page_number = request.GET.get('page')
    clubs_page = paginator.get_page(page_number)
    page_clubs = list(clubs_page.object_list)
    state_channel_ids = {
        channel.id
        for channel in [*toggle_channels, *alert_channels]
        if channel
    }
    disabled_by_channel = {channel_id: set() for channel_id in state_channel_ids}
    for channel_id, club_id in FormChannelClubState.objects.filter(
        channel_id__in=state_channel_ids,
        is_enabled=False,
    ).values_list('channel_id', 'club_id'):
        disabled_by_channel[channel_id].add(club_id)
    for club in page_clubs:
        club.dynamic_channel_states = [
            {
                'channel': channel,
                'is_enabled': bool(channel.global_enabled and club.id not in disabled_by_channel.get(channel.id, set())),
                'global_enabled': channel.global_enabled,
                'active_cycle': channel.active_cycle,
            }
            for channel in toggle_channels
        ]
    clubs_page.object_list = page_clubs
    
    # === 预警功能数据 ===
    # 获取当前干事负责的社团ID
    staff_club_ids = set(StaffClubRelation.objects.filter(
        staff=user.profile, 
        is_active=True
    ).values_list('club_id', flat=True))
    
    # 获取成员数少20人的社团（排除停止状态的社团）
    _president_prefetch = Prefetch(
        'officers',
        queryset=Officer.objects.filter(position='president', is_current=True).select_related('user_profile__user', 'user_profile'),
        to_attr='_president_list',
    )
    _staff_prefetch = Prefetch(
        'responsible_staff',
        queryset=StaffClubRelation.objects.filter(is_active=True).select_related('staff__user'),
    )

    def warning_club_lists(queryset):
        clubs = list(queryset.prefetch_related(_president_prefetch, _staff_prefetch))
        mine = [club for club in clubs if club.id in staff_club_ids]
        other = [club for club in clubs if club.id not in staff_club_ids]
        return clubs, mine, other

    from ..models import SiteSettings
    site_settings = SiteSettings.get_settings()
    low_member_threshold = site_settings.low_member_alert_threshold or 20
    clubs_with_low_members, clubs_with_low_members_my, clubs_with_low_members_other = warning_club_lists(
        Club.objects.filter(members_count__lt=low_member_threshold)
        .exclude(status='suspended')
        .order_by('members_count')
    )
    
    # === 统一告警数据（成员数量 + 各通道未提交） ===
    alerts = []

    if clubs_with_low_members:
        alerts.append({
            'key': 'low_members',
            'title': '社团成员数量预警',
            'icon': 'warning',
            'color': '#6750a4',
            'show_members': True,
            'empty_my': '暂无你负责的成员不足社团',
            'my': clubs_with_low_members_my,
            'my_count': len(clubs_with_low_members_my),
            'other': clubs_with_low_members_other,
            'other_count': len(clubs_with_low_members_other),
            'count': len(clubs_with_low_members),
            'copy_title': '成员数量不足的社团名单',
            'copy_cycle': '',
        })

    for channel in alert_channels:
        needs_cycle = channel.cycle_type != 'none' or channel.submission_policy == 'once_per_cycle'
        active_cycle = channel._active_cycles[0] if needs_cycle and channel._active_cycles else None
        if needs_cycle and not active_cycle:
            continue
        disabled_ids = disabled_by_channel.get(channel.id, set())
        enabled_clubs = Club.objects.exclude(status='suspended').exclude(id__in=disabled_ids)
        submitted_qs = FormSubmission.objects.filter(
            club__in=enabled_clubs,
            channel=channel,
            status__in=['pending', 'approved'],
        )
        if active_cycle:
            submitted_qs = submitted_qs.filter(cycle=active_cycle)
        submitted_ids = set(submitted_qs.values_list('club_id', flat=True))
        clubs, mine, other = warning_club_lists(
            enabled_clubs.exclude(id__in=submitted_ids).order_by('name')
        )
        if not clubs:
            continue
        alerts.append({
            'key': f'unsubmitted_{channel.id}',
            'title': f'未提交{channel.name}预警',
            'icon': 'error',
            'color': channel.alert_color or '#b3261e',
            'show_members': False,
            'empty_my': '暂无你负责的未提交社团',
            'my': mine,
            'my_count': len(mine),
            'other': other,
            'other_count': len(other),
            'count': len(clubs),
            'copy_title': f'未提交{channel.name}的社团名单',
            'copy_cycle': f'（{active_cycle.name}）' if active_cycle else '',
        })

    def _club_copy_info(club):
        president = club.president
        president_name = '未设置'
        if president:
            profile = getattr(president, 'profile', None)
            president_name = profile.get_full_name() if profile and profile.pk else president.get_full_name() or president.username
        staff_names = [relation.staff.get_full_name() for relation in club.responsible_staff.all()]
        return {
            'name': club.name,
            'members': club.members_count,
            'president': president_name,
            'staff': staff_names if staff_names else ['暂未分配负责干事'],
        }

    alerts_json = json.dumps([
        {
            'key': alert['key'],
            'title': alert['copy_title'],
            'cycle': alert['copy_cycle'],
            'show_members': alert['show_members'],
            'count': alert['count'],
            'my_count': alert['my_count'],
            'my': [_club_copy_info(club) for club in alert['my']],
            'all': [_club_copy_info(club) for club in [*alert['my'], *alert['other']]],
        }
        for alert in alerts
    ], ensure_ascii=False).replace('</', '<\\/')

    context = {
        'toggle_channels': toggle_channels,
        'toggle_colspan': 4 + len(toggle_channels),
        'clubs_page': clubs_page,
        'q': q,
        'low_member_threshold': low_member_threshold,
        # 统一告警数据
        'alerts': alerts,
        'alerts_json': alerts_json,
    }
    
    return render(request, 'clubs/staff/management.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def update_alert_threshold(request):
    """修改成员数量告警阈值（仅管理员）。"""
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role != 'admin':
        messages.error(request, _('仅管理员可以修改人数告警阈值'))
        return redirect('clubs:staff_management')

    from ..models import SiteSettings
    raw = (request.POST.get('low_member_threshold') or '').strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0
    if value < 1 or value > 999:
        messages.error(request, _('人数告警阈值需为 1-999 之间的整数'))
        return redirect('clubs:staff_management')

    site_settings = SiteSettings.get_settings()
    site_settings.low_member_alert_threshold = value
    site_settings.save(update_fields=['low_member_alert_threshold'])
    messages.success(request, f'人数告警阈值已更新为 {value} 人')
    return redirect('clubs:staff_management')


@login_required(login_url=settings.LOGIN_URL)
def verify_email(request):
    """邮箱验证视图"""
    user = request.user
    
    try:
        verification = user.email_verification
    except ObjectDoesNotExist:
        messages.error(request, _('邮箱验证记录不存在'))
        return redirect('clubs:user_dashboard')
    
    if verification.is_verified:
        messages.info(request, _('邮箱已验证'))
        return redirect('clubs:user_dashboard')
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        
        if not code:
            messages.error(request, _('验证码不能为空'))
            return render(request, 'clubs/auth/verify_email.html')
        
        success, message = verification.verify(code)
        
        if success:
            verification.is_verified = True
            verification.save()
            
            # 更新用户邮箱
            user.email = verification.email
            user.save()
            
            messages.success(request, _('邮箱验证成功！'))
            return redirect('clubs:user_dashboard')
        else:
            messages.error(request, message)
    
    context = {
        'email': verification.email,
        'created_at': verification.created_at,
        'expires_at': verification.expires_at,
    }
    return render(request, 'clubs/auth/verify_email.html', context)


@login_required(login_url=settings.LOGIN_URL)
def resend_verification_code(request):
    """重新发送验证码"""
    from django.core.cache import cache

    from ..email_utils import send_verification_email
    from ..models import EmailVerificationCode
    
    user = request.user
    
    try:
        verification = user.email_verification
    except ObjectDoesNotExist:
        messages.error(request, _('邮箱验证记录不存在'))
        return redirect('clubs:user_dashboard')
    
    if verification.is_verified:
        messages.info(request, _('邮箱已验证，无需重新发送'))
        return redirect('clubs:user_dashboard')

    cooldown_key = f'email_code_resend:{user.id}'
    if cache.get(cooldown_key):
        messages.error(request, _('发送过于频繁，请稍后再试'))
        return redirect('clubs:verify_email')
    
    # 生成新的验证码
    new_code = EmailVerificationCode.generate_code()
    verification.code = new_code
    verification.created_at = timezone.now()
    verification.expires_at = timezone.now() + timezone.timedelta(minutes=15)
    verification.failed_attempts = 0
    verification.save()
    
    # 发送邮件
    success, msg = send_verification_email(verification.email, new_code, user.username)
    
    if success:
        messages.success(request, msg)
        cache.set(cooldown_key, 1, 60)
    else:
        messages.error(request, msg)
    
    return redirect('clubs:verify_email')

@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(['GET', 'POST'])
def manage_department_staff(request):
    """部长管理本部门人员 - 仅部长可用"""
    user = request.user
    
    try:
        profile = user.profile
        if profile.staff_level != 'director':
            messages.error(request, _('您没有权限访问此页面，仅部长可以管理本部门人员'))
            return redirect('clubs:index')
    except UserProfile.DoesNotExist:
        messages.error(request, _('用户角色未配置'))
        return redirect('clubs:login')
    
    department_link = profile.department_link
    if not department_link:
        messages.error(request, _('您的部门信息未配置，无法管理部门人员'))
        return redirect('clubs:index')
    
    # 获取本部门的所有干事
    department_staff = UserProfile.objects.filter(
        role='staff',
        department_link=department_link
    ).select_related('user').order_by('staff_level', 'user__username')
    current_dept_name = department_link.name
    
    # 分类统计
    directors = department_staff.filter(staff_level='director')
    members = department_staff.filter(staff_level='member')
    
    context = {
        'department': current_dept_name,
        'department_key': current_dept_name,
        'all_staff': department_staff,
        'directors': directors,
        'members': members,
        'total_staff': department_staff.count(),
    }
    return render(request, 'clubs/staff/manage_department.html', context)






# ---- Dynamic form replacements -------------------------------------------------

def _dashboard_channel_card(channel, state, cycle, latest):
    enabled = True if state is None else state.is_enabled
    unavailable_reason = ''
    if channel.submission_policy == 'once_per_cycle':
        if not cycle:
            enabled = False
            unavailable_reason = '当前未开启周期'
    blocked = latest and latest.status in ['pending', 'approved'] and channel.submission_policy in ['once_total', 'once_per_cycle']
    if not enabled and not unavailable_reason:
        unavailable_reason = '暂未开放'
    can_submit = enabled and not blocked
    status = '未提交'
    status_class = 'pending'
    if latest:
        status = latest.get_status_display()
        status_class = latest.status
    return {
        'channel': channel,
        'cycle': cycle,
        'latest': latest,
        'status': status,
        'status_class': status_class,
        'can_submit': can_submit,
        'unavailable_reason': unavailable_reason,
        'is_cycle_channel': channel.submission_policy == 'once_per_cycle',
    }


@login_required(login_url='clubs:login')
def user_dashboard(request):
    user = request.user
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return redirect('clubs:login')

    if not is_president_mode(request):
        if has_president_officer(user):
            return render(request, 'clubs/user/president_identity_prompt.html', {
                'user': user,
                'president_club_count': Officer.objects.filter(
                    user_profile=profile,
                    position='president',
                    is_current=True,
                ).values('club_id').distinct().count(),
            })
        messages.error(request, _('您当前没有可管理的社团'))
        return redirect('clubs:index')

    staff_relations_prefetch = Prefetch(
        'responsible_staff',
        queryset=StaffClubRelation.objects.filter(is_active=True).select_related('staff__user'),
    )
    clubs = list(Club.objects.filter(
        officers__user_profile__user=user,
        officers__position='president',
        officers__is_current=True
    ).prefetch_related(staff_relations_prefetch).distinct())
    active_cycles_prefetch = Prefetch(
        'cycles',
        queryset=FormCycle.objects.filter(is_active=True).order_by('-sequence', '-starts_at'),
        to_attr='_active_cycles',
    )
    channels = externally_available_channels(list(
        FormChannel.objects.filter(is_active=True)
        .prefetch_related(active_cycles_prefetch, 'fields')
        .order_by('order', 'id')
    ))
    club_ids = [club.id for club in clubs]
    unread_total = FormSubmission.objects.filter(club_id__in=club_ids, status__in=['pending', 'rejected']).count()

    states = {
        (state.channel_id, state.club_id): state
        for state in FormChannelClubState.objects.filter(
            channel_id__in=[channel.id for channel in channels],
            club_id__in=club_ids,
        )
    }
    cycles = {
        channel.id: channel._active_cycles[0] if channel._active_cycles else None
        for channel in channels
    }
    submission_filter = Q()
    for channel in channels:
        if channel.submission_policy == 'once_per_cycle':
            cycle = cycles[channel.id]
            if cycle:
                submission_filter |= Q(channel_id=channel.id, cycle_id=cycle.id)
        else:
            submission_filter |= Q(channel_id=channel.id)
    latest_submissions = {}
    if club_ids and submission_filter:
        latest_submissions = {
            (submission.channel_id, submission.club_id): submission
            for submission in FormSubmission.objects.filter(
                submission_filter,
                club_id__in=club_ids,
                submitter=user,
            ).annotate(
                dashboard_row=Window(
                    expression=RowNumber(),
                    partition_by=[F('channel_id'), F('club_id')],
                    order_by=F('submitted_at').desc(),
                ),
            ).filter(dashboard_row=1)
        }

    clubs_with_submission_status = []
    for club in clubs:
        assigned_staff = [
            {
                'staff': relation.staff,
                'name': relation.staff.get_full_name(),
                'phone': relation.staff.phone or '--',
                'wechat': relation.staff.wechat or '--',
                'assigned_at': relation.assigned_at,
            }
            for relation in club.responsible_staff.all()
        ]
        action_cards = [
            _dashboard_channel_card(
                channel,
                states.get((channel.id, club.id)),
                cycles[channel.id],
                latest_submissions.get((channel.id, club.id)),
            )
            for channel in channels
        ]
        clubs_with_submission_status.append({
            'club': club,
            'assigned_staff': assigned_staff,
            'status_cards': [card for card in action_cards if card['channel'].show_unsubmitted_status],
            'action_cards': action_cards,
        })

    return render(request, 'clubs/user/dashboard.html', {
        'user': user,
        'clubs': clubs,
        'clubs_with_submission_status': clubs_with_submission_status,
        'club_count': len(clubs),
        'dynamic_channels': channels,
        'unread_approval_counts': {'total': unread_total, 'channels': {}},
    })
