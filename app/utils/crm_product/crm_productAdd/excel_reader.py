"""
Excel/CSV 读取和 item 构建模块

职责：
- 识别 Excel 列名
- 按模式筛选工作表
- 读取 Excel/CSV 文件
- 构建待处理的 item 列表
"""

import os
from typing import Dict, List, Optional, Tuple

import pandas as pd


# 列名候选（支持多种命名习惯）
OE_COLUMN_CANDIDATES = ['oe', 'OE', 'barcode', '物料条码']
BRAND_COLUMN_CANDIDATES = ['brand', '品牌', '品牌名称']
BRAND_CODE_COLUMN_CANDIDATES = ['brand_code', '条码', '物料条码', '品牌代码']

# 支持的处理模式
MODE_TWO_COLUMN = 'two_column'
MODE_THREE_COLUMN = 'three_column'


def identify_columns(df) -> Tuple[Optional[str], Optional[str]]:
    """
    识别两列模式的列（oe, brand）

    Returns:
        (oe_col, brand_col)
    """
    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))

    oe_col = None
    brand_col = None

    for key in OE_COLUMN_CANDIDATES:
        if key.lower() in columns_lower:
            oe_col = column_mapping[key.lower()]
            break

    for key in BRAND_COLUMN_CANDIDATES:
        if key.lower() in columns_lower:
            brand_col = column_mapping[key.lower()]
            break

    return oe_col, brand_col


def identify_columns_extended(df) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    识别三列模式的列（oe, brand, brand_code）

    Returns:
        (oe_col, brand_col, brand_code_col)
    """
    oe_col, brand_col = identify_columns(df)

    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))

    brand_code_col = None
    for key in BRAND_CODE_COLUMN_CANDIDATES:
        if key.lower() in columns_lower:
            brand_code_col = column_mapping[key.lower()]
            break

    return oe_col, brand_col, brand_code_col


def read_excel_file(file_path: str) -> Dict[str, pd.DataFrame]:
    """
    读取 Excel 或 CSV 文件

    Args:
        file_path: 文件路径

    Returns:
        {sheet_name: DataFrame}
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if file_path.endswith('.csv'):
        return {'Sheet1': pd.read_csv(file_path, dtype=str)}

    return pd.read_excel(file_path, sheet_name=None, dtype=str)


def filter_sheets_by_mode(all_sheets: Dict[str, pd.DataFrame], mode: str) -> Dict[str, dict]:
    """
    根据处理模式筛选符合条件的工作表

    Args:
        all_sheets: {sheet_name: DataFrame}
        mode: two_column 或 three_column

    Returns:
        {sheet_name: {'df': DataFrame, 'columns': (oe_col, brand_col, ...)}}
    """
    valid_sheets = {}

    for sheet_name, df in all_sheets.items():
        try:
            if mode == MODE_TWO_COLUMN:
                oe_col, brand_col = identify_columns(df)
                if oe_col and brand_col:
                    valid_sheets[sheet_name] = {
                        'df': df,
                        'columns': (oe_col, brand_col)
                    }
            else:  # three_column
                oe_col, brand_col, brand_code_col = identify_columns_extended(df)
                if oe_col and brand_col and brand_code_col:
                    valid_sheets[sheet_name] = {
                        'df': df,
                        'columns': (oe_col, brand_col, brand_code_col)
                    }
        except Exception:
            continue

    return valid_sheets


def build_items(df: pd.DataFrame, columns: Tuple[str, ...], mode: str) -> List[dict]:
    """
    根据列信息和模式构建 item 列表

    Args:
        df: DataFrame
        columns: (oe_col, brand_col) 或 (oe_col, brand_col, brand_code_col)
        mode: two_column 或 three_column

    Returns:
        item 列表
    """
    oe_col = columns[0]
    brand_col = columns[1]

    items = []
    for _, row in df.iterrows():
        oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''

        if not oe or not brand:
            continue

        item = {
            'oe_number': oe,
            'brand': brand,
            'mode': mode
        }

        if mode == MODE_THREE_COLUMN and len(columns) > 2:
            brand_code_col = columns[2]
            brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
            item['brand_code'] = brand_code

        items.append(item)

    return items
