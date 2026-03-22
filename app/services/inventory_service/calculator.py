# -*- coding: utf-8 -*-
"""
安全库存核心算法模块
实现波动缓冲区法和统计法计算安全库存
"""
import math
from typing import Dict, Tuple


class SafetyStockCalculator:
    """安全库存计算器"""
    
    # 服务水平对应的Z值（标准正态分布）
    Z_SCORES = {
        0.90: 1.28,
        0.95: 1.65,
        0.99: 2.33
    }
    
    @classmethod
    def calculate_buffer_method(
        cls,
        demand_avg: float,
        demand_max: float,
        lead_time_avg: float,
        lead_time_max: float
    ) -> Dict[str, float]:
        """
        波动缓冲区法计算安全库存
        
        公式：
        需求波动缓冲 = (需求峰值 - 需求均值) × 平均补货期
        补货延迟缓冲 = (最长交货期 - 平均补货期) × 需求均值
        安全库存 = 需求波动缓冲 + 补货延迟缓冲
        
        Args:
            demand_avg: 平均需求量（件/天）
            demand_max: 需求峰值（件/天）
            lead_time_avg: 平均补货期（天）
            lead_time_max: 最长交货期（天）
            
        Returns:
            dict: 包含各缓冲区和安全库存的字典
        """
        # 需求波动缓冲
        demand_buffer = (demand_max - demand_avg) * lead_time_avg
        
        # 补货延迟缓冲
        lead_time_buffer = (lead_time_max - lead_time_avg) * demand_avg
        
        # 基础安全库存
        safety_stock = demand_buffer + lead_time_buffer
        
        return {
            'demand_buffer': round(demand_buffer, 2),
            'lead_time_buffer': round(lead_time_buffer, 2),
            'safety_stock': round(safety_stock, 2),
            'method': 'buffer'
        }
    
    @classmethod
    def calculate_statistical_method(
        cls,
        demand_avg: float,
        demand_std: float,
        lead_time_avg: float,
        service_level: float = 0.95
    ) -> Dict[str, float]:
        """
        统计法计算安全库存（基于正态分布）
        
        公式：安全库存 = Z × 需求标准差 × √(补货期)
        
        Args:
            demand_avg: 平均需求量
            demand_std: 需求标准差
            lead_time_avg: 平均补货期
            service_level: 服务水平（默认95%）
            
        Returns:
            dict: 包含统计安全库存的字典
        """
        # 获取Z值
        z = cls.Z_SCORES.get(service_level, 1.65)
        
        # 计算安全库存
        safety_stock = z * demand_std * math.sqrt(lead_time_avg)
        
        return {
            'z_score': z,
            'safety_stock': round(safety_stock, 2),
            'method': 'statistical'
        }
    
    @classmethod
    def calculate_inventory_limits(
        cls,
        safety_stock: float,
        demand_avg: float,
        lead_time_avg: float,
        max_inventory_days: float = 30
    ) -> Dict[str, float]:
        """
        计算库存上下限
        
        Args:
            safety_stock: 安全库存
            demand_avg: 平均需求量
            lead_time_avg: 平均补货期
            max_inventory_days: 最大库存天数限制
            
        Returns:
            dict: 包含各阈值的字典
        """
        # 库存下限（紧急预警线）= 安全库存 × 0.5
        inventory_min = safety_stock * 0.5
        
        # 再订货点 = 安全库存 + 提前期内的平均需求
        lead_time_demand = demand_avg * lead_time_avg
        reorder_point = safety_stock + lead_time_demand
        
        # 目标库存 = 安全库存 + 补货周期需求（假设7天补货周期）
        order_cycle = 7
        target_inventory = safety_stock + demand_avg * (lead_time_avg + order_cycle)
        
        # 按最大库存天数限制
        max_by_days = demand_avg * max_inventory_days
        
        # 库存上限取较小值
        inventory_max = min(target_inventory, max_by_days)
        
        # 建议补货量
        suggested_qty = inventory_max - reorder_point
        
        return {
            'inventory_min': round(inventory_min, 2),
            'reorder_point': round(reorder_point, 2),
            'inventory_max': round(inventory_max, 2),
            'target_inventory': round(target_inventory, 2),
            'suggested_qty': round(suggested_qty, 2) if suggested_qty > 0 else 0
        }
    
    @classmethod
    def determine_stock_status(
        cls,
        current_stock: float,
        safety_stock: float,
        reorder_point: float
    ) -> str:
        """
        判断库存状态
        
        Returns:
            str: 'normal'(正常) / 'warning'(预警) / 'danger'(危险)
        """
        if current_stock <= safety_stock:
            return 'danger'
        elif current_stock <= reorder_point:
            return 'warning'
        else:
            return 'normal'
    
    @classmethod
    def calculate_complete(
        cls,
        demand_avg: float,
        demand_max: float,
        demand_std: float,
        lead_time_avg: float,
        lead_time_max: float,
        current_stock: float,
        service_level: float = 0.95,
        max_inventory_days: float = 30
    ) -> Dict[str, any]:
        """
        完整计算流程
        
        Returns:
            dict: 包含所有计算结果的字典
        """
        # 1. 波动缓冲区法
        buffer_result = cls.calculate_buffer_method(
            demand_avg, demand_max, lead_time_avg, lead_time_max
        )
        
        # 2. 统计法
        statistical_result = cls.calculate_statistical_method(
            demand_avg, demand_std, lead_time_avg, service_level
        )
        
        # 3. 取较大值作为最终安全库存（保守策略）
        final_safety_stock = max(
            buffer_result['safety_stock'],
            statistical_result['safety_stock']
        )
        
        # 4. 计算库存上下限
        limits = cls.calculate_inventory_limits(
            final_safety_stock, demand_avg, lead_time_avg, max_inventory_days
        )
        
        # 5. 判断库存状态
        stock_status = cls.determine_stock_status(
            current_stock, final_safety_stock, limits['reorder_point']
        )
        
        return {
            'demand_avg': round(demand_avg, 2),
            'demand_max': round(demand_max, 2),
            'demand_std': round(demand_std, 2),
            'lead_time_avg': round(lead_time_avg, 1),
            'lead_time_max': round(lead_time_max, 1),
            'buffer_safety_stock': buffer_result['safety_stock'],
            'statistical_safety_stock': statistical_result['safety_stock'],
            'safety_stock': round(final_safety_stock, 2),
            'inventory_min': limits['inventory_min'],
            'reorder_point': limits['reorder_point'],
            'inventory_max': limits['inventory_max'],
            'target_inventory': limits['target_inventory'],
            'current_stock': round(current_stock, 2),
            'suggested_qty': limits['suggested_qty'],
            'stock_status': stock_status,
            'service_level': service_level
        }
