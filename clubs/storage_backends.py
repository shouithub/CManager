# -*- coding: utf-8 -*-
"""
统一存储抽象层（Storage Abstraction Layer）
============================================

设计目标：
    无论后端使用本地存储还是在线 S3 兼容存储（AWS S3 / MinIO / 阿里云 OSS /
    腾讯云 COS / 七牛云 Kodo 等），上层业务代码只需面向 ``ClubStorage`` 这一套
    接口编程。切换后端时，只需在管理员后台修改 ``StorageConfig`` 配置，业务代码
    零改动。

核心组件：
    1. ``LocalStorageBackend``  —— 本地文件系统后端
    2. ``S3StorageBackend``    —— S3 协议后端（基于 boto3）
    3. ``ClubStorage``         —— Django Storage 接口适配器，运行时根据数据库
                                 ``StorageConfig`` 选择实际后端并委托调用

特性：
    * 切换后端无需重启服务（每次调用都重新读取配置）
    * 兼容 Django FileField：所有 ``file.url`` / ``file.path`` / ``file.open()``
      调用自动走抽象层
    * 提供 ``get_public_url(name)`` 兼容入口，实际返回短时签名地址
    * 提供 ``get_presigned_url(name)`` 用于生成临时下载直链
    * S3 模式下 ``file.path`` 会下载到临时文件（供 docx/PIL/fitz 等需要本地
      路径的库使用），调用方应在 ``finally`` 中调用 ``cleanup_temp_files``
      清理，或调用 ``storage.release_path(name)`` 主动释放

依赖：
    * boto3：S3 协议 SDK
"""

import os
import io
import json
import re
import time
import tempfile
import threading
import uuid
import logging
import mimetypes
from urllib.parse import urljoin, quote

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.db.utils import DatabaseError, IntegrityError
from django.core.files.storage import Storage
from django.core.exceptions import SuspiciousFileOperation
from django.core import signing
from django.urls import reverse
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)


