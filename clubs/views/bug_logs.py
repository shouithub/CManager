"""管理后台 BUG 日志：查看、筛选、标记处理与删除。"""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import ErrorLog
from ..permissions import roles_required


@roles_required('admin')
@require_http_methods(['GET', 'POST'])
def manage_bug_logs(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        log_id = request.POST.get('log_id', '')
        log = get_object_or_404(ErrorLog, pk=log_id) if log_id.isdigit() else None
        if log is None:
            messages.error(request, '日志不存在')
            return redirect('clubs:manage_bug_logs')
        if action == 'resolve':
            log.resolved = True
            log.resolved_at = timezone.now()
            log.resolved_by = request.user
            log.save(update_fields=['resolved', 'resolved_at', 'resolved_by'])
            messages.success(request, '已标记为已处理')
        elif action == 'unresolve':
            log.resolved = False
            log.resolved_at = None
            log.resolved_by = None
            log.save(update_fields=['resolved', 'resolved_at', 'resolved_by'])
            messages.success(request, '已恢复为未处理')
        elif action == 'delete':
            log.delete()
            messages.success(request, '日志已删除')
        else:
            messages.error(request, '未知操作')
        return redirect(request.GET.get('next') or 'clubs:manage_bug_logs')

    filter_key = request.GET.get('status', 'unresolved')
    q = (request.GET.get('q') or '').strip()
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

    counts = {
        'unresolved': ErrorLog.objects.filter(resolved=False).count(),
        'help': ErrorLog.objects.filter(help_requested=True, resolved=False).count(),
        'resolved': ErrorLog.objects.filter(resolved=True).count(),
        'all': ErrorLog.objects.count(),
    }
    return render(request, 'clubs/admin/bug_logs.html', {
        'logs': page_obj.object_list,
        'page_obj': page_obj,
        'filter_key': filter_key,
        'q': q,
        'counts': counts,
    })
