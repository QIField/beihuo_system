"""
购物车供应商展开

按 purchase_records 将一个产品行展开为"每个供应商一行"，
供列表查询与各导出路径共用，保证单元格、浮窗、导出三处口径一致。
"""
import json
from typing import Any, Dict, List

# 无任何有效采购记录时的兜底单条
PLACEHOLDER_RECORD = {
    'supplier_name': '未知供应商',
    'purchase_price': None,
    'purchase_quantity': None,
    'purchase_date': ''
}


def try_parse_valid_records(records_json: str):
    """
    解析 purchase_records JSON：
    返回含有效供应商名的记录列表；JSON 非法或无有效供应商时返回 None
    """
    if records_json and isinstance(records_json, str):
        try:
            records = json.loads(records_json)
            if isinstance(records, list):
                return [r for r in records if r.get('supplier_name', '').strip()]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return None


def parse_valid_records(records_json: str) -> List[Dict[str, Any]]:
    """
    返回有效采购记录列表；无法解析或无有效供应商时，返回一条占位记录
    """
    return try_parse_valid_records(records_json) or [dict(PLACEHOLDER_RECORD)]


def build_supplier_text(record: Dict[str, Any]) -> str:
    """页面单元格文本：名称：价格（×数量）"""
    name = record.get('supplier_name', '').strip()
    price_raw = record.get('purchase_price')
    qty_raw = record.get('purchase_quantity')

    price_text = f"{float(price_raw):.2f}" if price_raw is not None else 'N/A'
    qty_text = str(int(float(qty_raw))) if qty_raw not in (None, '') else None

    if qty_text:
        return f"{name}：{price_text}（×{qty_text}）"
    return f"{name}：{price_text}"


def build_export_supplier_text(record: Dict[str, Any]) -> str:
    """
    导出用单条文本，与产品维度导出每条格式一致：
      - 有日期："日期 - 供应商 - 数量 - 单价"
      - 无日期："供应商 - 数量 - 单价"
    """
    name = record.get('supplier_name', '').strip()
    date = (record.get('purchase_date') or '').strip()
    qty_raw = record.get('purchase_quantity')
    price_raw = record.get('purchase_price', 0.0)

    qty_text = str(int(float(qty_raw))) if qty_raw not in (None, '') else '-'
    price_text = f"{float(price_raw):.2f}" if price_raw is not None else 'N/A'

    if date:
        return f"{date} - {name} - {qty_text} - {price_text}"
    return f"{name} - {qty_text} - {price_text}"


def expand_items_by_supplier(cart_items: List[Dict[str, Any]],
                             text_builder=build_supplier_text) -> List[Dict[str, Any]]:
    """
    将产品行按采购记录展开为多行；
    每行 purchase_records 收窄为单条，supplier 文本由 text_builder 决定
    （页面默认 build_supplier_text，导出传 build_export_supplier_text）
    """
    expanded = []

    for item in cart_items:
        for record in parse_valid_records(item.get('purchase_records', '')):
            new_item = item.copy()
            new_item['supplier'] = text_builder(record)
            new_item['purchase_records'] = json.dumps([record], ensure_ascii=False)
            expanded.append(new_item)

    return expanded
