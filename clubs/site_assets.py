import os
from django.conf import settings
from PIL import Image


def process_site_logo(upload, allow_webp=True):
    """统一处理站点Logo，输出 favicon.ico 与 favicon.png。返回(ok, message)。"""
    if not upload:
        return False, '未提供Logo文件'

    allowed_exts = ['.ico', '.png', '.jpg', '.jpeg']
    if allow_webp:
        allowed_exts.append('.webp')

    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in allowed_exts:
        ext_text = ', '.join(allowed_exts)
        return False, f'仅支持 {ext_text} 格式'

    site_dir = os.path.join(settings.MEDIA_ROOT, 'site')
    os.makedirs(site_dir, exist_ok=True)
    ico_path = os.path.join(site_dir, 'favicon.ico')
    png_path = os.path.join(site_dir, 'favicon.png')

    try:
        img = Image.open(upload)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')

        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

        preview_img = img.resize((128, 128), Image.LANCZOS)
        preview_img.save(png_path, format='PNG')
        img.save(ico_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        return True, '网站图标已更新'
    except Exception as exc:
        return False, f'保存图标失败: {str(exc)}'
