"""
安全库存API接口
只处理HTTP请求和响应，不包含业务逻辑
"""

from flask import Blueprint, request, jsonify
from app.services.safety_stock_service import SafetyStockDBService, execute_daily_calculation

safety_stock_api = Blueprint('safety_stock_api', __name__)


@safety_stock_api.route('/api/safety-stock/list', methods=['GET'])
def get_safety_stock_list():
    """
    获取安全库存列表
    
    参数：
        calc_date: 计算日期（默认最新日期）
        stock_status: 库存状态筛选（需补货/库存偏低/库存积压/正常）
        abc_class: ABC分类筛选（A/B/C）
        keyword: 关键词搜索（OE/品牌/产品名称）
        page: 页码（默认1）
        limit: 每页条数（默认50，最大500）
    
    返回：
        {
            code: 0,
            data: [...],
            total: 总条数
        }
    """
    try:
        # 获取参数
        calc_date = request.args.get('calc_date')
        stock_status = request.args.get('stock_status')
        abc_class = request.args.get('abc_class')
        keyword = request.args.get('keyword', '').strip()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        # 查询数据（取消500条限制，最大支持10万条）
        results = SafetyStockDBService.get_calculation_results(
            calc_date=calc_date,
            stock_status=stock_status,
            abc_class=abc_class,
            limit=100000  # 查询大量数据用于内存筛选
        )
        
        # 关键词筛选
        if keyword:
            keyword_lower = keyword.lower()
            results = [
                r for r in results 
                if (keyword_lower in (r.get('frey_no') or '').lower() or
                    keyword_lower in (r.get('product_name') or '').lower())
            ]
        
        # 内存分页（保留分页功能）
        total = len(results)
        start = (page - 1) * limit
        end = start + limit
        paged_results = results[start:end]
        
        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': paged_results,
            'total': total,
            'page': page,
            'limit': limit
        })
        
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'查询失败: {str(e)}',
            'data': [],
            'total': 0
        }), 500


@safety_stock_api.route('/api/safety-stock/calculate', methods=['POST'])
def manual_calculate():
    """
    手动触发安全库存计算
    
    返回：
        {
            code: 0,
            msg: "计算完成，共XXX条记录",
            count: 计算的产品数量
        }
    """
    try:
        count = execute_daily_calculation()
        return jsonify({
            'code': 0,
            'msg': f'计算完成，共{count}条记录',
            'count': count
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'计算失败: {str(e)}',
            'count': 0
        }), 500


@safety_stock_api.route('/api/safety-stock/status-count', methods=['GET'])
def get_status_count():
    """
    获取各状态的统计数量
    
    返回：
        {
            code: 0,
            data: {
                '需补货': 10,
                '库存偏低': 20,
                '库存积压': 5,
                '正常': 100
            }
        }
    """
    try:
        calc_date = request.args.get('calc_date')
        
        # 查询所有数据
        results = SafetyStockDBService.get_calculation_results(
            calc_date=calc_date,
            limit=100000
        )
        
        # 统计各状态数量
        status_count = {}
        for r in results:
            status = r.get('stock_status', '未知')
            status_count[status] = status_count.get(status, 0) + 1
        
        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': status_count
        })
        
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'查询失败: {str(e)}',
            'data': {}
        }), 500
