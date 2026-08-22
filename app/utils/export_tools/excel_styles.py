# -*- coding:utf-8 -*-
"""
比价模块统一 Excel 样式规范

抽取自 purchase_history_excel_writer.py 的成熟样式，供比价模块所有导出点复用，
确保视觉呈现、布局结构和格式标准一致。

使用方式：
    from app.utils.export_tools.excel_styles import apply_uniform_style

    # pandas 写入后应用统一样式
    df.to_excel(writer, index=False, sheet_name='比价数据')
    worksheet = writer.sheets['比价数据']
    apply_uniform_style(worksheet)
"""

from typing import Optional

from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


# ── 统一样式常量 ──

# 表头：微软雅黑、11号、白色粗体、蓝色背景、居中、自动换行
HEADER_FONT = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="0070C0", end_color="0070C0", fill_type="solid")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
HEADER_BORDER = Border(bottom=Side(style="thin"))
HEADER_HEIGHT = 30

# 数据行：微软雅黑、10号、深灰色、底部细边框
DATA_FONT = Font(name="微软雅黑", size=10, color="333333")
DATA_BORDER = Border(bottom=Side(style="thin"))
DATA_HEIGHT = 20

# 交替行填充色（偶数行浅蓝）
ALT_FILL = PatternFill(start_color="EBF1F8", end_color="EBF1F8", fill_type="solid")


def apply_header_style(
    worksheet: Worksheet,
    header_row: int = 1,
    start_col: int = 1,
    end_col: Optional[int] = None,
) -> None:
    """
    为表头行应用统一样式。

    Args:
        worksheet: openpyxl 工作表对象
        header_row: 表头所在行号，默认第 1 行
        start_col: 起始列号
        end_col: 结束列号，默认使用工作表最大列
    """
    if end_col is None:
        end_col = worksheet.max_column

    for col_idx in range(start_col, end_col + 1):
        cell = worksheet.cell(row=header_row, column=col_idx)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGN
        cell.border = HEADER_BORDER

    worksheet.row_dimensions[header_row].height = HEADER_HEIGHT


def apply_data_style(
    worksheet: Worksheet,
    data_start_row: int = 2,
    start_col: int = 1,
    end_col: Optional[int] = None,
    apply_alt_fill: bool = True,
) -> None:
    """
    为数据行应用统一样式。

    Args:
        worksheet: openpyxl 工作表对象
        data_start_row: 数据起始行号
        start_col: 起始列号
        end_col: 结束列号，默认使用工作表最大列
        apply_alt_fill: 是否应用交替行填色
    """
    if end_col is None:
        end_col = worksheet.max_column

    for row_idx in range(data_start_row, worksheet.max_row + 1):
        for col_idx in range(start_col, end_col + 1):
            cell = worksheet.cell(row=row_idx, column=col_idx)
            cell.font = DATA_FONT
            cell.border = DATA_BORDER
            cell.alignment = Alignment(vertical="center")

            if apply_alt_fill and row_idx % 2 == 0:
                cell.fill = ALT_FILL

        worksheet.row_dimensions[row_idx].height = DATA_HEIGHT


def apply_freeze_panes(worksheet: Worksheet, header_row: int = 1) -> None:
    """冻结表头下方的首行数据。"""
    worksheet.freeze_panes = f"A{header_row + 1}"


def apply_auto_filter(
    worksheet: Worksheet,
    header_row: int = 1,
    data_start_row: int = 2,
) -> None:
    """为表头和数据范围添加自动筛选。"""
    if worksheet.max_row < header_row:
        return

    last_col = get_column_letter(worksheet.max_column)
    last_row = max(worksheet.max_row, data_start_row - 1)
    worksheet.auto_filter.ref = f"A{header_row}:{last_col}{last_row}"


def apply_uniform_style(
    worksheet: Worksheet,
    header_row: int = 1,
    data_start_row: int = 2,
    freeze_header: bool = True,
    auto_filter: bool = True,
    apply_alt_fill: bool = True,
) -> None:
    """
    一次性应用比价模块统一 Excel 样式。

    包含：表头样式、数据行样式、交替行填色、冻结首行、自动筛选。

    Args:
        worksheet: openpyxl 工作表对象
        header_row: 表头行号
        data_start_row: 数据起始行号
        freeze_header: 是否冻结表头
        auto_filter: 是否添加自动筛选
        apply_alt_fill: 是否应用交替行填色
    """
    apply_header_style(worksheet, header_row=header_row)
    apply_data_style(
        worksheet,
        data_start_row=data_start_row,
        apply_alt_fill=apply_alt_fill,
    )

    if freeze_header:
        apply_freeze_panes(worksheet, header_row=header_row)

    if auto_filter:
        apply_auto_filter(worksheet, header_row=header_row, data_start_row=data_start_row)
