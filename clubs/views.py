from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from django.conf import settings
from django.http import HttpResponse, FileResponse
from django.db.models import Q
import os
import urllib.parse
import os
import tempfile
from .models import Club, Officer, ReviewSubmission, UserProfile, Reimbursement, ClubRegistrationRequest, ClubRegistration, Template, Announcement, StaffClubRelation, SubmissionReview, ClubRegistrationReview, ClubInfoChangeRequest, RegistrationPeriod, PresidentTransition, ActivityApplication, Room222Booking, SMTPConfig, ActivityParticipation, TeacherClubAssignment
import shutil


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

import json

@login_required(login_url='login')
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


def index(request):
    """首页 - 显示所有社团和最新公告"""
    # 未登录用户不显示社团信息
    if not request.user.is_authenticated:
        context = {
            'is_anonymous': True,
            'message': '请先登录查看社团信息',
        }
        return render(request, 'clubs/index.html', context)
    
    clubs = Club.objects.all()
    # 获取最新的已发布公告
    announcements = Announcement.objects.filter(status='published').order_by('-published_at')[:5]
    
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
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        founded_date = request.POST.get('founded_date', '')
        members_count = request.POST.get('members_count', '').strip()
        president_profile_id = request.POST.get('president_profile_id', '')
        
        # 获取上传的文件
        establishment_application = request.FILES.get('establishment_application')
        constitution_draft = request.FILES.get('constitution_draft')
        three_year_plan = request.FILES.get('three_year_plan')
        leaders_resumes = request.FILES.get('leaders_resumes')
        one_month_activity_plan = request.FILES.get('one_month_activity_plan')
        advisor_certificates = request.FILES.get('advisor_certificates')
        
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
        
        # 验证上传的文件（必传材料）
        if not establishment_application:
            errors.append('请上传社团成立申请书')
        if not constitution_draft:
            errors.append('请上传社团章程草案')
        if not three_year_plan:
            errors.append('请上传社团三年发展规划')
        if not leaders_resumes:
            errors.append('请上传社团拟任负责人和指导老师的详细简历和身份证复印件')
        if not one_month_activity_plan:
            errors.append('请上传社团组建一个月后的活动计划')
        
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
            }
            return render(request, 'clubs/user/register_club.html', context)
        
        # 创建社团注册申请（待审核）
        ClubRegistrationRequest.objects.create(
            club_name=name,
            description=description,
            founded_date=founded_date,
            members_count=members_count,
            president_name=president_profile.real_name,
            president_id=president_profile.student_id,
            president_email=president_profile.user.email,
            requested_by=request.user,
            status='pending',
            establishment_application=establishment_application,
            constitution_draft=constitution_draft,
            three_year_plan=three_year_plan,
            leaders_resumes=leaders_resumes,
            one_month_activity_plan=one_month_activity_plan,
            advisor_certificates=advisor_certificates
        )
        
        messages.success(request, f'社团注册申请已提交，等待干事审核！')
        return redirect('clubs:user_dashboard')
    
    context = {
        'current_user_profile': current_user_profile,
        'other_presidents': other_presidents,
        'registration_templates': registration_templates,
    }
    return render(request, 'clubs/user/register_club.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def view_club_applications(request):
    """查看用户提交的社团申请记录"""
    if not _is_president(request.user):
        messages.error(request, '仅社长可以查看社团申请记录')
        return redirect('clubs:index')
    
    applications = ClubRegistrationRequest.objects.filter(requested_by=request.user).order_by('-submitted_at')

    # 将已审核的记录标记为已读
    for application in applications:
        if application.status in ['approved', 'rejected'] and not application.is_read:
            application.is_read = True
            application.save(update_fields=['is_read'])
    
    context = {
        'applications': applications,
    }
    return render(request, 'clubs/user/view_club_applications.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])



@login_required(login_url='login')
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
    
    # 获取请求类型
    request_type = request.GET.get('type', 'review')
    
    # 根据请求类型获取对应的对象和数据
    if request_type == 'club_application':
        # 处理社团申请重新提交
        application = get_object_or_404(ClubRegistrationRequest, pk=request_id, requested_by=request.user)
        
        # 只有被拒绝的申请才能重新提交
        if application.status != 'rejected':
            messages.error(request, '只有被拒绝的申请才能重新提交')
            return redirect('clubs:view_club_applications')
        
        # 检查是否已经被修改提交过（通过检查是否已有新的pending申请）
        newer_application = ClubRegistrationRequest.objects.filter(
            requested_by=request.user,
            club_name=application.club_name,
            submitted_at__gt=application.submitted_at
        ).exists()
        
        if newer_application:
            messages.error(request, '该申请已被修改提交，不允许再次修改之前的请求')
            return redirect('clubs:view_club_applications')
        
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
            'club': club
        }
        
    elif request_type == 'club_registration':
        # 处理社团注册重新提交
        registration = get_object_or_404(ClubRegistration, pk=request_id, club=club)
        
        # 只有被拒绝的申请才能重新提交
        if registration.status != 'rejected':
            messages.error(request, '只有被拒绝的申请才能重新提交')
            return redirect('clubs:view_club_registrations', club_id=club.id)
        
        # 检查是否已经被修改提交过（通过检查是否已有更新的pending申请）
        newer_registration = ClubRegistration.objects.filter(
            club=registration.club,
            registration_period=registration.registration_period,
            submitted_at__gt=registration.submitted_at
        ).exists()
        
        if newer_registration:
            messages.error(request, '该申请已被修改提交，不允许再次修改之前的请求')
            return redirect('clubs:view_club_registrations', club_id=club.id)
        
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
            'review_type': 'club_registration'
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
            return redirect('clubs:view_submissions', club_id=club.id)
        
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
            'review_type': 'review'
        }
    
    elif request_type == 'reimbursement':
        # 处理报销重新提交
        reimbursement = get_object_or_404(Reimbursement, pk=request_id, club=club)
        
        # 只有被拒绝的申请才能重新提交
        if reimbursement.status != 'rejected':
            messages.error(request, '只有被拒绝的报销申请才能重新提交')
            return redirect('clubs:view_reimbursements', club_id=club.id)
        
        # 获取可用模板
        reimbursement_templates = Template.objects.filter(template_type='reimbursement', is_active=True)
        
        context = {
            'club': club,
            'reimbursement': reimbursement,
            'templates': reimbursement_templates,
            'review_type': 'reimbursement'
        }
    
    elif request_type == 'activity_application':
        # 处理活动申请重新提交
        activity = get_object_or_404(ActivityApplication, pk=request_id, club=club)
        
        # 只有被拒绝的申请才能重新提交
        if activity.status != 'rejected':
            messages.error(request, '只有被拒绝的活动申请才能重新提交')
            return redirect('clubs:view_activity_applications', club_id=club.id)
        
        context = {
            'club': club,
            'activity': activity,
            'review_type': 'activity_application'
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
            'review_type': 'president_transition'
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
            
            # 验证上传的文件（必传材料）
            if not establishment_application:
                errors.append('请上传社团成立申请书')
            if not constitution_draft:
                errors.append('请上传社团章程草案')
            if not three_year_plan:
                errors.append('请上传社团三年发展规划')
            if not leaders_resumes:
                errors.append('请上传社团拟任负责人和指导老师的详细简历和身份证复印件')
            if not one_month_activity_plan:
                errors.append('请上传社团组建一个月后的活动计划')
            
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
            application.is_read = False
            application.resubmission_attempt += 1
            application.save()
            
            messages.success(request, f'社团申请已重新提交（第{application.resubmission_attempt}次），等待干事审核！')
            return redirect('clubs:view_club_applications')
            
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
            
            def validate_file(file, field_name):
                if file:
                    file_extension = os.path.splitext(file.name)[1].lower()
                    if file_extension not in allowed_extensions:
                        errors.append(f'{field_name}只能是{', '.join(allowed_extensions)}格式')
                        return False
                return True
            
            validate_file(registration_form, '社团注册申请表')
            validate_file(basic_info_form, '学生社团基础信息表')
            validate_file(fee_form, '会费表或免收会费说明书')
            
            # 验证可选文件
            validate_file(leader_change_form, '社团主要负责人变动申请表')
            validate_file(meeting_minutes, '社团大会会议记录')
            validate_file(name_change_form, '社团名称变更申请表')
            validate_file(advisor_change_form, '社团指导老师变动申请表')
            validate_file(business_unit_change_form, '社团业务指导单位变动申请表')
            validate_file(new_media_form, '新媒体平台建立申请表')
            
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
            registration.is_read = False
            registration.resubmission_attempt += 1
            registration.save()
            
            messages.success(request, f'社团注册申请已重新提交（第{registration.resubmission_attempt}次），等待审核')
            return redirect('clubs:view_club_registrations', club_id=club.id)
            
        elif request_type == 'review':
            # 验证文件类型是否为Word格式
            def validate_word_file(file, field_name):
                if not file:
                    return False
                # 检查文件扩展名是否为Word格式
                valid_extensions = ['.doc', '.docx']
                ext = file.name.lower().split('.')[-1]
                if f'.{ext}' not in valid_extensions:
                    errors.append(f'{field_name}必须是Word格式文件(.doc或.docx)')
                    return False
                return True
            
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
                    validate_word_file(file, field_name)
            
            # 验证可选字段的文件类型（如果提供了文件）
            if other_materials:
                validate_word_file(other_materials, '其他材料')
            
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
            submission.is_read_by_president = False
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
            reimbursement.is_read = False
            reimbursement.resubmission_attempt += 1
            reimbursement.save()
            
            messages.success(request, f'报销申请已重新提交（第{reimbursement.resubmission_attempt}次），等待审核')
            return redirect('clubs:view_reimbursements', club_id=club.id)
        
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
            activity.is_read = False
            activity.resubmission_attempt += 1
            activity.save()
            
            messages.success(request, f'活动申请已重新提交（第{activity.resubmission_attempt}次），等待审核')
            return redirect('clubs:view_activity_applications', club_id=club.id)
        
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
            transition.is_read = False
            transition.resubmission_attempt += 1
            transition.save()
            
            messages.success(request, f'换届申请已重新提交（第{transition.resubmission_attempt}次），等待审核')
            return redirect('clubs:user_dashboard')
    
    # GET请求时渲染页面
    return render(request, 'clubs/user/edit_rejected_review.html', context)


@login_required(login_url='login')
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
    
    # 验证文件类型是否为Word格式
    def validate_word_file(file, field_name):
        if not file:
            return False
        # 检查文件扩展名是否为Word格式
        valid_extensions = ['.doc', '.docx']
        ext = file.name.lower().split('.')[-1]
        if f'.{ext}' not in valid_extensions:
            errors.append(f'{field_name}必须是Word格式文件(.doc或.docx)')
            return False
        return True
    
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
    if is_resubmission:
        # 获取所有审核记录中的被拒绝材料
        reviews = SubmissionReview.objects.filter(submission=rejected_submission, status__in=['rejected', 'partially_rejected'])
        for review in reviews:
            if review.rejected_materials:
                rejected_materials.extend(review.rejected_materials)
        # 去重
        rejected_materials = list(set(rejected_materials))
    
    if request.method == 'POST':
        submission_year = request.POST.get('submission_year', '')
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
        if not submission_year:
            errors.append('年份不能为空')
        
        # 确定需要验证的必填字段
        required_files = []
        if is_resubmission:
            # 重新提交时，只需要验证被拒绝或部分拒绝的材料
            rejected_materials = []
            # 获取所有审核记录中的被拒绝材料
            reviews = SubmissionReview.objects.filter(submission=rejected_submission, status__in=['rejected', 'partially_rejected'])
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
        else:
            # 首次提交时，需要验证所有必填字段
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
                validate_word_file(file, field_name)
        
        # 验证可选字段的文件类型（如果提供了文件）
        if other_materials:
            validate_word_file(other_materials, '其他材料')
        
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
            }
            return render(request, 'clubs/user/submit_review.html', context)
        
        if is_resubmission:
            # 更新现有被拒绝的提交记录
            submission = rejected_submission
            
            # 重命名文件并更新被拒绝的材料
            if self_assessment_form:
                self_assessment_form = rename_uploaded_file(self_assessment_form, club.name, '年审', '自查表')
                submission.self_assessment_form = self_assessment_form
            if club_constitution:
                club_constitution = rename_uploaded_file(club_constitution, club.name, '年审', '社团章程')
                submission.club_constitution = club_constitution
            if leader_learning_work_report:
                leader_learning_work_report = rename_uploaded_file(leader_learning_work_report, club.name, '年审', '负责人学习及工作情况表')
                submission.leader_learning_work_report = leader_learning_work_report
            if annual_activity_list:
                annual_activity_list = rename_uploaded_file(annual_activity_list, club.name, '年审', '社团年度活动清单')
                submission.annual_activity_list = annual_activity_list
            if advisor_performance_report:
                advisor_performance_report = rename_uploaded_file(advisor_performance_report, club.name, '年审', '指导教师履职情况表')
                submission.advisor_performance_report = advisor_performance_report
            if financial_report:
                financial_report = rename_uploaded_file(financial_report, club.name, '年审', '年度财务情况表')
                submission.financial_report = financial_report
            if member_composition_list:
                member_composition_list = rename_uploaded_file(member_composition_list, club.name, '年审', '社团成员构成表')
                submission.member_composition_list = member_composition_list
            if new_media_account_report:
                new_media_account_report = rename_uploaded_file(new_media_account_report, club.name, '年审', '新媒体账号及运维情况表')
                submission.new_media_account_report = new_media_account_report
            if other_materials:
                other_materials = rename_uploaded_file(other_materials, club.name, '年审', '其他材料')
                submission.other_materials = other_materials
            
            # 重置状态和审核信息，增加提交次数
            submission.status = 'pending'
            submission.review_count = 0
            submission.reviewed_at = None
            submission.is_read_by_president = False
            submission.resubmission_attempt += 1
            submission.save()
            
            # 删除原有的审核记录
            SubmissionReview.objects.filter(submission=submission).delete()
            
            messages.success(request, f'{submission_year}年审材料重新提交成功（第{submission.resubmission_attempt}次），等待审核！')
        else:
            # 创建新的提交记录
            # 重命名文件
            if self_assessment_form:
                self_assessment_form = rename_uploaded_file(self_assessment_form, club.name, '年审', '自查表')
            if club_constitution:
                club_constitution = rename_uploaded_file(club_constitution, club.name, '年审', '社团章程')
            if leader_learning_work_report:
                leader_learning_work_report = rename_uploaded_file(leader_learning_work_report, club.name, '年审', '负责人学习及工作情况表')
            if annual_activity_list:
                annual_activity_list = rename_uploaded_file(annual_activity_list, club.name, '年审', '社团年度活动清单')
            if advisor_performance_report:
                advisor_performance_report = rename_uploaded_file(advisor_performance_report, club.name, '年审', '指导教师履职情况表')
            if financial_report:
                financial_report = rename_uploaded_file(financial_report, club.name, '年审', '年度财务情况表')
            if member_composition_list:
                member_composition_list = rename_uploaded_file(member_composition_list, club.name, '年审', '社团成员构成表')
            if new_media_account_report:
                new_media_account_report = rename_uploaded_file(new_media_account_report, club.name, '年审', '新媒体账号及运维情况表')
            if other_materials:
                other_materials = rename_uploaded_file(other_materials, club.name, '年审', '其他材料')
            
            ReviewSubmission.objects.create(
                club=club,
                submission_year=int(submission_year),
                self_assessment_form=self_assessment_form,
                club_constitution=club_constitution,
                leader_learning_work_report=leader_learning_work_report,
                annual_activity_list=annual_activity_list,
                advisor_performance_report=advisor_performance_report,
                financial_report=financial_report,
                member_composition_list=member_composition_list,
                new_media_account_report=new_media_account_report,
                other_materials=other_materials,
                status='pending'
            )
            
            messages.success(request, f'{submission_year}年审材料提交成功，等待审核！')
        
        return redirect('clubs:user_dashboard')
    
    # 收集被拒绝的材料列表
    rejected_materials = []
    if is_resubmission:
        reviews = SubmissionReview.objects.filter(submission=rejected_submission, status='rejected')
        for review in reviews:
            if review.rejected_materials:
                rejected_materials.extend(review.rejected_materials)
        # 去重
        rejected_materials = list(set(rejected_materials))
    
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
    }
    return render(request, 'clubs/user/submit_review.html', context)





