# -*- coding:utf-8 -*-
# @Time    : 2026/06/15 09:53
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : get_status_orders_tasks.py
# @Software: trae-cn


from app.scripts.spiders.spider_entities.wms_gzbbr import WmsGzbbrSpider
from app.scripts.spiders.pipeline_clean.wms_gzbbr_clear import get_status_orders_clean


def run_get_status_orders_task(page_num=None, status=2, store='fsbbr'):
    """
    分页爬取状态订单并清洗（while 循环版本）

    page_num 控制方式：
    - None = 自动爬取到最后一页
    - 数字 = 只爬取指定页数

    流程：
    1. while True 循环，current_page 从 1 开始累加
    2. 调用 get_status_orders 取当前页数据
    3. 无数据直接 break；数据少于 page_limit，也视为最后一页
    4. 指定了 page_num 时，爬够页数就退出
    5. 最后统一调用 get_status_orders_clean 清洗

    :param page_num: 爬取页数，None=自动全部，数字=指定页数，默认 None
    :param type: 订单类型，默认 3
    :param status: 订单状态，默认 2
    :param store: 门店标识，默认 'fsbbr'
    :param page_limit: 单页预期条数，用于判断是否最后一页，默认 20
    :return: list[dict] 清洗后的订单数据列表
    """
    spider = WmsGzbbrSpider()
    all_data = []
    current_page = 1
    type=3
    limit=20
    while True:
        print("正在爬取第", current_page, "页")
        json_data = spider.get_status_orders(type=type, status=status, page=current_page).json()  # pyright: ignore[reportOptionalMemberAccess]
        # print(json_data)
        page_data = json_data.get("data", {}).get("data", {}).get("data")
        
        # 无数据直接退出
        if not page_data:
            print(f"第 {current_page} 页无数据，爬取结束")
            break

        all_data.extend(page_data)
        print(f"第 {current_page} 页获取 {len(page_data)} 条，累计 {len(all_data)} 条")

        # 1. 指定了页数：爬够就退出
        if page_num is not None and current_page >= page_num:
            print(f"已爬取指定的 {page_num} 页，爬取结束")
            break

        # 2. 自动模式：当前页数量不足 page_limit，视为最后一页
        if len(page_data) < limit:
            print(f"第 {current_page} 页数量不足 {limit} 条，已到最后一页，爬取结束")
            break

        current_page += 1

    spider.close()
    print(f"原始数据共 {len(all_data)} 条")

    if not all_data:
        return []

    clean_data = get_status_orders_clean(all_data, store=store)
    print(f"清洗后数据共 {len(clean_data)} 条")

    return clean_data


if __name__ == '__main__':
    orders = run_get_status_orders_task(page_num=10, status=2, store='fsbbr')
    print(f"最终结果共 {len(orders)} 条清洗后订单")
    if orders:
        print("第一条示例：", orders[0])
