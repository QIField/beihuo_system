#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙报价服务（编排层）

按组织循环调用工具层提交报价，并将结果落库。
明细提取见 qpl_quote_detail_extract，落库见 qpl_quote_persistence。

原则：
  1. 减少逻辑判断，必要情况下采取字典分发
  2. 异常按层级隔离：条目级记录后跳过、订单级跳过继续、公司级跳过继续，
     不让单点异常中断整轮任务
"""

import logging

from app.utils.qpl_auto_bill.auto_submit_part_quote import submit_all_quotes
from app.utils.qpl_auto_bill.qpl_config import get_supported_companies, qpl_log
from app.services.qpl_quote_persistence import _persist_order_result

_qpl_logger = logging.getLogger('qpl_auto_bill')


def process_and_save_quotes_for_company(company, begin_date=None, end_date=None):
    """
    处理指定组织的报价并保存结果

    所有经过处理的订单（无论提交成功或失败）都会保存到数据库

    Args:
        company: 组织代码（必填）
        begin_date: 开始日期
        end_date: 结束日期

    Returns:
        dict: 处理结果统计
    """
    # 调用工具层提交报价
    results = submit_all_quotes(begin_date, end_date, company=company)

    # 分类计数
    category_counts = {'A': 0, 'B': 0, 'C': 0}
    success_count = 0
    fail_count = 0

    for result in results:
        try:
            _persist_order_result(result, company)
        except Exception as save_error:
            # 落库级异常隔离：单个订单保存失败不影响其余订单
            _qpl_logger.exception(
                f"[{company}] 报价结果落库失败: {result.get('enquiry_no')}: {save_error}"
            )

        # 统计（无论保存是否成功，该订单本轮均已处理）
        category_counts[result['order_category']] += 1
        if result['success']:
            success_count += 1
        else:
            fail_count += 1

    return {
        'company': company,
        'success_count': success_count,
        'fail_count': fail_count,
        'total': len(results),
        'category_a': category_counts['A'],
        'category_b': category_counts['B'],
        'category_c': category_counts['C']
    }


def process_and_save_quotes_for_all_companies(begin_date=None, end_date=None):
    """
    循环处理所有支持的组织的报价并保存结果

    Args:
        begin_date: 开始日期
        end_date: 结束日期

    Returns:
        list: 各组织处理结果统计列表
    """
    companies = get_supported_companies()
    all_results = []

    for company in companies:
        try:
            result = process_and_save_quotes_for_company(company, begin_date, end_date)
        except Exception:
            # 公司级异常隔离：单个公司失败不影响其他公司
            _qpl_logger.exception(f"[汽配龙报价] 组织 {company} 本轮处理异常，跳过该公司继续")
            result = {
                'company': company,
                'success_count': 0,
                'fail_count': 0,
                'total': 0,
                'category_a': 0,
                'category_b': 0,
                'category_c': 0
            }
        all_results.append(result)

    # 汇总统计
    total_success = sum(r.get('success_count', 0) for r in all_results)
    total_fail = sum(r.get('fail_count', 0) for r in all_results)

    qpl_log(f"所有组织报价任务完成 | 成功={total_success} 失败={total_fail}")

    return all_results
