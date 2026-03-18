"""
比价模块API
功能：查看询价比价表格、查询功能、导出功能
"""
from flask import Blueprint, request, jsonify, session, Response, render_template
from functools import wraps
import pandas as pd
import io
from datetime import datetime
from app.utils.database_connection import get_db_connection
from app.services.compare_service.compare_data_service import CompareDataService

# 创建蓝图
compare_bp = Blueprint('compare', __name__)


@compare_bp.route('/compare_module')
def compare_module_page():
    """比价模块页面"""
    # 检查用户是否有权限
    if 'logged_in' not in session:
        return render_template('login.html')
    if not session.get('can_compare_module') and not session.get('is_admin'):
        return "您没有权限访问此页面", 403
    return render_template('purchase_plan/compare_module.html')


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
        # 检查是否有比价模块权限或是admin
        if not session.get('can_compare_module') and not session.get('is_admin'):
            return jsonify({'code': 1, 'msg': '您没有权限访问比价模块'}), 403
        return f(*args, **kwargs)
    return decorated_function


@compare_bp.route('/list', methods=['GET'])
@compare_permission_required
def get_compare_list():
    """
    获取比价数据列表（服务端分页+排序）
    支持分页、筛选和排序
    根据用户所在组织过滤数据
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        product_name = request.args.get('product_name', '').strip()
        vehicle_brand = request.args.get('vehicle_brand', '').strip()

        # 获取排序参数
        sort_field = request.args.get('sort_field', '').strip()
        sort_order = request.args.get('sort_order', 'asc').strip().lower()

        # 限制最大每页数量，防止性能问题
        limit = min(limit, 500)

        # 获取用户当前切换到的组织
        company = session.get('current_org', session.get('store', 'fsbbr'))

        # 使用服务层查询数据（传入company过滤）
        data, total = CompareDataService.list_data(
            oe=oe,
            brand=brand,
            product_name=product_name,
            vehicle_brand=vehicle_brand,
            company=company,
            page=page,
            limit=limit,
            order_by='updated_time',
            order_desc=True,
            sort_field=sort_field,
            sort_order=sort_order
        )

        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': data,
            'count': total,
            'page': page,
            'limit': limit
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取数据失败: {str(e)}'}), 500


@compare_bp.route('/export', methods=['GET'])
@compare_permission_required
def export_compare_data():
    """
    导出比价数据为Excel或CSV
    支持筛选条件
    """
    try:
        # 获取查询参数
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        product_name = request.args.get('product_name', '').strip()
        vehicle_brand = request.args.get('vehicle_brand', '').strip()
        export_format = request.args.get('format', 'excel').lower()

        # 获取所有数据（不分页）
        data, _ = CompareDataService.list_data(
            oe=oe,
            brand=brand,
            product_name=product_name,
            vehicle_brand=vehicle_brand,
            page=1,
            limit=999999  # 获取所有数据
        )

        if not data:
            return jsonify({'code': 1, 'msg': '没有数据可导出'}), 400

        # 转换为DataFrame
        df = pd.DataFrame(data)

        # 选择要导出的列并重命名
        columns_mapping = {
            'oe': 'OE',
            'brand': '品牌',
            'product_name': '产品名称',
            'vehicle_brand': '车辆品牌',
            'replace_number': '替换号',
            'brand_code': '品牌编码',
            'inquiry_count': '询价次数',
            'product_level': '产品等级',
            'best_sales_month': '销量最好的月份',
            'best_sales_season': '销量最好的季节',
            'max_price': '最高价',
            'min_price': '最低价',
            'supplier_price': '供应商价格',
            'dealer_purchase_price': '4S含税进价',
            'dealer_sale_price': '4S含税售价',
            'price_update_time': '更新价格时间',
            'today_sales': '今日销量',
            'yesterday_sales': '昨日销量',
            'month_sales': '本月销量',
            'avg_sales_12m': '近12个月月均销量',
            'avg_sales_6m': '近6个月月均销量',
            'sales_7d': '近7天销量',
            'product_remark': '系统产品备注'
        }

        # 只保留存在的列
        existing_columns = [col for col in columns_mapping.keys() if col in df.columns]
        df = df[existing_columns]
        df = df.rename(columns=columns_mapping)

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'比价数据_{timestamp}'

        if export_format == 'csv':
            # 导出为CSV
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output.seek(0)

            return Response(
                output.getvalue(),
                mimetype='text/csv; charset=utf-8-sig',
                headers={
                    'Content-Disposition': f'attachment; filename={filename}.csv',
                    'Content-Type': 'text/csv; charset=utf-8-sig'
                }
            )
        else:
            # 导出为Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='比价数据')
            output.seek(0)

            return Response(
                output.getvalue(),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={
                    'Content-Disposition': f'attachment; filename={filename}.xlsx'
                }
            )

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'导出失败: {str(e)}'}), 500


@compare_bp.route('/statistics', methods=['GET'])
@compare_permission_required
def get_statistics():
    """
    获取比价数据统计信息
    """
    try:
        stats = CompareDataService.get_statistics()

        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': stats
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取统计信息失败: {str(e)}'}), 500





@compare_bp.route('/upsert', methods=['POST'])
@compare_permission_required
def upsert_data():
    """
    插入或更新单条数据
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 1, 'msg': '请求数据不能为空'}), 400

        if 'oe' not in data or not data['oe']:
            return jsonify({'code': 1, 'msg': 'OE号不能为空'}), 400

        record_id = CompareDataService.upsert_by_oe(data)

        return jsonify({
            'code': 0,
            'msg': '保存成功',
            'data': {'id': record_id}
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'保存失败: {str(e)}'}), 500


@compare_bp.route('/delete/<int:record_id>', methods=['DELETE'])
@compare_permission_required
def delete_data(record_id):
    """
    根据ID删除数据
    """
    try:
        affected = CompareDataService.delete_by_id(record_id)

        if affected > 0:
            return jsonify({
                'code': 0,
                'msg': '删除成功'
            })
        else:
            return jsonify({
                'code': 1,
                'msg': '记录不存在'
            }), 404

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'删除失败: {str(e)}'}), 500


@compare_bp.route('/get/<int:record_id>', methods=['GET'])
@compare_permission_required
def get_by_id(record_id):
    """
    根据ID获取单条数据
    """
    try:
        data = CompareDataService.get_by_id(record_id)

        if data:
            return jsonify({
                'code': 0,
                'msg': '获取成功',
                'data': data
            })
        else:
            return jsonify({
                'code': 1,
                'msg': '记录不存在'
            }), 404

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取失败: {str(e)}'}), 500
