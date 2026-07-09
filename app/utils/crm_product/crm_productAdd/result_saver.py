"""
结果保存模块

职责：
- 把处理结果写入 Excel 文件
- 支持单工作表和多工作表
"""

import os
from datetime import datetime
from typing import Dict

import pandas as pd

from .models import ProcessResult


def _format_result(result) -> str:
    """
    统一把结果格式化为字符串

    支持 ProcessResult 对象或旧版的字符串结果
    """
    if isinstance(result, ProcessResult):
        if result.status == 'success':
            return f"成功 - product_id: {result.product_id}" if result.product_id else f"成功 - {result.message}"
        elif result.status == 'existed':
            return f"已存在 - {result.message}"
        else:
            return f"失败 - {result.message}"
    return str(result)


def _add_result_column(df: pd.DataFrame, results: Dict[str, object], oe_col: str) -> pd.DataFrame:
    """
    在 DataFrame 中添加/填充“新建结果”列
    """
    df['新建结果'] = ''

    for idx, row in df.iterrows():
        oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        if oe in results:
            df.at[idx, '新建结果'] = _format_result(results[oe])

    return df


def save_single_sheet_results(df: pd.DataFrame, results: Dict[str, object], oe_col: str, original_file_path: str) -> str:
    """
    保存单工作表结果
    """
    df = _add_result_column(df, results, oe_col)

    base_name = os.path.splitext(original_file_path)[0]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"{base_name}_处理结果_{timestamp}.xlsx"

    df.to_excel(output_path, index=False)
    print(f"结果已保存: {output_path}")
    return output_path


def save_multi_sheet_results(all_results: Dict[str, dict], original_file_path: str) -> str:
    """
    保存多工作表结果到一个 Excel 文件

    Args:
        all_results: {
            sheet_name: {
                'df': DataFrame,
                'results': {oe: ProcessResult},
                'oe_col': str
            }
        }
        original_file_path: 原始文件路径

    Returns:
        输出文件路径
    """
    base_name = os.path.splitext(original_file_path)[0]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"{base_name}_处理结果_{timestamp}.xlsx"

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, sheet_data in all_results.items():
            df = sheet_data['df'].copy()
            results = sheet_data['results']
            oe_col = sheet_data['oe_col']

            df = _add_result_column(df, results, oe_col)

            safe_sheet_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_sheet_name, index=False)

    print(f"\n结果已保存: {output_path}")
    return output_path
