"""
修理厂询价单API

数据来自 cass_inquiry_quote 表（开思修理厂询单爬虫写入 fsbbr_data 线上库）
"""
from flask import Blueprint, jsonify, render_template, session, request
from functools import wraps

from app.services.cass_inquiry_service import CassInquiryQueryService
from app.services.cass_inquiry_service.price_compare_service import (
    list_stores as list_compare_stores,
    query_price_compare,
    filter_values as price_compare_filter_values,
)
from app.services.cass_inquiry_service.price_edit_service import (
    search_products_by_replacement,
    update_cass_prices,
)
from app.core.permission.user_flags import flag_required

bp = Blueprint('cass_inquiry', __name__)

# 查询服务实例
cass_inquiry_query_service = CassInquiryQueryService()


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '请先登录'}), 401
        return f(*args, **kwargs)
    return wrapper


def permission_required(f):
    """修理厂询价单权限验证（与管理员身份无关，必须显式拥有权限）"""
    return flag_required('can_cass_inquiry', '您没有权限访问修理厂询价单')(f)


@bp.route('/web/cass_inquiry')
@login_required
@permission_required
def page():
    """修理厂询价单页面"""
    return render_template('cass_inquiry/inquiry_list.html')


@bp.route('/api/cass_inquiry/list')
@login_required
@permission_required
def list_quotes():
    """
    分页查询修理厂询单报价数据

    参数：page、limit（或 page_size）、inquiry_start、inquiry_end、decode_num、
          brand_name、store_name、inquiry_id、sort_column、sort_dir、
          column_filters（列头菜单筛选 JSON，如 {"brand_name": ["博世"]}）
    """
    try:
        result = cass_inquiry_query_service.query_quotes(
            page=request.args.get('page', 1),
            page_size=request.args.get('limit') or request.args.get('page_size', 50),
            inquiry_start=request.args.get('inquiry_start'),
            inquiry_end=request.args.get('inquiry_end'),
            decode_num=request.args.get('decode_num'),
            brand_name=request.args.get('brand_name'),
            store_name=request.args.get('store_name'),
            inquiry_id=request.args.get('inquiry_id'),
            sort_column=request.args.get('sort_column'),
            sort_dir=request.args.get('sort_dir'),
            column_filters=request.args.get('column_filters'),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'code': 1, 'msg': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询失败: {e}'}), 500


@bp.route('/api/cass_inquiry/filter_values')
@login_required
@permission_required
def filter_values():
    """
    查询某列的全量去重候选值（列头菜单筛选勾选用）

    参数：column（列名，白名单内）、inquiry_start、inquiry_end、decode_num、
          brand_name、store_name、inquiry_id、column_filters（级联条件，已排除本列）
    """
    try:
        result = cass_inquiry_query_service.filter_values(
            column=request.args.get('column'),
            inquiry_start=request.args.get('inquiry_start'),
            inquiry_end=request.args.get('inquiry_end'),
            decode_num=request.args.get('decode_num'),
            brand_name=request.args.get('brand_name'),
            store_name=request.args.get('store_name'),
            inquiry_id=request.args.get('inquiry_id'),
            column_filters=request.args.get('column_filters'),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'code': 1, 'msg': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询失败: {e}'}), 500


@bp.route('/api/cass_inquiry/price_compare/stores')
@login_required
@permission_required
def price_compare_stores():
    """
    供应商价格对比 · 供应商候选（全表去重，排除巴博瑞自身）

    返回：{'code': 0, 'data': {'stores': [...]}}
    """
    try:
        return jsonify(list_compare_stores())
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询供应商失败: {e}'}), 500


@bp.route('/api/cass_inquiry/price_compare')
@login_required
@permission_required
def price_compare():
    """
    供应商价格对比 · 分页查询（与巴博瑞按译码OE号比对，价格取卖家价格）

    参数：store_name（必填）、page、page_size、sort_column、sort_dir、column_filters
    返回：{'code': 0, 'data': {'list': [...], 'total': n, 'page': p, 'page_size': s}}
          每行含 compare_status: higher/lower/equal/no_bbri
    """
    try:
        result = query_price_compare(
            store_name=request.args.get('store_name'),
            page=request.args.get('page', 1),
            page_size=request.args.get('page_size') or request.args.get('limit', 20),
            sort_column=request.args.get('sort_column'),
            sort_dir=request.args.get('sort_dir'),
            column_filters=request.args.get('column_filters'),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'code': 1, 'msg': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'比对查询失败: {e}'}), 500


@bp.route('/api/cass_inquiry/price_compare/filter_values')
@login_required
@permission_required
def price_compare_filter_values_api():
    """
    供应商价格对比 · 列头菜单筛选候选值（去重+计数，按其他列已生效筛选级联）

    参数：store_name（必填）、column（筛选列）、column_filters（级联条件，已排除本列）
    返回：{'code': 0, 'data': {'values': [{'value': v, 'count': n}, ...]}}
    """
    try:
        result = price_compare_filter_values(
            column=request.args.get('column'),
            store_name=request.args.get('store_name'),
            column_filters=request.args.get('column_filters'),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'code': 1, 'msg': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询筛选候选值失败: {e}'}), 500


@bp.route('/api/cass_inquiry/crm_products')
@login_required
@permission_required
def crm_products():
    """
    按商家替换号搜索 CRM 产品（开思价修改弹窗数据源）

    参数：replacement（替换号/OE）
    返回：[{product_id, number, brand_name, l_name_zh, store_cass_price, cost_price}]
    """
    replacement = (request.args.get('replacement') or '').strip()
    if not replacement:
        return jsonify({'code': 1, 'msg': '缺少替换号参数'}), 400
    try:
        products = search_products_by_replacement(replacement)
        return jsonify({'code': 0, 'data': {'list': products}})
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'CRM 搜索失败: {e}'}), 500


@bp.route('/api/cass_inquiry/update_price', methods=['POST'])
@login_required
@permission_required
def update_price():
    """
    批量更新产品开思价（前端仅提交勾选且改价的行，逐行返回结果）

    请求体：[{'product_id', 'store_cass_price'}]
    返回：{'results': [{'product_id', 'success', 'msg'}]}，与请求顺序一致
    """
    try:
        items = request.get_json(silent=True)
        if not isinstance(items, list) or not items:
            return jsonify({'code': 1, 'msg': '没有需要更新的产品'}), 400
        results = update_cass_prices(items)
        return jsonify({'code': 0, 'data': {'results': results}})
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'更新失败: {e}'}), 500
