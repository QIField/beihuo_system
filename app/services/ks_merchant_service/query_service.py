"""
开思商家数据查询服务

提供数据查询的业务逻辑
"""

from typing import Dict, Any, List
from datetime import datetime

from app.models.ks_merchant_models import (
    ShopEventSummaryModel,
    ShopEventDetailModel,
    ShopBusinessIndicatorModel,
)


class KsMerchantQueryService:
    """开思商家数据查询服务"""
    
    def __init__(self):
        self.summary_model = ShopEventSummaryModel()
        self.detail_model = ShopEventDetailModel()
        self.indicator_model = ShopBusinessIndicatorModel()
    
    def get_data_by_date(self, date: str) -> Dict[str, Any]:
        """
        根据日期获取所有数据
        
        Args:
            date: 日期字符串 YYYY-MM-DD
            
        Returns:
            包含 summary、details、indicators 的字典
        """
        # 验证日期格式
        datetime.strptime(date, '%Y-%m-%d')
        
        summary = self.summary_model.get_by_date(date)
        details = self.detail_model.get_by_date(date)
        indicator = self.indicator_model.get_by_date(date)
        
        return {
            "summary": summary,
            "details": details,
            "indicators": indicator
        }
    
    def get_data_by_range(self, start_date: str, end_date: str) -> Dict[str, List]:
        """
        根据日期范围获取数据
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            
        Returns:
            包含 summary、details、indicators 列表的字典
        """
        # 验证日期格式
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
        
        summary_list = self.summary_model.get_by_date_range(start_date, end_date)
        detail_list = self.detail_model.get_by_date_range(start_date, end_date)
        indicator_list = self.indicator_model.get_by_date_range(start_date, end_date)
        
        return {
            "summary": summary_list,
            "details": detail_list,
            "indicators": indicator_list
        }
