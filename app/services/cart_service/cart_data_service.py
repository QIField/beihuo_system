"""
购物车基础数据服务
处理购物车数据的查询和基础处理逻辑
"""

import pymysql
import re
from typing import List, Dict, Any
from app.utils.database_connection import get_db_connection

class CartDataService:
    """购物车基础数据服务类"""
    
    def get_cart_data(self, store: str, is_admin: bool = False, dimension: str = 'product') -> List[Dict[str, Any]]:
        """
        获取购物车数据 - 支持产品维度和供应商维度
        
        Args:
            store: 门店代码
            is_admin: 是否为管理员
            dimension: 维度类型，'product' 或 'supplier'
        """
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 统一使用传入的store参数，确保门店数据隔离
        sql = "SELECT * FROM crmapp_cart WHERE store = %s ORDER BY added_time DESC"
        cursor.execute(sql, (store,))

        result = cursor.fetchall()

        # 确保时间格式正确
        for item in result:
            if isinstance(item['added_time'], object) and hasattr(item['added_time'], 'strftime'):
                item['added_time'] = item['added_time'].strftime('%Y-%m-%d %H:%M:%S')
            elif item['added_time'] and isinstance(item['added_time'], str):
                # 如果已经是字符串格式，保持不变
                pass

        conn.close()
        
        # 如果是供应商维度，拆分供应商数据
        if dimension == 'supplier':
            result = self._expand_by_suppliers(result)
        
        return list(result)
    
    def _expand_by_suppliers(self, cart_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按供应商拆分购物车数据
        一个产品如果有多个供应商，会拆分成多行
        """
        expanded_result = []
        
        for item in cart_items:
            supplier_raw = item.get('supplier', '')
            suppliers = self._parse_supplier_string(supplier_raw)
            
            for supplier_name, price in suppliers:
                supplier_item = item.copy()
                # 使用中文冒号，与原始数据格式保持一致
                supplier_item['supplier'] = f"{supplier_name}：{price}"
                expanded_result.append(supplier_item)
        
        return expanded_result
    
    def _parse_supplier_string(self, supplier_str: str) -> List[tuple]:
        """
        解析供应商字符串，提取供应商名称和价格
        
        使用正则表达式匹配"供应商名称：价格"的模式
        价格格式为：数字.数字（如 42.0, 19.9 等）
        
        示例：
        "佛山颂沃德汽配：0.0 广州粤之星 品牌部：0.0 上海佳配：19.9"
        -> [("佛山颂沃德汽配", "0.0"), ("广州粤之星 品牌部", "0.0"), ("上海佳配", "19.9")]
        """
        if not supplier_str or not isinstance(supplier_str, str):
            return [(supplier_str or "未知供应商", "N/A")]
        
        # 使用正则表达式匹配"名称：价格"的模式
        # (.+?)： - 非贪婪匹配任意字符（供应商名称）和中文冒号
        # (\d+\.?\d*) - 匹配价格（支持 42, 42.0, 42.5 等格式）
        pattern = r'(.+?)：(\d+\.?\d*)'
        matches = re.findall(pattern, supplier_str)
        
        suppliers = []
        for name, price in matches:
            name = name.strip()
            price = price.strip()
            if name:
                suppliers.append((name, price))
        
        return suppliers if suppliers else [(supplier_str, "N/A")]
    
    def get_cart_data_with_cleanup(self, store: str, is_admin: bool = False, dimension: str = 'product'):
        """
        获取购物车数据并在返回前执行自动清理
        结合数据获取和自动清理功能
        """
        # 先导入自动清理服务（避免循环导入）
        from app.services.cart_service.cart_auto_cleanup import CartAutoCleanupService
        
        # 执行自动清理
        auto_cleanup_service = CartAutoCleanupService()
        cleanup_result = auto_cleanup_service.cleanup_on_cart_open(store)
        
        # 获取清理后的数据
        cart_data = self.get_cart_data(store, is_admin, dimension)
        
        return {
            'cart_data': cart_data,
            'cleanup_result': cleanup_result
        }
