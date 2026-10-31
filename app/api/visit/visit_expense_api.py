# -*- coding:utf-8 -*-
# @Time    : 2026/10/29 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_expense_api.py
# @Software: PyCharm
# 客访管理 - 费用 API（设计文档 doc/客访管理/09-费用分析.md）
# 包含：费用明细 CRUD + 批量新增 + 汇总/趋势/排名聚合
# 总利益公式中的"拿货额/退货金/成本"由前端另行调用
# visit_detail_api.py 的客户详情聚合，本文件只负责费用侧数据。

from flask import jsonify, request, session

from . import visit_bp
# 权限控制：费用侧接口同时要求「汽配客访管理」(visit:view) +
# 「汽配客访管理费用」(visit:expense) 两个权限（AND 校验，未登录返回 401，权限不足返回 403）
from app.core.permission.decorators import require_all_permissions
from app.services.visit_service import visit_expense_service


# ==================== CRUD ====================

@visit_bp.route("/expenses", methods=["POST"])
@require_all_permissions(['visit:view', 'visit:expense'])
def create_expense():
    """新增单条费用（设计文档 6.1）

    请求体 JSON：
        source_type:    必填 关联来源 1-拜访 2-跟进 3-订单(crm_sales_order.orders_id) 4-手动输入
        source_id:      条件必填 关联记录 ID（source_type=1/2/3 时必填，=4 时空）
        amap_customer_id: 必填 高德客户 POI 编码（source_type=1/2 未传时从关联记录反查）
        expense_date:   选填 费用日期 YYYY-MM-DD（不传默认今天）
        expense_type:   必填 费用类型（枚举：拜访投入/礼品物料投入/接待投入/服务投入/索赔/其他）
        amount:         必填 金额 > 0
        description:    选填 费用说明/备注
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = visit_expense_service.create_expense(
            data=payload,
            recorder_id=session.get("user_id"),
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"新增失败: {e}", "data": None})


@visit_bp.route("/expenses/batch", methods=["POST"])
@require_all_permissions(['visit:view', 'visit:expense'])
def batch_create_expenses():
    """批量新增费用（设计文档 6.1 批量接口）

    请求体 JSON：
        items: [ {...}, {...} ] 数组，每项字段同单条接口
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = visit_expense_service.batch_create_expenses(
            items=payload.get("items", []),
            recorder_id=session.get("user_id"),
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"批量新增失败: {e}", "data": None})


@visit_bp.route("/expenses/<int:expense_id>", methods=["GET"])
@require_all_permissions(['visit:view', 'visit:expense'])
def get_expense_detail(expense_id):
    """费用详情"""
    try:
        result = visit_expense_service.get_expense_detail(expense_id)
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 404, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/expenses/<int:expense_id>", methods=["PUT"])
@require_all_permissions(['visit:view', 'visit:expense'])
def update_expense(expense_id):
    """编辑费用（仅允许日期/金额/类型/说明）"""
    try:
        payload = request.get_json(silent=True) or {}
        result = visit_expense_service.update_expense(expense_id, payload)
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"编辑失败: {e}", "data": None})


@visit_bp.route("/expenses/<int:expense_id>/void", methods=["PUT"])
@require_all_permissions(['visit:view', 'visit:expense'])
def void_expense(expense_id):
    """作废费用"""
    try:
        result = visit_expense_service.void_expense(expense_id)
        return jsonify({"code": 200, "msg": "已作废", "data": result})
    except ValueError as e:
        return jsonify({"code": 404, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"作废失败: {e}", "data": None})


@visit_bp.route("/expenses/<int:expense_id>/restore", methods=["PUT"])
@require_all_permissions(['visit:view', 'visit:expense'])
def restore_expense(expense_id):
    """恢复已作废费用"""
    try:
        result = visit_expense_service.restore_expense(expense_id)
        return jsonify({"code": 200, "msg": "已恢复", "data": result})
    except ValueError as e:
        return jsonify({"code": 404, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"恢复失败: {e}", "data": None})


# ==================== 列表查询 ====================

@visit_bp.route("/expenses", methods=["GET"])
@require_all_permissions(['visit:view', 'visit:expense'])
def get_expense_list():
    """费用明细分页查询（费用分析页列表）

    查询参数：
        page / limit:       分页
        keyword:            高德客户名称关键词（模糊匹配客户名称）
        amap_customer_id:   按客户筛选
        recorder_id:        按录入人筛选
        status:             状态筛选（不传默认只看正常 1；传 0 看已作废）
        date_start / date_end: 费用日期范围（YYYY-MM-DD，含边界）
    """
    try:
        result = visit_expense_service.get_expense_list(
            page=request.args.get("page", 1),
            limit=request.args.get("limit", 20),
            amap_customer_id=request.args.get("amap_customer_id"),
            recorder_id=request.args.get("recorder_id"),
            status=request.args.get("status", type=int),
            date_start=request.args.get("date_start"),
            date_end=request.args.get("date_end"),
            keyword=request.args.get("keyword"),
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/records/<int:record_id>/expenses", methods=["GET"])
@require_all_permissions(['visit:view', 'visit:expense'])
def get_record_expenses(record_id):
    """按关联记录查费用（拜访时间轴卡片内嵌展示）

    查询参数：
        source_type: 1-拜访 2-跟进（默认 1）
    """
    try:
        source_type = request.args.get("source_type", 1, type=int)
        result = visit_expense_service.get_expenses_by_source(source_type, record_id)
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


# ==================== 订单搜索 ====================

@visit_bp.route("/orders/search", methods=["GET"])
@require_all_permissions(['visit:view', 'visit:expense'])
def search_orders():
    """订单搜索（费用关联订单选择器用，口径同拿货订单 Tab：sales_order_history 订单级）

    查询参数：
        keyword:           关键词（发货金蝶号/订单号/订单金蝶号）
        limit:             返回条数（默认 20，最大 50）
        amap_customer_id:  高德客户POI编码（选填；客户详情场景传入后，
                           仅返回该客户绑定 CRM 客户名下的订单）
    """
    try:
        result = visit_expense_service.search_orders(
            keyword=request.args.get("keyword"),
            limit=request.args.get("limit", 20),
            amap_customer_id=request.args.get("amap_customer_id"),
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


# ==================== 聚合查询 ====================

@visit_bp.route("/expenses/summary", methods=["GET"])
@require_all_permissions(['visit:view', 'visit:expense'])
def get_expense_summary():
    """费用汇总（费用分析页汇总卡 + 类型占比 + 趋势）

    查询参数：
        amap_customer_id: 按客户筛选（选填）
        month:            月份 YYYY-MM（选填，不传则默认本年）
        year:             年份 YYYY（选填）
        all:              传 1 时不限时间窗口，统计全部历史费用（客户累计投入场景）
    """
    try:
        result = visit_expense_service.get_summary(
            amap_customer_id=request.args.get("amap_customer_id"),
            month=request.args.get("month"),
            year=request.args.get("year"),
            all_time=(request.args.get("all") in ("1", "true", "True")),
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/expenses/ranking", methods=["GET"])
@require_all_permissions(['visit:view', 'visit:expense'])
def get_expense_ranking():
    """客户费用排名

    查询参数：
        date_start / date_end: 日期范围（选填）
        top_n: Top N（默认 20，最大 100）
    """
    try:
        result = visit_expense_service.get_ranking(
            date_start=request.args.get("date_start"),
            date_end=request.args.get("date_end"),
            top_n=request.args.get("top_n", 20),
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})
