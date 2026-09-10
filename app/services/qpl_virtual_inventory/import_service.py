#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存导入编排服务
"""

import logging
import os
import re
from datetime import datetime, timedelta

from app.routes.excel_download import DOWNLOAD_BASE_URL
from app.services.qpl_virtual_inventory.config import (
    DEFAULT_COMPANY, DOWNLOAD_CATEGORY, EXPORT_DIR,
    FILE_RETENTION_DAYS, OUTPUT_EXCEL_PATH
)
from app.services.qpl_virtual_inventory.data_service import fetch_virtual_inventory_records
from app.utils.common_util_module.server_push import message_push
from app.utils.qpl_virtual_inventory.api_client import upload_product_import
from app.utils.qpl_virtual_inventory.excel_builder import (
    build_import_excel, convert_records_to_rows
)

logger = logging.getLogger('qpl_virtual_inventory')


def _get_output_path():
    """
    根据当前日期生成输出文件路径
    """
    date_str = datetime.now().strftime('%Y%m%d')
    return OUTPUT_EXCEL_PATH.format(date_str=date_str)


def _build_download_url(date_str):
    """
    构建 Excel 下载链接
    """
    return f"{DOWNLOAD_BASE_URL}/web/download_excel/{DOWNLOAD_CATEGORY}/{DEFAULT_COMPANY}/{date_str}"


def _push_message(status, rows, message, download_url):
    """
    推送微信消息，包含导入状态和下载链接
    """
    title = '===【汽配龙虚拟库存导入】==='
    status_text = '成功' if status else '失败'
    lines = [
        title,
        f"日期：{datetime.now().strftime('%Y-%m-%d')}",
        f"状态：{status_text}",
        f"导入行数：{rows}",
    ]
    if message:
        lines.append(f"信息：{message}")
    if download_url:
        lines.append(f"下载链接：{download_url}")

    try:
        return message_push('虚拟库存数据', '\n'.join(lines))
    except Exception as e:
        logger.error(f"[虚拟库存] 微信推送失败: {e}")
        return None


def _cleanup_old_files():
    """
    清理超过保留天数的本业务历史导出文件
    """
    if not os.path.exists(EXPORT_DIR):
        return

    pattern = re.compile(r'^qpl_virtual_inventory_import_fsbbr_\d{8}\.xlsx$')
    cutoff = datetime.now() - timedelta(days=FILE_RETENTION_DAYS)
    removed = 0

    for filename in os.listdir(EXPORT_DIR):
        if not pattern.match(filename):
            continue
        file_path = os.path.join(EXPORT_DIR, filename)
        if not os.path.isfile(file_path):
            continue
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            if mtime < cutoff:
                os.remove(file_path)
                removed += 1
        except Exception as e:
            logger.error(f"[虚拟库存] 清理历史文件失败 {file_path}: {e}")

    if removed:
        logger.info(f"[虚拟库存] 已清理 {removed} 个超过 {FILE_RETENTION_DAYS} 天的历史文件")


def run_import():
    """
    执行完整导入流程：查询数据 → 生成 Excel → 上传 → 推送消息 → 清理旧文件

    无论上传成功或失败，Excel 文件均保留在 static/exports/ 并提供下载链接。

    Returns:
        dict: {
            'success': bool,
            'message': str,
            'rows': int,
            'output_path': str or None
        }
    """
    records = fetch_virtual_inventory_records()
    if not records:
        logger.info('[虚拟库存] 无待导入数据，跳过')
        return {'success': True, 'message': '无待导入数据', 'rows': 0, 'output_path': None}

    rows = convert_records_to_rows(records)
    output_path = _get_output_path()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    build_import_excel(rows, output_path)
    logger.info(f'[虚拟库存] 已生成导入文件: {output_path}，共 {len(rows)} 行')

    date_str = datetime.now().strftime('%Y%m%d')
    download_url = _build_download_url(date_str)

    upload_result = upload_product_import(output_path, company=DEFAULT_COMPANY)

    if upload_result['token_invalid']:
        message = upload_result['message']
        logger.error(f'[虚拟库存] 上传失败：{message}')
        _push_message(False, len(rows), message, download_url)
        return {
            'success': False,
            'message': message,
            'rows': len(rows),
            'output_path': output_path
        }

    if not upload_result['success']:
        message = upload_result['message']
        response = upload_result.get('response')
        logger.error(f'[虚拟库存] 上传失败：{message}，响应：{response}')
        _push_message(False, len(rows), message, download_url)
        return {
            'success': False,
            'message': message,
            'rows': len(rows),
            'output_path': output_path
        }

    logger.info(f'[虚拟库存] 上传成功，共导入 {len(rows)} 行')
    _push_message(True, len(rows), '上传成功', download_url)
    _cleanup_old_files()
    return {'success': True, 'message': '上传成功', 'rows': len(rows), 'output_path': output_path}
