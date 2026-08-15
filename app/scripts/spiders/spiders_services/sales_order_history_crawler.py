# -*- coding:utf-8 -*-
# @Time    : 2026/08/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : sales_order_history_crawler.py
# @Software: trae-cn

"""
销售订单历史数据爬虫服务 - 新流程（爬取 -> 清洗 -> 直接入库 sales_order_history）

核心流程：
  1. 按日期范围分批爬取CRM销售订单历史数据
  2. 调用 clean_sales_order_history 清洗数据（pipeline_clean/crm_gzbbr_clean.py）
  3. 调用 batch_upsert_sales_order_history 直接入库 sales_order_history 表

日志系统：统一使用 app/utils/logger_config.py 的 get_task_logger('stock_safe')
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict

from sqlalchemy.dialects.mysql import insert

from app.utils.orm.session import orm_session
from app.models.orm_models.crm.sales_order_history import SalesOrderHistory
from app.models.orm_models.partner_list import PartnerList
from app.models.orm_models.customer_quota_model import CustomerQuota
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.scripts.spiders.pipeline_clean.crm_gzbbr_clean import clean_sales_order_history
from app.scripts.spiders.spiders_services.log import get_stock_safe_logger

logger = get_stock_safe_logger()


# ============================================================================
# 工具函数
# ============================================================================

def time_to_ms(time_str: str):
    """
    时间字符串转换为毫秒级时间戳

    :param time_str: 日期字符串，格式 'YYYY-MM-DD'
    :return: (start_timestamp_ms, end_timestamp_ms)
    """
    start_time = int(time.mktime(time.strptime(time_str, '%Y-%m-%d')) * 1000)
    end_time = start_time + 86399000
    return start_time, end_time


# ============================================================================
# 爬虫函数
# ============================================================================

def get_sales_order_history_by_page_service(start_str, end_str, spider, logger):
    """
    分页爬取CRM销售订单历史（while 循环版本）

    :param start_str: 开始日期字符串，格式 'YYYY-MM-DD'
    :param end_str: 结束日期字符串，格式 'YYYY-MM-DD'
    :param spider: 爬虫实例
    :param logger: 日志器
    :return: list[dict] 原始数据列表
    """
    limit = 5000
    create_date_start, _ = time_to_ms(start_str)
    _, create_date_end = time_to_ms(end_str)

    str_date_flag = f" 时间范围: {start_str} 至 {end_str}  "

    all_data = []
    current_page = 1
    while True:
        response = spider.get_sales_order_history(
            page=current_page,
            limit=limit,
            create_date_start=create_date_start,
            create_date_end=create_date_end,
        )

        if response is None:
            logger.error(f"{str_date_flag} 第 {current_page} 页请求失败（网络异常），爬取终止")
            current_page += 1
            continue

        if response.status_code != 200:
            logger.error(f"{str_date_flag} 第 {current_page} 页请求失败，状态码: {response.status_code}，响应: {response.text[:200]}")
            current_page += 1
            continue

        try:
            json_data = response.json()
        except ValueError as e:
            logger.error(f"{str_date_flag} 第 {current_page} 页JSON解析失败: {str(e)}，响应内容: {response.text[:200]}")
            current_page += 1
            continue

        if not isinstance(json_data, dict):
            logger.error(f"{str_date_flag} 第 {current_page} 页返回数据格式异常，不是字典类型")
            current_page += 1
            continue

        page_data = json_data.get("data", {}).get("data", [])

        if not isinstance(page_data, list):
            logger.error(f"{str_date_flag} 第 {current_page} 页data.data格式异常，不是列表类型")
            current_page += 1
            continue

        if not page_data:
            logger.info(f"{str_date_flag} 第 {current_page} 页无数据，爬取结束")
            break

        all_data.extend(page_data)

        if len(page_data) < limit:
            logger.info(f"{str_date_flag} 第 {current_page} 页数量不足 {limit} 条，已到最后一页，爬取结束")
            break

        current_page += 1

    if all_data:
        logger.info("时间范围: %s~%s 共爬取 %d 条数据", start_str, end_str, len(all_data))
    return all_data


# ============================================================================
# 入库函数
# ============================================================================

def batch_upsert_sales_order_history(clean_data_list: List[Dict], logger=None) -> int:
    """
    批量 upsert 销售订单历史数据到 sales_order_history 表

    使用 on_duplicate_key_update 实现幂等入库，
    以 orders_items_id 为唯一键，冲突时更新其他字段。

    :param clean_data_list: 清洗后的数据字典列表
    :param logger: 日志器，可选
    :return: 受影响的行数（含插入和更新）
    """
    if not clean_data_list:
        if logger:
            logger.warning("清洗后无数据，跳过入库")
        return 0

    with orm_session() as session:
        insert_stmt = insert(SalesOrderHistory.__table__).values(clean_data_list)

        skip_cols = {'orders_items_id', 'created_at', 'updated_at'}
        all_cols = SalesOrderHistory.__table__.columns.keys()
        update_dict = {
            k: insert_stmt.inserted[k]
            for k in all_cols
            if k not in skip_cols
        }

        update_stmt = insert_stmt.on_duplicate_key_update(**update_dict)
        result = session.execute(update_stmt)
        affected = result.rowcount  # pyright: ignore[reportAttributeAccessIssue]

        if logger:
            logger.info(f"sales_order_history 入库完成，共 {affected} 条（含更新）")

        return affected


# ============================================================================
# 新整合入口：爬取+清洗+入库一体化入口
# ============================================================================

def crawl_and_store_sales_order_history(
    store: str = "fs",
    start_date: str = None,  # pyright: ignore[reportArgumentType]
    batch_days: int = 4
) -> int:
    """
    销售订单历史数据爬取+清洗+入库一体化入口

    执行流程：
    1. 按日期范围分批爬取CRM销售订单历史数据
    2. 调用 clean_sales_order_history 清洗数据
    3. 调用 batch_upsert_sales_order_history 直接入库 sales_order_history 表

    :param store: 门店标识，默认 "fs"
    :param start_date: 开始日期，格式 'YYYY-MM-DD'，默认当天
    :param batch_id: 批次ID，默认自动生成
    :param batch_days: 每个批次的天数，默认 4 天
    :return: 成功入库的总记录数
    """
    spider = CrmGzbbrSpider()

    # 默认参数处理
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    
    batch_id = str(int(time.time()))

    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    total_stored = 0
    current_start = start_dt
  

    logger.info("========== 批次ID: %s | 时间: %s ~ %s | 门店: %s | 每批天数: %d ==========",
                 batch_id, start_date, today.strftime('%Y-%m-%d'), store, batch_days)

    while current_start <= today:  # pyright: ignore[reportOperatorIssue]
        try:
            current_end = current_start + timedelta(days=batch_days - 1)
            if current_end > today:  # pyright: ignore[reportOperatorIssue]
                current_end = today

            start_str = current_start.strftime('%Y-%m-%d')  # pyright: ignore[reportAttributeAccessIssue]
            end_str = current_end.strftime('%Y-%m-%d')  # pyright: ignore[reportAttributeAccessIssue]
        
            logger.info("批次：[%s] 时间：%s 至 %s 正在爬取", batch_id, start_str, end_str)

            # 第一步：爬取原始数据
            batch_data = get_sales_order_history_by_page_service(
                start_str=start_str,
                end_str=end_str,
                spider=spider,
                logger=logger,
            )

            if not batch_data:
                logger.info(f"批次：[{batch_id}] 时间：{start_str} ~ {end_str} 无数据，跳过")
                current_start = current_end + timedelta(days=1)
                continue

            # 第二步：清洗数据
            clean_data = clean_sales_order_history(batch_data, store=store)

            if not clean_data:
                current_start = current_end + timedelta(days=1)
                continue

            # 第三步：直接入库 sales_order_history 表
            affected = batch_upsert_sales_order_history(clean_data, logger=logger)
            total_stored += affected

            current_start = current_end + timedelta(days=1)

        except Exception as e:
            logger.error(f"批次：[{batch_id}] 时间：{start_str} 至 {end_str} 处理失败: {str(e)}")
            # logger.exception("异常详情")
            current_start = current_end + timedelta(days=1)
            continue

    logger.info("全部批次处理完成，累计入库 %d 条 (批次ID: %s)", total_stored, batch_id)

    return total_stored




# ============================================================================
# 主入口
# ============================================================================

# if __name__ == "__main__":
#     crawl_and_store_sales_order_history(start_date="2024-01-01")
