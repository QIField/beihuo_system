"""
采购历史比对Excel写入工具
用于生成带有月份批注的比价结果Excel
"""
from typing import List
from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, Alignment, Border, Side
from app.models.purchase_history_compare_models import OECompareResult


class PurchaseHistoryExcelWriter:
    """采购历史比对Excel写入器"""
    
    # 列定义（根据模板文件 compare_price.xlsx）
    COL_INDEX = 1        # A列: 序号
    COL_OE = 2           # B列: oe
    COL_PRICE = 3        # C列: 价格/促销价
    COL_BRAND = 4        # D列: 品牌
    COL_NAME = 5         # E列: 名称
    COL_SPEC = 6         # F列: 规格
    COL_REPLACE = 7      # G列: 替换号
    COL_LOWEST = 8       # H列: 最低价
    COL_HIGHEST = 9      # I列: 最高价
    COL_4S_COST = 10     # J列: 4s含税进价
    COL_4S_PRICE = 11    # K列: 4s含税售价
    COL_JAN = 12         # L列: 一月
    COL_FEB = 13         # M列: 二月
    COL_MAR = 14         # N列: 三月
    COL_APR = 15         # O列: 四月
    COL_MAY = 16         # P列: 五月
    COL_JUN = 17         # Q列: 六月
    COL_JUL = 18         # R列: 七月
    COL_AUG = 19         # S列: 八月
    COL_SEP = 20         # T列: 九月
    COL_OCT = 21         # U列: 十月
    COL_NOV = 22         # V列: 十一月
    COL_DEC = 23         # W列: 十二月

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
        
    def write_compare_results(self, results: List[OECompareResult], start_row: int = 2):
        """
        写入比对结果到Excel
        
        Args:
            results: 比对结果列表
            start_row: 开始写入的行号，默认从第2行开始（第1行为表头）
        """
        current_row = start_row
        index = 1  # 序号从1开始
        
        for result in results:
            self._write_oe_result(result, current_row, index)
            current_row += 1
            index += 1
    
    def _write_oe_result(self, result: OECompareResult, row: int, index: int):
        """
        写入单个OE的比对结果
        
        Args:
            result: 单个OE的比对结果
            row: 写入的行号
            index: 序号
        """
        # 写入序号
        self.ws.cell(row=row, column=self.COL_INDEX, value=index)
        
        # 写入OE号
        self.ws.cell(row=row, column=self.COL_OE, value=result.oe)

        # 写入价格/促销价（从导入文件读取）
        price_cell = self.ws.cell(row=row, column=self.COL_PRICE)
        if result.price is not None:
            price_cell.value = result.price
        else:
            price_cell.value = ""

        # 写入品牌
        self.ws.cell(row=row, column=self.COL_BRAND, value=result.brand)

        # 写入产品信息（名称、规格、替换号）
        name_cell = self.ws.cell(row=row, column=self.COL_NAME)
        name_cell.value = result.product_name if result.product_name else ""

        spec_cell = self.ws.cell(row=row, column=self.COL_SPEC)
        spec_cell.value = result.spec if result.spec else ""

        replace_cell = self.ws.cell(row=row, column=self.COL_REPLACE)
        replace_cell.value = result.replace_name if result.replace_name else ""

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
        if result.overall_lowest and result.overall_lowest[2] > 0:
            lowest_cell.value = result.get_overall_lowest_text()
        else:
            lowest_cell.value = ""
        
        # 写入最高价列
        highest_cell = self.ws.cell(row=row, column=self.COL_HIGHEST)
        if result.overall_highest and result.overall_highest[2] > 0:
            highest_cell.value = result.get_overall_highest_text()
        else:
            highest_cell.value = ""
    
    def set_column_widths(self):
        """设置列宽"""
        # 序号列
        self.ws.column_dimensions['A'].width = 8
        # OE号列
        self.ws.column_dimensions['B'].width = 20
        # 价格列
        self.ws.column_dimensions['C'].width = 15
        # 品牌列
        self.ws.column_dimensions['D'].width = 15
        # 名称、规格、替换号列
        self.ws.column_dimensions['E'].width = 20
        self.ws.column_dimensions['F'].width = 15
        self.ws.column_dimensions['G'].width = 20
        # 最低价最高价列
        self.ws.column_dimensions['H'].width = 30
        self.ws.column_dimensions['I'].width = 30
        # 4s价格列
        self.ws.column_dimensions['J'].width = 15
        self.ws.column_dimensions['K'].width = 15
        # 月份列 (L-W)
        for col_letter in ['L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W']:
            self.ws.column_dimensions[col_letter].width = 12
    
    def save(self, output_path: str):
        """
        保存文件到指定路径
        
        Args:
            output_path: 输出文件路径
        """
        self.wb.save(output_path)
    
    @staticmethod
    def generate_excel(results: List[OECompareResult], template_path: str, output_path: str):
        """
        静态方法：快速生成Excel文件
        
        Args:
            results: 比对结果列表
            template_path: 模板文件路径
            output_path: 输出文件路径
        """
        writer = PurchaseHistoryExcelWriter(template_path)
        writer.write_compare_results(results)
        writer.set_column_widths()
        writer.save(output_path)
        return output_path
