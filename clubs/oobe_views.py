from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .email_utils import send_test_email_with_config
from .models import SMTPConfig
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

    if request.method == 'POST':
        admin_username = request.POST.get('admin_username', '').strip()
        admin_password = request.POST.get('admin_password', '').strip()
        admin_password_confirm = request.POST.get('admin_password_confirm', '').strip()
        admin_email = request.POST.get('admin_email', '').strip()

        db_type = request.POST.get('db_type', 'sqlite').strip().lower()
        db_name = request.POST.get('db_name', '').strip()
        db_user = request.POST.get('db_user', '').strip()
        db_password = request.POST.get('db_password', '').strip()
        db_host = request.POST.get('db_host', '').strip()
        db_port = request.POST.get('db_port', '').strip()

        use_redis = request.POST.get('use_redis', 'no').strip().lower() == 'yes'
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

        if db_type not in ['sqlite', 'postgresql', 'mysql']:
            errors.append('数据库类型不支持')

        if db_type in ['postgresql', 'mysql']:
            if not db_name:
                errors.append('数据库名不能为空')
            if not db_user:
                errors.append('数据库用户名不能为空')
            if not db_host:
                errors.append('数据库主机不能为空')
            if not db_port:
                errors.append('数据库端口不能为空')

        if use_redis and not redis_url:
            errors.append('启用Redis时必须填写REDIS_URL')

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
                'form_data': request.POST,
                'db_choices': db_choices,
                'smtp_provider_choices': SMTPConfig.PROVIDER_CHOICES,
            })

        if logo_upload:
            ok, logo_message = process_site_logo(logo_upload, allow_webp=True)
            if not ok:
                return render(request, 'clubs/oobe_setup.html', {
                    'errors': [logo_message],
                    'form_data': request.POST,
                    'db_choices': db_choices,
                    'smtp_provider_choices': SMTPConfig.PROVIDER_CHOICES,
                })

        db_engine_map = {
            'sqlite': 'django.db.backends.sqlite3',
            'postgresql': 'django.db.backends.postgresql',
            'mysql': 'django.db.backends.mysql',
        }

        updates = {
            'DB_ENGINE': db_engine_map[db_type],
            'DB_CONN_MAX_AGE': '120',
            'SESSION_USE_CACHED_DB': 'True',
            'CACHE_BACKEND': 'redis' if use_redis else 'filebased',
            'CACHE_TIMEOUT': '300',
            'CACHE_KEY_PREFIX': 'cmanager-prod',
            'REDIS_URL': redis_url if use_redis else None,
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
            'OOBE 配置已保存。请重启服务后执行 `python manage.py migrate`，系统会自动完成管理员与邮箱配置初始化。'
        )
        return redirect('clubs:oobe_setup')

    return render(request, 'clubs/oobe_setup.html', {
        'db_choices': db_choices,
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
