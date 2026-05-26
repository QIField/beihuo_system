# -*- coding:utf-8 -*-
# @Time    : 2026/5/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_api.py
# @Software: PyCharm

"""
汽车配件库API接口
负责处理配件库的HTTP请求
"""

from flask import Blueprint, request, jsonify, session
from app.services.car_parts_library_service.car_parts_library_benz_service import get_part_by_number, get_parts_list_page, set_mercedes_config, get_mercedes_config, data_refresh
from app.services.car_parts_library_service.car_parts_favorite_service import add_to_favorites, get_user_favorites, remove_from_favorites

car_parts_library_bp = Blueprint('car_parts_library', __name__, url_prefix='/car-parts')


@car_parts_library_bp.route('/list', methods=['GET'])
def get_parts_list():
    """
    获取配件列表（分页）

    参数:
        page: 页码，默认1
        page_size: 每页条数，默认20
        part_number: 配件编号筛选（可选）

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "status": 操作状态,
                "msg": 提示信息,
                "parts_count": 零件信息条数,
                "stock_count": 库存信息条数
            }
        }
    """
    try:
        # 获取参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        part_number = request.args.get('part_number')

        # 查询数据
        result = get_parts_list_page(
            page=page,
            page_size=page_size,
            part_number=part_number
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })



@car_parts_library_bp.route('/detail', methods=['GET'])
def get_part_detail():
    """
    获取配件详情

    参数:
        part_number: 配件编号（查询参数）

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {...}
        }
    """
    try:
        part_number = request.args.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '配件编号不能为空',
                'data': None
            })
        
        part = get_part_by_number(part_number)
        if part:
            return jsonify({
                'code': 200,
                'msg': 'success',
                'data': part
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '配件不存在',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/set-config', methods=['POST'])
def set_mercedes_config_api():
    """
    设置奔驰大库配置 API

    请求参数:
        {
            "cookie": "Cookie 字符串",
            "customer_id": "客户ID",
            "sales_organization_id": "销售组织ID"
        }

    返回:
        {
            "code": 200,
            "msg": "设置成功",
            "data": None
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        cookie = data.get('cookie')
        customer_id = data.get('customer_id')
        sales_organization_id = data.get('sales_organization_id')
        
        if not cookie or not customer_id or not sales_organization_id:
            return jsonify({
                'code': 400,
                'msg': 'Cookie、customer_id 和 sales_organization_id 不能为空',
                'data': None
            })
        
        result = set_mercedes_config(cookie, customer_id, sales_organization_id)
        
        if result.get('code') == 200:
            return jsonify({
                'code': 200,
                'msg': result.get('message', '设置成功'),
                'data': None
            })
        else:
            return jsonify({
                'code': 500,
                'msg': result.get('message', '设置失败'),
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'设置配置失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/get-config', methods=['GET'])
def get_mercedes_config_api():
    """
    获取奔驰大库配置 API

    返回:
    {
        "code": 200,
        "msg": "查询成功",
        "data": {
            "cookie": "Cookie 字符串",
            "customer_id": "客户ID",
            "sales_organization_id": "销售组织ID"
        }
    }
    """
    try:
        config = get_mercedes_config()
        
        if config:
            return jsonify({
                'code': 200,
                'msg': '查询成功',
                'data': config
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '配置不存在',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询配置失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/batch-refresh', methods=['POST'])
def batch_refresh_parts_data():
    """
    批量刷新配件数据 API

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...]
    }

    返回:
    {
        "code": 200,
        "msg": "刷新成功",
        "data": {
            "status": true,
            "msg": "数据刷新成功",
            "parts_count": 零件信息条数,
            "stock_count": 库存信息条数
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        part_numbers = data.get('part_numbers', [])
        
        if not part_numbers or len(part_numbers) == 0:
            return jsonify({
                'code': 400,
                'msg': '配件编号列表不能为空',
                'data': None
            })
        
        result = data_refresh(part_numbers)
        
        if result and result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '刷新成功'),
                'data': result
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '刷新失败'),
                'data': result
            })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'批量刷新失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/add-favorites', methods=['POST'])
def add_favorites_api():
    """
    批量添加配件到收藏夹 API

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...],
        "category": "分类名称" (可选，默认为"主收藏")
    }

    返回:
    {
        "code": 200,
        "msg": "收藏成功！新增 X 个，已存在 Y 个",
        "data": {
            "status": true,
            "msg": "收藏成功！新增 X 个，已存在 Y 个",
            "added_count": X,
            "exists_count": Y
        }
    }
    """
    try:
        # 检查是否登录
        if 'logged_in' not in session:
            return jsonify({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }), 401
        
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'code': 401,
                'msg': '用户信息异常，请重新登录',
                'data': None
            }), 401
        
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        part_numbers = data.get('part_numbers', [])
        category = data.get('category', '主收藏')
        
        if not part_numbers or len(part_numbers) == 0:
            return jsonify({
                'code': 400,
                'msg': '配件编号列表不能为空',
                'data': None
            })
        
        result = add_to_favorites(user_id, part_numbers, category)
        
        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg'),
                'data': result
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg'),
                'data': result
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'添加收藏失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/get-favorites', methods=['GET'])
def get_favorites_api():
    """
    获取用户收藏列表 API

    请求参数:
    - page: 页码，默认1
    - page_size: 每页条数，默认10
    - category: 分类名称（可选），不传则返回所有分类

    返回:
    {
        "code": 200,
        "msg": "获取成功",
        "data": {
            "status": True,
            "msg": "获取成功",
            "count": 总数,
            "data": [
                {
                    "part_number": "配件编号",
                    "description_cn": "中文描述",
                    "favorite_category": "分类",
                    ...
                }
            ]
        }
    }
    """
    try:
        # 检查是否登录
        if 'logged_in' not in session:
            return jsonify({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }), 401
        
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'code': 401,
                'msg': '用户信息异常，请重新登录',
                'data': None
            }), 401
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        category = request.args.get('category')
        
        favorites = get_user_favorites(user_id, category, page, page_size)
        
        if favorites:
            return jsonify({
                'code': 200,
                'msg': favorites.get('msg', '获取成功'),
                'data': favorites
            })
        else:
            return jsonify({
                'code': 500,
                'msg': '获取收藏列表失败',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取收藏列表失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/remove-favorites', methods=['POST'])
def remove_favorites_api():
    """
    批量从收藏夹删除配件 API

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...]
    }

    返回:
    {
        "code": 200,
        "msg": "删除成功！共删除 X 个收藏",
        "data": {
            "status": true,
            "msg": "删除成功！共删除 X 个收藏",
            "removed_count": X
        }
    }
    """
    try:
        # 检查是否登录
        if 'logged_in' not in session:
            return jsonify({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }), 401
        
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'code': 401,
                'msg': '用户信息异常，请重新登录',
                'data': None
            }), 401
        
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        part_numbers = data.get('part_numbers', [])
        if not part_numbers or len(part_numbers) == 0:
            return jsonify({
                'code': 400,
                'msg': '配件编号列表不能为空',
                'data': None
            })
        
        result = remove_from_favorites(user_id, part_numbers)
        
        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg'),
                'data': result
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg'),
                'data': result
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'删除收藏失败: {str(e)}',
            'data': None
        })