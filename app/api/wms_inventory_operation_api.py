# -*- coding:utf-8 -*-
"""
WMS 库存操作推送 - 管理 API

接口：
1. GET  /schedule_times   获取定时运行时间
2. POST /schedule_times   保存定时运行时间
3. POST /run               手动触发运行
4. GET  /run_status        查询运行状态
"""

from flask import Blueprint, jsonify, request

from app.services.wms_inventory_operation_service.task_control_service import (
    get_run_status,
    get_schedule_times,
    save_schedule_times,
    start_manual_run,
)


wms_inventory_operation_bp = Blueprint(
    "wms_inventory_operation", __name__, url_prefix="/wms_inventory_operation"
)


@wms_inventory_operation_bp.route("/schedule_times", methods=["GET"])
def get_schedule_times_api():
    """获取定时运行时间"""
    times = get_schedule_times()
    return jsonify({"code": 200, "msg": "success", "data": {"times": times}})


@wms_inventory_operation_bp.route("/schedule_times", methods=["POST"])
def save_schedule_times_api():
    """保存定时运行时间"""
    body = request.get_json(silent=True) or {}
    times = body.get("times", [])
    if not isinstance(times, list):
        return jsonify({"code": 400, "msg": "times 必须为数组", "data": None})

    saved = save_schedule_times(times)
    return jsonify({"code": 200, "msg": "success", "data": {"times": saved}})


@wms_inventory_operation_bp.route("/run", methods=["POST"])
def run_api():
    """手动触发一次完整流程"""
    result = start_manual_run()
    if not result["started"]:
        return jsonify({"code": 400, "msg": result["message"], "data": None})
    return jsonify({"code": 200, "msg": result["message"], "data": None})


@wms_inventory_operation_bp.route("/run_status", methods=["GET"])
def run_status_api():
    """查询运行状态"""
    return jsonify({"code": 200, "msg": "success", "data": get_run_status()})
