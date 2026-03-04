import json
import logging
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db.utils import OperationalError, ProgrammingError

from .models import SMTPConfig, UserProfile


logger = logging.getLogger(__name__)


def _pending_file_path() -> Path:
    return Path(settings.BASE_DIR) / '.oobe_pending.json'


def has_pending_oobe_setup() -> bool:
    return _pending_file_path().exists()


def write_pending_oobe_setup(payload: dict):
    file_path = _pending_file_path()
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def has_admin_user() -> bool:
    try:
        return UserProfile.objects.filter(role='admin').exists()
    except (OperationalError, ProgrammingError):
        return False
    except Exception:
        return False


def apply_pending_oobe_setup() -> bool:
    file_path = _pending_file_path()
    if not file_path.exists():
        return True

    try:
        if UserProfile.objects.filter(role='admin').exists():
            file_path.unlink(missing_ok=True)
            return True
    except (OperationalError, ProgrammingError):
        return False

    try:
        payload = json.loads(file_path.read_text(encoding='utf-8'))

        admin = payload.get('admin') or {}
        username = (admin.get('username') or '').strip()
        password = admin.get('password') or ''
        email = (admin.get('email') or '').strip()
        if not username or not password:
            return False

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
            }
        )

        if created:
            user.set_password(password)
        else:
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            if not user.has_usable_password():
                user.set_password(password)
        user.save()

        profile_defaults = {
            'role': 'admin',
            'status': 'approved',
            'real_name': username,
            'student_id': f'ADMIN_{username}',
            'phone': '',
            'wechat': '',
            'political_status': 'non_member',
            'must_change_password': False,
        }
        profile, profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults=profile_defaults,
        )
        if not profile_created:
            for key, value in profile_defaults.items():
                setattr(profile, key, value)
            profile.save()

        email_payload = payload.get('email') or {}
        if email_payload.get('enable_email'):
            SMTPConfig.objects.all().update(is_active=False)
            SMTPConfig.objects.create(
                provider=email_payload.get('provider', 'custom'),
                smtp_host=email_payload.get('smtp_host', ''),
                smtp_port=int(email_payload.get('smtp_port', 587) or 587),
                sender_email=email_payload.get('sender_email', ''),
                sender_password=email_payload.get('sender_password', ''),
                use_tls=bool(email_payload.get('smtp_use_tls', True)),
                is_active=True,
            )

        file_path.unlink(missing_ok=True)
        return True
    except (OperationalError, ProgrammingError):
        return False
    except Exception:
        return False


def ensure_database_migrated() -> bool:
    """确保数据库迁移已应用（幂等）。"""
    if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.dummy':
        logger.warning('OOBE bootstrap skipped migrate: database engine is dummy')
        return False

    try:
        logger.info('OOBE bootstrap: starting automatic migrate')
        call_command('migrate', interactive=False, verbosity=0)
        logger.info('OOBE bootstrap: automatic migrate completed')
        return True
    except Exception as exc:
        logger.exception('OOBE bootstrap: automatic migrate failed: %s', exc)
        return False


def bootstrap_oobe_if_needed() -> bool:
    """如果存在待初始化配置，则自动迁移并应用 OOBE 数据。"""
    if not has_pending_oobe_setup():
        logger.debug('OOBE bootstrap: no pending setup file found')
        return True

    logger.info('OOBE bootstrap: pending setup detected, starting bootstrap flow')
    if not ensure_database_migrated():
        logger.error('OOBE bootstrap: bootstrap aborted because migrate failed')
        return False

    applied = apply_pending_oobe_setup()
    if applied:
        logger.info('OOBE bootstrap: pending setup applied successfully')
    else:
        logger.error('OOBE bootstrap: failed to apply pending setup')
    return applied
