# -*- coding:utf-8 -*-
# @Time    : 2026/06/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : favorites_bmw_api.py
# @Software : trae-cn

"""
宝马收藏功能API接口
数据同样存储在 car_parts_favorite 表中，通过 category='宝马主收藏' 区分
"""

from flask import Blueprint, request, jsonify, session
from app.core.permission.decorators import require_authentication, require_permission
from app.services.car_parts_library_service.car_parts_favorite_bmw_service import (
    add_bmw_to_favorites,
    get_bmw_favorites,
    remove_bmw_from_favorites,
    get_bmw_favorite_categories,
    clear_bmw_category_favorites,
    move_bmw_to_main_category,
    copy_bmw_to_main_category,
)

favorites_bmw_bp = Blueprint('favorites_bmw', __name__)


@favorites_bmw_bp.route('/add-bmw-favorites', methods=['POST'])
@require_authentication()
def add_bmw_favorites_api():
    """
    批量添加宝马配件到收藏夹 API

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...],
        "category": "分类名称" (可选，默认为"宝马主收藏")
    }
    """
    try:
        operator_user_id = session.get('user_id') if 'logged_in' in session else None

        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求参数不能为空', 'data': None})

        part_numbers = data.get('part_numbers', [])
        category = data.get('category', '宝马主收藏')

        if not part_numbers or len(part_numbers) == 0:
            return jsonify({'code': 400, 'msg': '配件编号列表不能为空', 'data': None})

        result = add_bmw_to_favorites(operator_user_id, part_numbers, category)

        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        else:
            return jsonify({'code': 400, 'msg': result.get('msg'), 'data': result})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'添加收藏失败: {str(e)}', 'data': None})


@favorites_bmw_bp.route('/get-bmw-favorites', methods=['GET'])
@require_authentication()
def get_bmw_favorites_api():
    """
    获取宝马收藏列表 API

    请求参数:
    - page: 页码，默认1
    - page_size: 每页条数，默认10
    - category: 分类名称（可选），默认'宝马主收藏'
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('limit', 10))
        category = request.args.get('category') or '宝马主收藏'

        favorites = get_bmw_favorites(category, page, page_size)

        if favorites:
            return jsonify({'code': 200, 'msg': favorites.get('msg', '获取成功'), 'data': favorites})
        else:
            return jsonify({'code': 500, 'msg': '获取收藏列表失败', 'data': None})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'获取收藏列表失败: {str(e)}', 'data': None})


@favorites_bmw_bp.route('/remove-bmw-favorites', methods=['POST'])
@require_permission('favorites:remove')
def remove_bmw_favorites_api():
    """
    批量从收藏夹删除宝马配件 API

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...],
        "category": "分类名称" (可选)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求参数不能为空', 'data': None})

        part_numbers = data.get('part_numbers', [])
        if not part_numbers or len(part_numbers) == 0:
            return jsonify({'code': 400, 'msg': '配件编号列表不能为空', 'data': None})

        category = data.get('category')
        result = remove_bmw_from_favorites(part_numbers, category)

        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        else:
            return jsonify({'code': 400, 'msg': result.get('msg'), 'data': result})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'删除收藏失败: {str(e)}', 'data': None})


@favorites_bmw_bp.route('/get-bmw-categories', methods=['GET'])
@require_authentication()
def get_bmw_categories_api():
    """
    获取所有宝马相关的收藏分类 API
    """
    try:
        result = get_bmw_favorite_categories()
        return jsonify({'code': 200, 'msg': result.get('msg', '获取成功'), 'data': result})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'获取收藏分类失败: {str(e)}', 'data': None})


@favorites_bmw_bp.route('/clear-bmw-category', methods=['POST'])
@require_permission('favorites:clear')
def clear_bmw_category_api():
    """
    清空指定宝马分类下的所有收藏 API

    请求参数:
    {
        "category": "分类名称"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求参数不能为空', 'data': None})

        category = data.get('category')
        if not category:
            return jsonify({'code': 400, 'msg': '分类名称不能为空', 'data': None})

        result = clear_bmw_category_favorites(category)

        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        else:
            return jsonify({'code': 400, 'msg': result.get('msg'), 'data': result})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'清空收藏失败: {str(e)}', 'data': None})


@favorites_bmw_bp.route('/move-bmw-to-main', methods=['POST'])
@require_authentication()
def move_bmw_to_main_api():
    """
    批量将宝马收藏移动到宝马主收藏 API

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...],
        "source_category": "来源分类名称"（可选）
    }
    """
    try:
        operator_user_id = session.get('user_id') if 'logged_in' in session else None

        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求参数不能为空', 'data': None})

        part_numbers = data.get('part_numbers', [])
        if not part_numbers or len(part_numbers) == 0:
            return jsonify({'code': 400, 'msg': '配件编号列表不能为空', 'data': None})

        source_category = data.get('source_category')
        result = move_bmw_to_main_category(part_numbers, source_category, operator_user_id)

        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        else:
            return jsonify({'code': 400, 'msg': result.get('msg'), 'data': result})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'移动收藏失败: {str(e)}', 'data': None})


@favorites_bmw_bp.route('/copy-bmw-to-main', methods=['POST'])
@require_authentication()
def copy_bmw_to_main_api():
    """
    批量复制宝马收藏到宝马主收藏 API

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...]
    }
    """
    try:
        operator_user_id = session.get('user_id') if 'logged_in' in session else None

        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求参数不能为空', 'data': None})

        part_numbers = data.get('part_numbers', [])
        if not part_numbers or len(part_numbers) == 0:
            return jsonify({'code': 400, 'msg': '配件编号列表不能为空', 'data': None})

        result = copy_bmw_to_main_category(part_numbers, operator_user_id)

        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        else:
            return jsonify({'code': 400, 'msg': result.get('msg'), 'data': result})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'复制收藏失败: {str(e)}', 'data': None})
