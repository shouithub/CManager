"""管理后台 BUG 日志：查看、筛选、标记处理与删除。"""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from ..models import ErrorLog
from ..permissions import roles_required
from django.utils.translation import gettext as _


@roles_required('admin')
@require_http_methods(['GET', 'POST'])
def manage_bug_logs(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        log_id = request.POST.get('log_id', '')
        try:
            log = get_object_or_404(ErrorLog, pk=log_id) if log_id.isdigit() else None
        except Exception:
            log = None
        if log is None:
            messages.error(request, _('日志不存在或日志表尚未初始化'))
            return redirect('clubs:manage_bug_logs')
        try:
            if action == 'resolve':
                log.resolved = True
                log.resolved_at = timezone.now()
                log.resolved_by = request.user
                log.save(update_fields=['resolved', 'resolved_at', 'resolved_by'])
                messages.success(request, _('已标记为已处理'))
            elif action == 'unresolve':
                log.resolved = False
                log.resolved_at = None
                log.resolved_by = None
                log.save(update_fields=['resolved', 'resolved_at', 'resolved_by'])
                messages.success(request, _('已恢复为未处理'))
            elif action == 'delete':
                log.delete()
                messages.success(request, _('日志已删除'))
            else:
                messages.error(request, _('未知操作'))
        except Exception:
            messages.error(request, _('操作失败，请稍后重试'))
        next_url = request.GET.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect('clubs:manage_bug_logs')

    filter_key = request.GET.get('status', 'unresolved')
    q = (request.GET.get('q') or '').strip()
    try:
        logs = ErrorLog.objects.select_related('resolved_by')
        if filter_key == 'resolved':
            logs = logs.filter(resolved=True)
        elif filter_key == 'help':
            logs = logs.filter(help_requested=True, resolved=False)
        elif filter_key == 'all':
            pass
        else:
            filter_key = 'unresolved'
            logs = logs.filter(resolved=False)
        if q:
            logs = logs.filter(
                Q(path__icontains=q)
                | Q(user_identifier__icontains=q)
                | Q(exception_name__icontains=q)
                | Q(exception_message__icontains=q)
                | Q(ip__icontains=q)
                | Q(help_email__icontains=q)
            )
        paginator = Paginator(logs, 50)
        page_obj = paginator.get_page(request.GET.get('page'))
        log_rows = page_obj.object_list
    except Exception:
        # 表缺失/迁移未应用时仍渲染页面，避免管理页整体 500。
        paginator = Paginator(ErrorLog.objects.none(), 50)
        page_obj = paginator.get_page(1)
        log_rows = []

    counts = {'unresolved': 0, 'help': 0, 'resolved': 0, 'all': 0}
    try:
        counts = {
            'unresolved': ErrorLog.objects.filter(resolved=False).count(),
            'help': ErrorLog.objects.filter(help_requested=True, resolved=False).count(),
            'resolved': ErrorLog.objects.filter(resolved=True).count(),
            'all': ErrorLog.objects.count(),
        }
    except Exception:
        # 表缺失/迁移未应用时仍渲染页面，避免管理页整体 500。
        pass
    return render(request, 'clubs/admin/bug_logs.html', {
        'logs': log_rows,
        'page_obj': page_obj,
        'filter_key': filter_key,
        'q': q,
        'counts': counts,
    })
