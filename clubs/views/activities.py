"""Published activity browsing and member registration views."""

from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ..identity import is_president_mode
from ..models import ActivityRegistration, Club, ClubMember, PublishedActivity
from ..permissions import president_club_ids, roles_required, user_role


@roles_required('staff', 'admin', 'president', 'member')
def public_activities(request):
    """Filter in SQL and paginate so the page never loads every activity."""
    role = user_role(request.user)
    queryset = PublishedActivity.objects.select_related('club', 'source_submission').order_by('-published_at')
    if is_president_mode(request):
        queryset = queryset.filter(club_id__in=president_club_ids(request.user))
    elif role == 'member':
        member_club_ids = ClubMember.objects.filter(
            user_profile__user=request.user,
            status='active',
        ).values_list('club_id', flat=True)
        queryset = queryset.filter(Q(club_id__in=member_club_ids) | Q(is_public=True)).distinct()

    search_query = request.GET.get('search', '').strip()
    activity_type_filter = request.GET.get('activity_type', '').strip()
    club_filter = request.GET.get('club', '').strip()
    date_filter = request.GET.get('date', '').strip()
    if search_query:
        queryset = queryset.filter(Q(activity_name__icontains=search_query) | Q(club__name__icontains=search_query))
    if activity_type_filter:
        queryset = queryset.filter(activity_type=activity_type_filter)
    if club_filter:
        queryset = queryset.filter(club__name__icontains=club_filter)
    if date_filter:
        try:
            queryset = queryset.filter(activity_date=date.fromisoformat(date_filter))
        except ValueError:
            messages.warning(request, '日期筛选格式无效，已忽略')
            date_filter = ''

    page = Paginator(queryset, 36).get_page(request.GET.get('page'))
    activities_by_type = defaultdict(list)
    for activity in page.object_list:
        activities_by_type[activity.get_activity_type_display()].append(activity)

    registered_ids = set()
    if role == 'member':
        registered_ids = set(ActivityRegistration.objects.filter(
            user_profile__user=request.user,
            activity_id__in=[activity.pk for activity in page.object_list],
        ).values_list('activity_id', flat=True))

    return render(request, 'clubs/public_activities.html', {
        'approved_activities': page.object_list,
        'page_obj': page,
        'activities_by_type': dict(activities_by_type),
        'all_clubs': Club.objects.only('id', 'name').order_by('name'),
        'activity_type_choices': PublishedActivity.ACTIVITY_TYPE_CHOICES,
        'club_filter': club_filter,
        'activity_type_filter': activity_type_filter,
        'date_filter': date_filter,
        'search_query': search_query,
        'user_registered_ids': registered_ids,
    })


@require_POST
@roles_required('member', json_response=True)
def register_activity(request, activity_id):
    activity = get_object_or_404(PublishedActivity.objects.select_related('club'), pk=activity_id)
    if not activity.is_public and not ClubMember.objects.filter(
        user_profile=request.user.profile,
        club=activity.club,
        status='active',
    ).exists():
        return JsonResponse({'success': False, 'error': '您不是该社团成员，无法报名'}, status=403)
    _, created = ActivityRegistration.objects.get_or_create(activity=activity, user_profile=request.user.profile)
    if created:
        return JsonResponse({'success': True, 'registered': True})
    return JsonResponse({'success': False, 'error': '您已报名该活动'})


@require_POST
@roles_required('member', json_response=True)
def unregister_activity(request, activity_id):
    deleted, _ = ActivityRegistration.objects.filter(
        activity_id=activity_id,
        user_profile=request.user.profile,
    ).delete()
    if deleted:
        return JsonResponse({'success': True, 'registered': False})
    return JsonResponse({'success': False, 'error': '您尚未报名该活动'})
