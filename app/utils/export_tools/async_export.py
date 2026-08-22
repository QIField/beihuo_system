# -*- coding:utf-8 -*-
"""
异步导出支持

将大数据量导出任务提交到后台线程执行，前端通过 task_id 轮询进度并下载。
"""

import os
import tempfile
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.core.async_task_store import submit_excel_task

from .core import DataProvider, ExportConfig
from .exporters import get_exporter


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
    if progress_callback:
        progress_callback(0, 100, '正在查询数据...')

    data = fetcher(**search_params)

    if not data:
        raise ValueError('没有数据可导出')

    total = len(data)

    if progress_callback:
        progress_callback(30, 100, f'已查询 {total} 条数据，正在生成文件...')

    prepared_data = config.prepare_data(data)

    # 异步任务统一落盘到临时目录
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = config.get_filename().replace('{timestamp}', timestamp)
    output_path = os.path.join(tempfile.gettempdir(), filename)

    exporter = config.build_exporter()
    response = exporter.export(
        prepared_data,
        filename=filename,
        sheet_name=config.sheet_name,
    )

    # 将 Response 数据写入文件
    with open(output_path, 'wb') as f:
        f.write(response.get_data())

    if progress_callback:
        progress_callback(100, 100, '处理完成')

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
        fetcher: 数据获取函数
        search_params: 搜索条件

    Returns:
        task_id
    """
    return submit_excel_task(_async_export_wrapper, config, fetcher, search_params)


def submit_provider_export_task(provider: DataProvider, search_params: Dict[str, Any]) -> str:
    """通过数据提供者提交异步导出任务。"""
    config = provider.get_config()
    return submit_export_task(config, provider.fetch, search_params)
