# -*- coding:utf-8 -*-
# @Time    : 2026/10/18
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : sync_queue.py
# @Software: trae-cn

"""
安全库存同步设置业务服务

职责：
  管理 stock_safe_sync_queue 表的同步开关（sync_enabled）。

核心逻辑：
  - 开启同步（sync_enabled=1）：
      查表是否已有 (number, brand_name) 记录：
        - 没有 → 新增一条记录，sync_enabled=1
        - 有   → 将该记录的 sync_enabled 更新为 1
  - 关闭同步（sync_enabled=0）：
      查表是否已有 (number, brand_name) 记录：
        - 没有 → 新增一条记录，sync_enabled=0（显式标记不同步）
        - 有   → 将该记录的 sync_enabled 更新为 0
"""

from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.dao.stock_safe_dao.sync_queue_dao import (
    fetch_by_number_brand,
    batch_insert_queue,
    update_by_id,
)

# 本模块统一使用 stock_safe 任务 logger，与安全库存其他服务保持日志一致
logger = get_task_logger('stock_safe')


def set_sync_enabled(number, brand_name, enabled, frey_no=None, pdname=None) -> dict:
    """
    设置某条 (number, brand_name) 记录的同步开关状态

    Args:
        number: OE 号
        brand_name: 品牌名
        enabled: 是否开启同步，1=开启，0=关闭
        frey_no: 条码（新增记录时写入，可选）
        pdname: 产品名称（新增记录时写入，可选）

    Returns:
        dict: {"success": bool, "sync_enabled": int, "action": str}
              action: "insert"=新增 / "update"=更新
    """
    if not number or not brand_name:
        return {"success": False, "message": "OE号和品牌名不能为空", "sync_enabled": enabled}

    enabled = 1 if enabled else 0

    with orm_session() as session:
        record = fetch_by_number_brand(session, number, brand_name)

        if record:
            # 记录已存在，更新 sync_enabled
            update_by_id(session, record["id"], {"sync_enabled": enabled})
            action = "update"
            logger.info(
                f"[同步设置] 更新 OE={number} 品牌={brand_name} "
                f"sync_enabled={enabled}（原={record.get('sync_enabled')}）"
            )
        else:
            # 记录不存在，新增
            batch_insert_queue(session, [{
                "number": number,
                "brand_name": brand_name,
                "frey_no": frey_no,
                "pdname": pdname,
                "sync_enabled": enabled,
            }])
            action = "insert"
            logger.info(
                f"[同步设置] 新增 OE={number} 品牌={brand_name} "
                f"sync_enabled={enabled}"
            )

    return {"success": True, "sync_enabled": enabled, "action": action}


def batch_set_sync_enabled(items: list, enabled) -> dict:
    """
    批量设置同步开关（在同一个会话内处理所有记录）

    对每个 (number, brand_name)：
      - 记录已存在 → 更新 sync_enabled
      - 记录不存在 → 新增一条，sync_enabled=enabled

    Args:
        items: 字典列表，每项需包含 number / brand_name，可选 frey_no / pdname
        enabled: 是否开启同步，1=开启，0=关闭

    Returns:
        dict: {"success": bool, "enabled": int, "updated": 更新数,
               "inserted": 新增数, "total": 总数, "failed": 失败明细列表}
    """
    if not items:
        return {"success": False, "message": "待设置列表为空",
                "enabled": 1 if enabled else 0, "updated": 0, "inserted": 0,
                "total": 0, "failed": []}

    enabled = 1 if enabled else 0
    updated = 0
    inserted = 0
    failed = []

    with orm_session() as session:
        for item in items:
            number = str(item.get("number") or "").strip()
            brand_name = str(item.get("brand_name") or "").strip()

            if not number or not brand_name:
                failed.append({"number": number, "brand_name": brand_name,
                               "reason": "OE号或品牌名为空"})
                continue

            record = fetch_by_number_brand(session, number, brand_name)
            if record:
                update_by_id(session, record["id"], {"sync_enabled": enabled})
                updated += 1
            else:
                batch_insert_queue(session, [{
                    "number": number,
                    "brand_name": brand_name,
                    "frey_no": item.get("frey_no"),
                    "pdname": item.get("pdname"),
                    "sync_enabled": enabled,
                }])
                inserted += 1

    logger.info(
        f"[同步设置] 批量设置 sync_enabled={enabled} "
        f"总数={len(items)} 更新={updated} 新增={inserted} 失败={len(failed)}"
    )

    return {
        "success": True,
        "enabled": enabled,
        "updated": updated,
        "inserted": inserted,
        "total": len(items),
        "failed": failed,
    }


