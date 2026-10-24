# -*- coding:utf-8 -*-
# @Time    : 2026/10/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : replace_number_process_api.py

"""
替换号异步处理 API 接口（Excel 处理页内两阶段）

direct 模式：直接添加（异步任务，Excel 替换号列自动合并，无需人工核对）；
compare 模式：对比添加两阶段 —— 阶段一匹配检查生成核对表格，用户页内
编辑确认后经 replace_number_confirm 提交阶段二批量更新。
"""

import os
import tempfile
from datetime import datetime

from flask import request, jsonify, session


def _get_company() -> str:
    """从会话获取公司代码"""
    user_store = session.get('store', 'fsbbr')
    current_org = session.get('current_org', user_store)
    if not current_org or current_org in ('all', 'none', 'undefined', ''):
        return user_store
    return current_org


def _validate_upload(file) -> str:
    """校验上传文件，返回错误信息，None 表示通过"""
    if file.filename == '':
        return '文件名为空'
    allowed_extensions = {'.xlsx', '.xls', '.csv'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return f'不支持的文件格式，仅支持: {", ".join(allowed_extensions)}'
    return None


def _save_upload(file, prefix: str) -> str:
    """保存上传文件到临时目录，返回文件路径"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_filename = f"{prefix}_{timestamp}_{file.filename}"
    temp_file_path = os.path.join(tempfile.gettempdir(), temp_filename)
    file.save(temp_file_path)
    return temp_file_path


def register_replace_number_process_routes(app):

    @app.route('/api/excel/async/replace_number', methods=['POST'])
    def async_replace_number():
        """
        更新替换号-异步提交接口
        direct: 直接添加（异步任务自动合并）
        compare: 对比添加-阶段一匹配检查（不写 CRM，返回核对清单）
        """
        if 'file' not in request.files:
            return jsonify({'code': 1, 'msg': '没有上传文件'}), 400

        file = request.files['file']
        error_msg = _validate_upload(file)
        if error_msg:
            return jsonify({'code': 1, 'msg': error_msg}), 400

        mode = request.form.get('mode')
        if mode not in ['direct', 'compare']:
            return jsonify({
                'code': 1,
                'msg': '无效的处理模式，支持: direct, compare'
            }), 400

        temp_file_path = _save_upload(file, 'replace_number')

        from app.core.async_task_store import submit_excel_task
        from app.services.replace_number_service.direct_processor import process_direct_replace_number
        from app.services.replace_number_service.edit_processor import check_replace_number_wrapper

        company = _get_company()
        if mode == 'direct':
            task_id = submit_excel_task(
                process_direct_replace_number,
                temp_file_path,
                company,
            )
        else:
            task_id = submit_excel_task(
                check_replace_number_wrapper,
                temp_file_path,
                company=company,
            )

        return jsonify({
            'code': 0,
            'msg': '任务已提交',
            'data': {'task_id': task_id, 'mode': mode}
        })

    @app.route('/api/excel/async/replace_number_confirm', methods=['POST'])
    def async_replace_number_confirm():
        """
        更新替换号-阶段二确认更新接口
        根据阶段一核对清单提交批量更新异步任务
        """
        payload = request.get_json(silent=True) or {}
        check_task_id = payload.get('check_task_id')
        items = payload.get('items')
        if not check_task_id or not isinstance(items, list) or not items:
            return jsonify({'code': 1, 'msg': '参数缺失：check_task_id 或 items'}), 400

        from app.core.async_task_store import submit_excel_task, get_task_status
        from app.services.replace_number_service.edit_processor import update_replace_number_wrapper

        check_status = get_task_status(check_task_id)
        if not check_status:
            return jsonify({'code': 1, 'msg': '检查任务不存在或已过期'}), 400
        if check_status.get('status') != 'completed':
            return jsonify({'code': 1, 'msg': '检查任务未成功完成，无法确认更新'}), 400

        check_data = check_status.get('result_data') or {}
        check_items = check_data.get('items') or []
        file_path = check_data.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'code': 1, 'msg': '检查任务文件已失效，请重新上传'}), 400

        # 清洗提交数据：仅保留行号与产品ID、替换号
        clean_items = []
        for item in items:
            row_index = item.get('row_index')
            products = item.get('products')
            if row_index is None or not isinstance(products, list) or not products:
                continue
            clean_products = []
            for product in products:
                product_id = product.get('product_id')
                numbers = product.get('numbers')
                if product_id and isinstance(numbers, list) and numbers:
                    clean_products.append({'product_id': product_id, 'numbers': numbers})
            if clean_products:
                clean_items.append({'row_index': row_index, 'products': clean_products})

        if not clean_items:
            return jsonify({'code': 1, 'msg': '没有可更新的数据'}), 400

        company = _get_company()
        task_id = submit_excel_task(
            update_replace_number_wrapper,
            file_path,
            check_items,
            clean_items,
            company=company,
        )

        return jsonify({
            'code': 0,
            'msg': '更新任务已提交',
            'data': {'task_id': task_id}
        })
