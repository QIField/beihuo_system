# -*- coding:utf-8 -*-
"""
WMS 库存操作推送 - 任务控制服务

职责：
1. 定时运行时间配置的读写（beihuo_system_config 表）
2. 手动触发运行的线程管理与状态查询
3. 根据配置重新注册 APScheduler 任务
"""

import threading
from datetime import datetime
from typing import Any, Dict, List

from app.utils.logger_config import get_task_logger


logger = get_task_logger('wms_inventory_operation')

# 配置 key
SCHEDULE_TIMES_CONFIG_KEY = 'wms_inventory_operation_schedule_times'

# 默认运行时间（配置表无数据时兜底）
DEFAULT_SCHEDULE_TIMES = ["10:00", "20:00"]

# 运行状态（单进程内存态）
_run_state = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_state_lock = threading.Lock()


def get_schedule_times() -> List[str]:
    """读取运行时间配置，格式 ["10:00", "20:00"]"""
    from config.config_list_manager.config_cache import get_config_value

    value = get_config_value(SCHEDULE_TIMES_CONFIG_KEY)
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return list(DEFAULT_SCHEDULE_TIMES)


def save_schedule_times(times: List[str]) -> List[str]:
    """保存运行时间配置并重新注册定时任务"""
    from app.services.system_setting_service.beihuo_system_config_service import set_config_by_key

    # 格式校验与去重排序
    validated = _validate_times(times)
    set_config_by_key(
        SCHEDULE_TIMES_CONFIG_KEY,
        str(validated).replace("'", '"'),
        config_type='json',
        config_group='wms',
        label='WMS采购入库/移除推送运行时间',
    )
    reschedule_tasks()
    return validated


def _validate_times(times: List[str]) -> List[str]:
    """校验时间格式，返回合法的 HH:MM 列表（去重排序）"""
    validated = set()
    for item in times:
        text = str(item).strip()
        parts = text.split(":")
        if len(parts) != 2:
            continue
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            validated.add(f"{hour:02d}:{minute:02d}")
    if not validated:
        return list(DEFAULT_SCHEDULE_TIMES)
    return sorted(validated)


def reschedule_tasks() -> None:
    """移除旧 job 并按当前配置重新注册"""
    from app.core.task_manager import task_manager
    from app.tasks.wms_inventory_operation_task import (
        run_wms_inventory_operation_task,
        register_wms_inventory_operation_jobs,
    )

    # 移除所有旧 job
    for job in task_manager.get_jobs():
        if str(job.get('id', '')).startswith('wms_inventory_operation_task_'):
            task_manager._scheduler.remove_job(job['id'])

    # 按新时间重新注册
    register_wms_inventory_operation_jobs(task_manager)


def start_manual_run() -> Dict[str, Any]:
    """手动触发一次完整流程（后台线程执行）"""
    with _state_lock:
        if _run_state["running"]:
            return {"started": False, "message": "任务正在运行中"}

        _run_state.update({
            "running": True,
            "started_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "finished_at": None,
            "error": None,
        })

    thread = threading.Thread(target=_run_in_background, daemon=True)
    thread.start()
    return {"started": True, "message": "任务已开始运行"}


def _run_in_background() -> None:
    """后台执行完整流程并更新状态"""
    from app.services.wms_inventory_operation_service import run_wms_inventory_operation

    try:
        run_wms_inventory_operation('fsbbr', logger=logger)
        with _state_lock:
            _run_state["running"] = False
            _run_state["finished_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            _run_state["error"] = None
    except Exception as e:
        logger.exception("[手动运行] WMS库存操作推送失败")
        with _state_lock:
            _run_state["running"] = False
            _run_state["finished_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            _run_state["error"] = str(e)


def get_run_status() -> Dict[str, Any]:
    """查询当前运行状态"""
    with _state_lock:
        return dict(_run_state)
