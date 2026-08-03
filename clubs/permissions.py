"""Central role-based access checks and decorators."""

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import redirect


def user_role(user):
    if not getattr(user, 'is_authenticated', False):
        return None
    if getattr(user, 'is_superuser', False):
        return 'admin'
    return getattr(getattr(user, 'profile', None), 'role', None)


def has_any_role(user, *roles):
    return user_role(user) in roles


def president_club_ids(user):
    """Return current club IDs led by the user from the single Officer source."""
    if not getattr(user, 'is_authenticated', False):
        return []
    from .models import Officer
    return Officer.objects.filter(
        user_profile__user=user,
        position='president',
        is_current=True,
    ).values_list('club_id', flat=True)


def is_president_of_club(user, club):
    if not getattr(user, 'is_authenticated', False):
        return False
    from .models import Officer
    return Officer.objects.filter(
        user_profile__user=user,
        club=club,
        position='president',
        is_current=True,
    ).exists()


def roles_required(*roles, json_response=False):
    """Require authentication and one of the supplied application roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if json_response:
                    return JsonResponse({'error': '请先登录'}, status=401)
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
            if not has_any_role(request.user, *roles):
                if json_response:
                    return JsonResponse({'error': '权限不足'}, status=403)
                messages.error(request, '权限不足')
                return redirect('clubs:index')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
