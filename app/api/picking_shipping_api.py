# -*- coding:utf-8 -*-
# @Time    : 2026/10/01
# @Project : beihuo_system
# @File    : picking_shipping_api.py
# @Software: trae-cn

"""
拣货发货模块 API 路由

职责：
  1. 提供「已发货」列表的只读查询接口

说明：
  - 页面路由放在 app/routes/picking_shipping_web.py
  - 本文件由 app/api/__init__.py 注册到 /new/api 主蓝图下
  - 所有接口均为只读查询，不产生写操作
"""

from flask import Blueprint, request, jsonify

from app.core.permission.decorators import require_authentication
from app.services.picking_shipping import picking_shipping_service


picking_shipping_bp = Blueprint(
    "picking_shipping",
    __name__,
    url_prefix="/picking_shipping",
)


@picking_shipping_bp.route("/list", methods=["GET"])
@require_authentication()
def picking_shipping_list_api():
    """
    已发货列表查询 API

    请求参数：
      - keyword: 模糊搜索（销售订单号 / 出库单号 / 客户名称）
      - shipper: 操作员
      - ship_date_start: 发货时间起始（YYYY-MM-DD）
      - ship_date_end: 发货时间结束（YYYY-MM-DD）
      - order_date_start: 订单日期起始（YYYY-MM-DD）
      - order_date_end: 订单日期结束（YYYY-MM-DD）
      - has_photos: 是否有图片（空=全部，1=有图片，0=无图片）
      - page: 页码，默认 1
      - limit: 每页条数，默认 20
    """
    try:
        keyword = request.args.get("keyword", "")
        shipper = request.args.get("shipper", "")
        ship_date_start = request.args.get("ship_date_start", "")
        ship_date_end = request.args.get("ship_date_end", "")
        order_date_start = request.args.get("order_date_start", "")
        order_date_end = request.args.get("order_date_end", "")
        has_photos = request.args.get("has_photos", "")
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 20, type=int)

        data = picking_shipping_service.get_shipped_orders(
            keyword=keyword,
            shipper=shipper,
            ship_date_start=ship_date_start,
            ship_date_end=ship_date_end,
            order_date_start=order_date_start,
            order_date_end=order_date_end,
            has_photos=has_photos,
            page=page,
            limit=limit,
        )

        return jsonify({
            "code": 200,
            "msg": "查询成功",
            "data": data,
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"查询已发货列表失败: {str(e)}",
            "data": None,
        })


@picking_shipping_bp.route("/detail", methods=["GET"])
@require_authentication()
def picking_shipping_detail_api():
    """
    订单详情查询 API（已发货 / 待发货共用）

    请求参数：
      - order_id: CRM 订单 ID（必填）
      - status: shipped 或 pending（必填）
    """
    try:
        order_id = request.args.get("order_id", type=int)
        status = request.args.get("status", "")

        if not order_id or status not in ("shipped", "pending"):
            return jsonify({
                "code": 400,
                "msg": "参数错误：order_id 与 status 必填",
                "data": None,
            })

        data = picking_shipping_service.get_order_detail(
            order_id=order_id,
            status=status,
        )

        return jsonify({
            "code": 200,
            "msg": "查询成功",
            "data": data,
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"查询订单详情失败: {str(e)}",
            "data": None,
        })


@picking_shipping_bp.route("/shippers", methods=["GET"])
@require_authentication()
def picking_shipping_shippers_api():
    """
    已发货订单操作员列表 API

    返回已发货订单中所有不重复的操作员名称，用于前端下拉框。
    """
    try:
        data = picking_shipping_service.get_shipped_shippers()
        return jsonify({
            "code": 200,
            "msg": "查询成功",
            "data": data,
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"查询操作员列表失败: {str(e)}",
            "data": None,
        })


@picking_shipping_bp.route("/pending_list", methods=["GET"])
@require_authentication()
def picking_shipping_pending_list_api():
    """
    待发货列表查询 API

    数据实时取自 CRM mergeOrderList，10 分钟缓存。
    请求参数：
      - keyword: 前端内存模糊搜索（销售订单号 / 出库单号 / 客户名称）
      - page: 页码，默认 1
      - limit: 每页条数，默认 20
    """
    try:
        keyword = request.args.get("keyword", "")
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 20, type=int)

        data = picking_shipping_service.get_pending_orders_page(
            keyword=keyword,
            page=page,
            limit=limit,
        )

        return jsonify({
            "code": 200,
            "msg": "查询成功",
            "data": data,
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"查询待发货列表失败: {str(e)}",
            "data": None,
        })