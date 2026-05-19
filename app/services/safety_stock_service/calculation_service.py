"""
安全库存计算服务
包含：ABC分类、安全库存计算、季节性调整、库存状态判断
"""

import math
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from .config import ABC_CONFIG, SEASONAL_CONFIG, OVERSTOCK_THRESHOLD, WARNING_DAYS, LEAD_TIME


class SafetyStockCalculator:
    """
    安全库存计算器
    
    功能：
    1. ABC产品分类
    2. 安全库存计算（含季节性调整）
    3. 库存上下限计算
    4. 库存状态判断
    """
    
    def __init__(self):
        self.abc_config = ABC_CONFIG
        self.seasonal_config = SEASONAL_CONFIG
        
    def calculate_abc_class(self, products_sales: List[Dict]) -> Dict[str, str]:
        """
        ABC分类 - 按销量降序排列，分为A(20%)、B(60%)、C(20%)
        
        Args:
            products_sales: 产品销量列表，每项包含 {'frey_no': str, 'total_sales': float}
        
        Returns:
            字典，key为 "frey_no"，value为分类 'A'/'B'/'C'
        """
        if not products_sales:
            return {}
            
        # 按销量降序排序
        sorted_products = sorted(products_sales, key=lambda x: x['total_sales'], reverse=True)
        total = len(sorted_products)
        
        abc_classes = {}
        a_count = int(total * self.abc_config['A']['percent'])
        b_count = int(total * self.abc_config['B']['percent'])
        
        for i, prod in enumerate(sorted_products):
            key = prod['frey_no']
            if i < a_count:
                abc_classes[key] = 'A'
            elif i < a_count + b_count:
                abc_classes[key] = 'B'
            else:
                abc_classes[key] = 'C'
                
        return abc_classes
    
    def calculate_safety_stock(self, avg_daily: float, std_daily: float, abc_class: str, 
                            month: int, monthly_sales: Dict[int, float]) -> Dict[str, float]:
        """
        计算安全库存（含季节性调整）
        
        安全库存公式：SS = Z × σ × √LT
        
        Args:
            avg_daily: 平均日销量
            std_daily: 日销量标准差
            abc_class: ABC分类 ('A'/'B'/'C')
            month: 当前月份(1-12)
            monthly_sales: 各月销量字典 {1:销量, 2:销量...}
        
        Returns:
            包含基础安全库存、季节系数、调整后安全库存的字典
        """
        # 1. 基础安全库存 = Z × σ × √LT
        z_factor = self.abc_config[abc_class]['z_factor']
        base_safety_stock = z_factor * std_daily * math.sqrt(LEAD_TIME)
        
        # 2. 计算季节系数
        seasonal_factor = self._calculate_seasonal_factor(month, monthly_sales)
            
        # 3. 调整后安全库存
        adjusted_safety_stock = base_safety_stock * seasonal_factor
        
        return {
            'base_safety_stock': round(base_safety_stock, 2),
            'seasonal_factor': round(seasonal_factor, 2),
            'safety_stock': round(adjusted_safety_stock, 2)
        }
    
    def _calculate_seasonal_factor(self, month: int, monthly_sales: Dict[int, float]) -> float:
        """
        计算季节系数
        
        Args:
            month: 当前月份(1-12)
            monthly_sales: 各月销量字典
        
        Returns:
            季节系数（0.7-1.3之间）
        """
        if not monthly_sales or len(monthly_sales) < 6:
            # 数据不足，返回中性系数
            return 1.0
            
        # 计算全年平均月销量
        avg_monthly = sum(monthly_sales.values()) / len(monthly_sales)
        if avg_monthly <= 0:
            return 1.0
            
        # 获取当月销量（如果当月无数据，用平均）
        current_month_sales = monthly_sales.get(month, avg_monthly)
        
        # 计算季节系数
        seasonal_factor = current_month_sales / avg_monthly
        
        # 限制在合理范围内
        seasonal_factor = max(
            self.seasonal_config['min_factor'], 
            min(self.seasonal_config['max_factor'], seasonal_factor)
        )
        
        return seasonal_factor
    
    def calculate_stock_limits(self, avg_daily: float, safety_stock: float, abc_class: str) -> Dict[str, float]:
        """
        计算库存上下限
        
        Args:
            avg_daily: 平均日销量
            safety_stock: 安全库存
            abc_class: ABC分类
        
        Returns:
            {'reorder_point': 库存下限, 'target_stock': 库存上限}
        """
        cover_days = self.abc_config[abc_class]['cover_days']
        
        # 库存下限（再订货点）= 平均日销量 × 补货周期 + 安全库存
        reorder_point = avg_daily * LEAD_TIME + safety_stock
        
        # 库存上限（目标库存）= 平均日销量 × (补货周期 + 覆盖天数) + 安全库存
        target_stock = avg_daily * (LEAD_TIME + cover_days) + safety_stock
        
        return {
            'reorder_point': round(reorder_point, 2),
            'target_stock': round(target_stock, 2)
        }
    
    def determine_stock_status(self, available_stock: float, avg_daily: float, 
                              reorder_point: float, target_stock: float) -> Dict:
        """
        判断库存状态
        
        Args:
            available_stock: 可用库存（当前库存 + 在途库存）
            avg_daily: 平均日销量
            reorder_point: 库存下限
            target_stock: 库存上限
        
        Returns:
            {'status': 状态, 'sellable_days': 可卖天数}
        """
        # 计算可卖天数
        if avg_daily <= 0:
            sellable_days = 999
        else:
            sellable_days = available_stock / avg_daily
            
        # 判断状态
        if sellable_days <= LEAD_TIME:
            status = '需补货'
        elif sellable_days <= WARNING_DAYS:
            status = '库存偏低'
        elif available_stock > target_stock * OVERSTOCK_THRESHOLD:
            status = '库存积压'
        else:
            status = '正常'
            
        return {
            'status': status,
            'sellable_days': round(sellable_days, 1)
        }
    
    def calculate_all(self, product_sales_data: Dict, current_month: int = None) -> List[Dict]:
        """
        计算所有产品的安全库存参数
        
        Args:
            product_sales_data: 产品销量数据字典
                key: "oe|brand"
                value: {
                    'oe': str,
                    'brand': str,
                    'total_sales': float,      # 总销量
                    'avg_daily': float,        # 平均日销量
                    'std_daily': float,        # 日销量标准差
                    'monthly_sales': {1:销量, 2:销量...}  # 各月销量
                }
            current_month: 当前月份，默认取系统时间
        
        Returns:
            计算结果列表
        """
        if current_month is None:
            current_month = datetime.now().month
            
        # 1. 获取所有产品的销量列表，用于ABC分类
        products_list = [
            {
                'frey_no': data['frey_no'],
                'total_sales': data['total_sales']
            }
            for key, data in product_sales_data.items()
        ]
        
        # 2. ABC分类
        abc_classes = self.calculate_abc_class(products_list)
        
        # 3. 计算每个产品的安全库存参数
        results = []
        for key, data in product_sales_data.items():
            abc_class = abc_classes.get(key, 'C')
            
            # 安全库存计算
            safety_stock_info = self.calculate_safety_stock(
                data['avg_daily'],
                data['std_daily'],
                abc_class,
                current_month,
                data.get('monthly_sales', {})
            )
            
            # 库存上下限
            stock_limits = self.calculate_stock_limits(
                data['avg_daily'],
                safety_stock_info['safety_stock'],
                abc_class
            )
            
            results.append({
                'frey_no': data['frey_no'],
                'abc_class': abc_class,
                'avg_daily_sales': round(data['avg_daily'], 2),
                'sales_std': round(data['std_daily'], 2),
                **safety_stock_info,
                **stock_limits
            })
            
        return results
