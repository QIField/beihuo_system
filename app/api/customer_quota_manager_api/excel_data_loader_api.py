# -*- coding:utf-8 -*-
# @Time    : 2026/4/25 15:37
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : excel_data_loader_api.py
# @Software: PyCharm

from flask import jsonify, request

from . import customer_quota_manager_bp
from app.services.customer_quota_manager_service import excel_data_loader_services


@customer_quota_manager_bp.route('/import_account_receivable_api', methods=['POST'])
def import_account_receivable_api():
    """
    导入应收单Excel数据 API（自动执行回填，强制插入更新模式）
    """
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({
                'code': 400,
                'msg': '没有上传文件',
                'data': None
            })
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'code': 400,
                'msg': '没有选择文件',
                'data': None
            })
        
        # 强制使用 upsert 模式
        upsert = True
        
        # 使用文件对象导入并自动回填
        result = excel_data_loader_services.import_and_backfill_excel_from_file(
            file, file.filename, upsert
        )
        
        # 构建统一返回信息
        msg = f'导入成功，共导入 {result["import_count"]} 条记录'
        if result.get('backfill_result'):
            backfill = result['backfill_result']
            msg += f'；数据回填完成：总记录 {backfill["after"]["total"]} 条，回填 {backfill["after"]["backfilled"]} 条，未回填 {backfill["after"]["unbackfilled"]} 条'
        
        return jsonify({
            'code': 200,
            'msg': msg,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'导入失败: {str(e)}',
            'data': None
        })

