from datetime import timedelta
import logging

from django.utils import timezone

from .email_utils import send_inactive_account_notice
from .models import InactiveExtensionHistory

logger = logging.getLogger(__name__)


def mark_profile_inactive(profile, reason='system'):
    """将账户转为不活跃，并在可用时发送邮件提醒。"""
    if profile.role == 'admin':
        return False

    now = timezone.now()
    profile.account_status = 'inactive'
    profile.inactive_since = now
    profile.save(update_fields=['account_status', 'inactive_since', 'updated_at'])

    auto_delete_at = now + timedelta(days=365)
    try:
        send_inactive_account_notice(
            user=profile.user,
            inactive_since=now,
            auto_delete_at=auto_delete_at,
            reason=reason,
        )
    except Exception as exc:
        logger.warning('发送不活跃通知邮件失败 user_id=%s error=%s', profile.user_id, exc)

    return True


def extend_inactive_account(profile, days=365, reason='user_extend'):
    """用户主动延期注销：恢复为活跃，并把活跃截止时间顺延。"""
    now = timezone.now()
    previous_until = profile.active_until
    base = previous_until if previous_until and previous_until > now else now
    new_until = base + timedelta(days=days)

    profile.account_status = 'active'
    profile.inactive_since = None
    profile.active_until = new_until
    profile.save(update_fields=['account_status', 'inactive_since', 'active_until', 'updated_at'])

    InactiveExtensionHistory.objects.create(
        user_profile=profile,
        previous_active_until=previous_until,
        new_active_until=new_until,
        reason=reason,
    )

    return new_until
