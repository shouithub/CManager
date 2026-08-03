"""Central validation for untrusted uploaded files."""

import os
import posixpath
import zipfile

from PIL import Image, UnidentifiedImageError


DEFAULT_MAX_BYTES = 20 * 1024 * 1024
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.ico'}
ZIP_EXTENSIONS = {'.zip', '.docx', '.xlsx', '.pptx'}
MACRO_EXTENSIONS = {'.docm', '.dotm', '.xlsm', '.xltm', '.pptm', '.potm'}
SIGNATURES = {
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.gif': (b'GIF87a', b'GIF89a'),
    '.ico': (b'\x00\x00\x01\x00',),
    '.pdf': (b'%PDF-',),
    '.zip': (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'),
    '.docx': (b'PK\x03\x04',),
    '.xlsx': (b'PK\x03\x04',),
    '.pptx': (b'PK\x03\x04',),
    '.doc': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),
    '.xls': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),
    '.rar': (b'Rar!\x1a\x07\x00', b'Rar!\x1a\x07\x01\x00'),
}


def _rewind(upload):
    try:
        upload.seek(0)
    except (AttributeError, OSError):
        pass


def _validate_zip(upload):
    try:
        with zipfile.ZipFile(upload) as archive:
            infos = archive.infolist()
            if len(infos) > 1000:
                return '压缩包内文件数量超过 1000 个'
            total_size = 0
            for info in infos:
                normalized = posixpath.normpath(info.filename.replace('\\', '/'))
                if normalized.startswith('../') or normalized.startswith('/'):
                    return '压缩包包含不安全的路径'
                total_size += info.file_size
                if total_size > 200 * 1024 * 1024:
                    return '压缩包解压后总大小不能超过 200MB'
                if info.compress_size and info.file_size / info.compress_size > 200:
                    return '压缩包包含异常高压缩率文件'
    except (zipfile.BadZipFile, OSError):
        return '文件不是有效的 ZIP/Office 文档'
    finally:
        _rewind(upload)
    return None


def validate_upload(upload, *, field_name='上传文件', allowed_extensions=None,
                    max_bytes=DEFAULT_MAX_BYTES):
    """Return an error string for an unsafe upload, otherwise ``None``."""
    if not upload:
        return f'{field_name}不能为空'
    name = os.path.basename(getattr(upload, 'name', '') or '')
    ext = os.path.splitext(name)[1].lower()
    if ext in MACRO_EXTENSIONS:
        return f'{field_name}不能包含 Office 宏'
    allowed = {item.lower() for item in (allowed_extensions or set())}
    if not ext or (allowed and ext not in allowed):
        return f'{field_name}的文件类型不被允许（允许：{", ".join(sorted(allowed))}）'
    size = getattr(upload, 'size', 0) or 0
    if size > max_bytes:
        return f'{field_name}不能超过 {max_bytes // (1024 * 1024)}MB'

    content_type = (getattr(upload, 'content_type', '') or '').lower()
    if content_type and content_type != 'application/octet-stream':
        if ext in IMAGE_EXTENSIONS and not content_type.startswith('image/'):
            return f'{field_name}的 MIME 类型与图片后缀不一致'
        if ext == '.pdf' and content_type != 'application/pdf':
            return f'{field_name}的 MIME 类型与 PDF 后缀不一致'

    try:
        head = upload.read(16)
    except (AttributeError, OSError):
        return f'{field_name}无法读取'
    finally:
        _rewind(upload)

    if ext == '.webp':
        signature_ok = head.startswith(b'RIFF') and head[8:12] == b'WEBP'
    elif ext == '.csv':
        signature_ok = b'\x00' not in head
    else:
        expected = SIGNATURES.get(ext)
        signature_ok = not expected or any(head.startswith(prefix) for prefix in expected)
    if not signature_ok:
        return f'{field_name}的实际内容与文件后缀不一致'

    if ext in IMAGE_EXTENSIONS:
        try:
            with Image.open(upload) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            return f'{field_name}不是有效或安全的图片'
        finally:
            _rewind(upload)

    if ext in ZIP_EXTENSIONS:
        error = _validate_zip(upload)
        if error:
            return f'{field_name}：{error}'
    return None
