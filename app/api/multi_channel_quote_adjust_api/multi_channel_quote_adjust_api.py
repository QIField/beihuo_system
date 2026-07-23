# -*- coding:utf-8 -*-
"""
多渠道报价调价 API
"""

from functools import wraps

from flask import Blueprint, jsonify, request, session

from app.services.multi_channel_quote_adjust_service.quote_adjust_service import (
    parse_excel_file,
    expand_rows_with_suppliers,
    merge_rows_by_oe,
    build_quote_adjust_rows,
    get_template_download_url,
)
from app.services.multi_channel_quote_adjust_service.repository import (
    save_to_qq_msg,
    save_import_records,
    fetch_recent_imports,
)


bp = Blueprint('multi_channel_quote_adjust', __name__, url_prefix='/multi_channel_quote_adjust')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
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
@login_required
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

    try:
        save_to_qq_msg(expanded_rows)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'保存到 qq_msg 失败: {e}'}), 500

    merged_rows = merge_rows_by_oe(expanded_rows)

    try:
        create_by = session.get('username', '')
        save_import_records(merged_rows, create_by)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'保存导入记录失败: {e}'}), 500

    return jsonify({
        'code': 0,
        'msg': '导入成功',
        'data': {
            'count': len(rows)
        }
    })


@bp.route('/supplier-quote/quote-list', methods=['GET'])
@login_required
def quote_list():
    """
    获取最近 36 小时内导入的 OE 报价列表

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
    company = get_user_company()
    imports = fetch_recent_imports(36)

    if not imports:
        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': {
                'list': [],
                'total': 0
            }
        })

    data_list = build_quote_adjust_rows(company, imports)

    return jsonify({
        'code': 0,
        'msg': 'success',
        'data': {
            'list': data_list,
            'total': len(data_list)
        }
    })


@bp.route('/supplier-quote/template-url', methods=['GET'])
@login_required
def template_url():
    """获取模板下载地址"""
    return jsonify({
        'code': 0,
        'msg': 'success',
        'data': {
            'url': get_template_download_url()
        }
    })
