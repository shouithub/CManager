from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .models import UserProfile, Club, ReviewSubmission, Reimbursement, ClubRegistrationRequest, ClubInfoChangeRequest, RegistrationPeriod, ClubRegistration, StaffClubRelation
from datetime import datetime
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.core.cache import cache
import time

# 登录限制配置
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes


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
        
        # 社长必须选择政治面貌
        if role == 'president':
            if not political_status or political_status == '':
                errors.append('社长必须选择政治面貌')
        
        if errors:
            return render(request, 'clubs/auth/register.html', {
                'errors': errors,
                'form_data': request.POST,
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
        profile = UserProfile.objects.create(
            user=user,
            role=role,
            status=status,
            real_name=real_name,
            student_id=student_id,
            phone=phone,
            wechat=wechat,
            political_status=political_status if role == 'president' else 'non_member'
        )
        
        messages.success(request, message_text)
        return redirect('clubs:login')
    
    return render(request, 'clubs/auth/register.html')


def user_login(request):
    """用户登录"""
    if request.user.is_authenticated:
        return redirect('clubs:index')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        client_ip = request.META.get('REMOTE_ADDR', '')

        if not username or not password:
            messages.error(request, '用户名和密码不能为空')
            return render(request, 'clubs/auth/login.html')

        # 检查是否被锁定（按用户名或 IP）
        lock_key_user = f'login_lock:user:{username}'
        lock_key_ip = f'login_lock:ip:{client_ip}'
        if cache.get(lock_key_user) or cache.get(lock_key_ip):
            messages.error(request, '登录尝试过多，请等待5分钟后再试，或联系管理员重置密码。')
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
                    messages.error(request, '您的账号正在审核中，请等待管理员批准！')
                    return render(request, 'clubs/auth/login.html', {
                        'username': username,
                    })

                login(request, user)
                messages.success(request, f'欢迎回来，{username}！')

                # 根据角色跳转
                if user.profile.role == 'admin':
                    return redirect('clubs:admin_dashboard')
                elif user.profile.role == 'staff':
                    return redirect('clubs:staff_dashboard')
                elif user.profile.role == 'president':
                    return redirect('clubs:user_dashboard')
                else:
                    return redirect('clubs:index')  # 普通用户跳转首页
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

            # 如果达到阈值，则设锁
            if user_attempts >= MAX_LOGIN_ATTEMPTS:
                cache.set(lock_key_user, True, LOGIN_WINDOW_SECONDS)
                cache.delete(attempts_key_user)
            if ip_attempts >= MAX_LOGIN_ATTEMPTS:
                cache.set(lock_key_ip, True, LOGIN_WINDOW_SECONDS)
                cache.delete(attempts_key_ip)

            # 如果已经被锁定，提示联系管理员重置密码
            if cache.get(lock_key_user) or cache.get(lock_key_ip):
                messages.error(request, '登录尝试过多，请等待5分钟后再试，或联系管理员重置密码。')
                from django.conf import settings
                return render(request, 'clubs/auth/login.html', {
                    'username': username,
                    'show_admin_reset_prompt': True,
                    'admin_contact_email': getattr(settings, 'ADMIN_CONTACT_EMAIL', ''),
                })

            messages.error(request, '用户名或密码错误')
            return render(request, 'clubs/auth/login.html', {
                'username': username,
            })
    
    return render(request, 'clubs/auth/login.html')


def user_logout(request):
    """用户登出"""
    logout(request)
    messages.success(request, '已登出')
    return redirect('clubs:index')



@login_required
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
            
            # 根据用户角色执行不同的删除逻辑
            if user.profile.role == 'admin':
                # 管理员账户删除逻辑
                # 直接删除用户，Django会级联删除相关数据
                user.delete()
                messages.success(request, f'管理员账户 {username} 已成功删除！')
            
            elif user.profile.role == 'president':
                # 社长账户删除逻辑
                # 1. 先将管理的社团的社长设置为空，保留社长提交的年审记录
                from clubs.models import Club
                clubs = Club.objects.filter(president=user)
                for club in clubs:
                    club.president = None
                    club.save()
                # 2. 删除用户账户
                user.delete()
                messages.success(request, f'社长账户 {username} 已成功删除！您的年审记录已被保留。')
            
            elif user.profile.role == 'staff':
                # 干事账户删除逻辑 - 完整清除所有数据
                # 1. 先删除干事在所有社团中的角色关联
                from clubs.models import Officer, SubmissionReview
                
                # 删除干事在社团中的干部记录
                Officer.objects.filter(user_profile=user.profile).delete()
                
                # 删除干事的审核记录
                SubmissionReview.objects.filter(reviewer=user).delete()
                
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
            messages.error(request, '用户名输入错误，账户删除失败！')
            
            # 重定向回修改账户设置页面
            return redirect('clubs:change_account_settings')
    
    # 如果不是POST请求，重定向到修改账户设置页面
    return redirect('clubs:change_account_settings')


@login_required(login_url='clubs:login')
def user_dashboard(request):
    """用户仪表板 - 显示该用户的社团"""
    user = request.user

    # 统一导入相关模型，避免 UnboundLocalError
    from .models import ClubRegistration, RegistrationPeriod, StaffClubRelation, ClubRegistrationRequest, Reimbursement, ActivityApplication, PresidentTransition

    # 检查用户角色
    try:
        profile = user.profile
        if profile.role == 'staff':
            return redirect('clubs:staff_dashboard')
    except UserProfile.DoesNotExist:
        return redirect('clubs:login')

    # 获取该社长的社团
    clubs = user.clubs_as_president.all()

    # 检查每个社团是否已提交当前年度的年审
    current_year = datetime.now().year
    clubs_with_submission_status = []
    unread_approval_counts = {
        'annual_review': 0,
        'registration': 0,
        'application': 0,
        'reimbursement': 0,
        'activity': 0,
        'transition': 0,
        'total': 0
    }
    for club in clubs:
        # 年审未读
        unread_annual_review = ReviewSubmission.objects.filter(
            club=club,
            status__in=['approved', 'rejected'],
            reviewed_at__isnull=False,
            is_read_by_president=False
        ).count()
        # 注册未读
        unread_registration = ClubRegistration.objects.filter(
            club=club,
            status__in=['approved', 'rejected'],
            reviewed_at__isnull=False,
            is_read=False
        ).count()
        # 申请未读（如 ClubRegistrationRequest）
        unread_application = ClubRegistrationRequest.objects.filter(
            president_id=getattr(club, 'president_id', None),
            status__in=['approved', 'rejected'],
            reviewed_at__isnull=False,
            is_read=False
        ).count()
        # 报销未读
        unread_reimbursement = Reimbursement.objects.filter(
            club=club,
            status__in=['approved', 'rejected'],
            reviewed_at__isnull=False,
            is_read=False
        ).count()
        # 活动申请未读
        unread_activity = ActivityApplication.objects.filter(
            club=club,
            status__in=['approved', 'rejected'],
            reviewed_at__isnull=False,
            is_read=False
        ).count()
        # 社长换届未读
        unread_transition = PresidentTransition.objects.filter(
            club=club,
            status__in=['approved', 'rejected'],
            reviewed_at__isnull=False,
            is_read=False
        ).count()
        # 统计
        unread_approval_counts['annual_review'] += unread_annual_review
        unread_approval_counts['registration'] += unread_registration
        unread_approval_counts['application'] += unread_application
        unread_approval_counts['reimbursement'] += unread_reimbursement
        unread_approval_counts['activity'] += unread_activity
        unread_approval_counts['transition'] += unread_transition
        # 社团卡片数据
        from .models import RegistrationPeriod, ClubRegistration, StaffClubRelation
        has_submitted_review = ReviewSubmission.objects.filter(
            club=club,
            submission_year=current_year
        ).exists()
        has_submitted_registration = False
        try:
            active_period = RegistrationPeriod.objects.get(is_active=True)
            has_submitted_registration = ClubRegistration.objects.filter(
                club=club,
                registration_period=active_period
            ).exists()
        except RegistrationPeriod.DoesNotExist:
            pass
        staff_relations = StaffClubRelation.objects.filter(club=club, is_active=True)
        assigned_staff = [
            {
                'name': relation.staff.get_full_name(),
                'phone': relation.staff.phone or '--',
                'wechat': relation.staff.wechat or '--',
                'assigned_at': relation.assigned_at
            }
            for relation in staff_relations
        ]
        
        club_data = {
            'club': club,
            'has_submitted_review': has_submitted_review,
            'has_submitted_registration': has_submitted_registration,
            'assigned_staff': assigned_staff,
            'unread_submissions_count': unread_annual_review + unread_registration + unread_application + unread_reimbursement + unread_activity + unread_transition,
            'review_enabled': club.review_enabled,
            'registration_enabled': club.registration_enabled
        }
        clubs_with_submission_status.append(club_data)
    unread_approval_counts['total'] = unread_approval_counts['annual_review'] + unread_approval_counts['registration'] + unread_approval_counts['application'] + unread_approval_counts['reimbursement'] + unread_approval_counts['activity'] + unread_approval_counts['transition']
    context = {
        'user': user,
        'clubs': clubs,
        'clubs_with_submission_status': clubs_with_submission_status,
        'club_count': clubs.count(),
        'current_year': current_year,
        'unread_approval_counts': unread_approval_counts
    }
    return render(request, 'clubs/user/dashboard.html', context)


@login_required(login_url='clubs:login')
def staff_dashboard(request):
    """干事仪表板 - 活动审核中心（干事和管理员可用）"""
    user = request.user
    
    # 检查用户角色
    try:
        profile = user.profile
        if profile.role != 'staff' and profile.role != 'admin':
            messages.error(request, '您没有权限访问此页面')
            return redirect('clubs:user_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, '用户角色未配置')
        return redirect('clubs:login')
    
    # 导入所需的模型
    from .models import (
        ActivityApplication, ReviewSubmission, ClubRegistrationRequest,
        ClubRegistration, ClubInfoChangeRequest, Reimbursement, PresidentTransition,
        StaffClubRelation, Club, RegistrationPeriod
    )
    from datetime import datetime
    
    # 获取待审核的数据 - 使用模板中期望的变量名
    pending_submissions = ReviewSubmission.objects.filter(status='pending').order_by('-submitted_at')
    pending_club_registrations = ClubRegistration.objects.filter(status='pending').order_by('-submitted_at')
    pending_club_info_changes = ClubInfoChangeRequest.objects.filter(status='pending').order_by('-submitted_at')
    pending_reimbursements = Reimbursement.objects.filter(status='pending').order_by('-submitted_at')
    # 活动申请 - 获取干事还未审核的申请
    pending_activity_applications = ActivityApplication.objects.filter(
        staff_approved__isnull=True  # 干事还未审核
    ).order_by('-submitted_at')
    pending_president_transitions = PresidentTransition.objects.filter(status='pending').order_by('-submitted_at')
    pending_registrations = ClubRegistrationRequest.objects.filter(status='pending').order_by('-submitted_at')
    
    # 为所有待审核项添加review_url属性
    for item in pending_submissions:
        item.review_url = f'/clubs/staff/review-submission/{item.id}/'
    for item in pending_club_registrations:
        item.review_url = f'/clubs/staff/review-club-registration/{item.id}/'
    for item in pending_registrations:
        item.review_url = f'/clubs/staff/review-club-registration-submission/{item.id}/'
    for item in pending_reimbursements:
        item.review_url = f'/clubs/staff/review-reimbursement/{item.id}/'
    for item in pending_activity_applications:
        item.review_url = f'/clubs/staff/review-activity-application/{item.id}/'
    for item in pending_president_transitions:
        item.review_url = f'/clubs/staff/review-president-transition/{item.id}/'
    
    # 计算待审核数量
    pending_counts = {
        'submissions': pending_submissions.count(),
        'club_registrations': pending_club_registrations.count(),
        'club_info_changes': pending_club_info_changes.count(),
        'reimbursements': pending_reimbursements.count(),
        'activity_applications': pending_activity_applications.count(),
        'president_transitions': pending_president_transitions.count(),
        'registrations': pending_registrations.count(),
    }
    
    # 计算总待审核数
    total_pending = sum(pending_counts.values())
    
    # 获取当前干事负责的社团ID
    staff_club_ids = StaffClubRelation.objects.filter(
        staff=user.profile, 
        is_active=True
    ).values_list('club_id', flat=True)
    
    # 获取成员数少于20人的社团，并预加载负责干事信息（排除停止状态的社团）
    clubs_with_low_members = Club.objects.filter(members_count__lt=20).exclude(status='suspended').order_by('members_count').prefetch_related('responsible_staff', 'responsible_staff__staff')
    
    # 获取所有社团
    clubs = Club.objects.all().order_by('name')
    
    # 获取当前年份
    current_year = datetime.now().year
    # 获取已开启年审的社团（排除停止状态的社团）
    enabled_review_clubs = Club.objects.filter(review_enabled=True).exclude(status='suspended')
    # 获取已提交本年度年审的社团ID
    submitted_clubs_ids = ReviewSubmission.objects.filter(
        club__in=enabled_review_clubs, 
        submission_year=current_year
    ).values_list('club_id', flat=True)
    # 获取已开启年审但未提交的社团，并预加载负责干事信息
    clubs_enabled_review_not_submitted = enabled_review_clubs.exclude(id__in=submitted_clubs_ids).prefetch_related('responsible_staff')
    
    # 分别获取当前干事负责的和其他的未提交年审社团
    clubs_enabled_review_not_submitted_my = clubs_enabled_review_not_submitted.filter(id__in=staff_club_ids)
    clubs_enabled_review_not_submitted_other = clubs_enabled_review_not_submitted.exclude(id__in=staff_club_ids)
    
    # 获取当前活跃的社团注册周期
    active_registration_period = RegistrationPeriod.objects.filter(is_active=True).first()
    clubs_not_registered = []
    clubs_not_registered_my = []
    clubs_not_registered_other = []
    if active_registration_period:
        # 获取本周期已提交注册的社团ID
        registered_clubs_ids = ClubRegistration.objects.filter(
            registration_period=active_registration_period
        ).values_list('club_id', flat=True)
        # 获取所有活跃社团中未提交注册的社团（排除停止状态的社团）
        clubs_not_registered = Club.objects.exclude(status='suspended').exclude(id__in=registered_clubs_ids).prefetch_related('responsible_staff')
        clubs_not_registered_my = clubs_not_registered.filter(id__in=staff_club_ids)
        clubs_not_registered_other = clubs_not_registered.exclude(id__in=staff_club_ids)
    
    # 计算是否所有社团都开启了年审和注册
    all_clubs = Club.objects.all()
    all_review_enabled = all_clubs.exists() and all_clubs.filter(review_enabled=True).count() == all_clubs.count()
    all_registration_enabled = all_clubs.exists() and all_clubs.filter(registration_enabled=True).count() == all_clubs.count()
    
    context = {
        'pending_submissions': pending_submissions,
        'pending_club_registrations': pending_club_registrations,
        'pending_club_info_changes': pending_club_info_changes,
        'pending_reimbursements': pending_reimbursements,
        'pending_activity_applications': pending_activity_applications,
        'pending_president_transitions': pending_president_transitions,
        'pending_registrations': pending_registrations,
        'pending_counts': pending_counts,
        'total_pending': total_pending,
        'clubs_with_low_members': clubs_with_low_members,
        'clubs_with_low_members_count': clubs_with_low_members.count(),
        'clubs': clubs,
        'clubs_enabled_review_not_submitted': clubs_enabled_review_not_submitted,
        'clubs_enabled_review_not_submitted_my': clubs_enabled_review_not_submitted_my,
        'clubs_enabled_review_not_submitted_other': clubs_enabled_review_not_submitted_other,
        'current_year': current_year,
        'active_registration_period': active_registration_period,
        'clubs_not_registered': clubs_not_registered,
        'clubs_not_registered_my': clubs_not_registered_my,
        'clubs_not_registered_other': clubs_not_registered_other,
        'clubs_not_registered_count': clubs_not_registered.count() if clubs_not_registered else 0,
        'all_review_enabled': all_review_enabled,
        'all_registration_enabled': all_registration_enabled,
        # 为stats-grid卡片添加单独的计数变量
        'pending_submissions_count': pending_counts['submissions'],
        'pending_reimbursements_count': pending_counts['reimbursements'],
        'pending_registrations_count': pending_counts['registrations'],
        'pending_club_registrations_count': pending_counts['club_registrations'],
        'pending_activity_applications_count': pending_counts['activity_applications'],
        'pending_president_transitions_count': pending_counts['president_transitions'],
    }
    
    return render(request, 'clubs/staff/dashboard.html', context)


@login_required(login_url='clubs:login')
def change_account_settings(request):
    """修改用户名和密码"""
    user = request.user
    errors = []
    success_messages = []
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        
        # 修改用户名
        if action == 'change_username':
            new_username = request.POST.get('new_username', '').strip()
            password = request.POST.get('password', '').strip()
            
            if not new_username:
                errors.append('新用户名不能为空')
            elif len(new_username) < 3:
                errors.append('用户名至少3个字符')
            elif User.objects.exclude(id=user.id).filter(username=new_username).exists():
                errors.append('用户名已被使用')
            elif not password:
                errors.append('密码不能为空')
            else:
                # 验证密码
                if not user.check_password(password):
                    errors.append('密码错误')
                else:
                    old_username = user.username
                    user.username = new_username
                    user.save()
                    success_messages.append(f'用户名已从"{old_username}"更改为"{new_username}"')
        
        # 修改密码
        elif action == 'change_password':
            old_password = request.POST.get('old_password', '').strip()
            new_password = request.POST.get('new_password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()
            
            if not old_password:
                errors.append('原密码不能为空')
            elif not new_password:
                errors.append('新密码不能为空')
            elif len(new_password) < 6:
                errors.append('新密码至少6个字符')
            elif new_password != confirm_password:
                errors.append('两次密码不一致')
            elif old_password == new_password:
                errors.append('新密码不能与原密码相同')
            else:
                # 验证原密码
                if not user.check_password(old_password):
                    errors.append('原密码错误')
                else:
                    user.set_password(new_password)
                    user.save()
                    success_messages.append('密码修改成功！请重新登录')
                    # 密码修改后需要重新登录
                    return redirect('clubs:login')
    
    context = {
        'user': user,
        'errors': errors,
        'success_messages': success_messages,
    }
    return render(request, 'clubs/auth/change_account_settings.html', context)


@login_required(login_url='clubs:login')
def manage_staff_clubs(request):
    """干事管理负责的社团"""
    user = request.user
    
    # 检查用户是否为干事
    try:
        profile = user.profile
        if profile.role != 'staff' and profile.role != 'admin':
            messages.error(request, '您没有权限访问此页面')
            return redirect('clubs:user_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, '用户角色未配置')
        return redirect('clubs:login')
    
    if request.method == 'POST':
        # 获取所有选中的社团ID
        selected_club_ids = request.POST.getlist('club_ids', [])
        
        # 更新StaffClubRelation
        from .models import StaffClubRelation, Club
        
        # 先将所有现有关联设置为inactive
        StaffClubRelation.objects.filter(staff=profile, is_active=True).update(is_active=False)
        
        # 为选中的社团创建或更新关联
        for club_id in selected_club_ids:
            try:
                club = Club.objects.get(id=club_id)
                StaffClubRelation.objects.update_or_create(
                    staff=profile,
                    club=club,
                    defaults={
                        'is_active': True,
                        'assigned_at': timezone.now().date()
                    }
                )
            except Club.DoesNotExist:
                pass
        
        messages.success(request, '负责社团设置成功！')
        return redirect('clubs:manage_staff_clubs')
    
    # 获取所有社团
    from .models import Club, StaffClubRelation
    all_clubs = Club.objects.all().order_by('name')
    
    # 获取当前干事已选中的社团ID
    active_relations = StaffClubRelation.objects.filter(staff=profile, is_active=True)
    selected_club_ids = [relation.club.id for relation in active_relations]
    
    context = {
        'user': user,
        'all_clubs': all_clubs,
        'selected_club_ids': selected_club_ids
    }
    
    return render(request, 'clubs/staff/manage_clubs.html', context)


@login_required(login_url='clubs:login')
def edit_profile(request):
    """用户修改个人信息 - 社长和干事"""
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        # 获取表单数据
        real_name = request.POST.get('real_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        wechat = request.POST.get('wechat', '').strip()
        student_id = request.POST.get('student_id', '').strip()
        political_status = request.POST.get('political_status', '')
        is_info_public = request.POST.get('is_info_public') == 'on'
        
        errors = []
        
        # 验证
        if not real_name:
            errors.append('真实姓名不能为空')
        if email and User.objects.filter(email=email).exclude(pk=user.pk).exists():
            errors.append('邮箱已被其他用户注册')
        if not phone:
            errors.append('电话不能为空')
        if not wechat:
            errors.append('微信不能为空')
        if not student_id:
            errors.append('学号不能为空')
        
        # 仅社长和干事需要填写政治面貌
        if profile.role in ['president', 'staff']:
            if not political_status:
                errors.append('政治面貌不能为空')
        
        if errors:
            context = {
                'user': user,
                'profile': profile,
                'errors': errors,
            }
            return render(request, 'clubs/user/edit_profile.html', context)
        
        # 保存用户信息
        user.email = email
        user.save()
        
        # 保存个人资料信息
        profile.real_name = real_name
        profile.phone = phone
        profile.wechat = wechat
        profile.student_id = student_id
        profile.is_info_public = is_info_public
        if profile.role in ['president', 'staff'] and political_status:
            profile.political_status = political_status
        profile.save()
        
        messages.success(request, '个人信息已成功更新')
        return redirect('clubs:user_dashboard')
    
    context = {
        'user': user,
        'profile': profile,
    }
    return render(request, 'clubs/user/edit_profile.html', context)


@login_required(login_url='login')
def staff_management(request):
    """干事社团管理页面（干事和管理员可用）"""
    user = request.user
    
    # 检查用户角色
    try:
        profile = user.profile
        if profile.role != 'staff' and profile.role != 'admin':
            messages.error(request, '您没有权限访问此页面')
            return redirect('clubs:user_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, '用户角色未配置')
        return redirect('clubs:login')
    
    from .models import Club, RegistrationPeriod, ReviewSubmission, ClubRegistration, StaffClubRelation
    from datetime import datetime
    
    # 计算全局年审功能状态
    all_review_enabled = not Club.objects.filter(review_enabled=False).exists()
    
    # 计算全局注册功能状态
    all_registration_enabled = not Club.objects.filter(registration_enabled=False).exists()
    
    # 获取当前活跃的社团注册周期
    active_registration_period = RegistrationPeriod.objects.filter(is_active=True).first()

    # 搜索 & 列表（分页）
    q = request.GET.get('q', '').strip()
    clubs_qs = Club.objects.all().order_by('name')
    if q:
        clubs_qs = clubs_qs.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(president__username__icontains=q) |
            Q(president__profile__real_name__icontains=q)
        )

    paginator = Paginator(clubs_qs, 20)  # 每页20条
    page_number = request.GET.get('page')
    clubs_page = paginator.get_page(page_number)
    
    # === 预警功能数据 ===
    # 获取当前干事负责的社团ID
    staff_club_ids = StaffClubRelation.objects.filter(
        staff=user.profile, 
        is_active=True
    ).values_list('club_id', flat=True)
    
    # 获取成员数少于20人的社团（排除停止状态的社团）
    clubs_with_low_members = Club.objects.filter(members_count__lt=20).exclude(status='suspended').order_by('members_count').prefetch_related('responsible_staff', 'responsible_staff__staff')
    
    # 获取当前年份
    current_year = datetime.now().year
    # 获取已开启年审的社团（排除停止状态的社团）
    enabled_review_clubs = Club.objects.filter(review_enabled=True).exclude(status='suspended')
    # 获取已提交本年度年审的社团ID
    submitted_clubs_ids = ReviewSubmission.objects.filter(
        club__in=enabled_review_clubs, 
        submission_year=current_year
    ).values_list('club_id', flat=True)
    # 获取已开启年审但未提交的社团
    clubs_enabled_review_not_submitted = enabled_review_clubs.exclude(id__in=submitted_clubs_ids).prefetch_related('responsible_staff')
    
    # 分别获取当前干事负责的和其他的未提交年审社团
    clubs_enabled_review_not_submitted_my = clubs_enabled_review_not_submitted.filter(id__in=staff_club_ids)
    clubs_enabled_review_not_submitted_other = clubs_enabled_review_not_submitted.exclude(id__in=staff_club_ids)
    
    context = {
        'all_review_enabled': all_review_enabled,
        'all_registration_enabled': all_registration_enabled,
        'active_registration_period': active_registration_period,
        'clubs_page': clubs_page,
        'q': q,
        # 预警数据
        'clubs_with_low_members': clubs_with_low_members,
        'clubs_with_low_members_count': clubs_with_low_members.count(),
        'clubs_enabled_review_not_submitted': clubs_enabled_review_not_submitted,
        'clubs_enabled_review_not_submitted_my': clubs_enabled_review_not_submitted_my,
        'clubs_enabled_review_not_submitted_other': clubs_enabled_review_not_submitted_other,
        'current_year': current_year,
    }
    
    return render(request, 'clubs/staff/management.html', context)


@login_required(login_url='login')
def verify_email(request):
    """邮箱验证视图"""
    user = request.user
    
    try:
        verification = user.email_verification
    except:
        messages.error(request, '邮箱验证记录不存在')
        return redirect('clubs:user_dashboard')
    
    if verification.is_verified:
        messages.info(request, '邮箱已验证')
        return redirect('clubs:user_dashboard')
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        
        if not code:
            messages.error(request, '验证码不能为空')
            return render(request, 'clubs/auth/verify_email.html')
        
        success, message = verification.verify(code)
        
        if success:
            verification.is_verified = True
            verification.save()
            
            # 更新用户邮箱
            user.email = verification.email
            user.save()
            
            messages.success(request, '邮箱验证成功！')
            return redirect('clubs:user_dashboard')
        else:
            messages.error(request, message)
    
    context = {
        'email': verification.email,
        'created_at': verification.created_at,
        'expires_at': verification.expires_at,
    }
    return render(request, 'clubs/auth/verify_email.html', context)


@login_required(login_url='login')
def resend_verification_code(request):
    """重新发送验证码"""
    from .email_utils import send_verification_email
    from .models import EmailVerificationCode
    
    user = request.user
    
    try:
        verification = user.email_verification
    except:
        messages.error(request, '邮箱验证记录不存在')
        return redirect('clubs:user_dashboard')
    
    if verification.is_verified:
        messages.info(request, '邮箱已验证，无需重新发送')
        return redirect('clubs:user_dashboard')
    
    # 生成新的验证码
    new_code = EmailVerificationCode.generate_code()
    verification.code = new_code
    verification.created_at = timezone.now()
    verification.expires_at = timezone.now() + timezone.timedelta(minutes=15)
    verification.save()
    
    # 发送邮件
    success, msg = send_verification_email(verification.email, new_code, user.username)
    
    if success:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    
    return redirect('clubs:verify_email')

@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def manage_department_staff(request):
    """部长管理本部门人员 - 仅部长可用"""
    user = request.user
    
    try:
        profile = user.profile
        if profile.role != 'staff' or profile.staff_level != 'director':
            messages.error(request, '您没有权限访问此页面，仅部长可以管理本部门人员')
            return redirect('clubs:staff_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, '用户角色未配置')
        return redirect('clubs:login')
    
    department = profile.department
    
    if not department:
        messages.error(request, '您的部门信息未配置，无法管理部门人员')
        return redirect('clubs:staff_dashboard')
    
    # 获取本部门的所有干事
    department_staff = UserProfile.objects.filter(
        role='staff',
        department=department
    ).select_related('user').order_by('staff_level', 'user__username')
    
    # 分类统计
    directors = department_staff.filter(staff_level='director')
    members = department_staff.filter(staff_level='member')
    
    context = {
        'department': profile.get_department_display(),
        'department_key': department,
        'all_staff': department_staff,
        'directors': directors,
        'members': members,
        'total_staff': department_staff.count(),
    }
    return render(request, 'clubs/staff/manage_department.html', context)


@login_required
def staff_dashboard_home(request):
    """干事和管理员主页 - 显示部门介绍"""
    from .models import DepartmentIntroduction
    
    profile = request.user.profile
    
    # 只允许干事和管理员访问
    if profile.role not in ['staff', 'admin']:
        messages.error(request, '无权访问此页面')
        return redirect('clubs:index')
    
    # 获取所有部门介绍
    departments = DepartmentIntroduction.objects.all().order_by('department')
    
    # 获取组织统计
    total_staff = UserProfile.objects.filter(role='staff', status='approved').count()
    total_directors = UserProfile.objects.filter(role='staff', staff_level='director').count()
    total_members = UserProfile.objects.filter(role='staff', staff_level='member').count()
    
    context = {
        'departments': departments,
        'total_staff': total_staff,
        'total_directors': total_directors,
        'total_members': total_members,
        'can_edit': profile.role == 'admin',
    }
    
    return render(request, 'clubs/staff/home.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def edit_department_intro(request, department):
    """编辑部门介绍（仅管理员）"""
    from .models import DepartmentIntroduction
    
    profile = request.user.profile
    
    # 只允许管理员编辑
    if profile.role != 'admin':
        messages.error(request, '无权编辑部门介绍')
        return redirect('clubs:staff_dashboard_home')
    
    dept_intro = DepartmentIntroduction.objects.filter(department=department).first()
    
    if request.method == 'POST':
        description = request.POST.get('description', '').strip()
        highlights = request.POST.get('highlights', '').strip()
        icon = request.POST.get('icon', 'work').strip()
        
        if not description:
            messages.error(request, '职责描述不能为空')
        else:
            if dept_intro:
                dept_intro.description = description
                dept_intro.highlights = highlights
                dept_intro.icon = icon
                dept_intro.updated_by = request.user
                dept_intro.save()
                messages.success(request, f'{dept_intro.get_department_display()}介绍已更新')
            else:
                dept_intro = DepartmentIntroduction.objects.create(
                    department=department,
                    description=description,
                    highlights=highlights,
                    icon=icon,
                    updated_by=request.user
                )
                messages.success(request, f'{dept_intro.get_department_display()}介绍已创建')
            
            return redirect('clubs:staff_dashboard_home')
    
    context = {
        'dept_intro': dept_intro,
        'department': department,
    }
    
    return render(request, 'clubs/staff/edit_department_intro.html', context)