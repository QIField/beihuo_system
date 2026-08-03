"""
采购历史比对结果数据模型
"""
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional


@dataclass
class PurchaseRecord:
    """单条采购记录"""
    year: int
    month: int
    supplier: str
    price: float
    
    def __post_init__(self):
        """初始化后处理，确保数据类型正确"""
        self.year = int(self.year)
        self.month = int(self.month)
        self.price = float(self.price)


@dataclass
class MonthSummary:
    """月份汇总数据"""
    month: int                                    # 月份 1-12
    lowest_price: float                           # 该月最低价
    all_records: List[PurchaseRecord]             # 该月所有记录（已按价格从低到高排序）
    
    def __post_init__(self):
        """初始化后处理，按价格排序所有记录"""
        self.month = int(self.month)
        self.lowest_price = float(self.lowest_price)
        # 按价格从低到高排序
        self.all_records = sorted(
            self.all_records, 
            key=lambda x: x.price
        )
    
    def get_comment_text(self) -> str:
        """
        生成批注文本
        格式：
        2025年，万拓，255
        2024年，德孚，260
        """
        lines = []
        for record in self.all_records:
            line = f"{record.year}年，{record.supplier}，{record.price}"
            lines.append(line)
        return "\n".join(lines)


@dataclass
class OECompareResult:
    """单个OE的比对结果"""
    oe: str                                       # 显示在表格中的OE号（replace_number匹配时使用compare_summary.oe）
    search_oe: str                                # 原始搜索OE号（用于兆配云查询）
    brand: str                                    # 人工输入的品牌
    month_summaries: Dict[int, MonthSummary]      # 1-12月汇总数据，key为月份(1-12)
    overall_lowest: Tuple[str, str, float]        # 整体最低价 (年月, 供应商, 价格)
    overall_highest: Tuple[str, str, float]       # 整体最高价 (年月, 供应商, 价格)
    price_4s_cost: Optional[float] = None         # 4S含税进价
    price_4s_sale: Optional[float] = None         # 4S含税售价
    product_name: Optional[str] = None            # 名称
    spec: Optional[str] = None                    # 规格
    replace_name: Optional[str] = None            # 替换号
    price: Optional[float] = None                 # 价格/促销价（从导入文件读取）
    frey_no: Optional[str] = None                 # Frey编号（从crmapp_compare_summary获取）
    replace_stock_text: Optional[str] = None      # 替换号有库存文本
    group_index: Optional[int] = None             # 组号（主号+replace_number匹配行共享同一组号）
    search_brand: Optional[str] = None            # 原始搜索品牌（从上传文件读取）
    brand_code: Optional[str] = None              # 品牌号（当使用品牌号搜索时）

    # 从crmapp_beihuo表获取的字段
    stock_quantity: Optional[int] = None          # 库存数量
    tag: Optional[str] = None                     # 标签
    inquiry_1m: Optional[int] = None              # 近1个月询价量
    inquiry_3m_avg: Optional[int] = None          # 近3个月月均询价量
    sales_6m_avg: Optional[int] = None            # 近6个月月均销量
    inquiry_1m_national: Optional[int] = None     # 全国近1个月询价量
    inquiry_3m_avg_national: Optional[int] = None # 全国近3个月月均询价量
    
    # 销量数据（用于合并列显示）
    sales_today: Optional[int] = None             # 今日销量
    sales_yesterday: Optional[int] = None         # 昨日销量
    sales_7d: Optional[int] = None                # 近7天销量
    sales_month: Optional[int] = None             # 本月销量
    sales_6m: Optional[int] = None                # 近6个月销量
    sales_12m: Optional[int] = None               # 近12个月销量
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保month_summaries的key是整数
        self.month_summaries = {
            int(k): v for k, v in self.month_summaries.items()
        }
    
    def get_month_lowest_price(self, month: int) -> Optional[float]:
        """获取指定月份的最低价"""
        summary = self.month_summaries.get(month)
        return summary.lowest_price if summary else None
    
    def get_month_comment(self, month: int) -> str:
        """获取指定月份的批注文本"""
        summary = self.month_summaries.get(month)
        return summary.get_comment_text() if summary else ""
    
    def get_overall_lowest_text(self) -> str:
        """获取整体最低价文本"""
        year_month, supplier, price = self.overall_lowest
        return f"{year_month}，{supplier}，{price}"
    
    def get_overall_highest_text(self) -> str:
        """获取整体最高价文本"""
        year_month, supplier, price = self.overall_highest
        return f"{year_month}，{supplier}，{price}"
