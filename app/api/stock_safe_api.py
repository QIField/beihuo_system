# -*- coding:utf-8 -*-
# @Time    : 2026/08/13
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_api.py
# @Software: trae-cn

"""
安全库存 API 接口（stock_safe 表）

处理 HTTP 请求和响应，不包含业务逻辑。
所有查询委托给 stock_safe_query_service。
支持服务端排序和分页。
"""

from flask import Blueprint, request, jsonify
from app.services.stock_safe_service.stock_safe_query_service import (
    get_stock_safe_list,
    get_status_count,
    get_abc_count,
)


# 创建子蓝图，url_prefix 将在主蓝图注册时拼接
stock_safe_bp = Blueprint('stock_safe_bp', __name__, url_prefix='/stock_safe')


@stock_safe_bp.route('/list', methods=['GET'])
def api_stock_safe_list():
    """
    获取安全库存分页列表（服务端排序 + 分页）

    查询参数：
        keyword:             搜索关键词（OE号/品牌/产品名称/条码）
        stock_status:        库存状态筛选
        abc_classification:  ABC 分类筛选（A/B/C）
        page:                页码，默认 1
        limit:               每页条数，默认 50，最大 500
        sort_field:          排序字段名（如 available_stock、avg_daily_sales 等）
        sort_order:          排序方向，asc 升序 / desc 降序

    返回：
        {
            "code": 0,
            "msg": "success",
            "data": {
                "list": [...],
                "total": 100,
                "page": 1,
                "limit": 50
            }
        }
    """
    try:
        keyword = request.args.get('keyword', '').strip()
        stock_status = request.args.get('stock_status', '').strip()
        sales_status = request.args.get('sales_status', '').strip()
        abc_classification = request.args.get('abc_classification', '').strip()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        sort_field = request.args.get('sort_field', '').strip()
        sort_order = request.args.get('sort_order', 'asc').strip()

        # 校验排序方向
        if sort_order not in ('asc', 'desc'):
            sort_order = 'asc'

        result = get_stock_safe_list(
            keyword=keyword,
            stock_status=stock_status,
            sales_status=sales_status,
            abc_classification=abc_classification,
            page=page,
            limit=limit,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': result,
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'查询失败: {str(e)}',
            'data': {'list': [], 'total': 0, 'page': 1, 'limit': 50},
        }), 500


@stock_safe_bp.route('/status-count', methods=['GET'])
def api_status_count():
    """
    获取各库存状态的数量统计（用于前端卡片展示）

    返回：
        {
            "code": 0,
            "msg": "success",
            "data": {
                "呆滞清库": 10, "慢动销去库": 5,
                "紧急补货": 8, "需补货": 20,
                "库存积压": 3, "正常": 100
            }
        }
    """
    try:
        data = get_status_count()
        return jsonify({'code': 0, 'msg': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询失败: {str(e)}', 'data': {}}), 500


@stock_safe_bp.route('/abc-count', methods=['GET'])
def api_abc_count():
    """
    获取各 ABC 分类的数量统计

    返回：
        { "code": 0, "msg": "success", "data": {"A": 100, "B": 300, "C": 100} }
    """
    try:
        data = get_abc_count()
        return jsonify({'code': 0, 'msg': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询失败: {str(e)}', 'data': {}}), 500


