"""上下文处理器：动态表单导航、审核数量和站点设置。"""
import logging
import os
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from urllib.parse import urlsplit
from .models import FormChannel, FormSubmission, Officer
from .business_forms import externally_available_channels
from .identity import (
    active_identity_label,
    available_identities,
    get_active_identity,
    has_president_officer,
    IDENTITY_PRESIDENT,
)

logger = logging.getLogger(__name__)


THIRD_PARTY_CDN_DEFAULT_SRI = {
    'chartjs': 'sha384-XcdcwHqIPULERb2yDEM4R0XaQKU3YnDsrTmjACBZyfdVVqjh6xQ4/DCMd7XLcA6Y',
    'swiper_js': 'sha384-T6qkM4ANslBL/pKcwNUeB0bpsiI6pkXXzwrl7Avc6FXEC/UZaXAeBpZZ2zQ3Zbez',
    'swiper_css': 'sha384-eKrJLy2KlZuvuza/yNmSyFUE2Qb5aehRlXikp6XUOxXVw5pOQBb5n1C0UOcCnAJb',
    'cropper_js': 'sha384-jrOgQzBlDeUNdmQn3rUt/PZD+pdcRBdWd/HWRqRo+n2OR2QtGyjSaJC0GiCeH+ir',
    'cropper_css': 'sha384-6LFfkTKLRlzFtgx8xsWyBdKGpcMMQTkv+dB7rAbugeJAu1Ym2q1Aji1cjHBG12Xh',
}
def site_settings(request):
    cached = cache.get('site:presentation:v1')
    if cached is not None:
        return cached
    base_media_url = f"/{settings.MEDIA_URL.lstrip('/')}"
    if not base_media_url.endswith('/'):
        base_media_url = f"{base_media_url}/"
    cache_buster = cache.get('site:asset_version:v1', '1')

    # favicon URL 通过存储抽象层生成：
    # - 本地模式：仍走 MEDIA_URL（相对路径），由 nginx/static serve 提供
    # - S3 模式：返回 S3/CDN 直链（绝对 URL），不经本站代理
    site_favicon_url = None
    site_favicon_preview_url = None
    try:
        from .storage_backends import ClubStorage
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
        third_party_cdn_base_url = font_cfg.third_party_cdn_base_url or 'https://cdn.bootcdn.net'
        stored_cdn_sri = font_cfg.third_party_cdn_sri
        site_name = font_cfg.site_name or '社团管理系统'
        homepage_title = font_cfg.homepage_title or '社团管理服务中心'
        homepage_subtitle = font_cfg.homepage_subtitle or '致力于为社团提供全方位的管理与服务支持，促进社团健康发展'
    except Exception:
        font_icon_url = 'https://fonts.font.im/icon?family=Material+Icons'
        body_font_url = ''
        body_font_family = ''
        third_party_cdn_base_url = 'https://cdn.bootcdn.net'
        stored_cdn_sri = {}
        site_name = '社团管理系统'
        homepage_title = '社团管理服务中心'
        homepage_subtitle = '致力于为社团提供全方位的管理与服务支持，促进社团健康发展'

    # 仅使用合法的 HTTP(S) CDN 地址，避免配置错误导致模板中的资源地址失效。
    parsed_cdn_url = urlsplit(third_party_cdn_base_url)
    if parsed_cdn_url.scheme not in ('http', 'https') or not parsed_cdn_url.netloc:
        third_party_cdn_base_url = 'https://cdn.bootcdn.net'
    third_party_cdn_base_url = third_party_cdn_base_url.rstrip('/')
    third_party_cdn_sri = THIRD_PARTY_CDN_DEFAULT_SRI.copy()
    if isinstance(stored_cdn_sri, dict):
        for asset, integrity in stored_cdn_sri.items():
            if asset in third_party_cdn_sri and isinstance(integrity, str) and integrity.startswith('sha384-'):
                third_party_cdn_sri[asset] = integrity

    result = {
        'site_favicon_url': site_favicon_url,
        'site_favicon_preview_url': site_favicon_preview_url,
        'font_icon_url': font_icon_url,
        'body_font_url': body_font_url,
        'body_font_family': body_font_family,
        'third_party_cdn_base_url': third_party_cdn_base_url,
        'third_party_cdn_sri': third_party_cdn_sri,
        'site_name': site_name,
        'homepage_title': homepage_title,
        'homepage_subtitle': homepage_subtitle,
    }
    cache.set('site:presentation:v1', result, 300)
    return result


def base_template(request):
    """根据请求类型选择完整页面或仅内容区的基础模板。"""
    return {
        'base_template': (
            'clubs/base_partial.html'
            if getattr(request, 'partial', False)
            else 'clubs/base.html'
        ),
    }


def audit_center_counts(request):
    empty = {
        'audit_center_counts': {'total': 0, 'channels': {}},
        'unread_approval_counts': {'total': 0, 'channels': {}},
        'active_form_channels': [],
        'sidebar_primary_club': None,
        'sidebar_president_clubs': [],
        'active_identity': 'primary',
        'active_identity_label': '',
        'available_identities': [],
        'has_president_identity': False,
        'is_president_identity': False,
    }
    if not request.user.is_authenticated:
        return empty

    try:
        role = request.user.profile.role
    except Exception:
        return empty

    active_identity = get_active_identity(request)
    is_president_identity = active_identity == IDENTITY_PRESIDENT
    identities = available_identities(request)

    # 数据库异常（例如触发 500 的原因）时不得让错误页渲染再次失败。
    try:
        channels = externally_available_channels(
            FormChannel.objects.filter(is_active=True)
            .exclude(slug='')
            .prefetch_related('fields')
            .order_by('order', 'id')
        )
        audit_channels = {}
        approval_channels = {}
        audit_total = 0
        approval_total = 0

        if not is_president_identity and (role in ['staff', 'admin'] or request.user.is_superuser):
            counts = FormSubmission.objects.filter(
                channel__in=channels,
                status='pending',
            ).values('channel__slug').annotate(total=Count('id'))
            audit_channels = {row['channel__slug']: row['total'] for row in counts}
            audit_total = sum(audit_channels.values())

        president_clubs = []
        primary_club = None
        if is_president_identity:
            president_clubs = list(Officer.objects.filter(
                user_profile__user=request.user,
                position='president',
                is_current=True,
            ).select_related('club').order_by('club__name'))
            primary_club = president_clubs[0].club if president_clubs else None
            club_ids = [item.club_id for item in president_clubs]
            counts = FormSubmission.objects.filter(
                channel__in=channels,
                club_id__in=club_ids,
                status__in=['pending', 'rejected'],
            ).values('channel__slug').annotate(total=Count('id'))
            approval_channels = {row['channel__slug']: row['total'] for row in counts}
            approval_total = sum(approval_channels.values())
    except Exception:
        logger.exception('侧边栏统计上下文处理器数据库查询失败')
        return empty

    result = {
        'audit_center_counts': {
            'total': audit_total,
            'channels': audit_channels,
        },
        'unread_approval_counts': {'total': approval_total, 'channels': approval_channels},
        'active_form_channels': channels,
        'sidebar_primary_club': primary_club,
        'sidebar_president_clubs': [item.club for item in president_clubs],
        'active_identity': active_identity,
        'active_identity_label': active_identity_label(request),
        'available_identities': identities,
        'has_president_identity': has_president_officer(request.user) or role == 'president',
        'is_president_identity': is_president_identity,
    }
    return result


def unread_approvals(request):
    return audit_center_counts(request)