def _sanitize_storage_name(name):
    """把存储名规范化为站内相对路径。

    防止历史数据或异常文件名（如 ``file:///...``、绝对路径、目录穿越）被
    直接写入存储字段，进而被拼进文件 URL 导致浏览器加载 ``file://`` 链接。
    """
    name = str(name or '').replace('\\', '/')
    # 去掉 URL scheme（file://、https:// 等）
    name = re.sub(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', '', name)
    stack = []
    for part in name.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if stack:
                stack.pop()
            continue
        stack.append(part)
    return '/'.join(stack) or 'unnamed'


_MD5_RE = re.compile(r'^[0-9a-f]{32}$')
# 这些路径承担站点展示/个人展示缓存或固定寻址职责，不做内容寻址去重：
# - site/：站点图标/Logo，需要固定文件名
# - avatars/：头像走 /media/avatars/ 的 immutable 缓存，必须保留原目录
# - carousel/：首页轮播图走 /media/carousel/ 的 30d 缓存，同样保留原目录
_NO_DEDUP_PREFIXES = ('site/', 'avatars/', 'carousel/')
_PUBLIC_MEDIA_PREFIXES = ('site/', 'avatars/', 'carousel/')
_MEDIA_SIGNING_SALT = 'cmanager.temporary-media.v1'


def build_temporary_media_url(name):
    """Return a short-lived capability URL for a stored object.

    The URL contains only a signed storage key.  The serving endpoint validates
    its timestamp before reading local storage or issuing an S3 presigned URL.
    """
    safe_name = _sanitize_storage_name(name)
    token = signing.dumps({'name': safe_name}, salt=_MEDIA_SIGNING_SALT, compress=True)
    return reverse('clubs:temporary_media_file', kwargs={'token': token})


def load_temporary_media_name(token, max_age=None):
    """Validate a temporary-media token and return its normalized storage key."""
    if max_age is None:
        max_age = getattr(settings, 'TEMPORARY_MEDIA_URL_MAX_AGE', 900)
    payload = signing.loads(token, salt=_MEDIA_SIGNING_SALT, max_age=max_age)
    name = payload.get('name', '') if isinstance(payload, dict) else ''
    safe_name = _sanitize_storage_name(name)
    if not name or safe_name != name:
        raise signing.BadSignature('invalid storage name')
    return safe_name


def bind_client_md5_from_post(post, files):
    """把客户端提交的 MD5 按顺序绑定到对应上传文件对象上。

    multipart 表单中每个文件字段 ``field_name`` 会附带一个同名
    ``md5_<field_name>`` 隐藏字段，值为 JSON 数组，顺序与
    ``input.files`` 一致。服务器只读取该值并设置
    ``uploaded.client_md5``，不读取文件内容做任何计算。

    非法格式的 MD5 一律忽略（该文件退回普通随机名保存，不影响上传）。
    """
    if post is None or files is None:
        return
    for key in list(post.keys()):
        if not key.startswith('md5_'):
            continue
        field_name = key[4:]
        if not field_name:
            continue
        raw = post.get(key)
        if not raw:
            continue
        try:
            md5_list = json.loads(raw)
            if not isinstance(md5_list, list):
                md5_list = [md5_list]
        except (TypeError, ValueError):
            md5_list = [raw]
        uploaded_list = files.getlist(field_name)
        for index, uploaded in enumerate(uploaded_list):
            if index >= len(md5_list):
                break
            candidate = md5_list[index]
            if isinstance(candidate, str) and _MD5_RE.match(candidate):
                uploaded.client_md5 = candidate


# 模块级缓存：每个 StorageConfig 版本号对应一组后端实例
# 避免每次 save 都新建 client，但配置变更后会自动重建
_backend_lock = threading.Lock()
_backend_cache = {}  # {(backend_type, version, config_signature): backend_instance}
_temp_paths_registry = threading.local()  # 临时文件清理登记
_config_cache = {'value': None, 'expires_at': 0.0}


# ============================================================
# 后端实现
# ============================================================

class LocalStorageBackend:
    """本地文件系统存储后端。

    所有方法都直接基于 ``settings.MEDIA_ROOT`` 操作，与 Django 默认的
    ``FileSystemStorage`` 行为一致。
    """

    def __init__(self):
        self.location = str(settings.MEDIA_ROOT)
        self.base_url = settings.MEDIA_URL

    # ---------- 路径辅助 ----------
    def _full_path(self, name):
        """规范化并返回绝对路径。"""
        if name is None:
            raise ValueError("name 不能为空")
        # 防止目录穿越
        full = os.path.normpath(os.path.join(self.location, name))
        if not full.startswith(os.path.normpath(self.location)):
            raise SuspiciousFileOperation("不允许的路径: %s" % name)
        return full

    # ---------- Storage 接口 ----------
    def save(self, name, content, max_length=None):
        name = _sanitize_storage_name(name)
        full = self._full_path(name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        # content 可能是 Django UploadedFile / ContentFile / file-like
        if hasattr(content, 'chunks'):
            with open(full, 'wb') as f:
                for chunk in content.chunks():
                    f.write(chunk)
        elif hasattr(content, 'read'):
            with open(full, 'wb') as f:
                while True:
                    chunk = content.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        else:
            # 字节串
            with open(full, 'wb') as f:
                f.write(content)
        return name

    def open(self, name, mode='rb'):
        return open(self._full_path(name), mode)

    def delete(self, name):
        full = self._full_path(name)
        if os.path.exists(full):
            try:
                os.remove(full)
            except IsADirectoryError:
                pass

    def exists(self, name):
        return os.path.exists(self._full_path(name))

    def listdir(self, path=''):
        full = self._full_path(path)
        if not os.path.isdir(full):
            return [], []
        dirs, files = [], []
        for entry in os.listdir(full):
            if os.path.isdir(os.path.join(full, entry)):
                dirs.append(entry)
            else:
                files.append(entry)
        return dirs, files

    def size(self, name):
        return os.path.getsize(self._full_path(name))

    def url(self, name):
        # 本地模式下返回 MEDIA_URL 相对路径
        if self.base_url is None:
            raise ValueError("MEDIA_URL 未配置")
        # 历史数据可能写入过 file://、绝对路径等异常文件名，统一在拼 URL 前清洗，
        # 防止 file:// 或本地绝对路径泄漏到页面导致浏览器安全拦截。
        safe_name = _sanitize_storage_name(name)
        return urljoin(self.base_url, safe_name).replace('\\', '/')

    def path(self, name):
        # 本地直接返回真实路径
        return self._full_path(name)

    def get_available_name(self, name, max_length=None):
        """生成不冲突的文件名（与本地存储默认行为一致）。"""
        dir_name, file_name = os.path.split(name)
        root, ext = os.path.splitext(file_name)
        # 与 FileSystemStorage 不同，我们保留覆盖语义：若文件已存在，加序号
        counter = 1
        candidate = name
        while self.exists(candidate):
            candidate = os.path.join(dir_name, "%s_%d%s" % (root, counter, ext))
            counter += 1
            if max_length and len(candidate) > max_length:
                # 截断 root
                truncate = len(candidate) - max_length
                root = root[:len(root) - truncate]
                candidate = os.path.join(dir_name, "%s_%d%s" % (root, counter, ext))
        return candidate

    # ---------- 直链/预签名 ----------
    def get_public_url(self, name):
        """对 Office Online embedding 返回的直链。

        本地模式下与 ``url()`` 相同（部署后由 nginx/CloudFront 提供静态服务）。
        """
        return self.url(name)

    def get_presigned_url(self, name, expiration=3600, *, inline=None, filename=None):
        """本地模式没有预签名机制，直接返回 url。

        注意：本地模式下任何拿到 url 的用户都能下载，依赖部署层鉴权。
        """
        return self.url(name)


class S3StorageBackend:
    """S3 协议存储后端。

    兼容 AWS S3、MinIO、阿里云 OSS（S3 兼容模式）、腾讯云 COS（S3 兼容模式）、
    七牛云 Kodo 等。所有方法基于 boto3 实现。
    """

    def __init__(self, config):
        """
        :param config: StorageConfig 实例
        """
        self.config = config
        self._client = None
        self._resource = None

    # ---------- boto3 client ----------
    def _get_client(self):
        if self._client is None:
            cfg = self.config
            boto_config_kwargs = dict(
                signature_version='s3v4',
                retries={'max_attempts': 3, 'mode': 'standard'},
            )
            if cfg.s3_addressing_style:
                boto_config_kwargs['s3'] = {'addressing_style': cfg.s3_addressing_style}
            boto_config = _boto_config(**boto_config_kwargs)

            client_kwargs = dict(
                service_name='s3',
                aws_access_key_id=cfg.s3_access_key_id,
                aws_secret_access_key=cfg.s3_secret_access_key,
                config=boto_config,
            )
            if cfg.s3_endpoint_url:
                client_kwargs['endpoint_url'] = cfg.s3_endpoint_url
            if cfg.s3_region:
                client_kwargs['region_name'] = cfg.s3_region

            self._client = _boto3_client(**client_kwargs)
        return self._client

    @property
    def bucket(self):
        return self.config.s3_bucket_name

    # ---------- Storage 接口 ----------
    def save(self, name, content, max_length=None):
        client = self._get_client()
        # content 可能是 file-like 或 bytes
        if hasattr(content, 'chunks'):
            data_iter = content.chunks()
        elif hasattr(content, 'read'):
            # 读为 BytesIO，boto3 需要 seekable
            data = content.read()
            if isinstance(data, str):
                data = data.encode('utf-8')
            content = io.BytesIO(data)
            data_iter = None
        else:
            content = io.BytesIO(content if isinstance(content, bytes) else str(content).encode())
            data_iter = None

        if data_iter is not None:
            # 大文件分块上传
            try:
                client.upload_fileobj(
                    Fileobj=_ChunkedFileWrapper(data_iter),
                    Bucket=self.bucket,
                    Key=name,
                )
            except Exception:
                # 降级：读全量再传
                buf = io.BytesIO()
                for chunk in data_iter:
                    buf.write(chunk)
                buf.seek(0)
                client.upload_fileobj(Fileobj=buf, Bucket=self.bucket, Key=name)
        else:
            client.upload_fileobj(Fileobj=content, Bucket=self.bucket, Key=name)
        return name

    def open(self, name, mode='rb'):
        """S3 不支持随机写，仅支持读模式。

        :returns: 一个可读的 file-like 对象（StreamingBody）
        """
        if 'w' in mode:
            raise NotImplementedError(
                "S3 后端不支持 write 模式打开；请改用 save(name, content)"
            )
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket, Key=name)
        return response['Body']

    def delete(self, name):
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=name)
        except Exception as e:
            logger.warning("S3 删除 %s 失败：%s", name, e)

    def exists(self, name):
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket, Key=name)
            return True
        except _botocore_exceptions.ClientError as e:
            status = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 500)
            if status == 404:
                return False
            raise
        except Exception:
            # 兜底
            return False

    def listdir(self, path=''):
        client = self._get_client()
        prefix = (path or '').lstrip('/')
        if prefix and not prefix.endswith('/'):
            prefix += '/'
        kwargs = dict(Bucket=self.bucket, Prefix=prefix, Delimiter='/')
        dirs, files = [], []
        paginator = client.get_paginator('list_objects_v2')
        for page in paginator.paginate(**kwargs):
            for p in page.get('CommonPrefixes', []) or []:
                dirs.append(p['Prefix'].rstrip('/').split('/')[-1])
            for o in page.get('Contents', []) or []:
                key = o['Key']
                if key != prefix:
                    files.append(key[len(prefix):])
        return dirs, files

    def size(self, name):
        client = self._get_client()
        try:
            response = client.head_object(Bucket=self.bucket, Key=name)
            return int(response.get('ContentLength', 0))
        except Exception:
            return 0

    def url(self, name):
        """对外公开访问 URL（直链）。

        优先级：
            1. custom_domain（如 CDN）
            2. endpoint_url + bucket
            3. AWS 默认 https://<bucket>.s3.<region>.amazonaws.com/<key>
        """
        cfg = self.config
        # 历史数据可能写入过 file://、绝对路径等异常文件名，统一清洗后再拼直链。
        key = quote(_sanitize_storage_name(name), safe='/')
        if cfg.s3_custom_domain:
            base = cfg.s3_custom_domain.rstrip('/')
            # 自定义域名通常不包含 bucket
            return "%s/%s" % (base, key)
        if cfg.s3_endpoint_url:
            base = cfg.s3_endpoint_url.rstrip('/')
            return "%s/%s/%s" % (base, cfg.s3_bucket_name, key)
        # AWS S3 默认 URL（virtual-hosted）
        if cfg.s3_region:
            return "https://%s.s3.%s.amazonaws.com/%s" % (cfg.s3_bucket_name, cfg.s3_region, key)
        return "https://%s.s3.amazonaws.com/%s" % (cfg.s3_bucket_name, key)

    def path(self, name):
        """S3 没有本地路径，下载到 NamedTemporaryFile 返回路径。

        注意：调用方应在使用完毕后调用 ``storage.release_path(name)`` 释放，
        否则会泄漏到 ``/tmp``（最终由系统 tmpwatch 清理）。
        """
        # 已经下载过，直接返回
        registry = _get_temp_registry()
        cached = registry.get(name)
        if cached and os.path.exists(cached):
            return cached

        ext = os.path.splitext(name)[1]
        tmp = tempfile.NamedTemporaryFile(
            suffix=ext or '.bin', delete=False, prefix='s3cache_'
        )
        client = self._get_client()
        client.download_fileobj(self.bucket, name, tmp)
        tmp.close()
        registry[name] = tmp.name
        return tmp.name

    def get_available_name(self, name, max_length=None):
        # S3 默认覆盖同名文件。若需保留行为，则查询 exists 后加序号
        # 这里为了与本地一致，加序号防止覆盖
        if not self.exists(name):
            return name
        dir_name, file_name = os.path.split(name)
        root, ext = os.path.splitext(file_name)
        counter = 1
        candidate = name
        while self.exists(candidate):
            candidate = os.path.join(dir_name, "%s_%d%s" % (root, counter, ext))
            counter += 1
        return candidate

    # ---------- 直链/预签名 ----------
    def get_public_url(self, name):
        """返回后端原始 URL；业务页面应改用 ClubStorage 的签名入口。"""
        return self.url(name)

    def get_presigned_url(self, name, expiration=3600, *, inline=None, filename=None):
        """生成临时下载直链（默认 1 小时）。

        用于私密 bucket 的下载场景。
        """
        client = self._get_client()
        params = {'Bucket': self.bucket, 'Key': _sanitize_storage_name(name)}
        if inline is not None:
            safe_filename = os.path.basename(str(filename or name)).replace('\r', '').replace('\n', '')
            disposition = 'inline' if inline else 'attachment'
            params['ResponseContentDisposition'] = (
                f"{disposition}; filename*=UTF-8''{quote(safe_filename)}"
            )
            params['ResponseContentType'] = (
                mimetypes.guess_type(safe_filename)[0] or 'application/octet-stream'
            )
        return client.generate_presigned_url(
            'get_object',
            Params=params,
            ExpiresIn=expiration,
            HttpMethod='GET',
        )


