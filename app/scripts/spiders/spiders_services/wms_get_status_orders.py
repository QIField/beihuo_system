# -*- coding:utf-8 -*-
# @Time    : 2026/4/10 08:39
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_get_status_orders.py
# @Software: PyCharm

from app.models.raw_sql_models.wms_status_orders_raw import WmsStatusOrders
from app.services.dashboard_crm_wms_services.load_config import get_config
from app.utils.spider_utli import simple_spider


def get_status_orders_complete(url0, headers, page_num):
    """
    获取状态订单数据并直接保存到数据库
    """
    total_inserted = 0
    
    for i in range(1, page_num + 1):
        print("正在爬取第", i, "页")
        url = url0 + "?type=3" + "&status=2" + "&page=" + i.__str__()
        print("正在爬取的接口", url)
        json_data = simple_spider(url, headers)
        data = json_data.get("data", {}).get("data", {}).get("data")
        if data:
            inserted = WmsStatusOrders.batch_upsert(data)
            total_inserted += inserted
            print(f"第 {i} 页已保存 {len(data)} 条数据")
    
    print(f"总共保存 {total_inserted} 条数据到数据库")
    return total_inserted


def wms_get_status_orders_spider(url0, headers, page_num):
    """
    获取WMS状态订单数据并保存到数据库（完整版本）
    """
    all_data = []
    type_id = 3
    
    for status in range(0, 3):
        flag = 1
        while True:
            if flag == 1:
                page = ""
            else:
                page = "&page=" + flag.__str__()
            
            url = url0 + "?type=" + type_id.__str__() + "&status=" + status.__str__() + page
            print("正在爬取的接口", url)
            json_data = simple_spider(url, headers)
            data = json_data.get("data", {}).get("data", {}).get("data")
            
            if data:
                all_data.extend(data)
            
            flag += 1
            if len(json_data) < 20:
                break
    
    for i in range(1, page_num + 1):
        url = url0 + "?type=3" + "&status=2" + "&page=" + i.__str__()
        print("正在爬取的接口", url)
        json_data = simple_spider(url, headers)
        data = json_data.get("data", {}).get("data", {}).get("data")
        if data:
            all_data.extend(data)
    
    if all_data:
        total_affected = WmsStatusOrders.batch_upsert(all_data)
        print(f"总共保存 {total_affected} 条数据到数据库")
        return total_affected
    
    return 0


def get_status_orders_complete_by_page(page_num):
    print("-"*50)
    print("get_status_orders_complete")
    url_wms = "https://wms.gzbbr.com/api/Wms.Orders/get_status_orders"
    config = get_config()
    wms_token=config["wms_token"]
    headers_wms = {
        # 模拟浏览器请求头（必须加，否则很多网站会拦截）
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
        "authorization":wms_token
    }
    get_status_orders_complete(url_wms, headers_wms, page_num)
    print("-" * 50)


# if __name__ == '__main__':
#     get_status_orders_complete_by_page(10)