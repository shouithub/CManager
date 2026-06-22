from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import FormSubmission, UserProfile


def _is_staff(user):
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'staff'
    except UserProfile.DoesNotExist:
        return False


def _is_admin(user):
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'admin'
    except UserProfile.DoesNotExist:
        return False


@require_GET
def api_staff_review_history(request, review_type):
    if not _is_staff(request.user) and not _is_admin(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    slug = review_type.replace('_', '-')
    aliases = {
        'submission': 'annual-review',
        'annual-review': 'annual-review',
        'club-registration': 'registration',
        'club-application': 'application',
    }
    slug = aliases.get(slug, slug)
    items = FormSubmission.objects.exclude(status='pending').select_related('channel', 'club').order_by('-reviewed_at', '-submitted_at')
    if slug:
        items = items.filter(channel__slug=slug)

    data = []
    for item in items[:200]:
        data.append({
            'id': item.id,
            'title': item.display_title,
            'status': item.status,
            'date': item.submitted_at.strftime('%Y-%m-%d') if item.submitted_at else '',
            'meta': item.club.name,
            'type': item.channel.slug,
        })
    return JsonResponse({'items': data})
