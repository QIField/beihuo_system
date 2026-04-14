"""
开思询价单监控API
"""
from flask import Blueprint, jsonify, render_template, session, request
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.external_services.ks_inquiry_monitor import get_all_stats, get_store_stats, STORES
from app.external_services.ks_inquiry_monitor.alert_manager import confirm_alert, is_alert_confirmed, reset_alert_confirmation
from app.utils.permission_service import org_required

bp = Blueprint('ks_inquiry_monitor', __name__)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '请先登录'}), 401
        return f(*args, **kwargs)
    return wrapper


@bp.route('/ks_inquiry_monitor')
@login_required
@org_required(['fsbbr'])
def page():
    return render_template('ks_inquiry_monitor.html')


@bp.route('/api/ks_inquiry/stats')
@login_required
@org_required(['fsbbr'])
def get_stats():
    return jsonify({'code': 0, 'data': get_all_stats()})


@bp.route('/api/ks_inquiry/stats/<md_code>')
@login_required
@org_required(['fsbbr'])
def get_store(md_code):
    if md_code not in STORES:
        return jsonify({'code': 1, 'msg': '无效门店'}), 400
    return jsonify({'code': 0, 'data': get_store_stats(md_code)})


@bp.route('/api/ks_inquiry/confirm_alert', methods=['POST'])
@login_required
@org_required(['fsbbr'])
def confirm_alert_api():
    """用户确认报警"""
    user_id = session.get('user_id', session.get('_id', 'anonymous'))
    confirm_alert(user_id)
    return jsonify({'code': 0, 'msg': '已确认'})


@bp.route('/api/ks_inquiry/reset_alert', methods=['POST'])
@login_required
@org_required(['fsbbr'])
def reset_alert_api():
    """重置报警状态（用于测试）"""
    user_id = session.get('user_id', session.get('_id', 'anonymous'))
    reset_alert_confirmation(user_id)
    return jsonify({'code': 0, 'msg': '已重置'})


@bp.route('/api/ks_inquiry/check_alert_status')
@login_required
@org_required(['fsbbr'])
def check_alert_status():
    """检查当前用户是否已确认报警"""
    user_id = session.get('user_id', session.get('_id', 'anonymous'))
    confirmed = is_alert_confirmed(user_id)
    return jsonify({'code': 0, 'data': {'confirmed': confirmed}})
