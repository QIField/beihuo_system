"""
开思询价单监控API
"""
from flask import Blueprint, jsonify, render_template, session
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.external_services.ks_inquiry_monitor import get_all_stats, get_store_stats, STORES
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
