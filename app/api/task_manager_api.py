# -*- coding:utf-8 -*-
"""
任务管理 API —— 精简版

接口清单：
  GET  /api/tasks/health             健康检查
  GET  /api/tasks/list               所有任务列表（含运行状态）
  POST /api/tasks/toggle             切换任务启用/禁用
  POST /api/tasks/set_enabled        显式设置启用/禁用
  POST /api/tasks/request            按需执行心跳（标记"有请求"）
  POST /api/tasks/demand_driven      开/关按需执行模式
  GET  /api/tasks/config/<job_id>    读任务配置
  POST /api/tasks/config/<job_id>    写任务配置

统一返回：{"code": 200, "msg": "success", "data": {...}}
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

task_manager_bp = Blueprint("task_manager", __name__, url_prefix="/api/tasks")


# ----------------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------------

def _get_tm():
    """调用时才获取 task_manager 实例，避免模块级 import"""
    from app.core.task_enhancer import get_task_manager
    return get_task_manager()


def _jsonify(data, msg="success"):
    return jsonify({"code": 200, "msg": msg, "data": data})


def _error(msg, code=400):
    return jsonify({"code": code, "msg": msg, "data": None})


# ----------------------------------------------------------------------
# 接口
# ----------------------------------------------------------------------

@task_manager_bp.route("/health", methods=["GET"])
def health():
    """健康检查"""
    try:
        from app.core.task_enhancer import is_installed
        tm = _get_tm()
        return _jsonify({
            "enhancer_installed": is_installed(),
            "scheduler_initialized": tm._initialized if tm else False,
            "scheduler_alive": tm._scheduler.running if tm and tm._scheduler else False,
        })
    except ValueError as e:
        return _error(f"未初始化: {e}", 503)
    except Exception as e:
        return _error(str(e), 500)


@task_manager_bp.route("/list", methods=["GET"])
def list_tasks():
    """所有任务列表（含运行状态、下次执行时间）"""
    try:
        tm = _get_tm()
        configs = {c["job_id"]: c for c in tm.get_all_task_configs()}

        jobs = []
        if tm._scheduler:
            for job in tm._scheduler.get_jobs():
                cfg = configs.get(job.id, {})
                jobs.append({
                    "job_id": job.id,
                    "name": job.name,
                    "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                    "paused": job.next_run_time is None,
                    "enabled": cfg.get("enabled", True),
                    "demand_driven": cfg.get("demand_driven", False),
                    "last_request_time": cfg.get("last_request_time"),
                    "description": cfg.get("description", ""),
                })
        return _jsonify(jobs)
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return _error(str(e), 500)


@task_manager_bp.route("/toggle", methods=["POST"])
def toggle():
    """切换任务启用/禁用
    Body: {"job_id": "my_task_id"}
    """
    try:
        data = request.get_json() or {}
        job_id = data.get("job_id")
        if not job_id:
            return _error("缺少 job_id")
        tm = _get_tm()
        return _jsonify(tm.toggle_job(job_id))
    except Exception as e:
        logger.error(f"切换任务失败: {e}")
        return _error(str(e), 500)


@task_manager_bp.route("/set_enabled", methods=["POST"])
def set_enabled():
    """显式设置启用/禁用
    Body: {"job_id": "xxx", "enabled": true/false}
    """
    try:
        data = request.get_json() or {}
        job_id = data.get("job_id")
        enabled = data.get("enabled", True)
        if not job_id:
            return _error("缺少 job_id")
        tm = _get_tm()
        return _jsonify(tm.set_job_enabled(job_id, enabled))
    except Exception as e:
        logger.error(f"设置任务启用状态失败: {e}")
        return _error(str(e), 500)


@task_manager_bp.route("/request", methods=["POST"])
def mark_request():
    """按需执行心跳 —— 告诉系统最近有人用
    Body: {"job_id": "xxx"}
    """
    try:
        data = request.get_json() or {}
        job_id = data.get("job_id")
        if not job_id:
            return _error("缺少 job_id")
        tm = _get_tm()
        return _jsonify(tm.record_task_request(job_id))
    except Exception as e:
        logger.error(f"记录任务请求失败: {e}")
        return _error(str(e), 500)


@task_manager_bp.route("/demand_driven", methods=["POST"])
def set_demand_driven():
    """开/关任务的按需执行模式
    Body: {"job_id": "xxx", "enabled": true, "idle_timeout_minutes": 30}
    """
    try:
        data = request.get_json() or {}
        job_id = data.get("job_id")
        enabled = data.get("enabled", True)
        idle_timeout = data.get("idle_timeout_minutes")
        if not job_id:
            return _error("缺少 job_id")
        tm = _get_tm()
        result = tm.set_demand_driven(job_id, enabled, idle_timeout_minutes=idle_timeout)
        return _jsonify(result)
    except Exception as e:
        logger.error(f"设置按需执行模式失败: {e}")
        return _error(str(e), 500)


@task_manager_bp.route("/config/<job_id>", methods=["GET"])
def get_config(job_id):
    """获取单个任务配置"""
    try:
        tm = _get_tm()
        cfg = tm.get_task_config(job_id)
        if cfg is None:
            return _error(f"任务 [{job_id}] 未找到配置", 404)
        return _jsonify(cfg)
    except Exception as e:
        logger.error(f"获取任务配置失败: {e}")
        return _error(str(e), 500)


@task_manager_bp.route("/config/<job_id>", methods=["POST"])
def set_config(job_id):
    """保存任务配置
    Body: {"enabled": true, "demand_driven": false, ...}
    """
    try:
        from app.core.task_enhancer import save_task_config
        data = request.get_json() or {}
        if not data:
            return _error("body 不能为空")
        save_task_config(job_id, data)
        return _jsonify({"job_id": job_id, "updated": True})
    except Exception as e:
        logger.error(f"保存任务配置失败: {e}")
        return _error(str(e), 500)
