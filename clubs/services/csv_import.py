"""CSV 批量导入的公共逻辑与反馈构建。

用户导入、社团导入、时间段导入共用这里的解析、执行与响应逻辑，
页面 UI 使用 templates/clubs/components/_csv_import_modal.html 组件。

安全约定：所有展示给用户的错误信息必须是纯字符串，禁止把异常对象或其
``str()`` 结果直接写入反馈，避免向外部用户泄露堆栈/实现细节。
"""

import csv
import io
import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect


logger = logging.getLogger(__name__)


def read_csv_upload(upload):
    """读取并解码 CSV 上传文件，返回 (DictReader, error)。

    error 非空时 reader 为 None。
    """
    if not upload:
        return None, '请选择 CSV 文件'

    raw_bytes = upload.read()
    text = None
    for encoding in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            text = raw_bytes.decode(encoding)
            break
        except Exception:
            continue
    if text is None:
        return None, 'CSV 文件编码无法识别，请使用 UTF-8 编码'

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return None, 'CSV 表头无效'
    return reader, None


def run_simple_csv_import(upload, *, required_headers, process_row, start_row=2):
    """执行简单的逐行导入。

    返回 (summary, error)：error 非空表示文件级失败，error 为可直接展示
    给用户的纯字符串；成功时 error 为 None。

    process_row(row) 返回 (status, row_error)：
    - status 为 'created' / 'updated' / 'skipped'，row_error 为空表示成功；
    - status 为 None 时，row_error 为该行的纯字符串错误信息（可展示给用户）。
    process_row 内部抛出任何异常时，该行按“数据格式错误”处理，详细原因只写入
    服务端日志，不返回给客户端。
    """
    reader, error = read_csv_upload(upload)
    if error:
        return None, error

    missing = [header for header in required_headers if header not in reader.fieldnames]
    if missing:
        return None, 'CSV 缺少必要列：' + '、'.join(missing)

    created = 0
    updated = 0
    skipped = 0
    errors = []
    for index, row in enumerate(reader, start=start_row):
        try:
            status, row_error = process_row(row)
        except Exception:
            logger.exception('CSV 导入第 %s 行失败', index)
            errors.append(f'第{index}行：数据格式错误')
            continue
        if row_error:
            errors.append(f'第{index}行：{row_error}')
            continue
        if status == 'created':
            created += 1
        elif status == 'updated':
            updated += 1
        else:
            skipped += 1

    summary = {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
    }
    return summary, None


def build_import_feedback(request, *, is_ajax, success, message, errors=None,
                          extra=None, redirect_url=None):
    """统一构造导入结果反馈：AJAX 返回 JSON，普通请求写 messages 并跳转。"""
    errors = errors or []
    if is_ajax:
        payload = {
            'success': success,
            'message': message,
            'errors': errors[:10],
        }
        if extra:
            payload.update(extra)
        return JsonResponse(payload, status=200 if success else 400)

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    if errors:
        messages.warning(request, '部分数据有问题：' + '；'.join(errors[:10]))
    return redirect(redirect_url or 'clubs:admin_dashboard')
