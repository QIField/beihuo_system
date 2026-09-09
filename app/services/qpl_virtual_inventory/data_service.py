#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存数据查询与字段匹配服务
"""

import logging

from app.models.orm_models.crmapp_compare_summary import CrmappCompareSummary
from app.models.orm_models.qpl_virtual_qty import QplVirtualQty
from app.utils.orm.session import orm_session

logger = logging.getLogger('qpl_virtual_inventory')


def _is_frey_brand(pp):
    """
    判断 pp 是否为菲尔/FREY 类品牌（忽略大小写）
    """
    if not pp:
        return False
    pp_upper = str(pp).upper()
    return '菲尔' in pp_upper or 'FREY' in pp_upper


def _resolve_brand_part_no(row, brand_code_map):
    """
    确定品牌零件号

    菲尔/FREY 类：直接返回 merchant_code
    其他：使用 merchant_code 匹配 brand_code_map
    """
    merchant_code = row.get('merchant_code')
    pp = row.get('pp')

    if _is_frey_brand(pp):
        return merchant_code

    if merchant_code and merchant_code in brand_code_map:
        return brand_code_map[merchant_code]

    return None


def _match_brand_quality(pp):
    """
    根据 pp 匹配品牌与品质（预留，待匹配表完善后实现）

    Args:
        pp: 对应开思要求的品牌

    Returns:
        tuple: (品牌, 品质)
    """
    return None, None


def _load_brand_code_map(session, merchant_codes, company='fsbbr'):
    """
    批量查询 crmapp_compare_summary，建立 merchant_code -> brand_code 映射

    Args:
        session: SQLAlchemy Session
        merchant_codes: merchant_code 列表
        company: 公司代码

    Returns:
        dict: {merchant_code: brand_code}
    """
    if not merchant_codes:
        return {}

    results = (
        session.query(CrmappCompareSummary.frey_no, CrmappCompareSummary.brand_code)
        .filter(
            CrmappCompareSummary.frey_no.in_(merchant_codes),
            CrmappCompareSummary.company == company
        )
        .all()
    )

    return {frey_no: brand_code for frey_no, brand_code in results if frey_no}


def fetch_virtual_inventory_records():
    """
    查询 qpl_virtual_qty 全表数据，并转换为导入需要的字段

    Returns:
        list[dict]: 每条记录包含
            product_name, oe, brand_part_no, reference_price,
            number_of_inventories, brand, quality
    """
    with orm_session() as session:
        rows = (
            session.query(
                QplVirtualQty.ys_oe1,
                QplVirtualQty.product_name1,
                QplVirtualQty.pp,
                QplVirtualQty.reference_price,
                QplVirtualQty.number_of_inventories,
                QplVirtualQty.merchant_code,
            )
            .all()
        )

        merchant_codes = [r.merchant_code for r in rows if r.merchant_code]
        brand_code_map = _load_brand_code_map(session, merchant_codes)

    records = []
    for r in rows:
        row_dict = {
            'oe': r.ys_oe1,
            'product_name': r.product_name1,
            'pp': r.pp,
            'reference_price': r.reference_price,
            'number_of_inventories': r.number_of_inventories,
            'merchant_code': r.merchant_code,
        }
        brand_part_no = _resolve_brand_part_no(row_dict, brand_code_map)
        brand, quality = _match_brand_quality(r.pp)

        records.append({
            'product_name': r.product_name1,
            'oe': r.ys_oe1,
            'brand_part_no': brand_part_no,
            'reference_price': r.reference_price,
            'number_of_inventories': r.number_of_inventories,
            'brand': brand,
            'quality': quality,
        })

    logger.info(f"[虚拟库存] 查询到 {len(records)} 条待导入记录")
    return records