# ============================================================
# 辅助类：分块 file wrapper
# ============================================================

class _ChunkedFileWrapper:
    """将 Django 的 chunks() 迭代器包装为 file-like，用于 boto3 upload_fileobj。"""

    def __init__(self, chunks_iter):
        self._iter = iter(chunks_iter)
        self._buf = b''
        self._eof = False

    def read(self, amt=-1):
        if amt is None or amt < 0:
            # 全读完
            data = self._buf
            self._buf = b''
            for chunk in self._iter:
                data += chunk
            return data
        while len(self._buf) < amt and not self._eof:
            try:
                self._buf += next(self._iter)
            except StopIteration:
                self._eof = True
        out, self._buf = self._buf[:amt], self._buf[amt:]
        return out

    def seek(self, *args, **kwargs):
        # boto3 在某些版本会调用 seek，做兼容
        return 0

    def tell(self):
        return 0


# ============================================================
# 临时文件管理
# ============================================================

def _get_temp_registry():
    """获取当前线程的临时文件登记表。"""
    if not hasattr(_temp_paths_registry, 'paths'):
        _temp_paths_registry.paths = {}
    return _temp_paths_registry.paths


def cleanup_temp_files():
    """清理当前线程在 S3 path() 调用中产生的临时文件。

    建议在 view 中通过 ``finally`` 或 middleware 调用。
    """
    registry = _get_temp_registry()
    for name, path in list(registry.items()):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning("清理临时文件 %s 失败：%s", path, e)
        registry.pop(name, None)


