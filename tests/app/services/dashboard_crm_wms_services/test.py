# -*- coding:utf-8 -*-
# @Time    : 2026/4/6 09:19
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test.py
# @Software: PyCharm
import pandas as pd

from app.utils.spider_utli import simple_spider


def crm_mergeOrderList_spider(url0,headers,start_date,end_date):


    page = 1  # 第几页
    limit = 200  # 每页返回的数据
    # status = 1  # 状态（1为已调单）
    order_type_id = 1  # 表示1为销售订单
    is_wms = 1

    # 使用pandas进行分析，爬取的数据写入DataFrame
    df = pd.DataFrame()

    #循环分页爬取
    while True:

        # print("参数",page,limit,status,order_type_id,is_wms)
        url = (url0+"?page="+page.__str__()+"&limit="+limit.__str__()
               +"&order_type_id="+order_type_id.__str__()+"&is_wms="+is_wms.__str__()
               +"&orderdate[]="+start_date+"&orderdate[]="+end_date)

        print("爬取的api为",url)

        json_data=simple_spider(url, headers)
        page +=1

        if not json_data.get("data",{}):
            break
        print(json_data)
        data = json_data.get("data", {}).get("list", {}).get("data")

        if  data:
            # DataFrame数据追加
            df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
            # print(data)
            # print("数据为", len(data))
            if len(data) < limit:
                break
        else:
            continue



    return df


url_crm = "https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList"
headers_crm = {
        # 模拟浏览器请求头（必须加，否则很多网站会拦截）
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    "authorization":"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJjbGllbnQueGhhZG1pbiIsImF1ZCI6InNlcnZlci54aGFkbWluIiwiaWF0IjoxNzc1MDA0Mzc1LCJleHAiOjE3Nzc1OTYzNzUsInVpZCI6IjY2NSIsIm5hbWUiOiJcdTY3NGVcdTVmYjdcdTY3NzAiLCJhZG1pbl9zd2l0Y2hfbG9naW4iOiIifQ.RYxb-BxKvZoaClxkMFv2G8iiIsK4i8kTUw0Eo3xZYzg"}


# crm_mergeOrderList_spider(url_crm,headers_crm,"1775232000000","1775491199000")


a=203
b=20
print(a,b)
print("a/b",a/b)
print("a//b",a//b+3)
