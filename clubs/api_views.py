from django.http import JsonResponse
from .models import (
    ReviewSubmission, 
    ClubRegistration, 
    Reimbursement, 
    ClubRegistrationRequest, 
    ActivityApplication, 
    PresidentTransition,
    UserProfile
)

def _is_staff(user):
    """Check if user is staff"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'staff'
    except UserProfile.DoesNotExist:
        return False

def _is_admin(user):
    """Check if user is admin"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'admin'
    except UserProfile.DoesNotExist:
        return False

def api_staff_review_history(request, review_type):
    """API endpoint to fetch review history for modal"""
    if not _is_staff(request.user) and not _is_admin(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    items_data = []
    
    if review_type == 'submission':
        submissions = ReviewSubmission.objects.exclude(status='pending').order_by('-reviewed_at')
        for item in submissions:
            items_data.append({
                'id': item.id,
                'title': item.club.name,
                'status': item.status,
                'date': item.submission_year,
                'meta': item.submission_year,
                'type': 'annual_review'
            })
            
    elif review_type == 'club_registration':
        registrations = ClubRegistration.objects.exclude(status='pending').order_by('-reviewed_at')
        for item in registrations:
            items_data.append({
                'id': item.id,
                'title': item.club.name,
                'status': item.status,
                'date': item.submitted_at.strftime('%Y-%m-%d') if item.submitted_at else '',
                'meta': item.submitted_at.strftime('%m-%d') if item.submitted_at else '',
                'type': 'registration'
            })
            
    elif review_type == 'reimbursement':
        reimbursements = Reimbursement.objects.exclude(status='pending').order_by('-reviewed_at')
        for item in reimbursements:
            items_data.append({
                'id': item.id,
                'title': item.club.name,
                'status': item.status,
                'date': item.submitted_at.strftime('%Y-%m-%d') if item.submitted_at else '',
                'meta': f'¥{item.reimbursement_amount:.2f}',
                'type': 'reimbursement'
            })
            
    elif review_type == 'club_application':
        applications = ClubRegistrationRequest.objects.exclude(status='pending').order_by('-reviewed_at')
        for item in applications:
            items_data.append({
                'id': item.id,
                'title': item.club_name,
                'status': item.status,
                'date': item.submitted_at.strftime('%Y-%m-%d') if item.submitted_at else '',
                'meta': item.submitted_at.strftime('%m-%d') if item.submitted_at else '',
                'type': 'application'
            })

    elif review_type == 'activity_application':
        activities = ActivityApplication.objects.exclude(status='pending').order_by('-reviewed_at')
        for item in activities:
            status = 'pending'
            if item.staff_approved: status = 'approved'
            elif item.staff_approved == False: status = 'rejected'
            
            items_data.append({
                'id': item.id,
                'title': item.activity_name,
                'status': status,
                'date': item.activity_date.strftime('%Y-%m-%d') if item.activity_date else '',
                'meta': item.activity_date.strftime('%m-%d') if item.activity_date else '',
                'type': 'activity_application'
            })
            
    elif review_type == 'president_transition':
        transitions = PresidentTransition.objects.exclude(status='pending').order_by('-reviewed_at')
        for item in transitions:
            items_data.append({
                'id': item.id,
                'title': item.club.name,
                'status': item.status,
                'date': item.created_at.strftime('%Y-%m-%d') if item.created_at else '',
                'meta': item.new_president_name,
                'type': 'president_transition'
            })
            
    return JsonResponse({'items': items_data})
