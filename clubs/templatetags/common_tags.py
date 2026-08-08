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
