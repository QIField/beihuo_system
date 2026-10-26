# -*- coding:utf-8 -*-
# @Time    : 2026/10/22
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : get_merge_order_list_full_tasks.py
# @Software: PyCharm
# crm_sales_order 每周六 02:00 拉取任务（独立实现，不调用既有任务文件）：
#   - 与按天窗口任务（get_merge_order_list_by_all_updata，每天 02:00 拉近一天）互补，
#     兜底修正近一年订单在 CRM 侧的结清/金额变动（如 no_receive_amount 回刷）；
#   - 拉取窗口 = 近一年（orderdate 毫秒时间戳），2000/页自动翻页；
#   - 入库 upsert（on_duplicate_key_update，跳过 created_at/updated_at/orders_id），
#     重复拉取幂等无脏数据；最后一页判定 = 当页数量不足 limit
#     （原任务文件的退出条件含恒 False 判断，本文件已修正，避免空页误退出）；
#   - 环境变量 AUTO_START_CRM_SALES_ORDER_FULL=false 可禁用（默认启用）。

import os
from datetime import datetime, timedelta

from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.crm.crm_sales_order import CrmSalesOrder
from app.scripts.spiders.pipeline_clean.crm_gzbbr_clean import crm_sales_order_clear
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.utils.orm.session import orm_session


def get_merge_order_list_full_service(orderdate_start=None, orderdate_end=None, store="fsbbr"):
    """
    分页拉取合并订单列表并入库（独立实现，供本文件任务函数调用）

    :param orderdate_start: 订单时间范围起（毫秒时间戳，None = 不限）
    :param orderdate_end: 订单时间范围止（毫秒时间戳，None = 不限）
    :param store: 门店标识（仅参与清洗落库，接口请求不区分门店）
    :return: 入库的订单总数
    """
    # 全量接口单页 200 条响应较慢，默认 timeout=10s 会超时（重试耗尽后 fetch 返回 None），
    # 此处调大超时与重试次数
    spider = CrmGzbbrSpider(timeout=60, retry_count=3)
    limit = 2000
    data_total_count = 0  # 全量订单累计
    current_page = 1

    while True:
        json_data = spider.get_mergeOrderList(
            page=current_page,
            limit=limit,
            orderdate_start=orderdate_start,
            orderdate_end=orderdate_end,
        ).json()  # pyright: ignore[reportOptionalMemberAccess]

        order_list = (json_data.get("data") or {}).get("list", {}).get("data") or []

        # 接口返回空页：全部数据拉取完毕
        if not order_list:
            print(f"第{current_page}页无数据，拉取结束")
            break

        print(f"第{current_page}页原始订单数量: {len(order_list)}")

        # 数据清洗和字段过滤
        filtered_data_list = crm_sales_order_clear(data_list=order_list, store=store, level_id=None)
        print(f"第{current_page}页清洗后订单数量: {len(filtered_data_list)}")

        # 入库（插入或更新，跳过 orders_id/时间戳列）
        if filtered_data_list:
            print(f"开始入库第{current_page}页数据...")
            with orm_session() as session:
                insert_stmt = insert(CrmSalesOrder.__table__).values(filtered_data_list)

                # 从数据表取字段构建更新字典，避免多余字段 KeyError
                skip_cols = {'created_at', 'updated_at', 'orders_id'}
                all_cols = CrmSalesOrder.__table__.columns.keys()
                update_dict = {
                    k: insert_stmt.inserted[k]
                    for k in all_cols
                    if k not in skip_cols
                }
                session.execute(insert_stmt.on_duplicate_key_update(**update_dict))
                session.commit()

        data_total_count += len(filtered_data_list)
        print(f"第{current_page}页订单数量: {len(order_list)}, 全量累计: {data_total_count}")

        # 最后一页：当页数量不足 limit
        if len(order_list) < limit:
            print(f"当前页数量不足 {limit}，已到最后一页，拉取结束")
            break

        current_page += 1

    return data_total_count


def get_merge_order_list_full_task():
    """
    拉取 crm_sales_order 任务（每周六 02:00，近一年窗口）
    """
    print(f"\n[定时任务] crm_sales_order 近一年拉取开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * 100)
    # 订单时间窗口：近一年（接口 orderdate 为毫秒时间戳）
    orderdate_end = int(datetime.now().timestamp() * 1000)
    orderdate_start = int((datetime.now() - timedelta(days=365)).timestamp() * 1000)
    total = get_merge_order_list_full_service(orderdate_start=orderdate_start, orderdate_end=orderdate_end)
    print(f"\n[定时任务] crm_sales_order 近一年拉取完成，共入库 {total} 条 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * 100)


def get_merge_order_list_full_register():
    """
    注册 crm_sales_order 全量拉取定时任务（每周六 02:00）
    """
    from app.core.task_enhancer import get_task_manager
    task_manager = get_task_manager()

    auto_start = os.environ.get('AUTO_START_CRM_SALES_ORDER_FULL', 'true').lower() != 'false'
    if not auto_start:
        print("[crm_sales_order全量] 已禁用（AUTO_START_CRM_SALES_ORDER_FULL=false）")
        return

    try:
        task_manager.schedule(
            func=get_merge_order_list_full_task,
            trigger='cron',
            job_id='get_merge_order_list_full_task',
            day_of_week='sat',
            hour=2,
            minute=0,
            replace_existing=True,
        )
        print("[任务] get_merge_order_list_full_task 已注册（每周六 02:00 全量拉取）")

    except Exception as e:
        print(f"[任务] get_merge_order_list_full_task 注册失败: {e}")


# if __name__ == '__main__':
#     get_merge_order_list_full_task()