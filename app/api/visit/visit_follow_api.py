# -*- coding:utf-8 -*-
# @Time    : 2026/10/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_follow_api.py
# @Software: PyCharm
# 跟进记录数据接口（设计文档 doc/客访管理/04-跟进记录模块设计.md 第五/六节）
# 跟进记录与拜访记录完全独立，纯手动维护：时间轴查询 / 新增 / 编辑 / 作废。
# 标识传参口径：URL 不带路径参数，客户 id 走 query、跟进记录 id 走 JSON body
# （同 visit_detail_api 风格）。

from flask import jsonify, request, session

from . import visit_bp
# 权限控制：跟进记录接口统一要求「汽配客访管理」权限（visit:view）
from app.core.permission.decorators import require_permission
from app.services.visit_service import follow_record_service


@visit_bp.route("/customers/follows", methods=["GET"])
@require_permission('visit:view')
def get_customer_follows():
    """跟进记录时间轴（M7：按跟进时间倒序分页，渠道筛选选填）

    查询参数：
        id:      visit_amap_customer 主键 id，必填（避免 URL 透传含逗号的 POI 编码）
        page:    页码，默认 1
        limit:   每页条数，默认 20（最大 200）
        channel: 跟进渠道筛选，选填
    """
    try:
        result = follow_record_service.get_follow_list(
            request.args.get("id"),
            page=request.args.get("page", 1),  # pyright: ignore[reportArgumentType]
            limit=request.args.get("limit", 20),  # pyright: ignore[reportArgumentType]
            channel=(request.args.get("channel") or "").strip() or None,
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/follows", methods=["POST"])
@require_permission('visit:view')
def add_follow():
    """新增跟进（表单 JSON：amap_customer_id / channel / content 必填，
    follow_time 缺省当前时间、channel_desc 缺省按渠道映射）"""
    try:
        body = request.get_json(silent=True) or {}
        result = follow_record_service.add_follow(
            body.get("amap_customer_id"),
            body.get("channel"),
            body.get("content"),
            follow_time=body.get("follow_time"),
            channel_desc=body.get("channel_desc") or "",
            creator_id=session.get("user_id"),
            creator_name=session.get("username", ""),
        )
        return jsonify({"code": 200, "msg": "跟进已记录", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"新增失败: {e}", "data": None})


@visit_bp.route("/follows", methods=["PUT"])
@require_permission('visit:view')
def update_follow():
    """编辑跟进（JSON body：id 必填，待更新字段选填：
    channel / content / follow_time / channel_desc，部分更新）"""
    try:
        body = request.get_json(silent=True) or {}
        kwargs = {}
        for key in ("channel", "content", "follow_time", "channel_desc"):
            if key in body:
                kwargs[key] = body.get(key)
        result = follow_record_service.update_follow(body.get("id"), **kwargs)
        return jsonify({"code": 200, "msg": "跟进已更新", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"更新失败: {e}", "data": None})


@visit_bp.route("/follows/void", methods=["PUT"])
@require_permission('visit:view')
def void_follow():
    """作废跟进（JSON body：id 必填；status=0 软删，时间轴排除，本期不提供恢复）"""
    try:
        body = request.get_json(silent=True) or {}
        follow_record_service.void_follow(body.get("id"))
        return jsonify({"code": 200, "msg": "跟进已作废", "data": None})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"作废失败: {e}", "data": None})