def clear_storage_config_cache():
    with _backend_lock:
        _config_cache['value'] = None
        _config_cache['expires_at'] = 0.0
        _backend_cache.clear()


# ============================================================
# Django Storage 适配器
# ============================================================

@deconstructible
class ClubStorage(Storage):
    """统一存储抽象层（Django Storage 接口适配器）。

    运行时根据数据库 ``StorageConfig`` 选择实际后端（Local 或 S3）。
    业务代码无需感知后端类型，所有 ``FileField`` 自动走本抽象层。

    用法（settings.py）::

        STORAGES = {
            "default": {
                "BACKEND": "clubs.storage_backends.ClubStorage",
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }

    切换后端：管理员后台访问 ``/admin-panel/storage-config/`` 修改
    ``backend_type`` 即可，无需重启服务。
    """

    def __init__(self, *args, **kwargs):
        # 不缓存后端实例，避免配置变更后旧实例仍被使用
        # Django 的 Storage 类作为单例缓存（deconstructible），但每次方法调用
        # 都会重新读取最新配置
        super().__init__()

    # ---------- 后端选择 ----------
    def _get_config(self):
        """读取当前激活的 StorageConfig。

        表不存在或未配置时返回 None，降级到本地存储。
        """
        now = time.monotonic()
        if _config_cache['expires_at'] > now:
            return _config_cache['value']
        try:
            from .models import StorageConfig
            config = StorageConfig.get_active_config()
            with _backend_lock:
                _config_cache['value'] = config
                _config_cache['expires_at'] = now + 10
            return config
        except Exception:
            # 迁移未跑、表不存在等
            return None

    def _is_s3(self):
        cfg = self._get_config()
        return bool(
            cfg
            and cfg.backend_type == 's3'
            and cfg.is_active
            and cfg.s3_bucket_name
            and cfg.s3_access_key_id
            and cfg.s3_secret_access_key
        )

    def _backend(self):
        """返回当前生效的后端实例。"""
        cfg = self._get_config()
        if cfg and cfg.backend_type == 's3' and cfg.is_active:
            # 简单缓存：相同 config 版本复用 client
            sig = (cfg.pk, cfg.updated_at.timestamp() if cfg.updated_at else 0)
            with _backend_lock:
                cached = _backend_cache.get(sig)
                if cached is None:
                    cached = S3StorageBackend(cfg)
                    _backend_cache[sig] = cached
                    # 清理过旧缓存
                    if len(_backend_cache) > 5:
                        _backend_cache.clear()
                        _backend_cache[sig] = cached
                return cached
        # 本地后端无状态，可以每次新建
        return LocalStorageBackend()

    # ============ Django Storage 接口实现 ============

    def _save(self, name, content):
        name = _sanitize_storage_name(name)
        client_md5 = getattr(content, 'client_md5', '') or ''
        if (
            _MD5_RE.match(str(client_md5))
            and not name.startswith(_NO_DEDUP_PREFIXES)
        ):
            return self._save_deduplicated(str(client_md5), content, name)
        # Keep fixed site assets stable; all user uploads receive unpredictable keys.
        if getattr(settings, 'SECURE_RANDOMIZE_UPLOAD_NAMES', True) and not name.startswith('site/'):
            directory, filename = os.path.split(name)
            extension = os.path.splitext(filename)[1].lower()[:16]
            name = os.path.join(directory, f'{uuid.uuid4().hex}{extension}')
        return self._backend().save(name, content)

    def _save_deduplicated(self, md5, content, original_name):
        """内容寻址保存：同 MD5 复用同一份物理文件，仅增加引用计数。

        存储名固定为 ``blobs/<md5><扩展名>``。并发下依赖 md5 唯一索引：
        两个请求同时写入时，后提交者捕获 IntegrityError 后转为复用。

        MD5 完全由客户端计算，服务器不读取文件内容，因此以客户端同时提交的
        文件大小（``content.size`` 元数据，同样不读取内容）作为第二校验条件：
        若命中已有 blob 但大小不一致，说明客户端 MD5 异常，退回普通随机名
        保存，避免把新文件错误地指向旧文件内容。

        FileBlob 表缺失（迁移未应用）时同样退回普通随机名保存并记录告警，
        避免线上因表缺失导致上传 500；迁移补齐后去重能力自动恢复。
        """
        from .models import FileBlob
        extension = os.path.splitext(original_name)[1].lower()[:16]
        blob_name = f'blobs/{md5}{extension}'
        content_size = getattr(content, 'size', None)
        try:
            existing = FileBlob.objects.filter(md5=md5).first()
        except DatabaseError as exc:
            logger.warning('FileBlob 表不可用，退回随机名保存: %s', exc)
            return self._save_randomized(original_name, content)
        if existing is not None:
            if self._blob_size_conflict(existing, content_size):
                logger.warning(
                    '客户端 MD5 命中已有 blob 但文件大小不一致，退回随机名保存: '
                    'md5=%s existing_size=%s incoming_size=%s',
                    md5, existing.size, content_size,
                )
                return self._save_randomized(original_name, content)
            # 已存在：不再写物理文件，仅增加引用计数
            FileBlob.objects.filter(pk=existing.pk).update(ref_count=F('ref_count') + 1)
            # 必须以登记表中的实际存储名为准：同一 MD5 可能先以
            # .jpg 登记、后续又以 .jpeg 上传，扩展名必须保持首次登记值。
            return existing.storage_name
        try:
            with transaction.atomic():
                self._backend().save(blob_name, content)
                FileBlob.objects.create(
                    md5=md5, storage_name=blob_name, ref_count=1, size=content_size
                )
        except IntegrityError:
            # 并发下其他请求已创建同一 blob：回滚到 savepoint 后复用
            blob = FileBlob.objects.filter(md5=md5).first()
            if blob is None:
                # 记录被并发删除的极端情况，退回普通随机名保存
                logger.warning('FileBlob 并发创建冲突后未找到记录，回退普通保存: %s', md5)
                return self._save_randomized(original_name, content)
            if self._blob_size_conflict(blob, content_size):
                logger.warning(
                    'FileBlob 并发冲突后大小不一致，退回随机名保存: '
                    'md5=%s existing_size=%s incoming_size=%s',
                    md5, blob.size, content_size,
                )
                return self._save_randomized(original_name, content)
            FileBlob.objects.filter(pk=blob.pk).update(ref_count=F('ref_count') + 1)
            return blob.storage_name
        except DatabaseError as exc:
            # 表缺失/数据库异常：已写出的 blobs 物理文件无登记记录，
            # 先清理避免孤儿文件，再退回普通随机名保存。
            logger.warning('FileBlob 登记失败，退回随机名保存: %s', exc)
            try:
                self._backend().delete(blob_name)
            except Exception:
                pass
            return self._save_randomized(original_name, content)
        return blob_name

    @staticmethod
    def _blob_size_conflict(blob, content_size):
        """判断是否因文件大小不一致而放弃去重。

        旧数据（size 为空）无法比对，按原有行为继续复用，避免影响历史记录。
        只有两侧都明确给出大小且不一致时才视为冲突。
        """
        if blob.size is None or content_size is None:
            return False
        try:
            return int(blob.size) != int(content_size)
        except (TypeError, ValueError):
            return False

    def _save_randomized(self, original_name, content):
        # 回退路径可能收到已被读取过的 content（如并发冲突后重试），
        # 可 seek 时先回到开头，避免写出空文件。
        if hasattr(content, 'seek'):
            try:
                content.seek(0)
            except (OSError, ValueError):
                pass
        directory, filename = os.path.split(original_name)
        extension = os.path.splitext(filename)[1].lower()[:16]
        name = os.path.join(directory, f'{uuid.uuid4().hex}{extension}')
        return self._backend().save(name, content)

    def get_available_name(self, name, max_length=None):
        return self._backend().get_available_name(name, max_length)

    def exists(self, name):
        return self._backend().exists(name)

    def delete(self, name):
        name = _sanitize_storage_name(name)
        if name.startswith('blobs/'):
            self._release_blob(name)
            return None
        return self._backend().delete(name)

    def _release_blob(self, blob_name):
        """引用计数减一；归零时物理删除文件与登记记录。"""
        from .models import FileBlob
        try:
            with transaction.atomic():
                blob = FileBlob.objects.filter(storage_name=blob_name).select_for_update().first()
                if blob is None:
                    logger.warning('释放不存在的 FileBlob 引用: %s', blob_name)
                    return
                if blob.ref_count <= 1:
                    self._backend().delete(blob_name)
                    blob.delete()
                else:
                    FileBlob.objects.filter(pk=blob.pk).update(ref_count=F('ref_count') - 1)
        except Exception:
            logger.exception('释放 FileBlob 引用失败: %s', blob_name)

    def retain(self, name):
        """为内容寻址文件增加一个引用（历史快照等只引用不拷贝的场景）。"""
        name = _sanitize_storage_name(name)
        if not name.startswith('blobs/'):
            return False
        from .models import FileBlob
        try:
            blob = FileBlob.objects.filter(storage_name=name).first()
            if blob is None:
                logger.warning('retain 不存在的 FileBlob: %s', name)
                return False
            FileBlob.objects.filter(pk=blob.pk).update(ref_count=F('ref_count') + 1)
            return True
        except Exception:
            logger.exception('retain FileBlob 失败: %s', name)
            return False

    def listdir(self, path=''):
        return self._backend().listdir(path)

    def size(self, name):
        return self._backend().size(name)

    def url(self, name):
        name = _sanitize_storage_name(name)
        backend = self._backend()
        if name.startswith(_PUBLIC_MEDIA_PREFIXES):
            return backend.url(name)
        if isinstance(backend, S3StorageBackend):
            configured_expiration = max(1, int(backend.config.presigned_url_expiration or 900))
            inline_expiration = max(1, int(getattr(settings, 'TEMPORARY_MEDIA_URL_MAX_AGE', 900)))
            return backend.get_presigned_url(
                name,
                min(configured_expiration, inline_expiration),
                inline=True,
                filename=os.path.basename(name),
            )
        return build_temporary_media_url(name)

    def path(self, name):
        return self._backend().path(name)

    def open(self, name, mode='rb'):
        # Django Storage.open 期望返回 file-like 对象
        return self._backend().open(name, mode)

    # ============ 扩展接口（业务代码专用）============

    def get_public_url(self, name):
        """返回临时地址：本地走本站签名，S3 直接返回预签名 URL。"""
        return self.url(name)

    def get_presigned_url(self, name, expiration=3600, *, inline=None, filename=None):
        """生成下载用临时直链。

        S3 模式返回 STS 临时签名 URL（默认 1 小时）；
        本地模式返回普通 url（无签名）。
        """
        backend = self._backend()
        if hasattr(backend, 'get_presigned_url'):
            return backend.get_presigned_url(
                name,
                expiration,
                inline=inline,
                filename=filename,
            )
        return backend.url(name)

    def release_path(self, name):
        """主动释放 ``path()`` 调用产生的临时文件。"""
        registry = _get_temp_registry()
        path = registry.pop(name, None)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.warning("释放临时文件 %s 失败：%s", path, e)

    def cleanup_temp_files(self):
        """清理当前线程所有 S3 临时文件（与模块级 cleanup_temp_files 等价）。"""
        cleanup_temp_files()

    # ============ 工具方法 ============

    def test_s3_connection(self, config_dict):
        """测试 S3 连接是否正常。

        :param config_dict: 包含 endpoint/bucket/ak/sk 等键的字典
        :returns: (success: bool, message: str)
        """
        try:
            client = _boto3_client(
                service_name='s3',
                aws_access_key_id=config_dict.get('s3_access_key_id'),
                aws_secret_access_key=config_dict.get('s3_secret_access_key'),
                endpoint_url=config_dict.get('s3_endpoint_url') or None,
                region_name=config_dict.get('s3_region') or None,
                config=_boto_config(
                    signature_version='s3v4',
                    retries={'max_attempts': 2, 'mode': 'standard'},
                    s3={'addressing_style': config_dict.get('s3_addressing_style') or 'auto'}
                    if config_dict.get('s3_addressing_style') else None,
                ),
            )
            # 列出 bucket 中前 1 个对象，验证权限
            response = client.list_objects_v2(
                Bucket=config_dict.get('s3_bucket_name'),
                MaxKeys=1,
            )
            return True, "连接成功，bucket '%s' 可访问，当前对象数：%s" % (
                config_dict.get('s3_bucket_name'),
                response.get('KeyCount', 0),
            )
        except _botocore_exceptions.ClientError as e:
            status = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', '?')
            return False, "S3 拒绝访问（HTTP %s）：%s" % (
                status, e.response.get('Error', {}).get('Message', str(e))
            )
        except Exception as e:
            return False, "连接失败：%s" % str(e)


# ============================================================
# 延迟导入 boto3，避免本地模式无 boto3 时报错
# ============================================================

def _boto3_client(**kwargs):
    import boto3
    return boto3.client(**kwargs)


def _boto_config(**kwargs):
    from botocore.config import Config
    # 过滤 None
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return Config(**kwargs)


def _botocore_exceptions():
    from botocore import exceptions
    return exceptions


class _BotocoreExceptionsProxy:
    """懒加载 botocore.exceptions 的代理。"""

    def __getattr__(self, name):
        return getattr(_botocore_exceptions(), name)


_botocore_exceptions = _BotocoreExceptionsProxy()
