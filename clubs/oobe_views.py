import secrets
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _

from .email_utils import send_test_email_with_config
from .models import SMTPConfig, UserProfile
from .oobe_bootstrap import has_admin_user, write_pending_oobe_setup
from .site_assets import process_site_logo


def _write_env_local(updates: dict):
    env_path = Path(settings.BASE_DIR) / '.env.local'
    current = {}

    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            raw = line.strip()
            if not raw or raw.startswith('#') or '=' not in raw:
                continue
            key, value = raw.split('=', 1)
            current[key.strip()] = value.strip()

    for key, value in updates.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = str(value)

    content = '\n'.join([f'{key}={value}' for key, value in current.items()]) + '\n'
    env_path.write_text(content, encoding='utf-8')


def _parse_bool(raw_value, default=False):
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in ['1', 'true', 'yes', 'on']


def _parse_int(raw_value, default=0):
    if raw_value in [None, '']:
        return default
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return default


def _default_form_data():
    return {
        'secret_key': secrets.token_urlsafe(48),
        'debug': 'no',
        'allowed_hosts': 'localhost,127.0.0.1',
        'csrf_trusted_origins': 'http://127.0.0.1,http://localhost',
        'secure_browser_xss_filter': 'yes',
        'secure_content_type_nosniff': 'yes',
        'session_cookie_secure': 'no',
        'csrf_cookie_secure': 'no',
        'x_frame_options': 'DENY',
        'db_type': 'sqlite',
        'db_conn_max_age': '120',
        'sqlite_conn_max_age': '120',
        'sqlite_timeout': '30',
        'sqlite_synchronous': 'NORMAL',
        'sqlite_cache_size': '-20000',
        'sqlite_mmap_size': '134217728',
        'cache_backend': 'filebased',
        'cache_location': 'cmanager-default-cache',
        'cache_timeout': '300',
        'cache_key_prefix': 'cmanager-prod',
        'session_use_cached_db': 'yes',
        'enable_email': 'no',
        'email_provider': 'qq',
        'smtp_use_tls': 'yes',
        'admin_real_name': '',
        'admin_student_id': '',
        'admin_phone': '',
        'admin_wechat': '',
        'admin_political_status': 'non_member',
        'admin_is_info_public': 'no',
    }


