import os

from django import template
from django.utils.translation import get_language


register = template.Library()


@register.filter
def tr(value, field_name=''):
    """按当前语言返回对象字段译文；没有译文时回退到原始字段值。

    用法：{{ channel.name|tr:'name' }} 或 {{ field.label|tr:'label' }}。
    源语言或未配置译文时直接返回原始值，避免任何页面因为缺少译文而空白。
    """
    if value is None:
        return ''
    lang = get_language() or 'zh-hans'
    if lang == 'zh-hans':
        return _tr_fallback(value, str(field_name or ''))
    from ..services.object_translations import translated_text

    obj = value
    text = translated_text(obj, str(field_name or ''), languages=[lang])
    if text:
        return text
    return _tr_fallback(obj, str(field_name or ''))


def _tr_fallback(value, field_name):
    """译文缺失时回退到字段原始值；兼容 display_* 展示属性。"""
    if not field_name:
        return value
    raw = getattr(value, field_name, None)
    if raw is not None:
        return raw
    display_attr = getattr(value, f'display_{field_name}', None)
    if display_attr is not None:
        return display_attr
    return getattr(value, field_name, value)


@register.filter
def tr_options(value, field_name='options'):
    """按当前语言返回对象 options 字段的译文文本列表（与原始选项按索引对齐）。

    用法：{{ field|tr_options }}，无译文时逐项回退原文。
    """
    return _translated_options(value, field_name)


@register.filter
def tr_option_pairs(value, field_name='options'):
    """按当前语言返回 (原始值, 译文标签) 对，供选择类字段渲染时保留提交值。

    用法：{% for value, label in field|tr_option_pairs %}...
    """
    raw_options = _raw_option_list(value, field_name)
    translated = _translated_options(value, field_name)
    return list(zip(raw_options, translated))


@register.filter
def tr_option_label(value, field):
    """按当前语言返回选择类字段某个原始选项的译文标签。

    用法：{{ option_value|tr_option_label:field }}；未配置译文时返回原始值。
    """
    if value is None:
        return ''
    for raw, label in tr_option_pairs(field):
        if str(raw) == str(value):
            return label
    return value


def _raw_option_list(value, field_name='options'):
    if value is None:
        return []
    raw_options = getattr(value, str(field_name or 'options'), []) or []
    return [str(item) for item in raw_options] if isinstance(raw_options, list) else []


def _translated_options(value, field_name='options'):
    import json

    if value is None:
        return []
    lang = get_language() or 'zh-hans'
    obj = value
    raw_options = _raw_option_list(obj, field_name)
    if lang == 'zh-hans':
        return raw_options
    from ..services.object_translations import translated_text

    object_type = getattr(obj, '_meta', None) and getattr(obj._meta, 'model_name', None)
    pk = getattr(obj, 'pk', None)
    if not object_type or not pk:
        return raw_options
    try:
        translated = translated_text(obj, str(field_name), languages=[lang])
        if not translated:
            return raw_options
        parsed = json.loads(translated)
        if not isinstance(parsed, list):
            return raw_options
    except Exception:
        return raw_options
    return [
        str(parsed[index]) if index < len(parsed) and str(parsed[index]).strip() else str(item)
        for index, item in enumerate(raw_options)
    ]


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

    name = (
        getattr(value, 'name', '') or ''
        or getattr(getattr(value, 'file', None), 'name', '') or ''
    )
    display_name = getattr(value, 'original_name', '') or os.path.basename(str(name))
    return _office_preview_url_for_name(request, str(name), display_name)


@register.filter
def is_image_file(value):
    """判断文件对象是否为图片格式。"""
    name = (
        getattr(value, 'name', '') or ''
        or getattr(getattr(value, 'file', None), 'name', '') or ''
    )
    ext = os.path.splitext(str(name))[1].lower()
    return ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


@register.filter
def is_browser_previewable(value):
    """判断文件能否由常见浏览器直接内联预览。"""
    if isinstance(value, dict):
        name = value.get('file_name') or value.get('storage_name') or ''
    else:
        name = (
            getattr(value, 'original_name', '') or ''
            or getattr(value, 'name', '') or ''
            or getattr(getattr(value, 'file', None), 'name', '') or ''
        )
    ext = os.path.splitext(str(name))[1].lower()
    return ext in {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp'}


@register.filter
def file_basename(value):
    """提取文件对象的基础文件名，隐藏 upload_to 目录前缀。"""
    name = (
        getattr(value, 'name', '') or ''
        or getattr(getattr(value, 'file', None), 'name', '') or ''
    )
    return os.path.basename(str(name))


@register.filter
def file_exists(value):
    """文件对象所指向的物理文件/存储对象是否仍然存在。

    数据库记录可能因存储后端切换、迁移或手工清理而与实际存储脱节，
    此时直接使用 ``file.url`` 会得到 404 的破损链接。页面渲染前用本
    过滤器探测一次，缺失文件改为展示“已丢失”占位，而不是输出坏图。

    同时兼容历史轮次快照中的 ``{'storage_name': ...}`` 字典。
    """
    try:
        if isinstance(value, dict):
            name = value.get('storage_name') or ''
            if not name:
                return False
            from ..storage_backends import ClubStorage
            return bool(ClubStorage().exists(name))
        file_field = getattr(value, 'file', None)
        if file_field is None:
            return False
        name = getattr(file_field, 'name', '') or ''
        if not name:
            return False
        storage = getattr(file_field, 'storage', None)
        if storage is None:
            return False
        return bool(storage.exists(name))
    except Exception:
        return False



@register.filter
def tdefault(value, arg):
    """与 default 相同，但兜底文案会被 makemessages 提取（用于模板中文字符串）。"""
    return value if value else arg
