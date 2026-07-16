"""
更新替换号 Excel 处理工具
"""

import pandas as pd
from typing import List, Tuple
from .constants import (
    OE_COLUMN_CANDIDATES,
    BRAND_COLUMN_CANDIDATES,
    REPLACE_NUMBER_COLUMN_CANDIDATES,
)


def _find_column(df, candidates: List[str]) -> str:
    """根据候选列名查找实际列名"""
    lower_cols = {str(c).lower().strip(): c for c in df.columns}
    for key in candidates:
        if key.lower() in lower_cols:
            return lower_cols[key.lower()]
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
    replace_col = _find_column(df, REPLACE_NUMBER_COLUMN_CANDIDATES)

    if not oe_col or not brand_col:
        raise ValueError("Excel 缺少必要的 oe 或 品牌 列")

    rows = []
    for idx, row in df.iterrows():
        oe = str(row.get(oe_col, "")).strip()
        brand = str(row.get(brand_col, "")).strip()
        new_numbers = []
        if replace_col and pd.notna(row.get(replace_col)):
            new_numbers = [n.strip() for n in str(row.get(replace_col)).split(",") if n.strip()]

        rows.append({
            "row_index": idx,
            "oe": oe,
            "brand": brand,
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

    output_path = file_path.replace(".xlsx", "_result.xlsx").replace(".xls", "_result.xls")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, sheet_df in all_sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

    return output_path
