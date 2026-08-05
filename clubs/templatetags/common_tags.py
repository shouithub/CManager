import os

from django import template


register = template.Library()


@register.filter
def get_item(value, key):
    try:
        return value.get(key, 0)
    except Exception:
        return 0


@register.filter
def office_preview_url(value, request=None):
    """为文件对象生成 Office 在线预览 URL；非 Office 文档返回空字符串。"""
    if value is None:
        return ''
    from ..views.core import _office_preview_url_for_name

    name = getattr(value, 'name', '') or ''
    display_name = getattr(value, 'original_name', '') or os.path.basename(str(name))
    return _office_preview_url_for_name(request, str(name), display_name)
