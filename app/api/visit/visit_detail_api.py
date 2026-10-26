# -*- coding:utf-8 -*-
# @Time    : 2026/10/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_detail_api.py
# @Software: PyCharm
# 客户详情数据接口（设计文档 doc/客访管理/01-主设计文档.md 第七节）
# 本期实现：详情聚合（详情头部 + 基础档案）、指标卡聚合（核心指标 + 近30天动态）；
# 服务层见 app/services/visit_service/customer_detail_service.py / customer_stats_service.py。

from flask import jsonify, request

from . import visit_bp
from app.core.permission.decorators import require_authentication
from app.services.visit_service import customer_detail_service, customer_order_service, customer_stats_service


@visit_bp.route("/customers/stats", methods=["GET"])
@require_authentication()
def get_visit_customer_stats():
    """客户详情-指标卡聚合（M3：核心指标 + 近30天动态，01 文档第六节）

    查询参数：
        id: visit_amap_customer 主键 id，必填

    指标卡与近30天动态统一由本接口返回渲染契约（label/value/valueCls），
    数据源未接入的指标固定返回"暂时无数据"；拜访转化率已按业务要求删除（2026-10-22）。
    """
    try:
        result = customer_stats_service.get_customer_stats(
            (request.args.get("id") or "").strip())
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 404, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/customers/detail", methods=["GET"])
@require_authentication()
def get_visit_customer_detail():
    """客户详情聚合（详情头部 + 基础档案，01 文档第六节）

    查询参数：
        id: visit_amap_customer 主键 id，必填

    返回 customer（头部展示字段）/ amap（高德端采集信息）/
    crm_list（CRM端销售信息列表，1:N 绑定，未关联或绑定客户失效时为空数组）三组数据；
    流失预警判定暂不开放（阈值待业务给数）。
    """
    try:
        result = customer_detail_service.get_customer_detail(
            (request.args.get("id") or "").strip())
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 404, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/customers/orders", methods=["GET"])
@require_authentication()
def get_visit_customer_orders():
    """客户详情-拿货订单 Tab 聚合（M5：汇总卡 + 订单分页列表，01 文档第六节）

    查询参数：
        id:    visit_amap_customer 主键 id，必填
        page:  页码，默认 1
        limit: 每页条数，默认 10（最大 100）

    前端切到「拿货订单」Tab 时才请求（进入详情页不加载）。
    订单经 visit_customer_relation（1:N）取全部 partner_id 后按客户集合聚合；
    销售额口径仅常规订单（排除退货）；关联拜访列数据本期留空。
    """
    try:
        result = customer_order_service.get_customer_orders(
            (request.args.get("id") or "").strip(),
            page=request.args.get("page", 1),  # pyright: ignore[reportArgumentType]
            limit=request.args.get("limit", 10),  # pyright: ignore[reportArgumentType]
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 404, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})
