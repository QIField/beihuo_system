# -*- coding:utf-8 -*-
"""
异步导出支持

将大数据量导出任务提交到后台线程执行，前端通过 task_id 轮询进度并下载。
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.async_task_store import submit_excel_task
from app.utils.logger_config import get_task_logger

from .core import DataProvider, ExportConfig, export_multi_sheets
from .exporters import ExcelExporter, get_exporter


logger = get_task_logger('ks_inquiry_export')

_EXPORT_TEMP_DIR = tempfile.gettempdir()
_EXPORT_FILE_MAX_AGE_HOURS = 24
_EXPORT_FILENAME_PREFIX = '指挥总看板_'


def _build_output_path(filename: str) -> str:
    """生成异步导出文件落盘路径。"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = filename.replace('{timestamp}', timestamp)
    if not safe_filename.endswith('.xlsx'):
        safe_filename += '.xlsx'
    return os.path.join(_EXPORT_TEMP_DIR, safe_filename)


def _notify_progress(
    progress_callback: Optional[Callable[[int, int, str], None]],
    progress: int,
    message: str,
) -> None:
    """安全地触发进度回调。"""
    if not progress_callback:
        return
    try:
        progress_callback(progress, 100, message)
    except Exception:
        pass


def _save_export_response(
    response: Any,
    output_path: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> None:
    """将 Response 数据写入文件，并触发写入进度。"""
    _notify_progress(progress_callback, 90, '正在写入文件...')
    with open(output_path, 'wb') as f:
        f.write(response.get_data())
    _notify_progress(progress_callback, 100, '处理完成')


def cleanup_expired_exports(max_age_hours: int = _EXPORT_FILE_MAX_AGE_HOURS) -> None:
    """清理过期的临时导出文件。"""
    try:
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        removed = 0
        for name in os.listdir(_EXPORT_TEMP_DIR):
            if not name.startswith(_EXPORT_FILENAME_PREFIX) or not name.endswith('.xlsx'):
                continue
            path = os.path.join(_EXPORT_TEMP_DIR, name)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                if mtime < cutoff:
                    os.remove(path)
                    removed += 1
            except Exception:
                pass
        if removed:
            logger.info('[async_export] 清理 %s 个过期临时导出文件', removed)
    except Exception as e:
        logger.warning('[async_export] 清理过期导出文件失败: %s', e)


def remove_export_file(path: str) -> None:
    """删除已下载的临时导出文件。"""
    if not path or not os.path.exists(path):
        return
    try:
        os.remove(path)
        logger.info('[async_export] 已删除下载后的临时文件: %s', path)
    except Exception as e:
        logger.warning('[async_export] 删除临时文件失败: %s', e)


def _async_export_wrapper(
    config: ExportConfig,
    fetcher: Callable[..., List[Dict[str, Any]]],
    search_params: Dict[str, Any],
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> str:
    """
    异步导出任务包装函数。

    Args:
        config: 导出配置
        fetcher: 数据获取函数
        search_params: 搜索条件
        progress_callback: 进度回调

    Returns:
        生成的文件路径
    """
    _notify_progress(progress_callback, 0, '正在准备导出...')
    logger.info('[async_export] 开始单 Sheet 导出，参数: %s', search_params)

    _notify_progress(progress_callback, 10, '正在查询数据...')
    data = fetcher(progress_callback=progress_callback, **search_params)

    if not data:
        logger.warning('[async_export] 查询结果为空，无数据可导出')
        raise ValueError('没有数据可导出')

    total = len(data)
    logger.info('[async_export] 查询完成，共 %s 条数据', total)
    _notify_progress(progress_callback, 40, f'已查询 {total} 条数据，正在生成文件...')

    prepared_data = config.prepare_data(data)
    output_path = _build_output_path(config.get_filename())

    exporter = config.build_exporter()
    response = exporter.export(
        prepared_data,
        filename=os.path.basename(output_path),
        sheet_name=config.sheet_name,
    )

    _save_export_response(response, output_path, progress_callback)
    logger.info('[async_export] 导出文件已生成: %s', output_path)

    return output_path


def _prepare_sheet_data(
    sheet: Dict[str, Any],
    progress_callback: Optional[Callable[[int, int, str], None]],
    base_progress: int,
) -> Tuple[Optional[Dict[str, Any]], int]:
    """获取并准备一个 Sheet 的导出数据；返回 (配置, 原始数据条数)。"""
    config = sheet.get('config')
    sheet_name = sheet.get('sheet_name', 'Sheet')

    _notify_progress(progress_callback, base_progress + 5, f'正在查询「{sheet_name}」...')

    data = sheet.get('data')
    if data is None and 'fetcher' in sheet:
        try:
            data = sheet['fetcher'](progress_callback=progress_callback, **sheet.get('search_params', {}))
        except Exception as e:
            logger.exception('[async_export] 查询「%s」数据失败: %s', sheet_name, e)
            raise

    if not data:
        logger.warning('[async_export] 「%s」查询结果为空，跳过该 Sheet', sheet_name)
        return None, 0

    count = len(data)
    logger.info('[async_export] 「%s」查询完成，共 %s 条数据', sheet_name, count)
    _notify_progress(progress_callback, base_progress + 15, f'已查询「{sheet_name}」{count} 条数据...')

    return {
        'sheet_name': sheet_name,
        'fields': config.fields,
        'headers': config.headers,
        'data': config.prepare_data(data),
    }, count


def _async_multi_sheet_export_wrapper(
    sheets_config: List[Dict[str, Any]],
    filename: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> str:
    """
    多 Sheet 异步导出任务包装函数。

    Args:
        sheets_config: 每个 sheet 的配置，格式：
            {
                'sheet_name': str,
                'config': ExportConfig,
                'data': List[Dict],           # 可选，优先使用
                'fetcher': Callable,          # 未提供 data 时使用
                'search_params': Dict         # 配合 fetcher 使用
            }
        filename: 导出文件名（支持 {timestamp} 占位符）
        progress_callback: 进度回调

    Returns:
        生成的文件路径
    """
    _notify_progress(progress_callback, 0, '正在准备导出...')
    logger.info('[async_export] 开始多 Sheet 导出，共 %s 个 Sheet', len(sheets_config))

    prepared_sheets = []
    total_records = 0
    sheet_count = len(sheets_config)
    for idx, sheet in enumerate(sheets_config):
        base_progress = int((idx / sheet_count) * 60)
        prepared, count = _prepare_sheet_data(sheet, progress_callback, base_progress)

        if prepared:
            prepared_sheets.append(prepared)
            total_records += count

    if not prepared_sheets:
        logger.warning('[async_export] 所有 Sheet 均无数据，无数据可导出')
        raise ValueError('没有数据可导出')

    _notify_progress(progress_callback, 70, f'已查询 {total_records} 条数据，正在生成文件...')
    output_path = _build_output_path(filename)
    response = export_multi_sheets(
        filename=os.path.basename(output_path),
        sheets=prepared_sheets,
    )

    _save_export_response(response, output_path, progress_callback)
    logger.info('[async_export] 多 Sheet 导出文件已生成: %s', output_path)

    return output_path


def submit_export_task(
    config: ExportConfig,
    fetcher: Callable[..., List[Dict[str, Any]]],
    search_params: Dict[str, Any],
) -> str:
    """
    提交异步导出任务。

    Args:
        config: 导出配置
        fetcher: 数据获取函数，接收 search_params 返回 List[dict]
        search_params: 搜索条件

    Returns:
        task_id
    """
    cleanup_expired_exports()
    return submit_excel_task(_async_export_wrapper, config, fetcher, search_params)


def submit_multi_sheet_export_task(
    sheets_config: List[Dict[str, Any]],
    filename: str,
) -> str:
    """
    提交多 Sheet 异步导出任务。

    Args:
        sheets_config: 每个 sheet 的配置
        filename: 导出文件名（支持 {timestamp} 占位符）

    Returns:
        task_id
    """
    cleanup_expired_exports()
    return submit_excel_task(_async_multi_sheet_export_wrapper, sheets_config, filename)


def submit_provider_export_task(provider: DataProvider, search_params: Dict[str, Any]) -> str:
    """通过数据提供者提交异步导出任务。"""
    config = provider.get_config()
    return submit_export_task(config, provider.fetch, search_params)
