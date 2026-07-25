# -*- coding:utf-8 -*-
"""
多渠道报价调价 API
"""

from functools import wraps

from flask import Blueprint, jsonify, request, session

from app.utils.logger_config import get_task_logger
from app.services.multi_channel_quote_adjust_service.quote_adjust_service import (
    parse_excel_file,
    expand_rows_with_suppliers,
    merge_rows_by_oe,
    build_quote_adjust_rows,
    get_template_download_url,
    save_import_pipeline,
    fetch_quote_list_data,
)
from app.services.multi_channel_quote_adjust_service.price_update_service import (
    update_product_sell_price,
    batch_update_sell_price,
)
from app.services.multi_channel_quote_adjust_service.message_converter import (
    convert_qq_chat_messages,
)


bp = Blueprint('multi_channel_quote_adjust', __name__, url_prefix='/multi_channel_quote_adjust')
logger = get_task_logger('multi_channel_quote_adjust')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def multi_channel_quote_adjust_permission_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        if not session.get('is_admin', False) and not session.get('can_multi_channel_quote_adjust', False):
            return jsonify({'code': 1, 'msg': '无权限访问多渠道报价调价'}), 403
        return f(*args, **kwargs)
    return decorated_function


def get_user_company():
    """获取当前用户公司代码"""
    user_store = session.get('store', 'fsbbr')
    current_org = session.get('current_org', user_store)
    if not current_org or current_org in ('all', 'none', 'undefined', ''):
        return user_store
    return current_org


@bp.route('/supplier-quote/import-excel', methods=['POST'])
@multi_channel_quote_adjust_permission_required
def import_excel():
    """
    导入 OE Excel

    请求: multipart/form-data, file: excel 文件
    响应:
    {
        "code": 0,
        "msg": "success",
        "data": {
            "list": [...],
            "total": N
        }
    }
    """
    file = request.files.get('file')
    if not file:
        return jsonify({'code': 1, 'msg': '请上传文件'}), 400

    rows, error = parse_excel_file(file)
    if error:
        return jsonify({'code': 1, 'msg': error}), 400

    if not rows:
        return jsonify({'code': 0, 'msg': 'success', 'data': {'count': 0}})

    expanded_rows = expand_rows_with_suppliers(rows)
    if not expanded_rows:
        return jsonify({'code': 0, 'msg': 'success', 'data': {'count': 0}})

    company = get_user_company()
    merged_rows = merge_rows_by_oe(expanded_rows)
    full_rows = build_quote_adjust_rows(company, merged_rows)

    try:
        create_by = session.get('username', '')
        save_import_pipeline(expanded_rows, full_rows, create_by)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'保存导入数据失败: {e}'}), 500

    return jsonify({
        'code': 0,
        'msg': '导入成功',
        'data': {
            'count': len(rows)
        }
    })


@bp.route('/supplier-quote/quote-list', methods=['GET'])
@multi_channel_quote_adjust_permission_required
def quote_list():
    """
    获取最近 36 小时内导入的 OE 报价列表（直接读库，不再实时调 CRM）

    响应:
    {
        "code": 0,
        "msg": "success",
        "data": {
            "list": [...],
            "total": N
        }
    }
    """
    data_list = fetch_quote_list_data(36)

    return jsonify({
        'code': 0,
        'msg': 'success',
        'data': {
            'list': data_list,
            'total': len(data_list)
        }
    })


@bp.route('/supplier-quote/convert-qq-messages', methods=['POST'])
@multi_channel_quote_adjust_permission_required
def convert_qq_messages():
    """
    手动触发 QQ 聊天消息转换

    响应:
    {
        "code": 0,
        "msg": "转换完成，共处理 N 条"
    }
    """
    try:
        convert_qq_chat_messages(limit=100)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'QQ 消息转换失败: {e}'}), 500

    return jsonify({'code': 0, 'msg': 'QQ 消息转换完成'})


@bp.route('/supplier-quote/template-url', methods=['GET'])
@multi_channel_quote_adjust_permission_required
def template_url():
    """获取模板下载地址"""
    return jsonify({
        'code': 0,
        'msg': 'success',
        'data': {
            'url': get_template_download_url()
        }
    })


@bp.route('/supplier-quote/update-price', methods=['POST'])
@multi_channel_quote_adjust_permission_required
def update_price():
    """
    更新产品卖价到公司价格系统

    请求体:
    {
        "product_id": "117588",
        "price": "36.00",
        "peer_price": "35.00"
    }
    """
    data = request.get_json() or {}
    product_id = data.get('product_id')
    price = data.get('price')
    peer_price = data.get('peer_price')

    if not product_id:
        return jsonify({'code': 1, 'msg': 'product_id 不能为空'}), 400

    price = str(price).strip() if price is not None else ""
    peer_price = str(peer_price).strip() if peer_price is not None else ""

    if not price or not peer_price:
        return jsonify({'code': 1, 'msg': '开思价和同行价均不能为空'}), 400

    company = get_user_company()

    try:
        result = update_product_sell_price(company, str(product_id), price, peer_price)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'更新失败: {e}'}), 500

    if result.get('success'):
        return jsonify({'code': 0, 'msg': 'success', 'data': result.get('data')})

    return jsonify({'code': 1, 'msg': result.get('msg', '更新失败'), 'data': result.get('data')}), 500


@bp.route('/supplier-quote/batch-update-price', methods=['POST'])
@multi_channel_quote_adjust_permission_required
def batch_update_price():
    """
    批量更新当前页产品卖价

    请求体:
    {
        "updates": [
            {"product_id": "117588", "cass_price": "36.00", "peer_price": "35.00", "oe": "xxx"},
            ...
        ]
    }
    """
    data = request.get_json() or {}
    updates = data.get('updates', [])
    logger.info("batch_update_price request data: %s", data)

    if not isinstance(updates, list):
        return jsonify({'code': 1, 'msg': 'updates 必须是数组'}), 400

    if not updates:
        return jsonify({'code': 1, 'msg': '没有需要更新的数据'}), 400

    company = get_user_company()
    create_by = session.get('username', '')

    try:
        result = batch_update_sell_price(company, updates, create_by)
    except Exception as e:
        logger.exception("batch_update_price exception: %s", e)
        return jsonify({'code': 1, 'msg': f'批量更新失败: {e}'}), 500

    return jsonify({
        'code': 0,
        'msg': f"批量更新完成，成功 {result.get('success_count', 0)} 条，失败 {result.get('fail_count', 0)} 条",
        'data': result
    })
