import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db.utils import OperationalError, ProgrammingError

from .models import SMTPConfig, UserProfile


def _pending_file_path() -> Path:
    return Path(settings.BASE_DIR) / '.oobe_pending.json'


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
