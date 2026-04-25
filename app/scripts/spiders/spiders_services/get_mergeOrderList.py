# -*- coding:utf-8 -*-
# @Time    : 2026/4/9 14:48
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : get_mergeOrderList.py
# @Software: PyCharm
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.scripts.spiders.pipeline_clean.get_mergeOrderList_clean import remove_duplicate
from app.models.orm_models.merge_order_list import MergeOrderList
from app.utils.orm.session import orm_session
from config.config_list_manager.config_cache import get_config_value


def get_mergeOrderList_complete_by_level_id(token, page_num=None,
                                            level_id=None,
                                            orderdate_start=None,
                                            orderdate_end=None,
                                            status=None,
                                            order_type_id=None,
                                            is_wms=None,
                                            order_source_type=None):
    """
    分页爬取订单列表
    :param token: 认证token
    :param level_id: 层级ID
    :param page_num: 要爬取的页数，None=自动爬取全部，数字=指定爬取N页
    :return: 所有爬取到的订单列表
    """
    spider = CrmGzbbrSpider(token)
    limit = 200
    data_total_count = 0  # 存储所有订单数据总计
    current_page = 1

    # # 初始化去重管道
    # deduplication_pipeline = DeduplicationPipeline(
    #     pool_name=f"mergeOrderList_{level_id}",
    #     unique_key_fields=["d_sap_no"]
    # )

    while True:
        # 请求接口
        json_data = spider.get_mergeOrderList(
            page=current_page,
            limit=limit,
            level_id=level_id,
            orderdate_start=orderdate_start,
            orderdate_end=orderdate_end,
            status=status,
            order_type_id=order_type_id,
            is_wms=is_wms,
            order_source_type=order_source_type

        ).json()



        # 无数据直接退出
        if not json_data.get("data", {}):
            print(json_data)
            print(f"第{current_page}页无数据，爬取结束")
            break

        # 获取当前页订单
        order_list = json_data.get("data", {}).get("list", {}).get("data", [])

        # 进行数据清洗和字段过滤
        print(f"第{current_page}页原始订单数量: {len(order_list)}")
        filtered_data_list = remove_duplicate(order_list,level_id)
        print(f"第{current_page}页清洗后订单数量: {len(filtered_data_list)}")
        
        # 进行入库操作（插入或更新）
        if filtered_data_list:
            print(f"开始入库第{current_page}页数据...")
            with orm_session() as session:
                count = MergeOrderList.bulk_upsert(session, filtered_data_list)
                print(f"第{current_page}页成功入库 {count} 条数据（插入或更新）")

        # 累加数据
        data_total_count += len(filtered_data_list)
        print(f"第{current_page}页订单数量: {len(order_list)}, 累计: {data_total_count}")

        # ===================== 核心退出逻辑 =====================
        # 1. 指定了页数：爬够页数就退出
        if page_num is not None and current_page >= page_num:
            print(f"已爬取指定的{page_num}页，爬取结束")
            break

        # 2. 爬取全部模式：当前页数量不足limit，说明是最后一页
        if len(order_list) < limit and not json_data.get("data", {}):
            print(json_data)
            print("当前页数量不足限制，已到最后一页，爬取结束")

        # 3. 继续下一页
        current_page += 1

    # return total_item_count


def get_mergeOrderList_service():
    print("="*100)
    print("get_mergeOrderList_service执行开始")

    token = get_config_value("customer_quota_manager").get("WMS_TOKEN")

    level_id_list = [
                     22,  #开思
                     27,  #维修厂
                     25, #同行
                     20, #车主
                     30, #线上-途虎养车（汽配龙）
                     109,  # 维修厂大客户
                     # 105,
                     # 28,
                     # 101,
                     # 26,
                     # 102,
                     # 103,
                     # 104,
                     # 106,
                     # 107

                     ]
    for level_id in level_id_list:
        print("="*100)
        print(f"正在爬取level_id={level_id}")
        get_mergeOrderList_complete_by_level_id(token,level_id=level_id)
        print(f"level_id={level_id} 爬取结束")
        print("=" * 100)
    print("get_mergeOrderList_service执行结束")
    print("=" * 100)
