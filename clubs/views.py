# type: ignore[attr-defined]
"""
Django 社团管理系统视图模块

此文件包含大量 Django 模型交互代码。由于 Pylance 无法完全识别 Django ORM 的动态特性
（如自动生成的 id 字段、相关管理器等），我们在文件顶部添加全局类型忽略指令。
这对代码的实际功能没有影响，只是消除了 IDE 中的假性错误警告。
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from django.conf import settings
from django.http import HttpResponse, FileResponse, HttpResponseForbidden, JsonResponse
from django.db.models import Q
import os
import urllib.parse
import os
import tempfile
from .models import Club, Officer, ReviewSubmission, UserProfile, Reimbursement, ClubRegistrationRequest, ClubApplicationReview, ClubRegistration, Template, Announcement, StaffClubRelation, SubmissionReview, ClubRegistrationReview, RegistrationPeriod, PresidentTransition, ActivityApplication, SMTPConfig, CarouselImage, ActivityApplicationHistory, MaterialRequirement, SubmittedFile, Department, Room, RoomBooking, TimeSlot
from django.contrib.contenttypes.models import ContentType
import shutil
from PIL import Image


def rename_uploaded_file(file, club_name, request_type, material_type):
    """
    为上传的文件重命名为：社团名-请求类型-文件类型
    例如：社团名-年审-自查表.docx
    
    Args:
        file: 上传的文件对象
        club_name: 社团名称
        request_type: 请求类型（'年审', '报销', '注册'等）
        material_type: 文件类型（'自查表', '报销凭证'等）
    
    Returns:
        修改后的文件对象
    """
    if not file:
        return file
    
    # 获取文件扩展名
    file_ext = os.path.splitext(file.name)[1]
    
    # 生成新的文件名
    new_filename = f"{club_name}-{request_type}-{material_type}{file_ext}"
    
    # 清理特殊字符，避免文件系统问题
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        new_filename = new_filename.replace(char, '_')
    
    # 修改文件名
    file.name = new_filename
    return file


def _is_president(user):
    """检查用户是否为社长"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'president'
    except UserProfile.DoesNotExist:
        return False


def _is_staff(user):
    """检查用户是否为干事"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'staff'
    except UserProfile.DoesNotExist:
        return False


def _is_admin(user):
    """检查用户是否为管理员"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'admin'
    except UserProfile.DoesNotExist:
        return False


def is_staff_or_admin(user):
    """返回用户是否为干事或管理员（布尔）。超级用户也视为管理员。"""
    try:
        # 超级用户始终有管理员权限
        if getattr(user, 'is_superuser', False):
            return True
        return getattr(user, 'profile', None) and user.profile.role in ['staff', 'admin']
    except Exception:
        return False


def _validate_word_file(file, field_name):
    """验证上传文件是否为 Word 格式（.doc/.docx）。

    返回: 错误消息字符串或 None
    """
    if not file:
        return f"{field_name} 文件不能为空"
    valid_extensions = ['.doc', '.docx']
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in valid_extensions:
        return f"{field_name} 必须为 Word 文档 (.doc 或 .docx)"
    return None


def _validate_file_allowed(file, field_name, allowed_extensions, allowed_mimetypes=None):
    """通用文件类型验证函数。返回错误消息或 None。"""
    if not file:
        return f"{field_name} 文件不能为空"
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        return f"{field_name} 的文件类型不被允许（允许的后缀：{', '.join(allowed_extensions)}）"
    # 可选的 mime 类型检查（如果需要）
    return None


def get_dynamic_materials_list(target_obj, db_req_type):
    """
    辅助函数：获取动态材料列表
    返回: list of dicts suitable for _materials_display.html
    """
    from .models import MaterialRequirement, SubmittedFile
    from django.contrib.contenttypes.models import ContentType
    
    requirements = MaterialRequirement.objects.filter(request_type=db_req_type, is_active=True).order_by('order')
    m_list = []
    
    try:
        content_type = ContentType.objects.get_for_model(target_obj)
    except:
        return []
        
    # 旧字段映射表 - 用于兼容旧数据
    legacy_field_map = {
        'club_registration': {
            '社团注册申请表': 'registration_form',
            '学生社团基础信息表': 'basic_info_form',
            '会费表或免收会费说明书': 'membership_fee_form',
            '社团主要负责人变动申请': 'leader_change_application',
            '社团大会会议记录': 'meeting_minutes',
            '社团名称变更申请表': 'name_change_application',
            '社团指导老师变动申请表': 'advisor_change_application',
            '社团业务指导单位变动申请表': 'business_advisor_change_application',
            '新媒体平台建立申请表': 'new_media_application'
        },
        'annual_review': {
            '自查表': 'self_assessment_form',
            '社团章程': 'club_constitution',
            '负责人学习及工作情况报告': 'leader_learning_work_report',
            '社团年度活动清单': 'annual_activity_list',
            '指导教师履职情况报告': 'advisor_performance_report',
            '年度财务情况报告': 'financial_report',
            '社团成员构成表': 'member_composition_list',
            '新媒体账号报告（如适用）': 'new_media_account_report',
            '其他材料（如适用）': 'other_materials'
        }
    }

    for req in requirements:
        # 1. 尝试查找 SubmittedFile (新逻辑)
        submitted_file = SubmittedFile.objects.filter(
            content_type=content_type, 
            object_id=target_obj.id, 
            requirement=req
        ).first()
        
        file_obj = None
        if submitted_file:
            file_obj = submitted_file.file
        
        # 2. 如果没有找到，尝试从对象字段获取 (旧逻辑兼容)
        if not file_obj and db_req_type in legacy_field_map:
            field_name = legacy_field_map[db_req_type].get(req.name)
            if field_name and hasattr(target_obj, field_name):
                file_field = getattr(target_obj, field_name)
                if file_field:
                    file_obj = file_field
        
        if file_obj:
            # 确定标识符：使用req_id前缀
            field_identifier = f"req_{req.id}"
            
            item = {
                'field_name': field_identifier,
                'field': field_identifier,
                'label': req.name,
                'name': req.name,
                'icon': 'description', # 默认图标
                'file': file_obj,
                'req_id': req.id
            }
            m_list.append(item)
    
    return m_list


import json

