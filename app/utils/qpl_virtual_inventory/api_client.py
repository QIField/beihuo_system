#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存导入 API 客户端
复刻 curl 请求：POST /qpl-supplier/s/productImportApi/importProduct
"""

import os

import requests

from app.utils.qpl_auto_bill.qpl_config import (
    BASE_URL, get_headers, handle_qpl_response
)

API_PATH = '/qpl-supplier/s/productImportApi/importProduct'


def upload_product_import(file_path, company='fsbbr'):
    """
    上传 Excel 文件到汽配龙 importProduct 接口

    Args:
        file_path: 待上传的 xlsx 文件路径
        company: 组织代码，默认 fsbbr

    Returns:
        dict: {
            'success': bool,
            'token_invalid': bool,
            'message': str,
            'response': dict or None
        }
    """
    url = f'{BASE_URL}{API_PATH}'
    headers = get_headers(company)
    headers.pop('Content-Type', None)

    filename = os.path.basename(file_path)
    mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    with open(file_path, 'rb') as f:
        files = {'file': (filename, f, mime_type)}
        resp = requests.post(url, headers=headers, files=files, timeout=120)

    result = handle_qpl_response(resp, company)

    if isinstance(result, dict) and result.get('code') == 401:
        return {
            'success': False,
            'token_invalid': True,
            'message': result.get('message', '汽配龙cookie失效'),
            'response': result,
        }

    # 汽配龙成功响应 code 为 10000（已实测确认）
    success = isinstance(result, dict) and str(result.get('code', '')) == '10000'
    return {
        'success': success,
        'token_invalid': False,
        'message': result.get('message', '上传完成') if isinstance(result, dict) else str(result),
        'response': result,
    }
