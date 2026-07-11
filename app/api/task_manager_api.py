# -*- coding:utf-8 -*-
"""
任务管理 API —— 精简版

接口清单：
  GET  /api/tasks/list               所有任务列表（含运行状态）

统一返回：{"code": 200, "msg": "success", "data": {...}}
"""

import logging
from flask import Blueprint, jsonify

from app.core.permission.decorators import require_permission

logger = logging.getLogger(__name__)

task_manager_bp = Blueprint("task_manager", __name__, url_prefix="/tasks")


@task_manager_bp.route("/list", methods=["GET"])
@require_permission("task_manager:list")
def list_tasks():
    from app.core.task_manager import task_manager
    try:
        tm = task_manager

        jobs = []
        if tm._scheduler:
            # 从 task_enhancer 获取任务配置（包含 enabled, demand_driven, description, last_request_time）
            try:
                from app.core.task_enhancer import load_task_config
            except ImportError:
                load_task_config = lambda job_id: {}
            
            for job in tm._scheduler.get_jobs():
                # 获取任务配置，如果没有配置则使用默认值
                cfg = load_task_config(job.id) or {}
                
                jobs.append({
                    "job_id": job.id,
                    "name": job.name,
                    "description": cfg.get("description", ""),
                    "enabled": cfg.get("enabled", True),
                    "paused": job.next_run_time is None,
                    "demand_driven": cfg.get("demand_driven", False),
                    "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                    "last_request_time": cfg.get("last_request_time", None),
                })
        return jsonify({"code": 200, "msg": "success", "data": jobs})
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({"code": 500, "msg": str(e), "data": None})
