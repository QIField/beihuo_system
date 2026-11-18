#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 · 轮次入口（新版 PAGE_QUOTE 全链路）

职责单一：拉单列表 → 排序 → 逐单串行调用 pipeline.process_order → 轮次统计。
不含定时调度/互斥锁/时段控制（属 task 层职责，见 app/tasks/qpl_auto_quote_v2_task.py）。

与旧版差异：
- 拉单对齐网页参数：灰度订单(multiQuoteGray=true) + 仅含待报价明细(hasWaitingQuoteItem=1)，
  1 个月窗口仅个位数订单（旧参数拉 100 单，绝大多数无动作）
- 一单一单串行处理（不再 A/B 批量 + C 类重拉两阶段）
- 订单优先级仍保持 A 类在前（最快路径），B/C 类在后
- 状态过滤由三层表本地状态机承担（不再依赖 qpl_quote_result_v2 白名单）
- 订单分类复用旧模块 classify_order（零改动）
"""

from datetime import datetime, timedelta
import logging

from app.utils.qpl_auto_bill.qpl_config import qpl_log, get_supported_companies
from app.utils.qpl_auto_bill.auto_submit_part_quote import classify_order
from app.services.qpl_auto_quote.constants import ACTION_FETCH_LIST, RESULT_FAIL
from app.services.qpl_auto_quote.enquiry_api import list_enquiry_orders
from app.services.qpl_auto_quote.persistence import fetch_retry_order_nos, make_round_id, record_attempt
from app.services.qpl_auto_quote.pipeline import process_order

# 订单优先级：A 类（全 PART_QUOTE，最快路径）在前，B/C 类在后
_CATEGORY_ORDER = {'A': 0, 'B': 1, 'C': 1}

# 拉单日期窗口（接口限制不超过 1 个月）
FETCH_WINDOW_DAYS = 30


def run_round(company, begin_date=None, end_date=None):
    """
    执行单组织的一个报价轮次。

    双数据源：
    1. 列表接口（新单）：待报价tab + 灰度 + 仅含待报价明细
    2. 本地状态机（重试）：含 pending / 冷却到期 failed_temp 明细的订单
       （订单提交过报价后会掉出列表筛选范围，重试必须本地驱动）

    Args:
        company: 组织代码
        begin_date: 拉单开始日期 'YYYY-MM-DD'，默认30天前
        end_date:   拉单结束日期 'YYYY-MM-DD'，默认今天

    Returns:
        dict: 轮次统计 {'total', 'submitted', 'no_action', 'error'}
    """
    if begin_date is None:
        begin_date = (datetime.now() - timedelta(days=FETCH_WINDOW_DAYS)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    round_id = make_round_id(company)
    new_orders = _fetch_orders(company, begin_date, end_date, round_id)
    retry_nos = [no for no in fetch_retry_order_nos(company)
                 if no not in {no for no, _ in new_orders}]
    qpl_log(f"[{company}] 轮次 {round_id} 开始 | "
            f"新订单 {len(new_orders)} 个，本地待重试订单 {len(retry_nos)} 个")

    stats = {'total': len(new_orders) + len(retry_nos),
             'submitted': 0, 'no_action': 0, 'error': 0}
    idx = 0
    for enquiry_no, _ in _sort_orders_by_priority(new_orders):
        idx += 1
        _process_one(company, enquiry_no, round_id, idx, stats)
    for enquiry_no in retry_nos:
        idx += 1
        _process_one(company, enquiry_no, round_id, idx, stats)

    qpl_log(
        f"[{company}] 轮次 {round_id} 完成 | "
        f"提交={stats['submitted']} 无动作={stats['no_action']} 异常={stats['error']}"
    )
    return stats


def _process_one(company, enquiry_no, round_id, idx, stats):
    """处理单个订单并更新轮次统计（订单级异常隔离）"""
    try:
        submitted = process_order(company, enquiry_no, round_id)
        stats['submitted' if submitted else 'no_action'] += 1
        qpl_log(f"[{company}] 轮次 {round_id} [{idx}/{stats['total']}] "
                f"{enquiry_no} 处理完成（提交={submitted}）")
    except Exception as order_error:
        # 订单级异常隔离：单个订单失败不影响本轮其余订单
        stats['error'] += 1
        qpl_log(f"[{company}] 轮次 {round_id} 订单 {enquiry_no} 处理异常，跳过继续: {order_error}")


def run_all_companies(begin_date=None, end_date=None):
    """
    循环处理所有支持的组织（公司级异常隔离）。

    Returns:
        dict: {company: 轮次统计}
    """
    results = {}
    for company in get_supported_companies():
        try:
            results[company] = run_round(company, begin_date, end_date)
        except Exception:
            # 公司级异常隔离：单个公司失败不影响其他公司
            logger = logging.getLogger('qpl_auto_bill')
            logger.exception(f"[汽配龙自动报价] 组织 {company} 本轮处理异常，跳过该公司继续")
            results[company] = {'total': 0, 'submitted': 0, 'no_action': 0, 'error': 0}
    return results


# ============================================================================
# 内部步骤
# ============================================================================

def _fetch_orders(company, begin_date, end_date, round_id):
    """拉取询价单列表（网页版参数，自动翻页）并按 supplierEnquiryNo 去重"""
    unique = {}
    page_num = 1
    try:
        while True:
            result = list_enquiry_orders(begin_date, end_date,
                                         page_num=page_num, company=company)
            orders = result.get('data') or []
            for order in orders:
                no = order.get('supplierEnquiryNo')
                if no:
                    unique[no] = order
            if len(orders) < 100 or page_num >= 10:  # 每页100，不足一页即末页
                break
            page_num += 1
    except Exception as e:
        qpl_log(f"[{company}] 拉取订单列表失败: {e}")
        record_attempt(company, '', 0, round_id, ACTION_FETCH_LIST, RESULT_FAIL,
                       fail_stage='列表接口', fail_reason=str(e))
        return []
    return list(unique.items())


def _sort_orders_by_priority(order_pairs):
    """按类别排序：A 类在前，B/C 类在后，其余最后（保持稳定）"""
    def priority(pair):
        _, order = pair
        category = classify_order(order)
        return _CATEGORY_ORDER.get(category, 2)

    return sorted(order_pairs, key=priority)
