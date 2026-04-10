"""
采购历史比价模块API
功能：采购历史查询、比价功能
"""
from flask import Blueprint, request, jsonify, session, render_template
from functools import wraps

from app.services.compare_service.procurement_compare_service import ProcurementCompareService

# 创建蓝图
procurement_compare_bp = Blueprint('procurement_compare', __name__)


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def compare_permission_required(f):
    """比价模块权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        if not session.get('can_compare_module') and not session.get('is_admin'):
            return jsonify({'code': 1, 'msg': '您没有权限访问比价模块'}), 403
        return f(*args, **kwargs)
    return decorated_function


@procurement_compare_bp.route('/procurement_compare_module')
@compare_permission_required
def procurement_compare_module_page():
    """采购历史比价模块页面"""
    return render_template('purchase_plan/procurement_compare.html')


@procurement_compare_bp.route('/procurement_compare/search', methods=['POST'])
@compare_permission_required
def procurement_compare_search():
    """
    采购历史比价搜索
    根据OE、供应商、品牌、日期范围搜索采购历史
    不限制返回条数
    """
    try:
        data = request.get_json() or {}

        # 获取搜索参数
        start_date = data.get('start_date', '').strip()
        end_date = data.get('end_date', '').strip()
        oe_list = data.get('oe_list', [])
        supplier_list = data.get('supplier_list', [])
        brand_list = data.get('brand_list', [])

        # 获取用户当前组织
        company = session.get('current_org', session.get('store', 'fsbbr'))

        # 调用服务层查询数据
        result_data = ProcurementCompareService.search_procurement_history(
            company=company,
            oe_list=oe_list,
            supplier_list=supplier_list,
            brand_list=brand_list,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': result_data,
            'total': len(result_data)
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'搜索失败: {str(e)}'}), 500
