# -*- coding: utf-8 -*-
"""
汽配龙自动报价 - 本地 BMW 零件库查询
"""

from datetime import datetime, timedelta
from app.utils.orm.session import orm_session
from app.models.orm_models.car_parts_library_bmw import CarPartsLibraryBmw
from app.models.orm_models.car_parts_library_bmw_stock import CarPartsLibraryBmwStock


WAREHOUSE_MAP = {
    'warehouse_beijing': '北京',
    'warehouse_shanghai': '上海',
    'warehouse_foshan': '佛山',
    'warehouse_chengdu': '成都',
    'warehouse_shenyang': '沈阳',
    'warehouse_hefei': '合肥',
    'warehouse_ningbo': '宁波',
}


def check_bmw_oes_in_local_db(oe_list, days=2):
    """
    查询本地 BMW 零件库，返回命中结果和缺失 OE 列表。
    命中格式与 query_bmw_service_all() 保持一致。

    :param oe_list: OE 列表
    :param days:    有效期天数
    :return:        (hit_map, missing_list)
    """
    if not oe_list:
        return {}, []

    cutoff = datetime.now() - timedelta(days=days)
    oe_set = list(set(oe_list))

    with orm_session() as session:
        detail_rows = session.query(CarPartsLibraryBmw).filter(
            CarPartsLibraryBmw.part_number.in_(oe_set),
            CarPartsLibraryBmw.updated_at >= cutoff
        ).all()

        stock_rows = session.query(CarPartsLibraryBmwStock).filter(
            CarPartsLibraryBmwStock.part_number.in_(oe_set),
            CarPartsLibraryBmwStock.updated_at >= cutoff
        ).all()

        # 在 session 内把属性全部取出，避免 DetachedInstanceError
        detail_list = [
            {
                'part_number': row.part_number,
                'dealer_net_stock': row.dealer_net_stock,
            }
            for row in detail_rows
        ]
        stock_list = [
            {
                'part_number': row.part_number,
                **{col: getattr(row, col) for col in WAREHOUSE_MAP.keys()}
            }
            for row in stock_rows
        ]

    stock_map = {row['part_number']: row for row in stock_list}

    hit_map = {}
    missing = []
    no_stock = []
    invalid_price = []
    detail_oes = set()

    for detail in detail_list:
        oe = detail['part_number']
        detail_oes.add(oe)
        stock = stock_map.get(oe)

        if not stock:
            missing.append(oe)
            continue

        net_price = _to_float(detail['dealer_net_stock'])
        if net_price <= 0:
            invalid_price.append(oe)
            continue

        stock_info = []
        for col, city in WAREHOUSE_MAP.items():
            qty = _to_int(stock.get(col))
            if qty > 0:
                stock_info.append({
                    'warehouse': city,
                    'quantity_available': qty
                })

        if not stock_info:
            no_stock.append(oe)
            continue

        hit_map[oe] = {
            'net_price': net_price,
            'stock_info': stock_info
        }

    for oe in oe_set:
        if oe not in detail_oes and oe not in missing:
            missing.append(oe)

    return hit_map, {
        'missing': missing,
        'no_stock': no_stock,
        'invalid_price': invalid_price,
    }


def _to_float(v):
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_int(v):
    if v is None:
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0
