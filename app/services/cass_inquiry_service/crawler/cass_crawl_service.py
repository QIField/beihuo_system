"""
卡思商城爬取编排 + 内存任务管理

- 分页由原脚本递归改为 while 循环（多页日期范围避免递归爆栈）
- 询单明细 code != 200 时走归档接口（与原脚本 mingxi->mx2 一致），
  归档 data.status != SUCCESS 时跳过该询单（与原脚本一致，记入 failed 说明）
- 单个询单解析异常不中断任务，记入 failed 后继续
- 入库前不落盘、cookie 仅存内存并随任务结束保留（状态查询已剥离）
"""

import threading
import time
import uuid

from app.services.cass_inquiry_service.crawler import cass_client, cass_parser
from app.services.cass_inquiry_service.crawler.cass_quote_writer import save_quote_rows

VIEW_SIZE = 200  # 列表页每页条数（与原脚本一致）

_JOBS = {}
_JOBS_LOCK = threading.Lock()
_MAX_FINISHED_JOBS = 50


def start_job(start_date, end_date, cookie):
    """创建并启动爬取任务，返回 task_id"""
    task_id = uuid.uuid4().hex
    job = {
        'task_id': task_id,
        'status': 'running',  # running / done / failed
        'start_date': start_date,
        'end_date': end_date,
        'cookie': cookie,
        'page': 0,
        'total_pages': 0,
        'inquiry_done': 0,
        'rows_collected': 0,
        'rows_saved': 0,
        'failed': [],
        'result': None,
        'error': None,
        'created_time': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    with _JOBS_LOCK:
        _cleanup_finished_jobs_locked()
        _JOBS[task_id] = job
    thread = threading.Thread(target=_run, args=(job,), daemon=True)
    thread.start()
    return task_id


def get_job(task_id):
    """查询任务快照（剥离 cookie，不对外暴露）"""
    with _JOBS_LOCK:
        job = _JOBS.get(task_id)
        if not job:
            return None
        return {k: v for k, v in job.items() if k != 'cookie'}


def _run(job):
    """线程入口：执行爬取并入库，更新任务状态"""
    try:
        result = run_crawl(
            job['start_date'], job['end_date'], job['cookie'],
            on_page=lambda page, total: _update(job, page=page, total_pages=total),
            on_inquiry=lambda done: _update(job, inquiry_done=done),
            on_rows=lambda count: _update(job, rows_collected=count),
            on_saved=lambda count: _update(job, rows_saved=count),
            on_failed=lambda note: _update(job, failed=job['failed'] + [note]),
        )
        _update(job, status='done', result=result)
    except Exception as e:  # 任务级失败（如列表页请求失败、cookie 失效）
        _update(job, status='failed', error=str(e))


def _update(job, **fields):
    with _JOBS_LOCK:
        job.update(fields)


def run_crawl(start_date, end_date, cookie, on_page=None, on_inquiry=None,
              on_rows=None, on_saved=None, on_failed=None):
    """
    执行爬取：列表分页 -> 逐询单明细解析 -> 全量入库

    :return: {'rows_collected': n, 'rows_saved': n, 'failed_count': n, 'failed': [...]}
    """
    import requests

    records = []
    failed = []
    session = requests.Session()
    view_index = 1
    total_pages = 0
    inquiry_done = 0

    while True:
        html = cass_client.fetch_list_page(session, cookie, view_index, VIEW_SIZE,
                                           start_date, end_date)
        if html is None:
            raise RuntimeError(f'列表页访问失败（第 {view_index} 页），请检查 cookie 是否有效')
        parsed = cass_parser.parse_list_page(html)
        total_pages = parsed['total_pages']
        if on_page:
            on_page(view_index, total_pages)

        for row in parsed['rows']:
            if len(row['inquiryid']) < 5:  # 与原脚本一致：异常短 ID 跳过
                inquiry_done += 1
                if on_inquiry:
                    on_inquiry(inquiry_done)
                continue
            try:
                records.extend(_fetch_inquiry_records(session, cookie, row, on_failed))
            except Exception as e:
                note = {'inquiryid': row['inquiryid'], 'error': str(e)}
                failed.append(note)
                if on_failed:
                    on_failed(note)
            inquiry_done += 1
            if on_inquiry:
                on_inquiry(inquiry_done)
            if on_rows:
                on_rows(len(records))

        if total_pages <= view_index:  # 总页码不大于当前页码，结束
            break
        view_index += 1

    rows_saved = save_quote_rows(records, on_saved=on_saved)
    return {'rows_collected': len(records), 'rows_saved': rows_saved,
            'failed_count': len(failed), 'failed': failed}


def _fetch_inquiry_records(session, cookie, row, failed_notes=None):
    """获取单个询单的全部报价行：明细接口 code!=200 时走归档接口"""
    payload = cass_client.fetch_detail(session, cookie, row['inquiryid'])
    if payload.get('code') == 200:
        guide_map = cass_client.fetch_purchase_guide(session, cookie, row['inquiryid'])
        return cass_parser.parse_detail(payload, row, guide_map)

    # 归档明细
    archive = cass_client.fetch_archive_detail(session, cookie, row['inquiryid'])
    data = archive.get('data') if isinstance(archive, dict) else None
    if not isinstance(data, dict) or data.get('status') != 'SUCCESS':
        # 与原脚本一致：归档状态非 SUCCESS 跳过该询单
        if failed_notes is not None:
            note = {'inquiryid': row['inquiryid'], 'error': '归档明细状态非 SUCCESS，已跳过'}
            failed_notes.append(note)
        return []
    guide_map = cass_client.fetch_purchase_guide(session, cookie, row['inquiryid'])
    return cass_parser.parse_archive_detail(archive, row, guide_map, row['inquiryid'])


def _cleanup_finished_jobs_locked():
    """清理最旧的已完成任务，防止长期运行内存增长（调用方需持有锁）"""
    finished = [k for k, v in _JOBS.items() if v['status'] in ('done', 'failed')]
    if len(finished) < _MAX_FINISHED_JOBS:
        return
    finished.sort(key=lambda k: _JOBS[k]['created_time'])
    for k in finished[:len(finished) - _MAX_FINISHED_JOBS + 1]:
        _JOBS.pop(k, None)
