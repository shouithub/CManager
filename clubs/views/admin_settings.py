"""Administrator-only infrastructure configuration views.

Keeping credential-bearing settings out of the general view module makes their
authorization, secret-preservation and audit behaviour easier to review.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from ..email_utils import send_test_email_with_config
from ..models import ConfigChangeLog, SMTPConfig, StorageConfig
from ..permissions import roles_required
from ..storage_backends import ClubStorage


@roles_required('admin')
@require_http_methods(['GET', 'POST'])
def manage_smtp_config(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        config_id = request.POST.get('config_id', '')
        if action in {'create', 'edit'}:
            config = get_object_or_404(SMTPConfig, pk=config_id) if action == 'edit' else SMTPConfig()
            provider = request.POST.get('provider', '').strip()
            smtp_host = request.POST.get('smtp_host', '').strip()
            smtp_port = request.POST.get('smtp_port', '').strip()
            sender_email = request.POST.get('sender_email', '').strip()
            sender_password = request.POST.get('sender_password', '').strip()
            if not provider or not smtp_host or not smtp_port or not sender_email:
                messages.error(request, '请完整填写 SMTP 配置')
                return redirect('clubs:manage_smtp_config')
            if action == 'create' and not sender_password:
                messages.error(request, '新建 SMTP 配置时必须填写密码或授权码')
                return redirect('clubs:manage_smtp_config')
            try:
                config.smtp_port = int(smtp_port)
            except ValueError:
                messages.error(request, 'SMTP 端口必须是数字')
                return redirect('clubs:manage_smtp_config')
            if request.POST.get('is_active') == 'on':
                SMTPConfig.objects.all().update(is_active=False)
            config.provider = provider
            config.smtp_host = smtp_host
            config.sender_email = sender_email
            if sender_password:
                config.sender_password = sender_password
            config.use_tls = request.POST.get('use_tls') == 'on'
            config.is_active = request.POST.get('is_active') == 'on'
            config.save()
            ConfigChangeLog.objects.create(actor=request.user, category='smtp', action=action)
            messages.success(request, 'SMTP 配置已保存')
            return redirect('clubs:manage_smtp_config')
        if action == 'delete':
            get_object_or_404(SMTPConfig, pk=config_id).delete()
            ConfigChangeLog.objects.create(actor=request.user, category='smtp', action='delete')
            messages.success(request, 'SMTP 配置已删除')
            return redirect('clubs:manage_smtp_config')
        if action == 'activate':
            SMTPConfig.objects.all().update(is_active=False)
            config = get_object_or_404(SMTPConfig, pk=config_id)
            config.is_active = True
            config.save(update_fields=['is_active'])
            ConfigChangeLog.objects.create(actor=request.user, category='smtp', action='activate')
            messages.success(request, 'SMTP 配置已启用')
            return redirect('clubs:manage_smtp_config')
        if action == 'test_email':
            config = get_object_or_404(SMTPConfig, pk=config_id)
            test_email = request.POST.get('test_email', '').strip()
            if not test_email:
                messages.error(request, '请填写测试收件邮箱')
                return redirect('clubs:manage_smtp_config')
            success, msg = send_test_email_with_config(config, test_email)
            messages.success(request, msg) if success else messages.error(request, msg)
            return redirect('clubs:manage_smtp_config')

    return render(request, 'clubs/admin/smtp_config.html', {'configs': SMTPConfig.objects.all()})


@roles_required('admin')
@require_http_methods(['GET', 'POST'])
def manage_storage_config(request):
    """Configure local/S3 storage without ever echoing a persisted secret."""
    config = StorageConfig.get_active_config()
    errors = []

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'reset_local':
            config.backend_type = 'local'
            config.is_active = True
            config.save()
            ConfigChangeLog.objects.create(actor=request.user, category='storage', action='reset_local')
            messages.success(request, '已紧急回退到本地存储')
            return redirect('clubs:manage_storage_config')

        if action == 'test':
            test_cfg = {
                's3_endpoint_url': request.POST.get('s3_endpoint_url', '').strip(),
                's3_region': request.POST.get('s3_region', '').strip(),
                's3_bucket_name': request.POST.get('s3_bucket_name', '').strip(),
                's3_access_key_id': request.POST.get('s3_access_key_id', '').strip(),
                's3_secret_access_key': request.POST.get('s3_secret_access_key', '').strip() or config.s3_secret_access_key,
                's3_addressing_style': request.POST.get('s3_addressing_style', 'auto').strip(),
            }
            if not test_cfg['s3_bucket_name'] or not test_cfg['s3_access_key_id'] or not test_cfg['s3_secret_access_key']:
                errors.append('测试 S3 连接时必须填写 bucket / AK / SK')
                test_result = (False, '缺少必填字段')
            else:
                test_result = ClubStorage().test_s3_connection(test_cfg)
                if test_result[0]:
                    messages.success(request, test_result[1])
                else:
                    errors.append(test_result[1])
            return render(request, 'clubs/admin/storage_config.html', {
                'config': config,
                'test_result': test_result,
                'errors': errors,
                'test_form': {**test_cfg, 's3_secret_access_key': ''},
            })

        if action == 'save':
            backend_type = request.POST.get('backend_type', 'local').strip()
            if backend_type not in {'local', 's3'}:
                errors.append('后端类型必须是 local 或 s3')
            else:
                config.backend_type = backend_type
                config.is_active = request.POST.get('is_active') == 'on'
                config.s3_endpoint_url = request.POST.get('s3_endpoint_url', '').strip()
                config.s3_region = request.POST.get('s3_region', '').strip()
                config.s3_bucket_name = request.POST.get('s3_bucket_name', '').strip()
                config.s3_access_key_id = request.POST.get('s3_access_key_id', '').strip()
                new_secret = request.POST.get('s3_secret_access_key', '').strip()
                if new_secret:
                    config.s3_secret_access_key = new_secret
                elif not config.s3_secret_access_key and backend_type == 's3':
                    errors.append('切换到 S3 时必须填写 Secret Access Key')
                config.s3_custom_domain = request.POST.get('s3_custom_domain', '').strip()
                config.s3_addressing_style = request.POST.get('s3_addressing_style', 'auto').strip()
                config.s3_use_path_style = request.POST.get('s3_use_path_style') == 'on'
                try:
                    config.presigned_url_expiration = int(request.POST.get('presigned_url_expiration', '3600') or 3600)
                except ValueError:
                    errors.append('预签名有效期必须是数字')

                if backend_type == 's3' and not errors:
                    ok, msg = ClubStorage().test_s3_connection({
                        's3_endpoint_url': config.s3_endpoint_url,
                        's3_region': config.s3_region,
                        's3_bucket_name': config.s3_bucket_name,
                        's3_access_key_id': config.s3_access_key_id,
                        's3_secret_access_key': config.s3_secret_access_key,
                        's3_addressing_style': config.s3_addressing_style,
                    })
                    if not ok:
                        errors.append(f'S3 连接测试失败：{msg}')
                    else:
                        messages.success(request, 'S3 连接测试通过')

                if not errors:
                    config.save()
                    ConfigChangeLog.objects.create(actor=request.user, category='storage', action='save')
                    messages.success(request, '存储配置已保存')
                    return redirect('clubs:manage_storage_config')

    return render(request, 'clubs/admin/storage_config.html', {
        'config': config,
        'test_result': None,
        'errors': errors,
        'test_form': None,
    })
