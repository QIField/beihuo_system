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
from app.services.car_parts_library_service.car_parts_favorite_service import add_to_favorites, get_user_favorites, remove_from_favorites, get_user_favorite_categories, move_to_main_category, copy_to_main_category, clear_category_favorites

favorites_bp = Blueprint('favorites', __name__)


@favorites_bp.route('/add-favorites', methods=['POST'])
def add_favorites_api():
    """
    批量添加配件到收藏夹 API（全局共享收藏）

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...],
        "category": "分类名称" (可选，默认为"主收藏")
    }
    """
    try:
        # 获取操作人用户ID（可为空，仅记录）
        operator_user_id = session.get('user_id') if 'logged_in' in session else None

        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })

        part_numbers = data.get('part_numbers', [])
        category = data.get('category', '奔驰主收藏')

        if not part_numbers or len(part_numbers) == 0:
            return jsonify({
                'code': 400,
                'msg': '配件编号列表不能为空',
                'data': None
            })

        result = add_to_favorites(operator_user_id, part_numbers, category)

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
    获取全局共享的收藏列表 API

    请求参数:
    - page: 页码，默认1
    - page_size: 每页条数，默认10
    - category: 分类名称（可选），不传则返回所有分类
    """
    try:
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        category = request.args.get('category')

        favorites = get_user_favorites(category, page, page_size)

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
    批量从收藏夹删除配件 API（全局共享收藏）

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...],
        "category": "分类名称" (可选，不传则按配件编号删除所有分类下的该配件)
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

        category = data.get('category')
        result = remove_from_favorites(part_numbers, category)

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


@favorites_bp.route('/get-categories', methods=['GET'])
def get_categories_api():
    """
    获取全局共享的所有收藏分类 API
    """
    try:
        result = get_user_favorite_categories()

        return jsonify({
            'code': 200,
            'msg': result.get('msg', '获取成功'),
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取收藏分类失败: {str(e)}',
            'data': None
        })


@favorites_bp.route('/move-to-main', methods=['POST'])
def move_to_main_api():
    """
    批量将收藏移动到主收藏 API（全局共享收藏）

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...],
        "source_category": "收藏a"  // 可选，指定来源分类
    }
    """
    try:
        # 获取操作人用户ID（可为空，仅记录）
        operator_user_id = session.get('user_id') if 'logged_in' in session else None

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

        source_category = data.get('source_category')
        result = move_to_main_category(part_numbers, source_category, operator_user_id)

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
            'msg': f'移动收藏失败: {str(e)}',
            'data': None
        })


@favorites_bp.route('/copy-to-main', methods=['POST'])
def copy_to_main_api():
    """
    批量复制收藏到主收藏 API（全局共享收藏）

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...]
    }
    """
    try:
        # 获取操作人用户ID（可为空，仅记录）
        operator_user_id = session.get('user_id') if 'logged_in' in session else None

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

        result = copy_to_main_category(part_numbers, operator_user_id)

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
            'msg': f'复制收藏失败: {str(e)}',
            'data': None
        })


@favorites_bp.route('/clear-category', methods=['POST'])
def clear_category_api():
    """
    清空指定分类下的所有收藏 API（全局共享收藏）

    请求参数:
    {
        "category": "分类名称"
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

        category = data.get('category')
        if not category:
            return jsonify({
                'code': 400,
                'msg': '分类名称不能为空',
                'data': None
            })

        result = clear_category_favorites(category)

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
            'msg': f'清空收藏失败: {str(e)}',
            'data': None
        })
