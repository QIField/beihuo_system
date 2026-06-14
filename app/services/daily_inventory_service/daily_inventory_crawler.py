# -*- coding:utf-8 -*-
# @Time    : 2026/06/06 13:07
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : daily_inventory_crawler.py
# @Software: trae-cn
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.scripts.spiders.pipeline_clean.crm_gzbbr_clean import clean_purchase_order_list, clean_purchase_order_items
from typing import List, Dict, Optional

from app.utils.common_util_module.time_conversion_util import get_day_timestamp
from app.utils.orm.session import orm_session
from app.models.orm_models.crm_purchase_order_list import CrmPurchaseOrderList
from app.models.orm_models.crm_purchase_order_details import CrmPurchaseOrderDetails
from sqlalchemy.dialects.mysql import insert


def crawl_purchase_orders(page_num: Optional[int] = None,
                          orderdate_start: Optional[str] = None,
                          orderdate_end: Optional[str] = None,
                          cookies_key: str = 'fs') -> int:
    """
    分页爬取采购订单列表

    :param page_num: 要爬取的页数，None=自动爬取全部，数字=指定爬取N页
    :param orderdate_start: 创建时间开始时间戳
    :param orderdate_end: 创建时间结束时间戳
    :param cookies_key: cookies的key，可选值：fs, zs, zh, hf, by，默认为fs
    :return: 所有爬取到的采购订单列表
    """
    spider = CrmGzbbrSpider(cookies_key=cookies_key)
    limit = 2000
    data_total_count = 0
    current_page = 1
    

    while True:
        # 请求接口
        response = spider.get_purchaseOrder_mergeOrderList(
            page=current_page,
            limit=limit,
            orderdate=[orderdate_start, orderdate_end]
        )

        if not response:
            print(f"第{current_page}页请求失败，爬取结束")
            break

        json_data = response.json()

        # 无数据直接退出
        if not json_data.get("data", {}):
            print(json_data)
            print(f"第{current_page}页无数据，爬取结束")
            break

        # 获取当前页订单
        order_list = json_data.get("data", {}).get("list", {}).get("data", [])
        if not order_list:
            
            order_list = json_data.get("data", {}).get("list", [])

        # 进入清洗通道前检查：数据必须是非空列表
        if not order_list or not isinstance(order_list, list) or len(order_list) == 0:
            
            raise ValueError("暂无更新数据")

        # 进行数据清洗和字段过滤
        # print(f"第{current_page}页原始订单数量: {len(order_list)}")
        filtered_data_list = clean_purchase_order_list(order_list,cookies_key)
        # print(f"第{current_page}页清洗后订单数量: {len(filtered_data_list)}")

        ##入库
        with orm_session() as session:
            if filtered_data_list:
                stmt = insert(CrmPurchaseOrderList).values(filtered_data_list)
                update_dict = {c.name: c for c in stmt.inserted if c.name not in ['purchase_order_id','updated_at', 'created_at']}
                stmt = stmt.on_duplicate_key_update(**update_dict)
                session.execute(stmt)
                  


        # 累加数据
        data_total_count += len(filtered_data_list)
        # print(f"第{current_page}页订单数量: {len(order_list)}, 累计: {data_total_count}")

        # ===================== 核心退出逻辑 =====================
        # 1. 指定了页数：爬够页数就退出
        if page_num is not None and current_page >= page_num:
            print(f"已爬取指定的{page_num}页，爬取结束")
            break

        # 2. 爬取全部模式：当前页数量不足limit，说明是最后一页
        if len(order_list) < limit:
            print("当前页数量不足限制，已到最后一页，爬取结束")
            break

        # 3. 继续下一页
        current_page += 1

    return data_total_count

