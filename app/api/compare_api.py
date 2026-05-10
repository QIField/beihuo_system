"""
比价数据对比 API 接口

提供查询 replace_number 有差异的 OE 分组数据的 HTTP 接口
"""

from functools import wraps
from flask import Blueprint, jsonify, request, session

from app.services.compare_service.compare_data_service import (
    get_oe_with_different_replace_numbers,
    use_replace_number,
)

# 创建蓝图（不设置 url_prefix，在 __init__.py 中统一设置）
bp = Blueprint('compare', __name__)


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_user_company():
    """获取用户当前的公司/门店代码"""
    user_store = session.get('store', 'fsbbr')
    current_org = session.get('current_org', user_store)
    
    # 如果current_org是无效值，返回用户默认门店
    if not current_org or current_org in ('all', 'none', 'undefined', ''):
        return user_store
    
    return current_org


@bp.route('/diff-replace-numbers', methods=['GET'])
@login_required
def api_get_diff_replace_numbers():
    """
    获取 replace_number 有差异的 OE 分组数据
    
    查询逻辑：
    - 按 oe 分组，比较不同 brand 的 replace_number
    - 只要该 oe 下有一条 replace_number 不同，就展示该 oe 的所有 brand 数据
    - 如果所有 brand 的 replace_number 都相同，则不展示
    
    请求参数:
        - oe: OE号筛选（可选，支持空格分隔多值）
        - brand: 品牌筛选（可选，支持逗号分隔多值）
        - product_name: 产品名称筛选（可选，支持逗号分隔多值）
        - vehicle_brand: 车辆品牌筛选（可选，支持逗号分隔多值）
        - page: 页码（可选，默认1）
        - limit: 每页条数（可选，默认100）
    
    返回:
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [...],  // 数据列表
                "total": 100,   // 总记录数
                "page": 1,      // 当前页码
                "limit": 100    // 每页条数
            }
        }
    """
    try:
        # 获取请求参数
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        product_name = request.args.get('product_name', '').strip()
        vehicle_brand = request.args.get('vehicle_brand', '').strip()
        page = request.args.get('page', '1').strip()
        limit = request.args.get('limit', '100').strip()
        
        # 参数转换和验证
        try:
            page = int(page) if page else 1
            limit = int(limit) if limit else 100
        except ValueError:
            return jsonify({
                'code': -1,
                'message': '页码和每页条数必须是整数',
                'data': None
            }), 400
        
        # 限制每页最大条数
        if limit > 1000:
            limit = 1000
        if limit < 1:
            limit = 100
        if page < 1:
            page = 1
        
        # 获取当前用户公司
        company = get_user_company()
        
        # 调用服务层查询数据
        data_list, total = get_oe_with_different_replace_numbers(
            oe=oe,
            brand=brand,
            product_name=product_name,
            vehicle_brand=vehicle_brand,
            company=company,
            page=page,
            limit=limit
        )
        
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'list': data_list,
                'total': total,
                'page': page,
                'limit': limit
            }
        })
        
    except Exception as e:
        return jsonify({
            'code': -1,
            'message': f'查询失败: {str(e)}',
            'data': None
        }), 500


@bp.route('/total-oe-count', methods=['GET'])
@login_required
def api_get_total_oe_count():
    """
    获取数据库中总OE数量（用于统计）
    
    请求参数:
        - brand: 品牌筛选（可选）
    
    返回:
        {
            "code": 0,
            "message": "success",
            "data": {
                "total_oe_count": 1000
            }
        }
    """
    try:
        from app.utils.database_connection import get_db_connection
        import pymysql
        
        brand = request.args.get('brand', '').strip()
        company = get_user_company()
        
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
                # 构建 WHERE 条件
                where_conditions = ["company = %s"]
                params = [company]
                
                if brand:
                    brand_list = brand.split(',')
                    or_conditions = []
                    for item in brand_list:
                        or_conditions.append("brand LIKE %s")
                        params.append(f"%{item.strip()}%")
                    where_conditions.append("(" + " OR ".join(or_conditions) + ")")
                
                where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # 查询总OE数
                sql = f"""
                    SELECT COUNT(DISTINCT oe) 
                    FROM crmapp_compare_summary 
                    {where_clause}
                """
                cursor.execute(sql, params)
                total_oe_count = cursor.fetchone()[0]
                
                return jsonify({
                    'code': 0,
                    'message': 'success',
                    'data': {
                        'total_oe_count': total_oe_count
                    }
                })
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({
            'code': -1,
            'message': f'查询失败: {str(e)}',
            'data': None
        }), 500


@bp.route('/diff-replace-numbers/export', methods=['GET'])
@login_required
def api_export_diff_replace_numbers():
    """
    导出 replace_number 有差异的 OE 分组数据
    
    请求参数与查询接口相同，但导出所有数据（不分页）
    
    返回:
        CSV 文件下载
    """
    try:
        # 获取请求参数
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        product_name = request.args.get('product_name', '').strip()
        vehicle_brand = request.args.get('vehicle_brand', '').strip()
        
        # 获取当前用户公司
        company = get_user_company()
        
        # 调用服务层查询所有数据（不分页，设置一个较大的limit）
        data_list, total = get_oe_with_different_replace_numbers(
            oe=oe,
            brand=brand,
            product_name=product_name,
            vehicle_brand=vehicle_brand,
            company=company,
            page=1,
            limit=100000  # 导出时设置较大的限制
        )
        
        if not data_list:
            return jsonify({
                'code': -1,
                'message': '没有数据可导出',
                'data': None
            }), 404
        
        # 生成 CSV 内容
        import csv
        import io
        from flask import Response
        
        # 定义要导出的字段
        export_fields = [
            'oe', 'brand', 'replace_number', 'replace_number_with_keys',
            'product_name', 'vehicle_brand', 'brand_code',
            'max_price', 'min_price', 'supplier_price',
            'inquiry_count', 'month_sales', 'product_remark'
        ]
        
        # 创建 CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=export_fields)
        writer.writeheader()
        
        for item in data_list:
            row = {field: item.get(field, '') for field in export_fields}
            writer.writerow(row)
        
        # 返回 CSV 文件
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=diff_replace_numbers_{company}.csv'
            }
        )
        
    except Exception as e:
        return jsonify({
            'code': -1,
            'message': f'导出失败: {str(e)}',
            'data': None
        }), 500


@bp.route('/diff-replace-numbers/use', methods=['POST'])
@login_required
def api_use_replace_number():
    """
    一键使用替换号
    
    请求参数:
        {
            "product_ids": ["123", "456"],  // 要更新的产品ID列表
            "replace_number": "A000000001119"  // 要使用的替换号
        }
    
    返回:
        {
            "code": 0,
            "message": "success",
            "data": {
                "results": [...]  // 更新结果列表
            }
        }
    """
    try:
        data = request.get_json()
        
        product_ids = data.get('product_ids', [])
        replace_number = data.get('replace_number', '')
        
        if not product_ids:
            return jsonify({
                'code': -1,
                'message': '请选择要更新的产品',
                'data': None
            }), 400
        
        if not replace_number:
            return jsonify({
                'code': -1,
                'message': '替换号不能为空',
                'data': None
            }), 400
        
        # 获取用户门店
        store_code = get_user_company()
        
        # 调用服务层
        results = use_replace_number(
            product_ids=product_ids,
            replace_number=replace_number,
            store_code=store_code
        )
        
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'results': results
            }
        })
        
    except Exception as e:
        return jsonify({
            'code': -1,
            'message': f'操作失败: {str(e)}',
            'data': None
        }), 500
