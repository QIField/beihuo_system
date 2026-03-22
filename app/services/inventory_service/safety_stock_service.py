# -*- coding: utf-8 -*-
"""
安全库存业务服务
整合算法和数据聚合，提供完整的业务接口
"""
from datetime import datetime
from typing import List, Dict, Optional

from app.models.inventory import SafetyStock, get_db_session
from app.services.inventory_service.calculator import SafetyStockCalculator
from app.services.inventory_service.data_aggregation import InventoryDataAggregator


class SafetyStockService:
    """安全库存服务"""
    
    def __init__(self):
        self.calculator = SafetyStockCalculator()
        self.aggregator = InventoryDataAggregator()
    
    def calculate_single(self, sku: str, service_level: float = 0.95) -> Dict:
        """
        计算单个SKU的安全库存
        
        Args:
            sku: SKU编码
            service_level: 服务水平
            
        Returns:
            dict: 计算结果
        """
        # 1. 聚合数据
        data = self.aggregator.aggregate_sku_data(sku)
        
        if data['sales']['demand_avg'] == 0:
            return {
                'code': 400,
                'msg': f'SKU {sku} 没有销量数据，无法计算',
                'data': None
            }
        
        # 2. 执行计算
        result = self.calculator.calculate_complete(
            demand_avg=data['sales']['demand_avg'],
            demand_max=data['sales']['demand_max'],
            demand_std=data['sales']['demand_std'],
            lead_time_avg=data['purchase']['lead_time_avg'],
            lead_time_max=data['purchase']['lead_time_max'],
            current_stock=data['current_stock'],
            service_level=service_level
        )
        
        # 3. 补充SKU信息
        result['sku'] = sku
        result['sku_name'] = data['sku_name']
        result['inquiry_1m'] = data['inquiry']['inquiry_1m']
        result['inquiry_3m'] = data['inquiry']['inquiry_3m']
        
        # 4. 保存结果
        self._save_result(result, service_level)
        
        return {
            'code': 200,
            'msg': '计算成功',
            'data': result
        }
    
    def _save_result(self, result: Dict, service_level: float):
        """保存计算结果到数据库"""
        try:
            safety_stock = SafetyStock(
                sku=result['sku'],
                sku_name=result['sku_name'],
                calc_date=datetime.now().date(),
                demand_avg=result['demand_avg'],
                demand_max=result['demand_max'],
                demand_std=result['demand_std'],
                lead_time_avg=result['lead_time_avg'],
                lead_time_max=result['lead_time_max'],
                safety_stock=result['safety_stock'],
                inventory_min=result['inventory_min'],
                reorder_point=result['reorder_point'],
                inventory_max=result['inventory_max'],
                target_inventory=result['target_inventory'],
                current_stock=result['current_stock'],
                suggested_qty=result['suggested_qty'],
                stock_status=result['stock_status'],
                inquiry_1m=result.get('inquiry_1m', 0),
                inquiry_3m=result.get('inquiry_3m', 0),
                service_level=service_level
            )
            safety_stock.save()
        except Exception as e:
            print(f"保存结果失败: {e}")
    
    def calculate_pilot(self, limit: int = 10) -> Dict:
        """
        计算试点SKU（用于测试验证）
        
        Args:
            limit: 试点数量
            
        Returns:
            dict: 批量计算结果
        """
        # 获取试点SKU列表
        pilot_skus = self.aggregator.get_pilot_skus(limit)
        
        if not pilot_skus:
            return {
                'code': 400,
                'msg': '没有找到符合条件的试点SKU',
                'data': None
            }
        
        results = []
        errors = []
        
        for sku_info in pilot_skus:
            try:
                result = self.calculate_single(sku_info['sku'])
                if result['code'] == 200:
                    results.append(result['data'])
                else:
                    errors.append({'sku': sku_info['sku'], 'error': result['msg']})
            except Exception as e:
                errors.append({'sku': sku_info['sku'], 'error': str(e)})
        
        return {
            'code': 200,
            'msg': f'试点计算完成，成功{len(results)}个，失败{len(errors)}个',
            'data': {
                'results': results,
                'errors': errors
            }
        }
    
    def calculate_all(self, batch_size: int = 100) -> Dict:
        """
        计算所有活跃SKU（分批处理）
        
        Args:
            batch_size: 每批处理数量
            
        Returns:
            dict: 批量计算结果
        """
        offset = 0
        total_success = 0
        total_error = 0
        
        while True:
            # 获取一批SKU
            skus = self.aggregator.get_all_active_skus(offset, batch_size)
            
            if not skus:
                break
            
            # 逐个计算
            for sku_info in skus:
                try:
                    result = self.calculate_single(sku_info['sku'])
                    if result['code'] == 200:
                        total_success += 1
                    else:
                        total_error += 1
                except Exception as e:
                    total_error += 1
                    print(f"计算失败 {sku_info['sku']}: {e}")
            
            offset += batch_size
        
        return {
            'code': 200,
            'msg': f'全量计算完成，成功{total_success}个，失败{total_error}个',
            'data': {
                'total_success': total_success,
                'total_error': total_error
            }
        }
    
    def get_result(self, sku: str) -> Dict:
        """
        查询SKU的最新计算结果
        
        Args:
            sku: SKU编码
            
        Returns:
            dict: 查询结果
        """
        try:
            results = SafetyStock.get_by_sku(sku, limit=1)
            
            if not results:
                return {
                    'code': 404,
                    'msg': f'未找到SKU {sku} 的计算结果',
                    'data': None
                }
            
            return {
                'code': 200,
                'msg': '查询成功',
                'data': results[0].to_dict()
            }
        except Exception as e:
            return {
                'code': 500,
                'msg': f'查询失败: {str(e)}',
                'data': None
            }
    
    def get_list(self, page: int = 1, page_size: int = 20, 
                 status: Optional[str] = None) -> Dict:
        """
        获取安全库存列表
        
        Args:
            page: 页码
            page_size: 每页数量
            status: 筛选状态
            
        Returns:
            dict: 列表数据
        """
        try:
            result = SafetyStock.get_list(page=page, page_size=page_size, status=status)
            
            return {
                'code': 200,
                'msg': '查询成功',
                'data': result
            }
        except Exception as e:
            return {
                'code': 500,
                'msg': f'查询失败: {str(e)}',
                'data': None
            }
    
    def get_warning_list(self, status: str = 'danger') -> Dict:
        """
        获取预警列表
        
        Args:
            status: 预警状态(danger/warning)
            
        Returns:
            dict: 预警列表
        """
        try:
            items = SafetyStock.get_warning_list(status)
            
            return {
                'code': 200,
                'msg': '查询成功',
                'data': [item.to_dict() for item in items]
            }
        except Exception as e:
            return {
                'code': 500,
                'msg': f'查询失败: {str(e)}',
                'data': None
            }
    
    def run_daily_task(self):
        """
        定时任务入口
        每晚执行，先计算试点SKU验证，再全量计算
        """
        print(f"[{datetime.now()}] 安全库存定时任务开始")
        
        # 1. 先计算试点SKU验证
        pilot_result = self.calculate_pilot(limit=10)
        print(f"试点计算: {pilot_result['msg']}")
        
        if pilot_result['code'] == 200:
            # 2. 试点成功，执行全量计算
            all_result = self.calculate_all(batch_size=100)
            print(f"全量计算: {all_result['msg']}")
        
        print(f"[{datetime.now()}] 安全库存定时任务完成")


# 定时任务入口函数（供task_manager调用）
def run_safety_stock_task():
    """安全库存定时任务"""
    service = SafetyStockService()
    service.run_daily_task()
