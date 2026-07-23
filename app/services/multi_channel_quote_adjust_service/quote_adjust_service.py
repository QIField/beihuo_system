"""
多渠道报价调价 - 服务层

职责：
- 解析 Excel 模板
- 业务编排：展开供应商、合并行、调用 CRM 匹配产品
- 组装前端表格数据
"""

from typing import List, Dict, Any, Tuple

import pandas as pd

from app.services.multi_channel_quote_adjust_service.repository import (
    fetch_suppliers_by_car_brand,
)
from app.utils.crm_product.crm_product_matcher import (
    fetch_matched_products,
    pick_product_fields,
)


# Excel 表头候选名
OE_COLUMN_CANDIDATES = ["oe", "OE", "OE 号", "OE号"]
BRAND_COLUMN_CANDIDATES = ["brand", "品牌", "对比系统品牌"]
CAR_BRAND_COLUMN_CANDIDATES = ["car_brand", "车辆品牌", "车型品牌"]


def _find_column(df_columns, candidates):
    """从 DataFrame 列名中查找候选列"""
    columns_lower = {str(c).strip().lower(): c for c in df_columns}
    for candidate in candidates:
        key = str(candidate).strip().lower()
        if key in columns_lower:
            return columns_lower[key]
    return None


def parse_excel_file(file_storage) -> Tuple[List[Dict[str, Any]], str]:
    """
    解析上传的 Excel 模板

    模板列：OE | 对比系统品牌 | 车辆品牌

    Args:
        file_storage: Flask request.files 中的文件对象

    Returns:
        (row_list, error_msg)
        row_list 元素: {'oe': str, 'brand': str, 'car_brand': str}
    """
    try:
        # dtype=str 保持 OE 等字段为字符串，避免纯数字 OE 被转为数值
        df = pd.read_excel(file_storage, dtype=str)
    except Exception as e:
        return [], f"Excel 读取失败: {e}"

    if df.empty:
        return [], "Excel 文件为空"

    df = df.where(pd.notna(df), None)
    df.columns = [str(c).strip() for c in df.columns]

    oe_col = _find_column(df.columns, OE_COLUMN_CANDIDATES)
    brand_col = _find_column(df.columns, BRAND_COLUMN_CANDIDATES)
    car_brand_col = _find_column(df.columns, CAR_BRAND_COLUMN_CANDIDATES)

    if not oe_col:
        return [], f"未找到 OE 列，支持的列名: {OE_COLUMN_CANDIDATES}"
    if not brand_col:
        return [], f"未找到品牌列，支持的列名: {BRAND_COLUMN_CANDIDATES}"

    rows = []
    for _, row in df.iterrows():
        oe = str(row.get(oe_col, "") or "").strip()
        if not oe:
            continue

        brand = str(row.get(brand_col, "") or "").strip()
        car_brand = str(row.get(car_brand_col, "") or "").strip() if car_brand_col else ""

        rows.append({
            "oe": oe,
            "brand": brand,
            "car_brand": car_brand,
        })

    return rows, ""


def expand_rows_with_suppliers(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据车辆品牌展开 Excel 行：每个 OE 匹配到多个供应商时拆分为多行

    供应商名称同时自动映射为 QQ，保证 qq_msg 表 QQ 字段不为空。

    Returns:
        每个元素包含 oe, brand, car_brand, supplier_text, qq
    """
    expanded = []
    for row in rows:
        car_brand = row.get("car_brand", "")
        suppliers = fetch_suppliers_by_car_brand(car_brand)

        if not suppliers:
            expanded.append({
                "oe": row["oe"],
                "brand": row["brand"],
                "car_brand": car_brand,
                "supplier_text": "",
                "qq": "",
            })
            continue

        for supplier in suppliers:
            supplier_name = supplier["supplier"]
            expanded.append({
                "oe": row["oe"],
                "brand": row["brand"],
                "car_brand": car_brand,
                "supplier_text": supplier_name,
                "qq": supplier_name,
            })

    return expanded


def merge_rows_by_oe(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按 OE + 品牌 + 车辆品牌 合并行

    供应商和 QQ 均用'、'连接，保持前端一行展示。

    Args:
        rows: 展开后的行

    Returns:
        合并后的行列表
    """
    groups = {}
    for row in rows:
        key = (row["oe"], row["brand"], row["car_brand"])
        if key not in groups:
            groups[key] = {
                "oe": row["oe"],
                "brand": row["brand"],
                "car_brand": row["car_brand"],
                "supplier_texts": [],
                "qq_texts": [],
            }

        supplier_text = row.get("supplier_text", "")
        if supplier_text and supplier_text not in groups[key]["supplier_texts"]:
            groups[key]["supplier_texts"].append(supplier_text)
            groups[key]["qq_texts"].append(row.get("qq") or supplier_text)

    return [
        {
            "oe": g["oe"],
            "brand": g["brand"],
            "car_brand": g["car_brand"],
            "supplier_text": "、".join(g["supplier_texts"]),
            "qq": "、".join(g["qq_texts"]),
        }
        for g in groups.values()
    ]


def _to_float(value: Any) -> float:
    """安全转为浮点数"""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _calc_profit_rate(sell_price: float, cost_price: float) -> str:
    """计算利润率"""
    if not sell_price or not cost_price:
        return ""
    return f"{((sell_price - cost_price) / sell_price * 100):.2f}%"


def _calc_profit_amount(sell_price: float, cost_price: float) -> str:
    """计算毛利额"""
    if not sell_price or not cost_price:
        return ""
    return f"{sell_price - cost_price:.2f}"


def build_quote_adjust_rows(company: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    查询 CRM 并组装前端表格数据

    Args:
        company: 公司代码
        rows: 包含 oe, brand, car_brand, supplier_text, qq 的行

    Returns:
        前端表格行列表
    """
    result = []

    for row in rows:
        oe = row["oe"]
        brand = row["brand"]
        car_brand = row["car_brand"]
        supplier_text = row["supplier_text"]

        matched_products = fetch_matched_products(company, oe, brand)

        if not matched_products:
            result.append({
                "oe": oe,
                "brand": brand,
                "car_brand": car_brand,
                "system_oe": "系统无搜索结果",
                "supplier": supplier_text,
                "sell_price": "",
                "cost_price": "",
                "profit_rate": "",
                "profit_amount": "",
                "supplier_selected": "",
                "new_sell_price": "",
                "new_profit_rate": "",
                "new_profit_amount": "",
                "product_id": "",
                "barcode": "",
                "modify": "是",
                "qq": row["qq"],
            })
            continue

        for product in matched_products:
            fields = pick_product_fields(product)
            sell_price = _to_float(fields.get("store_cass_price"))
            cost_price = _to_float(fields.get("cost_price"))

            result.append({
                "oe": oe,
                "brand": brand,
                "car_brand": car_brand,
                "system_oe": fields.get("number", ""),
                "supplier": supplier_text,
                "sell_price": f"{sell_price:.2f}" if sell_price else "",
                "cost_price": f"{cost_price:.2f}" if cost_price else "",
                "profit_rate": _calc_profit_rate(sell_price, cost_price),
                "profit_amount": _calc_profit_amount(sell_price, cost_price),
                "supplier_selected": "",
                "new_sell_price": "",
                "new_profit_rate": "",
                "new_profit_amount": "",
                "product_id": fields.get("product_id", ""),
                "barcode": fields.get("frey_no", ""),
                "modify": "是",
                "qq": row["qq"],
            })

    return result


def get_template_download_url() -> str:
    """获取模板下载 URL"""
    return "/static/excel/multi_price_edit.xlsx"
