# -*- coding:utf-8 -*-
# @Time    : 2026/06/17
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_import_api.py
# @Software : trae-cn

"""
华晨宝马配件库 Excel 导入 API
负责处理 Excel/CSV 文件上传、批量导入、模板下载
数据写入 car_parts_library_bmw 表，成功的配件同时写入宝马收藏
"""

from flask import Blueprint, request, jsonify, send_file, session
import time

from app.services.car_parts_library_service.excel_import_bmw_service import (
    process_file_stream,
    generate_template,
)
from app.dao.car_parts_library_bmw_dao import CarPartsLibraryBmwDao
from app.services.car_parts_library_service.car_parts_favorite_bmw_service import (
    add_bmw_to_favorites,
)

bmw_import_bp = Blueprint('bmw_import', __name__, url_prefix='/bmw')


@bmw_import_bp.route('/import', methods=['POST'])
def import_parts_api():
    """
    批量导入宝马配件（插入更新模式）

    请求参数:
        file: 上传的 Excel/CSV 文件（multipart/form-data）

    返回:
        {
            "code": 200,
            "msg": "导入成功",
            "data": {
                "total": 总数,
                "success": 成功数,
                "failed": 失败数,
                "errors": [错误详情],
                "success_part_numbers": [成功的配件编号]
            }
        }
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                'code': 400,
                'msg': '请选择要上传的文件',
                'data': None,
            })

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'code': 400,
                'msg': '请选择要上传的文件',
                'data': None,
            })

        # 使用宝马专用 DAO
        dao = CarPartsLibraryBmwDao()

        # 调用服务层处理
        result = process_file_stream(file, file.filename, dao)

        # 如果导入成功且用户已登录，将成功的配件添加到宝马收藏
        if result.get('success', 0) > 0 and 'logged_in' in session:
            user_id = session.get('user_id')
            success_part_numbers = result.get('success_part_numbers', [])
            if success_part_numbers:
                try:
                    category = f'excel_bmw_{user_id}_{int(time.time())}'
                    add_bmw_to_favorites(user_id, success_part_numbers, category)
                except Exception as fav_e:
                    print(f'宝马配件导入后添加收藏失败: {str(fav_e)}')

        return jsonify({
            'code': 200,
            'msg': '导入成功',
            'data': result,
        })
    except ValueError as ve:
        return jsonify({
            'code': 400,
            'msg': str(ve),
            'data': None,
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'导入失败: {str(e)}',
            'data': None,
        })


@bmw_import_bp.route('/template', methods=['GET'])
def download_template_api():
    """
    下载宝马配件 Excel 导入模板

    返回: Excel 文件
    """
    try:
        template_file = generate_template()
        return send_file(
            template_file,
            as_attachment=True,
            download_name='宝马配件导入模板.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'下载模板失败: {str(e)}',
            'data': None,
        })


__all__ = ['bmw_import_bp']
