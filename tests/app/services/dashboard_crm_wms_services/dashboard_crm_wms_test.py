# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 16:26
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : dashboard_crm_wms_test.py
# @Software: PyCharm
import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.services.dashboard_crm_wms_services.dashboard_crm_wms import wms_get_status_orders_spider, get_config, crawl_data_crm_wms
import pandas as pd

def wms_get_status_orders_spider_test():
    
    config = get_config()

    url_wms = "https://wms.gzbbr.com/api/Wms.Orders/get_status_orders"
    headers_wms = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
        "authorization": config["wms_token"]
    }
    
    print("=" * 50)
    print("开始测试 wms_get_status_orders_spider 函数")
    print("=" * 50)
    print(f"请求URL: {url_wms}")
    print(f"请求头: {headers_wms}")
    print("=" * 50)
    
    df = wms_get_status_orders_spider(url_wms, headers_wms)
    
    print("=" * 50)
    print("函数返回结果:")
    print("=" * 50)
    print(f"数据类型: {type(df)}")
    print(f"数据行数: {len(df)}")
    print(f"列名: {df.columns.tolist()}")
    print("=" * 50)
    print("前5条数据:")
    print(df.head())
    print("=" * 50)
    print("测试完成")
    print("=" * 50)


def crawl_data_crm_wms_test():
    print("开始测试 crawl_data_crm_wms 函数")
    print("=" * 50)
    
    start_date = "1775491200000"
    end_date = "1775577599000"
    
    print(f"开始时间: {start_date}")
    print(f"结束时间: {end_date}")
    print("=" * 50)
    
    result = crawl_data_crm_wms(start_date, end_date)
    
    print("=" * 50)
    print("函数返回结果:")
    print("=" * 50)
    print(f"数据类型: {type(result)}")
    print(f"数据条数: {len(result)}")
    print("=" * 50)
    if len(result) > 0:
        print("前3条数据:")
        import json
        print(json.dumps(result[:3], ensure_ascii=False, indent=4))
    print("=" * 50)
    print("测试完成")
    print("=" * 50)

    # # # 生成带时间戳的文件名
    print("************生成excel")
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    filename = f'订单合并_{timestamp}.xlsx'
    # 将result转换为DataFrame（如果是字典列表）
    if isinstance(result, list) and len(result) > 0:
        df_result = pd.DataFrame(result)
    elif isinstance(result, pd.DataFrame):
        df_result = result
    else:
        df_result = pd.DataFrame(result)
    df_result.to_excel(
        filename,
        index=False,
        sheet_name='合并订单数据',
        engine='openpyxl',
    )
    print(f"✅ 导出成功！\n文件: {filename}\n记录数: {len(df_result)}")


if __name__ == "__main__":
    # wms_get_status_orders_spider_test()
    print()
    crawl_data_crm_wms_test()
