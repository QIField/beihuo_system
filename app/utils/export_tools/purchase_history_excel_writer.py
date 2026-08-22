"""
采购历史比对Excel写入工具

用于生成带有月份批注的比价结果Excel。
零模板依赖，所有列与样式通过代码声明式配置。
样式复用比价模块统一规范（app.utils.export_tools.excel_styles）。
"""

from typing import List, Callable, Any
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from app.models.purchase_history_compare_models import OECompareResult
from .excel_styles import (
    HEADER_FONT,
    HEADER_FILL,
    HEADER_ALIGN,
    HEADER_BORDER,
    HEADER_HEIGHT,
    DATA_FONT,
    DATA_BORDER,
    DATA_HEIGHT,
    ALT_FILL,
    apply_freeze_panes,
)


def _format_sales_data(result: OECompareResult) -> str:
    """格式化销量数据字符串"""
    today = result.sales_today if result.sales_today is not None else 0
    yesterday = result.sales_yesterday if result.sales_yesterday is not None else 0
    sales_7d = result.sales_7d if result.sales_7d is not None else 0
    sales_month = result.sales_month if result.sales_month is not None else 0
    sales_6m = result.sales_6m if result.sales_6m is not None else 0
    sales_12m = result.sales_12m if result.sales_12m is not None else 0
    return f"今/昨/近7天: {today}/{yesterday}/{sales_7d}\n近1/6/12月: {sales_month}/{sales_6m}/{sales_12m}"


# ── 列声明配置 ──
# 增加字段只需在此列表追加一行，无需修改模板
_COLUMN_SPECS: List[dict] = [
    {"title": "序号",          "width": 8,  "align": "center", "merge": True,
     "getter": lambda r, idx: idx},
    {"title": "原oe/品牌号",   "width": 15, "align": "center", "merge": True,
     "getter": lambda r, idx: r.brand_code if r.brand_code else r.search_oe},
    {"title": "原品牌",        "width": 12, "align": "center", "merge": True,
     "getter": lambda r, idx: r.search_brand or ""},
    {"title": "oe",            "width": 15, "align": "center",
     "getter": lambda r, idx: r.oe},
    {"title": "价格/促销价",    "width": 12, "align": "right",
     "getter": lambda r, idx: r.price if r.price is not None else ""},
    {"title": "4s含税进价",     "width": 14, "align": "right",
     "getter": lambda r, idx: r.price_4s_cost if r.price_4s_cost is not None else ""},
    {"title": "4s含税售价",     "width": 14, "align": "right",
     "getter": lambda r, idx: r.price_4s_sale if r.price_4s_sale is not None else ""},
    {"title": "品牌",          "width": 12, "align": "left",
     "getter": lambda r, idx: r.brand or ""},
    {"title": "名称",          "width": 22, "align": "left",
     "getter": lambda r, idx: r.product_name or ""},
    {"title": "规格",          "width": 50, "align": "left",
     "getter": lambda r, idx: r.spec or ""},
    {"title": "替换号",        "width": 15, "align": "center",
     "getter": lambda r, idx: r.replace_name or ""},
    {"title": "库存数量",       "width": 11, "align": "right",
     "getter": lambda r, idx: r.stock_quantity if r.stock_quantity is not None else ""},
    {"title": "替换号有库存",   "width": 16, "align": "left",
     "getter": lambda r, idx: r.replace_stock_text or ""},
    {"title": "标签",          "width": 8,  "align": "center",
     "getter": lambda r, idx: r.tag or ""},
    {"title": "近1个月询价量",   "width": 17, "align": "right",
     "getter": lambda r, idx: r.inquiry_1m if r.inquiry_1m is not None else ""},
    {"title": "近3个月月均询价量", "width": 21, "align": "right",
     "getter": lambda r, idx: r.inquiry_3m_avg if r.inquiry_3m_avg is not None else ""},
    {"title": "近6个月月均销量",  "width": 19, "align": "right",
     "getter": lambda r, idx: r.sales_6m_avg if r.sales_6m_avg is not None else ""},
    {"title": "全国近1个月询价量", "width": 21, "align": "right",
     "getter": lambda r, idx: r.inquiry_1m_national if r.inquiry_1m_national is not None else ""},
    {"title": "全国近3个月月均询价量", "width": 26, "align": "right",
     "getter": lambda r, idx: r.inquiry_3m_avg_national if r.inquiry_3m_avg_national is not None else ""},
    {"title": "销量数据",       "width": 44, "align": "left",
     "getter": lambda r, idx: _format_sales_data(r)},
    {"title": "最低价",         "width": 39, "align": "left",
     "getter": lambda r, idx: r.get_overall_lowest_text() if r.overall_lowest and r.overall_lowest[0] else ""},
    {"title": "最高价",         "width": 40, "align": "left",
     "getter": lambda r, idx: r.get_overall_highest_text() if r.overall_highest and r.overall_highest[0] else ""},
]

