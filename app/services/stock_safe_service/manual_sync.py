# -*- coding:utf-8 -*-
# @Time    : 2026/10/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : manual_sync.py
# @Software: trae-cn

"""
安全库存手动同步服务

职责：
  手动同步数据入队 + 同步执行，供 API 层与定时任务调用。

核心函数：
  - add_manual_sync_queue: 暴露给 API，把手动同步的数据加入队列
  - run_manual_sync:       暴露给定时任务，读取手动队列的数据并执行推送

数据通道：
  1. 进程内去重队列 UniqueQueue（(number, brand_name) 唯一键）：
     add_manual_sync_queue 入队，run_manual_sync 取出执行——这是手动同步唯一的数据来源。
     执行由每 1 分钟轮询的定时任务触发（见 stock_safe_tasks.stock_safe_manual_sync_register），
     队列为空时轮询直接跳过，不产生任何调用开销。
  2. 本模块对 stock_safe_sync_queue 表只做一件事：推送成功后回填 synced_at。
     严格约束：已有行不碰 sync_enabled；行不存在时插入新行，
     但必须显式 sync_enabled=0（默认值 1 会使新行混入自动同步流程的数据范围）。

推送值来源（与 doc/安全库存同步.md 一致，只读）：
  - 执行时实时从 stock_safe 表按 (number, brand_name) 读取：
      safety_stock ← stock_safe.safety_stock
      max_stock ← stock_safe.stock_upper_limit
      season_coefficient ← stock_safe.season_coefficient
      warehouse_id = 1，isnotstock = '0'
  - 推送成功 → 回填 synced_at（仅已存在行）；失败仅记日志，可再次手动入队重试
"""

import time
from datetime import datetime

from app.utils.common_util_module import UniqueQueue
from app.utils.logger_config import get_task_logger
from app.utils.orm.session import orm_session
from app.dao.stock_safe_dao.stock_safe_dao import fetch_push_values_by_keys
from app.dao.stock_safe_dao.sync_queue_dao import (
    fetch_by_number_brand,
    batch_insert_queue,
    update_by_id,
)
from app.services.stock_safe_service.push_data import batch_push_stock_safe_data

# 本模块统一使用 stock_safe 任务 logger，与安全库存其他服务保持日志一致
logger = get_task_logger('stock_safe')

# 进程内手动同步去重队列：以 (number, brand_name) 为唯一键，重复入队自动丢弃
_manual_sync_queue = UniqueQueue(key_func=lambda it: (it["number"], it["brand_name"]))


def has_pending() -> bool:
    """判断进程内手动同步队列是否有待执行数据（供轮询任务空跑跳过）"""
    return len(_manual_sync_queue) > 0


def _backfill_synced_at(success_items: list) -> int:
    """
    推送成功后回填 stock_safe_sync_queue.synced_at

    处理规则（这是手动同步对数据库的唯一写操作）：
      - 行已存在 → 只更新 synced_at，sync_enabled 等其他字段一律不碰
      - 行不存在 → 插入新行，显式 sync_enabled=0、synced_at=now
        （sync_enabled 默认值为 1，显式传 0 避免新行混入自动同步流程
        的数据范围：sync_enabled=1 且 synced_at IS NULL）

    Args:
        success_items: 推送成功且 stock_safe 中有推送值的入队元素列表，
                       每项包含 number / brand_name，可选 frey_no / pdname

    Returns:
        int: 成功回填的记录数
    """
    if not success_items:
        return 0

    backfilled = 0
    now = datetime.now()

    with orm_session() as session:
        existing_ids = []
        missing = []
        for item in success_items:
            number, brand_name = item["number"], item["brand_name"]
            record = fetch_by_number_brand(session, number, brand_name)
            if record is None:
                missing.append({
                    "number": number,
                    "brand_name": brand_name,
                    "frey_no": item.get("frey_no"),
                    "pdname": item.get("pdname"),
                    "sync_enabled": 0,
                })
            else:
                existing_ids.append(record["id"])

        # 行不存在 → 插入新行（显式 sync_enabled=0，不能用默认值 1）
        if missing:
            batch_insert_queue(session, missing)
            for item in missing:
                record = fetch_by_number_brand(session, item["number"], item["brand_name"])
                if record:
                    existing_ids.append(record["id"])
                else:
                    logger.warning(
                        f"[手动同步回填] OE={item['number']} 品牌={item['brand_name']} "
                        f"插入后仍查询不到记录，跳过回填"
                    )

        for queue_id in existing_ids:
            if update_by_id(session, queue_id, {"synced_at": now}):
                backfilled += 1

    return backfilled


def _normalize_items(items: list) -> tuple:
    """
    校验并标准化入队数据

    Args:
        items: 字典列表，每项需包含 number / brand_name，可选 frey_no / pdname

    Returns:
        tuple: (valid_list, invalid_list)
              valid_list: 标准化后的有效数据
              invalid_list: 无效数据及原因
    """
    valid = []
    invalid = []
    for item in items:
        number = str(item.get("number") or "").strip()
        brand_name = str(item.get("brand_name") or "").strip()
        if not number or not brand_name:
            invalid.append({"number": number, "brand_name": brand_name, "reason": "OE号或品牌名为空"})
            continue
        valid.append({
            "number": number,
            "brand_name": brand_name,
            "frey_no": item.get("frey_no"),
            "pdname": item.get("pdname"),
        })
    return valid, invalid


