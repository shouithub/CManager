"""Resolve and validate local or Cravatar-backed user avatars."""

from hashlib import md5
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache


AVATAR_SETTINGS_CACHE_KEY = 'site:avatar-settings:v2'
CRAVATAR_BASE_URL = 'https://cravatar.cn/avatar/'


def clear_avatar_settings_cache():
    cache.delete(AVATAR_SETTINGS_CACHE_KEY)


def get_avatar_settings():
    cached = cache.get(AVATAR_SETTINGS_CACHE_KEY)
    if cached is not None:
        return cached
    try:
        from .models import SiteSettings
        config = SiteSettings.get_settings()
        value = bool(config.cravatar_enabled)
    except Exception:
        value = False
    cache.set(AVATAR_SETTINGS_CACHE_KEY, value, timeout=300)
    return value


def normalize_avatar_email(email):
    return (email or '').strip().lower()


def get_cravatar_url(email, size=160, default='mp'):
    digest = md5(normalize_avatar_email(email).encode('utf-8')).hexdigest()
    safe_size = max(1, min(int(size or 160), 2048))
    query = urlencode({'s': safe_size, 'd': default, 'r': 'g'})
    # 走同源代理并附带 immutable 缓存，避免每次刷新都重新请求 Cravatar
    return f'/cravatar/{digest}/?{query}'


def cravatar_exists(email, timeout=4):
    """Return True/False for existence, or None when the service is unavailable."""
    digest = md5(normalize_avatar_email(email).encode('utf-8')).hexdigest()
    query = urlencode({'s': 32, 'd': '404', 'r': 'g'})
    url = f'{CRAVATAR_BASE_URL}{digest}?{query}'
    request = Request(url, headers={'User-Agent': 'CManager/1.0'}, method='GET')
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status == 200 and response.headers.get_content_type().startswith('image/')
    except HTTPError as exc:
        if exc.code == 404:
            return False
        return None
    except (URLError, TimeoutError, OSError):
        return None


def get_profile_avatar_url(profile, request=None, size=160):
    if (
        get_avatar_settings()
        and getattr(profile, 'avatar_source', 'local') == 'cravatar'
        and normalize_avatar_email(getattr(profile, 'avatar_email', ''))
    ):
        return get_cravatar_url(profile.avatar_email, size=size)

    avatar = getattr(profile, 'avatar', None)
    if avatar:
        try:
            url = avatar.url
        except Exception:
            return ''
        # 只允许 http(s) 或站内相对路径，防止历史异常文件名
        # （file://、javascript:、本地绝对路径）被拼进 <img> 触发浏览器拦截。
        if url.startswith(('http://', 'https://', '/')):
            return url
        return ''
    return ''
