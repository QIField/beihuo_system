# -*- coding: utf-8 -*-
"""
物料在途库存同步 - 数据处理

负责响应解析、产品层与在途明细层的展平、字段校验与类型清洗。

校验规则：
  - product_id（可转整数）、order_no（非空字符串）为关键字段，缺失则丢弃该明细
  - 数量/价格/日期为非关键字段，转换失败置 NULL 并保留记录
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.utils.logger_config import get_task_logger

logger = get_task_logger('b2b_intransit_sync')


def _to_str(value):
    """转去空白字符串；空值返回 None"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value):
    """安全转整数；失败返回 None"""
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None


def _to_decimal(value):
    """安全转 Decimal（价格）；失败返回 None"""
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        logger.warning(f"[在途校验] 价格无法转换: {value!r}")
        return None


def _to_date(value):
    """按 Y-m-d 解析日期；失败返回 None"""
    text = _to_str(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        logger.warning(f"[在途校验] 日期格式无法解析: {value!r}")
        return None


def extract_products(payload):
    """
    从响应 JSON 中提取产品列表

    兼容两种响应形态：
      - data 直接为产品数组（文档响应示例）
      - data 为分页对象（含 data 数组，文档参数表描述）

    :return: 产品 dict 列表；"暂无数据"时返回空列表
    :raises ValueError: 业务状态非200或 data 结构无法识别
    """
    status = payload.get('status')
    msg = payload.get('msg')

    if status == 404 or (msg and '暂无数据' in str(msg)):
        logger.info("[在途接口] 接口返回暂无数据，按空在途处理")
        return []

    if status != 200:
        raise ValueError(f"接口返回失败: status={status}, msg={msg}")

    data = payload.get('data')

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        inner = data.get('data')
        if isinstance(inner, list):
            logger.warning(
                f"[在途接口] 接口返回分页形态: total={data.get('total')}, "
                f"last_page={data.get('last_page')}，当前仅处理首页数据"
            )
            return inner
        logger.info("[在途接口] 分页对象无 data 列表，按空在途处理")
        return []

    if data is None:
        return []

    raise ValueError(f"data 字段格式异常: {type(data)}")


def flatten_and_validate(products, sync_time, company):
    """
    将产品列表展平为在途明细记录并做字段校验

    :param products: 产品 dict 列表
    :param sync_time: 本次同步时间
    :param company: 公司代码
    :return: (records, stats)
        records: 可直接 bulk_insert_mappings 的 dict 列表
        stats: {'product_count', 'item_count', 'valid_count', 'invalid_count'}
    """
    records = []
    stats = {'product_count': len(products), 'item_count': 0, 'valid_count': 0, 'invalid_count': 0}

    for product in products:
        if not isinstance(product, dict):
            continue

        product_id = _to_int(product.get('product_id'))
        base = {
            'product_id': product_id,
            'frey_no': _to_str(product.get('frey_no')),
            'oe_number': _to_str(product.get('number')),
            'product_name': _to_str(product.get('product_name')),
        }

        items = product.get('stock_zaitu_list')
        if not isinstance(items, list):
            continue

        for item in items:
            stats['item_count'] += 1

            if not isinstance(item, dict):
                stats['invalid_count'] += 1
                continue

            order_no = _to_str(item.get('order_no'))

            # 关键字段校验：产品ID、采购单号缺失则丢弃
            if product_id is None or not order_no:
                stats['invalid_count'] += 1
                logger.warning(
                    f"[在途校验] 丢弃缺少关键字段的明细: "
                    f"product_id={product.get('product_id')!r}, order_no={item.get('order_no')!r}"
                )
                continue

            records.append({
                **base,
                'company': company,
                'order_no': order_no,
                'supplier_name': _to_str(item.get('fullname')),
                'purchase_quantity': _to_int(item.get('purchase_quantity')),
                'price': _to_decimal(item.get('price')),
                'order_date': _to_date(item.get('create_date')),
                'expected_delivery_date': _to_date(item.get('expected_delivery_date')),
                'warehouse_name': _to_str(item.get('warehouse_name')),
                'sync_time': sync_time,
            })
            stats['valid_count'] += 1

    return records, stats
