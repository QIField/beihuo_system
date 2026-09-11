#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存数据查询与字段匹配服务
"""

import logging

from sqlalchemy import func, text

from app.models.orm_models.brand_qpl_mapping import BrandQplMapping
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


def _load_brand_quality_map(session, pp_list):
    """
    批量查询 brand_qpl_mapping，建立 pp -> (qpl_brand, qpl_quality) 映射

    Args:
        session: SQLAlchemy Session
        pp_list: pp 列表

    Returns:
        dict: {pp: (qpl_brand, qpl_quality)}
    """
    valid_pp_list = [pp for pp in pp_list if pp]
    if not valid_pp_list:
        return {}

    results = (
        session.query(BrandQplMapping.data_brand, BrandQplMapping.qpl_brand, BrandQplMapping.qpl_quality)
        .filter(BrandQplMapping.data_brand.in_(valid_pp_list))
        .all()
    )

    return {data_brand: (qpl_brand, qpl_quality) for data_brand, qpl_brand, qpl_quality in results}


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


def fetch_changsheng_raw_records():
    """
    从 changsheng_raw_inventory 获取最新一天、会被映射为"原厂国内4s件"的数据。

    映射规则：
    1. brand_name = '原厂大库'（经 normalize_brand 会映射为'原厂国内4s件'）
    2. brand_name = '原厂再制造' 且 清洗后的oe 以 '80' 结尾

    Returns:
        list[dict]: 每条记录包含
            product_name, oe, brand_part_no, reference_price,
            number_of_inventories, brand, quality
    """
    with orm_session() as session:
        try:
            latest_date = session.execute(
                text("SELECT DATE(MAX(fetch_time)) FROM changsheng_raw_inventory")
            ).scalar()

            if not latest_date:
                logger.info("[昌盛原始数据] changsheng_raw_inventory 无数据")
                return []

            rows = session.execute(
                text("""
                    SELECT part_name, `清洗后的oe`, sale_price, brand_name
                    FROM changsheng_raw_inventory
                    WHERE DATE(fetch_time) = :latest_date
                """),
                {'latest_date': latest_date}
            ).fetchall()

            records = []
            for row in rows:
                brand_name = str(row.brand_name or '').strip()
                cleaned_oe = str(row.清洗后的oe or '').strip()

                is_original_4s = False
                if brand_name == '原厂大库':
                    is_original_4s = True
                elif brand_name == '原厂再制造' and cleaned_oe.endswith('80'):
                    is_original_4s = True

                if not is_original_4s or not cleaned_oe:
                    continue

                records.append({
                    'product_name': row.part_name,
                    'oe': cleaned_oe,
                    'brand_part_no': None,
                    'reference_price': row.sale_price,
                    'number_of_inventories': 12,
                    'brand': '4S原厂件',
                    'quality': '国内品牌',
                })

            logger.info(
                f"[昌盛原始数据] 最新 {latest_date} 共 {len(records)} 条映射为原厂国内4s件"
            )
            return records
        except Exception:
            logger.exception("[昌盛原始数据] 获取失败，跳过")
            return []


def fetch_virtual_inventory_records(limit=None):
    """
    查询 qpl_virtual_qty 数据，并转换为导入需要的字段；
    同时合并 changsheng_raw_inventory 中映射为"原厂国内4s件"的数据。

    pp 需在 brand_qpl_mapping 中匹配到 qpl_brand 和 qpl_quality，
    未匹配到的记录直接丢弃，不生成到 Excel。

    Args:
        limit: 限制返回记录数，None 表示不限制；大于0时随机取样

    Returns:
        list[dict]: 每条记录包含
            product_name, oe, brand_part_no, reference_price,
            number_of_inventories, brand, quality
    """
    with orm_session() as session:
        query = session.query(
            QplVirtualQty.ys_oe1,
            QplVirtualQty.product_name1,
            QplVirtualQty.pp,
            QplVirtualQty.reference_price,
            QplVirtualQty.number_of_inventories,
            QplVirtualQty.merchant_code,
        )
        if limit:
            query = query.order_by(func.rand()).limit(limit)
        rows = query.all()

        merchant_codes = [r.merchant_code for r in rows if r.merchant_code]
        brand_code_map = _load_brand_code_map(session, merchant_codes)

        pp_list = [r.pp for r in rows if r.pp]
        brand_quality_map = _load_brand_quality_map(session, pp_list)

    records = []
    skipped_count = 0
    for r in rows:
        brand, quality = brand_quality_map.get(r.pp, (None, None))
        if not brand or not quality:
            skipped_count += 1
            continue

        row_dict = {
            'oe': r.ys_oe1,
            'product_name': r.product_name1,
            'pp': r.pp,
            'reference_price': r.reference_price,
            'number_of_inventories': r.number_of_inventories,
            'merchant_code': r.merchant_code,
        }
        brand_part_no = _resolve_brand_part_no(row_dict, brand_code_map)

        records.append({
            'product_name': r.product_name1,
            'oe': r.ys_oe1,
            'brand_part_no': brand_part_no,
            'reference_price': r.reference_price,
            'number_of_inventories': r.number_of_inventories,
            'brand': brand,
            'quality': quality,
        })

    logger.info(
        f"[虚拟库存] 查询到 {len(rows)} 条原始记录，"
        f"匹配成功 {len(records)} 条，跳过 {skipped_count} 条"
    )

    # 合并昌盛原始数据中映射为"原厂国内4s件"的记录
    changsheng_records = fetch_changsheng_raw_records()
    if changsheng_records:
        records.extend(changsheng_records)
        logger.info(
            f"[虚拟库存] 合并昌盛原始数据 {len(changsheng_records)} 条，"
            f"总记录数 {len(records)} 条"
        )

    return records
