import os
import io
from django.conf import settings
from PIL import Image


def process_site_logo(upload, allow_webp=True):
    """统一处理站点Logo，输出 favicon.ico 与 favicon.png。返回(ok, message)。

    通过存储抽象层写入文件，兼容本地存储与 S3 对象存储。
    """
    if not upload:
        return False, '未提供Logo文件'

    allowed_exts = ['.ico', '.png', '.jpg', '.jpeg']
    if allow_webp:
        allowed_exts.append('.webp')

    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in allowed_exts:
        ext_text = ', '.join(allowed_exts)
        return False, f'仅支持 {ext_text} 格式'

    try:
        # 走存储抽象层：local 模式下落到 MEDIA_ROOT/site/，S3 模式下传到 bucket
        from .storage_backends import ClubStorage
        storage = ClubStorage()

        img = Image.open(upload)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')

        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

        # 生成预览 PNG 与 ICO 到内存，再交给 storage 抽象层持久化
        preview_img = img.resize((128, 128), Image.LANCZOS)
        png_buf = io.BytesIO()
        preview_img.save(png_buf, format='PNG')
        png_buf.seek(0)

        ico_buf = io.BytesIO()
        img.save(ico_buf, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        ico_buf.seek(0)

        png_name = 'site/favicon.png'
        ico_name = 'site/favicon.ico'

        # 删除旧文件（避免重名加 _1 后缀）
        try:
            storage.delete(png_name)
        except Exception:
            pass
        try:
            storage.delete(ico_name)
        except Exception:
            pass

        storage.save(png_name, png_buf)
        storage.save(ico_name, ico_buf)
        return True, '网站图标已更新'
    except Exception as exc:
        return False, f'保存图标失败: {str(exc)}'
