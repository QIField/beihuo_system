# -*- coding:utf-8 -*-
"""
WMS 库存操作推送服务 - 主入口

职责：
1. 初始化 spider 和日志器
2. 串行调用采购入库、采购移除两个子流程
3. 汇总执行结果
"""

import logging
from typing import Any, Dict, Optional

from app.scripts.spiders.spider_entities.wms_gzbbr import WmsGzbbrSpider
from app.utils.logger_config import get_task_logger

# 保持向后兼容，测试文件仍从本模块导入这些函数
from .common import _extract_orders, _fetch_orders_by_type
from .utils import _is_not_empty, _safe_decimal, _safe_int


DEFAULT_COMPANY = "fsbbr"


def run_wms_inventory_operation(
    company: str = DEFAULT_COMPANY,
    logger: Optional[logging.Logger] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    执行 WMS 库存操作自动推送

    流程：
    1. 采购入库流程（type=5, status=0/1）-> addPurchaseToInventory
    2. 采购移除流程（type=3, status=0/1）-> removePurchaseFromInventory

    :param company: 门店代码
    :param logger: 可选日志器
    :param dry_run: 为 True 时只打印不调用 POST 接口
    :return: 执行结果汇总
    """
    from .purchase_inventory_service import run_purchase_inventory_push
    from .remove_inventory_service import run_remove_purchase_inventory

    logger = logger or get_task_logger('wms_inventory_operation')
    logger.info("[库存操作] 开始执行，dry_run=%s", dry_run)

    spider = WmsGzbbrSpider(logger=logger)
    try:
        purchase_result = run_purchase_inventory_push(spider, logger, dry_run)
        remove_result = run_remove_purchase_inventory(spider, logger, dry_run)

        logger.info(
            "[库存操作] 完成，采购入库推送 %s/%s，采购移除推送 %s/%s",
            purchase_result["pushed"],
            purchase_result["total"],
            remove_result["pushed"],
            remove_result["total"],
        )

        return {
            "company": company,
            "dry_run": dry_run,
            "purchase": purchase_result,
            "remove": remove_result,
        }
    finally:
        spider.close()
