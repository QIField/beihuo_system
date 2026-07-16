# -*- coding: utf-8 -*-
"""
更新结果 Excel 导出
"""

import os
from datetime import date, datetime
from typing import List

import pandas as pd

from app.utils.logger_config import TASK_LOG_DIR, get_task_logger
from .config import TASK_NAME
from .models import UpdateRecord


logger = get_task_logger(TASK_NAME)


def export_update_records(records: List[UpdateRecord], target_date: date) -> str:
    """
    将更新记录导出为 Excel，保存到 task_log/quote_replace_number/ 目录。
    如果默认文件名被占用，自动追加时间戳。
    """
    task_dir = os.path.join(TASK_LOG_DIR, TASK_NAME)
    os.makedirs(task_dir, exist_ok=True)

    base_name = f"{TASK_NAME}_{target_date.strftime('%Y%m%d')}"
    file_path = os.path.join(task_dir, f"{base_name}.xlsx")

    data = []
    for record in records:
        data.append({
            'oe': record.oe,
            '品牌': record.brand_name,
            'product_id': record.product_id,
            '更新前替换号': ','.join(record.numbers_before),
            '更新后替换号': ','.join(record.numbers_after),
            '状态': record.status,
            '备注': record.message,
        })

    df = pd.DataFrame(data)

    try:
        df.to_excel(file_path, index=False, engine='openpyxl')
    except PermissionError:
        timestamp = datetime.now().strftime('%H%M%S')
        file_path = os.path.join(task_dir, f"{base_name}_{timestamp}.xlsx")
        df.to_excel(file_path, index=False, engine='openpyxl')
        logger.warning(f"默认 Excel 文件被占用，已导出到: {file_path}")

    logger.info(f"Excel 导出完成: {file_path}，共 {len(records)} 条")
    return file_path