# 追加 1-12 月列
_MONTH_TITLES = ["一月", "二月", "三月", "四月", "五月", "六月",
                 "七月", "八月", "九月", "十月", "十一月", "十二月"]
for _mi, _mt in enumerate(_MONTH_TITLES, 1):
    _COLUMN_SPECS.append({
        "title": _mt,
        "width": 9 if _mi == 11 else 8,
        "align": "right",
        "month": _mi,
    })


class PurchaseHistoryExcelWriter:
    """采购历史比对Excel写入器（零模板依赖）"""

    TAG_PRIORITY_ORDER = ["A类", "B类", "C类", "D类"]

    def __init__(self):
        """初始化：从零创建工作簿并写入表头"""
        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = "Sheet1"
        self._build_header()

    def _build_header(self):
        """创建表头并应用统一表头样式"""
        for col_idx, spec in enumerate(_COLUMN_SPECS, 1):
            cell = self.ws.cell(row=1, column=col_idx, value=spec["title"])
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = HEADER_ALIGN
            cell.border = HEADER_BORDER
        self.ws.row_dimensions[1].height = HEADER_HEIGHT
        apply_freeze_panes(self.ws, header_row=1)

    def write_compare_results(self, results: List[OECompareResult], start_row: int = 2):
        """
        写入比对结果到Excel
        流程：写数据 → 合并单元格 → 按行交替填色
        """
        print(f"[Excel写入] 步骤1-开始: 共 {len(results)} 条结果待写入，起始行={start_row}")
        self._normalize_group_tags(results)

        current_row = start_row
        group_row_ranges = {}

        for result in results:
            group_index = result.group_index if result.group_index is not None else current_row - start_row + 1
            if group_index not in group_row_ranges:
                group_row_ranges[group_index] = [current_row, current_row]
            else:
                group_row_ranges[group_index][1] = current_row

            is_bc_item = (
                result.search_oe
                and result.oe == result.search_oe
                and not result.product_name
                and not result.brand
                and not result.frey_no
                and not result.month_summaries
            ) or (
                result.search_oe
                and any(c in str(result.search_oe) for c in ' .,/')
            )
            bc_tag = "[brand_code空行]" if is_bc_item else ""
            print(f"[Excel写入] 步骤2-写入行: row={current_row}, group={group_index}, "
                  f"search_oe={result.search_oe!r}, oe={result.oe!r}, brand={result.brand!r}, "
                  f"product_name={(result.product_name or '')!r}, 4S进价={result.price_4s_cost}, "
                  f"4S售价={result.price_4s_sale} {bc_tag}")

            self._write_row(result, current_row, group_index)
            current_row += 1

        print(f"[Excel写入] 步骤2-写入行完成: 共写入 {current_row - start_row} 行数据，组数={len(group_row_ranges)}")

        self._merge_group_cells(group_row_ranges)
        self._apply_alternating_fill(start_row, current_row - 1)

        # 添加自动筛选（表头+数据范围）
        last_col = get_column_letter(len(_COLUMN_SPECS))
        last_row = current_row - 1 if current_row > start_row else 1
        self.ws.auto_filter.ref = f"A1:{last_col}{last_row}"

        print(f"[Excel写入] 步骤3-样式处理完成")

    def _normalize_group_tags(self, results: List[OECompareResult]):
        """按组统一标签优先级（A类>B类>C类>D类）"""
        group_tags = {}
        for result in results:
            gi = result.group_index if result.group_index is not None else 0
            if gi not in group_tags:
                group_tags[gi] = []
            if result.tag:
                group_tags[gi].append(result.tag)
        for result in results:
            gi = result.group_index if result.group_index is not None else 0
            tags = group_tags.get(gi, [])
            for priority_tag in self.TAG_PRIORITY_ORDER:
                if priority_tag in tags:
                    result.tag = priority_tag
                    break

    def _write_row(self, result: OECompareResult, row: int, index: int):
        """写入单行数据"""
        for col_idx, spec in enumerate(_COLUMN_SPECS, 1):
            cell = self.ws.cell(row=row, column=col_idx)
            self._apply_data_style(cell, spec)

            month = spec.get("month")
            if month:
                self._write_month_cell(cell, result, month)
            else:
                getter: Callable[[OECompareResult, int], Any] = spec["getter"]
                cell.value = getter(result, index)

        self.ws.row_dimensions[row].height = DATA_HEIGHT

    def _apply_data_style(self, cell, spec: dict):
        """应用数据行基础样式"""
        cell.font = DATA_FONT
        cell.border = DATA_BORDER
        align = spec["align"]
        wrap = spec["title"] in ("销量数据", "替换号有库存")
        cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)

    def _write_month_cell(self, cell, result: OECompareResult, month: int):
        """写入月份单元格（含最低价与批注）"""
        summary = result.month_summaries.get(month)
        if summary:
            cell.value = summary.lowest_price
            comment_text = summary.get_comment_text()
            if comment_text:
                cell.comment = Comment(comment_text, "系统")
        else:
            cell.value = ""

    def _merge_group_cells(self, group_row_ranges: dict):
        """合并序号列、原oe/品牌号列、原品牌列"""
        merge_cols = [1, 2, 3]  # A列(序号), B列(原oe/品牌号), C列(原品牌)
        for start, end in group_row_ranges.values():
            if start < end:
                for col in merge_cols:
                    self.ws.merge_cells(start_row=start, start_column=col,
                                        end_row=end, end_column=col)
                    merged_cell = self.ws.cell(row=start, column=col)
                    merged_cell.alignment = Alignment(horizontal="center", vertical="center")
        print(f"[Excel写入] 步骤2-合并单元格完成")

    def _apply_alternating_fill(self, start_row: int, end_row: int):
        """按行号交替填色（偶数行浅蓝，奇数行白色）"""
        for row in range(start_row, end_row + 1):
            if row % 2 == 0:
                for col_idx in range(1, len(_COLUMN_SPECS) + 1):
                    self.ws.cell(row=row, column=col_idx).fill = ALT_FILL

    def set_column_widths(self):
        """根据列配置设置列宽"""
        for col_idx, spec in enumerate(_COLUMN_SPECS, 1):
            letter = get_column_letter(col_idx)
            self.ws.column_dimensions[letter].width = spec["width"]
        print(f"[Excel写入] 步骤3-设置列宽完成")

    def save(self, output_path: str):
        """保存文件到指定路径"""
        print(f"[Excel写入] 步骤4-保存文件: 路径={output_path}")
        try:
            self.wb.save(output_path)
            import os
            size = os.path.getsize(output_path) if os.path.exists(output_path) else -1
            print(f"[Excel写入] 步骤4-保存文件: 成功，文件大小={size} bytes")
        except Exception as e:
            import traceback
            print(f"[Excel写入] 步骤4-保存文件: 失败，错误={e}\n{traceback.format_exc()}")
            raise

    @staticmethod
    def generate_excel(results: List[OECompareResult], output_path: str):
        """
        静态方法：快速生成Excel文件（无需模板）

        Args:
            results: 比对结果列表
            output_path: 输出文件路径
        """
        print(f"[Excel写入] 步骤0-初始化: 输出={output_path}, 结果数={len(results)}")
        writer = PurchaseHistoryExcelWriter()
        writer.write_compare_results(results)
        print(f"[Excel写入] 步骤3-设置列宽")
        writer.set_column_widths()
        writer.save(output_path)
        return output_path
