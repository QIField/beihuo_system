"""
替换号功能 API
"""

from functools import wraps
from flask import Blueprint, jsonify, request, session

from app.services.replace_number_service.compare_processor import (
    build_replace_number_edit_list,
)
from app.utils.replace_number.crm_api_client import update_product_numbers


replace_number_bp = Blueprint('replace_number', __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_user_company():
    user_store = session.get('store', 'fsbbr')
    current_org = session.get('current_org', user_store)
    if not current_org or current_org in ('all', 'none', 'undefined', ''):
        return user_store
    return current_org


@replace_number_bp.route('/edit-list', methods=['POST'])
@login_required
def api_get_replace_number_edit_list():
    """
    获取替换号编辑列表

    请求体:
    {
        "oe_brand_list": [{"oe": "xxx", "brand": "xxx"}, ...],
        "page": 1,
        "limit": 10
    }
    """
    data = request.get_json() or {}
    oe_brand_list = data.get('oe_brand_list', [])
    page = int(data.get('page', 1))
    limit = int(data.get('limit', 10))

    if not isinstance(oe_brand_list, list):
        return jsonify({'code': 1, 'msg': 'oe_brand_list 必须是数组'}), 400

    company = get_user_company()
    data_list, total = build_replace_number_edit_list(
        company=company,
        oe_brand_list=oe_brand_list,
        page=page,
        limit=limit
    )

    return jsonify({
        'code': 0,
        'msg': 'success',
        'data': {
            'list': data_list,
            'total': total,
            'page': page,
            'limit': limit
        }
    })


@replace_number_bp.route('/bulk-update', methods=['POST'])
@login_required
def api_bulk_update_replace_numbers():
    """
    批量更新替换号

    请求体:
    {
        "updates": [
            {"product_id": "xxx", "numbers": ["A", "B"]},
            ...
        ]
    }
    """
    data = request.get_json() or {}
    updates = data.get('updates', [])
    if not isinstance(updates, list):
        return jsonify({'code': 1, 'msg': 'updates 必须是数组'}), 400

    company = get_user_company()
    updated = 0
    failed = 0
    details = []

    for item in updates:
        product_id = item.get('product_id')
        numbers = item.get('numbers', [])

        if not product_id or not numbers:
            failed += 1
            details.append({
                'product_id': product_id,
                'status': '失败: 缺少参数'
            })
            continue

        response = update_product_numbers(company, product_id, numbers)
        if response.get('status') == 200 or response.get('msg') == '操作成功':
            updated += 1
            details.append({
                'product_id': product_id,
                'status': '更新成功'
            })
        else:
            failed += 1
            details.append({
                'product_id': product_id,
                'status': f"更新失败: {response.get('msg', '未知错误')}"
            })

    return jsonify({
        'code': 0,
        'msg': 'success',
        'data': {
            'updated': updated,
            'failed': failed,
            'details': details
        }
    })