def add_manual_sync_queue(items: list) -> dict:
    """
    把手动同步的数据加入队列（暴露给 API 层调用）

    执行动作：
      1. 校验并标准化数据（number / brand_name 必填）
      2. 加入进程内去重队列 UniqueQueue（重复 key 自动丢弃），等待定时任务取出执行

    本函数不进行任何数据库写入操作。

    Args:
        items: 字典列表，每项需包含 number / brand_name，可选 frey_no / pdname

    Returns:
        dict: {"success": bool, "total": 总数, "valid": 有效数,
               "queued": 新入内存队列数, "invalid": 无效明细}
    """
    if not items:
        return {"success": False, "message": "待同步列表为空", "total": 0,
                "valid": 0, "queued": 0, "invalid": []}

    valid, invalid = _normalize_items(items)
    if not valid:
        return {"success": False, "message": "无有效数据（OE号和品牌名必填）",
                "total": len(items), "valid": 0, "queued": 0, "invalid": invalid}

    # 加入进程内去重队列（重复 key 自动丢弃，返回 False）
    queued = 0
    for item in valid:
        if _manual_sync_queue.put(item):
            queued += 1

    logger.info(
        f"[手动同步入队] 总数={len(items)} 有效={len(valid)} "
        f"入内存队列={queued} 无效={len(invalid)}"
    )

    return {"success": True, "total": len(items), "valid": len(valid),
            "queued": queued, "invalid": invalid}


def run_manual_sync() -> dict:
    """
    读取手动同步队列的数据并执行推送（暴露给定时任务调用）

    执行流程：
      1. 取出进程内手动同步队列（UniqueQueue）的全部数据——只处理手动入队的数据，
         不扫描 stock_safe_sync_queue 表（表内待同步数据属于自动同步流程）
      2. 实时从 stock_safe 读取推送值（safety_stock / stock_upper_limit / season_coefficient，只读）
      3. 调用 batch_push_stock_safe_data 批量推送 CRM（内部复用同一 CrmGzbbrSpider 实例）
      4. 推送成功 → 回填表中 synced_at（已有行只更新 synced_at；
         行不存在则插入新行，显式 sync_enabled=0）

    本流程对数据库的唯一写入是 Step 4 的 synced_at 回填；
    推送失败仅记日志，可再次手动入队重试。

    Returns:
        dict: {"total": 取出数, "success_count": 成功数, "fail_count": 失败数,
               "skipped_no_value": stock_safe 无记录跳过数, "details": 推送明细}
    """
    start = time.time()
    logger.info("[手动同步执行] ====== 开始执行 ======")

    # Step 1: 取出进程内手动同步队列的全部数据
    drained = []
    while True:
        item = _manual_sync_queue.pop()
        if item is None:
            break
        drained.append(item)

    if not drained:
        logger.info("[手动同步执行] 手动队列为空，结束")
        return {"total": 0, "success_count": 0, "fail_count": 0,
                "skipped_no_value": 0, "details": []}

    logger.info(f"[手动同步执行] 取出手动队列 {len(drained)} 条")

    # Step 2: 实时从 stock_safe 读取推送值（只读）
    keys = [(item["number"], item["brand_name"]) for item in drained]
    with orm_session() as session:
        value_list = fetch_push_values_by_keys(session, keys)
    value_map = {(v["number"], v["brand_name"]): v for v in value_list}

    push_records = []
    skipped_no_value = 0
    for item in drained:
        value = value_map.get((item["number"], item["brand_name"]))
        if value is None:
            # stock_safe 中无此商品，无法取推送值；仅记日志，用户可修正后重新入队
            skipped_no_value += 1
            logger.warning(
                f"[手动同步执行] OE={item['number']} 品牌={item['brand_name']} "
                f"stock_safe 中无记录，跳过推送"
            )
            continue
        push_records.append({
            "number": item["number"],
            "brand_name": item["brand_name"],
            "safety_stock": float(value["safety_stock"] or 0),
            "max_stock": float(value["stock_upper_limit"] or 0),
            "season_coefficient": float(value["season_coefficient"] or 1),
        })

    if not push_records:
        logger.info("[手动同步执行] 无可推送数据（stock_safe 中均无记录），结束")
        return {"total": len(drained), "success_count": 0, "fail_count": 0,
                "skipped_no_value": skipped_no_value, "details": []}

    # Step 3: 批量推送 CRM
    logger.info(f"[手动同步执行] 待推送 {len(push_records)} 条")
    push_result = batch_push_stock_safe_data(push_records)
    details = push_result.get("details", [])

    # Step 4: 推送成功的记录回填 synced_at（已有行只更新 synced_at；
    # 行不存在则插入新行，显式 sync_enabled=0，不碰已有行的 sync_enabled）
    success_keys = {
        (d["number"], d["brand_name"]) for d in details if d.get("success")
    }
    success_items = [
        item for item in drained
        if (item["number"], item["brand_name"]) in success_keys
    ]
    backfilled = _backfill_synced_at(success_items)

    success_count = len(success_keys)
    fail_count = len(push_records) - success_count
    logger.info(
        f"[手动同步执行] ====== 完成 取出={len(drained)} "
        f"推送成功={success_count} 失败={fail_count} "
        f"无推送值跳过={skipped_no_value} 回填={backfilled} "
        f"耗时={round(time.time() - start, 2)}s ======"
    )

    return {"total": len(drained), "success_count": success_count,
            "fail_count": fail_count, "skipped_no_value": skipped_no_value,
            "details": details}
