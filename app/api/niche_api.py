# -*- coding:utf-8 -*-
"""
商机（niche）模块 API 路由

职责：
  1. 提供商机列表、统计、Top N 等查询接口

说明：
  - 页面路由放在 app/routes/niche_web.py
  - 本文件只负责数据接口，由 app/api/__init__.py 注册到 /new/api 主蓝图下
  - 补货导出与手动刷新已移除，商机数据由每日凌晨 2:00 定时任务自动刷新
"""

from flask import Blueprint, request, jsonify

from app.core.permission.decorators import require_authentication
from app.services.niche_services import opportunity_query_service


niche_bp = Blueprint(
    "niche",
    __name__,
    url_prefix='/niche'
)


# =============================================================================
# 商机列表与统计 API
# =============================================================================

@niche_bp.route("/list", methods=["GET"])
@require_authentication()
def niche_list_api():
    """
    商机列表分页查询 API

    请求参数：
      - keyword: 关键词（OE号/品牌/配件名称）
      - opportunity_level: 商机等级 S/A/B/C/D
      - min_score: 最低商机评分（0~100）
      - min_oos_rate: 最低缺货率（0~1）
      - has_replenish: 是否有补货建议（1=是，0=全部）
      - page: 页码，默认 1
      - limit: 每页条数，默认 50
      - sort_field: 排序字段名
      - sort_order: asc / desc
    """
    try:
        keyword = request.args.get('keyword', '')
        opportunity_level = request.args.get('opportunity_level', '')
        min_score = request.args.get('min_score', 0, type=float)
        min_oos_rate = request.args.get('min_oos_rate', 0, type=float)
        has_replenish = request.args.get('has_replenish', 0, type=int)
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        sort_field = request.args.get('sort_field', '')
        sort_order = request.args.get('sort_order', 'desc')

        result = opportunity_query_service.get_niche_opportunity_list(
            keyword=keyword,
            opportunity_level=opportunity_level,
            min_score=min_score,
            min_oos_rate=min_oos_rate,
            has_replenish=has_replenish,
            page=page,
            limit=limit,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        return jsonify({
            'code': 200,
            'msg': '查询成功',
            'data': result,
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询商机列表失败: {str(e)}',
            'data': None,
        })


@niche_bp.route("/summary", methods=["GET"])
@require_authentication()
def niche_summary_api():
    """
    商机统计摘要 API

    返回各等级商机数量以及有补货建议的记录数。
    """
    try:
        level_count = opportunity_query_service.get_level_count()
        replenish_count = opportunity_query_service.get_replenish_count()

        return jsonify({
            'code': 200,
            'msg': '查询成功',
            'data': {
                **level_count,
                'replenish': replenish_count,
            },
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询商机统计失败: {str(e)}',
            'data': None,
        })


@niche_bp.route("/top", methods=["GET"])
@require_authentication()
def niche_top_api():
    """
    Top N 商机 API

    请求参数：
      - top_n: 返回数量，默认 10
    """
    try:
        top_n = request.args.get('top_n', 10, type=int)
        result = opportunity_query_service.get_top_opportunities(top_n=top_n)

        return jsonify({
            'code': 200,
            'msg': '查询成功',
            'data': result,
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询 Top 商机失败: {str(e)}',
            'data': None,
        })


