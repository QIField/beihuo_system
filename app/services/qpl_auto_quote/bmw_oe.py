#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 · 宝马(C类)本地 OE 库补齐适配层

宝马报价依赖本地 OE 价格库（check_bmw_oes_in_local_db / query_bmw_service_all）。
报价前需保证明细的原厂 OE 已在本地库中，缺失时调用 data_upsert 抓取补齐
（内部含宝马官网接口、兆配云兜底和入库，每个 OE 间隔 40-80 秒）。

本层平移旧链路（_collect_bmw_original_oes → check_bmw_oes_in_local_db
→ _ensure_bmw_oes_in_local_db），改为"单订单"粒度调用，旧函数零改动复用。
"""

from app.utils.qpl_auto_bill.qpl_config import qpl_log
from app.utils.qpl_auto_bill.auto_submit_part_quote import (
    _collect_bmw_original_oes,
    _ensure_bmw_oes_in_local_db,
)

CAR_BMW = '宝马'


def ensure_bmw_oes_for_order(detail, company, skip_item_ids=None):
    """
    单订单粒度的宝马 OE 补齐：收集 WAITING 明细的原厂 OE → 查本地库 → 补齐缺失。

    Args:
        detail: 全量详情（PAGE 合并后）
        company: 组织代码
        skip_item_ids: 本轮跳过的明细 ID 集合（本地终态/冷却中），不为其补 OE

    Returns:
        dict: 补齐统计
            {'collected': 收集到的 OE 数, 'missing': 本地缺失数,
             'filled': 实际补齐处理数, 'failed': 补齐失败数}
    """
    stats = {'collected': 0, 'missing': 0, 'filled': 0, 'failed': 0}
    if (detail.get('carBrand') or '').strip() != CAR_BMW:
        return stats

    enquiry_no = detail.get('supplierEnquiryNo') or ''
    processed = {(enquiry_no, item_id) for item_id in (skip_item_ids or set())}

    oe_set = _collect_bmw_original_oes([detail], company, processed_item_ids=processed)
    stats['collected'] = len(oe_set)
    if not oe_set:
        return stats

    from app.utils.qpl_auto_bill.bmw_quote_local_db import check_bmw_oes_in_local_db
    _, status = check_bmw_oes_in_local_db(list(oe_set))
    missing_oes = status.get('missing', [])
    stats['missing'] = len(missing_oes)
    if not missing_oes:
        qpl_log(f"[{company}] {enquiry_no} 宝马 OE 本地库齐全（{stats['collected']} 个）")
        return stats

    qpl_log(f"[{company}] {enquiry_no} 发现 {len(missing_oes)} 个宝马 OE 缺失，开始补齐本地库")
    result = _ensure_bmw_oes_in_local_db(missing_oes, company)
    stats['filled'] = result.get('total', 0)
    stats['failed'] = result.get('failed', 0)
    return stats
