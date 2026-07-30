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
    fetch_qq_chat_message_results_by_oes,
    fetch_qq_chat_message_results_by_oe,
    save_to_qq_msg,
    save_import_records,
    fetch_recent_imports,
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
                "system_oe": "系统无库存",
                "supplier": supplier_text,
                "sell_price": "",
                "cost_price": "",
                "profit_rate": "",
                "profit_amount": "",
                "supplier_selected": "",
                "cass_price": "",
                "peer_price": "",
                "qpl_price": "",
                "new_profit_rate": "",
                "new_profit_amount": "",
                "product_id": "",
                "barcode": "",
                "stock": "",
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
                "brand": fields.get("brand_name") or brand,
                "car_brand": car_brand,
                "system_oe": fields.get("number", ""),
                "supplier": supplier_text,
                "sell_price": f"{sell_price:.2f}" if sell_price else "",
                "cost_price": f"{cost_price:.2f}" if cost_price else "",
                "profit_rate": _calc_profit_rate(sell_price, cost_price),
                "profit_amount": _calc_profit_amount(sell_price, cost_price),
                "supplier_selected": "",
                "cass_price": "",
                "peer_price": "",
                "qpl_price": "",
                "new_profit_rate": "",
                "new_profit_amount": "",
                "product_id": fields.get("product_id", ""),
                "barcode": fields.get("frey_no", ""),
                "stock": str(fields.get("stock", "")),
                "modify": "是",
                "qq": row["qq"],
            })

    return result


def get_template_download_url() -> str:
    """获取模板下载 URL"""
    return "/static/excel/multi_price_edit.xlsx"


def _to_str_price(value: Any) -> str:
    """将价格转为字符串，保留两位小数"""
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return str(value)


