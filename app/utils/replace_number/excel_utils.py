"""
更新替换号 Excel 处理工具
"""

import os
from datetime import datetime

import pandas as pd
from typing import List, Tuple

from app.utils.logger_config import TASK_LOG_DIR
from .constants import (
    OE_COLUMN_CANDIDATES,
    BRAND_COLUMN_CANDIDATES,
    REPLACE_NUMBER_COLUMN_CANDIDATES,
    BRAND_NUMBER_COLUMN_CANDIDATES,
)


def _find_column(df, candidates: List[str]) -> str:
    """根据候选列名查找实际列名"""
    lower_cols = {str(c).lower().strip(): c for c in df.columns}
    for key in candidates:
        if key.lower() in lower_cols:
            return lower_cols[key.lower()]
    return None


def _find_column_fuzzy(df, keywords: List[str]) -> str:
    """模糊匹配列名，列名中包含任一关键词即可"""
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in keywords:
            if kw.lower() in col_lower:
                return col
    return None


def dedup_numbers(numbers: List[str]) -> List[str]:
    """仅去重，不改变原始内容"""
    seen = set()
    result = []
    for n in numbers:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result


def read_replace_number_excel(file_path: str) -> Tuple[pd.DataFrame, List[dict]]:
    """
    读取更新替换号 Excel 第一个 sheet

    Returns:
        (df, rows)
        rows 中每个元素包含 row_index, oe, brand, new_numbers
    """
    df = pd.read_excel(file_path, sheet_name=0, dtype=str)

    oe_col = _find_column(df, OE_COLUMN_CANDIDATES)
    brand_col = _find_column(df, BRAND_COLUMN_CANDIDATES)
    replace_col = _find_column_fuzzy(df, REPLACE_NUMBER_COLUMN_CANDIDATES)
    brand_number_col = _find_column_fuzzy(df, BRAND_NUMBER_COLUMN_CANDIDATES)

    if not brand_number_col and (not oe_col or not brand_col):
        raise ValueError("Excel 缺少必要的 oe/品牌 列，也未提供品牌号列")

    def _to_str(value):
        if pd.isna(value):
            return ""
        s = str(value).strip()
        return "" if s.lower() == "nan" else s

    rows = []
    for idx, row in df.iterrows():
        oe = _to_str(row.get(oe_col, ""))
        brand = _to_str(row.get(brand_col, ""))
        brand_number = _to_str(row.get(brand_number_col, "")) if brand_number_col else ""
        new_numbers = []
        if replace_col:
            replace_raw = _to_str(row.get(replace_col))
            if replace_raw:
                new_numbers = [n.strip() for n in replace_raw.split(",") if n.strip()]

        rows.append({
            "row_index": idx,
            "oe": oe,
            "brand": brand,
            "brand_number": brand_number,
            "new_numbers": new_numbers,
            "matched_products": [],
            "updated_numbers": [],
            "status": "",
            "product_desc": []
        })

    return df, rows


def save_direct_result(file_path: str, df: pd.DataFrame, rows: List[dict]) -> str:
    """
    直接添加结果输出到新的 Excel 文件

    在原第一个 sheet 追加三列，其他 sheet 保留
    """
    status_col = []
    updated_col = []
    product_col = []

    for idx in df.index:
        row = rows[idx]
        status_col.append(row["status"])
        updated_col.append(",".join(row["updated_numbers"]))
        product_col.append("\n".join(row["product_desc"]))

    df["更新后的替换号"] = updated_col
    df["更新是否成功"] = status_col
    df["已更新的产品"] = product_col

    all_sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
    first_sheet_name = list(all_sheets.keys())[0]
    all_sheets[first_sheet_name] = df

    output_dir = os.path.join(TASK_LOG_DIR, 'replace_number')
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(base_name)[0]
    output_name = f"{name_without_ext}_{timestamp}_result.xlsx"
    output_path = os.path.join(output_dir, output_name)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, sheet_df in all_sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

    return output_path
