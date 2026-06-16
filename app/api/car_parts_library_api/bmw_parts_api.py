# -*- coding:utf-8 -*-
# @Time    : 2026/6/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_parts_api.py
# @Software: PyCharm

"""
华晨宝马（BMW Brilliance）汽车配件库 API 接口
负责处理宝马配件库的 HTTP 请求：查询、分页、数据刷新、CRUD 操作
"""

from flask import Blueprint, request, jsonify
from app.services.car_parts_library_service.car_parts_library_bmw_service import (
    get_part_by_number,
    get_parts_list_page,
    data_refresh,
    add_part,
    update_part,
    delete_part,
)


# 创建宝马配件库蓝图
bmw_parts_bp = Blueprint('bmw_parts', __name__, url_prefix='/bmw')


# ====================================================
# 接口一：根据零件号查询单条配件详情（含库存信息）
# ====================================================
@bmw_parts_bp.route('/detail', methods=['GET'])
def get_part_detail():
    """
    根据零件号查询宝马配件详情（包含库存信息）

    参数（Query String）:
        part_number: 零件号（OE号），必填

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "part_number": "xxx",
                "part_name": "xxx",
                ...
                "stock_info": { ... }
            }
        }
    """
    try:
        part_number = request.args.get('part_number')
        if not part_number or not str(part_number).strip():
            return jsonify({
                'code': 400,
                'msg': '零件号不能为空',
                'data': None,
            })

        part = get_part_by_number(str(part_number).strip())
        if part:
            return jsonify({
                'code': 200,
                'msg': 'success',
                'data': part,
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '配件不存在',
                'data': None,
            })

    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口二：分页查询零件列表（支持按零件号筛选）
# ====================================================
@bmw_parts_bp.route('/list', methods=['GET'])
def get_parts_list():
    """
    获取宝马配件列表（分页 + 搜索）

    参数（Query String）:
        page:       页码，默认 1
        page_size:  每页条数，默认 20
        part_number: 零件号（模糊匹配），必填

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "status": True,
                "msg": "查询成功",
                "count": 100,
                "data": [ ... ]
            }
        }
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        part_number = request.args.get('part_number')

        result = get_parts_list_page(
            page=page,
            page_size=page_size,
            part_number=part_number,
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': result,
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口三：批量刷新零件数据（爬虫 + 入库）
# ====================================================
@bmw_parts_bp.route('/batch-refresh', methods=['POST'])
def batch_refresh_parts_data():
    """
    批量刷新宝马零件数据
    对每个零件号执行：爬取 BMW Brilliance 官方数据 → upsert 到数据库

    请求体 (JSON):
        {
            "part_numbers": ["part1", "part2", ...]
        }

    返回:
        {
            "code": 200,
            "msg": "数据刷新完成",
            "data": {
                "status": True,
                "parts_count": 10,
                "stock_count": 10,
                "failed": [ ... ]
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        part_numbers = data.get('part_numbers', [])

        if not part_numbers or not isinstance(part_numbers, list) or len(part_numbers) == 0:
            return jsonify({
                'code': 400,
                'msg': '零件号列表不能为空',
                'data': None,
            })

        result = data_refresh(part_numbers)

        if result and result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '刷新成功'),
                'data': result,
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '刷新失败'),
                'data': result,
            })

    except Exception as e:
        msg = f'批量刷新宝马零件数据接口异常: {str(e)}'
        print(msg)
        return jsonify({
            'code': 500,
            'msg': msg,
            'data': None,
        })


# ====================================================
# 接口四：新增配件
# ====================================================
@bmw_parts_bp.route('/add', methods=['POST'])
def add_part_api():
    """
    新增宝马配件

    请求体 (JSON):
        {
            "part_number": "零件号",
            "part_name": "零件名称",
            "sales_unit": "单位",
            ...
        }

    返回:
        { "code": 200, "msg": "添加成功" }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        if not data.get('part_number'):
            return jsonify({
                'code': 400,
                'msg': '零件号不能为空',
                'data': None,
            })

        result = add_part(data)

        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '添加成功'),
                'data': None,
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '添加失败'),
                'data': None,
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'添加失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口五：更新配件
# ====================================================
@bmw_parts_bp.route('/update', methods=['POST'])
def update_part_api():
    """
    更新宝马配件信息

    请求体 (JSON):
        {
            "part_number": "零件号（主键，不可修改）",
            "part_name": "零件名称",
            "sales_unit": "单位",
            ...
        }

    返回:
        { "code": 200, "msg": "更新成功" }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        part_number = data.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '零件号不能为空',
                'data': None,
            })

        result = update_part(part_number, data)

        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '更新成功'),
                'data': None,
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '更新失败'),
                'data': None,
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'更新失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口六：删除配件
# ====================================================
@bmw_parts_bp.route('/delete', methods=['POST'])
def delete_part_api():
    """
    删除宝马配件（同时删除库存表中关联记录）

    请求体 (JSON):
        { "part_number": "零件号" }

    返回:
        { "code": 200, "msg": "删除成功" }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        part_number = data.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '零件号不能为空',
                'data': None,
            })

        result = delete_part(part_number)

        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '删除成功'),
                'data': None,
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '删除失败'),
                'data': None,
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'删除失败: {str(e)}',
            'data': None,
        })


__all__ = ['bmw_parts_bp']
