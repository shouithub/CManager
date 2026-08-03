"""Application-level encryption for reversible service credentials."""

import base64
import hashlib

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


PREFIX = 'enc:v1:'


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise ImproperlyConfigured('cryptography is required for encrypted credentials') from exc

    configured = getattr(settings, 'CREDENTIAL_ENCRYPTION_KEY', '').strip()
    if configured:
        key = configured.encode('ascii')
    elif getattr(settings, 'ALLOW_DERIVED_CREDENTIAL_KEY', False):
        digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
        key = base64.urlsafe_b64encode(digest)
    else:
        raise ImproperlyConfigured('生产环境必须设置 CREDENTIAL_ENCRYPTION_KEY')
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured('CREDENTIAL_ENCRYPTION_KEY 必须是有效的 Fernet 密钥') from exc


def encrypt_secret(value):
    if value in (None, '') or str(value).startswith(PREFIX):
        return value or ''
    token = _fernet().encrypt(str(value).encode('utf-8')).decode('ascii')
    return PREFIX + token


def decrypt_secret(value):
    if value in (None, ''):
        return ''
    value = str(value)
    if not value.startswith(PREFIX):
        # Backward compatibility until the data migration encrypts old rows.
        return value
    return _fernet().decrypt(value[len(PREFIX):].encode('ascii')).decode('utf-8')


class EncryptedCharField(models.CharField):
    """A CharField that transparently encrypts values at the database boundary."""

    def from_db_value(self, value, expression, connection):
        return decrypt_secret(value)

    def to_python(self, value):
        return decrypt_secret(value)

    def get_prep_value(self, value):
        return encrypt_secret(super().get_prep_value(value))
