"""自定义 404/500 错误页与用户求助入口。"""

import logging
import sys
import traceback

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..email_utils import send_email_with_config
from ..models import ErrorLog, SMTPConfig, SiteSettings

logger = logging.getLogger(__name__)


def _client_ip(request):
    """反代场景下取 X-Forwarded-For 最左侧真实 IP，与登录限速保持一致。"""
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if getattr(settings, 'USE_X_FORWARDED_FOR', False) and forwarded:
        parts = [part.strip() for part in forwarded.split(',') if part.strip()]
        if parts:
            return parts[0]
    return request.META.get('REMOTE_ADDR', '')


def _user_label(request):
    """500 时 request.user 可能不可靠，统一兜底。"""
    try:
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            return (user.username or '')[:200], (user.email or '')
    except Exception:
        logger.debug('读取错误页用户身份失败，按匿名处理', exc_info=True)
    return '', ''


def _exception_details(exception):
    """提取异常类型与完整 traceback。

    Django 生产环境对普通 500 是通过 handle_uncaught_exception 调用
    handler500(request) 的，并不会把异常对象传进来，因此需要在当前
    线程异常上下文（sys.exc_info）中兜底取回，否则日志只剩错误码。
    """
    if exception is None:
        exc_info = sys.exc_info()
        if exc_info is not None and exc_info[1] is not None:
            exception = exc_info[1]
    if exception is None:
        return '', ''
    name = type(exception).__name__
    try:
        lines = traceback.format_exception(
            type(exception), exception, getattr(exception, '__traceback__', None)
        )
        message = ''.join(lines).strip() or str(exception)
    except Exception:
        message = str(exception) or ''
    return name, message[:20000]


def error_help_enabled():
    """错误页求助按钮是否可用：站点级开关，不依赖 SMTP 配置。"""
    try:
        return bool(SiteSettings.get_settings().error_help_enabled)
    except Exception:
        logger.debug('读取站点求助开关失败，按关闭处理', exc_info=True)
        return False


def _error_context(request, status_code, error_log_id=None):
    return {
        'error_help_enabled': error_help_enabled(),
        'error_log_id': error_log_id,
        'error_status_code': status_code,
        'error_path': request.path or '/',
    }


def handler404(request, exception=None):
    """404 页面：不自动记录日志，仅渲染友好页面（求助需用户主动点击）。"""
    return render(
        request,
        'clubs/error_page.html',
        _error_context(request, 404),
        status=404,
    )


def handler500(request, exception=None):
    """500 页面：记录错误日志并渲染友好页面。"""
    log_id = None
    try:
        username, email = _user_label(request)
        exception_name, exception_message = _exception_details(exception)
        log = ErrorLog.objects.create(
            status_code=500,
            path=(request.path or '/')[:500],
            method=request.method or 'GET',
            referer=(request.META.get('HTTP_REFERER') or '')[:500],
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:500],
            ip=_client_ip(request)[:100],
            exception_name=exception_name[:200],
            exception_message=exception_message,
            user_identifier=username,
            help_email=email,
        )
        log_id = log.pk
        logger.error('已记录 500 错误日志 #%s: %s %s', log_id, request.method, request.path)
    except Exception:
        logger.exception('写入 500 错误日志失败，不影响错误页展示')
    return render(
        request,
        'clubs/error_page.html',
        _error_context(request, 500, log_id),
        status=500,
    )


def _admin_emails(config):
    """求助通知收件人：优先使用配置邮箱，否则汇总所有管理员账号邮箱。"""
    recipient = (getattr(config, 'help_recipient_email', '') or '').strip()
    if recipient:
        return [recipient]
    User = get_user_model()
    emails = set()
    try:
        from ..models import UserProfile
        for row in UserProfile.objects.filter(
            role='admin', user__email__isnull=False
        ).exclude(user__email='').values_list('user__email', flat=True):
            if row:
                emails.add(row)
        for row in User.objects.filter(
            is_superuser=True, email__isnull=False
        ).exclude(email='').values_list('email', flat=True):
            if row:
                emails.add(row)
    except Exception:
        logger.exception('查询管理员邮箱失败')
    return sorted(emails)


@require_http_methods(['POST'])
def error_help_request(request):
    """用户在错误页点击“请求帮助”：更新/新建日志并通知管理员。"""
    if not error_help_enabled():
        return JsonResponse({'success': False, 'message': '求助功能未开启'}, status=403)

    log_id = (request.POST.get('error_log_id') or '').strip()
    contact = (request.POST.get('contact_email') or '').strip()
    note = (request.POST.get('note') or '').strip()[:2000]
    error_type = (request.POST.get('error_type') or '500').strip()
    error_path = (request.POST.get('error_path') or request.path or '/').strip()[:500]

    if log_id.isdigit():
        log = ErrorLog.objects.filter(pk=log_id).first()
    else:
        log = None

    if log is None:
        # 404 页面没有自动日志，点击求助时单独建立记录。
        username, email = _user_label(request)
        log = ErrorLog(
            status_code=404 if error_type == '404' else 500,
            path=error_path,
            method='GET',
            referer=(request.META.get('HTTP_REFERER') or '')[:500],
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:500],
            ip=_client_ip(request)[:100],
            user_identifier=username,
            help_email=email or contact,
        )
        try:
            log.save()
        except Exception:
            logger.exception('写入 404 求助记录失败')
            return JsonResponse({'success': False, 'message': '提交失败，请稍后重试'}, status=500)

    log.help_requested = True
    log.help_requested_at = timezone.now()
    if contact:
        log.help_email = contact
    if note:
        log.help_note = note
    try:
        log.save(update_fields=['help_requested', 'help_requested_at', 'help_email', 'help_note'])
    except Exception:
        logger.exception('更新求助记录失败')
        return JsonResponse({'success': False, 'message': '提交失败，请稍后重试'}, status=500)

    # 发送管理员通知邮件；发送失败不影响页面反馈。
    try:
        config = SMTPConfig.get_active_config()
        if config:
            recipients = _admin_emails(config)
            if recipients:
                path_line = f"错误地址：{log.path}"
                referer_line = f"来源页面：{log.referer}" if log.referer else ''
                user_line = f"用户：{log.user_identifier or '未登录'}"
                email_line = f"联系邮箱：{log.help_email}" if log.help_email else ''
                note_line = f"用户描述：\n{log.help_note}" if log.help_note else ''
                text = (
                    "您好！\n\n"
                    "有用户在使用 CManager 时遇到了问题并请求帮助。\n\n"
                    f"日志编号：{log.pk}\n"
                    f"错误类型：{log.get_status_code_display()}\n"
                    f"{path_line}\n"
                    f"{referer_line}\n"
                    f"{user_line}\n"
                    f"{email_line}\n"
                    f"发生时间：{timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"{note_line}\n\n"
                    "请登录管理后台查看 BUG 日志处理。\n"
                    "此邮件由系统自动发送，请勿直接回复。"
                )
                for recipient in recipients:
                    try:
                        send_email_with_config(
                            config=config,
                            to_email=recipient,
                            subject=f'[CManager] 用户请求帮助（日志 #{log.pk}）',
                            text_body=text,
                        )
                    except Exception:
                        logger.exception('发送求助通知邮件给 %s 失败', recipient)
    except Exception:
        logger.exception('发送求助通知邮件失败')

    return JsonResponse({'success': True, 'message': '已提交求助，管理员会尽快联系你'})
