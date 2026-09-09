#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存导入编排服务
"""

import logging
import os
import shutil
from datetime import datetime

from app.services.qpl_virtual_inventory.config import (
    DEFAULT_COMPANY, FAILED_DIR, OUTPUT_EXCEL_PATH
)
from app.services.qpl_virtual_inventory.data_service import fetch_virtual_inventory_records
from app.utils.common_util_module.server_push import message_push
from app.utils.qpl_virtual_inventory.api_client import upload_product_import
from app.utils.qpl_virtual_inventory.excel_builder import (
    build_import_excel, convert_records_to_rows
)

logger = logging.getLogger('qpl_virtual_inventory')


def _archive_failed_file(file_path):
    """
    将上传失败的文件归档到 failed 目录，附加时间戳避免重名
    """
    os.makedirs(FAILED_DIR, exist_ok=True)
    basename = os.path.basename(file_path)
    name, ext = os.path.splitext(basename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_path = os.path.join(FAILED_DIR, f'{name}_{timestamp}{ext}')
    shutil.move(file_path, target_path)
    return target_path


def _push_alert(message):
    """
    推送企微预警
    """
    try:
        return message_push('汽配龙虚拟库存导入', message)
    except Exception as e:
        logger.error(f"[虚拟库存] 企微预警推送失败: {e}")
        return None


def run_import():
    """
    执行完整导入流程：查询数据 → 生成 Excel → 上传 → 清理

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
    build_import_excel(rows, OUTPUT_EXCEL_PATH)
    logger.info(f'[虚拟库存] 已生成导入文件: {OUTPUT_EXCEL_PATH}，共 {len(rows)} 行')

    upload_result = upload_product_import(OUTPUT_EXCEL_PATH, company=DEFAULT_COMPANY)

    if upload_result['token_invalid']:
        message = f"[虚拟库存] 上传失败：{upload_result['message']}，文件保留: {OUTPUT_EXCEL_PATH}"
        logger.error(message)
        _push_alert(message)
        return {
            'success': False,
            'message': upload_result['message'],
            'rows': len(rows),
            'output_path': OUTPUT_EXCEL_PATH
        }

    if not upload_result['success']:
        archived_path = _archive_failed_file(OUTPUT_EXCEL_PATH)
        message = (
            f"[虚拟库存] 上传失败：{upload_result['message']}\n"
            f"已归档: {archived_path}\n"
            f"响应: {upload_result.get('response')}"
        )
        logger.error(message)
        _push_alert(message)
        return {
            'success': False,
            'message': upload_result['message'],
            'rows': len(rows),
            'output_path': archived_path
        }

    os.remove(OUTPUT_EXCEL_PATH)
    logger.info(f'[虚拟库存] 上传成功，共导入 {len(rows)} 行，已删除输出文件')
    return {'success': True, 'message': '上传成功', 'rows': len(rows), 'output_path': None}
