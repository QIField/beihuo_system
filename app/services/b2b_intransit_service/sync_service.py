# -*- coding: utf-8 -*-
"""
物料在途库存同步 - 编排服务

流程：
  1. 幂等建表
  2. 读取 B2B token
  3. 调用"获取物料在途库存列表"接口（网络异常自动重试）
  4. 响应解析、展平、字段校验与完整性对账
  5. 事务内物理删除旧快照并批量写入新快照

安全约束：接口调用或解析失败时不执行任何删除操作，防止误清空。
"""

from datetime import datetime

from app.utils.logger_config import get_task_logger
from app.utils.orm import orm_session
from .api_client import fetch_in_transit_stock
from .config import COMPANY_TOKEN_CONFIGS
from .data_processor import extract_products, flatten_and_validate
from .db_service import ensure_tables, replace_snapshot_for_company

logger = get_task_logger('b2b_intransit_sync')


def _get_token(token_config_key):
    """从系统配置表读取指定公司的 B2B token"""
    from config.config_list_manager.config_cache import get_config_value
    token = get_config_value(token_config_key)
    if not token:
        raise RuntimeError(f"系统配置中未找到 token: {token_config_key}")
    return token


def _sync_company(company, token_config_key, sync_start):
    """同步单个公司的在途库存数据"""
    logger.info(f"[在途同步] 开始同步公司: {company}")
    token = _get_token(token_config_key)
    payload = fetch_in_transit_stock(token)
    products = extract_products(payload)
    records, stats = flatten_and_validate(products, sync_start, company)
    logger.info(
        f"[在途同步] 公司 {company}: 产品{stats['product_count']} "
        f"明细{stats['item_count']} 合法{stats['valid_count']} 丢弃{stats['invalid_count']}"
    )
    return records, stats


def _config_for_company(company):
    """根据公司代码查找同步配置"""
    for config in COMPANY_TOKEN_CONFIGS:
        if config['company'] == company:
            return config
    raise RuntimeError(f"未找到公司在途同步配置: {company}")


def run_in_transit_sync_for_company(company):
    """
    执行单个公司的物料在途库存同步

    :param company: 公司代码，如 'fsbbr'
    :return: 本次同步统计 dict
    :raises: 同步失败时抛出异常，不执行数据库删除操作
    """
    ensure_tables()

    sync_start = datetime.now()
    config = _config_for_company(company)
    records, stats = _sync_company(company, config['token_config_key'], sync_start)

    # 完整性对账：明细总数 = 合法数 + 丢弃数
    if stats['item_count'] != stats['valid_count'] + stats['invalid_count']:
        logger.warning(
            f"[在途同步] 数量对账异常: 明细{stats['item_count']} != "
            f"合法{stats['valid_count']} + 丢弃{stats['invalid_count']}"
        )

    # 事务内按公司重建快照
    with orm_session() as session:
        deleted_count, inserted_count = replace_snapshot_for_company(session, company, records)

    sync_end = datetime.now()
    logger.info(
        f"[在途同步] 公司 {company} 完成: 产品{stats['product_count']} 明细{stats['item_count']} "
        f"入库{inserted_count} 丢弃{stats['invalid_count']} 清理旧数据{deleted_count} "
        f"耗时{(sync_end - sync_start).total_seconds():.1f}s"
    )

    return stats


def run_in_transit_sync():
    """
    执行一次物料在途库存同步（五家公司全部成功后统一重建快照）

    :return: 本次同步统计 dict
    :raises: 任意公司同步失败时抛出异常，不执行数据库删除操作
    """
    ensure_tables()

    sync_start = datetime.now()
    total_stats = {'product_count': 0, 'item_count': 0, 'valid_count': 0, 'invalid_count': 0}
    all_records = []

    # 1. 依次拉取五家公司数据（全部在内存中，任一失败都不入库）
    for config in COMPANY_TOKEN_CONFIGS:
        company = config['company']
        token_config_key = config['token_config_key']
        records, stats = _sync_company(company, token_config_key, sync_start)
        all_records.extend(records)
        for key in total_stats:
            total_stats[key] += stats[key]

    # 2. 完整性对账：明细总数 = 合法数 + 丢弃数
    if total_stats['item_count'] != total_stats['valid_count'] + total_stats['invalid_count']:
        logger.warning(
            f"[在途同步] 数量对账异常: 明细{total_stats['item_count']} != "
            f"合法{total_stats['valid_count']} + 丢弃{total_stats['invalid_count']}"
        )

    # 3. 事务内按公司重建快照
    with orm_session() as session:
        deleted_count = 0
        inserted_count = 0
        for config in COMPANY_TOKEN_CONFIGS:
            company = config['company']
            company_records = [r for r in all_records if r['company'] == company]
            d, i = replace_snapshot_for_company(session, company, company_records)
            deleted_count += d
            inserted_count += i

    sync_end = datetime.now()
    logger.info(
        f"[在途同步] 完成: 产品{total_stats['product_count']} 明细{total_stats['item_count']} "
        f"入库{inserted_count} 丢弃{total_stats['invalid_count']} 清理旧数据{deleted_count} "
        f"耗时{(sync_end - sync_start).total_seconds():.1f}s"
    )

    return total_stats
