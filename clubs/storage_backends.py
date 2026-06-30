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
    * 提供 ``get_public_url(name)`` 用于给 Office Online embedding 生成直链
    * 提供 ``get_presigned_url(name)`` 用于生成临时下载直链
    * S3 模式下 ``file.path`` 会下载到临时文件（供 docx/PIL/fitz 等需要本地
      路径的库使用），调用方应在 ``finally`` 中调用 ``cleanup_temp_files``
      清理，或调用 ``storage.release_path(name)`` 主动释放

依赖：
    * boto3：S3 协议 SDK
"""

import os
import io
import time
import tempfile
import threading
import uuid
import logging
from urllib.parse import urljoin, urlparse, quote

from django.conf import settings
from django.core.files.storage import Storage
from django.core.exceptions import SuspiciousFileOperation
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)

# 模块级缓存：每个 StorageConfig 版本号对应一组后端实例
# 避免每次 save 都新建 client，但配置变更后会自动重建
_backend_lock = threading.Lock()
_backend_cache = {}  # {(backend_type, version, config_signature): backend_instance}
_temp_paths_registry = threading.local()  # 临时文件清理登记


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
        return urljoin(self.base_url, name).replace('\\', '/')

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

    def get_presigned_url(self, name, expiration=3600):
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
        key = quote(name, safe='/')
        if cfg.s3_custom_domain:
            base = cfg.s3_custom_domain.rstrip('/')
            # 自定义域名通常不包含 bucket
            return "%s/%s" % (base, key)
        if cfg.s3_endpoint_url:
            base = cfg.s3_endpoint_url.rstrip('/')
            if cfg.s3_use_path_style or cfg.s3_addressing_style == 'path':
                return "%s/%s/%s" % (base, cfg.s3_bucket_name, key)
            else:
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
        """给 Office Online embedding 用的直链。

        * 若配置了 custom_domain，返回 ``<custom_domain>/<key>``
        * 若 bucket 是 public-read，直接返回 ``url()``
        * 否则推荐生成 presigned URL（但 Office Online 不接受短期链接的
          部分场景，因此建议管理员在 S3 后端配置 public-read bucket 或 CDN）

        本方法返回 ``url()``，由调用方决定是否改用 ``get_presigned_url``。
        """
        return self.url(name)

    def get_presigned_url(self, name, expiration=3600):
        """生成临时下载直链（默认 1 小时）。

        用于私密 bucket 的下载场景。
        """
        client = self._get_client()
        return client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': name},
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
        try:
            from .models import StorageConfig
            return StorageConfig.get_active_config()
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
        return self._backend().save(name, content)

    def get_available_name(self, name, max_length=None):
        return self._backend().get_available_name(name, max_length)

    def exists(self, name):
        return self._backend().exists(name)

    def delete(self, name):
        return self._backend().delete(name)

    def listdir(self, path=''):
        return self._backend().listdir(path)

    def size(self, name):
        return self._backend().size(name)

    def url(self, name):
        return self._backend().url(name)

    def path(self, name):
        return self._backend().path(name)

    def open(self, name, mode='rb'):
        # Django Storage.open 期望返回 file-like 对象
        return self._backend().open(name, mode)

    # ============ 扩展接口（业务代码专用）============

    def get_public_url(self, name):
        """给 Office Online embedding 使用的直链。

        S3 模式下返回 S3/CDN 直链（不经过本站代理），
        本地模式下返回 ``MEDIA_URL + name``。
        """
        backend = self._backend()
        if hasattr(backend, 'get_public_url'):
            return backend.get_public_url(name)
        return backend.url(name)

    def get_presigned_url(self, name, expiration=3600):
        """生成下载用临时直链。

        S3 模式返回 STS 临时签名 URL（默认 1 小时）；
        本地模式返回普通 url（无签名）。
        """
        backend = self._backend()
        if hasattr(backend, 'get_presigned_url'):
            return backend.get_presigned_url(name, expiration)
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
            count = response.get('KeyCount', 0)
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