@require_http_methods(['GET', 'POST'])
def oobe_setup(request):
    if has_admin_user():
        return redirect('clubs:login')

    db_choices = [
        ('sqlite', 'SQLite（部署简单，单机轻量，写并发能力有限）'),
        ('postgresql', 'PostgreSQL（事务强、并发好、上线推荐）'),
        ('mysql', 'MySQL（生态成熟、并发好、运维常见）'),
    ]
    smtp_defaults = {
        'qq': ('smtp.qq.com', 587),
        '163': ('smtp.163.com', 994),
        'outlook': ('smtp-mail.outlook.com', 587),
        'gmail': ('smtp.gmail.com', 587),
        'custom': ('', 587),
    }
    frame_option_choices = ['DENY', 'SAMEORIGIN']
    cache_backend_choices = [
        ('filebased', '文件缓存（推荐默认）'),
        ('redis', 'Redis 缓存（生产推荐）'),
        ('locmem', '内存缓存（单进程开发环境）'),
        ('dummy', '禁用缓存（排障用）'),
    ]
    political_status_choices = UserProfile.POLITICAL_STATUS_CHOICES
    political_status_values = {value for value, _label in political_status_choices}
    base_form_data = _default_form_data()

    if request.method == 'POST':
        form_data = base_form_data.copy()
        form_data.update(request.POST.dict())

        admin_username = request.POST.get('admin_username', '').strip()
        admin_password = request.POST.get('admin_password', '').strip()
        admin_password_confirm = request.POST.get('admin_password_confirm', '').strip()
        admin_email = request.POST.get('admin_email', '').strip()
        admin_real_name = request.POST.get('admin_real_name', '').strip()
        admin_student_id = request.POST.get('admin_student_id', '').strip()
        admin_phone = request.POST.get('admin_phone', '').strip()
        admin_wechat = request.POST.get('admin_wechat', '').strip()
        admin_political_status = request.POST.get('admin_political_status', 'non_member').strip()
        admin_is_info_public = _parse_bool(request.POST.get('admin_is_info_public', 'no'), default=False)

        secret_key = request.POST.get('secret_key', '').strip()
        debug_mode = _parse_bool(request.POST.get('debug', 'no'), default=False)
        allowed_hosts = request.POST.get('allowed_hosts', '').strip()
        csrf_trusted_origins = request.POST.get('csrf_trusted_origins', '').strip()
        secure_browser_xss_filter = _parse_bool(request.POST.get('secure_browser_xss_filter', 'yes'), default=True)
        secure_content_type_nosniff = _parse_bool(request.POST.get('secure_content_type_nosniff', 'yes'), default=True)
        session_cookie_secure = _parse_bool(request.POST.get('session_cookie_secure', 'no'), default=False)
        csrf_cookie_secure = _parse_bool(request.POST.get('csrf_cookie_secure', 'no'), default=False)
        x_frame_options = request.POST.get('x_frame_options', 'DENY').strip().upper()

        db_type = request.POST.get('db_type', 'sqlite').strip().lower()
        db_name = request.POST.get('db_name', '').strip()
        db_user = request.POST.get('db_user', '').strip()
        db_password = request.POST.get('db_password', '').strip()
        db_host = request.POST.get('db_host', '').strip()
        db_port = request.POST.get('db_port', '').strip()
        db_conn_max_age = _parse_int(request.POST.get('db_conn_max_age', '120'), default=120)
        sqlite_conn_max_age = _parse_int(request.POST.get('sqlite_conn_max_age', '120'), default=120)
        sqlite_timeout = _parse_int(request.POST.get('sqlite_timeout', '30'), default=30)
        sqlite_synchronous = request.POST.get('sqlite_synchronous', 'NORMAL').strip().upper() or 'NORMAL'
        sqlite_cache_size = _parse_int(request.POST.get('sqlite_cache_size', '-20000'), default=-20000)
        sqlite_mmap_size = _parse_int(request.POST.get('sqlite_mmap_size', '134217728'), default=134217728)

        cache_backend = request.POST.get('cache_backend', '').strip().lower()
        if not cache_backend:
            use_redis = request.POST.get('use_redis', 'no').strip().lower() == 'yes'
            cache_backend = 'redis' if use_redis else 'filebased'
        cache_location = request.POST.get('cache_location', '').strip()
        cache_timeout = _parse_int(request.POST.get('cache_timeout', '300'), default=300)
        cache_key_prefix = request.POST.get('cache_key_prefix', '').strip()
        session_use_cached_db = _parse_bool(request.POST.get('session_use_cached_db', 'yes'), default=True)
        redis_url = request.POST.get('redis_url', '').strip()

        enable_email = request.POST.get('enable_email', 'no').strip().lower() == 'yes'
        email_provider = request.POST.get('email_provider', 'qq').strip().lower()
        smtp_host = request.POST.get('smtp_host', '').strip()
        smtp_port_raw = request.POST.get('smtp_port', '').strip()
        sender_email = request.POST.get('sender_email', '').strip()
        sender_password = request.POST.get('sender_password', '').strip()
        smtp_use_tls = request.POST.get('smtp_use_tls', 'yes').strip().lower() == 'yes'

        logo_upload = request.FILES.get('site_logo')

        errors = []
        if not admin_username:
            errors.append('管理员用户名不能为空')

        if not admin_password:
            errors.append('管理员密码不能为空')
        elif len(admin_password) < 6:
            errors.append('管理员密码至少6位')

        if admin_password != admin_password_confirm:
            errors.append('两次管理员密码不一致')

        if admin_political_status not in political_status_values:
            errors.append('政治面貌选项不支持')

        if not secret_key:
            errors.append('SECRET_KEY 不能为空')

        if not allowed_hosts:
            errors.append('ALLOWED_HOSTS 不能为空')

        if not csrf_trusted_origins:
            errors.append('CSRF_TRUSTED_ORIGINS 不能为空')

        if x_frame_options not in frame_option_choices:
            errors.append('X_FRAME_OPTIONS 仅支持 DENY 或 SAMEORIGIN')

        if db_type not in ['sqlite', 'postgresql', 'mysql']:
            errors.append('数据库类型不支持')

        if db_conn_max_age < 0:
            errors.append('DB_CONN_MAX_AGE 不能小于 0')

        if sqlite_conn_max_age < 0:
            errors.append('SQLITE_CONN_MAX_AGE 不能小于 0')

        if sqlite_timeout <= 0:
            errors.append('SQLITE_TIMEOUT 必须大于 0')

        if sqlite_synchronous not in ['OFF', 'NORMAL', 'FULL', 'EXTRA']:
            errors.append('SQLITE_SYNCHRONOUS 仅支持 OFF/NORMAL/FULL/EXTRA')

        if sqlite_mmap_size < 0:
            errors.append('SQLITE_MMAP_SIZE 不能小于 0')

        if cache_backend not in ['filebased', 'redis', 'locmem', 'dummy']:
            errors.append('缓存后端不支持')

        if cache_timeout < 0:
            errors.append('CACHE_TIMEOUT 不能小于 0')

        if not cache_key_prefix:
            errors.append('CACHE_KEY_PREFIX 不能为空')

        if db_type in ['postgresql', 'mysql']:
            if not db_name:
                errors.append('数据库名不能为空')
            if not db_user:
                errors.append('数据库用户名不能为空')
            if not db_host:
                errors.append('数据库主机不能为空')
            if not db_port:
                errors.append('数据库端口不能为空')

        if cache_backend == 'redis' and not redis_url:
            errors.append('启用 Redis 缓存时必须填写 REDIS_URL')

        if cache_backend == 'locmem' and not cache_location:
            errors.append('使用 locmem 缓存时必须填写 CACHE_LOCATION')

        smtp_port = 0
        if enable_email:
            if email_provider not in ['qq', '163', 'outlook', 'gmail', 'custom']:
                errors.append('邮箱服务商不支持')

            if not smtp_host and email_provider in smtp_defaults:
                smtp_host = smtp_defaults[email_provider][0]

            if not smtp_port_raw and email_provider in smtp_defaults:
                smtp_port_raw = str(smtp_defaults[email_provider][1])

            if not smtp_host:
                errors.append('启用邮箱时必须填写SMTP服务器地址')

            try:
                smtp_port = int(smtp_port_raw)
                if smtp_port <= 0:
                    raise ValueError('invalid')
            except Exception:
                errors.append('SMTP端口必须为正整数')

            if not sender_email:
                errors.append('启用邮箱时必须填写发送邮箱')
            if not sender_password:
                errors.append('启用邮箱时必须填写邮箱密码/授权码')

        if errors:
            return render(request, 'clubs/oobe_setup.html', {
                'errors': errors,
                'form_data': form_data,
                'db_choices': db_choices,
                'frame_option_choices': frame_option_choices,
                'cache_backend_choices': cache_backend_choices,
                'political_status_choices': political_status_choices,
                'smtp_provider_choices': SMTPConfig.PROVIDER_CHOICES,
            })

        if logo_upload:
            ok, logo_message = process_site_logo(logo_upload, allow_webp=True)
            if not ok:
                return render(request, 'clubs/oobe_setup.html', {
                    'errors': [logo_message],
                    'form_data': form_data,
                    'db_choices': db_choices,
                    'frame_option_choices': frame_option_choices,
                    'cache_backend_choices': cache_backend_choices,
                    'political_status_choices': political_status_choices,
                    'smtp_provider_choices': SMTPConfig.PROVIDER_CHOICES,
                })

        db_engine_map = {
            'sqlite': 'django.db.backends.sqlite3',
            'postgresql': 'django.db.backends.postgresql',
            'mysql': 'django.db.backends.mysql',
        }

        updates = {
            'SECRET_KEY': secret_key,
            'DEBUG': 'True' if debug_mode else 'False',
            'ALLOWED_HOSTS': allowed_hosts,
            'CSRF_TRUSTED_ORIGINS': csrf_trusted_origins,
            'SECURE_BROWSER_XSS_FILTER': 'True' if secure_browser_xss_filter else 'False',
            'SECURE_CONTENT_TYPE_NOSNIFF': 'True' if secure_content_type_nosniff else 'False',
            'SESSION_COOKIE_SECURE': 'True' if session_cookie_secure else 'False',
            'CSRF_COOKIE_SECURE': 'True' if csrf_cookie_secure else 'False',
            'X_FRAME_OPTIONS': x_frame_options,
            'DB_ENGINE': db_engine_map[db_type],
            'DB_CONN_MAX_AGE': db_conn_max_age,
            'SQLITE_CONN_MAX_AGE': sqlite_conn_max_age,
            'SQLITE_TIMEOUT': sqlite_timeout,
            'SQLITE_SYNCHRONOUS': sqlite_synchronous,
            'SQLITE_CACHE_SIZE': sqlite_cache_size,
            'SQLITE_MMAP_SIZE': sqlite_mmap_size,
            'SESSION_USE_CACHED_DB': 'True' if session_use_cached_db else 'False',
            'CACHE_BACKEND': cache_backend,
            'CACHE_LOCATION': cache_location if cache_backend == 'locmem' else None,
            'CACHE_TIMEOUT': cache_timeout,
            'CACHE_KEY_PREFIX': cache_key_prefix,
            'REDIS_URL': redis_url if cache_backend == 'redis' else None,
            'ADMIN_CONTACT_EMAIL': admin_email or None,
        }

        if db_type == 'sqlite':
            updates.update({
                'DB_NAME': db_name or 'db.sqlite3',
                'DB_USER': None,
                'DB_PASSWORD': None,
                'DB_HOST': None,
                'DB_PORT': None,
            })
        else:
            updates.update({
                'DB_NAME': db_name,
                'DB_USER': db_user,
                'DB_PASSWORD': db_password,
                'DB_HOST': db_host,
                'DB_PORT': db_port,
            })

        if enable_email:
            updates.update({
                'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
                'EMAIL_HOST': smtp_host,
                'EMAIL_PORT': smtp_port,
                'EMAIL_HOST_USER': sender_email,
                'EMAIL_HOST_PASSWORD': sender_password,
                'EMAIL_USE_TLS': 'True' if smtp_use_tls else 'False',
                'DEFAULT_FROM_EMAIL': sender_email,
            })
        else:
            updates.update({
                'EMAIL_BACKEND': 'django.core.mail.backends.console.EmailBackend',
                'EMAIL_HOST': None,
                'EMAIL_PORT': None,
                'EMAIL_HOST_USER': None,
                'EMAIL_HOST_PASSWORD': None,
                'EMAIL_USE_TLS': None,
                'DEFAULT_FROM_EMAIL': None,
            })

        _write_env_local(updates)
        write_pending_oobe_setup({
            'admin': {
                'username': admin_username,
                'password': admin_password,
                'email': admin_email,
                'real_name': admin_real_name,
                'student_id': admin_student_id,
                'phone': admin_phone,
                'wechat': admin_wechat,
                'political_status': admin_political_status,
                'is_info_public': admin_is_info_public,
            },
            'email': {
                'enable_email': enable_email,
                'provider': email_provider,
                'smtp_host': smtp_host,
                'smtp_port': smtp_port,
                'sender_email': sender_email,
                'sender_password': sender_password,
                'smtp_use_tls': smtp_use_tls,
            },
        })

        messages.success(
            request,
            'OOBE 配置已保存。请重启服务，系统会自动执行数据库迁移并完成管理员与邮箱配置初始化。'
        )
        return redirect('clubs:oobe_setup')

    return render(request, 'clubs/oobe_setup.html', {
        'form_data': base_form_data,
        'db_choices': db_choices,
        'frame_option_choices': frame_option_choices,
        'cache_backend_choices': cache_backend_choices,
        'political_status_choices': political_status_choices,
        'smtp_provider_choices': SMTPConfig.PROVIDER_CHOICES,
    })


