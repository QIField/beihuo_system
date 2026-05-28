# -*- coding:utf-8 -*-
# @Time    : 2026/5/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : favorites_api.py
# @Software: PyCharm

"""
收藏功能API接口
负责处理收藏夹的HTTP请求
"""

from flask import Blueprint, request, jsonify, session
from app.services.car_parts_library_service.car_parts_favorite_service import add_to_favorites, get_user_favorites, remove_from_favorites

favorites_bp = Blueprint('favorites', __name__)


@favorites_bp.route('/add-favorites', methods=['POST'])
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


@favorites_bp.route('/get-favorites', methods=['GET'])
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


@favorites_bp.route('/remove-favorites', methods=['POST'])
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
