"""
修理厂询价单API

数据来自 cass_inquiry_quote 表（开思修理厂询单爬虫写入 fsbbr_data 线上库）
"""
from flask import Blueprint, jsonify, render_template, session, request
from functools import wraps

from app.services.cass_inquiry_service import CassInquiryQueryService

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


@bp.route('/web/cass_inquiry')
@login_required
def page():
    """修理厂询价单页面"""
    return render_template('cass_inquiry/inquiry_list.html')


@bp.route('/api/cass_inquiry/list')
@login_required
def list_quotes():
    """
    分页查询修理厂询单报价数据

    参数：page、limit（或 page_size）、inquiry_start、inquiry_end、decode_num、
          brand_name、store_name、inquiry_id、sort_column、sort_dir
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
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'code': 1, 'msg': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询失败: {e}'}), 500
