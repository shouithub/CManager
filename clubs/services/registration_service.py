"""Transactional registration-token operations."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from clubs.models import ClubMember, RegistrationToken, UserProfile


class RegistrationTokenUnavailable(ValidationError):
    """Raised when a registration token cannot be consumed."""


@transaction.atomic
def register_member_with_token(*, token_id, user, existing_account, username,
                               password, email, profile_data):
    """Create/bind a member and consume the token as one atomic operation."""
    token = RegistrationToken.objects.select_for_update().select_related('club').get(pk=token_id)
    if not token.can_use():
        raise RegistrationTokenUnavailable('注册链接已失效（已使用或已过期）')

    if user is None:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=profile_data['real_name'],
        )

    profile, _created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'role': 'member',
            'status': 'approved',
            'account_status': 'active',
            **profile_data,
        },
    )

    if not existing_account:
        profile.role = 'member'
        profile.status = 'approved'
        profile.account_status = 'active'
        for field, value in profile_data.items():
            setattr(profile, field, value)
        profile.save()

        user.email = email
        user.first_name = profile_data['real_name']
        user.save(update_fields=['email', 'first_name'])

    ClubMember.objects.get_or_create(
        club=token.club,
        user_profile=profile,
        defaults={'status': 'active'},
    )
    token.mark_used()
    return user, token
