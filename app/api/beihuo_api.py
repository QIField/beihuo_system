"""
备货数据 API 接口

提供手动更新和手动拉取数据的 HTTP 接口。
"""

from functools import wraps
from flask import Blueprint, jsonify, request, session

from app.services.beihuo_service import (
    update_company,
    fetch_company,
)

# 创建蓝图
bp = Blueprint('beihuo', __name__, url_prefix='/api')


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_user_store():
    """获取用户当前的门店"""
    user_store = session.get('store', 'fsbbr')
    current_org = session.get('current_org', user_store)
    
    # 如果current_org是无效值，返回用户默认门店
    if not current_org or current_org in ('all', 'none', 'undefined', ''):
        return user_store
    
    return current_org


@bp.route('/update_data', methods=['POST'])
@login_required
def api_update_data():
    """
    手动更新数据 API
    
    根据当前用户门店触发数据更新
    """
    try:
        current_store = get_user_store()
        result = update_company(current_store)
        
        if result['success']:
            return jsonify({
                'code': 0,
                'message': result['message'],
                'data': {'company': current_store}
            })
        else:
            return jsonify({
                'code': -1,
                'message': result['message'],
                'data': {'company': current_store}
            }), 500
            
    except Exception as e:
        return jsonify({
            'code': -1,
            'message': f'更新失败: {str(e)}',
            'data': None
        }), 500


@bp.route('/fetch_data', methods=['POST'])
@login_required
def api_fetch_data():
    """
    手动拉取数据 API
    
    根据当前用户门店拉取数据并保存到数据库
    """
    try:
        current_store = get_user_store()
        count = fetch_company(current_store)
        
        if count >= 0:
            return jsonify({
                'code': 0,
                'msg': f'成功拉取 {count} 条数据',
                'data': {'company': current_store, 'count': count}
            })
        else:
            return jsonify({
                'code': -1,
                'msg': '拉取数据失败',
                'data': {'company': current_store}
            }), 500
            
    except Exception as e:
        return jsonify({
            'code': -1,
            'msg': f'拉取失败: {str(e)}',
            'data': None
        }), 500
