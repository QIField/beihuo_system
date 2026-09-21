# -*- coding:utf-8 -*-
"""
OE搜索日志爬取入库服务

核心流程：
  1. 按日期范围分批调用 CRM /api/Product.Product/oeSearchLog 接口爬取数据
  2. 调用 clean_oe_search_log 清洗数据
  3. 调用 oe_search_log_dao.batch_upsert 写入 oe_search_log 表

日志系统：统一使用 app/utils/logger_config.py 的 get_task_logger('niche')
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Iterator

from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.scripts.spiders.pipeline_clean.oe_search_log_clean import clean_oe_search_log
from app.dao.niche_dao.oe_search_log_dao import batch_upsert, clear_by_date_range
from app.utils.logger_config import get_task_logger

logger = get_task_logger('niche')


# ============================================================================
# 工具函数
# ============================================================================

def time_to_ms(time_str: str):
    """
    日期字符串转换为毫秒级时间戳

    :param time_str: 日期字符串，格式 'YYYY-MM-DD'
    :return: (start_timestamp_ms, end_timestamp_ms)
    """
    start_time = int(time.mktime(time.strptime(time_str, '%Y-%m-%d')) * 1000)
    end_time = start_time + 86399000
    return start_time, end_time


# ============================================================================
# 爬虫函数
# ============================================================================

def crawl_oe_search_log_by_page(
    start_str: str,
    end_str: str,
    spider: CrmGzbbrSpider,
    logger,
) -> Iterator[List[Dict]]:
    """
    分页爬取 CRM OE 搜索日志，每页请求直接 yield 一次

    :param start_str: 开始日期字符串，格式 'YYYY-MM-DD'
    :param end_str: 结束日期字符串，格式 'YYYY-MM-DD'
    :param spider: 爬虫实例
    :param logger: 日志器
    :return: 每页 list[dict] 原始数据
    """
    search_time_start, _ = time_to_ms(start_str)
    _, search_time_end = time_to_ms(end_str)

    str_date_flag = f" 时间范围: {start_str} 至 {end_str}  "

    current_page = 1
    total_count = 0

    while True:
        response = spider.get_oe_search_log(
            page=current_page,
            search_time_start=search_time_start,
            search_time_end=search_time_end,
        )

        if response is None:
            logger.error(f"{str_date_flag} 第 {current_page} 页请求失败（网络异常），爬取终止")
            break

        if response.status_code != 200:
            logger.error(f"{str_date_flag} 第 {current_page} 页请求失败，状态码: {response.status_code}，响应: {response.text[:200]}")
            break

        try:
            json_data = response.json()
        except ValueError as e:
            logger.error(f"{str_date_flag} 第 {current_page} 页JSON解析失败: {str(e)}，响应内容: {response.text[:200]}")
            break

        if not isinstance(json_data, dict):
            logger.error(f"{str_date_flag} 第 {current_page} 页返回数据格式异常，不是字典类型")
            break

        page_data = json_data.get("data", {}).get("data", [])

        if not isinstance(page_data, list):
            logger.error(f"{str_date_flag} 第 {current_page} 页data.data格式异常，不是列表类型")
            break

        if not page_data:
            logger.info(f"{str_date_flag} 第 {current_page} 页无数据，爬取结束")
            break

        total_count += len(page_data)
        yield page_data

        last_page = json_data.get("data", {}).get("last_page", 0)
        if current_page >= last_page:
            logger.info(f"{str_date_flag} 第 {current_page}/{last_page} 页，已到达最后一页，爬取结束")
            break

        current_page += 1

    logger.info(f"时间范围: {start_str}~{end_str} 共爬取 {total_count} 条数据")


# ============================================================================
# 整合入口：爬取 + 清洗 + 入库
# ============================================================================

def crawl_and_store_oe_search_log(
    store: str = 'fs',
    start_date: str = None,  # pyright: ignore[reportArgumentType]
    end_date: str = None,  # pyright: ignore[reportArgumentType]
    batch_days: int = 1,
    batch_size: int = 2000,
    clear_before_write: bool = False,
) -> int:
    """
    OE 搜索日志爬取+清洗+入库一体化入口

    执行流程：
    1. 按日期范围分批爬取 CRM OE 搜索日志数据
    2. 调用 clean_oe_search_log 清洗数据
    3. 调用 batch_upsert 写入 oe_search_log 表

    :param store: 门店标识，默认 "fs"
    :param start_date: 开始日期，格式 'YYYY-MM-DD'，默认昨天
    :param end_date: 结束日期，格式 'YYYY-MM-DD'，默认昨天
    :param batch_days: 每个批次的天数，默认 1 天
    :param batch_size: 每次写入数据库的最大条数，默认 2000
    :param clear_before_write: 写入前是否清空日期范围内的旧数据，默认 False
    :return: 成功入库的总记录数
    """
    spider = CrmGzbbrSpider(timeout=60, logger=logger)

    if start_date is None:
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    batch_id = str(int(time.time()))

    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    total_stored = 0
    current_start = start_dt

    logger.info(f"========== OE搜索日志 | 批次ID: {batch_id} | 时间: {start_date} ~ {end_date} | 门店: {store} | 每批天数: {batch_days} ==========")

    if clear_before_write:
        deleted = clear_by_date_range(start_date, end_date)
        logger.info(f"[预处理] 清空 {start_date} ~ {end_date} 旧数据 {deleted} 条")

    while current_start <= end_dt:  # pyright: ignore[reportOperatorIssue]
        try:
            current_end = current_start + timedelta(days=batch_days - 1)
            if current_end > end_dt:  # pyright: ignore[reportOperatorIssue]
                current_end = end_dt

            start_str = current_start.strftime('%Y-%m-%d')  # pyright: ignore[reportAttributeAccessIssue]
            end_str = current_end.strftime('%Y-%m-%d')  # pyright: ignore[reportAttributeAccessIssue]

            logger.info(f"批次：[{batch_id}] 时间：{start_str} 至 {end_str} 正在爬取")

            # 第一步：爬取原始数据，每页请求直接清洗入库
            chunk_index = 0
            date_has_data = False
            for batch_data in crawl_oe_search_log_by_page(
                start_str=start_str,
                end_str=end_str,
                spider=spider,
                logger=logger,
            ):
                chunk_index += 1
                date_has_data = True

                # 第二步：清洗数据
                clean_data = clean_oe_search_log(batch_data, store=store)

                if not clean_data:
                    logger.warning(f"批次：[{batch_id}] 时间：{start_str} ~ {end_str} 第 {chunk_index} 批 清洗后无数据，跳过")
                    continue

                # 第三步：入库（业务层控制分批）
                sub_index = 0
                for i in range(0, len(clean_data), batch_size):
                    sub_index += 1
                    chunk = clean_data[i:i + batch_size]
                    affected = batch_upsert(chunk)
                    total_stored += affected

                    logger.info(f"批次：[{batch_id}] 时间：{start_str} ~ {end_str} 第 {chunk_index} 批-{sub_index} 更新或者插入 {affected} 条数据")

            if not date_has_data:
                logger.info(f"批次：[{batch_id}] 时间：{start_str} ~ {end_str} 无数据，跳过")

            current_start = current_end + timedelta(days=1)

        except Exception:
            logger.exception(f"批次：[{batch_id}] 时间：{start_str} 至 {end_str} 处理失败")
            current_start = current_end + timedelta(days=1)
            continue

    logger.info(f"全部批次处理完成，累计更新或插入 {total_stored} 条数据 (批次ID: {batch_id})")

    spider.close()
    return total_stored


# ============================================================================
# 主入口
# ============================================================================

# if __name__ == "__main__":
#     crawl_and_store_oe_search_log(start_date="2026-07-01", end_date="2026-09-21")

# if __name__ == "__main__":
#     spider = CrmGzbbrSpider(timeout=60, logger=logger)
#     response = spider.get_oe_search_log(
#             page=19,
#             search_time_start='1786809600000',
#             search_time_end='1786895999000',
#         )

#     data = response.json()['data']['data']
#     print(len(data))
#     print(data)
