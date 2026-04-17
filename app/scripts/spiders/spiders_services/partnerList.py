# -*- coding:utf-8 -*-
# @Time    : 2026/4/14 17:36
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : partnerList.py
# @Software: PyCharm
import sys

import pandas as pd

from app.models.orm_models.partner_list import PartnerList
from app.scripts.spiders.pipeline_clean.partnerList_clean import remove_duplicate
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.utils.orm import orm_session


def partnerList(token, page_num=None):
    spider = CrmGzbbrSpider(token)
    limit = 200
    data_total_count = 0  # 存储所有客户数据总计
    current_page = 1



    while True:
        # 请求接口
        json_data = spider.get_partnerList(
            page=current_page,
            limit=limit,
        ).json()

        # print(json_data)
        # 无数据直接退出
        if not json_data.get("data", {}).get("data", {}):
            print(json_data)
            print(f"第{current_page}页无数据，爬取结束")
            break

        # 获取当前页订单
        order_list = json_data.get("data", {}).get("data", {})

        # 进行数据清洗和字段过滤
        print(f"第{current_page}页原始订单数量: {len(order_list)}")
        filtered_data_list = remove_duplicate(order_list)
        print(f"第{current_page}页清洗后订单数量: {len(filtered_data_list)}")

        # 进行入库操作（插入或更新）
        if filtered_data_list:
            print(f"开始入库第{current_page}页数据...")
            with orm_session() as session:
                count = PartnerList.bulk_upsert(session, filtered_data_list)
                print(f"第{current_page}页成功入库 {count} 条数据（插入或更新）")


        # #生成excel
        # df = pd.DataFrame(filtered_data_list)
        # df.to_excel(f"partnerList_{current_page}.xlsx", index=False)


        # 累加数据
        data_total_count += len(filtered_data_list)
        print(f"第{current_page}页订单数量: {len(order_list)}, 累计: {data_total_count}")

        # ===================== 核心退出逻辑 =====================
        # 1. 指定了页数：爬够页数就退出
        if page_num is not None and current_page >= page_num:
            print(f"已爬取指定的{page_num}页，爬取结束")
            break

        # # 2. 爬取全部模式：当前页数量不足limit，说明是最后一页
        # if len(order_list) < limit and not order_list:
        #     print(json_data)
        #     print("当前页数量不足限制，已到最后一页，爬取结束")

        # 3. 继续下一页
        current_page += 1

if __name__ == '__main__':
    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJjbGllbnQueGhhZG1pbiIsImF1ZCI6InNlcnZlci54aGFkbWluIiwiaWF0IjoxNzc2MjE1NDYxLCJleHAiOjE3Nzg4MDc0NjEsInVpZCI6IjY2NSIsIm5hbWUiOiJcdTY3NGVcdTVmYjdcdTY3NzAiLCJhZG1pbl9zd2l0Y2hfbG9naW4iOiIifQ.x8YL5pQyXpY4nf9Ap62uUkM4B16qpYXCKi06KewH9vw"
    partnerList(token)