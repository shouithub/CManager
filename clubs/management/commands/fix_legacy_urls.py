"""修复历史遗留的异常 URL 与存储文件名（file://、绝对路径等）。

用法：python manage.py fix_legacy_urls
"""

import os
import re

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from ...storage_backends import LocalStorageBackend, _sanitize_storage_name


_SCHEME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://')
_WINDOWS_DRIVE_RE = re.compile(r'^[a-zA-Z]:[\\/]')


def _is_bad_storage_name(name):
    if not name:
        return False
    name = str(name).replace('\\', '/')
    return name.startswith('/') or bool(_SCHEME_RE.match(name)) or bool(_WINDOWS_DRIVE_RE.match(name))


def _is_safe_url(value):
    from urllib.parse import urlsplit

    candidate = str(value or '').strip()
    if not candidate:
        return True
    if candidate.startswith('//'):
        return True
    parsed = urlsplit(candidate)
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def _repair_file_field(instance, field, stdout, style):
    value = getattr(instance, field.name)
    if not value:
        return
    name = value.name
    if not _is_bad_storage_name(name):
        return

    storage = field.storage
    safe_name = _sanitize_storage_name(name)
    moved = False

    if safe_name != name and storage.exists(safe_name):
        try:
            setattr(instance, field.name, safe_name)
            instance.save(update_fields=[field.name])
            moved = True
        except Exception:
            pass

    if not moved:
        try:
            with storage.open(name, 'rb') as source:
                content = source.read()
            if content:
                old_name = name
                storage.save(safe_name, ContentFile(content))
                setattr(instance, field.name, safe_name)
                instance.save(update_fields=[field.name])
                try:
                    storage.delete(old_name)
                except Exception:
                    pass
                moved = True
        except Exception:
            pass

    if not moved:
        try:
            backend = storage._backend() if hasattr(storage, '_backend') else None
        except Exception:
            backend = None
        if isinstance(backend, LocalStorageBackend):
            legacy_path = _SCHEME_RE.sub('', name) if _SCHEME_RE.match(name) else name
            if os.path.exists(legacy_path) and os.path.isfile(legacy_path):
                try:
                    with open(legacy_path, 'rb') as source:
                        content = source.read()
                    if content:
                        storage.save(safe_name, ContentFile(content))
                        setattr(instance, field.name, safe_name)
                        instance.save(update_fields=[field.name])
                        moved = True
                except Exception:
                    pass

    if moved:
        stdout.write(style.SUCCESS(
            "  已修复 %s#%s %s: %s -> %s" % (instance.__class__.__name__, instance.pk, field.name, name, safe_name)
        ))
    else:
        stdout.write(style.WARNING(
            "  无法定位文件，保留原值 %s#%s %s: %s" % (instance.__class__.__name__, instance.pk, field.name, name)
        ))


class Command(BaseCommand):
    help = "修复历史遗留的 file:// / 绝对路径等异常 URL 与存储文件名"

    def handle(self, *args, **options):
        style = self.style

        from ...models import SiteSettings

        try:
            site = SiteSettings.get_settings()
        except Exception as exc:
            self.stdout.write(style.ERROR(
                "读取站点设置失败（%s），请先执行 python manage.py migrate 再重试。" % exc
            ))
            return

        url_fields = {
            'font_icon_url': 'https://fonts.font.im/icon?family=Material+Icons',
            'body_font_url': '',
            'third_party_cdn_base_url': 'https://cdn.bootcdn.net',
        }
        changed = False
        for field, fallback in url_fields.items():
            if not _is_safe_url(getattr(site, field)):
                setattr(site, field, fallback)
                changed = True
                self.stdout.write(style.WARNING(
                    "  已重置站点设置 %s（原值不是合法 http(s) 地址）" % field
                ))
        if changed:
            site.save()
            from django.core.cache import cache
            cache.delete('site:presentation:v1')

        self.stdout.write("开始扫描文件字段...")
        from django.db.models import FileField

        model_fields = []
        for model in apps.get_app_config('clubs').get_models():
            for field in model._meta.fields:
                if isinstance(field, FileField):
                    model_fields.append((model, field))

        for model, field in model_fields:
            try:
                queryset = model.objects.all()
            except Exception as exc:
                self.stdout.write(style.WARNING(
                    "跳过 %s.%s（%s）" % (model.__name__, field.name, exc)
                ))
                continue
            for instance in queryset.iterator():
                try:
                    with transaction.atomic():
                        _repair_file_field(instance, field, self.stdout, style)
                except Exception as exc:
                    self.stdout.write(style.ERROR(
                        "修复 %s#%s %s 失败：%s" % (model.__name__, instance.pk, field.name, exc)
                    ))

        self.stdout.write(style.SUCCESS("历史 URL / 存储名修复完成。"))
