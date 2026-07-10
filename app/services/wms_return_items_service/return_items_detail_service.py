# -*- coding:utf-8 -*-
# @Time    : 2026/7/10
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : return_items_detail_service.py
# @Software: PyCharm
# @Desc    : WMS 采购入库单明细同步服务（按指定字段抽取）

import logging
from typing import Any, Dict, List, Optional

from app.models.orm_models.wms.wms_return_items_detail import WmsReturnItemsDetail
from app.scripts.spiders.spider_entities.wms_gzbbr import WmsGzbbrSpider
from app.utils.orm.session import orm_session


# 每页固定条数，与 WMS 接口一致
PAGE_LIMIT = 20


def _safe_int(value: Any) -> Optional[int]:
    """安全转换为整数，失败返回 None"""
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _clean_number(value: Any) -> Optional[str]:
    """
    处理 number 字段：删除空格及空格后的内容

    例如："31106786959 LFD" -> "31106786959"
    """
    if value is None or value == '':
        return None

    text = str(value).strip()
    if not text:
        return None

    # 只保留第一个空格前面的内容
    if ' ' in text:
        text = text.split(' ', 1)[0]

    return text if text else None


def _extract_status_orders(response: Any) -> List[Dict[str, Any]]:
    """
    从 get_status_orders 响应中提取订单号、拣货单号、订单日期

    目标结构：data.data.data[*].orders_no / pono / orderdate
    """
    if response is None:
        return []

    try:
        json_data = response.json()
    except Exception:
        return []

    page_data = json_data.get("data", {}).get("data", {}).get("data", []) or []

    orders = []
    for item in page_data:
        orders_no = item.get("orders_no")
        if not orders_no:
            continue
        orders.append({
            "orders_no": orders_no,
            "pono": item.get("pono"),
            "orderdate": item.get("orderdate"),
        })

    return orders


