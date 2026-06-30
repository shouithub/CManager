"""上下文处理器：动态表单导航、审核数量和站点设置。"""
import os
from django.conf import settings
from .models import FormChannel, FormSubmission, Officer


def _get_president_club_ids(user):
    return list(Officer.objects.filter(
        user_profile__user=user,
        position='president',
        is_current=True
    ).values_list('club_id', flat=True))


def site_settings(request):
    base_media_url = f"/{settings.MEDIA_URL.lstrip('/')}"
    if not base_media_url.endswith('/'):
        base_media_url = f"{base_media_url}/"
    import time
    cache_buster = int(time.time())

    # favicon URL 通过存储抽象层生成：
    # - 本地模式：仍走 MEDIA_URL（相对路径），由 nginx/static serve 提供
    # - S3 模式：返回 S3/CDN 直链（绝对 URL），不经本站代理
    site_favicon_url = None
    site_favicon_preview_url = None
    try:
        from .storage_backends import ClubStorage
        from .models import StorageConfig
        storage = ClubStorage()
        # 探测是否存在 favicon
        if storage.exists('site/favicon.ico'):
            url = storage.get_public_url('site/favicon.ico')
            if not url.startswith(('http://', 'https://')):
                # 本地模式相对 URL，补 cache buster
                site_favicon_url = f"{url}?v={cache_buster}"
            else:
                site_favicon_url = f"{url}?v={cache_buster}"
        if storage.exists('site/favicon.png'):
            url = storage.get_public_url('site/favicon.png')
            site_favicon_preview_url = f"{url}?v={cache_buster}"
    except Exception:
        # 兜底：尝试用本地文件系统
        favicon_path = os.path.join(settings.MEDIA_ROOT, 'site', 'favicon.ico')
        favicon_preview_path = os.path.join(settings.MEDIA_ROOT, 'site', 'favicon.png')
        if os.path.exists(favicon_path):
            site_favicon_url = f"{base_media_url}site/favicon.ico?v={cache_buster}"
        if os.path.exists(favicon_preview_path):
            site_favicon_preview_url = f"{base_media_url}site/favicon.png?v={cache_buster}"

    try:
        from .models import SiteSettings
        font_cfg = SiteSettings.get_settings()
        font_icon_url = font_cfg.font_icon_url or 'https://fonts.font.im/icon?family=Material+Icons'
        body_font_url = font_cfg.body_font_url or ''
        body_font_family = font_cfg.body_font_family or ''
    except Exception:
        font_icon_url = 'https://fonts.font.im/icon?family=Material+Icons'
        body_font_url = ''
        body_font_family = ''

    return {
        'site_favicon_url': site_favicon_url,
        'site_favicon_preview_url': site_favicon_preview_url,
        'font_icon_url': font_icon_url,
        'body_font_url': body_font_url,
        'body_font_family': body_font_family,
    }


def audit_center_counts(request):
    empty = {
        'audit_center_counts': {'total': 0, 'channels': {}},
        'unread_approval_counts': {'total': 0, 'channels': {}},
        'active_form_channels': [],
        'sidebar_primary_club': None,
        'sidebar_president_clubs': [],
    }
    if not request.user.is_authenticated:
        return empty

    try:
        role = request.user.profile.role
    except Exception:
        return empty

    channels = list(
        FormChannel.objects.filter(is_active=True)
        .exclude(slug='')
        .order_by('order', 'id')
    )
    audit_channels = {}
    approval_channels = {}
    audit_total = 0
    approval_total = 0

    if role in ['staff', 'admin'] or request.user.is_superuser:
        for channel in channels:
            count = FormSubmission.objects.filter(channel=channel, status='pending').count()
            audit_channels[channel.slug] = count
            audit_total += count

    president_clubs = []
    primary_club = None
    if role == 'president':
        president_clubs = list(Officer.objects.filter(
            user_profile__user=request.user,
            position='president',
            is_current=True,
        ).select_related('club').order_by('club__name'))
        primary_club = president_clubs[0].club if president_clubs else None
        club_ids = [item.club_id for item in president_clubs]
        for channel in channels:
            count = FormSubmission.objects.filter(
                channel=channel,
                club_id__in=club_ids,
                status__in=['pending', 'rejected'],
            ).count()
            approval_channels[channel.slug] = count
            approval_total += count

    result = {
        'audit_center_counts': {
            'total': audit_total,
            'channels': audit_channels,
        },
        'unread_approval_counts': {'total': approval_total, 'channels': approval_channels},
        'active_form_channels': channels,
        'sidebar_primary_club': primary_club,
        'sidebar_president_clubs': [item.club for item in president_clubs],
    }
    return result


def unread_approvals(request):
    return audit_center_counts(request)