@require_http_methods(['POST'])
def oobe_test_email(request):
    if has_admin_user():
        return JsonResponse({'ok': False, 'message': '系统已初始化，测试入口已关闭'}, status=403)

    provider_choices = dict(SMTPConfig.PROVIDER_CHOICES)

    sender_email = request.POST.get('sender_email', '').strip()
    sender_password = request.POST.get('sender_password', '').strip()
    smtp_host = request.POST.get('smtp_host', '').strip()
    smtp_port_raw = request.POST.get('smtp_port', '').strip()
    smtp_use_tls = request.POST.get('smtp_use_tls', 'yes').strip().lower() == 'yes'
    test_to_email = request.POST.get('test_to_email', '').strip()
    provider = request.POST.get('email_provider', 'custom').strip().lower() or 'custom'

    if not sender_email or not sender_password or not smtp_host or not smtp_port_raw or not test_to_email:
        return JsonResponse({'ok': False, 'message': '请完整填写SMTP与测试收件邮箱信息'}, status=400)

    try:
        smtp_port = int(smtp_port_raw)
        if smtp_port <= 0:
            raise ValueError('port')
    except Exception:
        return JsonResponse({'ok': False, 'message': 'SMTP端口必须为正整数'}, status=400)

    temp_config = SMTPConfig(
        provider=provider if provider in provider_choices else 'custom',
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        sender_email=sender_email,
        sender_password=sender_password,
        use_tls=smtp_use_tls,
        is_active=False,
    )

    success, message = send_test_email_with_config(temp_config, test_to_email)
    if success:
        return JsonResponse({'ok': True, 'message': message})
    return JsonResponse({'ok': False, 'message': message}, status=400)
