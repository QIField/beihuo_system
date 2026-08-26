# -*- coding:utf-8 -*-
# @Time    : 2026/08/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_useless_data_service.py
# @Software: trae-cn

"""
安全库存废弃数据业务服务

将 stock_safe 表中某条记录标记为"废弃数据"，写入 stock_safe_useless_data 表。
用于归档被判断为无效、需要从安全库存看板中剔除的零件数据。

说明：
- 只将待废弃的记录写入废弃表（按 frey_no 命中唯一键），不会删除 / 修改
  stock_safe 表中的原始数据。
- 列表查询（stock_safe_query_service）会按 frey_no 排除废弃表中已存在的记录，
  因此废弃后该数据将从看板中隐藏，但原始数据仍保留。

数据流：
    stock_safe（原始记录，保留不动）
        ──查询──►  组装字段  ──INSERT IGNORE──►  stock_safe_useless_data（记录废弃）
"""

from sqlalchemy import select

from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.models.orm_models.stock_safe_models.stock_safe import StockSafe
from app.dao.stock_safe_dao.stock_safe_useless_data_dao import (
    insert_useless_data,
    delete_useless_data_by_freys,
)

# 本模块统一使用 stock_safe 任务 logger，与安全库存其他服务保持日志一致
logger = get_task_logger('stock_safe')


def abandon_stock_safe_rows(ids: list) -> dict:
    """
    废弃指定的一组安全库存记录（仅写入废弃表，不删除 stock_safe 原记录）

    对每个待废弃 id：在 stock_safe 表查询原始记录，组装 number / brand_name /
    frey_no / pdname 写入 stock_safe_useless_data 表（INSERT IGNORE，按 frey_no
    唯一键冲突时跳过，避免重复记录）。

    Args:
        ids: 待废弃的 stock_safe 记录主键 id 列表（需为可转换为 int 的值）

    Returns:
        dict: {
            'code': 0 成功 / 1 失败,
            'msg': 提示信息,
            'total': 请求废弃的记录数,
            'moved': 实际成功写入废弃表的记录数
        }
    """
    # 清洗参数：仅保留合法正整数 id
    clean_ids = []
    for raw in ids or []:
        try:
            val = int(raw)
            if val > 0:
                clean_ids.append(val)
        except (TypeError, ValueError):
            continue

    if not clean_ids:
        logger.warning(f'[安全库存废弃] 参数为空或非法: {ids}')
        return {'code': 1, 'msg': '参数为空或非法', 'total': 0, 'moved': 0}

    with orm_session() as session:
        # ---- 1. 查询待废弃的原始记录（仅取废弃表需要的标识字段） ----
        rows = (
            session.execute(
                select(
                    StockSafe.number,
                    StockSafe.brand_name,
                    StockSafe.frey_no,
                    StockSafe.pdname,
                ).where(StockSafe.id.in_(clean_ids))
            )
            .mappings()
            .all()
        )

        if not rows:
            logger.warning(f'[安全库存废弃] 未找到对应记录: {clean_ids}')
            return {'code': 1, 'msg': '未找到对应记录', 'total': len(clean_ids), 'moved': 0}

        # ---- 2. 组装废弃表字段并写入（INSERT IGNORE，不删除 stock_safe 原记录） ----
        ignore_fields = ('number', 'brand_name', 'frey_no', 'pdname')
        useless_rows = [{k: row[k] for k in ignore_fields} for row in rows]
        moved = insert_useless_data(session, useless_rows)

    logger.info(
        f'[安全库存废弃] 完成: 请求 {len(clean_ids)} 条, 写入废弃表 {moved} 条'
    )

    return {
        'code': 0,
        'msg': 'success',
        'total': len(clean_ids),
        'moved': moved,
    }


def restore_stock_safe_rows(freys: list) -> dict:
    """
    恢复指定条码（frey_no）的废弃记录（从废弃表删除对应记录）

    废弃仅记录在 stock_safe_useless_data 表中，恢复即在表中按 frey_no 删除，
    随后该数据重新纳入查询视图。不会修改 stock_safe 表原始数据。

    Args:
        freys: 待恢复的条码 frey_no 列表

    Returns:
        dict: {
            'code': 0 成功 / 1 失败,
            'msg': 提示信息,
            'restored': 实际恢复（删除）的记录数
        }
    """
    # 清洗参数：去重、去空
    clean_freys = []
    for raw in freys or []:
        if raw is None:
            continue
        val = str(raw).strip()
        if val and val not in clean_freys:
            clean_freys.append(val)

    if not clean_freys:
        logger.warning(f'[安全库存恢复] 参数为空或非法: {freys}')
        return {'code': 1, 'msg': '参数为空或非法', 'restored': 0}

    with orm_session() as session:
        restored = delete_useless_data_by_freys(session, clean_freys)

    logger.info(f'[安全库存恢复] 完成: 请求 {len(clean_freys)} 条, 恢复 {restored} 条')

    return {
        'code': 0,
        'msg': 'success',
        'restored': restored,
    }