def crawl_purchase_order_details(purchase_order_ids: List[int], cookies_key: str = 'fs') -> int:
    """
    爬取指定采购订单的明细数据

    :param purchase_order_ids: 采购订单ID列表
    :param cookies_key: cookies的key，可选值：fs, zs, zh, hf, by，默认为fs
    :return: 爬取到的订单明细总数
    """
    spider = CrmGzbbrSpider(cookies_key=cookies_key)
    data_total_count = 0
    all_filtered_data = []  # 收集所有清洗后的数据
    batch_size = 2000  # 每批2000条数据

    for purchase_order_id in purchase_order_ids:
        try:
            # 请求订单明细接口
            response = spider.get_purchaseOrder_orders_view(
                purchase_order_id=purchase_order_id,
                page=1,
                limit=2000
            )

            if not response:
                print(f"采购订单 {purchase_order_id} 请求失败")
                continue

            json_data = response.json()

            # 无数据跳过
            if not json_data.get("data", {}):
                print(f"采购订单 {purchase_order_id} 无明细数据")
                continue

            # 获取订单明细
            item_list = json_data.get("data", {}).get("Quotelineitem", {}).get("data", [])

            if not item_list:
                print(f"采购订单 {purchase_order_id} 明细列表为空")
                continue

            # 进行数据清洗和字段过滤
            filtered_data_list = clean_purchase_order_items(json_data, cookies_key)

            # 收集数据
            if filtered_data_list:
                all_filtered_data.extend(filtered_data_list)
                data_total_count += len(filtered_data_list)
                print(f"采购订单 {purchase_order_id} 爬取到 {len(filtered_data_list)} 条明细")

            # 检查是否达到批次大小，达到则入库
            if len(all_filtered_data) >= batch_size:
                _batch_insert_purchase_order_details(all_filtered_data)
                all_filtered_data = []  # 清空已入库的数据

        except Exception as e:
            print(f"爬取采购订单 {purchase_order_id} 时出错: {str(e)}")
            continue

    # 最后处理剩余的数据
    if all_filtered_data:
        _batch_insert_purchase_order_details(all_filtered_data)

    return data_total_count

def _batch_insert_purchase_order_details(data_list: List[Dict]) -> None:
    """
    批量入库采购订单明细数据

    :param data_list: 要入库的数据列表
    :param batch_size: 每批的数据量（未使用，保留参数兼容）
    """
    with orm_session() as session:
        if data_list:
            
            stmt = insert(CrmPurchaseOrderDetails).values(data_list)
            update_dict = {c.name: c for c in stmt.inserted if c.name not in ['purchase_order_line_id', 'updated_at', 'created_at','operator']}
            stmt = stmt.on_duplicate_key_update(**update_dict)
            session.execute(stmt)
            session.commit()
            print(f"成功入库 {len(data_list)} 条采购订单明细")
           
def get_purchase_order_ids_from_db(cookies_key: str = 'fs', 
                                    create_date_start: Optional[str] = None,
                                    create_date_end: Optional[str] = None) -> List[int]:
    """
    从数据库获取采购订单ID列表

    :param cookies_key: cookies的key，用于筛选门店
    :param create_date_start: 创建时间范围的起始值（可选），格式如 "2026-06-06"
    :param create_date_end: 创建时间范围的结束值（可选），格式如 "2026-06-06"
    :return: 采购订单ID列表
    """
    with orm_session() as session:
        # 查询采购订单ID，根据store筛选
        query = session.query(CrmPurchaseOrderList.purchase_order_id)
        if cookies_key:
            query = query.filter(CrmPurchaseOrderList.store == cookies_key)
        # 添加create_date范围筛选 - 拼接时间部分
        if create_date_start:
            # 如果只有日期，拼接 " 00:00:00"
            start_time = f"{create_date_start} 00:00:00"
            query = query.filter(CrmPurchaseOrderList.create_date >= start_time)
        if create_date_end:
            # 如果只有日期，拼接 " 23:59:59"
            end_time = f"{create_date_end} 23:59:59"
            query = query.filter(CrmPurchaseOrderList.create_date <= end_time)
        results = query.all()
        return [result[0] for result in results]

def daily_inventory_crawler_service(cookies_key: str = 'fs',
                                      create_date_start: Optional[str] = None,
                                      create_date_end: Optional[str] = None) -> None:
    """
    每日库存爬虫服务入口

    :param cookies_key: cookies的key，可选值：fs, zs, zh, hf, by，默认为fs
    :param create_date_start: 创建时间范围的起始值（可选）
    :param create_date_end: 创建时间范围的结束值（可选）
    """


    print("=" * 100)

    orderdate_start,_=get_day_timestamp(create_date_start)  # pyright: ignore[reportArgumentType]
    _,orderdate_end=get_day_timestamp(create_date_end)  # pyright: ignore[reportArgumentType]


    # 爬取采购订单
    print("开始爬取采购订单...")
    purchase_count = crawl_purchase_orders(
        orderdate_start=orderdate_start*1000,   # pyright: ignore[reportArgumentType]
        orderdate_end=orderdate_end*1000,  # pyright: ignore[reportArgumentType]
        page_num=10, cookies_key=cookies_key)
    print(f"共爬取到 {purchase_count} 条采购订单数据")

    # 爬取采购订单明细
    print("\n开始爬取采购订单明细...")
    purchase_order_ids = get_purchase_order_ids_from_db(cookies_key, create_date_start, create_date_end)
    details_count = crawl_purchase_order_details(purchase_order_ids, cookies_key)
    print(f"共爬取到 {details_count} 条采购订单明细数据")

   
    print("=" * 100)


if __name__ == "__main__":
    daily_inventory_crawler_service(cookies_key='fs', create_date_start="2026-06-06", create_date_end="2026-06-06")
