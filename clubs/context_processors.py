from django.db.models import Q
from .models import ReviewSubmission, ClubRegistration, ClubRegistrationRequest, Reimbursement, Officer


def unread_approvals(request):
    """为所有页面提供未读审核数量"""
    context = {
        'unread_approval_counts': {
            'total': 0,
            'annual_review': 0,
            'registration': 0,
            'application': 0,
            'reimbursement': 0,
        }
    }
    
    if not request.user.is_authenticated:
        return context
    
    # 检查用户是否是社长
    try:
        is_president = request.user.profile.role == 'president' and Officer.objects.filter(
            user_profile=request.user.profile,
            position='president',
            is_current=True
        ).exists()
    except:
        return context
    
    if not is_president:
        return context
    
    # 获取当前用户作为社长的所有社团
    clubs = Officer.objects.filter(
        user_profile=request.user.profile,
        position='president',
        is_current=True
    ).values_list('club', flat=True)
    
    # 统计各类型的待审核/已拒绝数量
    annual_review_count = ReviewSubmission.objects.filter(
        club__in=clubs,
        status__in=['pending', 'rejected']
    ).count()
    
    registration_count = ClubRegistration.objects.filter(
        club__in=clubs,
        status__in=['pending', 'rejected', 'partially_rejected']
    ).count()
    
    application_count = ClubRegistrationRequest.objects.filter(
        requested_by=request.user,
        status__in=['pending', 'rejected']
    ).count()
    
    reimbursement_count = Reimbursement.objects.filter(
        club__in=clubs,
        status__in=['pending', 'rejected']
    ).count()
    
    total_count = annual_review_count + registration_count + application_count + reimbursement_count
    
    context['unread_approval_counts'] = {
        'total': total_count,
        'annual_review': annual_review_count,
        'registration': registration_count,
        'application': application_count,
        'reimbursement': reimbursement_count,
    }
    
    return context