def aggregate_qq_results_by_supplier_brand(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按供应商 + 品牌聚合 QQ 消息结果

    规则：
    - 分组键：（询价供应商, 返回品牌）
    - 过滤 price 为 null 或无效值的记录
    - 中间价 = (最大值 + 最小值) / 2，保留两位小数
    - 返回 OE 用逗号连接分组内所有 result_oe
    - 每组仅输出一条聚合记录
    """
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for r in results:
        supplier = r.get("供应商", "") or r.get("supplier", "")
        brand = r.get("brand", "")
        key = (supplier, brand)
        groups.setdefault(key, []).append(r)

    aggregated: List[Dict[str, Any]] = []
    for (supplier, brand), group_records in groups.items():
        valid_prices: List[float] = []
        oes: List[str] = []
        search_oe = ""

        for r in group_records:
            price = r.get("price")
            if price is None or price == "":
                continue
            try:
                valid_prices.append(float(price))
                oes.append(str(r.get("result_oe", "") or "").strip())
                if not search_oe:
                    search_oe = r.get("search_oe", "")
            except (ValueError, TypeError):
                continue

        if not valid_prices:
            continue

        max_price = max(valid_prices)
        min_price = min(valid_prices)
        mid_price = round((max_price + min_price) / 2, 2)

        aggregated.append({
            "search_oe": search_oe,
            "result_oe": ",".join(oe for oe in oes if oe),
            "供应商": supplier,
            "brand": brand,
            "price": mid_price,
        })

    return aggregated


def _extract_allowed_suppliers(rows: List[Dict[str, Any]]) -> List[str]:
    """
    从表格行中提取所有允许的供应商（支持 '、' 分隔）
    """
    allowed = []
    for row in rows:
        supplier_text = row.get("supplier", "") or ""
        for part in str(supplier_text).split("、"):
            part = part.strip()
            if part:
                allowed.append(part)
    return allowed


def _is_supplier_allowed(result_supplier: str, allowed_suppliers: List[str]) -> bool:
    """
    判断结果供应商是否被允许，支持模糊匹配（双向包含）
    """
    if not result_supplier:
        return False
    result_supplier = str(result_supplier).strip()
    for allowed in allowed_suppliers:
        allowed = str(allowed).strip()
        if not allowed:
            continue
        if allowed in result_supplier or result_supplier in allowed:
            return True
    return False


def expand_rows_with_qq_results(rows: List[Dict[str, Any]], hours: int = 36) -> List[Dict[str, Any]]:
    """
    将导入行按 qq_chat_message_result 的匹配结果逐行展开

    规则：
    - 用导入行的 oe 匹配结果表的 search_oe
    - 只取最近 N 小时内的结果
    - 只保留表格中已存在的供应商（支持模糊匹配）
    - 对结果按供应商 + 品牌聚合，每组输出一行
    - 无结果时保留原行， supplier / return_brand / return_price 为空

    Args:
        rows: fetch_recent_imports 返回的行列表
        hours: 结果时间窗口（小时）

    Returns:
        展开后的行列表
    """
    if not rows:
        return []

    allowed_suppliers = _extract_allowed_suppliers(rows)

    oe_list = [row.get("oe", "") for row in rows if row.get("oe")]
    results = fetch_qq_chat_message_results_by_oes(oe_list, hours)

    # 按表格供应商过滤，只保留匹配的报价
    results = [r for r in results if _is_supplier_allowed(r.get("供应商", ""), allowed_suppliers)]

    results = aggregate_qq_results_by_supplier_brand(results)

    results_by_oe: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        oe = r.get("search_oe", "")
        if oe not in results_by_oe:
            results_by_oe[oe] = []
        results_by_oe[oe].append(r)

    expanded = []
    for row in rows:
        oe = row.get("oe", "")
        row_brand = row.get("brand", "") or ""

        # 按当前行品牌过滤，只展示系统返回品牌匹配的结果
        matched = [
            r for r in results_by_oe.get(oe, [])
            if str(r.get("brand", "") or "").strip() == str(row_brand).strip()
        ]

        if not matched:
            new_row = dict(row)
            new_row["supplier"] = ""
            new_row["return_oe"] = ""
            new_row["return_brand"] = ""
            new_row["return_price"] = ""
            expanded.append(new_row)
            continue

        for r in matched:
            new_row = dict(row)
            new_row["supplier"] = r.get("供应商", "")
            new_row["return_oe"] = r.get("result_oe", "")
            new_row["return_brand"] = r.get("brand", "")
            new_row["return_price"] = _to_str_price(r.get("price"))
            expanded.append(new_row)

    return expanded


def fetch_all_brand_quotes_by_oe(oe: str, hours: int = 36) -> List[Dict[str, Any]]:
    """
    获取单个 OE 的全部品牌供应商报价（不过滤品牌，不过滤表格供应商）

    Args:
        oe: 搜索 OE
        hours: 结果时间窗口（小时）

    Returns:
        聚合后的报价列表，每条包含 supplier, brand, result_oe, price
    """
    results = fetch_qq_chat_message_results_by_oe(oe, hours)
    aggregated = aggregate_qq_results_by_supplier_brand(results)

    return [
        {
            "supplier": r.get("供应商", ""),
            "brand": r.get("brand", ""),
            "result_oe": r.get("result_oe", ""),
            "price": _to_str_price(r.get("price")),
        }
        for r in aggregated
    ]


def save_import_pipeline(expanded_rows: List[Dict[str, Any]], full_rows: List[Dict[str, Any]], create_by: str) -> None:
    """
    导入 Excel 后的完整保存流程

    Args:
        expanded_rows: 展开供应商后的行
        full_rows: 组装完成的前端表格行
        create_by: 操作人
    """
    save_to_qq_msg(expanded_rows)
    save_import_records(full_rows, create_by)


def fetch_quote_list_data(hours: int = 36) -> List[Dict[str, Any]]:
    """
    获取报价列表数据（含 QQ 聊天消息结果展开）

    Args:
        hours: 查询最近 N 小时内的导入记录

    Returns:
        展开后的前端表格行列表
    """
    data_list = fetch_recent_imports(hours)
    return expand_rows_with_qq_results(data_list, hours=hours)
