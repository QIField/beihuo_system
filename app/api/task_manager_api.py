# -*- coding:utf-8 -*-
"""
任务管理 API —— 精简版

接口清单：
  GET  /api/tasks/list                        所有任务列表（含运行状态）
  POST /api/tasks/crm_warehouse_inventory_sync/run   手动触发 CRM 仓库库存同步任务

统一返回：{"code": 200, "msg": "success", "data": {...}}
"""

import logging
from flask import Blueprint, jsonify, request

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


@task_manager_bp.route("/crm_warehouse_inventory_sync/run", methods=["POST"])
@require_permission("task_manager:run")
def run_crm_warehouse_inventory_sync_task():
    """
    手动触发 CRM 仓库库存同步任务。

    请求参数（可选）：
      - company: 门店代码，如 fsbbr；不传则同步所有配置门店
    """
    from app.core.task_manager import task_manager
    from app.services.crm_inventory.crm_warehouse_inventory_sync import (
        sync_company_inventory,
        SHOP_MAPPING,
    )
    from app.tasks.crm_warehouse_inventory_sync_task import run_crm_warehouse_inventory_sync

    company = request.json.get("company") if request.is_json else request.form.get("company")

    if company and company not in SHOP_MAPPING:
        return jsonify({
            "code": 400,
            "msg": f"未知门店: {company}，可选: {list(SHOP_MAPPING.keys())}",
            "data": None
        }), 400

    try:
        if company:
            task_manager.submit(sync_company_inventory, company)
            logger.info(f"[手动触发] CRM 仓库库存同步任务已提交，门店: {company}")
            return jsonify({
                "code": 200,
                "msg": "success",
                "data": {"company": company, "status": "submitted"}
            })
        else:
            task_manager.submit(run_crm_warehouse_inventory_sync)
            logger.info("[手动触发] CRM 仓库库存全量同步任务已提交")
            return jsonify({
                "code": 200,
                "msg": "success",
                "data": {"company": "all", "status": "submitted"}
            })
    except Exception as e:
        logger.error(f"[手动触发] CRM 仓库库存同步任务提交失败: {e}")
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500
