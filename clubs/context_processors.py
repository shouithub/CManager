"""上下文处理器，用于在所有模板中提供全局变量"""
import os
from django.conf import settings
from django.core.cache import cache
from .models import (
    ReviewSubmission, 
    ClubRegistration, 
    ClubRegistrationRequest, 
    Reimbursement, 
    ActivityApplication, 
    PresidentTransition,
    Officer
)


def _get_president_club_ids(user):
    """获取社长可访问社团ID（通过 Officer 表查询）。"""
    return list(Officer.objects.filter(
        user_profile__user=user,
        position='president',
        is_current=True
    ).values_list('club_id', flat=True))


def site_settings(request):
    """全局站点设置，如favicon和字体"""
    base_media_url = f"/{settings.MEDIA_URL.lstrip('/')}"
    if not base_media_url.endswith('/'):
        base_media_url = f"{base_media_url}/"
    favicon_path = os.path.join(settings.MEDIA_ROOT, 'site', 'favicon.ico')
    favicon_preview_path = os.path.join(settings.MEDIA_ROOT, 'site', 'favicon.png')
    import time
    cache_buster = int(time.time())
    if os.path.exists(favicon_path):
        site_favicon_url = f"{base_media_url}site/favicon.ico?v={cache_buster}"
    else:
        site_favicon_url = None
    if os.path.exists(favicon_preview_path):
        site_favicon_preview_url = f"{base_media_url}site/favicon.png?v={cache_buster}"
    else:
        site_favicon_preview_url = None

    # 字体设置
    try:
        from .models import SiteSettings
        font_cfg = SiteSettings.get_settings()
        font_icon_url = font_cfg.font_icon_url or 'https://fonts.font.im/icon?family=Material+Icons'
        body_font_url = font_cfg.body_font_url or ''
        body_font_family = font_cfg.body_font_family or ''
    except Exception:
        font_icon_url = 'https://fonts.font.im/icon?family=Material+Icons'
        body_font_url = ''
        body_font_family = ''

    return {
        'site_favicon_url': site_favicon_url,
        'site_favicon_preview_url': site_favicon_preview_url,
        'font_icon_url': font_icon_url,
        'body_font_url': body_font_url,
        'body_font_family': body_font_family,
    }


def audit_center_counts(request):
    """为审核中心菜单项提供待审核申请的数目"""
    empty_result = {
        'audit_center_counts': {
            'annual_review': 0,
            'registration': 0,
            'application': 0,
            'reimbursement': 0,
            'activity_application': 0,
            'president_transition': 0,
        },
        'unread_approval_counts': {
            'annual_review': 0,
            'registration': 0,
            'application': 0,
            'reimbursement': 0,
            'activity': 0,
            'transition': 0,
            'total': 0
        }
    }

    if not request.user.is_authenticated:
        return empty_result
    
    # 检查用户是否为干事或管理员
    try:
        user_role = request.user.profile.role
        is_staff_or_admin = user_role in ['staff', 'admin']
        is_president = user_role == 'president'
    except:
        is_staff_or_admin = False
        is_president = False

    cache_key = f"audit_center_counts:{request.user.id}:{user_role if 'user_role' in locals() else 'unknown'}:{int(request.user.is_superuser)}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # 计算干事端审核中心数量
    if is_staff_or_admin or request.user.is_superuser:
        audit_counts = {
            'annual_review': ReviewSubmission.objects.filter(status='pending').count(),
            'registration': ClubRegistration.objects.filter(status='pending').count(),
            'application': ClubRegistrationRequest.objects.filter(status='pending').count(),
            'reimbursement': Reimbursement.objects.filter(status='pending').count(),
            'activity_application': ActivityApplication.objects.filter(staff_approved__isnull=True).count(),
            'president_transition': PresidentTransition.objects.filter(status='pending').count(),
        }
    else:
        audit_counts = {
            'annual_review': 0,
            'registration': 0,
            'application': 0,
            'reimbursement': 0,
            'activity_application': 0,
            'president_transition': 0,
        }
    
    # 计算社长端审批中心数量
    if is_president:
        try:
            president_clubs = _get_president_club_ids(request.user)
            
            annual_review_count = ReviewSubmission.objects.filter(
                club__in=president_clubs, 
                status__in=['pending', 'rejected']
            ).count()
            registration_count = ClubRegistration.objects.filter(
                club__in=president_clubs, 
                status__in=['pending', 'rejected']
            ).count()
            application_count = ClubRegistrationRequest.objects.filter(
                requested_by=request.user, 
                status__in=['pending', 'rejected']
            ).count()
            reimbursement_count = Reimbursement.objects.filter(
                club__in=president_clubs, 
                status__in=['pending', 'rejected', 'partially_rejected']
            ).count()
            activity_count = ActivityApplication.objects.filter(
                club__in=president_clubs, 
                status__in=['pending', 'rejected']
            ).count()
            transition_count = PresidentTransition.objects.filter(
                club__in=president_clubs, 
                status__in=['pending', 'rejected']
            ).count()
            
            approval_counts = {
                'annual_review': annual_review_count,
                'registration': registration_count,
                'application': application_count,
                'reimbursement': reimbursement_count,
                'activity': activity_count,
                'transition': transition_count,
                'total': annual_review_count + registration_count + application_count + reimbursement_count + activity_count + transition_count
            }
        except:
            approval_counts = {
                'annual_review': 0,
                'registration': 0,
                'application': 0,
                'reimbursement': 0,
                'activity': 0,
                'transition': 0,
                'total': 0
            }
    else:
        approval_counts = {
            'annual_review': 0,
            'registration': 0,
            'application': 0,
            'reimbursement': 0,
            'activity': 0,
            'transition': 0,
            'total': 0
        }

    result = {
        'audit_center_counts': audit_counts,
        'unread_approval_counts': approval_counts
    }

    cache.set(cache_key, result, timeout=10)
    return result


def unread_approvals(request):
    """兼容旧的上下文处理器名，返回审核/审批相关计数"""
    return audit_center_counts(request)