@login_required(login_url='login')
def view_submissions(request, club_id):
    """查看年审提交历史 - 社长和干事可用"""
    user = request.user
    
    # 检查权限：社长或干事
    if not (_is_president(user) or _is_staff(user)):
        messages.error(request, '您没有权限查看此页面')
        return redirect('clubs:index')
    
    club = get_object_or_404(Club, pk=club_id)
    
    # 社长只能查看自己社团的历史
    if _is_president(user) and (not club.president or club.president != user):
        messages.error(request, '您没有权限查看此社团的历史')
        return redirect('clubs:user_dashboard')
    
    # 返回所有年审记录，并将有拒绝状态审核记录的提交放在前面
    from django.db.models import Q, Case, When, Value, BooleanField
    
    # 获取所有提交记录
    submissions = club.review_submissions.all()
    
    # 使用annotate和order_by来将有拒绝记录的提交放在前面
    submissions = submissions.annotate(
        has_rejected_reviews=Case(
            When(reviews__status='rejected', then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    ).order_by(
        '-has_rejected_reviews',  # 有拒绝记录的排在前面
        '-submission_year',       # 按年份降序
        '-submitted_at'           # 按提交时间降序
    ).distinct()
    
    # 社长查看时，将审核结果标记为已读
    if _is_president(user):
        for submission in submissions:
            if submission.status in ['approved', 'rejected'] and not submission.is_read_by_president:
                submission.is_read_by_president = True
                submission.save()
    
    context = {
        'club': club,
        'submissions': submissions,
    }
    return render(request, 'clubs/user/view_submissions.html', context)


@login_required(login_url='login')
def view_submissions_global(request):
    """查看所有社团的年审记录 - 社长可用，将有拒绝记录的提交放在前面"""
    user = request.user
    
    # 检查权限：社长或干事
    if not (_is_president(user) or _is_staff(user)):
        messages.error(request, '您没有权限查看此页面')
        return redirect('clubs:index')
    
    # 如果用户是社长，则显示该用户所有社团的所有提交
    if _is_president(user):
        # 获取用户所有社团
        clubs = user.clubs_as_president.all()
        if not clubs:
            messages.error(request, '您还没有管理任何社团')
            return redirect('clubs:user_dashboard')
        
        # 返回所有年审记录，并将有拒绝状态审核记录的提交放在前面
        from django.db.models import Q, Case, When, Value, BooleanField
        
        # 获取所有提交记录
        submissions = ReviewSubmission.objects.filter(club__in=clubs)
        
        # 使用annotate和order_by来将有拒绝记录的提交放在前面
        submissions = submissions.annotate(
            has_rejected_reviews=Case(
                When(reviews__status='rejected', then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).order_by(
            '-has_rejected_reviews',  # 有拒绝记录的排在前面
            '-submission_year',       # 按年份降序
            '-submitted_at'           # 按提交时间降序
        ).distinct()
        
        # 社长查看时，将审核结果标记为已读
        for submission in submissions:
            if submission.status in ['approved', 'rejected'] and not submission.is_read_by_president:
                submission.is_read_by_president = True
                submission.save()
        
        context = {
            'clubs': clubs,
            'submissions': submissions,
        }
        return render(request, 'clubs/user/view_submissions_global.html', context)
    elif _is_staff(user):
        # 如果用户是干事，则显示所有社团的所有提交
        from django.db.models import Q, Case, When, Value, BooleanField
        
        # 获取所有提交记录
        submissions = ReviewSubmission.objects.all()
        
        # 使用annotate和order_by来将有拒绝记录的提交放在前面
        submissions = submissions.annotate(
            has_rejected_reviews=Case(
                When(reviews__status='rejected', then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).order_by(
            '-has_rejected_reviews',  # 有拒绝记录的排在前面
            '-submission_year',       # 按年份降序
            '-submitted_at'           # 按提交时间降序
        ).distinct()
        
        context = {
            'submissions': submissions,
        }
        return render(request, 'clubs/user/view_submissions_global.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def approval_center(request):
    """审批中心 - 展示所有类型的审批记录"""
    if not _is_president(request.user):
        messages.error(request, '仅社团社长可以访问审批中心')
        return redirect('clubs:index')
    
    # 获取当前用户作为社长的所有社团
    clubs = Officer.objects.filter(user_profile=request.user.profile, position='president', is_current=True).values_list('club', flat=True)
    
    # 获取所有状态的审批记录
    annual_reviews = ReviewSubmission.objects.filter(club__in=clubs).order_by('-submitted_at')
    registrations = ClubRegistration.objects.filter(club__in=clubs).order_by('-submitted_at')
    applications = ClubRegistrationRequest.objects.filter(requested_by=request.user).order_by('-submitted_at')
    reimbursements = Reimbursement.objects.filter(club__in=clubs).order_by('-submitted_at')
    activity_applications = ActivityApplication.objects.filter(club__in=clubs).order_by('-submitted_at')
    president_transitions = PresidentTransition.objects.filter(club__in=clubs).order_by('-submitted_at')
    
    # 标记所有已审核项为已读
    annual_reviews.filter(status__in=['approved', 'rejected'], is_read_by_president=False).update(is_read_by_president=True)
    registrations.filter(status__in=['approved', 'rejected'], is_read=False).update(is_read=True)
    applications.filter(status__in=['approved', 'rejected'], is_read=False).update(is_read=True)
    reimbursements.filter(status__in=['approved', 'rejected'], is_read=False).update(is_read=True)
    activity_applications.filter(status__in=['approved', 'rejected'], is_read=False).update(is_read=True)
    president_transitions.filter(status__in=['approved', 'rejected'], is_read=False).update(is_read=True)
    
    # 重新获取更新后的数据
    annual_reviews = ReviewSubmission.objects.filter(club__in=clubs).order_by('-submitted_at')
    registrations = ClubRegistration.objects.filter(club__in=clubs).order_by('-submitted_at')
    applications = ClubRegistrationRequest.objects.filter(requested_by=request.user).order_by('-submitted_at')
    reimbursements = Reimbursement.objects.filter(club__in=clubs).order_by('-submitted_at')
    activity_applications = ActivityApplication.objects.filter(club__in=clubs).order_by('-submitted_at')
    president_transitions = PresidentTransition.objects.filter(club__in=clubs).order_by('-submitted_at')
    
    # 标记已修改过的项目（有更新版本提交）
    for item in annual_reviews:
        if item.status == 'rejected':
            newer = ReviewSubmission.objects.filter(
                club=item.club,
                submission_year=item.submission_year,
                submitted_at__gt=item.submitted_at
            ).exists()
            item.has_newer_version = newer
    
    for item in registrations:
        if item.status == 'rejected':
            newer = ClubRegistration.objects.filter(
                club=item.club,
                registration_period=item.registration_period,
                submitted_at__gt=item.submitted_at
            ).exists()
            item.has_newer_version = newer
    
    for item in applications:
        if item.status == 'rejected':
            newer = ClubRegistrationRequest.objects.filter(
                requested_by=item.requested_by,
                club_name=item.club_name,
                submitted_at__gt=item.submitted_at
            ).exists()
            item.has_newer_version = newer
    
    for item in reimbursements:
        if item.status == 'rejected':
            newer = Reimbursement.objects.filter(
                club=item.club,
                submitted_at__gt=item.submitted_at
            ).exists()
            item.has_newer_version = newer
    
    for item in activity_applications:
        if item.status == 'rejected':
            newer = ActivityApplication.objects.filter(
                club=item.club,
                submitted_at__gt=item.submitted_at
            ).exists()
            item.has_newer_version = newer
    
    for item in president_transitions:
        if item.status == 'rejected':
            newer = PresidentTransition.objects.filter(
                club=item.club,
                submitted_at__gt=item.submitted_at
            ).exists()
            item.has_newer_version = newer
    
    approved_rejected_items = {
        'annual_review': annual_reviews,
        'registration': registrations,
        'application': applications,
        'reimbursement': reimbursements,
        'activity_application': activity_applications,
        'president_transition': president_transitions,
    }
    
    context = {
        'approved_rejected_items': approved_rejected_items,
    }
    
    return render(request, 'clubs/user/approval_center.html', context)

@login_required(login_url='login')
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
        items = ReviewSubmission.objects.filter(club__in=clubs).order_by('-submitted_at')
        title = '年审材料历史'
    elif item_type == 'club_registration':
        items = ClubRegistration.objects.filter(club__in=clubs).order_by('-submitted_at')
        title = '社团注册历史'
    elif item_type == 'club_application':
        items = ClubRegistrationRequest.objects.filter(requested_by=request.user).order_by('-submitted_at')
        title = '社团申请历史'
    elif item_type == 'reimbursement':
        items = Reimbursement.objects.filter(club__in=clubs).order_by('-submitted_at')
        title = '报销申请历史'
    elif item_type == 'activity_application':
        items = ActivityApplication.objects.filter(club__in=clubs).order_by('-submitted_at')
        title = '活动申请历史'
    elif item_type == 'president_transition':
        items = PresidentTransition.objects.filter(club__in=clubs).order_by('-submitted_at')
        title = '社长换届历史'
    else:
        messages.error(request, '无效的审批类型')
        return redirect('clubs:approval_center')
    
    # 标记已审核项为已读
    for item in items:
        if item.status in ['approved', 'rejected']:
            if hasattr(item, 'is_read_by_president'):
                if not item.is_read_by_president:
                    item.is_read_by_president = True
                    item.save(update_fields=['is_read_by_president'])
            elif hasattr(item, 'is_read'):
                if not item.is_read:
                    item.is_read = True
                    item.save(update_fields=['is_read'])
    
    context = {
        'items': items,
        'item_type': item_type,
        'title': title,
    }
    
    return render(request, 'clubs/user/approval_history_by_type.html', context)

@login_required(login_url='login')
def approval_detail(request, item_type, item_id):
    """查看审批详情 - 显示审批历史时间轴"""
    if not _is_president(request.user):
        messages.error(request, '仅社团社长可以访问此页面')
        return redirect('clubs:index')
    
    context = {}
    item = None
    
    if item_type == 'annual_review':
        item = get_object_or_404(ReviewSubmission, pk=item_id)
        # 检查权限
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center')
        context['title'] = f'{item.club.name} - 年审记录'
        context['item'] = item
        context['reviews'] = SubmissionReview.objects.filter(submission=item).order_by('-reviewed_at')
        
    elif item_type == 'registration':
        item = get_object_or_404(ClubRegistration, pk=item_id)
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center')
        context['title'] = f'{item.club.name} - 社团注册'
        context['item'] = item
        context['reviews'] = ClubRegistrationReview.objects.filter(registration=item).order_by('-reviewed_at')
        
    elif item_type == 'application':
        # 新社团申请 - ClubRegistrationRequest
        item = get_object_or_404(ClubRegistrationRequest, pk=item_id)
        if item.requested_by != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center')
        context['title'] = f'{item.club_name} - 新社团申请'
        context['item'] = item
        # 为新社团申请创建模拟的审核记录
        reviews = []
        if item.status in ['approved', 'rejected'] and item.reviewed_at:
            reviews.append({
                'reviewed_at': item.reviewed_at,
                'reviewer': item.reviewer if item.reviewer else None,
                'status': item.status,
                'comment': item.reviewer_comment or '',
            })
        context['reviews'] = reviews
        
    elif item_type == 'reimbursement':
        item = get_object_or_404(Reimbursement, pk=item_id)
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center')
        context['title'] = f'{item.club.name} - 报销申请'
        context['item'] = item
        # 为报销申请创建模拟的审核记录
        reviews = []
        if item.status in ['approved', 'rejected'] and item.reviewed_at:
            reviews.append({
                'reviewed_at': item.reviewed_at,
                'reviewer': item.reviewer,
                'status': item.status,
                'comment': item.reviewer_comment or '',
            })
        context['reviews'] = reviews
        
    elif item_type == 'activity_application':
        item = get_object_or_404(ActivityApplication, pk=item_id)
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center')
        context['title'] = f'{item.club.name} - 活动申请'
        context['item'] = item
        # 为活动申请创建模拟的审核记录
        reviews = []
        if item.status in ['approved', 'rejected'] and item.reviewed_at:
            reviews.append({
                'reviewed_at': item.reviewed_at,
                'reviewer': item.reviewer,
                'status': item.status,
                'comment': item.reviewer_comment or '',
            })
        context['reviews'] = reviews
        
    elif item_type == 'president_transition':
        item = get_object_or_404(PresidentTransition, pk=item_id)
        if item.club.president != request.user:
            messages.error(request, '您没有权限查看此项目')
            return redirect('clubs:approval_center')
        context['title'] = f'{item.club.name} - 社长交接'
        context['item'] = item
        # 为社长换届创建模拟的审核记录
        reviews = []
        if item.status in ['approved', 'rejected'] and item.reviewed_at:
            reviews.append({
                'reviewed_at': item.reviewed_at,
                'reviewer': item.reviewer,
                'status': item.status,
                'comment': item.reviewer_comment or '',
            })
        context['reviews'] = reviews
    
    else:
        messages.error(request, '无效的项目类型')
        return redirect('clubs:approval_center')
    
    context['item_type'] = item_type
    return render(request, 'clubs/user/approval_detail.html', context)

@login_required(login_url='login')
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

@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def review_submission(request, submission_id):
    """审核年审材料 - 干事和管理员可用"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以审核年审材料')
        return redirect('clubs:index')
    
    submission = get_object_or_404(ReviewSubmission, pk=submission_id)
    
    # 检查当前用户是否已经审核过该材料
    if request.method == 'GET':
        existing_review = SubmissionReview.objects.filter(submission=submission, reviewer=request.user).first()
        if existing_review:
            messages.error(request, '您已经审核过该材料，无法再次查看审核页面')
            # 根据用户角色选择不同的重定向页面
            if _is_staff(request.user):
                return redirect('clubs:staff_dashboard')
            return redirect('clubs:approval_center')
    
    if request.method == 'POST':
        status = request.POST.get('review_status', '')
        comment = request.POST.get('review_comment', '').strip()
        
        if status not in ['approved', 'rejected']:
            messages.error(request, '无效的审核状态')
            return redirect('clubs:admin_dashboard')
        
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
        
        # 根据用户角色选择不同的重定向页面
        if _is_staff(request.user):
            return redirect('clubs:staff_dashboard')
        return redirect('clubs:approval_center')
    
    # 准备材料列表用于审核表单
    submission_materials = []
    material_fields = [
        ('self_assessment_form', '社团自查表', 'fact_check'),
        ('club_constitution', '社团章程', 'description'),
        ('leader_learning_work_report', '负责人学习及工作情况表', 'person'),
        ('annual_activity_list', '社团年度活动清单', 'event_note'),
        ('advisor_performance_report', '指导教师履职情况表', 'school'),
        ('financial_report', '年度财务情况表', 'account_balance'),
        ('member_composition_list', '社团成员构成表', 'group'),
        ('new_media_account_report', '新媒体账号及运维情况表', 'campaign'),
        ('other_materials', '其他材料', 'attach_file'),
    ]
    
    for field_name, label, icon in material_fields:
        if getattr(submission, field_name):
            submission_materials.append({
                'field_name': field_name,
                'label': label,
                'icon': icon
            })
    
    context = {
        'submission': submission,
        'club': submission.club,
        'existing_reviews': SubmissionReview.objects.filter(submission=submission).order_by('-reviewed_at'),
        'submission_materials': submission_materials,
    }
    return render(request, 'clubs/staff/review_submission.html', context)





# ==================== 报销功能 ====================

@login_required(login_url='login')
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

    # 社长查看时，将已审核的记录标记为已读
    if _is_president(user):
        for reimbursement in reimbursements:
            if reimbursement.status in ['approved', 'rejected'] and not reimbursement.is_read:
                reimbursement.is_read = True
                reimbursement.save(update_fields=['is_read'])
    
    context = {
        'club': club,
        'reimbursements': reimbursements,
    }
    return render(request, 'clubs/user/view_reimbursements.html', context)


@login_required(login_url='login')
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
    
    if request.method == 'POST':
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
            return render(request, 'clubs/user/submit_reimbursement.html', {
                'errors': errors,
                'club': club,
                'templates': reimbursement_templates,
            })
        
        # 重命名报销凭证文件
        receipt_file = rename_uploaded_file(receipt_file, club.name, '报销', '凭证')
        
        try:
            Reimbursement.objects.create(
                club=club,
                submission_date=submission_date,
                reimbursement_amount=reimbursement_amount,
                description=description,
                receipt_file=receipt_file,
                status='pending'
            )
            messages.success(request, '报销材料已提交，等待审核！')
            return redirect('clubs:user_dashboard')
        except Exception as e:
            messages.error(request, f'提交失败: {str(e)}')
    
    context = {
        'club': club,
        'templates': reimbursement_templates,
    }
    return render(request, 'clubs/user/submit_reimbursement.html', context)





# ==================== 干事管理功能 ====================

@login_required(login_url='login')
def get_templates_by_type(template_type):
    """根据模板类型获取活跃的模板列表"""
    return Template.objects.filter(template_type=template_type, is_active=True).order_by('-created_at')

def upload_template(request):
    """上传模板 - 仅干事可用"""
    if not _is_staff(request.user):
        messages.error(request, '仅干事可以上传模板')
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


@login_required(login_url='login')
def review_reimbursement(request, reimbursement_id):
    """审核报销材料 - 干事和管理员可用"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以审核报销')
        return redirect('clubs:index')
    
    reimbursement = get_object_or_404(Reimbursement, pk=reimbursement_id)
    
    if request.method == 'POST':
        decision = request.POST.get('decision', '')
        review_comments = request.POST.get('review_comments', '').strip()
        
        if decision not in ['approved', 'rejected']:
            messages.error(request, '状态不合法')
            return redirect('clubs:staff_dashboard')
        
        reimbursement.status = decision
        reimbursement.reviewer_comment = review_comments
        reimbursement.reviewed_at = timezone.now()
        reimbursement.reviewer = request.user
        reimbursement.save()
        
        messages.success(request, f'报销材料已{'批准' if decision == 'approved' else '拒绝'}')
        return redirect('clubs:staff_dashboard')
    
    context = {
        'reimbursement': reimbursement,
    }
    return render(request, 'clubs/staff/review_reimbursement.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def review_club_registration(request, registration_id):
    """审核社团注册申请 - 仅干事和管理员可用"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '仅干事和管理员可以审核社团注册')
        return redirect('clubs:index')
    
    registration = get_object_or_404(ClubRegistrationRequest, pk=registration_id)
    
    # 检查当前用户是否已经审核过该申请
    if registration.reviews.filter(reviewer=request.user).exists():
        messages.error(request, '您已经审核过该社团注册申请，无法再次审核')
        return redirect('clubs:staff_dashboard')
    
    if request.method == 'POST':
        # 兼容两种参数名：'decision'（来自按钮提交）和'review_status'（统一名称）
        decision = request.POST.get('decision', '') or request.POST.get('review_status', '')
        review_comments = request.POST.get('review_comments', '').strip() or request.POST.get('review_comment', '').strip()
        
        # 获取被拒绝的材料
        rejected_materials = []
        if 'reject_establishment_application' in request.POST:
            rejected_materials.append('establishment_application')
        if 'reject_constitution_draft' in request.POST:
            rejected_materials.append('constitution_draft')
        if 'reject_three_year_plan' in request.POST:
            rejected_materials.append('three_year_plan')
        if 'reject_leaders_resumes' in request.POST:
            rejected_materials.append('leaders_resumes')
        if 'reject_one_month_activity_plan' in request.POST:
            rejected_materials.append('one_month_activity_plan')
        if 'reject_advisor_certificates' in request.POST:
            rejected_materials.append('advisor_certificates')
        
        # 处理直接从模板中获取的被拒绝材料列表
        rejected_materials_list = request.POST.getlist('rejected_materials')
        if rejected_materials_list:
            rejected_materials.extend(rejected_materials_list)
        
        # 去重
        rejected_materials = list(set(rejected_materials))
        
        if decision not in ['approved', 'rejected']:
            messages.error(request, '状态不合法')
            return redirect('clubs:staff_dashboard')
        
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
    
    # 准备材料列表
    material_fields = [
        ('establishment_application', '社团成立申请表', 'description'),
        ('constitution_draft', '社团章程草案', 'gavel'),
        ('three_year_plan', '三年规划', 'calendar_today'),
        ('leaders_resumes', '负责人简历', 'person'),
        ('one_month_activity_plan', '一个月活动计划', 'event'),
        ('advisor_certificates', '指导老师聘书', 'badge'),
    ]
    
    materials_list = []
    for field_name, label, icon in material_fields:
        if getattr(registration, field_name):
            materials_list.append({
                'field_name': field_name,
                'label': label,
                'icon': icon
            })
    
    context = {
        'registration': registration,
        'rejected_materials': ClubApplicationReview.REJECTED_MATERIALS_CHOICES if hasattr(ClubApplicationReview, 'REJECTED_MATERIALS_CHOICES') else [],
        'materials_list': materials_list,
    }
    return render(request, 'clubs/staff/review_club_registration.html', context)


@login_required(login_url='login')
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
    if not _is_staff(request.user) and not _is_admin(request.user):
        messages.error(request, '您没有权限进行审核操作')
        return redirect('clubs:index')
    
    # 从URL查询参数中获取请求类型和申请次数
    request_type = request.GET.get('type', '')
    submission_number = request.GET.get('number', '')
    
    if not request_type:
        messages.error(request, '无效的审核请求类型')
        return redirect('clubs:staff_dashboard')
    
    # 对于某些审核类型不需要申请次数
    # - staff_registration: 用 club_id 作为 user_id
    # - registration: 用 club_id 作为申请ID
    if request_type not in ['staff_registration', 'registration']:
        if not submission_number:
            messages.error(request, '无效的申请次数')
            return redirect('clubs:staff_dashboard')
        
        # 尝试将申请次数转换为整数
        try:
            submission_number = int(submission_number)
        except ValueError:
            messages.error(request, '无效的申请次数格式')
            return redirect('clubs:staff_dashboard')
    
    # 定义不同审核类型的被拒绝材料字段映射
    rejected_materials_mapping = {
        'submission': [
            'self_assessment_form', 'club_constitution', 'leader_learning_work_report',
            'annual_activity_list', 'advisor_performance_report', 'financial_report',
            'member_composition_list', 'new_media_account_report', 'other_materials'
        ],
        'registration': [
            'establishment_application', 'constitution_draft', 'three_year_plan',
            'leaders_resumes', 'one_month_activity_plan', 'advisor_certificates'
        ],
        'club_registration_submission': [
            'registration_form', 'constitution', 'leader_information',
            'advisor_information', 'activity_plan', 'financial_budget',
            'member_list', 'application_reason', 'other_materials'
        ],
        'reimbursement': [
            'reimbursement_form', 'expense_invoices'
        ],
        'leader_change': [],  # 社长变更可能不需要具体材料
        'staff_registration': []  # 干事注册可能不需要具体材料
    }
    
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
                # 获取当前审核类型对应的材料字段列表
                material_fields = rejected_materials_mapping.get(request_type, [])
                
                # 收集被拒绝的材料
                rejected_materials = request.POST.getlist('rejected_materials')
                
                # 如果没有选择任何被拒绝的材料，默认拒绝所有
                if not rejected_materials:
                    rejected_materials = material_fields
            
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
        
        # 构建拒绝材料列表
        rejected_materials_mapping_display = [
            ('self_assessment_form', '自查表', 'description'),
            ('club_constitution', '社团章程', 'gavel'),
            ('leader_learning_work_report', '负责人学习及工作情况表', 'assignment_ind'),
            ('annual_activity_list', '社团年度活动清单', 'event_note'),
            ('advisor_performance_report', '指导教师履职情况表', 'badge'),
            ('financial_report', '年度财务情况表', 'account_balance'),
            ('member_composition_list', '社团成员构成表', 'groups'),
            ('new_media_account_report', '新媒体账号及运维情况表', 'campaign'),
            ('other_materials', '其他材料', 'attach_file')
        ]
        
        # 过滤只显示已提交的材料，并转换为统一组件格式
        materials_list = []
        for field, display_name, icon in rejected_materials_mapping_display:
            if hasattr(obj, field) and getattr(obj, field):
                materials_list.append({
                    'field_name': field,
                    'label': display_name,
                    'icon': icon
                })

        # 如果检测不到上传文件，仍提供完整材料列表，避免拒绝面板缺失
        if not materials_list:
            materials_list = [
                {
                    'field_name': field,
                    'label': display_name,
                    'icon': icon
                }
                for field, display_name, icon in rejected_materials_mapping_display
            ]

        # 若未能识别到上传文件，仍然提供完整材料列表以便选择
        if not materials_list:
            materials_list = [
                {
                    'field_name': field,
                    'label': display_name,
                    'icon': icon
                }
                for field, display_name, icon in rejected_materials_mapping_display
            ]
        
        # 准备用于模板显示的文件列表 (submission_files)
        submission_files = []
        for field, display_name, icon in rejected_materials_mapping_display:
            file_field = getattr(obj, field, None)
            if file_field:
                # 获取文件扩展名以确定类型
                file_extension = file_field.name.split('.')[-1].lower() if '.' in file_field.name else ''
                submission_files.append({
                    'name': display_name,
                    'url': file_field.url,
                    'type': file_extension
                })
        
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
            
            # 兼容两种参数名：'decision'（来自按钮提交）和'review_status'（统一名称）
            decision = request.POST.get('decision', '') or request.POST.get('review_status', '')
            review_comments = request.POST.get('review_comments', '').strip() or request.POST.get('review_comment', '').strip()
            
            # 统一处理被拒绝的材料
            rejected_materials = []
            if decision == 'rejected':
                # 获取当前审核类型对应的材料字段列表
                material_fields = rejected_materials_mapping.get(request_type, [])
                
                # 收集被拒绝的材料 - 统一使用getlist('rejected_materials')，与模板保持一致
                rejected_materials = request.POST.getlist('rejected_materials')
                
                # 如果没有选择任何被拒绝的材料，默认拒绝所有
                if not rejected_materials:
                    rejected_materials = material_fields
            
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
        
        # 构建注册申请的拒绝材料列表
        rejected_materials_mapping_display = [
            ('establishment_application', '社团成立申请书', 'description'),
            ('constitution_draft', '社团章程草案', 'gavel'),
            ('three_year_plan', '社团三年发展规划', 'calendar_today'),
            ('leaders_resumes', '社团拟任负责人和指导老师的详细简历和身份证复印件', 'person'),
            ('one_month_activity_plan', '社团组建一个月后的活动计划', 'event'),
            ('advisor_certificates', '社团老师的相关专业证书', 'badge')
        ]
        
        # 过滤只显示已提交的材料，并转换为统一组件格式
        materials_list = []
        for field, display_name, icon in rejected_materials_mapping_display:
            file_field = getattr(obj, field, None) if hasattr(obj, field) else None
            if file_field:
                materials_list.append({
                    'field_name': field,
                    'label': display_name,
                    'icon': icon,
                    'file': file_field
                })
        
        # 为模板准备submission_files（用于材料显示）
        submission_files = []
        for field, display_name, icon in rejected_materials_mapping_display:
            file_field = getattr(obj, field, None) if hasattr(obj, field) else None
            if file_field:
                submission_files.append({
                    'name': display_name,
                    'url': file_field.url
                })
        
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
                # 获取当前审核类型对应的材料字段列表
                material_fields = rejected_materials_mapping.get(request_type, [])
                
                # 收集被拒绝的材料
                rejected_materials = request.POST.getlist('rejected_materials')
                
                # 如果没有选择任何被拒绝的材料，默认拒绝所有
                if not rejected_materials:
                    rejected_materials = material_fields
            
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
        
        # 构建报销申请的拒绝材料列表
        rejected_materials_mapping_display = [
            ('receipt_file', '报销凭证', 'receipt')
        ]
        
        # 过滤只显示已提交的材料，并转换为统一组件格式
        materials_list = []
        for field, display_name, icon in rejected_materials_mapping_display:
            if hasattr(obj, field) and getattr(obj, field):
                materials_list.append({
                    'field_name': field,
                    'label': display_name,
                    'icon': icon
                })
        
        # 准备用于模板显示的文件列表 (submission_files)
        submission_files = []
        for field, display_name, icon in rejected_materials_mapping_display:
            file_field = getattr(obj, field, None)
            if file_field:
                # 获取文件扩展名以确定类型
                file_extension = file_field.name.split('.')[-1].lower() if '.' in file_field.name else ''
                submission_files.append({
                    'name': display_name,
                    'url': file_field.url,
                    'type': file_extension
                })
        
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
            # 兼容两种参数名：'decision'（来自按钮提交）和'review_status'（统一名称）
            decision = request.POST.get('decision', '') or request.POST.get('review_status', '')
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
                    material_fields = rejected_materials_mapping.get(request_type, [])
                    rejected_materials = material_fields
            
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
        
        # 构建社团注册材料的拒绝材料列表
        rejected_materials_mapping_display = [
              ('registration_form', '注册申请表', 'description'),
              ('basic_info_form', '学生社团基础信息表', 'info'),
              ('membership_fee_form', '会费表或免收会费说明书', 'account_balance'),
              ('leader_change_application', '负责人变更申请', 'swap_horiz'),
            ('meeting_minutes', '会议记录', 'fact_check'),
            ('name_change_application', '社团名称变更申请', 'edit'),
            ('advisor_change_application', '指导老师变更申请', 'badge'),
            ('business_advisor_change_application', '业务指导单位变更申请', 'business'),
            ('new_media_application', '新媒体运营平台申请', 'campaign')
        ]
        
        # 过滤只显示已提交的材料，并转换为统一组件格式
        materials_list = []
        for field, display_name, icon in rejected_materials_mapping_display:
            if hasattr(obj, field) and getattr(obj, field):
                materials_list.append({
                    'field_name': field,
                    'label': display_name,
                    'icon': icon
                })
        
        # 构建文件列表用于统一模板显示
        submission_files = []
        file_field_mapping = {
            'registration_form': ('社团注册申请表', 'description'),
            'basic_info_form': ('学生社团基础信息表', 'info'),
            'membership_fee_form': ('会费表或免收会费说明书', 'account_balance'),
            'leader_change_application': ('负责人变更申请', 'swap_horiz'),
            'meeting_minutes': ('会议记录', 'fact_check'),
            'name_change_application': ('社团名称变更申请', 'edit'),
            'advisor_change_application': ('指导老师变更申请', 'badge'),
            'business_advisor_change_application': ('业务指导单位变更申请', 'business'),
            'new_media_application': ('新媒体运营平台申请', 'campaign')
        }
        
        for field_name, (display_name, icon) in file_field_mapping.items():
            file_field = getattr(obj, field_name, None)
            if file_field:
                # 获取文件扩展名以确定类型
                file_extension = file_field.name.split('.')[-1].lower() if '.' in file_field.name else ''
                submission_files.append({
                    'name': display_name,
                    'url': file_field.url,
                    'type': file_extension
                })
        
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
    
    elif request_type == 'club_info_change':
        from clubs.models import ClubInfoChangeRequest, Club
        # 确保已经导入了Club模型
        
        # 获取当前社团
        club = get_object_or_404(Club, pk=club_id)
        
        # 获取该社团所有此类申请（按提交时间排序）
        submissions = ClubInfoChangeRequest.objects.filter(club=club).order_by('submitted_at')
        
        # 优先使用ID参数获取信息修改申请（解决重新提交后的链接问题）
        change_id = request.GET.get('id', '')
        if change_id:
            try:
                obj = ClubInfoChangeRequest.objects.get(pk=change_id, club=club)
                # 计算该申请在列表中的实际位置
                submission_number = list(submissions).index(obj) + 1
            except (ValueError, ClubInfoChangeRequest.DoesNotExist):
                # 如果ID无效，回退到使用submission_number
                if submission_number > len(submissions) or submission_number < 1:
                    messages.error(request, '无效的申请次数')
                    return redirect('clubs:staff_dashboard')
                obj = submissions[submission_number - 1]
        else:
            # 没有ID参数时，使用submission_number
            if submission_number > len(submissions) or submission_number < 1:
                messages.error(request, '无效的申请次数')
                return redirect('clubs:staff_dashboard')
            obj = submissions[submission_number - 1]
        
        template_name = 'clubs/staff/review_request.html'  # 使用统一审核模板
        title = f"审核 {club.name} 的第 {submission_number} 次信息变更申请"
        
        # 处理POST请求
        if request.method == 'POST':
            decision = request.POST.get('status', '')  # 统一使用'status'参数名
            review_comments = request.POST.get('comment', '').strip()  # 统一使用'comment'参数名
            
            if decision not in ['approved', 'rejected']:
                messages.error(request, '状态不合法')
                return redirect('clubs:staff_dashboard')
            
            obj.status = decision
            obj.reviewer_comment = review_comments
            obj.reviewed_at = timezone.now()
            
            # 如果批准，更新社团信息
            if decision == 'approved':
                if obj.new_name:
                    club.name = obj.new_name
                if obj.new_description:
                    club.description = obj.new_description
                if obj.new_members_count is not None:
                    club.members_count = obj.new_members_count
                club.save()
            
            obj.save()
            messages.success(request, f'社团信息变更申请已{'批准' if decision == 'approved' else '拒绝'}')
            return redirect('clubs:staff_dashboard')
        
        # 构建社团信息变更的拒绝材料列表
        rejected_materials_mapping_display = [
            ('new_name', '社团名称变更', 'edit'),
            ('new_description', '社团简介变更', 'description'),
            ('new_president', '社长信息变更', 'person'),
            ('new_advisor', '指导老师变更', 'badge'),
            ('new_members_count', '成员数量变更', 'groups'),
            ('supporting_document', '支持文件', 'attach_file')
        ]
        
        # 过滤只显示已提交的材料，并转换为统一组件格式
        materials_list = []
        for field, display_name, icon in rejected_materials_mapping_display:
            if hasattr(obj, field) and getattr(obj, field):
                materials_list.append({
                    'field_name': field,
                    'label': display_name,
                    'icon': icon
                })
        
        context = {
            'change_request': obj,
            'materials_list': materials_list,
        }
    
    else:
        messages.error(request, '无效的审核请求类型')
        return redirect('clubs:staff_dashboard')
    
    # 添加通用上下文
    context['title'] = title
    context['request_type'] = request_type
    
    return render(request, template_name, context)

# ==================== 管理员功能 ====================

@login_required(login_url='login')
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


@login_required(login_url='login')
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


@login_required(login_url='login')
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


@login_required(login_url='login')
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

@login_required(login_url='login')
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
    
    if request.method == 'POST':
        registration_form = request.FILES.get('registration_form', None)
        basic_info_form = request.FILES.get('basic_info_form', None)
        membership_fee_form = request.FILES.get('membership_fee_form', None)
        leader_change_application = request.FILES.get('leader_change_application', None)
        meeting_minutes = request.FILES.get('meeting_minutes', None)
        name_change_application = request.FILES.get('name_change_application', None)
        advisor_change_application = request.FILES.get('advisor_change_application', None)
        business_advisor_change_application = request.FILES.get('business_advisor_change_application', None)
        new_media_application = request.FILES.get('new_media_application', None)
        
        # 验证必填文件
        if not registration_form:
            messages.error(request, '请上传社团注册申请表')
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if not basic_info_form:
            messages.error(request, '请上传学生社团基础信息表')
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if not membership_fee_form:
            messages.error(request, '请上传会费表或免收会费说明书')
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        # 验证文件类型
        allowed_extensions = ['.zip', '.rar', '.docx']
        
        def validate_file(file, field_name):
            if file:
                file_extension = os.path.splitext(file.name)[1].lower()
                if file_extension not in allowed_extensions:
                    messages.error(request, f'{field_name}只能是{', '.join(allowed_extensions)}格式')
                    return False
            return True
        
        if not validate_file(registration_form, '社团注册申请表'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if not validate_file(basic_info_form, '学生社团基础信息表'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if not validate_file(membership_fee_form, '会费表或免收会费说明书'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        # 验证可选文件
        if leader_change_application and not validate_file(leader_change_application, '社团主要负责人变动申请表'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if meeting_minutes and not validate_file(meeting_minutes, '社团大会会议记录'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if name_change_application and not validate_file(name_change_application, '社团名称变更申请表'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if advisor_change_application and not validate_file(advisor_change_application, '社团指导老师变动申请表'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if business_advisor_change_application and not validate_file(business_advisor_change_application, '社团业务指导单位变动申请表'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        if new_media_application and not validate_file(new_media_application, '新媒体平台建立申请表'):
            return redirect('clubs:submit_club_registration', club_id=club_id)
        
        # 创建社团注册记录
        registration = ClubRegistration.objects.create(
            club=club,
            registration_period=active_period,  # 关联到当前活跃的注册周期
            requested_by=request.user,
            registration_form=registration_form,
            basic_info_form=basic_info_form,
            membership_fee_form=membership_fee_form,
            leader_change_application=leader_change_application if leader_change_application else None,
            meeting_minutes=meeting_minutes if meeting_minutes else None,
            name_change_application=name_change_application if name_change_application else None,
            advisor_change_application=advisor_change_application if advisor_change_application else None,
            business_advisor_change_application=business_advisor_change_application if business_advisor_change_application else None,
            new_media_application=new_media_application if new_media_application else None,
            status='pending'
        )
        
        messages.success(request, '社团注册已提交，等待审核')
        return redirect('clubs:user_dashboard')
    
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
        'active_period': active_period
    }
    return render(request, 'clubs/user/submit_club_registration.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])


@login_required(login_url='login')
def view_club_registrations(request, club_id):
    """查看社团注册记录 - 仅社团社长可用"""
    # 获取社团对象
    club = get_object_or_404(Club, pk=club_id)
    
    # 验证权限：只有当前社团社长可以查看注册记录
    is_club_president = Officer.objects.filter(
        user_profile__user=request.user,
        club=club,
        position='president',
        is_current=True
    ).exists()
    
    if not is_club_president:
        messages.error(request, '仅社团社长可以查看社团注册记录')
        return redirect('clubs:user_dashboard')
    
    registrations = ClubRegistration.objects.filter(club=club).order_by('-submitted_at')

    # 将已审核的记录标记为已读
    for registration in registrations:
        if registration.status in ['approved', 'rejected'] and not registration.is_read:
            registration.is_read = True
            registration.save(update_fields=['is_read'])
    
    context = {
        'club': club,
        'registrations': registrations,
    }
    return render(request, 'clubs/user/view_club_registrations.html', context)

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def test_review_access(request, registration_id):
    """测试审核访问权限"""
    # 简单的权限检查
    try:
        user_role = request.user.profile.role
        print(f"User role: {user_role}")
        if user_role in ['staff', 'admin']:
            # 权限通过，渲染审核页面
            registration = get_object_or_404(ClubRegistration, pk=registration_id)
            
            # 检查审核是否已完成，已完成则不允许查看
            if registration.status != 'pending':
                messages.error(request, '该申请已完成审核，无法再查看审核页面')
                return redirect('clubs:staff_dashboard')
            
            # 检查当前用户是否已经审核过该申请
            # 禁止同一干事审核同一个请求两次及以上
            has_reviewed = registration.reviews.filter(reviewer=request.user).exists()
            if has_reviewed:
                messages.error(request, '您已经审核过该社团注册申请，无法再次审核')
                return redirect('clubs:staff_dashboard')
            
            if request.method == 'POST':
                # 兼容两种参数名：'decision'（旧名称）和'review_status'（统一名称）
                decision = request.POST.get('decision', '') or request.POST.get('review_status', '')
                review_comments = request.POST.get('review_comments', '').strip() or request.POST.get('review_comment', '').strip()
                
                # 获取被拒绝的材料
                rejected_materials = []
                if 'reject_registration_form' in request.POST:
                    rejected_materials.append('registration_form')
                if 'reject_basic_info_form' in request.POST:
                    rejected_materials.append('basic_info_form')
                if 'reject_membership_fee_form' in request.POST:
                    rejected_materials.append('membership_fee_form')
                if 'reject_leader_change_application' in request.POST:
                    rejected_materials.append('leader_change_application')
                if 'reject_meeting_minutes' in request.POST:
                    rejected_materials.append('meeting_minutes')
                if 'reject_name_change_application' in request.POST:
                    rejected_materials.append('name_change_application')
                if 'reject_advisor_change_application' in request.POST:
                    rejected_materials.append('advisor_change_application')
                if 'reject_business_advisor_change_application' in request.POST:
                    rejected_materials.append('business_advisor_change_application')
                if 'reject_new_media_application' in request.POST:
                    rejected_materials.append('new_media_application')
                
                if decision not in ['approved', 'rejected']:
                    messages.error(request, '状态不合法')
                    return redirect('clubs:staff_dashboard')
                
                # 如果是拒绝，需要确保至少有一个被拒绝的材料
                if decision == 'rejected' and not rejected_materials:
                    messages.error(request, '拒绝必须选择至少一个被拒绝的材料')
                    return redirect('clubs:test_review_access', registration_id=registration_id)
                
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
                
                return redirect('clubs:staff_dashboard')
            
            # 计算审核统计信息
            approved_count = registration.reviews.filter(status='approved').count()
            rejected_count = registration.reviews.filter(status='rejected').count()
            
            context = {
                'registration': registration,
                'approved_count': approved_count,
                'rejected_count': rejected_count,
                'has_reviewed': has_reviewed
            }
            
            return render(request, 'clubs/staff/review_club_registration_submission.html', context)
        else:
            # 权限不足，重定向到首页
            messages.error(request, '仅干事和管理员可以审核社团注册')
            return redirect('clubs:index')
    except UserProfile.DoesNotExist:
        messages.error(request, '用户配置文件不存在')
        return redirect('clubs:index')

def review_club_registration_submission(request, registration_id):
    """审核社团注册 - 仅干事和管理员可用"""
    # 重定向到测试视图
    return redirect('clubs:test_review_access', registration_id=registration_id)


@login_required(login_url='login')
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


@login_required(login_url='login')
@login_required(login_url='login')
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
    
    context = {
        'users': users,
        'total_users': User.objects.count(),
        'search': search,
        'role': role,
    }
    return render(request, 'clubs/admin/manage_users.html', context)


@login_required(login_url='login')
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


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def admin_reset_user_password(request, user_id):
    """管理员重置用户密码 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以重置用户密码')
        return redirect('clubs:index')
    
    target_user = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        errors = []
        if not new_password:
            errors.append('新密码不能为空')
        elif len(new_password) < 6:
            errors.append('新密码至少6个字符')
        elif new_password != confirm_password:
            errors.append('两次密码不一致')
        
        if errors:
            context = {
                'target_user': target_user,
                'errors': errors,
            }
            return render(request, 'clubs/admin/admin_reset_user_password.html', context)
        
        # 重置密码
        target_user.set_password(new_password)
        target_user.save()
        messages.success(request, f'已成功重置用户 {target_user.username} 的密码')
        return redirect('clubs:manage_users')
    
    context = {
        'target_user': target_user,
    }
    return render(request, 'clubs/admin/admin_reset_user_password.html', context)


@login_required(login_url='login')
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
        
        # 修改教师负责的社团
        elif action == 'change_teacher_clubs':
            if target_user.profile.role != 'teacher':
                errors.append('只有教师可以修改负责的社团')
            else:
                selected_club_ids = request.POST.getlist('responsible_clubs')
                
                try:
                    # 清除原有的关联
                    TeacherClubAssignment.objects.filter(user=target_user).delete()
                    
                    # 添加新的关联
                    for club_id in selected_club_ids:
                        try:
                            club = Club.objects.get(pk=club_id)
                            TeacherClubAssignment.objects.create(
                                user=target_user,
                                club=club
                            )
                        except Club.DoesNotExist:
                            errors.append(f'社团ID {club_id} 不存在')
                    
                    if not errors:
                        success_messages.append(f'已成功更新用户 {target_user.username} 的负责社团')
                except Exception as e:
                    errors.append(f'更新负责社团时出错: {str(e)}')
    
    # 获取用户角色信息
    try:
        profile = target_user.profile
    except UserProfile.DoesNotExist:
        profile = None
    
    # 如果是教师，获取所有社团和该教师负责的社团
    all_clubs = []
    responsible_club_ids = []
    if profile and profile.role == 'teacher':
        all_clubs = Club.objects.all().order_by('name')
        responsible_club_ids = list(
            TeacherClubAssignment.objects.filter(user=target_user).values_list('club_id', flat=True)
        )
    
    context = {
        'target_user': target_user,
        'profile': profile,
        'errors': errors,
        'success_messages': success_messages,
        'is_admin_view': True,  # 标记为管理员视图
        'ROLE_CHOICES': UserProfile.ROLE_CHOICES,
        'POLITICAL_STATUS_CHOICES': UserProfile.POLITICAL_STATUS_CHOICES,
        'all_clubs': all_clubs,
        'responsible_club_ids': responsible_club_ids,
    }
    
    return render(request, 'clubs/auth/change_account_settings.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def change_user_role(request, user_id):
    """修改用户角色 - 仅管理员可用"""
    if not _is_admin(request.user):
        messages.error(request, '仅管理员可以修改用户角色')
        return redirect('clubs:index')
    
    target_user = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        new_role = request.POST.get('new_role', '')
        
        if new_role not in ['president', 'staff', 'admin', 'teacher', 'user']:
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


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def create_teacher_account(request):
    """管理员创建用户账户 - 支持创建任何用户类型"""
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
        role = request.POST.get('role', 'user').strip()
        student_id = request.POST.get('student_id', '').strip()
        club_ids = request.POST.getlist('clubs')  # 教师可以分配到多个社团
        
        errors = []
        
        # 验证
        if not username:
            errors.append('用户名不能为空')
        elif User.objects.filter(username=username).exists():
            errors.append('用户名已存在')
        elif len(username) < 3 or len(username) > 30:
            errors.append('用户名长度应在3-30个字符之间')
        
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
        
        if role not in ['user', 'teacher', 'staff', 'president', 'admin']:
            errors.append('无效的用户角色')
        
        # 如果是教师，必须分配至少一个社团
        if role == 'teacher' and not club_ids:
            errors.append('教师必须分配至少一个社团')
        
        # 对于非staff角色，student_id可选；对于staff角色，student_id必填
        if not student_id and role in ['staff', 'president']:
            student_id = f"{role.upper()}_{username}"
        elif not student_id:
            # 为其他角色生成唯一的student_id
            import uuid
            student_id = f"{role.upper()}_{username}_{str(uuid.uuid4())[:8]}"
        elif UserProfile.objects.filter(student_id=student_id).exists():
            errors.append('学号已被使用')
        
        if errors:
            clubs = Club.objects.all().order_by('name')
            return render(request, 'clubs/admin/create_teacher.html', {
                'errors': errors,
                'form_data': request.POST,
                'clubs': clubs,
                'selected_clubs': club_ids,
            })
        
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
        UserProfile.objects.create(
            user=user,
            role=role,
            status=status,
            real_name=real_name,
            phone=phone,
            wechat=wechat,
            student_id=student_id
        )
        
        # 如果是教师，创建社团分配关系
        if role == 'teacher':
            from .models import TeacherClubAssignment
            for club_id in club_ids:
                try:
                    club = Club.objects.get(id=club_id)
                    TeacherClubAssignment.objects.create(
                        user=user,
                        club=club,
                        role='advisor'
                    )
                except Club.DoesNotExist:
                    pass
        
        role_display = dict(UserProfile.ROLE_CHOICES).get(role, role)
        messages.success(request, f'成功创建用户账户：{username}（角色：{role_display}）')
        return redirect('clubs:manage_users')
    
    clubs = Club.objects.all().order_by('name')
    return render(request, 'clubs/admin/create_teacher.html', {
        'clubs': clubs,
    })


@login_required(login_url='login')
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
            use_tls = request.POST.get('use_tls', 'on') == 'on'
            
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
    if not _is_staff(request.user) and not _is_admin(request.user):
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
    return redirect('clubs:staff_dashboard')

@login_required(login_url='login')
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


@login_required(login_url='login')
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

@login_required(login_url='login')
@login_required(login_url='login')
def zip_registration_docs(request, registration_id):
    """打包所有注册材料为zip文件并下载"""
    registration = get_object_or_404(ClubRegistration, pk=registration_id)
    
    # 定义权限检查函数
    def check_permission():
        return _is_staff(request.user)
    
    # 定义要打包的材料列表，按顺序
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
    
    # 创建zip文件，使用简化的文件名格式
    zip_filename = f"{registration.club.name}-注册材料.zip"
    
    # 调用通用的zip_materials函数
    return zip_materials(request, registration, materials, zip_filename, check_permission)

@login_required(login_url='login')
def zip_reimbursement_docs(request, reimbursement_id):
    """打包所有报销材料为zip文件并下载"""
    from clubs.models import Reimbursement
    
    reimbursement = get_object_or_404(Reimbursement, pk=reimbursement_id)
    
    # 定义权限检查函数
    def check_permission():
        return _is_staff(request.user) or reimbursement.club.president == request.user
    
    # 定义要打包的材料列表
    materials = []
    if reimbursement.receipt_file:
        materials.append((reimbursement.receipt_file, '1_收据_发票'))
    if reimbursement.proof_document:
        materials.append((reimbursement.proof_document, '2_支持文件'))
    
    if not materials:
        messages.error(request, '该报销记录没有附件')
        return redirect('clubs:staff_dashboard')
    
    # 创建zip文件
    zip_filename = f"{reimbursement.club.name}-报销材料-{reimbursement.id}.zip"
    
    # 调用通用的zip_materials函数
    return zip_materials(request, reimbursement, materials, zip_filename, check_permission)

@login_required(login_url='login')
def zip_president_transition_docs(request, transition_id):
    """打包所有社长变更材料为zip文件并下载"""
    from clubs.models import PresidentTransition
    
    transition = get_object_or_404(PresidentTransition, pk=transition_id)
    
    # 定义权限检查函数
    def check_permission():
        return _is_staff(request.user) or transition.club.president == request.user
    
    # 定义要打包的材料列表
    materials = []
    if transition.transition_form:
        materials.append((transition.transition_form, '1_社长换届申请表'))
    
    if not materials:
        messages.error(request, '该社长变更记录没有附件')
        return redirect('clubs:staff_dashboard')
    
    # 创建zip文件
    zip_filename = f"{transition.club.name}-社长变更材料.zip"
    
    # 调用通用的zip_materials函数
    return zip_materials(request, transition, materials, zip_filename, check_permission)

@login_required(login_url='login')


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


@login_required(login_url='login')
def toggle_registration_enabled(request):
    """
    统一开启/关闭社团注册功能
    - 关闭时：关闭当前活跃的注册周期，禁用所有社团注册
    - 开启时：创建新的注册周期，启用所有社团注册
    """
    # 检查用户权限 - 仅干事和管理员可以操作
    if not _is_staff(request.user) and not _is_admin(request.user):
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
    
    return redirect('clubs:staff_dashboard')


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


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def submit_club_info_change(request, club_id):
    """
    提交社团信息变更申请 - 仅社团社长可用
    """
    # 获取社团对象
    try:
        club = Club.objects.get(pk=club_id)
    except Club.DoesNotExist:
        messages.error(request, '社团不存在')
        return redirect('clubs:user_dashboard')
    
    # 验证权限：只有当前社团社长可以提交信息变更申请
    is_club_president = Officer.objects.filter(
        user_profile__user=request.user,
        club=club,
        position='president',
        is_current=True
    ).exists()
    
    if not is_club_president:
        messages.error(request, '仅社团社长可以提交社团信息变更申请')
        return redirect('clubs:user_dashboard')
    
    if request.method == 'POST':
        new_name = request.POST.get('new_name', '').strip()
        new_description = request.POST.get('new_description', '').strip()
        new_members_count = request.POST.get('new_members_count', '')
        change_reason = request.POST.get('change_reason', '').strip()
        supporting_document = request.FILES.get('supporting_document', None)
        
        # 验证
        errors = []
        
        if not change_reason:
            errors.append('变更原因不能为空')
        
        if new_members_count and not new_members_count.isdigit():
            errors.append('成员数量必须是数字')
        
        # 至少需要修改一项信息
        if not (new_name or new_description or new_members_count):
            errors.append('至少需要修改一项社团信息')
        
        if errors:
            context = {
                'club': club,
                'errors': errors,
                'form_data': request.POST,
            }
            return render(request, 'clubs/user/submit_club_info_change.html', context)
        
        # 重命名支持文档文件
        if supporting_document:
            supporting_document = rename_uploaded_file(supporting_document, club.name, '信息变更', '支持文档')
        
        # 创建社团信息变更申请
        info_change_request = ClubInfoChangeRequest.objects.create(
            club=club,
            new_name=new_name if new_name != club.name else '',
            new_description=new_description if new_description != club.description else '',
            new_members_count=int(new_members_count) if new_members_count else None,
            change_reason=change_reason,
            supporting_document=supporting_document,
            requested_by=request.user,
            status='pending'
        )
        
        messages.success(request, '社团信息变更申请已提交，等待审核')
        return redirect('clubs:user_dashboard')
    
    # GET 请求：显示表单
    context = {
        'club': club,
    }
    return render(request, 'clubs/user/submit_club_info_change.html', context)


@login_required(login_url='login')
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
def submit_president_transition(request, club_id):
    """提交社长换届申请"""
    club = get_object_or_404(Club, pk=club_id)
    
    # 检查用户是否为该社团的社长
    if club.president != request.user:
        messages.error(request, '只有社团社长可以提交换届申请')
        return redirect('clubs:club_detail', club_id=club_id)
    
    if request.method == 'POST':
        # 获取表单数据
        new_president_name = request.POST.get('new_president_name')
        new_president_student_id = request.POST.get('new_president_student_id')
        new_president_phone = request.POST.get('new_president_phone')
        new_president_email = request.POST.get('new_president_email', '')
        transition_date = request.POST.get('transition_date')
        transition_reason = request.POST.get('transition_reason')
        transition_form = request.FILES.get('transition_form')
        meeting_minutes = request.FILES.get('meeting_minutes')
        
        # 验证必填字段
        if not all([new_president_name, new_president_student_id, new_president_phone, 
                   transition_date, transition_reason, transition_form]):
            messages.error(request, '请填写所有必填字段并上传换届申请表')
            return redirect('clubs:submit_president_transition', club_id=club_id)
        
        # 重命名文件
        transition_form = rename_uploaded_file(transition_form, club.name, '换届', '申请表')
        if meeting_minutes:
            meeting_minutes = rename_uploaded_file(meeting_minutes, club.name, '换届', '会议记录')
        
        # 创建换届申请
        transition = PresidentTransition.objects.create(
            club=club,
            old_president=request.user,
            new_president_name=new_president_name,
            new_president_student_id=new_president_student_id,
            new_president_phone=new_president_phone,
            new_president_email=new_president_email,
            transition_date=transition_date,
            transition_reason=transition_reason,
            transition_form=transition_form,
            meeting_minutes=meeting_minutes
        )
        
        messages.success(request, '社长换届申请已提交，等待审核')
        return redirect('clubs:view_president_transitions', club_id=club_id)
    
    # GET 请求
    context = {
        'club': club,
    }
    return render(request, 'clubs/user/submit_president_transition.html', context)


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


@login_required
def review_president_transition(request, transition_id):
    """审核社长换届申请 - 干事和管理员"""
    transition = get_object_or_404(PresidentTransition, pk=transition_id)
    
    # 检查权限
    if not (_is_staff(request.user) or _is_admin(request.user)):
        messages.error(request, '您没有权限审核换届申请')
        return redirect('clubs:index')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        comment = request.POST.get('comment', '')
        
        if action == 'approve':
            transition.status = 'approved'
            transition.reviewer = request.user
            transition.reviewer_comment = comment
            transition.reviewed_at = timezone.now()
            transition.is_read = True  # 换届批准后自动标记为已读，因为结果对原社长是已知的
            transition.save()
            
            # 如果审核通过，可以选择是否自动更新社团社长信息
            # 这里暂时不自动更新，需要管理员手动处理
            
            messages.success(request, f'社长换届申请已批准')
        elif action == 'reject':
            if not comment:
                messages.error(request, '拒绝时必须填写审核意见')
                return redirect('clubs:review_president_transition', transition_id=transition_id)
            
            transition.status = 'rejected'
            transition.reviewer = request.user
            transition.reviewer_comment = comment
            transition.reviewed_at = timezone.now()
            transition.is_read = False  # 拒绝后设为未读，用户需要重新修改提交
            transition.save()
            
            messages.success(request, f'社长换届申请已拒绝')
        
        return redirect('clubs:staff_dashboard')
    
    context = {
        'transition': transition,
    }
    return render(request, 'clubs/staff/review_president_transition.html', context)


# ==================== 活动申请相关视图 ====================

@login_required
def submit_activity_application(request, club_id):
    """提交活动申请"""
    club = get_object_or_404(Club, pk=club_id)
    
    # 检查用户是否为该社团的社长
    if club.president != request.user:
        messages.error(request, '只有社团社长可以提交活动申请')
        return redirect('clubs:club_detail', club_id=club_id)
    
    if request.method == 'POST':
        # 获取表单数据
        activity_name = request.POST.get('activity_name')
        activity_type = request.POST.get('activity_type')
        activity_description = request.POST.get('activity_description')
        activity_date = request.POST.get('activity_date')
        activity_time_start = request.POST.get('activity_time_start')
        activity_time_end = request.POST.get('activity_time_end')
        activity_location = request.POST.get('activity_location')
        expected_participants = request.POST.get('expected_participants')
        budget = request.POST.get('budget', 0)
        contact_person = request.POST.get('contact_person')
        contact_phone = request.POST.get('contact_phone')
        application_form = request.FILES.get('application_form')
        activity_plan = request.FILES.get('activity_plan')
        
        # 验证必填字段
        if not all([activity_name, activity_type, activity_description, activity_date,
                   activity_time_start, activity_time_end, activity_location,
                   expected_participants, contact_person, contact_phone, application_form]):
            messages.error(request, '请填写所有必填字段并上传活动申请表')
            return redirect('clubs:submit_activity_application', club_id=club_id)
        
        # 重命名文件
        application_form = rename_uploaded_file(application_form, club.name, '活动', '申请表')
        if activity_plan:
            activity_plan = rename_uploaded_file(activity_plan, club.name, '活动', '活动计划')
        
        # 创建活动申请
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
            contact_person=contact_person,
            contact_phone=contact_phone,
            application_form=application_form,
            activity_plan=activity_plan
        )
        
        messages.success(request, '活动申请已提交，等待审核')
        return redirect('clubs:view_activity_applications', club_id=club_id)
    
    # GET 请求
    context = {
        'club': club,
    }
    return render(request, 'clubs/user/submit_activity_application.html', context)


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


@login_required
def review_room222_booking(request, booking_id):
    """审核222房间借用申请 - 已废弃，保留用于兼容"""
    messages.info(request, '222房间预约无需审核，已自动生效')
    return redirect('clubs:room222_calendar')


# ==================== 活动申请功能 ====================

@login_required(login_url='login')
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
        application_form = request.FILES.get('application_form')

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
        if not application_form:
            errors.append('活动申请表必须上传')
        
        # 验证预计人数和预算
        try:
            expected_participants = int(expected_participants) if expected_participants else 0
            if expected_participants < 0:
                errors.append('预计参与人数不能为负数')
        except ValueError:
            errors.append('预计参与人数必须是整数')
        
        try:
            budget = float(budget) if budget else 0
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
            }
            return render(request, 'clubs/user/submit_activity_application.html', context)
        
        # 重命名活动申请表文件
        application_form = rename_uploaded_file(application_form, club.name, '活动', '申请表')
        
        # 创建活动申请
        try:
            ActivityApplication.objects.create(
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
                application_form=application_form,
                contact_person=contact_person,
                contact_phone=contact_phone or '无',
                status='pending'
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
    }
    return render(request, 'clubs/user/submit_activity_application.html', context)


@login_required(login_url='login')
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
    
    if request.method == 'POST':
        new_president_officer_id = request.POST.get('new_president_officer_id', '')
        transition_date = request.POST.get('transition_date', '')
        transition_reason = request.POST.get('transition_reason', '').strip()
        transition_form = request.FILES.get('transition_form')
        
        errors = []
        if not new_president_officer_id:
            errors.append('新社长不能为空')
        if not transition_date:
            errors.append('换届日期不能为空')
        if not transition_reason:
            errors.append('换届原因不能为空')
        if not transition_form:
            errors.append('社团主要负责人变动申请表必须上传')
        
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
            context = {
                'club': club,
                'errors': errors,
                'club_officers': Officer.objects.filter(club=club, is_current=True),
                'transition_date': transition_date,
                'transition_reason': transition_reason,
            }
            return render(request, 'clubs/user/submit_president_transition.html', context)
        
        # 重命名换届申请表文件
        transition_form = rename_uploaded_file(transition_form, club.name, '换届', '申请表')
        
        # 创建社长换届申请
        try:
            PresidentTransition.objects.create(
                club=club,
                old_president=request.user,
                new_president_officer=new_president_officer,
                transition_date=transition_date,
                transition_reason=transition_reason,
                transition_form=transition_form,
                status='pending'
            )
            messages.success(request, '社长换届申请已提交，等待审核')
            return redirect('clubs:user_dashboard')
        except Exception as e:
            messages.error(request, f'提交失败: {str(e)}')
            return redirect('clubs:submit_president_transition', club_id=club_id)
    
    # GET请求 - 显示表单
    club_officers = Officer.objects.filter(position='president', is_current=True).exclude(user_profile__user=request.user)
    context = {
        'club': club,
        'club_officers': club_officers,
    }
    return render(request, 'clubs/user/submit_president_transition.html', context)


# ==================== 审核活动申请和社长换届 ====================

@login_required(login_url='login')
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
            # 根据老师审核状态显示不同消息
            if activity.teacher_approved is True:
                messages.success(request, '活动申请已批准（老师也已批准，活动审核通过）')
            elif activity.teacher_approved is False:
                messages.warning(request, '活动申请已批准，但老师已拒绝此申请')
            else:
                messages.success(request, '活动申请已批准（等待老师审核）')
        elif action == 'reject':
            activity.staff_approved = False
            activity.staff_reviewer = request.user
            activity.staff_comment = comment
            activity.staff_reviewed_at = timezone.now()
            activity.update_status()
            messages.success(request, '活动申请已拒绝')
        else:
            messages.error(request, '无效的审核操作')
        
        return redirect('clubs:staff_dashboard')
    
    context = {
        'activity': activity,
        'club': activity.club,
    }
    return render(request, 'clubs/staff/review_activity_application.html', context)


@login_required(login_url='login')
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
    
    context = {
        'transition': transition,
        'club': transition.club,
    }
    return render(request, 'clubs/staff/review_president_transition.html', context)


@login_required(login_url='login')
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
        
    elif review_type == 'club_info_change':
        # 社团信息修改审核历史
        changes = ClubInfoChangeRequest.objects.exclude(status='pending').order_by('-reviewed_at')
        context['title'] = '社团信息修改审核历史'
        context['items'] = changes
        context['item_type'] = 'club_info_change'
        
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
    
    return render(request, 'clubs/staff/review_history.html', context)


@login_required(login_url='login')
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
        context['reviews'] = []
        
    elif item_type == 'info_change':
        item = get_object_or_404(ClubInfoChangeRequest, pk=item_id)
        context['title'] = f'{item.club.name} - 社团信息修改'
        context['item'] = item
        context['reviews'] = ClubInfoChangeReview.objects.filter(change_request=item).order_by('-reviewed_at')
        
    elif item_type == 'reimbursement':
        item = get_object_or_404(Reimbursement, pk=item_id)
        context['title'] = f'{item.club.name} - 报销申请'
        context['item'] = item
        context['reviews'] = SubmissionReview.objects.filter(reimbursement=item).order_by('-reviewed_at')
        
    elif item_type == 'activity_application':
        item = get_object_or_404(ActivityApplication, pk=item_id)
        context['title'] = f'{item.club.name} - 活动申请'
        context['item'] = item
        # ActivityApplication doesn't have a separate review model; build reviews list from fields
        from types import SimpleNamespace
        reviews = []
        # staff review
        if item.staff_approved is not None or item.staff_reviewer or item.staff_reviewed_at:
            staff_status = 'approved' if item.staff_approved is True else 'rejected' if item.staff_approved is False else 'pending'
            reviews.append(SimpleNamespace(reviewer=item.staff_reviewer, status=staff_status, comment=item.staff_comment, reviewed_at=item.staff_reviewed_at))
        # teacher review
        if item.teacher_approved is not None or item.teacher_reviewer or item.teacher_reviewed_at:
            teacher_status = 'approved' if item.teacher_approved is True else 'rejected' if item.teacher_approved is False else 'pending'
            reviews.append(SimpleNamespace(reviewer=item.teacher_reviewer, status=teacher_status, comment=item.teacher_comment, reviewed_at=item.teacher_reviewed_at))
        # general reviewer (legacy field)
        if getattr(item, 'reviewer', None) or getattr(item, 'reviewed_at', None):
            legacy_status = 'approved' if item.status == 'approved' else 'rejected' if item.status == 'rejected' else 'pending'
            reviews.append(SimpleNamespace(reviewer=item.reviewer, status=legacy_status, comment=getattr(item, 'reviewer_comment', '') or '', reviewed_at=item.reviewed_at))
        context['reviews'] = sorted(reviews, key=lambda r: r.reviewed_at or timezone.make_aware(timezone.datetime.min), reverse=True)
        
    elif item_type == 'president_transition':
        item = get_object_or_404(PresidentTransition, pk=item_id)
        context['title'] = f'{item.club.name} - 社长换届'
        context['item'] = item
        context['reviews'] = SubmissionReview.objects.filter(president_transition=item).order_by('-reviewed_at')
    
    else:
        messages.error(request, '无效的项目类型')
        return redirect('clubs:staff_dashboard')
    
    context['item_type'] = item_type
    return render(request, 'clubs/staff/review_detail.html', context)


def public_activities(request):
    """
    公共活动列表页面 - 所有人都可以访问
    显示所有已审批通过的活动（需要干事和老师都同意）
    教师只能看自己负责的社团的活动
    """
    # 获取所有已批准且未过期的活动
    from datetime import datetime, time
    current_datetime = timezone.now()
    
    approved_activities = ActivityApplication.objects.filter(
        status='approved'
    ).exclude(
        # 排除已过期的活动（活动日期小于今天，或活动日期是今天但结束时间已过）
        Q(activity_date__lt=current_datetime.date()) |
        Q(activity_date=current_datetime.date(), activity_time_end__lt=current_datetime.time())
    ).order_by('activity_date', 'activity_time_start')
    
    # 初始化教师相关变量
    user_assigned_clubs = []
    
    # 如果是教师，只显示自己负责的社团的活动
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role == 'teacher':
        from .models import TeacherClubAssignment
        assigned_clubs = Club.objects.filter(
            assigned_teachers__user=request.user
        ).distinct()
        approved_activities = approved_activities.filter(club__in=assigned_clubs)
        user_assigned_clubs = list(assigned_clubs.values_list('id', flat=True))
    
    # 分类活动
    activities_by_type = {}
    for activity in approved_activities:
        activity_type = activity.get_activity_type_display()
        if activity_type not in activities_by_type:
            activities_by_type[activity_type] = []
        activities_by_type[activity_type].append(activity)
    
    context = {
        'approved_activities': approved_activities,
        'activities_by_type': activities_by_type,
        'user_assigned_clubs': user_assigned_clubs,  # 传递教师的负责社团 ID
    }
    return render(request, 'clubs/public_activities.html', context)


@login_required
def join_activity(request, activity_id):
    """
    参加活动视图 - 所有认证用户都可以申请参加活动
    对干事、社长、普通用户开放
    """
    activity = get_object_or_404(ActivityApplication, pk=activity_id)
    
    # 检查用户是否已经申请过此活动
    existing = ActivityParticipation.objects.filter(activity=activity, user=request.user).first()
    if existing:
        messages.warning(request, '您已经申请过此活动')
        return redirect('clubs:public_activities')
    
    try:
        # 创建参加活动记录 - 默认为已批准（对所有人开放）
        participation = ActivityParticipation.objects.create(
            activity=activity,
            user=request.user,
            status='approved',
            approved_at=timezone.now()
        )
        messages.success(request, f'成功申请参加《{activity.activity_name}》活动')
    except Exception as e:
        messages.error(request, f'申请失败: {str(e)}')
    
    return redirect('clubs:public_activities')


@login_required
def my_activities(request):
    """
    我的活动 - 显示当前用户已参加的所有活动
    """
    participations = ActivityParticipation.objects.filter(
        user=request.user,
        activity__activity_date__gte=timezone.now().date()
    ).select_related('activity', 'activity__club').order_by('activity__activity_date')
    
    context = {
        'participations': participations,
        'title': '我的活动',
    }
    return render(request, 'clubs/my_activities.html', context)


@login_required
def activity_participants(request, activity_id):
    """
    查看活动报名名单
    - 管理员可以看所有活动的报名名单
    - 干事和老师可以看所有活动的报名名单
    - 社长只能看自己社团的活动报名名单
    """
    activity = get_object_or_404(ActivityApplication, pk=activity_id)
    user_profile = request.user.profile if hasattr(request.user, 'profile') else None
    
    # 权限检查
    is_admin = user_profile and user_profile.role == 'admin'
    is_staff = user_profile and user_profile.role == 'staff'
    is_teacher = user_profile and user_profile.role == 'teacher'
    is_president = request.user == activity.club.president
    
    # 权限限制：只有管理员、干事、老师和该社团的社长才能查看
    if not (is_admin or is_staff or is_teacher or is_president):
        messages.error(request, '您没有权限查看此活动的报名名单')
        return redirect('clubs:public_activities')
    
    # 社长只能查看自己社团的活动
    if is_president and not is_admin and not is_staff and not is_teacher:
        if activity.club.president != request.user:
            messages.error(request, '您只能查看自己社团的活动报名名单')
            return redirect('clubs:public_activities')
    
    # 获取报名名单
    participants = ActivityParticipation.objects.filter(
        activity=activity,
        status='approved'
    ).select_related('user', 'user__profile').order_by('-approved_at')
    
    context = {
        'activity': activity,
        'participants': participants,
        'participant_count': participants.count(),
    }
    return render(request, 'clubs/activity_participants.html', context)


@login_required
def teacher_dashboard(request):
    """
    教师仪表板 - 显示我的社团和待审核的活动申请
    """
    # 检查是否是教师
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'teacher':
        messages.error(request, '您没有权限访问此页面')
        return redirect('clubs:index')
    
    # 获取该教师负责的社团
    from .models import TeacherClubAssignment
    assigned_clubs = Club.objects.filter(
        assigned_teachers__user=request.user
    ).distinct()
    
    # 获取这些社团的待审核活动申请（只显示需要老师审核且干事未拒绝的）
    pending_activities = ActivityApplication.objects.filter(
        club__in=assigned_clubs,
        teacher_approved__isnull=True,  # 老师还未审核
        staff_approved__isnull=True     # 干事也还未拒绝
    ).order_by('-submitted_at')
    
    context = {
        'assigned_clubs': assigned_clubs,
        'pending_activities': pending_activities,
    }
    return render(request, 'clubs/teacher/dashboard.html', context)


@login_required
def teacher_review_activity(request, activity_id):
    """
    教师审核活动申请
    """
    # 检查是否是教师
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'teacher':
        messages.error(request, '您没有权限访问此页面')
        return redirect('clubs:index')
    
    activity = get_object_or_404(ActivityApplication, id=activity_id)
    
    # 检查教师是否负责该社团
    from .models import TeacherClubAssignment
    if not TeacherClubAssignment.objects.filter(user=request.user, club=activity.club).exists():
        messages.error(request, '您没有权限审核此活动')
        return redirect('clubs:teacher_dashboard')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        comment = request.POST.get('comment', '')
        
        if action == 'approve':
            activity.teacher_approved = True
            activity.teacher_reviewer = request.user
            activity.teacher_comment = comment
            activity.teacher_reviewed_at = timezone.now()
            activity.update_status()
            messages.success(request, '活动申请已批准')
        elif action == 'reject':
            activity.teacher_approved = False
            activity.teacher_reviewer = request.user
            activity.teacher_comment = comment
            activity.teacher_reviewed_at = timezone.now()
            activity.update_status()
            messages.success(request, '活动申请已拒绝')
        
        return redirect('clubs:teacher_dashboard')
    
    context = {
        'activity': activity,
    }
    return render(request, 'clubs/teacher/review_activity.html', context)


@login_required
def teacher_review_history(request):
    """
    教师审核历史记录
    """
    # 检查是否是教师
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'teacher':
        messages.error(request, '您没有权限访问此页面')
        return redirect('clubs:index')
    
    # 获取该教师负责的社团
    from .models import TeacherClubAssignment
    assigned_clubs = Club.objects.filter(
        assigned_teachers__user=request.user
    ).distinct()
    
    # 获取已审核的活动申请
    reviewed_activities = ActivityApplication.objects.filter(
        club__in=assigned_clubs,
        teacher_approved__isnull=False  # 老师已审核
    ).order_by('-teacher_reviewed_at')
    
    context = {
        'reviewed_activities': reviewed_activities,
        'assigned_clubs': assigned_clubs,
    }
    return render(request, 'clubs/teacher/review_history.html', context)


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
    elif user_role == 'teacher':
        # 检查是否是负责该社团的老师
        from .models import TeacherClubAssignment
        has_permission = TeacherClubAssignment.objects.filter(
            user=request.user, 
            club=activity.club
        ).exists()
    
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
