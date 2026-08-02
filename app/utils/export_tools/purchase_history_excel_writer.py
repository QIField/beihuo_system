"""
采购历史比对Excel写入工具
用于生成带有月份批注的比价结果Excel
"""
from typing import List
from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from app.models.purchase_history_compare_models import OECompareResult


class PurchaseHistoryExcelWriter:
    """采购历史比对Excel写入器"""

    # 列定义（根据模板文件 compare_price.xlsx）
    COL_INDEX = 1              # A列: 序号
    COL_ORIGIN_OE = 2          # B列: 原oe（主号，同一组合并）
    COL_OE = 3                 # C列: oe
    COL_PRICE = 4              # D列: 价格/促销价
    COL_4S_COST = 5            # E列: 4s含税进价
    COL_4S_PRICE = 6           # F列: 4s含税售价
    COL_BRAND = 7              # G列: 品牌
    COL_NAME = 8               # H列: 名称
    COL_SPEC = 9               # I列: 规格
    COL_REPLACE = 10           # J列: 替换号
    COL_STOCK = 11             # K列: 库存数量
    COL_REPLACE_STOCK = 12     # L列: 替换号有库存
    COL_TAG = 13               # M列: 标签
    COL_INQUIRY_1M = 14        # N列: 近1个月询价量
    COL_INQUIRY_3M = 15        # O列: 近3个月月均询价量
    COL_SALES_6M_AVG = 16      # P列: 近6个月月均销量
    COL_INQUIRY_1M_NATIONAL = 17   # Q列: 全国近1个月询价量
    COL_INQUIRY_3M_NATIONAL = 18   # R列: 全国近3个月月均询价量
    COL_SALES_DATA = 19        # S列: 销量数据(合并列)
    COL_LOWEST = 20            # T列: 最低价
    COL_HIGHEST = 21           # U列: 最高价
    COL_JAN = 22               # V列: 一月
    COL_FEB = 23               # W列: 二月
    COL_MAR = 24               # X列: 三月
    COL_APR = 25               # Y列: 四月
    COL_MAY = 26               # Z列: 五月
    COL_JUN = 27               # AA列: 六月
    COL_JUL = 28               # AB列: 七月
    COL_AUG = 29               # AC列: 八月
    COL_SEP = 30               # AD列: 九月
    COL_OCT = 31               # AE列: 十月
    COL_NOV = 32               # AF列: 十一月
    COL_DEC = 33               # AG列: 十二月

    # 月份列映射
    MONTH_COLS = {
        1: COL_JAN,
        2: COL_FEB,
        3: COL_MAR,
        4: COL_APR,
        5: COL_MAY,
        6: COL_JUN,
        7: COL_JUL,
        8: COL_AUG,
        9: COL_SEP,
        10: COL_OCT,
        11: COL_NOV,
        12: COL_DEC,
    }

    def __init__(self, template_path: str):
        """
        初始化Excel写入器

        Args:
            template_path: 模板文件路径
        """
        self.wb = load_workbook(template_path)
        self.ws = self.wb.active

    # 标签优先级：A类 > B类 > C类 > D类
    TAG_PRIORITY_ORDER = ["A类", "B类", "C类", "D类"]

    def write_compare_results(self, results: List[OECompareResult], start_row: int = 2):
        """
        写入比对结果到Excel

        Args:
            results: 比对结果列表
            start_row: 开始写入的行号，默认从第2行开始（第1行为表头）
        """
        print(f"[Excel写入] 步骤1-开始: 共 {len(results)} 条结果待写入，起始行={start_row}")
        # 预处理：按组统一标签优先级（A类>B类>C类>D类）
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

        current_row = start_row
        group_row_ranges = {}  # group_index -> (start_row, end_row)

        # Excel "白色 背景1，深色25%" = #BFBFBF
        alternate_fill = PatternFill(start_color='BFBFBF', end_color='BFBFBF', fill_type='solid')

        for result in results:
            # 使用组号作为序号，主号+replace_number匹配行共享同一序号
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
                and not result.records
            ) or (
                result.search_oe
                and any(c in str(result.search_oe) for c in ' .,/')
            )
            bc_tag = "[brand_code空行]" if is_bc_item else ""
            print(f"[Excel写入] 步骤2-写入行: row={current_row}, group={group_index}, search_oe={result.search_oe!r}, oe={result.oe!r}, brand={result.brand!r}, product_name={(result.product_name or '')!r}, 4S进价={result.price_4s_cost}, 4S售价={result.price_4s_sale} {bc_tag}")
            self._write_oe_result(result, current_row, group_index)

            # 偶数组（第2、4、6...组）设置交替背景色
            if group_index % 2 == 0:
                for col in range(1, 34):  # A到AG列
                    self.ws.cell(row=current_row, column=col).fill = alternate_fill

            current_row += 1

        print(f"[Excel写入] 步骤2-写入行完成: 共写入 {current_row - start_row} 行数据，组数={len(group_row_ranges)}")
        # 合并序号列和原oe列：同一组的多行纵向合并并垂直居中
        for start, end in group_row_ranges.values():
            if start < end:
                self.ws.merge_cells(start_row=start, start_column=self.COL_INDEX,
                                    end_row=end, end_column=self.COL_INDEX)
                merged_cell = self.ws.cell(row=start, column=self.COL_INDEX)
                merged_cell.alignment = Alignment(vertical='center')

                self.ws.merge_cells(start_row=start, start_column=self.COL_ORIGIN_OE,
                                    end_row=end, end_column=self.COL_ORIGIN_OE)
                merged_cell_oe = self.ws.cell(row=start, column=self.COL_ORIGIN_OE)
                merged_cell_oe.alignment = Alignment(vertical='center')
        print(f"[Excel写入] 步骤2-合并单元格完成")

    def _write_oe_result(self, result: OECompareResult, row: int, index: int):
        """
        写入单个OE的比对结果

        Args:
            result: 单个OE的比对结果
            row: 写入的行号
            index: 序号（组号）
        """
        # 写入序号（组号）
        self.ws.cell(row=row, column=self.COL_INDEX, value=index)

        # 写入原oe（主号，同一组共享）
        self.ws.cell(row=row, column=self.COL_ORIGIN_OE, value=result.search_oe)

        # 写入OE号（replace_number匹配时显示compare_summary.oe）
        self.ws.cell(row=row, column=self.COL_OE, value=result.oe)

        # 写入价格/促销价（从导入文件读取）
        price_cell = self.ws.cell(row=row, column=self.COL_PRICE)
        if result.price is not None:
            price_cell.value = result.price
        else:
            price_cell.value = ""

        # 写入4S价格（查不到时保持为空）
        cost_cell = self.ws.cell(row=row, column=self.COL_4S_COST)
        if result.price_4s_cost is not None:
            cost_cell.value = result.price_4s_cost
        else:
            cost_cell.value = ""

        sale_cell = self.ws.cell(row=row, column=self.COL_4S_PRICE)
        if result.price_4s_sale is not None:
            sale_cell.value = result.price_4s_sale
        else:
            sale_cell.value = ""

        # 写入品牌
        self.ws.cell(row=row, column=self.COL_BRAND, value=result.brand)

        # 写入产品信息（名称、规格、替换号）
        name_cell = self.ws.cell(row=row, column=self.COL_NAME)
        name_cell.value = result.product_name if result.product_name else ""

        spec_cell = self.ws.cell(row=row, column=self.COL_SPEC)
        spec_cell.value = result.spec if result.spec else ""

        replace_cell = self.ws.cell(row=row, column=self.COL_REPLACE)
        replace_cell.value = result.replace_name if result.replace_name else ""

        # 写入备货数据（从crmapp_beihuo表获取）
        # J列: 库存数量
        stock_cell = self.ws.cell(row=row, column=self.COL_STOCK)
        stock_cell.value = result.stock_quantity if result.stock_quantity is not None else ""

        # K列: 替换号有库存
        replace_stock_cell = self.ws.cell(row=row, column=self.COL_REPLACE_STOCK)
        replace_stock_cell.value = result.replace_stock_text if result.replace_stock_text else ""
        replace_stock_cell.alignment = Alignment(wrap_text=True, vertical='center')

        # L列: 标签
        tag_cell = self.ws.cell(row=row, column=self.COL_TAG)
        tag_cell.value = result.tag if result.tag else ""

        # M列: 近1个月询价量
        inquiry_1m_cell = self.ws.cell(row=row, column=self.COL_INQUIRY_1M)
        inquiry_1m_cell.value = result.inquiry_1m if result.inquiry_1m is not None else ""

        # N列: 近3个月月均询价量
        inquiry_3m_cell = self.ws.cell(row=row, column=self.COL_INQUIRY_3M)
        inquiry_3m_cell.value = result.inquiry_3m_avg if result.inquiry_3m_avg is not None else ""

        # O列: 近6个月月均销量
        sales_6m_avg_cell = self.ws.cell(row=row, column=self.COL_SALES_6M_AVG)
        sales_6m_avg_cell.value = result.sales_6m_avg if result.sales_6m_avg is not None else ""

        # P列: 全国近1个月询价量
        inquiry_1m_national_cell = self.ws.cell(row=row, column=self.COL_INQUIRY_1M_NATIONAL)
        inquiry_1m_national_cell.value = result.inquiry_1m_national if result.inquiry_1m_national is not None else ""

        # Q列: 全国近3个月月均询价量
        inquiry_3m_national_cell = self.ws.cell(row=row, column=self.COL_INQUIRY_3M_NATIONAL)
        inquiry_3m_national_cell.value = result.inquiry_3m_avg_national if result.inquiry_3m_avg_national is not None else ""

        # R列: 销量数据(合并列)
        # 格式: 今/昨/近7天: {今日销量}/{昨日销量}/{近7天销量}
        #       近1/6/12月: {本月销量}/{近6个月销量}/{近12个月销量}
        sales_data_cell = self.ws.cell(row=row, column=self.COL_SALES_DATA)
        today = result.sales_today if result.sales_today is not None else 0
        yesterday = result.sales_yesterday if result.sales_yesterday is not None else 0
        sales_7d = result.sales_7d if result.sales_7d is not None else 0
        sales_month = result.sales_month if result.sales_month is not None else 0
        sales_6m = result.sales_6m if result.sales_6m is not None else 0
        sales_12m = result.sales_12m if result.sales_12m is not None else 0
        sales_data_cell.value = f"今/昨/近7天: {today}/{yesterday}/{sales_7d}\n近1/6/12月: {sales_month}/{sales_6m}/{sales_12m}"
        sales_data_cell.alignment = Alignment(wrap_text=True, vertical='center')

        # 写入1-12月数据
        for month in range(1, 13):
            col = self.MONTH_COLS[month]
            cell = self.ws.cell(row=row, column=col)

            summary = result.month_summaries.get(month)
            if summary:
                # 写入最低价
                cell.value = summary.lowest_price

                # 添加批注（所有记录，按价格排序）
                comment_text = summary.get_comment_text()
                if comment_text:
                    comment = Comment(comment_text, "系统")
                    cell.comment = comment
            else:
                # 无数据时写入空值或0
                cell.value = ""

        # 写入最低价列
        lowest_cell = self.ws.cell(row=row, column=self.COL_LOWEST)
        if result.overall_lowest and result.overall_lowest[0]:
            lowest_cell.value = result.get_overall_lowest_text()
        else:
            lowest_cell.value = ""

        # 写入最高价列
        highest_cell = self.ws.cell(row=row, column=self.COL_HIGHEST)
        if result.overall_highest and result.overall_highest[0]:
            highest_cell.value = result.get_overall_highest_text()
        else:
            highest_cell.value = ""

    def set_column_widths(self):
        """设置列宽"""
        # 序号列
        self.ws.column_dimensions['A'].width = 8
        # 原oe列
        self.ws.column_dimensions['B'].width = 20
        # OE号列
        self.ws.column_dimensions['C'].width = 20
        # 价格列
        self.ws.column_dimensions['D'].width = 15
        # 4s价格列
        self.ws.column_dimensions['E'].width = 15
        self.ws.column_dimensions['F'].width = 15
        # 品牌列
        self.ws.column_dimensions['G'].width = 15
        # 名称、规格、替换号列
        self.ws.column_dimensions['H'].width = 20
        self.ws.column_dimensions['I'].width = 15
        self.ws.column_dimensions['J'].width = 20
        # 备货相关列
        self.ws.column_dimensions['K'].width = 12  # 库存数量
        self.ws.column_dimensions['L'].width = 25  # 替换号有库存
        self.ws.column_dimensions['M'].width = 15  # 标签
        self.ws.column_dimensions['N'].width = 15  # 近1个月询价量
        self.ws.column_dimensions['O'].width = 18  # 近3个月月均询价量
        self.ws.column_dimensions['P'].width = 18  # 近6个月月均销量
        self.ws.column_dimensions['Q'].width = 18  # 全国近1个月询价量
        self.ws.column_dimensions['R'].width = 20  # 全国近3个月月均询价量
        self.ws.column_dimensions['S'].width = 20  # 销量数据(合并列)
        # 最低价最高价列
        self.ws.column_dimensions['T'].width = 30
        self.ws.column_dimensions['U'].width = 30
        # 月份列 (V-AG)
        for col_letter in ['V', 'W', 'X', 'Y', 'Z', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG']:
            self.ws.column_dimensions[col_letter].width = 12

    def save(self, output_path: str):
        """
        保存文件到指定路径

        Args:
            output_path: 输出文件路径
        """
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
    def generate_excel(results: List[OECompareResult], template_path: str, output_path: str):
        """
        静态方法：快速生成Excel文件

        Args:
            results: 比对结果列表
            template_path: 模板文件路径
            output_path: 输出文件路径
        """
        print(f"[Excel写入] 步骤0-初始化: 模板={template_path}, 输出={output_path}, 结果数={len(results)}")
        writer = PurchaseHistoryExcelWriter(template_path)
        writer.write_compare_results(results)
        print(f"[Excel写入] 步骤3-设置列宽")
        writer.set_column_widths()
        writer.save(output_path)
        return output_path