def _extract_return_items_detail(response: Any, base_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从 get_return_items 响应中提取指定字段

    目标结构：data.data["IN-Q3JTUFVF"][*].brandname / frey_no / l_name_zh /
              number / poqty / qty / product_id
    """
    if response is None:
        return []

    try:
        json_data = response.json()
    except Exception:
        return []

    # data.data 是一个字典，key 为动态入库单号
    items_by_group = json_data.get("data", {}).get("data", {}) or {}
    if not isinstance(items_by_group, dict):
        return []

    detail_list = []
    for group_key, items in items_by_group.items():
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            raw_number = item.get("number")
            detail_list.append({
                "orders_no": base_info.get("orders_no"),
                "pono": base_info.get("pono"),
                "orderdate": base_info.get("orderdate"),
                "brandname": item.get("brandname"),
                "frey_no": item.get("frey_no"),
                "l_name_zh": item.get("l_name_zh"),
                "number": raw_number,
                "number_clean": _clean_number(raw_number),
                "poqty": _safe_int(item.get("poqty")),
                "qty": _safe_int(item.get("qty")),
                "product_id": item.get("product_id"),
            })

    return detail_list


def _clean_detail_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    清洗入库明细记录

    规则：
    1. 过滤 orders_no 为空的记录
    2. 把空字符串 / 空白 / None 统一处理为 None
    """
    if not records:
        return []

    clean_records = []
    for record in records:
        if not record.get("orders_no"):
            continue

        clean_record = {}
        for key, value in record.items():
            if value is None or value == '':
                clean_record[key] = None
            elif isinstance(value, str) and value.strip() == '':
                clean_record[key] = None
            else:
                clean_record[key] = value

        clean_records.append(clean_record)

    return clean_records


def _filter_new_orders(
    page_orders: List[Dict[str, Any]],
    existing_orders_nos: set,
    logger: logging.Logger,
) -> tuple:
    """
    从当前页订单中过滤出未存在于数据库的订单

    找到第一个已存在的订单位置，只保留该位置之前的订单。

    :param page_orders: 当前页订单列表
    :param existing_orders_nos: 已存在的 orders_no 集合
    :param logger: 日志器
    :return: (新订单列表, 是否发现已存在订单)
    """
    if not page_orders:
        return [], False

    # 找到第一个已存在订单的索引
    first_existing_index = None
    for idx, order in enumerate(page_orders):
        if order.get("orders_no") in existing_orders_nos:
            first_existing_index = idx
            break

    if first_existing_index is None:
        return page_orders, False

    new_orders = page_orders[:first_existing_index]
    found_existing_no = page_orders[first_existing_index].get("orders_no")
    logger.info(
        "发现已存在订单 orders_no=%s，停止爬取，当前页保留 %s 条新订单",
        found_existing_no,
        len(new_orders),
    )
    return new_orders, True


def sync_wms_return_items_detail(
    page_num: Optional[int] = None,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    同步 WMS 采购入库单明细（按指定字段抽取）

    流程：
    1. 调用 get_status_orders(type=5, status=2) 分页获取订单列表
    2. 提取 orders_no / pono / orderdate
    3. 对每个 orders_no 调用 get_return_items
    4. 按 data.data[dynamic_key][*] 结构提取指定字段
    5. 清洗后批量 upsert 到 wms_return_items_detail 表

    :param page_num: 指定爬取页数，None 表示自动爬到最后一页
    :param logger: 可选日志器
    :return: {"orders_count": 订单数, "items_count": 明细数, "saved_count": 保存数}
    """
    logger = logger or logging.getLogger("wms_return_items_detail")
    spider = WmsGzbbrSpider(logger=logger)

    try:
        all_orders = []
        current_page = 1

        # 1. 分页拉取 type=5, status=2 的订单列表
        # 规则：每页查询数据库，遇到已存在的订单立即停止
        should_stop = False

        while True:
            logger.info("正在爬取订单列表第 %s 页", current_page)
            resp = spider.get_status_orders(type=5, status=2, page=current_page)
            page_orders = _extract_status_orders(resp)

            if not page_orders:
                logger.info("第 %s 页无数据，订单列表爬取结束", current_page)
                break

            # 查询当前页订单中哪些已存在
            orders_no_list = [order.get("orders_no") for order in page_orders if order.get("orders_no")]
            with orm_session() as session:
                existing_orders_nos = WmsReturnItemsDetail.get_existing_orders_nos(session, orders_no_list)

            new_orders, has_existing = _filter_new_orders(page_orders, existing_orders_nos, logger)

            if new_orders:
                all_orders.extend(new_orders)
                logger.info(
                    "第 %s 页获取 %s 条新订单（原始 %s 条），累计 %s 条",
                    current_page,
                    len(new_orders),
                    len(page_orders),
                    len(all_orders),
                )

            if has_existing:
                should_stop = True
                break

            if page_num is not None and current_page >= page_num:
                logger.info("已爬取指定 %s 页，订单列表爬取结束", page_num)
                break

            if len(page_orders) < PAGE_LIMIT:
                logger.info("第 %s 页不足 %s 条，已到最后一页", current_page, PAGE_LIMIT)
                break

            current_page += 1

        if should_stop:
            logger.info("因遇到已存在订单，订单列表爬取提前结束")

        if not all_orders:
            logger.info("无新订单数据，跳过同步")
            return {"orders_count": 0, "items_count": 0, "saved_count": 0}

        # 2. 逐个订单获取 return_items 明细
        all_detail_records = []
        total_orders = len(all_orders)

        for idx, order in enumerate(all_orders, 1):
            orders_no = order["orders_no"]
            logger.info("[%s/%s] 正在获取 return_items: orders_no=%s", idx, total_orders, orders_no)

            resp = spider.get_return_items(orders_no=orders_no)
            detail_records = _extract_return_items_detail(resp, order)

            if not detail_records:
                logger.info("[%s/%s] orders_no=%s 无明细数据", idx, total_orders, orders_no)
                continue

            all_detail_records.extend(detail_records)
            logger.info("[%s/%s] orders_no=%s 获取 %s 条明细", idx, total_orders, orders_no, len(detail_records))

        if not all_detail_records:
            logger.info("无 return_items 明细数据，跳过入库")
            return {"orders_count": total_orders, "items_count": 0, "saved_count": 0}

        # 3. 清洗
        clean_records = _clean_detail_records(all_detail_records)
        if not clean_records:
            logger.info("清洗后无有效数据，跳过入库")
            return {"orders_count": total_orders, "items_count": len(all_detail_records), "saved_count": 0}

        # 4. 入库
        with orm_session() as session:
            saved_count = WmsReturnItemsDetail.bulk_upsert(session, clean_records)

        logger.info("同步完成：订单 %s 条，明细 %s 条，入库 %s 条", total_orders, len(all_detail_records), saved_count)
        return {
            "orders_count": total_orders,
            "items_count": len(all_detail_records),
            "saved_count": saved_count,
        }

    finally:
        spider.close()