@login_required(login_url=settings.LOGIN_URL)
def download_file(request):
    """自定义文件下载视图，用于处理文件下载并重命名
    
    GET参数:
        file_path: 文件的相对路径（相对于MEDIA_ROOT）
        filename: 下载时使用的文件名
    """
    # 从GET请求中获取参数
    file_path = request.GET.get('file_path', '')
    filename = request.GET.get('filename', '')
    
    # 添加调试信息
    debug_info = {
        'received_params': {
            'file_path': file_path,
            'filename': filename,
        },
        'processing_steps': [],
        'settings_info': {
            'MEDIA_ROOT': str(getattr(settings, 'MEDIA_ROOT', 'Not set')),
            'MEDIA_URL': str(getattr(settings, 'MEDIA_URL', 'Not set')),
            'BASE_DIR': str(getattr(settings, 'BASE_DIR', 'Not set')),
        }
    }
    
    debug_info['processing_steps'].append(f"Received parameters - file_path: {file_path}, filename: {filename}")
    
    # 检查必要参数
    if not file_path:
        debug_info['processing_steps'].append('Missing file_path parameter')
        response = HttpResponse("缺少文件路径参数", status=400)
        response['X-Debug-Info'] = json.dumps(debug_info, ensure_ascii=False)
        return response
    
    # 构建完整的文件路径
    # 清理file_path，移除可能的查询参数或片段
    if '?' in file_path:
        file_path = file_path.split('?')[0]
        debug_info['processing_steps'].append(f"Removed query parameters: {file_path}")
    if '#' in file_path:
        file_path = file_path.split('#')[0]
        debug_info['processing_steps'].append(f"Removed fragment: {file_path}")
    
    # 如果file_path包含完整URL，提取相对路径
    if file_path.startswith('http://') or file_path.startswith('https://'):
        # 移除域名部分，获取相对路径
        from urllib.parse import urlparse
        parsed_url = urlparse(file_path)
        file_path = parsed_url.path
        debug_info['processing_steps'].append(f"Extracted path from URL: {file_path}")
        
        # 如果路径以MEDIA_URL开头，移除它
        media_url = settings.MEDIA_URL
        if file_path.startswith(media_url):
            file_path = file_path[len(media_url):]
            debug_info['processing_steps'].append(f"Removed MEDIA_URL prefix: {file_path}")
        elif file_path.startswith('/' + media_url):
            file_path = file_path[len('/' + media_url):]
            debug_info['processing_steps'].append(f"Removed leading slash and MEDIA_URL prefix: {file_path}")
    elif file_path.startswith('/'):
        # 如果路径以斜杠开头，移除它
        file_path = file_path[1:]
        debug_info['processing_steps'].append(f"Removed leading slash: {file_path}")
    
    # 特别处理以media/开头的路径
    if file_path.startswith('media/'):
        file_path = file_path[6:]  # 移除'media/'前缀
        debug_info['processing_steps'].append(f"Removed media/ prefix: {file_path}")
    
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    debug_info['processing_steps'].append(f"Constructed full path: {full_path}")
    debug_info['processing_steps'].append(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
    
    # 检查文件是否存在
    if not os.path.exists(full_path):
        debug_info['processing_steps'].append(f"File not found at primary path: {full_path}")
        # 尝试其他可能的路径
        alternative_path = os.path.join(settings.BASE_DIR, file_path)
        debug_info['processing_steps'].append(f"Trying alternative path: {alternative_path}")
        if os.path.exists(alternative_path):
            full_path = alternative_path
            debug_info['processing_steps'].append(f"Found file at alternative path: {full_path}")
        else:
            debug_info['processing_steps'].append(f"Alternative path also not found: {alternative_path}")
            response = HttpResponse(json.dumps(debug_info, ensure_ascii=False, indent=2), content_type='application/json', status=404)
            response['X-Debug-Info'] = json.dumps(debug_info, ensure_ascii=False)
            return response
    
    debug_info['processing_steps'].append(f"File exists: {full_path}")
    
    # 获取文件大小
    try:
        file_size = os.path.getsize(full_path)
        debug_info['processing_steps'].append(f"File size: {file_size} bytes")
    except Exception as e:
        debug_info['processing_steps'].append(f"Error getting file size: {str(e)}")
        file_size = None
    
    # 如果没有提供文件名，使用原始文件名
    if not filename:
        filename = os.path.basename(full_path)
        debug_info['processing_steps'].append(f"Using default filename: {filename}")
    else:
        # 确保文件名是安全的（移除路径分隔符）
        filename = os.path.basename(filename)
        debug_info['processing_steps'].append(f"Using provided filename: {filename}")
    
    # 添加最终调试信息
    debug_info['processing_steps'].append(f"Final filename: {filename}")
    
    # 创建文件响应
    try:
        # 打开文件并创建响应
        with open(full_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            
            # 处理文件名编码以支持中文
            ascii_filename = filename.encode('ascii', 'ignore').decode('ascii')
            utf8_filename = filename.encode('utf-8')
            
            # 设置Content-Disposition头以指定下载文件名
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{urllib.parse.quote(utf8_filename)}"
            debug_info['processing_steps'].append(f"Set Content-Disposition: attachment; filename*=UTF-8''{urllib.parse.quote(utf8_filename)}")
            
            # 添加文件信息到响应头
            if file_size:
                response['Content-Length'] = str(file_size)
                debug_info['processing_steps'].append(f"Set Content-Length: {file_size}")
            
            # 添加调试信息到响应头
            response['X-Debug-Info'] = json.dumps(debug_info, ensure_ascii=False)
            
            return response
            
    except Exception as e:
        debug_info['processing_steps'].append(f"Error opening file: {str(e)}")
        response = HttpResponse(json.dumps(debug_info, ensure_ascii=False, indent=2), content_type='application/json', status=500)
        response['X-Debug-Info'] = json.dumps(debug_info, ensure_ascii=False)
        return response



@login_required(login_url='clubs:login')
def user_detail(request, user_id):
    """用户详情页 - 显示用户公开信息及关联社团/干事"""
    target_user = get_object_or_404(User, pk=user_id)
    from .models import StaffClubRelation, Officer
    
    context = {
        'target_user': target_user,
        'responsible_clubs': [],
        'affiliated_clubs': [],
        'affiliated_clubs_with_staff': [],
        'responsible_staff_list': [],
        'is_staff_of_viewing_president': False,
    }
    
    try:
        profile = target_user.profile
        
        # 检查是否为当前查看者(社长)负责的社团的干事
        if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role == 'president':
            if profile.role == 'staff':
                # 获取该干事负责的社团
                staff_club_ids = StaffClubRelation.objects.filter(
                    staff=profile, 
                    is_active=True
                ).values_list('club_id', flat=True)
                
                # 获取当前用户(社长)负责的社团
                president_club_ids = Officer.objects.filter(
                    user_profile=request.user.profile,
                    position='president',
                    is_current=True
                ).values_list('club_id', flat=True)
                
                # 检查是否有交集
                if set(staff_club_ids) & set(president_club_ids):
                    context['is_staff_of_viewing_president'] = True

        # 如果是干事或管理员，获取负责的社团
        if profile.role in ['staff', 'admin']:
            context['responsible_clubs'] = StaffClubRelation.objects.filter(
                staff=profile,
                is_active=True
            ).select_related('club')
            
        # 如果是社长，获取所属社团及对应的负责干事
        if profile.role == 'president':
            # 获取当前担任职位的社团
            officer_positions = Officer.objects.filter(
                user_profile=profile,
                is_current=True
            ).select_related('club')
            context['affiliated_clubs'] = officer_positions
            
            # 获取这些社团对应的负责干事
            club_ids = officer_positions.values_list('club_id', flat=True)
            staff_relations = StaffClubRelation.objects.filter(
                club_id__in=club_ids,
                is_active=True
            ).select_related('staff', 'staff__user').distinct()
            
            staff_by_club = {}
            staff_seen_by_club = {}
            for relation in staff_relations:
                club_id = relation.club_id
                staff_by_club.setdefault(club_id, [])
                staff_seen_by_club.setdefault(club_id, set())
                if relation.staff_id in staff_seen_by_club[club_id]:
                    continue
                staff_by_club[club_id].append(relation.staff)
                staff_seen_by_club[club_id].add(relation.staff_id)

            context['affiliated_clubs_with_staff'] = [
                {
                    'officer': officer,
                    'club': officer.club,
                    'staff_list': staff_by_club.get(officer.club_id, []),
                }
                for officer in officer_positions
            ]
            
    except UserProfile.DoesNotExist:
        pass
        
    return render(request, 'clubs/user_detail.html', context)


def index(request):
    """首页 - 显示部门介绍、社团信息和最新公告"""
    from .models import Department
    
    # 未登录用户显示部门介绍和公告
    if not request.user.is_authenticated:
        departments = Department.objects.all().order_by('order')
        announcements = Announcement.objects.filter(status='published').order_by('-published_at')[:5]
        carousel_images = CarouselImage.objects.filter(is_active=True).order_by('-uploaded_at')
        
        context = {
            'is_anonymous': True,
            'departments': departments,
            'announcements': announcements,
            'carousel_images': carousel_images,
        }
        return render(request, 'clubs/index.html', context)
    
    # 社长访问首页：跳转到社长工作台
    # if _is_president(request.user):
    #    return redirect('clubs:user_dashboard')
    
    # 检查是否为干事或管理员
    staff_admin = is_staff_or_admin(request.user)
    
    if staff_admin:
        # 为干事和管理员显示部门介绍和树状图
        from .models import StaffClubRelation
        
        # 获取部门介绍
        departments = Department.objects.all().order_by('order')
        
        # 获取组织统计
        total_staff = UserProfile.objects.filter(role='staff', status='approved').count()
        total_directors = UserProfile.objects.filter(role='staff', staff_level='director').count()
        total_members = UserProfile.objects.filter(role='staff', staff_level='member').count()
        
        # 获取所有干事用户
        staff_users = UserProfile.objects.filter(role='staff', status='approved').select_related('user')
        
        # 构建树状图数据
        staff_tree_data = []
        for staff_profile in staff_users:
            # 获取该干事负责的社团
            relations = StaffClubRelation.objects.filter(
                staff=staff_profile, 
                is_active=True
            ).select_related('club')
            
            clubs = []
            for relation in relations:
                clubs.append({
                    'id': relation.club.id,  # type: ignore[attr-defined]
                    'name': relation.club.name,
                    'status': relation.club.status,
                    'members_count': relation.club.members_count,
                    'founded_date': relation.club.founded_date,
                    'description': relation.club.description,
                })
            
            staff_tree_data.append({
                'staff_id': staff_profile.id,  # type: ignore[attr-defined]
                'staff_name': staff_profile.get_full_name(),
                'staff_username': staff_profile.user.username,
                'clubs': clubs,
                'clubs_count': len(clubs),
            })
        
        # 获取最新的已发布公告
        announcements = Announcement.objects.filter(status='published').order_by('-published_at')[:5]
        
        # 获取轮播图片
        carousel_images = CarouselImage.objects.filter(is_active=True).order_by('order', '-uploaded_at')
        
        context = {
            'is_staff_or_admin': staff_admin,
            'departments': departments,
            'total_staff': total_staff,
            'total_directors': total_directors,
            'total_members': total_members,
            'can_edit': request.user.profile.role == 'admin',
            'staff_tree_data': staff_tree_data,
            'announcements': announcements,
            'carousel_images': carousel_images,
            'total_clubs': Club.objects.count(),
        }
        return render(request, 'clubs/index.html', context)
    
    # 普通用户显示所有社团
    clubs = Club.objects.all()
    # 获取最新的已发布公告
    announcements = Announcement.objects.filter(status='published').order_by('-published_at')[:5]
    
    # 获取轮播图片
    carousel_images = CarouselImage.objects.filter(is_active=True).order_by('order', '-uploaded_at')
    
    # 获取部门介绍
    departments = Department.objects.all().order_by('order')
    
    # 为每个社团添加当前用户是否是社长的信息（作为字典存储）
    clubs_data = []
    for club in clubs:
        is_president = Officer.objects.filter(
            user_profile__user=request.user,
            club=club,
            position='president',
            is_current=True
        ).exists()
        clubs_data.append({
            'club': club,
            'is_president': is_president
        })
    
    context = {
        'clubs_data': clubs_data,
        'clubs': clubs,
        'announcements': announcements,
        'carousel_images': carousel_images,
        'departments': departments,
        'total_clubs': clubs.count(),
    }
    return render(request, 'clubs/index.html', context)


def club_detail(request, club_id):
    """社团详情页"""
    club = get_object_or_404(Club, pk=club_id)
    officers = Officer.objects.filter(club=club, is_current=True)
    
    # 检查当前用户是否为该社团的社长
    is_president = False
    is_staff = False
    if request.user.is_authenticated:
        # 检查是否为社长
        is_president = Officer.objects.filter(
            user_profile__user=request.user,
            club=club,
            position='president',
            is_current=True
        ).exists()
        
        # 检查是否为干事或管理员
        try:
            is_staff = request.user.profile.role in ['staff', 'admin']
        except:
            is_staff = False
    
    context = {
        'club': club,
        'officers': officers,
        'is_president': is_president,
        'is_staff': is_staff,
    }
    return render(request, 'clubs/club_detail.html', context)


@login_required(login_url='clubs:login')
@require_http_methods(["GET", "POST"])
def register_club(request):
    """社团注册申请 - 仅社长可用（需要干事审核批准）"""
    if not _is_president(request.user):
        messages.error(request, '仅社长可以注册社团')
        return redirect('clubs:index')
    
    # 获取当前用户的实名信息
    try:
        current_user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, '用户实名信息未配置，请联系管理员')
        return redirect('clubs:user_dashboard')
    
    # 获取所有其他社长的用户信息，允许选择其他用户作为申请人
    other_presidents = UserProfile.objects.filter(role='president').exclude(user=request.user).select_related('user')
    
    # 获取社团创建模板
    registration_templates = Template.objects.filter(template_type='club_creation', is_active=True)
    
    # 获取材料要求
    requirements = MaterialRequirement.objects.filter(
        request_type='club_application', 
        is_active=True
    ).order_by('order')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        founded_date = request.POST.get('founded_date', '')
        members_count = request.POST.get('members_count', '').strip()
        president_profile_id = request.POST.get('president_profile_id', '')
        
        # 验证
        errors = []
        if not name:
            errors.append('社团名称不能为空')
        if Club.objects.filter(name=name).exists():
            errors.append('社团名称已存在')
        if ClubRegistrationRequest.objects.filter(club_name=name, status='pending').exists():
            errors.append('该社团已有待审核的注册申请')
        if not founded_date:
            errors.append('成立日期不能为空')
        if not members_count:
            errors.append('社团人数不能为空')
        else:
            try:
                members_count = int(members_count)
                if members_count <= 0:
                    errors.append('社团人数必须大于0')
            except ValueError:
                errors.append('社团人数必须是数字')
        
        # 验证上传的文件（动态材料）
        uploaded_files_map = {} # req.id -> file_obj
        
        for req in requirements:
            file_key = f'material_{req.id}'
            file_obj = request.FILES.get(file_key)
            
            if req.is_required and not file_obj:
                errors.append(f'请上传{req.name}')
                continue
                
            if file_obj:
                # 验证文件类型
                if req.allowed_extensions:
                    allowed_exts = [ext.strip().lower() for ext in req.allowed_extensions.split(',')]
                    file_ext = os.path.splitext(file_obj.name)[1].lower()
                    if file_ext not in allowed_exts:
                        errors.append(f'{req.name}格式不正确，支持的格式: {req.allowed_extensions}')
                
                # 验证文件大小
                if req.max_size_mb > 0:
                    if file_obj.size > req.max_size_mb * 1024 * 1024:
                        errors.append(f'{req.name}文件过大，最大允许{req.max_size_mb}MB')
                
                # 重命名文件 (使用 helper)
                file_obj = rename_uploaded_file(file_obj, name, '社团申请', req.name)
                
                uploaded_files_map[req.id] = file_obj
        
        # 确定申请人的实名信息
        if president_profile_id:
            # 选择其他用户
            try:
                president_profile = UserProfile.objects.get(id=president_profile_id)
                if president_profile.role != 'president':
                    errors.append('所选用户不是社长')
            except UserProfile.DoesNotExist:
                errors.append('所选用户不存在')
        else:
            # 使用当前用户
            president_profile = current_user_profile
        
        if errors:
            context = {
                'errors': errors,
                'form_data': request.POST,
                'current_user_profile': current_user_profile,
                'other_presidents': other_presidents,
                'registration_templates': registration_templates,
                'requirements': requirements,
            }
            return render(request, 'clubs/user/register_club.html', context)
        
        # 创建社团注册申请（待审核）
        registration_request = ClubRegistrationRequest.objects.create(
            club_name=name,
            description=description,
            founded_date=founded_date,
            members_count=members_count,
            president_name=president_profile.real_name,
            president_id=president_profile.student_id,
            president_email=president_profile.user.email,
            requested_by=request.user,
            status='pending'
        )
        
        # 创建 SubmittedFile 记录
        content_type = ContentType.objects.get_for_model(ClubRegistrationRequest)
        for req in requirements:
            if req.id in uploaded_files_map:
                SubmittedFile.objects.create(
                    content_type=content_type,
                    object_id=registration_request.id,
                    requirement=req,
                    file=uploaded_files_map[req.id]
                )
        
        messages.success(request, f'社团注册申请已提交，等待干事审核！')
        return redirect('clubs:user_dashboard')
    
    context = {
        'current_user_profile': current_user_profile,
        'other_presidents': other_presidents,
        'registration_templates': registration_templates,
        'requirements': requirements,
    }
    return render(request, 'clubs/user/register_club.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def edit_rejected_review(request, club_id):
    # 获取查询参数
    request_id = request.GET.get('request_id')
    if not request_id:
        messages.error(request, '缺少请求ID参数')
        return redirect('clubs:user_dashboard')
    """统一处理修改被拒绝材料的请求 - 仅社长可用
    支持的请求类型：
    - club_application: 社团申请
    - club_registration: 社团注册
    - review: 社团年审
    - club_info_change: 社团信息变更
    """
    
    # 获取请求类型
    request_type = request.GET.get('type', 'review')
    
    # 对于社团申请类型，不需要检查是否是社长（因为申请时还没有社团）
    if request_type == 'club_application':
        # 社团申请只需要检查是否是申请人本人
        application = get_object_or_404(ClubRegistrationRequest, pk=request_id)
        if application.requested_by != request.user:
            messages.error(request, '您没有权限修改此申请')
            return redirect('clubs:user_dashboard')
    else:
        # 其他类型需要检查是否是社长
        if not _is_president(request.user):
            messages.error(request, '仅社长可以修改被拒绝的申请材料')
            return redirect('clubs:index')
        
        club = get_object_or_404(Club, pk=club_id)
        
        # 检查权限 - 只能修改自己社团的申请
        is_club_president = Officer.objects.filter(
            user_profile__user=request.user,
            club=club,
            position='president',
            is_current=True
        ).exists()
        
        if not is_club_president:
            messages.error(request, '您没有权限修改此社团的申请材料')
            return redirect('clubs:user_dashboard')
    
    # 根据请求类型获取对应的对象和数据
    if request_type == 'club_application':
        # 处理社团申请重新提交（application 已在权限检查时获取）
        
        # 只有被拒绝的申请才能重新提交
        if application.status != 'rejected':
            messages.error(request, '只有被拒绝的申请才能重新提交')
            return redirect('clubs:approval_center', tab='application')
        
        # 检查是否已经被修改提交过（通过检查是否已有新的pending申请）
        newer_application = ClubRegistrationRequest.objects.filter(
            requested_by=request.user,
            club_name=application.club_name,
            submitted_at__gt=application.submitted_at
        ).exists()
        
        if newer_application:
            messages.error(request, '该申请已被修改提交，不允许再次修改之前的请求')
            return redirect('clubs:approval_center', tab='application')
        
        # 获取社团创建模板
        registration_templates = Template.objects.filter(template_type='club_creation', is_active=True)
        
        # 获取被拒绝的材料列表
        rejected_materials = []
        review = application.reviews.filter(status='rejected').last()
        if review:
            rejected_materials = review.rejected_materials
            
        context = {
            'application': application,
            'registration_templates': registration_templates,
            'rejected_materials': rejected_materials,
            'review_type': 'club_application',
            'club_id_param': 0,  # 社团申请时还没有club，使用0作为占位符
        }
        
    elif request_type == 'club_registration':
        # 处理社团注册重新提交
        registration = get_object_or_404(ClubRegistration, pk=request_id, club=club)
        
        # 只有被拒绝的申请才能重新提交
        if registration.status != 'rejected':
            messages.error(request, '只有被拒绝的申请才能重新提交')
            return redirect('clubs:approval_center', tab='registration')
        
        # 检查是否已经被修改提交过（通过检查是否已有更新的pending申请）
        newer_registration = ClubRegistration.objects.filter(
            club=registration.club,
            registration_period=registration.registration_period,
            submitted_at__gt=registration.submitted_at
        ).exists()
        
        if newer_registration:
            messages.error(request, '该申请已被修改提交，不允许再次修改之前的请求')
            return redirect('clubs:approval_center', tab='registration')
        
        # 获取所有注册相关的模板
        registration_templates = Template.objects.filter(template_type__startswith='registration_').order_by('template_type')
        
        # 获取被拒绝的材料列表
        rejected_materials = []
        review = registration.reviews.filter(status='rejected').last()
        if review:
            rejected_materials = review.rejected_materials
        
        context = {
            'club': club,
            'registration': registration,
            'registration_templates': registration_templates,
            'rejected_materials': rejected_materials,
            'review_type': 'club_registration',
            'club_id_param': club.id,
        }
        
    elif request_type == 'review':
        # 处理年审材料重新提交
        submission = get_object_or_404(ReviewSubmission, pk=request_id, club=club, status='rejected')
        
        # 检查是否已经被修改提交过（通过检查是否已有该年份的更新提交）
        newer_submission = ReviewSubmission.objects.filter(
            club=submission.club,
            submission_year=submission.submission_year,
            submitted_at__gt=submission.submitted_at
        ).exists()
        
        if newer_submission:
            messages.error(request, '该申请已被修改提交，不允许再次修改之前的请求')
            return redirect('clubs:approval_center', tab='annual_review')
        
        is_resubmission = True
        
        # 获取可用模板
        financial_templates = Template.objects.filter(template_type='review_financial', is_active=True)
        activity_templates = Template.objects.filter(template_type='review_activity', is_active=True)
        member_list_templates = Template.objects.filter(template_type='review_member_list', is_active=True)
        self_assessment_templates = Template.objects.filter(template_type='review_self_assessment', is_active=True)
        club_constitution_templates = Template.objects.filter(template_type='review_club_constitution', is_active=True)
        leader_report_templates = Template.objects.filter(template_type='review_leader_report', is_active=True)
        annual_activity_templates = Template.objects.filter(template_type='review_annual_activity', is_active=True)
        advisor_report_templates = Template.objects.filter(template_type='review_advisor_report', is_active=True)
        member_composition_templates = Template.objects.filter(template_type='review_member_composition', is_active=True)
        media_account_templates = Template.objects.filter(template_type='review_media_account', is_active=True)
        
        # 收集被拒绝的材料列表
        rejected_materials = []
        review_comments = []
        # 同时包含被拒绝和部分拒绝的审核记录
        reviews = SubmissionReview.objects.filter(submission=submission, status__in=['rejected', 'partially_rejected'])
        for review in reviews:
            if review.rejected_materials:
                rejected_materials.extend(review.rejected_materials)
            # 收集审核意见
            if review.comment:
                review_comments.append(review.comment)
        # 去重
        rejected_materials = list(set(rejected_materials))
        
        # 如果没有具体的被拒绝材料列表，但有审核意见，添加提示
        if not rejected_materials and review_comments:
            # 提供一个通用提示，让用户查看审核意见
            pass
        
        context = {
            'club': club,
            'financial_templates': financial_templates,
            'activity_templates': activity_templates,
            'member_list_templates': member_list_templates,
            'self_assessment_templates': self_assessment_templates,
            'club_constitution_templates': club_constitution_templates,
            'leader_report_templates': leader_report_templates,
            'annual_activity_templates': annual_activity_templates,
            'advisor_report_templates': advisor_report_templates,
            'member_composition_templates': member_composition_templates,
            'media_account_templates': media_account_templates,
            'is_resubmission': is_resubmission,
            'rejected_submission': submission,
            'rejected_materials': rejected_materials,
            'review_comments': review_comments,  # 添加审核意见到上下文
            'review_type': 'review',
            'club_id_param': club.id,
        }
    
    elif request_type == 'reimbursement':
        # 处理报销重新提交
        reimbursement = get_object_or_404(Reimbursement, pk=request_id, club=club)
        
        # 只有被拒绝的申请才能重新提交
        if reimbursement.status != 'rejected':
            messages.error(request, '只有被拒绝的报销申请才能重新提交')
            return redirect('clubs:view_reimbursements', club_id=club.id)  # type: ignore[attr-defined]
        
        # 获取可用模板
        reimbursement_templates = Template.objects.filter(template_type='reimbursement', is_active=True)
        
        context = {
            'club': club,
            'reimbursement': reimbursement,
            'templates': reimbursement_templates,
            'review_type': 'reimbursement',
            'club_id_param': club.id,
        }
    
    elif request_type == 'activity_application':
        # 处理活动申请重新提交
        activity = get_object_or_404(ActivityApplication, pk=request_id, club=club)
        
        # 只有被拒绝的申请才能重新提交
        if activity.status != 'rejected':
            messages.error(request, '只有被拒绝的活动申请才能重新提交')
            return redirect('clubs:approval_center', tab='activity_application')
        
        context = {
            'club': club,
            'activity': activity,
            'review_type': 'activity_application',
            'club_id_param': club.id,
        }
    
    elif request_type == 'president_transition':
        # 处理社长换届申请重新提交
        transition = get_object_or_404(PresidentTransition, pk=request_id, club=club)
        
        # 只有被拒绝的申请才能重新提交
        if transition.status != 'rejected':
            messages.error(request, '只有被拒绝的换届申请才能重新提交')
            return redirect('clubs:user_dashboard')
        
        # 获取当前社团的所有干部（用于选择新社长）
        officers = Officer.objects.filter(club=club, is_current=True).exclude(position='president')
        
        context = {
            'club': club,
            'transition': transition,
            'officers': officers,
            'review_type': 'president_transition',
            'club_id_param': club.id,
        }
    
    if request.method == 'POST':
        # 根据请求类型处理不同的提交逻辑
        if request_type == 'club_application':
            # 获取上传的文件
            establishment_application = request.FILES.get('establishment_application')
            constitution_draft = request.FILES.get('constitution_draft')
            three_year_plan = request.FILES.get('three_year_plan')
            leaders_resumes = request.FILES.get('leaders_resumes')
            one_month_activity_plan = request.FILES.get('one_month_activity_plan')
            advisor_certificates = request.FILES.get('advisor_certificates')
            
            # 验证
            errors = []
            
            # 只验证被拒绝的材料是否重新上传
            if 'establishment_application' in rejected_materials and not establishment_application:
                errors.append('请上传社团成立申请书')
            if 'constitution_draft' in rejected_materials and not constitution_draft:
                errors.append('请上传社团章程草案')
            if 'three_year_plan' in rejected_materials and not three_year_plan:
                errors.append('请上传社团三年发展规划')
            if 'leaders_resumes' in rejected_materials and not leaders_resumes:
                errors.append('请上传社团拟任负责人和指导老师的详细简历和身份证复印件')
            if 'one_month_activity_plan' in rejected_materials and not one_month_activity_plan:
                errors.append('请上传社团组建一个月后的活动计划')
            if 'advisor_certificates' in rejected_materials and not advisor_certificates:
                errors.append('请上传社团老师的相关专业证书')
            
            # 验证文件类型
            if establishment_application:
                allowed_extensions = ['.docx']
                file_ext = os.path.splitext(establishment_application.name)[1].lower()
                if file_ext not in allowed_extensions:
                    errors.append('社团成立申请书请上传Word文档(.docx)')
            
            if constitution_draft:
                allowed_extensions = ['.docx']
                file_ext = os.path.splitext(constitution_draft.name)[1].lower()
                if file_ext not in allowed_extensions:
                    errors.append('社团章程草案请上传Word文档(.docx)')
            
            if three_year_plan:
                allowed_extensions = ['.docx']
                file_ext = os.path.splitext(three_year_plan.name)[1].lower()
                if file_ext not in allowed_extensions:
                    errors.append('社团三年发展规划请上传Word文档(.docx)')
            
            if leaders_resumes:
                allowed_extensions = ['.zip', '.rar', '.docx']
                file_ext = os.path.splitext(leaders_resumes.name)[1].lower()
                if file_ext not in allowed_extensions:
                    errors.append('社团拟任负责人和指导老师的详细简历和身份证复印件请上传压缩包(.zip, .rar)或Word文档(.docx)')
            
            if one_month_activity_plan:
                allowed_extensions = ['.docx']
                file_ext = os.path.splitext(one_month_activity_plan.name)[1].lower()
                if file_ext not in allowed_extensions:
                    errors.append('社团组建一个月后的活动计划请上传Word文档(.docx)')
            
            if advisor_certificates:
                allowed_extensions = ['.zip', '.rar', '.jpg', '.png']
                file_ext = os.path.splitext(advisor_certificates.name)[1].lower()
                if file_ext not in allowed_extensions:
                    errors.append('社团老师的相关专业证书请上传压缩包(.zip, .rar)或图片文件(.jpg, .png)')
            
            if errors:
                context['errors'] = errors
                return render(request, 'clubs/user/edit_rejected_review.html', context)
            
            # 重命名上传的文件
            club_name = application.club_name
            if establishment_application:
                establishment_application = rename_uploaded_file(establishment_application, club_name, '社团申请', '成立申请书')
            if constitution_draft:
                constitution_draft = rename_uploaded_file(constitution_draft, club_name, '社团申请', '章程草案')
            if three_year_plan:
                three_year_plan = rename_uploaded_file(three_year_plan, club_name, '社团申请', '三年规划')
            if leaders_resumes:
                leaders_resumes = rename_uploaded_file(leaders_resumes, club_name, '社团申请', '负责人简历')
            if one_month_activity_plan:
                one_month_activity_plan = rename_uploaded_file(one_month_activity_plan, club_name, '社团申请', '一个月活动计划')
            if advisor_certificates:
                advisor_certificates = rename_uploaded_file(advisor_certificates, club_name, '社团申请', '指导老师聘书')
            
            # 更新现有的社团申请记录而不是创建新的
            # 只更新被拒绝的材料
            if 'establishment_application' in rejected_materials and establishment_application:
                application.establishment_application = establishment_application
            if 'constitution_draft' in rejected_materials and constitution_draft:
                application.constitution_draft = constitution_draft
            if 'three_year_plan' in rejected_materials and three_year_plan:
                application.three_year_plan = three_year_plan
            if 'leaders_resumes' in rejected_materials and leaders_resumes:
                application.leaders_resumes = leaders_resumes
            if 'one_month_activity_plan' in rejected_materials and one_month_activity_plan:
                application.one_month_activity_plan = one_month_activity_plan
            if 'advisor_certificates' in rejected_materials and advisor_certificates:
                application.advisor_certificates = advisor_certificates
            
            # 如果没有明确的被拒绝材料列表，则更新所有上传的文件
            if not rejected_materials:
                if establishment_application:
                    application.establishment_application = establishment_application
                if constitution_draft:
                    application.constitution_draft = constitution_draft
                if three_year_plan:
                    application.three_year_plan = three_year_plan
                if leaders_resumes:
                    application.leaders_resumes = leaders_resumes
                if one_month_activity_plan:
                    application.one_month_activity_plan = one_month_activity_plan
                if advisor_certificates:
                    application.advisor_certificates = advisor_certificates
            
            # 重置状态和审核信息，增加提交次数
            application.status = 'pending'
            application.submitted_at = timezone.now()
            application.reviewed_at = None
            application.reviewer_comment = ''
            application.reviewer = None
            application.resubmission_attempt += 1
            application.save()
            
            messages.success(request, f'社团申请已重新提交（第{application.resubmission_attempt}次），等待干事审核！')
            return redirect('clubs:approval_center', tab='application')
            
        elif request_type == 'club_registration':
            # 获取被拒绝的材料列表
            rejected_materials = []
            review = registration.reviews.filter(status='rejected').last()
            if review:
                rejected_materials = review.rejected_materials
            
            registration_form = request.FILES.get('registration_form', None)
            basic_info_form = request.FILES.get('basic_info_form', None)
            fee_form = request.FILES.get('fee_form', None)
            leader_change_form = request.FILES.get('leader_change_form', None)
            meeting_minutes = request.FILES.get('meeting_minutes', None)
            name_change_form = request.FILES.get('name_change_form', None)
            advisor_change_form = request.FILES.get('advisor_change_form', None)
            business_unit_change_form = request.FILES.get('business_unit_change_form', None)
            new_media_form = request.FILES.get('new_media_form', None)
            
            # 验证必填文件
            errors = []
            # 无论状态如何，只要求重新上传被拒绝的材料
            if 'registration_form' in rejected_materials and not registration_form:
                errors.append('请上传社团注册申请表')
            if 'basic_info_form' in rejected_materials and not basic_info_form:
                errors.append('请上传学生社团基础信息表')
            if 'fee_form' in rejected_materials and not fee_form:
                errors.append('请上传会费表或免收会费说明书')
            
            # 验证文件类型
            allowed_extensions = ['.zip', '.rar', '.docx']
            
            # 使用通用文件验证
            for f, label in [
                (registration_form, '社团注册申请表'),
                (basic_info_form, '学生社团基础信息表'),
                (fee_form, '会费表或免收会费说明书'),
                (leader_change_form, '社团主要负责人变动申请表'),
                (meeting_minutes, '社团大会会议记录'),
                (name_change_form, '社团名称变更申请表'),
                (advisor_change_form, '社团指导老师变动申请表'),
                (business_unit_change_form, '社团业务指导单位变动申请表'),
                (new_media_form, '新媒体平台建立申请表')
            ]:
                err = _validate_file_allowed(f, label, allowed_extensions)
                if err:
                    errors.append(err)
            
            if errors:
                context['errors'] = errors
                return render(request, 'clubs/user/edit_rejected_review.html', context)
            
            if errors:
                context['errors'] = errors
                return render(request, 'clubs/user/edit_rejected_review.html', context)
            
            # 更新现有的社团注册申请记录而不是创建新的
            # 更新被拒绝的材料
            if 'registration_form' in rejected_materials and registration_form:
                registration.registration_form = registration_form
            
            if 'basic_info_form' in rejected_materials and basic_info_form:
                registration.basic_info_form = basic_info_form
            
            if 'fee_form' in rejected_materials and fee_form:
                registration.membership_fee_form = fee_form
            
            # 只在上传了新文件时才更新可选文件
            if 'leader_change_form' in rejected_materials and leader_change_form:
                registration.leader_change_application = leader_change_form
            
            if 'meeting_minutes' in rejected_materials and meeting_minutes:
                registration.meeting_minutes = meeting_minutes
            
            if 'name_change_form' in rejected_materials and name_change_form:
                registration.name_change_application = name_change_form
            
            if 'advisor_change_form' in rejected_materials and advisor_change_form:
                registration.advisor_change_application = advisor_change_form
            
            if 'business_unit_change_form' in rejected_materials and business_unit_change_form:
                registration.business_advisor_change_application = business_unit_change_form
            
            if 'new_media_form' in rejected_materials and new_media_form:
                registration.new_media_application = new_media_form
            
            # 如果没有明确的被拒绝材料列表，则更新所有上传的文件
            if not rejected_materials:
                if registration_form:
                    registration.registration_form = registration_form
                if basic_info_form:
                    registration.basic_info_form = basic_info_form
                if fee_form:
                    registration.membership_fee_form = fee_form
                if leader_change_form:
                    registration.leader_change_application = leader_change_form
                if meeting_minutes:
                    registration.meeting_minutes = meeting_minutes
                if name_change_form:
                    registration.name_change_application = name_change_form
                if advisor_change_form:
                    registration.advisor_change_application = advisor_change_form
                if business_unit_change_form:
                    registration.business_advisor_change_application = business_unit_change_form
                if new_media_form:
                    registration.new_media_application = new_media_form
            
            # 重置状态和审核信息，增加提交次数
            registration.status = 'pending'
            registration.submitted_at = timezone.now()
            registration.reviewed_at = None
            registration.reviewer_comment = ''
            registration.resubmission_attempt += 1
            registration.save()
            
            messages.success(request, f'社团注册申请已重新提交（第{registration.resubmission_attempt}次），等待审核')
            return redirect('clubs:approval_center', tab='registration')
            
        elif request_type == 'review':

            
            # 获取新的材料字段
            self_assessment_form = request.FILES.get('self_assessment_form')
            club_constitution = request.FILES.get('club_constitution')
            leader_learning_work_report = request.FILES.get('leader_learning_work_report')
            annual_activity_list = request.FILES.get('annual_activity_list')
            advisor_performance_report = request.FILES.get('advisor_performance_report')
            financial_report = request.FILES.get('financial_report')
            member_composition_list = request.FILES.get('member_composition_list')
            new_media_account_report = request.FILES.get('new_media_account_report')
            other_materials = request.FILES.get('other_materials')
            
            # 验证
            errors = []
            
            # 确定需要验证的必填字段
            required_files = []
            # 重新提交时，只需要验证被拒绝或部分拒绝的材料
            rejected_materials = []
            # 获取所有审核记录中的被拒绝材料
            reviews = SubmissionReview.objects.filter(submission=context['rejected_submission'], status__in=['rejected', 'partially_rejected'])
            for review in reviews:
                if review.rejected_materials:
                    rejected_materials.extend(review.rejected_materials)
            
            # 去重
            rejected_materials = list(set(rejected_materials))
            
            # 构建需要重新提交的材料列表
            material_fields_map = {
                'self_assessment_form': ('自查表', self_assessment_form),
                'club_constitution': ('社团章程', club_constitution),
                'leader_learning_work_report': ('负责人学习及工作情况表', leader_learning_work_report),
                'annual_activity_list': ('社团年度活动清单', annual_activity_list),
                'advisor_performance_report': ('指导教师履职情况表', advisor_performance_report),
                'financial_report': ('年度财务情况表', financial_report),
                'member_composition_list': ('社团成员构成表', member_composition_list)
                # 移除 new_media_account_report，即使被拒绝也不作为必填字段
            }
            
            # 检查被拒绝的材料是否已重新提交
            for field_name in rejected_materials:
                if field_name in material_fields_map:
                    field_display_name, file = material_fields_map[field_name]
                    required_files.append((file, field_display_name))
            
            # 如果没有被拒绝的材料记录，默认需要重新提交所有材料
            if not rejected_materials:
                # 将所有材料都设为必填
                required_files = [
                    (self_assessment_form, '自查表'),
                    (club_constitution, '社团章程'),
                    (leader_learning_work_report, '负责人学习及工作情况表'),
                    (annual_activity_list, '社团年度活动清单'),
                    (advisor_performance_report, '指导教师履职情况表'),
                    (financial_report, '年度财务情况表'),
                    (member_composition_list, '社团成员构成表')
                    # 移除 new_media_account_report 作为必填字段
                ]
            
            # 验证必填字段和文件类型
            for file, field_name in required_files:
                if not file:
                    errors.append(f'{field_name}不能为空')
                else:
                    err = _validate_word_file(file, field_name)
                    if err:
                        errors.append(err)
            
            # 验证可选字段的文件类型（如果提供了文件）
            if other_materials:
                err = _validate_word_file(other_materials, '其他材料')
                if err:
                    errors.append(err)
            
            if errors:
                context['errors'] = errors
                return render(request, 'clubs/user/edit_rejected_review.html', context)
            
            # 更新现有被拒绝的提交记录
            submission = context['rejected_submission']
            # 更新被拒绝的材料
            if self_assessment_form:
                submission.self_assessment_form = self_assessment_form
            if club_constitution:
                submission.club_constitution = club_constitution
            if leader_learning_work_report:
                submission.leader_learning_work_report = leader_learning_work_report
            if annual_activity_list:
                submission.annual_activity_list = annual_activity_list
            if advisor_performance_report:
                submission.advisor_performance_report = advisor_performance_report
            if financial_report:
                submission.financial_report = financial_report
            if member_composition_list:
                submission.member_composition_list = member_composition_list
            if new_media_account_report:
                submission.new_media_account_report = new_media_account_report
            if other_materials:
                submission.other_materials = other_materials
            
            # 重置状态和审核信息，增加提交次数
            submission.status = 'pending'
            submission.review_count = 0
            submission.reviewed_at = None
            submission.resubmission_attempt += 1
            submission.save()
            
            # 删除原有的审核记录
            SubmissionReview.objects.filter(submission=submission).delete()
            
            messages.success(request, f'{submission.submission_year}年审材料重新提交成功（第{submission.resubmission_attempt}次），等待审核！')
            return redirect('clubs:user_dashboard')
        
        elif request_type == 'reimbursement':
            # 获取上传的文件
            submission_date = request.POST.get('submission_date', '')
            reimbursement_amount = request.POST.get('reimbursement_amount', '')
            description = request.POST.get('description', '').strip()
            receipt_file = request.FILES.get('receipt_file')
            
            errors = []
            if not submission_date:
                errors.append('报销日期不能为空')
            if not reimbursement_amount:
                errors.append('报销金额不能为空')
            if not description:
                errors.append('报销说明不能为空')
            if not receipt_file:
                errors.append('报销凭证必须上传')
            else:
                # 验证文件类型是否为Word格式
                valid_extensions = ['.doc', '.docx']
                ext = receipt_file.name.lower().split('.')[-1]
                if f'.{ext}' not in valid_extensions:
                    errors.append('报销凭证必须是Word格式文件(.doc或.docx)')
            
            if errors:
                context['errors'] = errors
                return render(request, 'clubs/user/edit_rejected_review.html', context)
            
            # 更新现有的报销记录
            reimbursement = context['reimbursement']
            reimbursement.submission_date = submission_date
            reimbursement.reimbursement_amount = reimbursement_amount
            reimbursement.description = description
            if receipt_file:
                # 重命名报销凭证文件
                receipt_file = rename_uploaded_file(receipt_file, club.name, '报销', '凭证')
                reimbursement.receipt_file = receipt_file
            
            # 重置状态和审核信息，增加提交次数
            reimbursement.status = 'pending'
            reimbursement.reviewed_at = None
            reimbursement.reviewer = None
            reimbursement.reviewer_comment = ''
            reimbursement.resubmission_attempt += 1
            reimbursement.save()
            
            messages.success(request, f'报销申请已重新提交（第{reimbursement.resubmission_attempt}次），等待审核')
            return redirect('clubs:approval_center', tab='reimbursement')
        
        elif request_type == 'activity_application':
            # 获取表单数据
            activity_name = request.POST.get('activity_name', '').strip()
            activity_type = request.POST.get('activity_type', 'other')
            activity_description = request.POST.get('activity_description', '').strip()
            activity_date = request.POST.get('activity_date', '')
            activity_location = request.POST.get('activity_location', '').strip()
            application_form = request.FILES.get('application_form')
            contact_person = request.POST.get('contact_person', '').strip()
            contact_phone = request.POST.get('contact_phone', '').strip()
            
            errors = []
            if not activity_name:
                errors.append('活动名称不能为空')
            if not activity_description:
                errors.append('活动描述不能为空')
            if not activity_date:
                errors.append('活动日期不能为空')
            if not activity_location:
                errors.append('活动地点不能为空')
            if not application_form:
                errors.append('活动申请表必须上传')
            
            if errors:
                context['errors'] = errors
                return render(request, 'clubs/user/edit_rejected_review.html', context)
            
            # 更新现有的活动申请记录
            activity = context['activity']
            activity.activity_name = activity_name
            activity.activity_type = activity_type
            activity.activity_description = activity_description
            activity.activity_date = activity_date
            activity.activity_location = activity_location
            if contact_person:
                activity.contact_person = contact_person
            if contact_phone:
                activity.contact_phone = contact_phone
            if application_form:
                # 重命名活动申请表文件
                application_form = rename_uploaded_file(application_form, club.name, '活动', '申请表')
                activity.application_form = application_form
            
            # 重置状态和审核信息，增加提交次数
            activity.status = 'pending'
            activity.reviewed_at = None
            activity.reviewer = None
            activity.reviewer_comment = ''
            activity.resubmission_attempt += 1
            activity.save()
            
            messages.success(request, f'活动申请已重新提交（第{activity.resubmission_attempt}次），等待审核')
            return redirect('clubs:approval_center', tab='activity_application')
        
        elif request_type == 'president_transition':
            # 获取表单数据
            new_president_officer_id = request.POST.get('new_president_officer')
            reason = request.POST.get('reason', '').strip()
            transition_plan = request.FILES.get('transition_plan')
            
            errors = []
            if not new_president_officer_id:
                errors.append('请选择新社长')
            if not reason:
                errors.append('换届原因不能为空')
            if not transition_plan:
                errors.append('换届计划书必须上传')
            
            if errors:
                context['errors'] = errors
                return render(request, 'clubs/user/edit_rejected_review.html', context)
            
            try:
                new_president_officer = Officer.objects.get(pk=new_president_officer_id, club=club, is_current=True)
            except Officer.DoesNotExist:
                messages.error(request, '选择的新社长不是当前社团的有效干部')
                return redirect('clubs:user_dashboard')
            
            # 更新现有的换届申请记录
            transition = context['transition']
            transition.new_president_officer = new_president_officer
            transition.reason = reason
            if transition_plan:
                # 重命名换届计划书文件
                transition_plan = rename_uploaded_file(transition_plan, club.name, '换届', '计划书')
                transition.transition_plan = transition_plan
            
            # 重置状态和审核信息，增加提交次数
            transition.status = 'pending'
            transition.reviewed_at = None
            transition.reviewer = None
            transition.reviewer_comment = ''
            transition.resubmission_attempt += 1
            transition.save()
            
            messages.success(request, f'换届申请已重新提交（第{transition.resubmission_attempt}次），等待审核')
            return redirect('clubs:user_dashboard')
    
    # GET请求时渲染页面
    return render(request, 'clubs/user/edit_rejected_review.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def submit_review(request, club_id):
    """年审材料提交/重新提交 - 仅社长可用"""
    if not _is_president(request.user):
        messages.error(request, '仅社长可以提交年审材料')
        return redirect('clubs:index')
    
    club = get_object_or_404(Club, pk=club_id)
    
    # 检查权限 - 只能提交自己社团的年审
    if club.president != request.user:
        messages.error(request, '您没有权限提交此社团的年审材料')
        return redirect('clubs:user_dashboard')
    
    # 获取可用模板
    financial_templates = Template.objects.filter(template_type='review_financial', is_active=True)
    activity_templates = Template.objects.filter(template_type='review_activity', is_active=True)
    member_list_templates = Template.objects.filter(template_type='review_member_list', is_active=True)
    self_assessment_templates = Template.objects.filter(template_type='review_self_assessment', is_active=True)
    club_constitution_templates = Template.objects.filter(template_type='review_club_constitution', is_active=True)
    leader_report_templates = Template.objects.filter(template_type='review_leader_report', is_active=True)
    annual_activity_templates = Template.objects.filter(template_type='review_annual_activity', is_active=True)
    advisor_report_templates = Template.objects.filter(template_type='review_advisor_report', is_active=True)
    member_composition_templates = Template.objects.filter(template_type='review_member_composition', is_active=True)
    media_account_templates = Template.objects.filter(template_type='review_media_account', is_active=True)
    
    # 获取动态材料要求
    requirements = MaterialRequirement.objects.filter(
        request_type='annual_review', 
        is_active=True
    ).order_by('order')

    # 验证文件函数
    def validate_file(file, requirement):
        if not file:
            return None
        
        # 检查扩展名
        allowed_exts = [ext.strip().lower() for ext in requirement.allowed_extensions.split(',')]
        ext = '.' + file.name.lower().split('.')[-1]
        if ext not in allowed_exts:
            return f'{requirement.name}必须是以下格式: {requirement.allowed_extensions}'
        
        # 检查大小
        if file.size > requirement.max_size_mb * 1024 * 1024:
            return f'{requirement.name}文件大小不能超过{requirement.max_size_mb}MB'
            
        return None
    
    # 检查是否有被拒绝的提交记录
    resubmit_id = request.GET.get('resubmit')
    if resubmit_id:
        # 使用用户指定的提交记录进行重新提交
        rejected_submission = get_object_or_404(ReviewSubmission, pk=resubmit_id, club=club, status='rejected')
    else:
        # 使用最新的被拒绝记录
        rejected_submission = ReviewSubmission.objects.filter(club=club, status='rejected').order_by('-submitted_at').first()
    is_resubmission = rejected_submission is not None
    
    # 收集被拒绝的材料列表
    rejected_materials = []
    rejected_req_ids = set()
    if is_resubmission:
        # 获取所有审核记录中的被拒绝材料
        reviews = SubmissionReview.objects.filter(submission=rejected_submission, status__in=['rejected', 'partially_rejected'])
        for review in reviews:
            if review.rejected_materials:
                rejected_materials.extend(review.rejected_materials)
        # 去重
        rejected_materials = list(set(rejected_materials))
        
        # 提取被拒绝的 Requirement ID
        for item in rejected_materials:
            if item.startswith('req_'):
                try:
                    rejected_req_ids.add(int(item.split('_')[1]))
                except ValueError:
                    pass
    
    # 准备已存在的文件信息
    existing_files = {}
    if is_resubmission:
        # 获取SubmittedFiles
        submitted_files = SubmittedFile.objects.filter(
            content_type=ContentType.objects.get_for_model(ReviewSubmission),
            object_id=rejected_submission.id
        )
        file_map = {sf.requirement_id: sf.file for sf in submitted_files}
        
        for req in requirements:
            file_field = file_map.get(req.id)
            if file_field:
                try:
                    existing_files[req.id] = {
                        'url': file_field.url,
                        'name': file_field.name.split('/')[-1]
                    }
                except Exception:
                    pass

    if request.method == 'POST':
        submission_year = request.POST.get('submission_year', '')
        
        # 验证
        errors = []
        if not submission_year:
            errors.append('年份不能为空')
            
        # 收集上传的文件
        uploaded_files = {}
        
        for req in requirements:
            file = request.FILES.get(f'material_{req.id}')
            uploaded_files[req.id] = file
            
            # 验证必填项
            is_req_rejected = f"req_{req.id}" in rejected_materials
            
            # 如果是重新提交，且该材料被拒绝，则必须上传
            # 如果是首次提交，且该材料是必填，则必须上传
            if is_resubmission:
                if is_req_rejected and not file:
                    errors.append(f'{req.name}是被拒绝的材料，必须重新上传')
            else:
                if req.is_required and not file:
                    errors.append(f'{req.name}不能为空')
            
            # 验证文件格式和大小
            if file:
                err = validate_file(file, req)
                if err:
                    errors.append(err)
        
        if errors:
            context = {
                'club': club,
                'errors': errors,
                'financial_templates': financial_templates,
                'activity_templates': activity_templates,
                'member_list_templates': member_list_templates,
                'self_assessment_templates': self_assessment_templates,
                'club_constitution_templates': club_constitution_templates,
                'leader_report_templates': leader_report_templates,
                'annual_activity_templates': annual_activity_templates,
                'advisor_report_templates': advisor_report_templates,
                'member_composition_templates': member_composition_templates,
                'media_account_templates': media_account_templates,
                'is_resubmission': is_resubmission,
                'rejected_submission': rejected_submission,
                'requirements': requirements,
                'rejected_materials': rejected_materials,
                'rejected_req_ids': rejected_req_ids,
                'existing_files': existing_files,
            }
            return render(request, 'clubs/user/submit_review.html', context)
        
        try:
            if is_resubmission:
                submission = rejected_submission
                submission.status = 'pending'
                submission.review_count = 0
                submission.reviewed_at = None
                submission.resubmission_attempt += 1
            else:
                submission = ReviewSubmission(
                    club=club,
                    submission_year=int(submission_year),
                    status='pending'
                )
            
            # 保存 Submission (为了获取 ID 用于 GenericForeignKey)
            submission.save()
            
            # 处理文件保存
            for req in requirements:
                file = uploaded_files.get(req.id)
                if file:
                    # 重命名文件
                    file = rename_uploaded_file(file, club.name, '年审', req.name)
                    
                    # 1. 保存到 SubmittedFile
                    SubmittedFile.objects.update_or_create(
                        content_type=ContentType.objects.get_for_model(ReviewSubmission),
                        object_id=submission.id,
                        requirement=req,
                        defaults={'file': file}
                    )
            
            # 再次保存 submission 以更新 legacy fields
            submission.save()
            
            if is_resubmission:
                # 删除原有的审核记录
                SubmissionReview.objects.filter(submission=submission).delete()
                messages.success(request, f'{submission_year}年审材料重新提交成功（第{submission.resubmission_attempt}次），等待审核！')
            else:
                messages.success(request, f'{submission_year}年审材料提交成功，等待审核！')
            
            return redirect('clubs:user_dashboard')
            
        except Exception as e:
            messages.error(request, f'提交失败: {str(e)}')
            # 出错时返回页面
            context = {
                'club': club,
                'financial_templates': financial_templates,
                'activity_templates': activity_templates,
                'member_list_templates': member_list_templates,
                'self_assessment_templates': self_assessment_templates,
                'club_constitution_templates': club_constitution_templates,
                'leader_report_templates': leader_report_templates,
                'annual_activity_templates': annual_activity_templates,
                'advisor_report_templates': advisor_report_templates,
                'member_composition_templates': member_composition_templates,
                'media_account_templates': media_account_templates,
                'is_resubmission': is_resubmission,
                'rejected_submission': rejected_submission,
                'requirements': requirements,
                'rejected_materials': rejected_materials,
            }
            return render(request, 'clubs/user/submit_review.html', context)
    
    # GET请求时渲染页面
    context = {
        'club': club,
        'financial_templates': financial_templates,
        'rejected_materials': rejected_materials,
        'activity_templates': activity_templates,
        'member_list_templates': member_list_templates,
        'self_assessment_templates': self_assessment_templates,
        'club_constitution_templates': club_constitution_templates,
        'leader_report_templates': leader_report_templates,
        'annual_activity_templates': annual_activity_templates,
        'advisor_report_templates': advisor_report_templates,
        'member_composition_templates': member_composition_templates,
        'media_account_templates': media_account_templates,
        'is_resubmission': is_resubmission,
        'rejected_submission': rejected_submission,
        'current_year': timezone.now().year,
        'requirements': requirements,
        'existing_files': existing_files,
    }
    return render(request, 'clubs/user/submit_review.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET"])
def approval_center_tabs(request, tab='annual_review'):
    """审批中心"""
    if not _is_president(request.user):
        messages.error(request, '仅社团社长可以访问审批中心')
        return redirect('clubs:index')
    
    # 获取当前用户作为社长的所有社团
    clubs = Officer.objects.filter(user_profile=request.user.profile, position='president', is_current=True).values_list('club', flat=True)
    
    # 根据选项卡类型获取数据
    active_items = []
    completed_items = []
    
    if tab == 'annual_review':
        all_items = ReviewSubmission.objects.filter(club__in=clubs).order_by('-submitted_at')
        active_items = all_items.filter(status__in=['pending', 'rejected'])
        completed_items = all_items.filter(status='approved')
        
    elif tab == 'registration':
        all_items = ClubRegistration.objects.filter(club__in=clubs).select_related('registration_period', 'club').order_by('-submitted_at')
        active_items = all_items.filter(status__in=['pending', 'rejected'])
        completed_items = all_items.filter(status='approved')
        
    elif tab == 'application':
        all_items = ClubRegistrationRequest.objects.filter(requested_by=request.user).order_by('-submitted_at')
        active_items = all_items.filter(status__in=['pending', 'rejected'])
        completed_items = all_items.filter(status='approved')
        
    elif tab == 'reimbursement':
        all_items = Reimbursement.objects.filter(club__in=clubs).order_by('-submitted_at')
        active_items = all_items.filter(status__in=['pending', 'rejected', 'partially_rejected'])
        completed_items = all_items.filter(status='approved')
        
    elif tab == 'activity_application':
        all_items = ActivityApplication.objects.filter(club__in=clubs).order_by('-submitted_at')
        active_items = all_items.filter(status__in=['pending', 'rejected'])
        completed_items = all_items.filter(status='approved')
        
    elif tab == 'president_transition':
        all_items = PresidentTransition.objects.filter(club__in=clubs).order_by('-submitted_at')
        active_items = all_items.filter(status__in=['pending', 'rejected'])
        completed_items = all_items.filter(status='approved')
    
    # 标记是否有更新版本
    for item in active_items:
        if hasattr(item, 'status') and item.status == 'rejected':
            item.has_newer_version = False
            # 检查是否有更新版本
            if tab == 'annual_review':
                newer = ReviewSubmission.objects.filter(
                    club=item.club,
                    submission_year=item.submission_year,
                    submitted_at__gt=item.submitted_at
                ).exists()
                item.has_newer_version = newer
            elif tab == 'registration':
                newer = ClubRegistration.objects.filter(
                    club=item.club,
                    registration_period=item.registration_period,
                    submitted_at__gt=item.submitted_at
                ).exists()
                item.has_newer_version = newer
            elif tab == 'application':
                newer = ClubRegistrationRequest.objects.filter(
                    requested_by=item.requested_by,
                    club_name=item.club_name,
                    submitted_at__gt=item.submitted_at
                ).exists()
                item.has_newer_version = newer
            elif tab in ['reimbursement', 'activity_application', 'president_transition']:
                model_class = type(item)
                newer = model_class.objects.filter(
                    club=item.club,
                    submitted_at__gt=item.submitted_at
                ).exists()
                item.has_newer_version = newer
    
    context = {
        'current_tab': tab,
        'active_items': active_items,
        'completed_items': completed_items,
    }
    
    return render(request, 'clubs/user/approval_center.html', context)

@login_required(login_url=settings.LOGIN_URL)
def approval_center_mobile(request, tab='annual_review'):
    """审批中心移动版 - 卡片网格UI用于手机端"""
    if not _is_president(request.user):
        messages.error(request, '仅社团社长可以访问审批中心')
        return redirect('clubs:index')
    
    # 获取当前用户作为社长的所有社团
    clubs = Officer.objects.filter(user_profile=request.user.profile, position='president', is_current=True).values_list('club', flat=True)
    
    # 获取所有6种审批类型的数据
    approved_rejected_items = {
        'annual_review': ReviewSubmission.objects.filter(club__in=clubs, status__in=['approved', 'rejected', 'pending']).order_by('-submitted_at'),
        'registration': ClubRegistration.objects.filter(club__in=clubs, status__in=['approved', 'rejected', 'pending']).order_by('-submitted_at'),
        'application': ClubRegistrationRequest.objects.filter(requested_by=request.user, status__in=['approved', 'rejected', 'pending']).order_by('-submitted_at'),
        'reimbursement': Reimbursement.objects.filter(club__in=clubs, status__in=['approved', 'rejected', 'pending', 'partially_rejected']).order_by('-submitted_at'),
        'activity_application': ActivityApplication.objects.filter(club__in=clubs, status__in=['approved', 'rejected', 'pending']).order_by('-submitted_at'),
        'president_transition': PresidentTransition.objects.filter(club__in=clubs, status__in=['approved', 'rejected', 'pending']).order_by('-submitted_at'),
    }
    
    # 计算未处理数量（pending状态）
    pending_counts = {
        'annual_review': ReviewSubmission.objects.filter(club__in=clubs, status='pending').count(),
        'registration': ClubRegistration.objects.filter(club__in=clubs, status='pending').count(),
        'application': ClubRegistrationRequest.objects.filter(requested_by=request.user, status='pending').count(),
        'reimbursement': Reimbursement.objects.filter(club__in=clubs, status='pending').count(),
        'activity_application': ActivityApplication.objects.filter(club__in=clubs, status='pending').count(),
        'president_transition': PresidentTransition.objects.filter(club__in=clubs, status='pending').count(),
    }
    
    # 计算需要修改材料的数量（已拒绝且无新版本）
    rejected_need_action_counts = {item_type: 0 for item_type in approved_rejected_items.keys()}
    
    # 标记是否有更新版本
    for item_type, items in approved_rejected_items.items():
        for item in items:
            if hasattr(item, 'status') and item.status == 'rejected':
                item.has_newer_version = False
                # 检查是否有更新版本
                if item_type == 'annual_review':
                    newer = ReviewSubmission.objects.filter(
                        club=item.club,
                        submission_year=item.submission_year,
                        submitted_at__gt=item.submitted_at
                    ).exists()
                    item.has_newer_version = newer
                elif item_type == 'registration':
                    newer = ClubRegistration.objects.filter(
                        club=item.club,
                        registration_period=item.registration_period,
                        submitted_at__gt=item.submitted_at
                    ).exists()
                    item.has_newer_version = newer
                elif item_type == 'application':
                    newer = ClubRegistrationRequest.objects.filter(
                        requested_by=item.requested_by,
                        club_name=item.club_name,
                        submitted_at__gt=item.submitted_at
                    ).exists()
                    item.has_newer_version = newer
                elif item_type in ['reimbursement', 'activity_application', 'president_transition']:
                    model_class = type(item)
                    newer = model_class.objects.filter(
                        club=item.club,
                        submitted_at__gt=item.submitted_at
                    ).exists()
                    item.has_newer_version = newer
                
                # 累计需要处理的已拒绝项目（无新版本）
                if not item.has_newer_version:
                    rejected_need_action_counts[item_type] += 1
    
    # 合并计算：需要处理的总数 = pending + rejected且无新版本
    unread_approval_counts = {
        item_type: pending_counts[item_type] + rejected_need_action_counts[item_type]
        for item_type in pending_counts.keys()
    }
    
    # 计算活跃请求总数（用于底栏显示）
    total_active_requests = sum(unread_approval_counts.values())
    # 添加 total 键以便底栏徽章使用（与 context processor 格式一致）
    unread_approval_counts['total'] = total_active_requests
    
    context = {
        'approved_rejected_items': approved_rejected_items,
        'unread_approval_counts': unread_approval_counts,
        'total_active_requests': total_active_requests,
    }
    
    return render(request, 'clubs/user/approval_center_mobile.html', context)


@login_required(login_url=settings.LOGIN_URL)
def approval_history_by_type(request, item_type):
    """按类型显示审批历史 - 显示某个类型的全部审批记录"""
    if not _is_president(request.user):
        messages.error(request, '仅社团社长可以访问此页面')
        return redirect('clubs:index')
    
    # 获取当前用户作为社长的所有社团
    clubs = Officer.objects.filter(user_profile=request.user.profile, position='president', is_current=True).values_list('club', flat=True)
    
    items = []
    title = ''
    
    if item_type == 'annual_review':
        items = list(ReviewSubmission.objects.filter(club__in=clubs).order_by('-submitted_at'))
        title = '年审材料历史'
        # 标记是否有更新版本
        for item in items:
            if item.status == 'rejected':
                item.has_newer_version = ReviewSubmission.objects.filter(
                    club=item.club,
                    submission_year=item.submission_year,
                    submitted_at__gt=item.submitted_at
                ).exists()
            else:
                item.has_newer_version = False
    elif item_type == 'club_registration':
        items = list(ClubRegistration.objects.filter(club__in=clubs).order_by('-submitted_at'))
        title = '社团注册历史'
        for item in items:
            if item.status == 'rejected':
                item.has_newer_version = ClubRegistration.objects.filter(
                    club=item.club,
                    registration_period=item.registration_period,
                    submitted_at__gt=item.submitted_at
                ).exists()
            else:
                item.has_newer_version = False
    elif item_type == 'club_application':
        items = list(ClubRegistrationRequest.objects.filter(requested_by=request.user).order_by('-submitted_at'))
        title = '社团申请历史'
        for item in items:
            if item.status == 'rejected':
                item.has_newer_version = ClubRegistrationRequest.objects.filter(
                    requested_by=item.requested_by,
                    club_name=item.club_name,
                    submitted_at__gt=item.submitted_at
                ).exists()
            else:
                item.has_newer_version = False
    elif item_type == 'reimbursement':
        items = list(Reimbursement.objects.filter(club__in=clubs).order_by('-submitted_at'))
        title = '报销申请历史'
        for item in items:
            if item.status == 'rejected':
                item.has_newer_version = Reimbursement.objects.filter(
                    club=item.club,
                    submitted_at__gt=item.submitted_at
                ).exists()
            else:
                item.has_newer_version = False
    elif item_type == 'activity_application':
        items = list(ActivityApplication.objects.filter(club__in=clubs).order_by('-submitted_at'))
        title = '活动申请历史'
        for item in items:
            if item.status == 'rejected':
                item.has_newer_version = ActivityApplication.objects.filter(
                    club=item.club,
                    submitted_at__gt=item.submitted_at
                ).exists()
            else:
                item.has_newer_version = False
    elif item_type == 'president_transition':
        items = list(PresidentTransition.objects.filter(club__in=clubs).order_by('-submitted_at'))
        title = '社长换届历史'
        for item in items:
            if item.status == 'rejected':
                item.has_newer_version = PresidentTransition.objects.filter(
                    club=item.club,
                    submitted_at__gt=item.submitted_at
                ).exists()
            else:
                item.has_newer_version = False
    else:
        messages.error(request, '无效的审批类型')
        return redirect('clubs:approval_center', 'annual_review')
    
    context = {
        'items': items,
        'item_type': item_type,
        'title': title,
    }
    
    return render(request, 'clubs/user/approval_history_by_type.html', context)

@login_required(login_url=settings.LOGIN_URL)
def approval_detail(request, item_type, item_id):
    """查看审批详情 - 显示审批历史时间轴 - 社长使用与干事相同的详情页面"""
    if not _is_president(request.user):
        messages.error(request, '仅社团社长可以访问此页面')
        return redirect('clubs:index')
    
    from types import SimpleNamespace
    
    context = {}
    item = None
    materials = []
    
    if item_type == 'annual_review':
        item = get_object_or_404(ReviewSubmission, pk=item_id)
        # 检查权限
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center', 'annual_review')
        context['title'] = f'{item.club.name} - 年审记录'
        context['item'] = item
        context['reviews'] = SubmissionReview.objects.filter(submission=item).order_by('-reviewed_at')
        
        # 构建材料列表
        material_fields = [
            ('self_assessment_form', '自查表', 'description'),
            ('club_constitution', '社团章程', 'description'),
            ('leader_learning_work_report', '负责人学习及工作情况表', 'description'),
            ('annual_activity_list', '社团年度活动清单', 'receipt'),
            ('advisor_performance_report', '指导教师履职情况表', 'description'),
            ('financial_report', '年度财务情况表', 'receipt'),
            ('member_composition_list', '社团成员构成表', 'people'),
            ('new_media_account_report', '新媒体账号及运维情况表', 'newspaper'),
            ('other_materials', '其他材料', 'attach_file'),
        ]
        for field_name, display_name, icon in material_fields:
            file_field = getattr(item, field_name, None)
            if file_field:
                materials.append({
                    'name': display_name,
                    'file': file_field,
                    'icon': icon
                })
        
    elif item_type == 'registration':
        item = get_object_or_404(ClubRegistration, pk=item_id)
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center', 'registration')
        context['title'] = f'{item.club.name} - 社团注册'
        context['item'] = item
        context['reviews'] = ClubRegistrationReview.objects.filter(registration=item).order_by('-reviewed_at')
        
    elif item_type == 'application':
        # 新社团申请 - ClubRegistrationRequest
        item = get_object_or_404(ClubRegistrationRequest, pk=item_id)
        if item.requested_by != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center', 'application')
        context['title'] = f'{item.club_name} - 新社团申请'
        context['item'] = item
        # 使用 ClubApplicationReview 存储的审核记录
        context['reviews'] = ClubApplicationReview.objects.filter(application=item).order_by('-reviewed_at')
        
        # 构建材料列表
        material_fields = [
            ('establishment_application', '社团成立申请书', 'description'),
            ('constitution_draft', '社团章程草案', 'description'),
            ('three_year_plan', '社团三年发展规划', 'description'),
            ('leaders_resumes', '拟任负责人和指导老师简历', 'attach_file'),
            ('one_month_activity_plan', '一个月后活动计划', 'description'),
        ]
        for field_name, display_name, icon in material_fields:
            file_field = getattr(item, field_name, None)
            if file_field:
                materials.append({
                    'name': display_name,
                    'file': file_field,
                    'icon': icon
                })
        
    elif item_type == 'reimbursement':
        item = get_object_or_404(Reimbursement, pk=item_id)
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center', 'reimbursement')
        context['title'] = f'{item.club.name} - 报销申请'
        context['item'] = item
        # 报销只有一条审核记录，直接从对象字段获取
        reviews = []
        if item.reviewer or item.reviewed_at:
            status = 'approved' if item.status == 'approved' else 'rejected' if item.status == 'rejected' else 'pending'
            reviews.append(SimpleNamespace(reviewer=item.reviewer, status=status, comment=item.reviewer_comment, reviewed_at=item.reviewed_at))
        context['reviews'] = reviews
        
        # 构建材料列表
        if item.receipt_file:
            materials.append({
                'name': '报销凭证',
                'file': item.receipt_file,
                'icon': 'receipt'
            })
        
    elif item_type == 'activity_application':
        item = get_object_or_404(ActivityApplication, pk=item_id)
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center', 'activity_application')
        context['title'] = f'{item.club.name} - 活动申请'
        context['item'] = item
        # 使用 ActivityApplicationHistory 获取审核历史
        context['reviews'] = ActivityApplicationHistory.objects.filter(activity_application=item).order_by('-attempt_number')
        
        # 构建材料列表
        if item.application_form:
            materials.append({
                'name': '活动申请表',
                'file': item.application_form,
                'icon': 'description'
            })
        
    elif item_type == 'president_transition':
        item = get_object_or_404(PresidentTransition, pk=item_id)
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center', 'president_transition')
        context['title'] = f'{item.club.name} - 社长换届'
        context['item'] = item
        # 为社长换届创建模拟的审核记录
        reviews = []
        if item.status in ['approved', 'rejected'] and item.reviewed_at:
            reviews.append(SimpleNamespace(
                reviewed_at=item.reviewed_at,
                reviewer=item.reviewer,
                status=item.status,
                comment=item.reviewer_comment or '',
            ))
        context['reviews'] = reviews
        
        # 构建材料列表 - PresidentTransition可能没有附件，但如果需要可在此扩展
        material_fields = [
            ('transition_document', '换届申请文档', 'description'),
        ]
        for field_name, display_name, icon in material_fields:
            file_field = getattr(item, field_name, None)
            if file_field:
                materials.append({
                    'name': display_name,
                    'file': file_field,
                    'icon': icon
                })
    
    else:
        messages.error(request, '无效的项目类型')
        return redirect('clubs:approval_center', 'annual_review')
    
    context['item_type'] = item_type
    context['materials'] = materials
    # 使用与干事审核详情相同的模板
    return render(request, 'clubs/user/approval_detail.html', context)

@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(['POST'])
def cancel_submission(request, submission_id):
    """取消年审请求并删除已上传的文件 - 仅社长可用"""
    if not _is_president(request.user):
        messages.error(request, '仅社长可以取消年审请求')
        return redirect('clubs:index')
    
    submission = get_object_or_404(ReviewSubmission, pk=submission_id)
    
    # 检查权限 - 只能取消自己社团的年审请求
    if submission.club.president != request.user:
        messages.error(request, '您没有权限取消此社团的年审请求')
        return redirect('clubs:user_dashboard')
    
    # 只有待审核状态的请求可以取消
    if submission.status != 'pending':
        messages.error(request, '只有待审核的请求可以取消')
        return redirect('clubs:user_dashboard')
    
    # 删除已上传的文件
    file_fields = [
        'self_assessment_form',
        'club_constitution',
        'leader_learning_work_report',
        'annual_activity_list',
        'advisor_performance_report',
        'financial_report',
        'member_composition_list',
        'new_media_account_report',
        'other_materials'
    ]
    
    for field_name in file_fields:
        file_field = getattr(submission, field_name)
        if file_field:
            # 获取文件路径
            file_path = file_field.path
            # 检查文件是否存在并删除
            if os.path.exists(file_path):
                os.remove(file_path)
    
    # 删除审核记录
    submission.reviews.all().delete()
    
    # 删除提交记录
    submission.delete()
    
    messages.success(request, '年审请求已成功取消，所有上传的文件已删除')
    return redirect('clubs:user_dashboard')





# ==================== 干事审核界面 ====================

@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(['GET', 'POST'])
def review_submission(request, submission_id):
    """审核年审材料 - 干事和管理员可用"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '仅干事和管理员可以审核年审材料')
        return redirect('clubs:index')
    
    submission = get_object_or_404(ReviewSubmission, pk=submission_id)
    
    # 检查当前用户是否已经审核过该材料
    if request.method == 'GET':
        existing_review = SubmissionReview.objects.filter(submission=submission, reviewer=request.user).first()
        if existing_review:
            messages.error(request, '您已经审核过该材料，无法再次查看审核页面')
            # 都重定向到审核中心的年审标签页
            return redirect('clubs:staff_audit_center', 'annual_review')
    
    if request.method == 'POST':
        status = request.POST.get('review_status', '')
        comment = request.POST.get('review_comment', '').strip()
        
        if status not in ['approved', 'rejected']:
            messages.error(request, '无效的审核状态')
            return redirect('clubs:staff_audit_center', 'annual_review')
        
        # 处理被拒绝的材料
        rejected_materials = []
        if status == 'rejected':
            # 获取所有可能的材料字段
            material_fields = [
                ('self_assessment_form', '自查表'),
                ('club_constitution', '社团章程'),
                ('leader_learning_work_report', '负责人学习及工作情况表'),
                ('annual_activity_list', '社团年度活动清单'),
                ('advisor_performance_report', '指导教师履职情况表'),
                ('financial_report', '年度财务情况表'),
                ('member_composition_list', '社团成员构成表'),
                ('new_media_account_report', '新媒体账号及运维情况表'),
                ('other_materials', '其他材料')
            ]
            
            # 收集被拒绝的材料（从 checkbox 获取）
            rejected_materials = request.POST.getlist('rejected_materials')
            
            # 如果没有选择任何被拒绝的材料，默认拒绝所有
            if not rejected_materials:
                rejected_materials = [field[0] for field in material_fields]
        
        # 创建新的审核记录
        review = SubmissionReview(
            submission=submission,
            reviewer=request.user,
            status=status,
            comment=comment,
            rejected_materials=rejected_materials
        )
        review.save()
        
        # 更新审核计数
        submission.review_count = SubmissionReview.objects.filter(submission=submission).count()
        submission.reviewed_at = timezone.now()
        
        # 如果当前审核是拒绝，直接打回请求
        if status == 'rejected':
            submission.status = status
            messages.success(request, f'{submission.club.name}的年审申请已驳回')
            submission.save()
        else:
            # 检查是否有任何拒绝记录
            has_reject = SubmissionReview.objects.filter(submission=submission, status='rejected').exists()
            if has_reject:
                # 如果之前已有拒绝记录，保持拒绝状态
                submission.status = 'rejected'
                submission.save()
            else:
                # 没有拒绝记录，检查是否已经有三次审核
                if submission.review_count >= 3:
                    # 所有审核都通过，批准申请
                    submission.status = 'approved'
                    # 更新社团状态
                    submission.club.is_active = True
                    submission.club.last_review_date = timezone.now()
                    submission.club.save()
                    messages.success(request, f'{submission.club.name}的年审申请已通过（3人全部通过）')
                    submission.save()
                else:
                    # 还没到三次审核，保持pending状态
                    submission.status = 'pending'
                    submission.save()
                    messages.success(request, f'已完成审核，当前审核次数：{submission.review_count}/3')
        
        # 重定向到审核中心的年审标签页
        return redirect('clubs:staff_audit_center', 'annual_review')
    
    # 获取动态材料列表
    materials = get_dynamic_materials_list(submission, 'annual_review')
    
    # 获取审核记录
    existing_reviews = SubmissionReview.objects.filter(submission=submission).order_by('-reviewed_at')
    
    # 计算批准和拒绝数量
    approved_count = existing_reviews.filter(status='approved').count()
    rejected_count = existing_reviews.filter(status='rejected').count()
    
    context = {
        'submission': submission,
        'club': submission.club,
        'existing_reviews': existing_reviews,
        'submission_materials': materials,
        'materials': materials,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    return render(request, 'clubs/staff/review_submission.html', context)





# ==================== 报销功能 ====================

@login_required(login_url=settings.LOGIN_URL)
def view_reimbursements(request, club_id):
    """查看报销历史 - 社长和干事可用"""
    user = request.user
    
    # 检查权限：社长或干事
    if not (_is_president(user) or _is_staff(user)):
        messages.error(request, '您没有权限查看此页面')
        return redirect('clubs:index')
    
    club = get_object_or_404(Club, pk=club_id)
    
    # 社长只能查看自己社团的报销历史
    if _is_president(user) and (not club.president or club.president != user):
        messages.error(request, '您没有权限查看此社团的报销历史')
        return redirect('clubs:user_dashboard')
    
    # 获取该社团的所有报销记录，按提交时间降序排列
    reimbursements = club.reimbursements.all().order_by('-submitted_at')

    context = {
        'club': club,
        'reimbursements': reimbursements,
    }
    return render(request, 'clubs/user/view_reimbursements.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def submit_reimbursement(request, club_id):
    """提交报销材料 - 仅社长可用"""
    if not _is_president(request.user):
        messages.error(request, '仅社长可以提交报销材料')
        return redirect('clubs:index')
    
    club = get_object_or_404(Club, pk=club_id)
    
    if club.president != request.user:
        messages.error(request, '您没有权限为此社团提交报销')
        return redirect('clubs:user_dashboard')
    
    # 获取可用模板
    reimbursement_templates = Template.objects.filter(template_type='reimbursement', is_active=True)
    
    # 获取动态材料要求
    requirements = MaterialRequirement.objects.filter(
        request_type='reimbursement', 
        is_active=True
    ).order_by('order')

    # 验证文件函数
    def validate_file(file, requirement):
        if not file:
            return None
        
        # 检查扩展名
        allowed_exts = [ext.strip().lower() for ext in requirement.allowed_extensions.split(',')]
        ext = '.' + file.name.lower().split('.')[-1]
        if ext not in allowed_exts:
            return f'{requirement.name}必须是以下格式: {requirement.allowed_extensions}'
        
        # 检查大小
        if file.size > requirement.max_size_mb * 1024 * 1024:
            return f'{requirement.name}文件大小不能超过{requirement.max_size_mb}MB'
        
        return None

    if request.method == 'POST':
        submission_date = request.POST.get('submission_date', '')
        reimbursement_amount = request.POST.get('reimbursement_amount', '')
        description = request.POST.get('description', '').strip()
        
        errors = []
        if not submission_date:
            errors.append('报销日期不能为空')
        if not reimbursement_amount:
            errors.append('报销金额不能为空')
        if not description:
            errors.append('报销说明不能为空')
            
        # 验证动态材料
        uploaded_files = {}
        for req in requirements:
            file = request.FILES.get(f'material_{req.id}')
            uploaded_files[req.id] = file
            
            # 验证必填项
            if req.is_required and not file:
                errors.append(f'{req.name}不能为空')
            
            # 验证文件格式和大小
            if file:
                err = validate_file(file, req)
                if err:
                    errors.append(err)
        
        if errors:
            return render(request, 'clubs/user/submit_reimbursement.html', {
                'errors': errors,
                'club': club,
                'templates': reimbursement_templates,
                'requirements': requirements,
                'submission_date': submission_date,
                'reimbursement_amount': reimbursement_amount,
                'description': description,
            })
        
        try:
            # 创建报销申请
            reimbursement = Reimbursement(
                club=club,
                submission_date=submission_date,
                reimbursement_amount=reimbursement_amount,
                description=description,
                status='pending'
            )
            
            # 查找 receipt_file 对应的文件
            receipt_file_content = None
            for req in requirements:
                if req.legacy_field_name == 'receipt_file' and uploaded_files.get(req.id):
                    receipt_file_content = uploaded_files.get(req.id)
                    # 重命名
                    receipt_file_content = rename_uploaded_file(receipt_file_content, club.name, '报销', '凭证')
                    reimbursement.receipt_file = receipt_file_content
                    break
            
            # 保存主对象
            reimbursement.save()
            
            # 处理所有文件保存
            for req in requirements:
                file = uploaded_files.get(req.id)
                if file:
                    final_file = file
                    if req.legacy_field_name == 'receipt_file':
                         final_file = receipt_file_content
                    else:
                         final_file = rename_uploaded_file(file, club.name, '报销', req.name)

                    # 1. 保存到 SubmittedFile
                    SubmittedFile.objects.create(
                        content_type=ContentType.objects.get_for_model(Reimbursement),
                        object_id=reimbursement.id,
                        requirement=req,
                        file=final_file
                    )
            
            messages.success(request, '报销材料已提交，等待审核！')
            return redirect('clubs:user_dashboard')
            
        except Exception as e:
            messages.error(request, f'提交失败: {str(e)}')
            return render(request, 'clubs/user/submit_reimbursement.html', {
                'errors': [f'提交失败: {str(e)}'],
                'club': club,
                'templates': reimbursement_templates,
                'requirements': requirements,
                'submission_date': submission_date,
                'reimbursement_amount': reimbursement_amount,
                'description': description,
            })
    
    context = {
        'club': club,
        'templates': reimbursement_templates,
        'requirements': requirements,
    }
    return render(request, 'clubs/user/submit_reimbursement.html', context)


# ==================== 干事管理功能 ====================

@login_required(login_url=settings.LOGIN_URL)
def get_templates_by_type(template_type):
    """根据模板类型获取活跃的模板列表"""
    return Template.objects.filter(template_type=template_type, is_active=True).order_by('-created_at')

def upload_template(request):
    """上传模板 - 干事和管理员可用"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '仅干事和管理员可以上传模板')
        return redirect('clubs:index')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        template_type = request.POST.get('template_type', '')
        description = request.POST.get('description', '').strip()
        file = request.FILES.get('file')
        
        errors = []
        if not name:
            errors.append('模板名称不能为空')
        if not template_type:
            errors.append('模板类型不能为空')
        if not file:
            errors.append('模板文件不能为空')
        
        if errors:
            return render(request, 'clubs/staff/upload_template.html', {
                'errors': errors,
                'template_types': Template.TEMPLATE_TYPES,
            })
        
        Template.objects.create(
            name=name,
            template_type=template_type,
            description=description,
            file=file,
            uploaded_by=request.user,
            is_active=True
        )
        messages.success(request, '模板上传成功！')
        return redirect('clubs:staff_dashboard')
    
    context = {
        'template_types': Template.TEMPLATE_TYPES,
    }
    return render(request, 'clubs/staff/upload_template.html', context)


@login_required(login_url=settings.LOGIN_URL)
def review_reimbursement(request, reimbursement_id):
    """审核报销材料 - 干事和管理员可用"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '仅干事和管理员可以审核报销')
        return redirect('clubs:index')
    
    reimbursement = get_object_or_404(Reimbursement, pk=reimbursement_id)
    
    if request.method == 'POST':
        decision = request.POST.get('review_status', '')
        review_comments = request.POST.get('review_comment', '').strip()
        
        if decision not in ['approved', 'rejected']:
            messages.error(request, '状态不合法')
            return redirect('clubs:staff_audit_center', 'reimbursement')
        
        # 保存历史记录
        from clubs.models import ReimbursementHistory
        ReimbursementHistory.objects.create(
            reimbursement=reimbursement,
            attempt_number=reimbursement.resubmission_attempt,
            submission_date=reimbursement.submission_date,
            reimbursement_amount=reimbursement.reimbursement_amount,
            description=reimbursement.description,
            submitted_at=reimbursement.submitted_at,
            reviewed_at=timezone.now(),
            reviewer=request.user,
            status=decision,
            reviewer_comment=review_comments
        )
        
        reimbursement.status = decision
        reimbursement.reviewer_comment = review_comments
        reimbursement.reviewed_at = timezone.now()
        reimbursement.reviewer = request.user
        reimbursement.save()
        
        messages.success(request, f'报销材料已{'批准' if decision == 'approved' else '拒绝'}')
        return redirect('clubs:staff_audit_center', 'reimbursement')
    
    # 报销是单人审核，不需要多人审核统计
    # 检查当前用户是否已经审核过（通过检查reimbursement的reviewer字段）
    user_has_reviewed = reimbursement.reviewer == request.user if reimbursement.reviewer else False
    
    # 获取动态材料列表
    materials = get_dynamic_materials_list(reimbursement, 'reimbursement')

    context = {
        'reimbursement': reimbursement,
        'materials': materials,
        'user_has_reviewed': user_has_reviewed,
        'approved_count': 1 if reimbursement.status == 'approved' else 0,
        'rejected_count': 1 if reimbursement.status == 'rejected' else 0,
        'existing_reviews': [],  # 报销是单人审核，没有多个审核记录
    }
    return render(request, 'clubs/staff/review_reimbursement.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def review_club_registration(request, registration_id):
    """审核社团注册申请 - 仅干事和管理员可用"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '仅干事和管理员可以审核社团注册')
        return redirect('clubs:index')
    
    registration = get_object_or_404(ClubRegistrationRequest, pk=registration_id)
    
    # 检查当前用户是否已经审核过该申请
    user_has_reviewed = registration.reviews.filter(reviewer=request.user).exists()
    
    if request.method == 'POST':
        # 如果用户已审核过，禁止重复提交
        if user_has_reviewed:
            messages.error(request, '您已经审核过该社团注册申请，无法再次审核')
            return redirect('clubs:review_club_registration', registration_id=registration_id)
            
        decision = request.POST.get('review_status', '')
        review_comments = request.POST.get('review_comment', '').strip()
        
        # 获取被拒绝的材料
        rejected_materials = request.POST.getlist('rejected_materials')
        
        if decision not in ['approved', 'rejected']:
            messages.error(request, '状态不合法')
            return redirect('clubs:staff_audit_center', 'application')
        
        # 如果是拒绝，需要确保至少有一个被拒绝的材料
        if decision == 'rejected' and not rejected_materials:
            messages.error(request, '拒绝必须选择至少一个被拒绝的材料')
            return redirect('clubs:review_club_registration', registration_id=registration_id)
        
        # 创建审核记录
        ClubApplicationReview.objects.create(
            application=registration,
            reviewer=request.user,
            status=decision,
            comment=review_comments,
            rejected_materials=rejected_materials
        )
        
        # 更新申请状态
        registration.status = decision
        registration.reviewer_comment = review_comments
        registration.reviewed_at = timezone.now()
        registration.reviewer = request.user
        registration.save()
        
        # 如果批准，创建社团和社长Officer记录
        if decision == 'approved':
            club, created = Club.objects.get_or_create(
                name=registration.club_name,
                defaults={
                    'description': registration.description,
                    'founded_date': registration.founded_date,
                    'status': 'active',
                    'president': registration.requested_by,
                    'members_count': registration.members_count
                }
            )
            
            # 创建或获取申请人的UserProfile
            try:
                president_profile = registration.requested_by.profile
            except UserProfile.DoesNotExist:
                # 如果申请人没有profile，需要创建一个
                import uuid
                president_profile = UserProfile.objects.create(
                    user=registration.requested_by,
                    role='president',
                    real_name=registration.president_name,
                    student_id=registration.president_id,
                    status='approved'
                )
            
            # 创建社长Officer记录
            Officer.objects.get_or_create(
                club=club,
                user_profile=president_profile,
                position='president',
                defaults={
                    'appointed_date': timezone.now().date(),
                    'is_current': True
                }
            )
        
        messages.success(request, f'社团注册申请已{'批准' if decision == 'approved' else '拒绝'}')
        return redirect('clubs:staff_dashboard')
    
    # 准备材料列表 (动态构建)
    from .models import MaterialRequirement, SubmittedFile
    from django.contrib.contenttypes.models import ContentType

    requirements = MaterialRequirement.objects.filter(request_type='club_registration', is_active=True).order_by('order')

    # 使用统一函数获取材料列表
    materials_list = get_dynamic_materials_list(registration, 'club_registration')
    
    # 获取现有审核记录
    existing_reviews = registration.reviews.all().order_by('-reviewed_at')
    approved_count = existing_reviews.filter(status='approved').count()
    rejected_count = existing_reviews.filter(status='rejected').count()
    
    # 动态生成被拒绝材料选项
    rejected_choices = [(req.name, req.name) for req in requirements]
    
    context = {
        'registration': registration,
        'rejected_materials': rejected_choices,
        'materials_list': materials_list,
        'materials': materials_list,
        'show_rejected_materials': True,
        'existing_reviews': existing_reviews,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'has_reviewed': user_has_reviewed,
    }
    return render(request, 'clubs/staff/review_club_registration.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(['GET', 'POST'])
def review_request(request, club_id):
    """
    统一审核视图函数，处理所有类型的审核请求
    
    request_type 可以是以下值：
    - 'submission': 年审材料审核
    - 'registration': 社团注册审核
    - 'leader_change': 社长变更审核
    - 'reimbursement': 报销审核
    - 'staff_registration': 干事注册审核
    """
    # 验证用户权限
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限进行审核操作')
        return redirect('clubs:index')
    
    # 从URL查询参数中获取请求类型和申请次数
    request_type = request.GET.get('type', '')
    submission_number = request.GET.get('number', '')
    
    if not request_type:
        messages.error(request, '无效的审核请求类型')
        return redirect('clubs:staff_dashboard')
    
    # 映射request_type到audit-center的tab名称
    audit_center_tab_mapping = {
        'submission': 'annual_review',
        'registration': 'application',
        'club_registration_submission': 'registration',
        'leader_change': 'info_change',
        'reimbursement': 'reimbursement',
        'staff_registration': 'staff_dashboard'  # 使用旧的重定向地址
    }
    audit_center_tab = audit_center_tab_mapping.get(request_type, 'staff_dashboard')
    
    # 对于某些审核类型不需要申请次数
    # - staff_registration: 用 club_id 作为 user_id
    # - registration: 用 club_id 作为申请ID
    if request_type not in ['staff_registration', 'registration']:
        if not submission_number:
            messages.error(request, '无效的申请次数')
            if audit_center_tab == 'staff_dashboard':
                return redirect('clubs:staff_dashboard')
            else:
                return redirect('clubs:staff_audit_center', audit_center_tab)
        
        # 尝试将申请次数转换为整数
        try:
            submission_number = int(submission_number)
        except ValueError:
            messages.error(request, '无效的申请次数格式')
            if audit_center_tab == 'staff_dashboard':
                return redirect('clubs:staff_dashboard')
            else:
                return redirect('clubs:staff_audit_center', audit_center_tab)
    
    # 引入模型
    from .models import MaterialRequirement, SubmittedFile
    from django.contrib.contenttypes.models import ContentType

    # 映射request_type到MaterialRequirement.request_type
    request_type_map = {
        'submission': 'annual_review',
        'registration': 'club_application',
        'club_registration_submission': 'club_registration',
        'reimbursement': 'reimbursement',
        'leader_change': 'president_transition',
        'club_info_change': 'info_change',
        'staff_registration': 'staff_registration'
    }
    
    req_type_db = request_type_map.get(request_type)
    
    # 辅助函数：获取动态材料列表
    def get_dynamic_materials_list(target_obj, db_req_type):
        requirements = MaterialRequirement.objects.filter(request_type=db_req_type, is_active=True).order_by('order')
        m_list = []
        s_files = []
        
        try:
            content_type = ContentType.objects.get_for_model(target_obj)
        except:
            return [], []
            
        for req in requirements:
            # 尝试查找 SubmittedFile
            submitted_file = SubmittedFile.objects.filter(
                content_type=content_type, 
                object_id=target_obj.id, 
                requirement=req
            ).first()
            
            file_obj = None
            if submitted_file:
                file_obj = submitted_file.file
            
            if file_obj:
                # 确定标识符：使用req_id前缀
                field_identifier = f"req_{req.id}"
                
                item = {
                    'field_name': field_identifier,
                    'field': field_identifier,
                    'label': req.name,
                    'name': req.name,
                    'icon': 'description', # 默认图标
                    'file': file_obj,
                    'req_id': req.id
                }
                m_list.append(item)
                
                file_ext = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else ''
                s_files.append({
                    'name': req.name,
                    'url': file_obj.url,
                    'type': file_ext
                })
        
        return m_list, s_files

    # 根据请求类型获取审核对象
    if request_type == 'submission':
        from clubs.models import Club, ReviewSubmission, SubmissionReview
        
        # 获取社团对象
        club = get_object_or_404(Club, pk=club_id)
        
        # 获取所有年审申请（用于计算submission_number）
        submissions = ReviewSubmission.objects.filter(club=club).order_by('submitted_at')
        
        # 优先使用ID参数获取年审申请（解决重新提交后的链接问题）
        submission_id = request.GET.get('id', '')
        if submission_id:
            try:
                obj = ReviewSubmission.objects.get(pk=submission_id, club=club)
                # 计算该申请在列表中的实际位置
                submission_number = list(submissions).index(obj) + 1
            except (ValueError, ReviewSubmission.DoesNotExist):
                # 如果ID无效，回退到使用submission_number
                if submission_number > len(submissions):
                    messages.error(request, '该社团没有这么多次的申请记录')
                    return redirect('clubs:staff_dashboard')
                obj = submissions[submission_number - 1]
        else:
            # 没有ID参数时，使用submission_number
            if submission_number > len(submissions):
                messages.error(request, '该社团没有这么多次的申请记录')
                return redirect('clubs:staff_dashboard')
            obj = submissions[submission_number - 1]
        template_name = 'clubs/staff/review_request.html'  # 使用统一审核模板
        title = f"审核 {club.name} 的第 {submission_number} 次年审材料"
        
        # 检查当前用户是否已经审核过
        existing_review = SubmissionReview.objects.filter(submission=obj, reviewer=request.user).first()
        
        # 处理POST请求
        if request.method == 'POST':
            # 如果已经审核过，不允许再次提交
            if existing_review:
                messages.error(request, '您已经审核过该材料，无法重复提交')
                return redirect('clubs:staff_dashboard')
            
            status = request.POST.get('review_status', '')
            comment = request.POST.get('review_comment', '').strip()
            
            if status not in ['approved', 'rejected']:
                messages.error(request, '无效的审核状态')
                return redirect('clubs:staff_dashboard')
            
            # 统一处理被拒绝的材料
            rejected_materials = []
            if status == 'rejected':
                # 收集被拒绝的材料
                rejected_materials = request.POST.getlist('rejected_materials')
                
                # 如果没有选择任何被拒绝的材料，默认拒绝所有
                if not rejected_materials:
                    reqs = MaterialRequirement.objects.filter(request_type=req_type_db, is_active=True)
                    for r in reqs:
                        fid = f"req_{r.id}"
                        rejected_materials.append(fid)
            
            # 创建新的审核记录
            review = SubmissionReview(
                submission=obj,
                reviewer=request.user,
                status=status,
                comment=comment,
                rejected_materials=rejected_materials
            )
            review.save()
            
            # 更新审核计数和状态
            obj.review_count = SubmissionReview.objects.filter(submission=obj).count()
            obj.reviewed_at = timezone.now()
            
            # 如果当前审核是拒绝，直接打回请求
            if status == 'rejected':
                obj.status = status
                messages.success(request, f'{obj.club.name}的年审申请已驳回')
                obj.save()
            else:
                # 检查是否有任何拒绝记录
                has_reject = SubmissionReview.objects.filter(submission=obj, status='rejected').exists()
                if has_reject:
                    # 如果之前已有拒绝记录，保持拒绝状态
                    obj.status = 'rejected'
                    obj.save()
                else:
                    # 没有拒绝记录，检查是否已经有三次审核
                    if obj.review_count >= 3:
                        # 所有审核都通过，批准申请
                        obj.status = 'approved'
                        # 更新社团状态
                        obj.club.is_active = True
                        obj.club.last_review_date = timezone.now()
                        obj.club.save()
                        messages.success(request, f'{obj.club.name}的年审申请已通过（3人全部通过）')
                        obj.save()
                    else:
                        # 还没到三次审核，保持pending状态
                        obj.status = 'pending'
                        obj.save()
                        messages.success(request, f'已完成审核，当前审核次数：{obj.review_count}/3')
            
            return redirect('clubs:staff_dashboard')
        
        # 使用动态函数获取材料列表
        materials_list, submission_files = get_dynamic_materials_list(obj, req_type_db)
        
        # 获取现有的审核记录
        existing_reviews = SubmissionReview.objects.filter(submission=obj).order_by('reviewed_at')
        
        # 计算批准和拒绝数量
        approved_count = existing_reviews.filter(status='approved').count()
        rejected_count = existing_reviews.filter(status='rejected').count()
        
        context = {
            'submission': obj,
            'club': obj.club,
            'materials_list': materials_list,
            'existing_reviews': existing_reviews,
            'submission_files': submission_files,
            'user_has_reviewed': existing_review is not None,
            'user_review': existing_review,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
        }
    
    elif request_type == 'registration':
        # 注意：社团注册请求是在社团创建之前提交的，所以没有club_id
        # 这种情况下，我们仍然使用request_id作为申请ID
        from clubs.models import ClubRegistrationRequest
        obj = get_object_or_404(ClubRegistrationRequest, pk=club_id)  # 这里club_id实际上是申请ID
        template_name = 'clubs/staff/review_request.html'  # 使用统一审核模板
        title = f"审核 {obj.club_name} 的注册申请"
        
        # 处理POST请求
        if request.method == 'POST':
            # 检查当前用户是否已经审核过该申请
            if obj.reviews.filter(reviewer=request.user).exists():
                messages.error(request, '您已经审核过该社团注册申请，无法再次审核')
                return redirect('clubs:staff_dashboard')
            
            decision = request.POST.get('review_status', '')
            review_comments = request.POST.get('review_comment', '').strip()
            
            # 统一处理被拒绝的材料
            rejected_materials = []
            if decision == 'rejected':
                # 收集被拒绝的材料 - 统一使用getlist('rejected_materials')，与模板保持一致
                rejected_materials = request.POST.getlist('rejected_materials')
                
                # 如果没有选择任何被拒绝的材料，默认拒绝所有
                if not rejected_materials:
                    reqs = MaterialRequirement.objects.filter(request_type=req_type_db, is_active=True)
                    for r in reqs:
                        fid = f"req_{r.id}"
                        rejected_materials.append(fid)
            
            if decision not in ['approved', 'rejected']:
                messages.error(request, '状态不合法')
                return redirect('clubs:staff_dashboard')
            
            # 创建审核记录
            from clubs.models import ClubApplicationReview
            ClubApplicationReview.objects.create(
                application=obj,
                reviewer=request.user,
                status=decision,
                comment=review_comments,
                rejected_materials=rejected_materials
            )
            
            # 更新申请状态
            obj.status = decision
            obj.reviewer_comment = review_comments
            obj.reviewed_at = timezone.now()
            obj.save()
            
            # 如果批准，创建社团和社长Officer记录
            if decision == 'approved':
                from clubs.models import Club, Officer
                club, created = Club.objects.get_or_create(
                    name=obj.club_name,
                    defaults={
                        'description': obj.description,
                        'founded_date': obj.founded_date,
                        'status': 'active',
                        'president': obj.requested_by,
                        'members_count': obj.members_count
                    }
                )
                
                # 创建或获取申请人的UserProfile
                try:
                    president_profile = obj.requested_by.profile
                except UserProfile.DoesNotExist:
                    # 如果申请人没有profile，需要创建一个
                    import uuid
                    president_profile = UserProfile.objects.create(
                        user=obj.requested_by,
                        role='president',
                        real_name=obj.president_name,
                        student_id=obj.president_id,
                        status='approved'
                    )
                
                # 创建社长Officer记录
                Officer.objects.get_or_create(
                    club=club,
                    user_profile=president_profile,
                    position='president',
                    defaults={
                        'appointed_date': timezone.now().date(),
                        'is_current': True
                    }
                )
            
            messages.success(request, f'社团注册申请已{'批准' if decision == 'approved' else '拒绝'}')
            return redirect('clubs:staff_dashboard')
        
        # 使用动态函数获取材料列表
        materials_list, submission_files = get_dynamic_materials_list(obj, req_type_db)
        
        context = {
            'registration': obj,
            'materials_list': materials_list,
            'submission_files': submission_files,
        }
    

    
    elif request_type == 'reimbursement':
        from clubs.models import Club, Reimbursement
        
        # 获取社团对象
        club = get_object_or_404(Club, pk=club_id)
        
        # 获取所有报销申请（用于计算submission_number）
        reimbursements = Reimbursement.objects.filter(club=club).order_by('submitted_at')
        
        # 优先使用ID参数获取报销申请（解决重新提交后的链接问题）
        reimbursement_id = request.GET.get('id', '')
        if reimbursement_id:
            try:
                obj = Reimbursement.objects.get(pk=reimbursement_id, club=club)
                # 计算该申请在列表中的实际位置
                submission_number = list(reimbursements).index(obj) + 1
            except (ValueError, Reimbursement.DoesNotExist):
                # 如果ID无效，回退到使用submission_number
                if submission_number > len(reimbursements):
                    messages.error(request, '该社团没有这么多次的报销申请记录')
                    return redirect('clubs:staff_dashboard')
                obj = reimbursements[submission_number - 1]
        else:
            # 没有ID参数时，使用submission_number
            if submission_number > len(reimbursements):
                messages.error(request, '该社团没有这么多次的报销申请记录')
                return redirect('clubs:staff_dashboard')
            obj = reimbursements[submission_number - 1]
        template_name = 'clubs/staff/review_request.html'  # 使用统一审核模板
        title = f"审核 {club.name} 的第 {submission_number} 次报销申请"
        
        # 处理POST请求
        if request.method == 'POST':
            decision = request.POST.get('review_status', '')  # 统一使用'review_status'参数名
            review_comments = request.POST.get('review_comment', '').strip()  # 统一使用'review_comment'参数名
            
            # 统一处理被拒绝的材料
            rejected_materials = []
            if decision == 'rejected':
                # 收集被拒绝的材料
                rejected_materials = request.POST.getlist('rejected_materials')
                
                # 如果没有选择任何被拒绝的材料，默认拒绝所有
                if not rejected_materials:
                    reqs = MaterialRequirement.objects.filter(request_type=req_type_db, is_active=True)
                    for r in reqs:
                        fid = f"req_{r.id}"
                        rejected_materials.append(fid)
            
            if decision not in ['approved', 'rejected']:
                messages.error(request, '状态不合法')
                return redirect('clubs:staff_dashboard')
            
            obj.status = decision
            obj.reviewer_comment = review_comments
            # 保存被拒绝的材料（如果有）
            if hasattr(obj, 'rejected_materials'):
                obj.rejected_materials = rejected_materials
            obj.reviewed_at = timezone.now()
            obj.save()
            
            messages.success(request, f'报销材料已{'批准' if decision == 'approved' else '拒绝'}')
            return redirect('clubs:staff_dashboard')
        
        # 使用动态函数获取材料列表
        materials_list, submission_files = get_dynamic_materials_list(obj, req_type_db)
        
        context = {
            'reimbursement': obj,
            'materials_list': materials_list,
            'submission_files': submission_files,
        }
    
    elif request_type == 'staff_registration':
        # 干事注册审核需要管理员权限
        if not _is_admin(request.user):
            messages.error(request, '仅管理员可以审核干事注册申请')
            return redirect('clubs:index')
        
        # 注意：这里club_id实际上是user_id，因为我们统一了路由参数名
        user = get_object_or_404(User, pk=club_id)
        obj = user.profile
        template_name = 'clubs/admin/review_staff_registration.html'  # 使用干事审核模板
        title = f"审核 {obj.user.username} 的干事注册申请"
        
        # 处理POST请求
        if request.method == 'POST':
            decision = request.POST.get('review_status', '')
            review_comments = request.POST.get('review_comment', '').strip()
            
            if decision not in ['approved', 'rejected']:
                messages.error(request, '状态不合法')
                return redirect('clubs:admin_dashboard')
            
            obj.status = decision
            # 保存审核意见（如果有）
            if hasattr(obj, 'review_comments'):
                obj.review_comments = review_comments
            obj.save()
            
            messages.success(request, f'干事注册申请已{"批准" if decision == "approved" else "拒绝"}')
            return redirect('clubs:admin_dashboard')
        
        context = {
            'user': user,
            'profile': obj,
        }
        # 继续执行下面的代码，不要在这里直接返回
    

    
    elif request_type == 'club_registration_submission':
        from clubs.models import Club, ClubRegistration, ClubRegistrationReview
        
        # 获取社团对象
        club = get_object_or_404(Club, pk=club_id)
        
        # 优先使用ID参数获取注册申请（解决重新提交后的链接问题）
        registration_id = request.GET.get('id', '')
        
        # 获取所有注册申请（用于计算submission_number）
        registrations = ClubRegistration.objects.filter(club=club).order_by('submitted_at')
        
        if registration_id:
            try:
                obj = ClubRegistration.objects.get(pk=registration_id, club=club)
                # 计算该申请在列表中的实际位置
                submission_number = list(registrations).index(obj) + 1
            except (ValueError, ClubRegistration.DoesNotExist):
                # 如果ID无效，回退到使用submission_number
                if submission_number > len(registrations):
                    messages.error(request, '该社团没有这么多次的注册申请记录')
                    return redirect('clubs:staff_dashboard')
                obj = registrations[submission_number - 1]
        else:
            # 没有ID参数时，使用submission_number
            if submission_number > len(registrations):
                messages.error(request, '该社团没有这么多次的注册申请记录')
                return redirect('clubs:staff_dashboard')
            obj = registrations[submission_number - 1]
        template_name = 'clubs/staff/review_request.html'  # 使用统一审核模板
        title = f"审核 {club.name} 的第 {submission_number} 次注册申请"
        
        # 检查审核是否已完成，已完成则不允许查看
        if obj.status != 'pending':
            messages.error(request, '该申请已完成审核，无法再查看审核页面')
            return redirect('clubs:staff_dashboard')
        
        # 检查当前用户是否已经审核过该申请
        # 对于重新提交的申请（状态为pending），允许同一干事再次审核
        has_reviewed = obj.reviews.filter(reviewer=request.user).exists()
        if has_reviewed and obj.status != 'pending':
            messages.error(request, '您已经审核过该申请，无法再次查看审核页面')
            return redirect('clubs:staff_dashboard')
        
        # 处理POST请求
        if request.method == 'POST':
            # 检查当前用户是否已经审核过该申请
            if has_reviewed:
                messages.error(request, '您已经审核过该社团注册申请，无法再次审核')
                return redirect('clubs:staff_dashboard')
            
            decision = request.POST.get('review_status', '')  # 使用统一的'review_status'参数名
            review_comments = request.POST.get('review_comment', '').strip()  # 使用统一的'review_comment'参数名
            
            # 统一处理被拒绝的材料
            rejected_materials = []
            if decision == 'rejected':
                # 直接从表单中获取被拒绝的材料列表
                rejected_materials = request.POST.getlist('rejected_materials')
                
                # 如果没有选择任何被拒绝的材料，默认拒绝所有
                if not rejected_materials:
                    reqs = MaterialRequirement.objects.filter(request_type=req_type_db, is_active=True)
                    for r in reqs:
                        fid = f"req_{r.id}"
                        rejected_materials.append(fid)
            
            if decision not in ['approved', 'rejected']:
                messages.error(request, '状态不合法')
                return redirect('clubs:staff_dashboard')
            
            # 创建审核记录
            club_registration_review = ClubRegistrationReview.objects.create(
                registration=obj,
                reviewer=request.user,
                status=decision,
                comment=review_comments,
                rejected_materials=rejected_materials if decision == 'rejected' else []
            )
            
            # 检查当前审核状态
            reviews = obj.reviews.all()
            
            # 收集所有审核意见
            all_comments = []
            for review in reviews:
                if review.comment:
                    all_comments.append(f"{review.reviewer.username}: {review.comment}")
                else:
                    all_comments.append(f"{review.reviewer.username}: 无")
            
            # 如果当前审核是拒绝，直接打回请求
            if decision == 'rejected':
                obj.status = decision
                obj.reviewer_comment = '\n'.join(all_comments)
                obj.reviewed_at = timezone.now()
                messages.success(request, f'社团注册申请已拒绝')
            # 如果当前审核是批准，检查是否有3人或以上批准，通过该申请
            elif reviews.filter(status='approved').count() >= 3:
                obj.status = 'approved'
                obj.reviewer_comment = '\n'.join(all_comments)
                obj.reviewed_at = timezone.now()
                messages.success(request, f'社团注册申请已批准')
            # 否则保持待审核状态
            else:
                obj.status = 'pending'
                messages.success(request, f'已提交审核意见，等待其他审核者完成审核（当前有{reviews.filter(status="approved").count()}人批准）')
            
            obj.save()
            
            return redirect('clubs:staff_dashboard')
        
        # 计算审核统计信息
        approved_count = obj.reviews.filter(status='approved').count()
        rejected_count = obj.reviews.filter(status='rejected').count()
        
        # 获取现有的审核记录
        existing_reviews = obj.reviews.all().order_by('reviewed_at')
        
        # 使用动态函数获取材料列表
        materials_list, submission_files = get_dynamic_materials_list(obj, req_type_db)
        
        context = {
            'registration': obj,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'has_reviewed': has_reviewed,
            'user_has_reviewed': has_reviewed,
            'materials_list': materials_list,
            'submission_files': submission_files,
            'existing_reviews': existing_reviews,
        }   
    
    else:
        messages.error(request, '无效的审核请求类型')
        return redirect('clubs:staff_dashboard')
    
    # 添加通用上下文
    context['title'] = title
    context['request_type'] = request_type
    
    return render(request, template_name, context)

# ==================== 管理员功能 ====================

@login_required(login_url=settings.LOGIN_URL)
def review_staff_registration(request, user_id):
    """
    审核干事注册申请 - 仅管理员可用
    """
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以审核干事注册申请')
        return redirect('clubs:index')
    
    # 获取用户和用户角色信息
    user = get_object_or_404(User, pk=user_id)
    try:
        profile = user.profile
        # 确保只审核干事角色且状态为待审核的用户
        if profile.role != 'staff' or profile.status != 'pending':
            messages.error(request, '只能审核待审核状态的干事账号')
            return redirect('clubs:admin_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, '用户角色信息不存在')
        return redirect('clubs:admin_dashboard')
    
    if request.method == 'POST':
        decision = request.POST.get('decision', '')
        review_comment = request.POST.get('review_comment', '').strip()
        
        if decision not in ['approved', 'rejected']:
            messages.error(request, '审核结果不合法')
            return redirect('clubs:review_staff_registration', user_id=user_id)
        
        # 更新用户状态
        profile.status = decision
        if review_comment:
            # 这里可以考虑将评论保存到其他字段或表中
            # 为了简单起见，我们暂时不保存评论
            pass
        profile.save()
        
        messages.success(request, f'用户 {user.username} 的注册申请已{'批准' if decision == 'approved' else '拒绝'}')
        return redirect('clubs:manage_users')
    
    context = {
        'user': user,
        'profile': profile,
    }
    return render(request, 'clubs/admin/review_staff_registration.html', context)

@login_required(login_url=settings.LOGIN_URL)
def admin_dashboard(request):
    """管理员仪表板"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以访问此页面')
        return redirect('clubs:index')
    
    # 统计数据
    total_clubs = Club.objects.count()
    total_users = User.objects.count()
    pending_registrations = ClubRegistrationRequest.objects.filter(status='pending').count()
    published_announcements = Announcement.objects.filter(status='published').count()
    pending_staff_count = UserProfile.objects.filter(role='staff', status='pending').count()
    
    # 用户角色分布
    presidents_count = UserProfile.objects.filter(role='president').count()
    staff_count = UserProfile.objects.filter(role='staff').count()
    admins_count = UserProfile.objects.filter(role='admin').count()
    
    # 最近发布的公告
    recent_announcements = Announcement.objects.all().order_by('-created_at')[:5]
    
    context = {
        'total_clubs': total_clubs,
        'total_users': total_users,
        'pending_registrations': pending_registrations,
        'published_announcements': published_announcements,
        'pending_staff_count': pending_staff_count,
        'presidents_count': presidents_count,
        'staff_count': staff_count,
        'admins_count': admins_count,
        'announcements': recent_announcements,
    }
    return render(request, 'clubs/admin/dashboard.html', context)


@login_required(login_url=settings.LOGIN_URL)
def manage_carousel(request):
    """管理轮播图列表"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以访问此页面')
        return redirect('clubs:index')
    
    carousel_images = CarouselImage.objects.all().order_by('-uploaded_at')
    return render(request, 'clubs/admin/manage_carousel.html', {
        'carousel_images': carousel_images,
    })


@login_required(login_url=settings.LOGIN_URL)
def add_carousel(request):
    """添加轮播图"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以访问此页面')
        return redirect('clubs:index')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        link = request.POST.get('link', '').strip()
        order = int(request.POST.get('order', 0))
        is_active = request.POST.get('is_active') == 'on'
        image = request.FILES.get('image')
        
        if not image:
            messages.error(request, '请选择要上传的图片')
            return render(request, 'clubs/admin/carousel_form.html')
        
        carousel = CarouselImage.objects.create(
            title=title,
            description=description,
            link=link,
            order=order,
            is_active=is_active,
            image=image,
            uploaded_by=request.user
        )
        messages.success(request, '轮播图添加成功')
        return redirect('clubs:manage_carousel')
    
    return render(request, 'clubs/admin/carousel_form.html')


@login_required(login_url=settings.LOGIN_URL)
def edit_carousel(request, carousel_id):
    """编辑轮播图"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以访问此页面')
        return redirect('clubs:index')
    
    carousel = get_object_or_404(CarouselImage, id=carousel_id)
    
    if request.method == 'POST':
        carousel.title = request.POST.get('title', '').strip()
        carousel.description = request.POST.get('description', '').strip()
        carousel.link = request.POST.get('link', '').strip()
        carousel.order = int(request.POST.get('order', 0))
        carousel.is_active = request.POST.get('is_active') == 'on'
        
        # 如果上传了新图片，替换旧图片
        new_image = request.FILES.get('image')
        if new_image:
            # 删除旧图片文件
            if carousel.image:
                try:
                    import os
                    if os.path.isfile(carousel.image.path):
                        os.remove(carousel.image.path)
                except:
                    pass
            carousel.image = new_image
        
        carousel.save()
        messages.success(request, '轮播图更新成功')
        return redirect('clubs:manage_carousel')
    
    return render(request, 'clubs/admin/carousel_form.html', {
        'carousel': carousel,
    })


@login_required(login_url=settings.LOGIN_URL)
def delete_carousel(request, carousel_id):
    """删除轮播图"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以访问此页面')
        return redirect('clubs:index')
    
    carousel = get_object_or_404(CarouselImage, id=carousel_id)
    
    if request.method == 'POST':
        # 删除图片文件
        if carousel.image:
            try:
                import os
                if os.path.isfile(carousel.image.path):
                    os.remove(carousel.image.path)
            except:
                pass
        
        carousel.delete()
        messages.success(request, '轮播图删除成功')
    
    return redirect('clubs:manage_carousel')


@login_required(login_url=settings.LOGIN_URL)
def locked_accounts(request):
    """列出被锁定的用户名，供管理员解锁或重置密码"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可访问此页面')
        return redirect('clubs:index')

    from django.core.cache import cache
    locked = []
    for u in User.objects.all():
        key = f'login_lock:user:{u.username}'
        if cache.get(key):
            locked.append(u)

    return render(request, 'clubs/admin/locked_accounts.html', {'locked': locked})

@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def publish_announcement(request):
    """发布公告 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以发布公告')
        return redirect('clubs:index')


# admin_force_reset_password 已移除
# 该功能由管理员界面的“重设密码”表单替代，移除以简化入口并减少重复功能。
# 如果将来需要恢复，再添加对应的视图和路由即可。


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(['POST'])
def unlock_account(request, username):
    """管理员解锁被锁账号（POST）"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可执行此操作')
        return redirect('clubs:index')

    from django.core.cache import cache
    lock_key = f'login_lock:user:{username}'
    attempts_key = f'login_attempts:user:{username}'
    cache.delete(lock_key)
    cache.delete(attempts_key)

    messages.success(request, f'账号 {username} 已解锁')
    return redirect('clubs:locked_accounts')


@require_http_methods(["GET", "POST"])
def publish_announcement(request):
    """发布公告 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以发布公告')
        return redirect('clubs:index')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        status = request.POST.get('status', 'published')
        expires_at = request.POST.get('expires_at', '')
        attachment = request.FILES.get('attachment')
        
        errors = []
        if not title:
            errors.append('公告标题不能为空')
        if not content:
            errors.append('公告内容不能为空')
        
        if errors:
            announcements = Announcement.objects.all().order_by('-created_at')[:10]
            context = {
                'errors': errors,
                'title': title,
                'content': content,
                'announcements': announcements,
            }
            return render(request, 'clubs/admin/publish_announcement.html', context)
        
        announcement = Announcement.objects.create(
            title=title,
            content=content,
            status=status,
            created_by=request.user,
            published_at=timezone.now() if status == 'published' else None,
            expires_at=expires_at if expires_at else None,
            attachment=attachment,
        )
        
        messages.success(request, '公告发布成功！')
        return redirect('clubs:admin_dashboard')
    
    # GET 请求 - 获取最近的公告列表
    announcements = Announcement.objects.all().order_by('-created_at')[:10]
    context = {
        'announcements': announcements,
    }
    return render(request, 'clubs/admin/publish_announcement.html', context)


@login_required(login_url=settings.LOGIN_URL)
def delete_announcement(request, announcement_id):
    """删除公告 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以删除公告')
        return redirect('clubs:admin_dashboard')
    
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    
    if request.method == 'POST':
        announcement_title = announcement.title
        announcement.delete()
        messages.success(request, f'公告"{announcement_title}"已删除')
        return redirect('clubs:admin_dashboard')
    
    # GET 请求：确认删除
    context = {
        'announcement': announcement,
    }
    return render(request, 'clubs/admin/confirm_delete_announcement.html', context)

@login_required(login_url=settings.LOGIN_URL)
def submit_club_registration(request, club_id):
    """提交社团注册 - 仅社团社长可用"""
    # 获取社团对象
    try:
        club = Club.objects.get(pk=club_id)
    except Club.DoesNotExist:
        messages.error(request, '社团不存在')
        return redirect('clubs:user_dashboard')
    
    # 验证权限：只有当前社团社长可以提交注册
    is_club_president = Officer.objects.filter(
        user_profile__user=request.user,
        club=club,
        position='president',
        is_current=True
    ).exists()
    
    if not is_club_president:
        messages.error(request, '仅社团社长可以提交社团注册')
        return redirect('clubs:user_dashboard')
    
    # 检查是否有活跃的注册周期
    active_period = RegistrationPeriod.objects.filter(is_active=True).first()
    if not active_period:
        messages.error(request, '当前社团注册功能未开启，无法提交注册申请')
        return redirect('clubs:user_dashboard')
    
    # 获取动态材料要求
    requirements = MaterialRequirement.objects.filter(
        request_type='club_registration', 
        is_active=True
    ).order_by('order')

    # 验证文件函数
    def validate_file(file, requirement):
        if not file:
            return None
        
        # 检查扩展名
        allowed_exts = [ext.strip().lower() for ext in requirement.allowed_extensions.split(',')]
        ext = '.' + file.name.lower().split('.')[-1]
        if ext not in allowed_exts:
            return f'{requirement.name}必须是以下格式: {requirement.allowed_extensions}'
        
        # 检查大小
        if file.size > requirement.max_size_mb * 1024 * 1024:
            return f'{requirement.name}文件大小不能超过{requirement.max_size_mb}MB'
        
        return None

    if request.method == 'POST':
        errors = []
        uploaded_files = {}
        
        for req in requirements:
            file = request.FILES.get(f'material_{req.id}')
            uploaded_files[req.id] = file
            
            # 验证必填项
            if req.is_required and not file:
                errors.append(f'{req.name}不能为空')
            
            # 验证文件格式和大小
            if file:
                err = validate_file(file, req)
                if err:
                    errors.append(err)
        
        if errors:
            for err in errors:
                messages.error(request, err)
            # 返回页面
            registration_templates = Template.objects.filter(template_type__startswith='registration_').order_by('template_type')
            context = {
                'club': club,
                'registration_templates': registration_templates,
                'active_period': active_period,
                'requirements': requirements,
            }
            return render(request, 'clubs/user/submit_club_registration.html', context)
        
        # 创建社团注册记录
        try:
            registration = ClubRegistration.objects.create(
                club=club,
                registration_period=active_period,  # 关联到当前活跃的注册周期
                requested_by=request.user,
                status='pending'
            )
            
            # 处理文件保存
            for req in requirements:
                file = uploaded_files.get(req.id)
                if file:
                    # 重命名文件
                    file = rename_uploaded_file(file, club.name, '社团注册', req.name)
                    
                    # 1. 保存到 SubmittedFile
                    SubmittedFile.objects.create(
                        content_type=ContentType.objects.get_for_model(ClubRegistration),
                        object_id=registration.id,
                        requirement=req,
                        file=file
                    )
            
            messages.success(request, '社团注册已提交，等待审核')
            return redirect('clubs:user_dashboard')
            
        except Exception as e:
            messages.error(request, f'提交失败: {str(e)}')
            # 出错时返回页面
            registration_templates = Template.objects.filter(template_type__startswith='registration_').order_by('template_type')
            context = {
                'club': club,
                'registration_templates': registration_templates,
                'active_period': active_period,
                'requirements': requirements,
            }
            return render(request, 'clubs/user/submit_club_registration.html', context)
    
    # GET请求 - 显示注册表单
    # 再次检查是否有活跃的注册周期（可能在加载页面时被关闭）
    if not active_period:
        messages.error(request, '当前社团注册功能未开启，无法提交注册申请')
        return redirect('clubs:user_dashboard')
    
    # 获取所有注册相关的模板
    registration_templates = Template.objects.filter(template_type__startswith='registration_').order_by('template_type')
    
    context = {
        'club': club,
        'registration_templates': registration_templates,
        'active_period': active_period,
        'requirements': requirements,
    }
    return render(request, 'clubs/user/submit_club_registration.html', context)


def review_club_registration_submission(request, registration_id):
    """审核社团注册 - 仅干事和管理员可用"""
    # 简单的权限检查
    try:
        user_role = request.user.profile.role
        if user_role in ['staff', 'admin']:
            # 权限通过，渲染审核页面
            registration = get_object_or_404(ClubRegistration, pk=registration_id)
            
            # 检查审核是否已完成，已完成则不允许查看
            if registration.status != 'pending':
                messages.error(request, '该申请已完成审核，无法再查看审核页面')
                return redirect('clubs:staff_audit_center', 'registration')
            
            # 检查当前用户是否已经审核过该申请
            # 禁止同一干事审核同一个请求两次及以上
            has_reviewed = registration.reviews.filter(reviewer=request.user).exists()
            if has_reviewed:
                messages.error(request, '您已经审核过该社团注册申请，无法再次审核')
                return redirect('clubs:staff_audit_center', 'registration')
            
            if request.method == 'POST':
                decision = request.POST.get('review_status', '')
                review_comments = request.POST.get('review_comment', '').strip()
                
                # 获取被拒绝的材料
                rejected_materials = request.POST.getlist('rejected_materials')
                
                if decision not in ['approved', 'rejected']:
                    messages.error(request, '状态不合法')
                    return redirect('clubs:staff_audit_center', 'registration')
                
                # 如果是拒绝，需要确保至少有一个被拒绝的材料
                if decision == 'rejected' and not rejected_materials:
                    messages.error(request, '拒绝必须选择至少一个被拒绝的材料')
                    return redirect('clubs:review_club_registration_submission', registration_id=registration_id)
                
                # 创建审核记录
                club_registration_review = ClubRegistrationReview.objects.create(
                    registration=registration,
                    reviewer=request.user,
                    status=decision,
                    comment=review_comments,
                    rejected_materials=rejected_materials if decision == 'rejected' else []
                )
                
                # 检查当前审核状态
                reviews = registration.reviews.all()
                
                # 收集所有审核意见
                all_comments = []
                for review in reviews:
                    if review.comment:
                        all_comments.append(f"{review.reviewer.username}: {review.comment}")
                    else:
                        all_comments.append(f"{review.reviewer.username}: 无")
                
                # 如果当前审核是拒绝，直接打回请求
                if decision == 'rejected':
                    registration.status = decision
                    registration.reviewer_comment = '\n'.join(all_comments)
                    registration.reviewed_at = timezone.now()
                    messages.success(request, f'社团注册申请已拒绝')
                # 如果当前审核是批准，检查是否有3人或以上批准，通过该申请
                elif reviews.filter(status='approved').count() >= 3:
                    registration.status = 'approved'
                    registration.reviewer_comment = '\n'.join(all_comments)
                    registration.reviewed_at = timezone.now()
                    messages.success(request, f'社团注册申请已批准')
                # 否则保持待审核状态
                else:
                    registration.status = 'pending'
                    messages.success(request, f'已提交审核意见，等待其他审核者完成审核（当前有{reviews.filter(status="approved").count()}人批准）')
                
                registration.save()
                
                return redirect('clubs:staff_audit_center', 'registration')
            
            # 计算审核统计信息
            approved_count = registration.reviews.filter(status='approved').count()
            rejected_count = registration.reviews.filter(status='rejected').count()
            
            # 获取动态材料列表
            materials = get_dynamic_materials_list(registration, 'club_registration')
            
            context = {
                'registration': registration,
                'approved_count': approved_count,
                'rejected_count': rejected_count,
                'has_reviewed': has_reviewed,
                'materials': materials,
                'materials_list': materials,
            }
            
            return render(request, 'clubs/staff/review_club_registration_submission.html', context)
        else:
            # 权限不足，重定向到首页
            messages.error(request, '仅干事和管理员可以审核社团注册')
            return redirect('clubs:index')
    except UserProfile.DoesNotExist:
        messages.error(request, '用户配置文件不存在')
        return redirect('clubs:index')


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def edit_announcement(request, announcement_id):
    """编辑公告 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以编辑公告')
        return redirect('clubs:admin_dashboard')
    
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        status = request.POST.get('status', 'published')
        expires_at = request.POST.get('expires_at', '')
        attachment = request.FILES.get('attachment')
        
        errors = []
        if not title:
            errors.append('公告标题不能为空')
        if not content:
            errors.append('公告内容不能为空')
        
        if errors:
            context = {
                'errors': errors,
                'title': title,
                'content': content,
                'announcement': announcement,
            }
            return render(request, 'clubs/admin/edit_announcement.html', context)
        
        announcement.title = title
        announcement.content = content
        announcement.status = status
        announcement.expires_at = expires_at if expires_at else None
        
        # 如果有新附件，则更新附件
        if attachment:
            announcement.attachment = attachment
        
        # 如果状态从非发布状态变为发布状态，更新发布时间
        if status == 'published' and announcement.status != 'published':
            announcement.published_at = timezone.now()
        
        announcement.save()
        
        messages.success(request, '公告修改成功！')
        return redirect('clubs:admin_dashboard')
    
    # GET 请求 - 预填充表单
    context = {
        'announcement': announcement,
    }
    return render(request, 'clubs/admin/edit_announcement.html', context)


@login_required(login_url=settings.LOGIN_URL)
def manage_users(request):
    """用户管理 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以管理用户')
        return redirect('clubs:index')
    
    # 获取所有用户，使用select_related加载关联的UserProfile以包含状态信息
    # 便于管理员审核待审核的干事账号
    users = User.objects.select_related('profile').all()
    
    # 搜索过滤
    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        users = users.filter(Q(username__icontains=search) | Q(email__icontains=search))
    
    # 角色过滤
    role = request.GET.get('role', '').strip()
    if role:
        users = users.filter(profile__role=role)
    
    # 检查哪些用户被锁（用于在用户列表中显示解锁按钮）
    from django.core.cache import cache
    locked_usernames = set()
    for u in User.objects.all():
        key = f'login_lock:user:{u.username}'
        if cache.get(key):
            locked_usernames.add(u.username)

    context = {
        'users': users,
        'total_users': User.objects.count(),
        'search': search,
        'role': role,
        'locked_usernames': locked_usernames,
    }
    return render(request, 'clubs/admin/manage_users.html', context)


@login_required(login_url=settings.LOGIN_URL)
def staff_view_users(request):
    """干事查看用户列表 - 查看专用，无编辑权限"""
    if not _is_staff(request.user):
        messages.error(request, '仅干事可以查看用户列表')
        return redirect('clubs:index')
    
    # 获取所有用户，但不提供编辑功能
    users = User.objects.select_related('profile').all()
    
    # 搜索过滤
    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        users = users.filter(Q(username__icontains=search) | Q(email__icontains=search))
    
    # 角色过滤
    role = request.GET.get('role', '').strip()
    if role:
        users = users.filter(profile__role=role)
    
    context = {
        'users': users,
        'total_users': User.objects.count(),
        'search': search,
        'role': role,
        'is_staff_view': True,  # 标记为干事视图
    }
    return render(request, 'clubs/staff/view_users.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def create_user(request):
    """管理员创建用户账户 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以创建用户账户')
        return redirect('clubs:index')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        real_name = request.POST.get('real_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        wechat = request.POST.get('wechat', '').strip()
        password = request.POST.get('password', '').strip()
        password2 = request.POST.get('password2', '').strip()
        role = request.POST.get('role', 'president').strip()
        student_id = request.POST.get('student_id', '').strip()
        
        errors = []
        
        # 验证
        if not username:
            errors.append('登录用户名不能为空')
        elif User.objects.filter(username=username).exists():
            errors.append('登录用户名已存在')
        elif len(username) < 3 or len(username) > 30:
            errors.append('登录用户名长度应在3-30个字符之间')
        
        if not real_name:
            errors.append('姓名不能为空')
        
        if not email:
            errors.append('邮箱不能为空')
        elif User.objects.filter(email=email).exists():
            errors.append('邮箱已被使用')
        
        if not phone:
            errors.append('电话不能为空')
        
        if not wechat:
            errors.append('微信号不能为空')
        
        if not password:
            errors.append('密码不能为空')
        elif len(password) < 6:
            errors.append('密码至少6个字符')
        
        if password != password2:
            errors.append('两次输入的密码不一致')
        
        if role not in ['president', 'staff', 'admin']:
            errors.append('无效的用户角色')
        
        # 学号验证（必填字段）
        if not student_id:
            errors.append('学号不能为空')
        
        if errors:
            context = {
                'errors': errors,
                'form_data': request.POST,
            }
            return render(request, 'clubs/admin/create_user.html', context)
        
        # 创建用户
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=real_name
        )
        
        # 确定用户状态 - 干事默认待审核，其他类型直接批准
        status = 'pending' if role == 'staff' else 'approved'
        
        # 创建用户角色信息
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': role,
                'status': status,
                'real_name': real_name,
                'phone': phone,
                'wechat': wechat,
                'student_id': student_id
            }
        )
        
        # 如果profile已经存在，更新它
        if not created:
            profile.role = role
            profile.status = status
            profile.real_name = real_name
            profile.phone = phone
            profile.wechat = wechat
            profile.student_id = student_id
            profile.save()
        
        role_display = dict(UserProfile.ROLE_CHOICES).get(role, role)
        messages.success(request, f'成功创建用户账户：{username}（角色：{role_display}）')
        return redirect('clubs:manage_users')
    
    return render(request, 'clubs/admin/create_user.html')



@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def admin_edit_user_account(request, user_id):
    """管理员编辑用户账户信息 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以编辑用户账户信息')
        return redirect('clubs:index')
    
    # 获取目标用户
    target_user = get_object_or_404(User, pk=user_id)
    
    # 确保管理员不能编辑自己的账户（使用自己的账户设置页面）
    if request.user == target_user:
        messages.error(request, '请使用您自己的账户设置页面编辑个人信息')
        return redirect('clubs:change_account_settings')
    
    errors = []
    success_messages = []
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        
        # 修改用户名
        if action == 'change_username':
            new_username = request.POST.get('new_username', '').strip()
            
            if not new_username:
                errors.append('新用户名不能为空')
            elif len(new_username) < 3:
                errors.append('用户名至少3个字符')
            elif User.objects.exclude(id=target_user.id).filter(username=new_username).exists():
                errors.append('用户名已被使用')
            else:
                old_username = target_user.username
                target_user.username = new_username
                target_user.save()
                success_messages.append(f'已将用户 {old_username} 的用户名修改为 {new_username}')
        
        # 修改密码
        elif action == 'change_password':
            new_password = request.POST.get('new_password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()
            
            if not new_password:
                errors.append('新密码不能为空')
            elif len(new_password) < 6:
                errors.append('新密码至少6个字符')
            elif new_password != confirm_password:
                errors.append('两次密码不一致')
            else:
                target_user.set_password(new_password)
                target_user.save()
                success_messages.append(f'已成功重置用户 {target_user.username} 的密码')
        
        # 修改角色
        elif action == 'change_role':
            new_role = request.POST.get('new_role', '')
            
            if new_role not in ['president', 'staff', 'admin']:
                errors.append('角色不合法')
            else:
                try:
                    profile = target_user.profile
                    old_role = profile.get_role_display()
                    profile.role = new_role
                    profile.save()
                    role_display = dict(UserProfile.ROLE_CHOICES).get(new_role, new_role)
                    success_messages.append(f'已将用户 {target_user.username} 的角色从「{old_role}」更改为「{role_display}」')
                except UserProfile.DoesNotExist:
                    # 创建UserProfile时处理student_id唯一性约束
                    import uuid
                    unique_student_id = f"USER_{target_user.username}_{str(uuid.uuid4())[:8]}"
                    
                    profile = UserProfile.objects.create(
                        user=target_user, 
                        role=new_role,
                        student_id=unique_student_id  # 设置唯一的student_id
                    )
                    role_display = dict(UserProfile.ROLE_CHOICES).get(new_role, new_role)
                    success_messages.append(f'已为用户 {target_user.username} 创建角色：「{role_display}」')
        
        # 修改用户详细信息
        elif action == 'change_user_info':
            real_name = request.POST.get('real_name', '').strip()
            student_id = request.POST.get('student_id', '').strip()
            phone = request.POST.get('phone', '').strip()
            wechat = request.POST.get('wechat', '').strip()
            political_status = request.POST.get('political_status', 'non_member')
            email = request.POST.get('email', '').strip()
            
            # 验证必填字段
            if not email:
                errors.append('邮箱不能为空')
            elif User.objects.exclude(id=target_user.id).filter(email=email).exists():
                errors.append('邮箱已被使用')
            
            if not real_name:
                errors.append('真实姓名不能为空')
            
            if student_id and UserProfile.objects.exclude(user=target_user).filter(student_id=student_id).exists():
                errors.append('学号已被使用')
            
            if not errors:
                # 更新用户基本信息
                target_user.email = email
                target_user.save()
                
                # 更新用户资料信息
                try:
                    profile = target_user.profile
                    profile.real_name = real_name
                    profile.student_id = student_id
                    profile.phone = phone
                    profile.wechat = wechat
                    profile.political_status = political_status
                    profile.save()
                except UserProfile.DoesNotExist:
                    # 如果用户没有资料，创建一个
                    import uuid
                    unique_student_id = student_id or f"USER_{target_user.username}_{str(uuid.uuid4())[:8]}"
                    
                    profile = UserProfile.objects.create(
                        user=target_user,
                        role='president',  # 默认角色
                        real_name=real_name,
                        student_id=unique_student_id,
                        phone=phone,
                        wechat=wechat,
                        political_status=political_status
                    )
                
                success_messages.append(f'已成功更新用户 {target_user.username} 的详细信息')
        

    # 获取用户角色信息
    try:
        profile = target_user.profile
    except UserProfile.DoesNotExist:
        profile = None
    
    context = {
        'target_user': target_user,
        'profile': profile,
        'errors': errors,
        'success_messages': success_messages,
        'is_admin_view': True,  # 标记为管理员视图
        'ROLE_CHOICES': UserProfile.ROLE_CHOICES,
        'POLITICAL_STATUS_CHOICES': UserProfile.POLITICAL_STATUS_CHOICES,
    }
    
    return render(request, 'clubs/auth/change_account_settings.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def change_user_role(request, user_id):
    """修改用户角色 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以修改用户角色')
        return redirect('clubs:index')
    
    target_user = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        new_role = request.POST.get('new_role', '')
        
        if new_role not in ['president', 'staff', 'admin']:
            messages.error(request, '角色不合法')
            context = {'user': target_user}
            return render(request, 'clubs/admin/change_user_role.html', context)
        
        # 干事注册需要管理员同意（已确保只有管理员可以执行此操作）
        
        try:
            profile = target_user.profile
            old_role = profile.get_role_display()
            profile.role = new_role
            profile.save()
            role_display = dict(UserProfile.ROLE_CHOICES).get(new_role, new_role)
            messages.success(request, f'已将 {target_user.username} 的角色从「{old_role}」更改为「{role_display}」')
        except UserProfile.DoesNotExist:
            # 创建UserProfile时处理student_id唯一性约束
            # 为新创建的用户生成一个唯一的student_id，使用用户名+时间戳确保唯一性
            import uuid
            unique_student_id = f"USER_{target_user.username}_{str(uuid.uuid4())[:8]}"
            
            profile = UserProfile.objects.create(
                user=target_user, 
                role=new_role,
                student_id=unique_student_id  # 设置唯一的student_id
            )
            role_display = dict(UserProfile.ROLE_CHOICES).get(new_role, new_role)
            messages.success(request, f'已为 {target_user.username} 创建角色：「{role_display}」')
        
        return redirect('clubs:manage_users')
    
    # GET 请求
    try:
        profile = target_user.profile
    except UserProfile.DoesNotExist:
        profile = None
    
    context = {
        'user': target_user,
        'profile': profile,
    }
    return render(request, 'clubs/admin/change_user_role.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(['GET', 'POST'])
def change_staff_attributes(request, user_id):
    """修改干事的部门和职级属性 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以修改干事属性')
        return redirect('clubs:index')
    
    target_user = get_object_or_404(User, pk=user_id)
    
    # 检查目标用户是否为干事
    try:
        profile = target_user.profile
        if profile.role != 'staff':
            messages.error(request, '该用户不是干事，无法修改干事属性')
            return redirect('clubs:manage_users')
    except UserProfile.DoesNotExist:
        messages.error(request, '用户角色信息不存在')
        return redirect('clubs:manage_users')
    
    if request.method == 'POST':
        department = request.POST.get('department', '').strip()
        staff_level = request.POST.get('staff_level', '').strip()
        
        # 验证部门和职级
        valid_departments = dict(UserProfile.DEPARTMENT_CHOICES).keys()
        valid_levels = dict(UserProfile.STAFF_LEVEL_CHOICES).keys()
        
        if department and department not in valid_departments:
            messages.error(request, '部门选择无效')
            return redirect('clubs:manage_users')
        
        if staff_level and staff_level not in valid_levels:
            messages.error(request, '职级选择无效')
            return redirect('clubs:manage_users')
        
        try:
            old_department = profile.get_department_display() if profile.department else '未设定'
            old_level = profile.get_staff_level_display() if profile.staff_level else '未设定'
            
            profile.department = department if department else None
            profile.staff_level = staff_level if staff_level else profile.staff_level
            profile.save()
            
            new_department = profile.get_department_display() if profile.department else '未设定'
            new_level = profile.get_staff_level_display()
            
            messages.success(request, f'已修改 {target_user.username} 的干事属性：部门「{old_department}」→「{new_department}」，职级「{old_level}」→「{new_level}」')
        except Exception as e:
            messages.error(request, f'修改失败：{str(e)}')
        
        return redirect('clubs:manage_users')
    
    context = {
        'user': target_user,
        'profile': profile,
        'department_choices': UserProfile.DEPARTMENT_CHOICES,
        'staff_level_choices': UserProfile.STAFF_LEVEL_CHOICES,
    }
    return render(request, 'clubs/admin/change_staff_attributes.html', context)



@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(['GET', 'POST'])
def manage_smtp_config(request):
    """管理SMTP邮箱配置"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以管理SMTP配置')
        return redirect('clubs:index')
    
    from .models import SMTPConfig
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        config_id = request.POST.get('config_id', '')
        
        if action == 'create':
            provider = request.POST.get('provider', '').strip()
            smtp_host = request.POST.get('smtp_host', '').strip()
            smtp_port = request.POST.get('smtp_port', '').strip()
            sender_email = request.POST.get('sender_email', '').strip()
            sender_password = request.POST.get('sender_password', '').strip()
            use_tls = 'use_tls' in request.POST  # checkbox 未勾选时不会在 POST 中
            
            errors = []
            if not provider:
                errors.append('邮箱服务商不能为空')
            if not smtp_host:
                errors.append('SMTP服务器地址不能为空')
            if not smtp_port:
                errors.append('SMTP端口不能为空')
            if not sender_email:
                errors.append('发送邮箱不能为空')
            if not sender_password:
                errors.append('邮箱密码/授权码不能为空')
            
            try:
                if smtp_port:
                    int(smtp_port)
            except ValueError:
                errors.append('SMTP端口必须是数字')
            
            if errors:
                configs = SMTPConfig.objects.all()
                return render(request, 'clubs/admin/smtp_config.html', {
                    'configs': configs,
                    'errors': errors,
                    'form_data': request.POST,
                })
            
            # 创建新配置时，取消其他配置的激活状态
            if request.POST.get('is_active') == 'on':
                SMTPConfig.objects.all().update(is_active=False)
            
            SMTPConfig.objects.create(
                provider=provider,
                smtp_host=smtp_host,
                smtp_port=int(smtp_port),
                sender_email=sender_email,
                sender_password=sender_password,
                use_tls=use_tls,
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'SMTP配置创建成功')
            return redirect('clubs:manage_smtp_config')
        
        elif action == 'delete':
            config = get_object_or_404(SMTPConfig, pk=config_id)
            config.delete()
            messages.success(request, 'SMTP配置已删除')
            return redirect('clubs:manage_smtp_config')
        
        elif action == 'activate':
            # 取消其他配置的激活状态
            SMTPConfig.objects.all().update(is_active=False)
            config = get_object_or_404(SMTPConfig, pk=config_id)
            config.is_active = True
            config.save()
            messages.success(request, f'SMTP配置已激活：{config.sender_email}')
            return redirect('clubs:manage_smtp_config')
        
        elif action == 'edit':
            config = get_object_or_404(SMTPConfig, pk=config_id)
            
            provider = request.POST.get('provider', '').strip()
            smtp_host = request.POST.get('smtp_host', '').strip()
            smtp_port = request.POST.get('smtp_port', '').strip()
            sender_email = request.POST.get('sender_email', '').strip()
            sender_password = request.POST.get('sender_password', '').strip()
            use_tls = 'use_tls' in request.POST
            
            errors = []
            if not provider:
                errors.append('邮箱服务商不能为空')
            if not smtp_host:
                errors.append('SMTP服务器地址不能为空')
            if not smtp_port:
                errors.append('SMTP端口不能为空')
            if not sender_email:
                errors.append('发送邮箱不能为空')
            
            try:
                if smtp_port:
                    int(smtp_port)
            except ValueError:
                errors.append('SMTP端口必须是数字')
            
            if errors:
                configs = SMTPConfig.objects.all()
                return render(request, 'clubs/admin/smtp_config.html', {
                    'configs': configs,
                    'errors': errors,
                    'editing_config': config,
                })
            
            # 更新配置
            config.provider = provider
            config.smtp_host = smtp_host
            config.smtp_port = int(smtp_port)
            config.sender_email = sender_email
            if sender_password:  # 只有填写了新密码才更新
                config.sender_password = sender_password
            config.use_tls = use_tls
            config.save()
            
            messages.success(request, 'SMTP配置更新成功')
            return redirect('clubs:manage_smtp_config')
        
        elif action == 'test_email':
            # 发送测试邮件
            test_email = request.POST.get('test_email', '').strip()
            if not test_email:
                messages.error(request, '请输入测试邮箱地址')
                return redirect('clubs:manage_smtp_config')
            
            config = get_object_or_404(SMTPConfig, pk=config_id)
            
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            try:
                # 创建邮件
                msg = MIMEMultipart()
                msg['From'] = config.sender_email
                msg['To'] = test_email
                msg['Subject'] = 'CManager SMTP配置测试邮件'
                
                body = f'''
您好！

这是一封来自 CManager 系统的测试邮件。

如果您收到了这封邮件，说明 SMTP 配置成功！

配置信息：
- 服务商：{config.get_provider_display()}
- SMTP服务器：{config.smtp_host}:{config.smtp_port}
- 发送邮箱：{config.sender_email}
- TLS加密：{'已启用' if config.use_tls else '未启用'}

此邮件为系统自动发送，请勿回复。
                '''
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                # 连接SMTP服务器并发送
                # 端口465/994通常使用SSL，端口587使用STARTTLS，端口25通常无加密
                if config.smtp_port in [465, 994]:
                    # SSL连接（端口465/994）
                    server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
                    server.ehlo()
                elif config.use_tls:
                    # STARTTLS（端口587等）
                    server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                else:
                    # 无加密（端口25等）- 某些服务器需要特殊处理
                    import socket
                    # 先测试端口连通性
                    sock = socket.create_connection((config.smtp_host, config.smtp_port), timeout=30)
                    sock.close()
                    # 使用较长超时并设置调试
                    server = smtplib.SMTP(timeout=30)
                    server.connect(config.smtp_host, config.smtp_port)
                    server.ehlo()
                
                server.login(config.sender_email, config.sender_password)
                server.sendmail(config.sender_email, [test_email], msg.as_string())
                server.quit()
                
                messages.success(request, f'测试邮件已成功发送到 {test_email}')
            except smtplib.SMTPAuthenticationError as e:
                messages.error(request, f'SMTP认证失败：邮箱或密码/授权码错误 ({e.smtp_code}: {e.smtp_error})')
            except smtplib.SMTPConnectError as e:
                messages.error(request, f'SMTP连接失败：无法连接到服务器 ({str(e)})')
            except smtplib.SMTPServerDisconnected as e:
                messages.error(request, f'SMTP服务器断开连接：{str(e)}。建议尝试SSL端口(465/994)')
            except smtplib.SMTPException as e:
                messages.error(request, f'SMTP错误：{str(e)}')
            except socket.timeout:
                messages.error(request, 'SMTP连接超时：请检查服务器地址和端口')
            except ConnectionRefusedError:
                messages.error(request, 'SMTP连接被拒绝：请检查端口是否正确')
            except Exception as e:
                messages.error(request, f'发送失败：{type(e).__name__}: {str(e)}')
            
            return redirect('clubs:manage_smtp_config')
    
    configs = SMTPConfig.objects.all()
    context = {
        'configs': configs,
    }
    return render(request, 'clubs/admin/smtp_config.html', context)


# review_club_info_change 视图已整合到 review_request 中


def toggle_review_enabled(request, club_id):
    """
    切换社团的年审功能启用状态
    """
    # 检查用户权限 - 干事和管理员都可以操作
    if not is_staff_or_admin(request.user):
        return HttpResponseForbidden("您没有权限执行此操作")

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        from django.http import Http404
        return Http404("社团不存在")

    # 切换年审启用状态
    club.review_enabled = not club.review_enabled
    club.save()

    messages.success(request, f"社团年审功能已{'启用' if club.review_enabled else '禁用'}")
    return redirect(request.META.get('HTTP_REFERER', 'clubs:staff_management'))

@login_required(login_url=settings.LOGIN_URL)
def zip_materials(request, obj, materials, zip_filename, check_permission_func):
    """通用的材料打包函数，将指定材料列表打包为zip文件并下载"""
    import tempfile
    import zipfile
    import os
    from django.http import FileResponse
    import urllib.parse
    
    # 检查权限
    if not check_permission_func():
        messages.error(request, '您没有权限下载此材料')
        return redirect('clubs:index')
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        # 创建zip文件
        zip_path = os.path.join(temp_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 处理每个材料文件
            for file_field, title in materials:
                if file_field and hasattr(file_field, 'path'):
                    file_path = file_field.path
                    # 获取原始文件名和扩展名
                    original_filename = os.path.basename(file_path)
                    file_ext = os.path.splitext(original_filename)[1]
                    
                    # 创建新的文件名，添加序号和标题
                    new_filename = f"{title}{file_ext}"
                    
                    # 将文件添加到zip中
                    zipf.write(file_path, new_filename)
        
        # 创建HTTP响应
        response = FileResponse(open(zip_path, 'rb'), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'' + urllib.parse.quote(zip_filename)
        
        return response
    finally:
        # 注意：这里我们不能直接删除temp_dir，因为FileResponse还在使用它
        pass


@login_required(login_url=settings.LOGIN_URL)
def zip_review_docs(request, submission_id):
    """打包所有年审材料为zip文件并下载"""
    import tempfile
    import shutil
    import zipfile
    from django.http import HttpResponse
    
    submission = get_object_or_404(ReviewSubmission, pk=submission_id)
    
    # 定义权限检查函数
    def check_permission():
        return _is_staff(request.user) or submission.club.president == request.user
    
    # 定义要打包的材料列表，按顺序
    materials = [
        (submission.self_assessment_form, '1_自查表'),
        (submission.club_constitution, '2_社团章程'),
        (submission.leader_learning_work_report, '3_负责人学习及工作情况表'),
        (submission.annual_activity_list, '4_社团年度活动清单'),
        (submission.advisor_performance_report, '5_指导教师履职情况表'),
        (submission.financial_report, '6_年度财务情况表'),
        (submission.member_composition_list, '7_社团成员构成表'),
        (submission.new_media_account_report, '8_新媒体账号及运维情况表'),
    ]
    
    # 如果有其他材料，也添加进来
    if submission.other_materials:
        materials.append((submission.other_materials, '9_其他材料'))
    
    # 创建zip文件，使用简化的文件名格式
    zip_filename = f"{submission.club.name}-{submission.submission_year}.zip"
    
    # 调用通用的zip_materials函数
    return zip_materials(request, submission, materials, zip_filename, check_permission)

@login_required(login_url=settings.LOGIN_URL)
def zip_club_registration_docs(request, registration_id):
    """为已有社团的 `ClubRegistration` 打包材料并下载。"""
    registration = get_object_or_404(ClubRegistration, pk=registration_id)

    def check_permission():
        return is_staff_or_admin(request.user)

    materials = [
        (registration.registration_form, '1_社团注册申请表'),
        (registration.basic_info_form, '2_基础信息表'),
        (registration.membership_fee_form, '3_社团会费表'),
        (registration.leader_change_application, '4_负责人变动申请'),
        (registration.meeting_minutes, '5_会议纪要'),
        (registration.name_change_application, '6_名称变更申请'),
        (registration.advisor_change_application, '7_指导老师变动申请'),
        (registration.business_advisor_change_application, '8_业务指导单位变动申请'),
        (registration.new_media_application, '9_新媒体平台建立申请'),
    ]

    if hasattr(registration, 'other_materials') and registration.other_materials:
        materials.append((registration.other_materials, '9_其他材料'))

    zip_filename = f"{registration.club.name}-社团注册.zip"
    return zip_materials(request, registration, materials, zip_filename, check_permission)


@login_required(login_url=settings.LOGIN_URL)
def zip_registration_request_docs(request, request_id):
    """为社团创建申请 `ClubRegistrationRequest` 打包材料并下载。"""
    registration = get_object_or_404(ClubRegistrationRequest, pk=request_id)

    def check_permission():
        return is_staff_or_admin(request.user)

    # 使用动态函数获取材料列表
    m_list = get_dynamic_materials_list(registration, 'club_registration')
    materials = []
    for item in m_list:
        if item.get('file'):
            materials.append((item['file'], item['name']))

    zip_filename = f"{registration.club_name}-社团申请.zip"
    return zip_materials(request, registration, materials, zip_filename, check_permission)


# 已移除：原来的通用兼容视图 zip_registration_docs
# 为了强制使用更明确的路由和权限边界，已删除旧实现。
# 如果需要相应的下载逻辑，请使用以下两个视图：
# - zip_club_registration_docs(request, registration_id)
# - zip_registration_request_docs(request, request_id)
# 旧路由和视图已从项目中移除。

@login_required(login_url=settings.LOGIN_URL)
def zip_reimbursement_docs(request, reimbursement_id):
    """打包所有报销材料为zip文件并下载"""
    from clubs.models import Reimbursement
    
    reimbursement = get_object_or_404(Reimbursement, pk=reimbursement_id)
    
    # 定义权限检查函数
    def check_permission():
        return _is_staff(request.user) or reimbursement.club.president == request.user
    
    # 使用动态函数获取材料列表
    m_list = get_dynamic_materials_list(reimbursement, 'reimbursement')
    materials = []
    for item in m_list:
        if item.get('file'):
            materials.append((item['file'], item['name']))
    
    # 兼容: 如果没有动态材料但有 receipt_file (旧数据/模型字段), 也添加进去
    if not materials and reimbursement.receipt_file:
         materials.append((reimbursement.receipt_file, '凭证'))
    
    if not materials:
        messages.error(request, '该报销记录没有附件')
        return redirect('clubs:staff_dashboard')
    
    # 创建zip文件
    zip_filename = f"{reimbursement.club.name}-报销材料-{reimbursement.id}.zip"
    
    # 调用通用的zip_materials函数
    return zip_materials(request, reimbursement, materials, zip_filename, check_permission)

@login_required(login_url=settings.LOGIN_URL)
def zip_president_transition_docs(request, transition_id):
    """打包所有社长变更材料为zip文件并下载"""
    from clubs.models import PresidentTransition
    
    transition = get_object_or_404(PresidentTransition, pk=transition_id)
    
    # 定义权限检查函数
    def check_permission():
        return _is_staff(request.user) or transition.club.president == request.user
    
    # 使用动态函数获取材料列表
    m_list = get_dynamic_materials_list(transition, 'president_transition')
    materials = []
    for item in m_list:
        if item.get('file'):
            materials.append((item['file'], item['name']))
            
    # 兼容: 如果没有动态材料但有 transition_form (旧数据/模型字段)
    if not materials and transition.transition_form:
        materials.append((transition.transition_form, '社长换届申请表'))
    
    if not materials:
        messages.error(request, '该社长变更记录没有附件')
        return redirect('clubs:staff_dashboard')
    
    # 创建zip文件
    zip_filename = f"{transition.club.name}-社长变更材料.zip"
    
    # 调用通用的zip_materials函数
    return zip_materials(request, transition, materials, zip_filename, check_permission)

@login_required(login_url=settings.LOGIN_URL)
def toggle_all_review_enabled(request):
    """
    切换所有社团的年审功能启用状态
    """
    # 检查用户权限 - 干事和管理员都可以操作
    if not _is_staff(request.user) and not _is_admin(request.user):
        return HttpResponseForbidden("您没有权限执行此操作")

    # 获取所有社团
    all_clubs = Club.objects.all()
    
    if not all_clubs.exists():
        messages.warning(request, '暂无社团，无需操作')
        return redirect('clubs:staff_dashboard')
    
    # 检查是否所有社团都已开启
    all_enabled = all_clubs.filter(review_enabled=True).count() == all_clubs.count()
    
    # 切换状态：如果全部开启则关闭，否则开启
    new_status = not all_enabled
    
    # 更新所有社团的年审状态
    Club.objects.update(review_enabled=new_status)

    messages.success(request, f"所有社团年审功能已{'启用' if new_status else '禁用'}")
    return redirect('clubs:staff_dashboard')


@login_required(login_url=settings.LOGIN_URL)
def toggle_registration_enabled(request):
    """
    统一开启/关闭社团注册功能
    - 关闭时：关闭当前活跃的注册周期，禁用所有社团注册
    - 开启时：创建新的注册周期，启用所有社团注册
    """
    # 检查用户权限 - 仅干事和管理员可以操作
    if not is_staff_or_admin(request.user):
        return HttpResponseForbidden("您没有权限执行此操作")
    
    # 获取所有社团和当前活跃的注册周期
    all_clubs = Club.objects.all()
    active_period = RegistrationPeriod.objects.filter(is_active=True).first()
    
    if active_period:
        # 如果存在活跃周期，则关闭它并禁用所有社团的注册功能
        active_period.is_active = False
        active_period.end_date = timezone.now()
        active_period.save()
        Club.objects.update(registration_enabled=False)
        messages.success(request, f"社团注册功能已关闭（第{active_period.period_number}次注册周期已结束）")
    else:
        # 如果不存在活跃周期，则创建新的周期并启用所有社团的注册功能
        new_period = RegistrationPeriod.objects.create(
            is_active=True,
            created_by=request.user
        )
        Club.objects.update(registration_enabled=True)
        messages.success(request, f"社团注册功能已开启（第{new_period.period_number}次注册周期已启动）")
    
    return redirect(request.META.get('HTTP_REFERER', 'clubs:staff_management'))


@login_required(login_url=settings.LOGIN_URL)



@login_required(login_url=settings.LOGIN_URL)
def toggle_club_registration_enabled(request, club_id):
    """切换单个社团的注册开启状态"""
    if not is_staff_or_admin(request.user):
        return HttpResponseForbidden("您没有权限执行此操作")

    club = get_object_or_404(Club, pk=club_id)
    club.registration_enabled = not club.registration_enabled
    club.save()
    messages.success(request, f"社团注册功能已{'启用' if club.registration_enabled else '禁用'}：{club.name}")
    return redirect(request.META.get('HTTP_REFERER', 'clubs:staff_management'))


def change_club_status(request, club_id):
    """
    改变社团的活跃状态 - 仅干事可用
    """
    # 检查用户权限 - 仅干事和管理员可以操作
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:club_detail', club_id=club_id)
    
    club = get_object_or_404(Club, pk=club_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status', club.status)
        
        # 验证状态值
        valid_statuses = ['active', 'inactive', 'suspended']
        if new_status not in valid_statuses:
            messages.error(request, '无效的社团状态')
            return redirect('clubs:club_detail', club_id=club_id)
        
        # 如果状态没有改变
        if new_status == club.status:
            messages.info(request, f'社团状态已是 {club.get_status_display()}')
            return redirect('clubs:club_detail', club_id=club_id)
        
        old_status = club.get_status_display()
        club.status = new_status
        club.save()
        
        messages.success(request, f'社团状态已从"{old_status}"更改为"{club.get_status_display()}"')
        return redirect('clubs:club_detail', club_id=club_id)
    
    # GET 请求：返回状态变更选项
    context = {
        'club': club,
        'status_choices': Club._meta.get_field('status').choices,
        'current_status': club.status,
    }
    return render(request, 'clubs/change_club_status.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["POST"])
def update_club_description(request, club_id):
    club = get_object_or_404(Club, pk=club_id)

    if not (is_staff_or_admin(request.user) or (_is_president(request.user) and club.president_id == request.user.id)):
        return HttpResponseForbidden("您没有权限执行此操作")

    club.description = request.POST.get('description', '').strip()
    club.save(update_fields=['description'])
    messages.success(request, "社团简介已更新")
    return redirect('clubs:club_detail', club_id=club_id)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def direct_edit_club_info(request, club_id):
    """
    直接修改社团信息 - 仅干事和管理员可用（无需审核）
    """
    # 检查用户权限 - 仅干事和管理员可以操作
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:club_detail', club_id=club_id)
    
    club = get_object_or_404(Club, pk=club_id)
    
    if request.method == 'POST':
        # 获取表单数据
        new_name = request.POST.get('name', '').strip()
        new_description = request.POST.get('description', '').strip()
        new_founded_date = request.POST.get('founded_date', '')
        new_members_count = request.POST.get('members_count', '')
        
        # 验证
        errors = []
        
        if not new_name:
            errors.append('社团名称不能为空')
        
        if new_members_count and not new_members_count.isdigit():
            errors.append('成员数量必须是数字')
        
        if errors:
            context = {
                'club': club,
                'errors': errors,
                'form_data': request.POST,
            }
            return render(request, 'clubs/direct_edit_club_info.html', context)
        
        # 更新社团信息
        if new_name:
            club.name = new_name
        
        if new_description:
            club.description = new_description
        else:
            club.description = ''
        
        if new_founded_date:
            club.founded_date = new_founded_date
        
        if new_members_count:
            club.members_count = int(new_members_count)
        
        club.save()
        
        messages.success(request, '社团信息已成功更新！')
        return redirect('clubs:club_detail', club_id=club_id)
    
    # GET 请求：显示表单
    context = {
        'club': club,
    }
    return render(request, 'clubs/direct_edit_club_info.html', context)


def delete_club(request, club_id):
    """
    删除社团 - 仅干事和管理员可用
    """
    # 检查用户权限 - 仅干事和管理员可以操作
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
    
    club = get_object_or_404(Club, pk=club_id)
    
    if request.method == 'POST':
        # 获取并验证用户输入的确认社团名称
        confirm_club_name = request.POST.get('confirm_club_name')
        
        # 检查确认社团名称是否正确
        if confirm_club_name == club.name:
                club_name = club.name
                club.delete()
                messages.success(request, f'社团 "{club_name}" 已成功删除')
                return redirect('clubs:index')  # 删除后重定向到首页
        else:
            # 显示错误消息
            messages.error(request, '社团名称输入错误，删除失败！')
    
    # GET 请求：返回确认页面
    context = {
        'club': club,
    }
    return render(request, 'clubs/delete_club.html', context)


# ==================== 社长换届申请相关视图 ====================




@login_required
def view_president_transitions(request, club_id):
    """查看社长换届申请记录"""
    club = get_object_or_404(Club, pk=club_id)
    
    # 检查用户是否为该社团的社长
    if club.president != request.user:
        messages.error(request, '只有社团社长可以查看换届申请记录')
        return redirect('clubs:club_detail', club_id=club_id)
    
    transitions = PresidentTransition.objects.filter(club=club).order_by('-submitted_at')
    
    context = {
        'club': club,
        'transitions': transitions,
    }
    return render(request, 'clubs/user/view_president_transitions.html', context)





# ==================== 活动申请相关视图 ====================




@login_required
def view_activity_applications(request, club_id):
    """查看活动申请记录"""
    club = get_object_or_404(Club, pk=club_id)
    
    # 检查用户是否为该社团的社长
    if club.president != request.user:
        messages.error(request, '只有社团社长可以查看活动申请记录')
        return redirect('clubs:club_detail', club_id=club_id)
    
    applications = ActivityApplication.objects.filter(club=club).order_by('-submitted_at')
    
    context = {
        'club': club,
        'applications': applications,
    }
    return render(request, 'clubs/user/view_activity_applications.html', context)


# ==================== 222房间借用相关视图 ====================

@login_required
def room222_calendar(request):
    """222房间借用日历视图 - 谷歌日历单日网格风格"""
    # 获取日期参数，默认为今天
    date_str = request.GET.get('date')
    
    if date_str:
        try:
            from datetime import datetime
            view_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            view_date = timezone.now().date()
    else:
        view_date = timezone.now().date()
    
    # 获取前一天和后一天
    from datetime import timedelta
    prev_date = view_date - timedelta(days=1)
    next_date = view_date + timedelta(days=1)
    
    # 获取当天所有有效的预订
    bookings = Room222Booking.objects.filter(
        booking_date=view_date,
        status='active'
    ).select_related('user__profile', 'club').order_by('start_time')
    
    # 定义时间段（按照实际课程时间）
    from datetime import time
    raw_time_slots = [
        {'start': time(8, 15), 'end': time(9, 55), 'label': '第1-2节'},
        {'start': time(10, 5), 'end': time(11, 40), 'label': '第3-4节'},
        {'start': time(11, 40), 'end': time(13, 0), 'label': '午休'},
        {'start': time(13, 0), 'end': time(14, 35), 'label': '第5-6节'},
        {'start': time(14, 45), 'end': time(16, 20), 'label': '第7-8节'},
        {'start': time(16, 20), 'end': time(18, 0), 'label': '课外时间'},
        {'start': time(18, 0), 'end': time(19, 0), 'label': '晚餐'},
        {'start': time(19, 0), 'end': time(20, 0), 'label': '晚间1'},
        {'start': time(20, 0), 'end': time(21, 0), 'label': '晚间2'},
        {'start': time(21, 0), 'end': time(22, 0), 'label': '晚间3'},
    ]
    
    # 计算总分钟数（从8:15到22:00）
    day_start_minutes = 8 * 60 + 15
    total_minutes = (22 * 60) - day_start_minutes  # 13小时45分钟 = 825分钟

    time_slots = []
    for slot in raw_time_slots:
        slot_start_minutes = slot['start'].hour * 60 + slot['start'].minute
        slot_end_minutes = slot['end'].hour * 60 + slot['end'].minute
        duration_minutes = slot_end_minutes - slot_start_minutes
        top_percent = ((slot_start_minutes - day_start_minutes) / total_minutes) * 100
        height_percent = (duration_minutes / total_minutes) * 100
        
        # 检查该时间段是否有预约覆盖
        has_booking = False
        for booking in bookings:
            booking_start = booking.start_time.hour * 60 + booking.start_time.minute
            booking_end = booking.end_time.hour * 60 + booking.end_time.minute
            # 如果预约时间与时间段有重叠
            if booking_start < slot_end_minutes and booking_end > slot_start_minutes:
                has_booking = True
                break

        time_slots.append({
            'start': slot['start'],
            'end': slot['end'],
            'label': slot['label'],
            'height_percent': height_percent,
            'top_percent': top_percent,
            'has_booking': has_booking,
        })
    
    # 为每个预订计算其在时间轴上的位置和高度
    bookings_with_position = []
    for booking in bookings:
        # 计算开始时间在时间轴上的位置（以分钟为单位，从8:15开始）
        start_minutes = (booking.start_time.hour * 60 + booking.start_time.minute) - day_start_minutes
        end_minutes = (booking.end_time.hour * 60 + booking.end_time.minute) - day_start_minutes
        
        # 确保不超出范围
        start_minutes = max(0, start_minutes)
        end_minutes = min(total_minutes, end_minutes)
        
        # 计算持续时间和位置百分比
        duration_minutes = end_minutes - start_minutes
        top_percent = (start_minutes / total_minutes) * 100
        height_percent = (duration_minutes / total_minutes) * 100
        
        bookings_with_position.append({
            'booking': booking,
            'top_percent': top_percent,
            'height_percent': height_percent,
            'can_edit': booking.can_edit(request.user),
            'can_delete': booking.can_delete(request.user),
        })
    
    # 计算周的起始日期（周一）
    from datetime import datetime
    week_start = view_date - timedelta(days=view_date.weekday())
    week_end = week_start + timedelta(days=6)
    
    context = {
        'view_date': view_date,
        'prev_date': prev_date,
        'next_date': next_date,
        'bookings': bookings_with_position,
        'time_slots': time_slots,
        'is_today': view_date == timezone.now().date(),
        'week_start': week_start,
        'week_end': week_end,
    }
    return render(request, 'clubs/room222_calendar.html', context)


@login_required
def submit_room222_booking(request):
    """提交222房间借用申请 - 无需审核，直接创建"""
    from datetime import datetime
    if request.method == 'POST':
        # 获取表单数据
        club_id = request.POST.get('club_id')
        booking_date_str = request.POST.get('booking_date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        purpose = request.POST.get('purpose')
        participant_count = request.POST.get('participant_count')
        contact_phone = request.POST.get('contact_phone')
        special_requirements = request.POST.get('special_requirements', '')
        
        # 验证必填字段
        if not all([booking_date_str, start_time_str, end_time_str, purpose, 
                   participant_count, contact_phone]):
            messages.error(request, '请填写所有必填字段')
            return redirect('clubs:submit_room222_booking')
        
        # 转换日期、时间字符串为对象
        from datetime import datetime
        try:
            booking_date = datetime.strptime(booking_date_str, '%Y-%m-%d').date()
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            messages.error(request, '时间格式不正确')
            return redirect('clubs:submit_room222_booking')
        
        # 获取社团（如果选择了）
        club = None
        if club_id:
            club = get_object_or_404(Club, pk=club_id)
            # 验证用户是否为该社团社长
            if club.president != request.user:
                messages.error(request, '您不是该社团的社长')
                return redirect('clubs:submit_room222_booking')
        
        # 创建借用记录（状态为active，无需审核）
        booking = Room222Booking(
            user=request.user,
            club=club,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            purpose=purpose,
            participant_count=participant_count,
            contact_phone=contact_phone,
            special_requirements=special_requirements,
            status='active'
        )
        
        # 检查时间冲突
        if booking.has_conflict():
            messages.error(request, '该时间段已被预订，请选择其他时间')
            return redirect('clubs:submit_room222_booking')
        
        booking.save()
        messages.success(request, '222房间预约成功！')
        return redirect('clubs:room222_calendar')
    
    # GET 请求
    # 获取用户是社长的所有社团
    user_clubs = Club.objects.filter(president=request.user, status='active')
    
    # 获取日期参数（从日历页面跳转过来时）
    selected_date = request.GET.get('date', '')
    selected_start_time = request.GET.get('start_time', '')
    selected_end_time = request.GET.get('end_time', '')

    # 获取今天的日期
    today = timezone.now().date().strftime('%Y-%m-%d')

    # 获取当天已存在的预约，用于前端快速校验
    booked_intervals = []
    if selected_date:
        try:
            selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            existing = Room222Booking.objects.filter(
                booking_date=selected_date_obj,
                status='active'
            ).values('start_time', 'end_time')
            booked_intervals = [
                {
                    'start': item['start_time'].strftime('%H:%M'),
                    'end': item['end_time'].strftime('%H:%M'),
                }
                for item in existing
            ]
        except ValueError:
            booked_intervals = []

    context = {
        'user_clubs': user_clubs,
        'selected_date': selected_date,
        'selected_start_time': selected_start_time,
        'selected_end_time': selected_end_time,
        'today': today,
        'booked_intervals': booked_intervals,
    }
    return render(request, 'clubs/submit_room222_booking.html', context)


@login_required
def my_room222_bookings(request):
    """查看我的222房间借用记录"""
    bookings = Room222Booking.objects.filter(
        user=request.user
    ).order_by('-booking_date', '-start_time')
    
    context = {
        'bookings': bookings,
    }
    return render(request, 'clubs/my_room222_bookings.html', context)


@login_required
def edit_room222_booking(request, booking_id):
    """编辑222房间借用"""
    booking = get_object_or_404(Room222Booking, pk=booking_id)
    
    # 检查权限
    if not booking.can_edit(request.user):
        messages.error(request, '您没有权限编辑此预约')
        return redirect('clubs:my_room222_bookings')
    
    if request.method == 'POST':
        # 获取表单数据
        club_id = request.POST.get('club_id')
        booking_date = request.POST.get('booking_date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        purpose = request.POST.get('purpose')
        participant_count = request.POST.get('participant_count')
        contact_phone = request.POST.get('contact_phone')
        special_requirements = request.POST.get('special_requirements', '')
        
        # 验证必填字段
        if not all([booking_date, start_time, end_time, purpose, 
                   participant_count, contact_phone]):
            messages.error(request, '请填写所有必填字段')
            return redirect('clubs:edit_room222_booking', booking_id=booking_id)
        
        # 获取社团（如果选择了）
        club = None
        if club_id:
            club = get_object_or_404(Club, pk=club_id)
        
        # 更新预订信息
        booking.club = club
        booking.booking_date = booking_date
        booking.start_time = start_time
        booking.end_time = end_time
        booking.purpose = purpose
        booking.participant_count = participant_count
        booking.contact_phone = contact_phone
        booking.special_requirements = special_requirements
        
        # 检查时间冲突
        if booking.has_conflict():
            messages.error(request, '该时间段已被其他预订占用，请选择其他时间')
            return redirect('clubs:edit_room222_booking', booking_id=booking_id)
        
        booking.save()
        messages.success(request, '预约已成功更新')
        return redirect('clubs:my_room222_bookings')
    
    # GET 请求
    user_clubs = Club.objects.filter(president=request.user, status='active')
    
    context = {
        'booking': booking,
        'user_clubs': user_clubs,
    }
    return render(request, 'clubs/edit_room222_booking.html', context)


@login_required
def delete_room222_booking(request, booking_id):
    """删除/取消222房间借用"""
    booking = get_object_or_404(Room222Booking, pk=booking_id)
    
    # 检查权限
    if not booking.can_delete(request.user):
        messages.error(request, '您没有权限删除此预约')
        return redirect('clubs:my_room222_bookings')
    
    if request.method == 'POST':
        booking_info = f"{booking.booking_date} {booking.start_time}-{booking.end_time}"
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, f'已取消预约：{booking_info}')
        return redirect('clubs:my_room222_bookings')
    
    context = {
        'booking': booking,
    }
    return render(request, 'clubs/delete_room222_booking.html', context)


# ==================== 活动申请功能 ====================

@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def submit_activity_application(request, club_id):
    """提交活动申请 - 仅社团社长可用"""
    # 当前用户负责的社团列表（社长身份）
    user_clubs = Club.objects.filter(president=request.user)
    if not user_clubs.exists():
        messages.error(request, '您目前没有负责的社团，无法提交活动申请')
        return redirect('clubs:user_dashboard')

    # 允许通过表单选择社团，默认为URL中的club_id
    selected_club_id = request.POST.get('club_id', club_id)
    try:
        club = user_clubs.get(pk=selected_club_id)
    except Club.DoesNotExist:
        messages.error(request, '仅能为自己负责的社团提交活动申请')
        return redirect('clubs:user_dashboard')

    # 获取动态材料要求
    requirements = MaterialRequirement.objects.filter(
        request_type='activity_application', 
        is_active=True
    ).order_by('order')

    if request.method == 'POST':
        activity_name = request.POST.get('activity_name', '').strip()
        activity_type = request.POST.get('activity_type', 'other')
        activity_description = request.POST.get('activity_description', '').strip()
        activity_date = request.POST.get('activity_date', '')
        activity_time_start = request.POST.get('activity_time_start', '')
        activity_time_end = request.POST.get('activity_time_end', '')
        activity_location = request.POST.get('activity_location', '').strip()
        expected_participants = request.POST.get('expected_participants', '0').strip()
        budget = request.POST.get('budget', '0').strip()
        
        # 收集上传的文件
        uploaded_files = {}
        for req in requirements:
            file = request.FILES.get(f'material_{req.id}')
            uploaded_files[req.id] = file
            
            if req.is_required and not file:
                errors.append(f'{req.name}不能为空')

        # 自动填充联系人信息（可选）
        profile = getattr(request.user, 'profile', None)
        contact_person = profile.real_name if profile and profile.real_name else request.user.get_username()
        contact_phone = profile.phone if profile and getattr(profile, 'phone', None) else ''
        
        errors = []
        if not activity_name:
            errors.append('活动名称不能为空')
        if not activity_description:
            errors.append('活动描述不能为空')
        if not activity_date:
            errors.append('活动日期不能为空')
        if not activity_time_start:
            errors.append('活动开始时间不能为空')
        if not activity_time_end:
            errors.append('活动结束时间不能为空')
        if not activity_location:
            errors.append('活动地点不能为空')
        
        # 验证预计人数和预算（必填）
        if not expected_participants:
            errors.append('预计参与人数不能为空')
        else:
            try:
                expected_participants = int(expected_participants)
                if expected_participants <= 0:
                    errors.append('预计参与人数必须大于0')
            except ValueError:
                errors.append('预计参与人数必须是整数')
        
        if not budget:
            errors.append('活动预算不能为空')
        else:
            try:
                budget = float(budget)
                if budget < 0:
                    errors.append('活动预算不能为负数')
            except ValueError:
                errors.append('活动预算必须是数字')

        if errors:
            context = {
                'club': club,
                'clubs': user_clubs,
                'selected_club_id': int(selected_club_id) if selected_club_id else None,
                'errors': errors,
                'activity_name': activity_name,
                'activity_type': activity_type,
                'activity_description': activity_description,
                'activity_date': activity_date,
                'activity_time_start': activity_time_start,
                'activity_time_end': activity_time_end,
                'activity_location': activity_location,
                'expected_participants': expected_participants,
                'budget': budget,
                'contact_person': contact_person,
                'contact_phone': contact_phone,
                'requirements': requirements,
            }
            return render(request, 'clubs/user/submit_activity_application.html', context)
        
        # 准备 application_form 文件 (兼容旧模型字段)
        application_form_file = None
        if uploaded_files:
            # 使用第一个上传的文件作为主申请表
            application_form_file = list(uploaded_files.values())[0]
            
        if application_form_file:
            application_form_file = rename_uploaded_file(application_form_file, club.name, '活动', '申请表')
        
        # 创建活动申请
        try:
            application = ActivityApplication.objects.create(
                club=club,
                activity_name=activity_name,
                activity_type=activity_type,
                activity_description=activity_description,
                activity_date=activity_date,
                activity_time_start=activity_time_start,
                activity_time_end=activity_time_end,
                activity_location=activity_location,
                expected_participants=expected_participants,
                budget=budget,
                application_form=application_form_file,
                contact_person=contact_person,
                contact_phone=contact_phone or '无',
                status='pending'
            )
            
            # 保存 SubmittedFile
            from django.contrib.contenttypes.models import ContentType
            from .models import SubmittedFile
            
            for req in requirements:
                file = uploaded_files.get(req.id)
                if file:
                    # 重命名
                    file = rename_uploaded_file(file, club.name, '活动', req.name)
                    
                    SubmittedFile.objects.create(
                        content_type=ContentType.objects.get_for_model(ActivityApplication),
                        object_id=application.id,
                        requirement=req,
                        file=file
                    )
            
            messages.success(request, '活动申请已提交，等待审核')
            return redirect('clubs:user_dashboard')
        except Exception as e:
            messages.error(request, f'提交失败: {str(e)}')
            return redirect('clubs:submit_activity_application', club_id=club_id)
    
    # GET请求 - 显示表单
    context = {
        'club': club,
        'clubs': user_clubs,
        'selected_club_id': int(selected_club_id) if selected_club_id else None,
        'contact_person': (getattr(getattr(request.user, 'profile', None), 'real_name', None) or request.user.get_username()),
        'contact_phone': (getattr(getattr(request.user, 'profile', None), 'phone', None) or ''),
        'activity_date': '',
        'activity_time_start': '09:00',
        'activity_time_end': '10:00',
        'expected_participants': '',
        'budget': '',
        'requirements': requirements,
    }
    return render(request, 'clubs/user/submit_activity_application.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def submit_president_transition(request, club_id):
    """提交社长换届申请 - 仅社团社长可用"""
    # 获取社团对象
    try:
        club = Club.objects.get(pk=club_id)
    except Club.DoesNotExist:
        messages.error(request, '社团不存在')
        return redirect('clubs:user_dashboard')
    
    # 验证权限：只有当前社团社长可以提交社长换届申请
    is_club_president = Officer.objects.filter(
        user_profile__user=request.user,
        club=club,
        position='president',
        is_current=True
    ).exists()
    
    if not is_club_president:
        messages.error(request, '仅社团社长可以提交社长换届申请')
        return redirect('clubs:user_dashboard')
    
    # 获取动态材料要求
    requirements = MaterialRequirement.objects.filter(
        request_type='president_transition', 
        is_active=True
    ).order_by('order')

    # 验证文件函数
    def validate_file(file, requirement):
        if not file:
            return None
        
        # 检查扩展名
        allowed_exts = [ext.strip().lower() for ext in requirement.allowed_extensions.split(',')]
        ext = '.' + file.name.lower().split('.')[-1]
        if ext not in allowed_exts:
            return f'{requirement.name}必须是以下格式: {requirement.allowed_extensions}'
        
        # 检查大小
        if file.size > requirement.max_size_mb * 1024 * 1024:
            return f'{requirement.name}文件大小不能超过{requirement.max_size_mb}MB'
        
        return None

    if request.method == 'POST':
        new_president_officer_id = request.POST.get('new_president_officer_id', '')
        transition_date = request.POST.get('transition_date', '')
        transition_reason = request.POST.get('transition_reason', '').strip()
        
        errors = []
        if not new_president_officer_id:
            errors.append('新社长不能为空')
        if not transition_date:
            errors.append('换届日期不能为空')
        if not transition_reason:
            errors.append('换届原因不能为空')
        
        # 验证动态材料
        uploaded_files = {}
        for req in requirements:
            file = request.FILES.get(f'material_{req.id}')
            uploaded_files[req.id] = file
            
            # 验证必填项
            if req.is_required and not file:
                errors.append(f'{req.name}不能为空')
            
            # 验证文件格式和大小
            if file:
                err = validate_file(file, req)
                if err:
                    errors.append(err)

        # 验证新社长是否存在且不是当前社长
        try:
            new_president_officer = Officer.objects.get(
                pk=new_president_officer_id,
                position='president',
                is_current=True
            )
            if new_president_officer.user_profile.user == request.user:
                errors.append('新社长不能是当前社长')
        except Officer.DoesNotExist:
            errors.append('选择的社长不存在或不符合条件')
        
        if errors:
            club_officers = Officer.objects.filter(position='president', is_current=True).exclude(user_profile__user=request.user)
            context = {
                'club': club,
                'errors': errors,
                'club_officers': club_officers, # Fix: Use club_officers not Officer.objects.filter(...) directly again to match GET
                'transition_date': transition_date,
                'transition_reason': transition_reason,
                'requirements': requirements,
                'available_presidents': Officer.objects.filter(position='president', is_current=True).exclude(user_profile__user=request.user) # Keeping this for template compatibility if it uses available_presidents
            }
            # Note: The template uses available_presidents loop, let's double check GET context
            return render(request, 'clubs/user/submit_president_transition.html', context)
        
        # 创建社长换届申请
        try:
            transition = PresidentTransition.objects.create(
                club=club,
                old_president=request.user,
                new_president_officer=new_president_officer,
                transition_date=transition_date,
                transition_reason=transition_reason,
                status='pending'
            )
            
            # 处理文件保存
            for req in requirements:
                file = uploaded_files.get(req.id)
                if file:
                    # 重命名文件
                    file = rename_uploaded_file(file, club.name, '社长换届', req.name)
                    
                    # 1. 保存到 SubmittedFile
                    SubmittedFile.objects.create(
                        content_type=ContentType.objects.get_for_model(PresidentTransition),
                        object_id=transition.id,
                        requirement=req,
                        file=file
                    )
            
            messages.success(request, '社长换届申请已提交，等待审核')
            return redirect('clubs:user_dashboard')
        except Exception as e:
            messages.error(request, f'提交失败: {str(e)}')
            return redirect('clubs:submit_president_transition', club_id=club_id)
    
    # GET请求 - 显示表单
    club_officers = Officer.objects.filter(position='president', is_current=True).exclude(user_profile__user=request.user)
    
    # Check for existing pending transition to show files if needed (usually resubmission logic handles this, but here it's a new submission)
    # If we want to support editing a rejected one, we might need more logic, but for now this is a fresh submission page or resubmission of rejected.
    # The current view logic doesn't seem to load a previous rejected one explicitly unless passed via ID, but here it is club_id based.
    # So it is creating a NEW transition.
    
    context = {
        'club': club,
        'available_presidents': club_officers, # Template uses available_presidents
        'requirements': requirements,
    }
    return render(request, 'clubs/user/submit_president_transition.html', context)


# ==================== 审核活动申请和社长换届 ====================

@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def review_activity_application(request, activity_id):
    """审核活动申请 - 干事审核"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以审核活动申请')
        return redirect('clubs:index')
    
    activity = get_object_or_404(ActivityApplication, pk=activity_id)
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        comment = request.POST.get('comment', '').strip()
        
        if action == 'approve':
            activity.staff_approved = True
            activity.staff_reviewer = request.user
            activity.staff_comment = comment
            activity.staff_reviewed_at = timezone.now()
            activity.update_status()
            
            # 保存审核历史记录
            ActivityApplicationHistory.objects.create(
                activity_application=activity,
                attempt_number=activity.resubmission_attempt,
                activity_name=activity.activity_name,
                activity_date=activity.activity_date,
                submitted_at=activity.submitted_at,
                reviewed_at=activity.staff_reviewed_at,
                reviewer=request.user,
                status='approved',
                reviewer_comment=comment
            )
            
            messages.success(request, '活动申请已批准')
        elif action == 'reject':
            activity.staff_approved = False
            activity.staff_reviewer = request.user
            activity.staff_comment = comment
            activity.staff_reviewed_at = timezone.now()
            activity.update_status()
            
            # 保存审核历史记录
            ActivityApplicationHistory.objects.create(
                activity_application=activity,
                attempt_number=activity.resubmission_attempt,
                activity_name=activity.activity_name,
                activity_date=activity.activity_date,
                submitted_at=activity.submitted_at,
                reviewed_at=activity.staff_reviewed_at,
                reviewer=request.user,
                status='rejected',
                reviewer_comment=comment
            )
            
            messages.success(request, '活动申请已拒绝')
        else:
            messages.error(request, '无效的审核操作')
        
        return redirect('clubs:staff_audit_center', 'activity_application')
    
    context = {
        'activity': activity,
        'club': activity.club,
    }
    return render(request, 'clubs/staff/review_activity_application.html', context)


@login_required(login_url=settings.LOGIN_URL)
@require_http_methods(["GET", "POST"])
def review_president_transition(request, transition_id):
    """审核社长换届申请 - 干事和管理员可用"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以审核社长换届申请')
        return redirect('clubs:index')
    
    transition = get_object_or_404(PresidentTransition, pk=transition_id)
    
    if request.method == 'POST':
        status = request.POST.get('review_status', '')
        comment = request.POST.get('review_comment', '').strip()
        
        if status not in ['approved', 'rejected']:
            messages.error(request, '无效的审核状态')
            return redirect('clubs:staff_dashboard')
        
        transition.status = status
        transition.reviewer = request.user
        transition.reviewer_comment = comment
        transition.reviewed_at = timezone.now()
        transition.save()
        
        # 如果批准，更新社长信息
        if status == 'approved':
            # 更新现任社长为不在任状态
            old_officer = Officer.objects.filter(
                club=transition.club,
                position='president',
                is_current=True
            ).first()
            if old_officer:
                old_officer.is_current = False
                old_officer.end_date = timezone.now().date()
                old_officer.save()
            
            # 新社长Officer已存在，直接设置其为现任
            try:
                new_officer = transition.new_president_officer
                new_officer.is_current = True
                new_officer.appointed_date = transition.transition_date
                new_officer.save()
                
                # 更新社团社长字段
                if new_officer.user_profile and new_officer.user_profile.user:
                    transition.club.president = new_officer.user_profile.user
                    transition.club.save()
            except Exception as e:
                messages.warning(request, f'社长换届已批准，但更新社长信息时出错: {str(e)}')
        
        messages.success(request, f'社长换届申请已{'批准' if status == 'approved' else '拒绝'}')
        return redirect('clubs:staff_dashboard')
    
    # 构建材料列表给组件使用
    transition_materials = get_dynamic_materials_list(transition, 'president_transition')
    
    context = {
        'transition': transition,
        'club': transition.club,
        'transition_materials': transition_materials,
        'materials': transition_materials,
        'zip_url': reverse('clubs:zip_president_transition_docs', args=[transition.id]) if transition_materials else None,
    }
    return render(request, 'clubs/staff/review_president_transition.html', context)


@login_required(login_url=settings.LOGIN_URL)
def staff_review_history(request, review_type):
    """干事审核历史记录"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以访问此页面')
        return redirect('clubs:staff_dashboard')
    
    context = {'review_type': review_type}
    
    if review_type == 'submission':
        # 年审材料审核历史
        submissions = ReviewSubmission.objects.exclude(status='pending').order_by('-reviewed_at')
        context['title'] = '年审材料审核历史'
        context['items'] = submissions
        context['item_type'] = 'submission'
        
    elif review_type == 'club_registration':
        # 社团注册审核历史
        registrations = ClubRegistration.objects.exclude(status='pending').order_by('-reviewed_at')
        context['title'] = '社团注册审核历史'
        context['items'] = registrations
        context['item_type'] = 'club_registration'
        
        
    elif review_type == 'reimbursement':
        # 报销申请审核历史
        reimbursements = Reimbursement.objects.exclude(status='pending').order_by('-reviewed_at')
        context['title'] = '报销申请审核历史'
        context['items'] = reimbursements
        context['item_type'] = 'reimbursement'
        
    elif review_type == 'club_application':
        # 新社团申请审核历史
        applications = ClubRegistrationRequest.objects.exclude(status='pending').order_by('-reviewed_at')
        context['title'] = '新社团申请审核历史'
        context['items'] = applications
        context['item_type'] = 'club_application'
        
    elif review_type == 'activity_application':
        # 活动申请审核历史
        activities = ActivityApplication.objects.exclude(status='pending').order_by('-reviewed_at')
        context['title'] = '活动申请审核历史'
        context['items'] = activities
        context['item_type'] = 'activity_application'
        
    elif review_type == 'president_transition':
        # 社长换届申请审核历史
        transitions = PresidentTransition.objects.exclude(status='pending').order_by('-reviewed_at')
        context['title'] = '社长换届申请审核历史'
        context['items'] = transitions
        context['item_type'] = 'president_transition'
        
    else:
        messages.error(request, '无效的审核类型')
        return redirect('clubs:staff_dashboard')
    
    # staff_review_history view removed as it's replaced by modal
    # return render(request, 'clubs/staff/review_history.html', context)


@login_required(login_url=settings.LOGIN_URL)
def staff_review_detail(request, item_type, item_id):
    """干事查看审核详情 - 显示完整的审核信息和历史"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以访问此页面')
        return redirect('clubs:staff_dashboard')
    
    context = {}
    item = None
    
    if item_type == 'annual_review':
        item = get_object_or_404(ReviewSubmission, pk=item_id)
        context['title'] = f'{item.club.name} - 年审记录'
        context['item'] = item
        context['reviews'] = SubmissionReview.objects.filter(submission=item).order_by('-reviewed_at')
        
    elif item_type == 'registration':
        item = get_object_or_404(ClubRegistration, pk=item_id)
        context['title'] = f'{item.club.name} - 社团注册'
        context['item'] = item
        context['reviews'] = ClubRegistrationReview.objects.filter(registration=item).order_by('-reviewed_at')
        
    elif item_type == 'application':
        # 新社团申请 - ClubRegistrationRequest
        item = get_object_or_404(ClubRegistrationRequest, pk=item_id)
        context['title'] = f'{item.club_name} - 新社团申请'
        context['item'] = item
        # 使用 ClubApplicationReview 存储的审核记录
        context['reviews'] = ClubApplicationReview.objects.filter(application=item).order_by('-reviewed_at')
        
        
    elif item_type == 'reimbursement':
        item = get_object_or_404(Reimbursement, pk=item_id)
        context['title'] = f'{item.club.name} - 报销申请'
        context['item'] = item
        # 报销只有一条审核记录，直接从对象字段获取
        from types import SimpleNamespace
        reviews = []
        if item.reviewer or item.reviewed_at:
            status = 'approved' if item.status == 'approved' else 'rejected' if item.status == 'rejected' else 'pending'
            reviews.append(SimpleNamespace(reviewer=item.reviewer, status=status, comment=item.reviewer_comment, reviewed_at=item.reviewed_at))
        context['reviews'] = reviews
        
    elif item_type == 'activity_application':
        item = get_object_or_404(ActivityApplication, pk=item_id)
        context['title'] = f'{item.club.name} - 活动申请'
        context['item'] = item
        # 使用 ActivityApplicationHistory 获取审核历史
        context['reviews'] = ActivityApplicationHistory.objects.filter(activity_application=item).order_by('-attempt_number')
        
    elif item_type == 'president_transition':
        item = get_object_or_404(PresidentTransition, pk=item_id)
        context['title'] = f'{item.club.name} - 社长换届'
        context['item'] = item
        
        # 换届只有一条审核记录，直接从对象字段获取
        from types import SimpleNamespace
        reviews = []
        if item.reviewer or item.reviewed_at:
            status = 'approved' if item.status == 'approved' else 'rejected' if item.status == 'rejected' else 'pending'
            reviews.append(SimpleNamespace(reviewer=item.reviewer, status=status, comment=item.reviewer_comment, reviewed_at=item.reviewed_at))
        context['reviews'] = reviews
    
    else:
        messages.error(request, '无效的项目类型')
        return redirect('clubs:staff_dashboard')
    
    # 获取动态材料列表
    req_type_map = {
        'annual_review': 'annual_review',
        'registration': 'club_registration',
        'application': 'club_application',

        'reimbursement': 'reimbursement',
        'activity_application': 'activity_application',
        'president_transition': 'president_transition'
    }
    
    if item and item_type in req_type_map:
        context['materials_list'] = get_dynamic_materials_list(item, req_type_map[item_type])

    context['item_type'] = item_type
    return render(request, 'clubs/staff/review_detail.html', context)


@login_required
def public_activities(request):
    """
    活动列表页面 - 干事、管理员和社长可见
    社长只能看到本社团的活动，干事和管理员可以看到所有社团的活动
    支持筛选和搜索功能
    """
    # 权限检查：干事、管理员和社长可以访问
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    if user_role not in ['staff', 'admin', 'president']:
        messages.error(request, '您没有权限访问此页面。')
        return redirect('clubs:user_dashboard')
    
    # 获取筛选和搜索参数
    club_filter = request.GET.get('club', '')
    activity_type_filter = request.GET.get('activity_type', '')
    date_filter = request.GET.get('date', '')
    search_query = request.GET.get('search', '')
    
    # 获取所有已批准且未过期的活动
    from datetime import datetime, time
    current_datetime = timezone.now()
    
    approved_activities = ActivityApplication.objects.filter(
        status='approved'
    ).exclude(
        # 排除已过期的活动（活动日期小于今天，或活动日期是今天但结束时间已过）
        Q(activity_date__lt=current_datetime.date()) |
        Q(activity_date=current_datetime.date(), activity_time_end__lt=current_datetime.time())
    ).select_related('club')  # 优化查询，预加载社团信息
    
    # 根据用户角色过滤活动
    if user_role == 'president':
        # 社长只能看到自己社团的活动
        user_clubs = Officer.objects.filter(user_profile=request.user.profile, position='president').values_list('club', flat=True)
        if user_clubs:
            approved_activities = approved_activities.filter(club__in=user_clubs)
        else:
            # 如果找不到社长职位，显示空列表
            approved_activities = approved_activities.none()
    
    # 应用筛选条件
    if club_filter:
        approved_activities = approved_activities.filter(club__name__icontains=club_filter)
    
    if activity_type_filter:
        approved_activities = approved_activities.filter(activity_type=activity_type_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            approved_activities = approved_activities.filter(activity_date=filter_date)
        except ValueError:
            pass  # 忽略无效的日期格式
    
    # 应用搜索条件
    if search_query:
        approved_activities = approved_activities.filter(
            Q(club__name__icontains=search_query) |
            Q(activity_name__icontains=search_query)
        )
    
    approved_activities = approved_activities.order_by('activity_date', 'activity_time_start')
    
    # 分类活动
    activities_by_type = {}
    for activity in approved_activities:
        activity_type = activity.get_activity_type_display()
        if activity_type not in activities_by_type:
            activities_by_type[activity_type] = []
        activities_by_type[activity_type].append(activity)
    
    # 获取筛选选项数据
    if user_role == 'president':
        # 社长只能看到自己负责的社团
        user_club_ids = Officer.objects.filter(user_profile=request.user.profile, position='president').values_list('club', flat=True)
        if user_club_ids:
            all_clubs = Club.objects.filter(id__in=user_club_ids)
        else:
            all_clubs = Club.objects.none()
    else:
        # 干事和管理员可以看到所有社团
        all_clubs = Club.objects.filter(activity_applications__status='approved').distinct().order_by('name')
    
    activity_type_choices = ActivityApplication.ACTIVITY_TYPE_CHOICES
    
    context = {
        'approved_activities': approved_activities,
        'activities_by_type': activities_by_type,
        'all_clubs': all_clubs,
        'activity_type_choices': activity_type_choices,
        # 传递筛选参数用于表单回填
        'club_filter': club_filter,
        'activity_type_filter': activity_type_filter,
        'date_filter': date_filter,
        'search_query': search_query,
    }
    return render(request, 'clubs/public_activities.html', context)






@login_required
def edit_activity_application(request, activity_id):
    """
    编辑活动申请 - 干事、管理员和负责老师可用
    """
    activity = get_object_or_404(ActivityApplication, pk=activity_id)
    
    # 权限检查
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    # 检查用户权限
    has_permission = False
    if user_role in ['admin', 'staff']:
        has_permission = True
    
    if not has_permission:
        messages.error(request, '您没有权限编辑此活动')
        return redirect('clubs:public_activities')
    
    if request.method == 'POST':
        # 获取表单数据
        activity_name = request.POST.get('activity_name', '').strip()
        activity_type = request.POST.get('activity_type', '').strip()
        activity_description = request.POST.get('activity_description', '').strip()
        activity_date = request.POST.get('activity_date', '').strip()
        activity_time_start = request.POST.get('activity_time_start', '').strip()
        activity_time_end = request.POST.get('activity_time_end', '').strip()
        activity_location = request.POST.get('activity_location', '').strip()
        expected_participants = request.POST.get('expected_participants', '').strip()
        budget = request.POST.get('budget', '').strip() or '0'
        contact_person = request.POST.get('contact_person', '').strip()
        contact_phone = request.POST.get('contact_phone', '').strip()
        
        errors = []
        
        # 基本验证
        if not activity_name:
            errors.append('活动名称不能为空')
        if not activity_type:
            errors.append('活动类型不能为空')
        if not activity_description:
            errors.append('活动描述不能为空')
        if not activity_date:
            errors.append('活动日期不能为空')
        if not activity_time_start:
            errors.append('活动开始时间不能为空')
        if not activity_time_end:
            errors.append('活动结束时间不能为空')
        if not activity_location:
            errors.append('活动地点不能为空')
        if not contact_person:
            errors.append('联系人不能为空')
        
        # 验证参与人数
        try:
            expected_participants = int(expected_participants) if expected_participants else 0
            if expected_participants < 0:
                errors.append('预计参与人数不能为负数')
        except ValueError:
            errors.append('预计参与人数必须是整数')
        
        # 验证预算
        try:
            budget = float(budget) if budget else 0
            if budget < 0:
                errors.append('活动预算不能为负数')
        except ValueError:
            errors.append('活动预算必须是数字')
        
        if errors:
            context = {
                'activity': activity,
                'errors': errors,
                'activity_name': activity_name,
                'activity_type': activity_type,
                'activity_description': activity_description,
                'activity_date': activity_date,
                'activity_time_start': activity_time_start,
                'activity_time_end': activity_time_end,
                'activity_location': activity_location,
                'expected_participants': expected_participants,
                'budget': budget,
                'contact_person': contact_person,
                'contact_phone': contact_phone,
            }
            return render(request, 'clubs/edit_activity_application.html', context)
        
        # 更新活动信息
        try:
            activity.activity_name = activity_name
            activity.activity_type = activity_type
            activity.activity_description = activity_description
            activity.activity_date = activity_date
            activity.activity_time_start = activity_time_start
            activity.activity_time_end = activity_time_end
            activity.activity_location = activity_location
            activity.expected_participants = expected_participants
            activity.budget = budget
            activity.contact_person = contact_person
            activity.contact_phone = contact_phone or '无'
            activity.save()
            
            messages.success(request, '活动信息已更新')
            return redirect('clubs:public_activities')
        except Exception as e:
            messages.error(request, f'更新失败: {str(e)}')
            return redirect('clubs:edit_activity_application', activity_id=activity_id)
    
    # GET请求 - 显示编辑表单
    context = {
        'activity': activity,
    }
    return render(request, 'clubs/edit_activity_application.html', context)


@login_required(login_url=settings.LOGIN_URL)
def staff_audit_center(request, tab='annual-review'):
    """干事/管理员审核中心 - 类似社长审批中心的界面"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以访问审核中心')
        return redirect('clubs:index')
    
    # 将连字符转换为下划线以兼容内部处理
    tab_internal = tab.replace('-', '_')
    
    # 根据选项卡类型获取数据
    pending_items = []
    reviewing_items = []
    completed_items = []
    
    if tab_internal == 'annual_review':
        all_items = ReviewSubmission.objects.all().order_by('-submitted_at')
        pending_items_queryset = all_items.filter(status='pending')
        completed_items = all_items.exclude(status='pending')
        
        # 分离待审核和审核中的项目
        for item in pending_items_queryset:
            # 检查当前用户是否已审核过
            user_reviewed = SubmissionReview.objects.filter(submission=item, reviewer=request.user).exists()
            item.user_reviewed = user_reviewed
            
            # 检查是否有其他人审核过（审核中状态）
            total_reviews = SubmissionReview.objects.filter(submission=item).count()
            if total_reviews > 0:
                item.review_count = total_reviews
                reviewing_items.append(item)
            else:
                pending_items.append(item)
        
    elif tab_internal == 'registration':
        all_items = ClubRegistration.objects.all().order_by('-submitted_at')
        pending_items_queryset = all_items.filter(status='pending')
        completed_items = all_items.exclude(status='pending')
        
        # 分离待审核和审核中的项目
        for item in pending_items_queryset:
            # 检查当前用户是否已审核过
            user_reviewed = ClubRegistrationReview.objects.filter(registration=item, reviewer=request.user).exists()
            item.user_reviewed = user_reviewed
            
            # 检查是否有其他人审核过（审核中状态）
            total_reviews = ClubRegistrationReview.objects.filter(registration=item).count()
            if total_reviews > 0:
                item.review_count = total_reviews
                reviewing_items.append(item)
            else:
                pending_items.append(item)
        
    elif tab_internal == 'application':
        all_items = ClubRegistrationRequest.objects.all().order_by('-submitted_at')
        pending_items_queryset = all_items.filter(status='pending')
        completed_items = all_items.exclude(status='pending')
        
        # 分离待审核和审核中的项目
        for item in pending_items_queryset:
            # 检查当前用户是否已审核过
            user_reviewed = ClubApplicationReview.objects.filter(application=item, reviewer=request.user).exists()
            item.user_reviewed = user_reviewed
            
            # 检查是否有其他人审核过（审核中状态）
            total_reviews = ClubApplicationReview.objects.filter(application=item).count()
            if total_reviews > 0:
                item.review_count = total_reviews
                reviewing_items.append(item)
            else:
                pending_items.append(item)
        
        
    elif tab_internal == 'reimbursement':
        all_items = Reimbursement.objects.all().order_by('-submitted_at')
        pending_items = all_items.filter(status='pending')
        completed_items = all_items.exclude(status='pending')
        
    elif tab_internal == 'activity_application':
        all_items = ActivityApplication.objects.all().order_by('-submitted_at')
        pending_items = all_items.filter(status='pending')
        completed_items = all_items.exclude(status='pending')
        
    elif tab_internal == 'president_transition':
        all_items = PresidentTransition.objects.all().order_by('-submitted_at')
        pending_items = all_items.filter(status='pending')
        completed_items = all_items.exclude(status='pending')
    
    context = {
        'current_tab': tab_internal,
        'pending_items': pending_items,
        'reviewing_items': reviewing_items if tab_internal in ['annual_review', 'registration', 'application'] else [],
        'active_items': list(pending_items) + list(reviewing_items) if tab_internal in ['annual_review', 'registration', 'application'] else pending_items,
        'completed_items': completed_items,
    }
    
    return render(request, 'clubs/staff/audit_center.html', context)

@login_required(login_url=settings.LOGIN_URL)
def staff_audit_center_mobile(request):
    """干事/管理员审核中心移动版 - 卡片网格UI用于手机端"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以访问审核中心')
        return redirect('clubs:index')
    
    # 获取所有审核类型的数据
    audit_items = {
        'annual_review': ReviewSubmission.objects.all().order_by('-submitted_at'),
        'registration': ClubRegistration.objects.all().order_by('-submitted_at'),
        'application': ClubRegistrationRequest.objects.all().order_by('-submitted_at'),
        'reimbursement': Reimbursement.objects.all().order_by('-submitted_at'),
        'activity_application': ActivityApplication.objects.all().order_by('-submitted_at'),
        'president_transition': PresidentTransition.objects.all().order_by('-submitted_at'),
    }
    
    # 计算未审核数量
    pending_counts = {
        'annual_review': ReviewSubmission.objects.filter(status='pending').count(),
        'registration': ClubRegistration.objects.filter(status='pending').count(),
        'application': ClubRegistrationRequest.objects.filter(status='pending').count(),
        'reimbursement': Reimbursement.objects.filter(status='pending').count(),
        'activity_application': ActivityApplication.objects.filter(staff_approved__isnull=True).count(),
        'president_transition': PresidentTransition.objects.filter(status='pending').count(),
    }
    
    context = {
        'audit_items': audit_items,
        'pending_counts': pending_counts,
    }
    
    return render(request, 'clubs/staff/audit_center_mobile.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def edit_department_introduction(request):
    """编辑部门介绍页面 - 仅管理员可访问"""
    # 检查权限 - 仅管理员可编辑
    if not _is_admin(request.user) and not request.user.is_superuser:
        messages.error(request, '您没有权限编辑部门介绍')
        return redirect('clubs:index')
    
    # 获取所有部门
    departments = DepartmentIntroduction.objects.all().order_by('department')
    
    if request.method == 'POST':
        # 处理表单提交 - 更新每个部门的介绍
        try:
            for dept in departments:
                # 获取表单数据
                dept_key = f"dept_{dept.id}"
                description = request.POST.get(f"{dept_key}_description", "").strip()
                highlights = request.POST.get(f"{dept_key}_highlights", "").strip()
                icon = request.POST.get(f"{dept_key}_icon", dept.icon).strip()
                
                # 更新部门信息
                if description:  # 只有在有描述时才更新
                    dept.description = description
                    dept.highlights = highlights
                    dept.icon = icon
                    dept.updated_by = request.user
                    dept.save()
                    messages.success(request, f'已更新{dept.get_department_display()}部门信息')
            
            messages.success(request, '所有部门介绍已成功更新')
            return redirect('clubs:index')
        except Exception as e:
            messages.error(request, f'更新部门介绍时出错: {str(e)}')
    
    context = {
        'departments': departments,
        'material_icons': [
            'work', 'assessment', 'event', 'people', 'speaker',
            'star', 'explore', 'check', 'info', 'favorite',
            'school', 'business', 'settings', 'security', 'trending_up'
        ]
    }
    return render(request, 'clubs/edit_department_introduction.html', context)


# ==================== 材料要求管理视图 ====================

@login_required
def manage_material_requirements(request):
    """管理材料上传要求"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    requirements = MaterialRequirement.objects.all().order_by('request_type', 'order')
    
    # 按请求类型分组
    grouped_requirements = {}
    
    # 初始化所有类型的分组
    for code, name in MaterialRequirement.REQUEST_TYPE_CHOICES:
        grouped_requirements[code] = {
            'name': name,
            'items': []
        }
        
    for req in requirements:
        if req.request_type in grouped_requirements:
            grouped_requirements[req.request_type]['items'].append(req)
            
    context = {
        'grouped_requirements': grouped_requirements,
    }
    return render(request, 'clubs/admin/material_requirements_list.html', context)


@login_required
def add_material_requirement(request):
    """添加材料要求"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    if request.method == 'POST':
        try:
            request_type = request.POST.get('request_type')
            name = request.POST.get('name')
            icon = request.POST.get('icon', 'cloud_upload')
            description = request.POST.get('description', '')
            is_required = request.POST.get('is_required') == 'on'
            allowed_extensions = request.POST.get('allowed_extensions')
            max_size_mb = int(request.POST.get('max_size_mb', 10))
            order = int(request.POST.get('order', 0))
            is_active = request.POST.get('is_active') == 'on'
            template_file = request.FILES.get('template_file')
            
            MaterialRequirement.objects.create(
                request_type=request_type,
                name=name,
                icon=icon,
                description=description,
                is_required=is_required,
                allowed_extensions=allowed_extensions,
                max_size_mb=max_size_mb,
                order=order,
                is_active=is_active,
                template_file=template_file
            )
            messages.success(request, '添加成功')
            return redirect('clubs:manage_material_requirements')
        except Exception as e:
            messages.error(request, f'添加失败: {str(e)}')
            
    context = {
        'request_type_choices': MaterialRequirement.REQUEST_TYPE_CHOICES,
    }
    return render(request, 'clubs/admin/material_requirement_form.html', context)


@login_required
def edit_material_requirement(request, req_id):
    """编辑材料要求"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    req = get_object_or_404(MaterialRequirement, pk=req_id)
    
    if request.method == 'POST':
        try:
            req.request_type = request.POST.get('request_type')
            req.name = request.POST.get('name')
            req.icon = request.POST.get('icon', 'cloud_upload')
            req.description = request.POST.get('description', '')
            req.is_required = request.POST.get('is_required') == 'on'
            req.allowed_extensions = request.POST.get('allowed_extensions')
            req.max_size_mb = int(request.POST.get('max_size_mb', 10))
            req.order = int(request.POST.get('order', 0))
            req.is_active = request.POST.get('is_active') == 'on'
            
            if 'template_file' in request.FILES:
                req.template_file = request.FILES['template_file']
            elif request.POST.get('clear_template') == 'on':
                req.template_file = None
                
            req.save()
            
            messages.success(request, '修改成功')
            return redirect('clubs:manage_material_requirements')
        except Exception as e:
            messages.error(request, f'修改失败: {str(e)}')
            
    context = {
        'requirement': req,
        'request_type_choices': MaterialRequirement.REQUEST_TYPE_CHOICES,
    }
    return render(request, 'clubs/admin/material_requirement_form.html', context)


@login_required
def delete_material_requirement(request, req_id):
    """删除材料要求"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    req = get_object_or_404(MaterialRequirement, pk=req_id)
    
    if request.method == 'POST':
        req.delete()
        messages.success(request, '删除成功')
        
    return redirect('clubs:manage_material_requirements')


@login_required
def manage_departments(request):
    """管理部门"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    departments = Department.objects.all()
    return render(request, 'clubs/admin/manage_departments.html', {'departments': departments})


@login_required
def add_department(request):
    """添加部门"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        highlights = request.POST.get('highlights')
        icon = request.POST.get('icon', 'work')
        order = request.POST.get('order', 0)
        
        try:
            Department.objects.create(
                name=name,
                description=description,
                highlights=highlights,
                icon=icon,
                order=int(order)
            )
            messages.success(request, '部门添加成功')
            return redirect('clubs:manage_departments')
        except Exception as e:
            messages.error(request, f'添加失败: {str(e)}')
            
    return render(request, 'clubs/admin/department_form.html', {'title': '添加部门'})


@login_required
def get_clubs_list(request):
    """获取社团列表API"""
    if not is_staff_or_admin(request.user):
        return HttpResponseForbidden()
        
    clubs = Club.objects.filter(status='active').values('id', 'name')
    return JsonResponse({'clubs': list(clubs)})


@login_required
def zip_activity_application_docs(request, application_id):
    """打包下载活动申请文件"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    application = get_object_or_404(ActivityApplication, pk=application_id)
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 获取所有提交的文件
        files = SubmittedFile.objects.filter(
            content_type=ContentType.objects.get_for_model(ActivityApplication),
            object_id=application.id
        )
        
        if not files.exists():
            messages.warning(request, '没有可下载的文件')
            return redirect('clubs:review_activity_application', activity_id=application.id)
            
        # 复制文件到临时目录
        for f in files:
            if f.file:
                try:
                    src_path = f.file.path
                    if os.path.exists(src_path):
                        # 使用 requirement 名称作为文件名
                        req_name = f.requirement.name if f.requirement else 'unknown'
                        file_ext = os.path.splitext(f.file.name)[1]
                        dst_name = f"{req_name}{file_ext}"
                        shutil.copy2(src_path, os.path.join(temp_dir, dst_name))
                except Exception as e:
                    print(f"Error copying file: {e}")
                    
        # 创建zip文件
        zip_filename = f"{application.club.name}-活动申请-{application.name}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
        
        shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', temp_dir)
        
        # 发送文件
        response = FileResponse(open(zip_path, 'rb'), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{urllib.parse.quote(zip_filename)}"'
    return response


@login_required
def room_calendar(request):
    """
    显示房间预约日历
    """
    # 获取参数
    room_id = request.GET.get('room_id')
    date_str = request.GET.get('date')
    
    # 获取当前查看的日期
    if date_str:
        try:
            view_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            view_date = timezone.now().date()
    else:
        view_date = timezone.now().date()
        
    # 获取所有可用房间
    rooms = Room.objects.filter(status='available')
    if not rooms.exists():
        messages.error(request, '暂时没有可用的房间')
        return redirect('clubs:index')
        
    # 确定当前选中的房间
    if room_id:
        selected_room = get_object_or_404(Room, pk=room_id)
    else:
        selected_room = rooms.first()
        
    # 计算日期导航
    is_today = (view_date == timezone.now().date())
    prev_date = view_date - timezone.timedelta(days=1)
    next_date = view_date + timezone.timedelta(days=1)
    week_start = view_date - timezone.timedelta(days=view_date.weekday())
    
    # 获取时间段
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    # 计算整个日历的起止时间（用于计算百分比）
    # 默认 8:00 (480min) 到 22:00 (1320min)，总长 840min
    day_start_minutes = 8 * 60
    day_end_minutes = 22 * 60
    
    if time_slots.exists():
        first_slot = time_slots.first()
        last_slot = time_slots.last()
        day_start_minutes = min(day_start_minutes, first_slot.start_time.hour * 60 + first_slot.start_time.minute)
        day_end_minutes = max(day_end_minutes, last_slot.end_time.hour * 60 + last_slot.end_time.minute)
    
    total_minutes = day_end_minutes - day_start_minutes
    if total_minutes <= 0:
        total_minutes = 14 * 60
        
    processed_slots = []
    for slot in time_slots:
        slot_start_min = slot.start_time.hour * 60 + slot.start_time.minute
        slot_end_min = slot.end_time.hour * 60 + slot.end_time.minute
        
        # 使用浮点数计算百分比，保留4位小数以确保精度
        top_percent = ((slot_start_min - day_start_minutes) / total_minutes) * 100
        height_percent = ((slot_end_min - slot_start_min) / total_minutes) * 100
        
        # 检查该时间段是否已有预约
        has_booking = RoomBooking.objects.filter(
            room=selected_room,
            booking_date=view_date,
            status='active',
            start_time__lt=slot.end_time,
            end_time__gt=slot.start_time
        ).exists()
        
        processed_slots.append({
            'start': slot.start_time,
            'end': slot.end_time,
            'label': slot.label,
            'top_percent': f"{top_percent:.4f}",  # 格式化为字符串，避免本地化问题
            'height_percent': f"{height_percent:.4f}", # 格式化为字符串
            'has_booking': has_booking,
            'id': slot.id
        })
        
    # 获取当天的预约
    bookings = RoomBooking.objects.filter(
        room=selected_room,
        booking_date=view_date,
        status='active'
    ).select_related('user__profile', 'club')
    
    processed_bookings = []
    for booking in bookings:
        # 权限检查
        can_edit = booking.can_edit(request.user)
        can_delete = booking.can_delete(request.user)
             
        # 计算位置
        b_start_min = booking.start_time.hour * 60 + booking.start_time.minute
        b_end_min = booking.end_time.hour * 60 + booking.end_time.minute
        
        top_percent = ((b_start_min - day_start_minutes) / total_minutes) * 100
        height_percent = ((b_end_min - b_start_min) / total_minutes) * 100
        
        processed_bookings.append({
            'booking': booking,
            'top_percent': f"{top_percent:.4f}", # 格式化为字符串
            'height_percent': f"{height_percent:.4f}", # 格式化为字符串
            'can_edit': can_edit,
            'can_delete': can_delete
        })

    context = {
        'rooms': rooms,
        'selected_room': selected_room,
        'view_date': view_date,
        'is_today': is_today,
        'prev_date': prev_date,
        'next_date': next_date,
        'week_start': week_start,
        'time_slots': processed_slots,
        'bookings': processed_bookings,
    }
    
    return render(request, 'clubs/room_calendar.html', context)



@login_required
def edit_department(request, dept_id):
    """编辑部门"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    dept = get_object_or_404(Department, pk=dept_id)
    
    if request.method == 'POST':
        dept.name = request.POST.get('name')
        dept.description = request.POST.get('description')
        dept.highlights = request.POST.get('highlights')
        dept.icon = request.POST.get('icon', 'work')
        dept.order = int(request.POST.get('order', 0))
        dept.updated_by = request.user
        dept.save()
        messages.success(request, '部门更新成功')
        return redirect('clubs:manage_departments')
        
    return render(request, 'clubs/admin/department_form.html', {
        'title': '编辑部门',
        'department': dept
    })


@login_required
def delete_department(request, dept_id):
    """删除部门"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '您没有权限执行此操作')
        return redirect('clubs:index')
        
    dept = get_object_or_404(Department, pk=dept_id)
    if request.method == 'POST':
        dept.delete()
        messages.success(request, '部门删除成功')
        
    return redirect('clubs:manage_departments')


@login_required
@login_required
@require_http_methods(["GET", "POST"])
def submit_room_booking(request):
    """提交房间预约"""
    if request.method == 'GET':
        # 获取预填参数
        room_id = request.GET.get('room_id')
        date_str = request.GET.get('date')
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        
        # 获取基础数据
        rooms = Room.objects.filter(status='available')
        
        # 获取用户关联的社团（作为社长）
        user_clubs = []
        if hasattr(request.user, 'profile'):
            # 获取用户作为社长的社团
            # 注意：这里假设Officer模型维护了社长关系，或者Club模型有president字段
            # 根据之前的代码，Club模型有president字段
            user_clubs = Club.objects.filter(president=request.user, status='active')
            
        today = timezone.now().date().strftime('%Y-%m-%d')
        
        context = {
            'rooms': rooms,
            'user_clubs': user_clubs,
            'today': today,
            'selected_room_id': int(room_id) if room_id and room_id.isdigit() else None,
            'selected_date': date_str,
            'selected_start_time': start_time,
            'selected_end_time': end_time,
            'is_staff_or_admin': is_staff_or_admin(request.user)
        }
        return render(request, 'clubs/submit_room_booking.html', context)

    # POST 请求处理
    try:
        room_id = request.POST.get('room_id')
        date_str = request.POST.get('booking_date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        club_id = request.POST.get('club_id')
        purpose = request.POST.get('purpose')
        contact_phone = request.POST.get('contact_phone')
        special_requirements = request.POST.get('special_requirements')
        participant_count = request.POST.get('participant_count')
        
        if not all([room_id, date_str, start_time_str, end_time_str, purpose, contact_phone, participant_count]):
            messages.error(request, '请填写所有必填项')
            return redirect('clubs:submit_room_booking')

        room = get_object_or_404(Room, pk=room_id)
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 解析时间
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        # 验证时间顺序
        if start_time >= end_time:
            messages.error(request, '结束时间必须晚于开始时间')
            return redirect('clubs:submit_room_booking')

        # 验证是否为有效的固定时间段
        is_valid_slot = TimeSlot.objects.filter(
            start_time=start_time,
            end_time=end_time,
            is_active=True
        ).exists()
        
        if not is_valid_slot:
            messages.error(request, '请选择有效的固定时间段')
            return redirect('clubs:room_calendar')

        # 确定社团
        club = None
        if club_id:
            club = get_object_or_404(Club, pk=club_id)
            # 验证用户是否有权代表该社团申请（如果是社长）
            if not is_staff_or_admin(request.user):
                if club.president != request.user:
                    messages.error(request, '您不是该社团的社长，无法代表申请')
                    return redirect('clubs:submit_room_booking')
        else:
            # 个人申请，必须是干事或管理员
            if not is_staff_or_admin(request.user):
                messages.error(request, '普通用户必须选择社团进行申请')
                return redirect('clubs:submit_room_booking')
        
        # 检查冲突
        existing_booking = RoomBooking.objects.filter(
            room=room,
            booking_date=booking_date,
            status='active'
        ).filter(
            Q(start_time__lt=end_time) & 
            Q(end_time__gt=start_time)
        ).exists()
        
        if existing_booking:
            messages.error(request, '该时间段已被预约，请选择其他时间')
            # 返回并带上参数以便重填，这里简单处理直接跳回日历
            return redirect('clubs:room_calendar')

        # 创建预约
        RoomBooking.objects.create(
            room=room,
            user=request.user,
            club=club,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            purpose=purpose,
            contact_phone=contact_phone,
            special_requirements=special_requirements,
            participant_count=int(participant_count),
            status='active'
        )
        messages.success(request, '预约提交成功')
    except Exception as e:
        messages.error(request, f'预约失败: {str(e)}')
        # 发生错误时，最好能保留用户输入，但这里简化处理
        return redirect('clubs:room_calendar')
            
    return redirect('clubs:room_calendar')


@login_required
def my_room_bookings(request):
    """我的预约"""
    bookings = RoomBooking.objects.filter(user=request.user).order_by('-booking_date', '-start_time')
    return render(request, 'clubs/room_my_bookings.html', {'bookings': bookings})


@login_required
def edit_room_booking(request, booking_id):
    """编辑预约"""
    booking = get_object_or_404(RoomBooking, pk=booking_id)
    if not booking.can_edit(request.user):
        messages.error(request, '您没有权限编辑此预约')
        return redirect('clubs:my_room_bookings')
        
    if request.method == 'POST':
        # 简单实现，实际可能需要更多逻辑
        booking.reason = request.POST.get('reason')
        booking.save()
        messages.success(request, '预约已更新')
        return redirect('clubs:my_room_bookings')
        
    return render(request, 'clubs/room_my_bookings.html', {'booking': booking})


@login_required
def delete_room_booking(request, booking_id):
    """取消预约"""
    booking = get_object_or_404(RoomBooking, pk=booking_id)
    if not booking.can_delete(request.user):
        messages.error(request, '您没有权限取消此预约')
    else:
        booking.delete()
        messages.success(request, '预约已取消')
    return redirect('clubs:my_room_bookings')


@login_required
def admin_room_list(request):
    """管理员-房间列表"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    rooms = Room.objects.all()
    return render(request, 'clubs/admin/room_list.html', {'rooms': rooms})


@login_required
def admin_room_add(request):
    """管理员-添加房间"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    if request.method == 'POST':
        Room.objects.create(
            name=request.POST.get('name'),
            capacity=request.POST.get('capacity'),
            location=request.POST.get('location'),
            description=request.POST.get('description'),
            status=request.POST.get('status')
        )
        return redirect('clubs:admin_room_list')
    return render(request, 'clubs/admin/room_form.html')


@login_required
def admin_room_edit(request, room_id):
    """管理员-编辑房间"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        room.name = request.POST.get('name')
        room.capacity = request.POST.get('capacity')
        room.location = request.POST.get('location')
        room.description = request.POST.get('description')
        room.status = request.POST.get('status')
        room.save()
        return redirect('clubs:admin_room_list')
    return render(request, 'clubs/admin/room_form.html', {'room': room})


@login_required
def admin_room_delete(request, room_id):
    """管理员-删除房间"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        room.delete()
    return redirect('clubs:admin_room_list')


@login_required
def admin_booking_management(request):
    """管理员-预约管理"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    bookings = RoomBooking.objects.all().order_by('-booking_date')
    return render(request, 'clubs/admin/booking_management.html', {'bookings': bookings})


@login_required
def admin_time_slots(request):
    """管理员-时间段管理"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    slots = TimeSlot.objects.all().order_by('start_time')
    return render(request, 'clubs/admin/time_slots.html', {'time_slots': slots})


@login_required
def admin_time_slot_add(request):
    """管理员-添加时间段"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    if request.method == 'POST':
        TimeSlot.objects.create(
            start_time=request.POST.get('start_time'),
            end_time=request.POST.get('end_time'),
            label=request.POST.get('label'),
            is_active=request.POST.get('is_active') == 'on'
        )
        return redirect('clubs:admin_time_slots')
    return render(request, 'clubs/admin/time_slot_form.html')


@login_required
def admin_time_slot_edit(request, slot_id):
    """管理员-编辑时间段"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    slot = get_object_or_404(TimeSlot, pk=slot_id)
    if request.method == 'POST':
        slot.start_time = request.POST.get('start_time')
        slot.end_time = request.POST.get('end_time')
        slot.label = request.POST.get('label')
        slot.is_active = request.POST.get('is_active') == 'on'
        slot.save()
        return redirect('clubs:admin_time_slots')
    return render(request, 'clubs/admin/time_slot_form.html', {'slot': slot})


@login_required
def admin_time_slot_delete(request, slot_id):
    """管理员-删除时间段"""
    if not is_staff_or_admin(request.user):
        return redirect('clubs:index')
    slot = get_object_or_404(TimeSlot, pk=slot_id)
    if request.method == 'POST':
        slot.delete()
    return redirect('clubs:admin_time_slots')


@login_required(login_url=settings.LOGIN_URL)
def manage_favicon(request):
    """管理网站图标"""
    if not is_staff_or_admin(request.user):
        messages.error(request, '权限不足')
        return redirect('clubs:index')
        
    if request.method == 'POST':
        if 'favicon' in request.FILES:
            upload = request.FILES['favicon']
            ext = os.path.splitext(upload.name)[1].lower()
            if ext not in ['.ico', '.png', '.jpg', '.jpeg']:
                messages.error(request, '仅支持 .ico, .png, .jpg 格式')
                return redirect('clubs:manage_favicon')
            site_dir = os.path.join(settings.MEDIA_ROOT, 'site')
            os.makedirs(site_dir, exist_ok=True)
            file_path = os.path.join(site_dir, 'favicon.ico')
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    messages.error(request, f'删除旧图标失败: {str(e)}')
            try:
                img = Image.open(upload)
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA')
                w, h = img.size
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                img = img.crop((left, top, left + side, top + side))
                preview_path = os.path.join(site_dir, 'favicon.png')
                preview_img = img.resize((128, 128), Image.LANCZOS)
                preview_img.save(preview_path, format='PNG')
                img.save(file_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
                messages.success(request, '网站图标已更新')
            except Exception as e:
                messages.error(request, f'保存图标失败: {str(e)}')
            return redirect('clubs:manage_favicon')
            
    return render(request, 'clubs/admin/manage_favicon.html')


@login_required(login_url='clubs:login')
def get_department_members(request, department_id):
    """API: 获取部门成员列表"""
    try:
        department = Department.objects.get(id=department_id)
    except Department.DoesNotExist:
        return JsonResponse({'error': '部门不存在'}, status=404)
        
    members = UserProfile.objects.filter(
        role='staff',
        department_link=department
    ).select_related('user').order_by('staff_level', 'user__username')
    
    directors_data = []
    members_data = []
    
    for member in members:
        avatar_url = member.avatar.url if member.avatar else None
        item = {
            'id': member.user.id,
            'name': member.get_full_name(),
            'avatar': avatar_url,
            'initial': member.get_full_name()[0].upper() if member.get_full_name() else member.user.username[0].upper(),
        }
        if member.staff_level == 'director':
            directors_data.append(item)
        else:
            members_data.append(item)
            
    return JsonResponse({
        'name': department.name,
        'directors': directors_data,
        'members': members_data
    })


