from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from .models import Officer, UserProfile


IDENTITY_SESSION_KEY = 'active_identity'
IDENTITY_PRIMARY = 'primary'
IDENTITY_PRESIDENT = 'president'


def _profile(user):
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return None
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return None


def get_primary_role(user) -> str:
    profile = _profile(user)
    return profile.role if profile else ''


def get_primary_role_label(user) -> str:
    role = get_primary_role(user)
    return dict(UserProfile.ROLE_CHOICES).get(role, role or '访客')


def has_president_officer(user) -> bool:
    profile = _profile(user)
    if not profile:
        return False
    return Officer.objects.filter(
        user_profile=profile,
        position='president',
        is_current=True,
    ).exists()


def president_club_count(user) -> int:
    profile = _profile(user)
    if not profile:
        return 0
    return Officer.objects.filter(
        user_profile=profile,
        position='president',
        is_current=True,
    ).values('club_id').distinct().count()


def get_active_identity(request) -> str:
    user = getattr(request, 'user', None)
    role = get_primary_role(user)
    if role == IDENTITY_PRESIDENT:
        request.session.pop(IDENTITY_SESSION_KEY, None)
        return IDENTITY_PRESIDENT

    requested = request.session.get(IDENTITY_SESSION_KEY, IDENTITY_PRIMARY)
    if requested == IDENTITY_PRESIDENT:
        if has_president_officer(user):
            return IDENTITY_PRESIDENT
        request.session.pop(IDENTITY_SESSION_KEY, None)
        return IDENTITY_PRIMARY
    if requested != IDENTITY_PRIMARY:
        request.session.pop(IDENTITY_SESSION_KEY, None)
    return IDENTITY_PRIMARY


def is_president_mode(request) -> bool:
    user = getattr(request, 'user', None)
    if get_active_identity(request) != IDENTITY_PRESIDENT:
        return False
    return get_primary_role(user) == IDENTITY_PRESIDENT or has_president_officer(user)


def available_identities(request) -> list[dict[str, object]]:
    user = getattr(request, 'user', None)
    role = get_primary_role(user)
    if not role:
        return []

    identities = []
    if role != IDENTITY_PRESIDENT:
        identities.append({
            'key': IDENTITY_PRIMARY,
            'label': get_primary_role_label(user),
            'description': '主身份',
        })
        if has_president_officer(user):
            identities.append({
                'key': IDENTITY_PRESIDENT,
                'label': '社长',
                'description': f'管理 {president_club_count(user)} 个社团',
            })
    else:
        identities.append({
            'key': IDENTITY_PRESIDENT,
            'label': '社长',
            'description': '主身份',
        })
    return identities


def active_identity_label(request) -> str:
    identity = get_active_identity(request)
    if identity == IDENTITY_PRESIDENT:
        return '社长'
    return get_primary_role_label(getattr(request, 'user', None))
