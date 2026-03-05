"""
购物车删除服务模块 - 精简版
只保留核心的四个必要删除方法
"""

import pymysql
from typing import List, Dict, Any, Optional
from app.utils.database_connection import get_db_connection


class CartRemoveService:
    """购物车删除服务类 - 精简核心功能"""
    
    def clear_cart(self, store: str) -> Dict[str, Any]:
        """
        清空购物车 - 直接DELETE法
        适用场景：用户一键清空当前门店购物车
        数据安全：通过store参数确保只删除当前门店数据
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 明确指定只删除当前门店数据
            sql = "DELETE FROM crmapp_cart WHERE store = %s"
            cursor.execute(sql, (store,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return {
                'code': 0,
                'msg': f'成功清空{store}门店购物车，删除 {deleted_count} 个商品',
                'deleted_count': deleted_count
            }
            
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            return {
                'code': 1,
                'msg': f'清空购物车失败: {str(e)}'
            }
    
    def remove_multiple_items(self, store: str, item_details: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        用户主动批量删除 - Set集合优化法
        适用场景：用户明确选择要删除的具体商品
        优势：精确控制，避免误删，性能优秀
        """
        if not item_details:
            return {
                'code': 1,
                'msg': '没有要删除的商品'
            }
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 分离有条码和无条码的商品
            items_with_barcode = []
            items_without_barcode = []
            
            for item in item_details:
                item_oe = item.get('item_oe')
                item_barcode = item.get('item_barcode')
                
                if item_barcode:
                    items_with_barcode.append((item_oe, item_barcode))
                else:
                    items_without_barcode.append(item_oe)
            
            deleted_count = 0
            
            # 处理有条码的商品 - 使用IN子句批量删除
            if items_with_barcode:
                oe_list = [item[0] for item in items_with_barcode]
                barcode_list = [item[1] for item in items_with_barcode]
                
                oe_placeholders = ','.join(['%s'] * len(oe_list))
                barcode_placeholders = ','.join(['%s'] * len(barcode_list))
                
                sql = f"""
                    DELETE FROM crmapp_cart 
                    WHERE oe IN ({oe_placeholders}) 
                    AND barcode IN ({barcode_placeholders}) 
                    AND store = %s
                """
                params = oe_list + barcode_list + [store]
                cursor.execute(sql, params)
                deleted_count += cursor.rowcount
            
            # 处理无条码的商品 - 使用IN子句批量删除
            if items_without_barcode:
                oe_placeholders = ','.join(['%s'] * len(items_without_barcode))
                sql = f"DELETE FROM crmapp_cart WHERE oe IN ({oe_placeholders}) AND store = %s"
                params = items_without_barcode + [store]
                cursor.execute(sql, params)
                deleted_count += cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return {
                'code': 0,
                'msg': f'成功删除 {deleted_count} 个用户选择的商品',
                'deleted_count': deleted_count
            }
            
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            return {
                'code': 1,
                'msg': f'批量删除失败: {str(e)}'
            }
    
    def remove_single_item(self, store: str, item_oe: str, item_barcode: Optional[str] = None) -> Dict[str, Any]:
        """
        删除单个商品 - Set集合法包装
        适用场景：用户删除单个明确的商品
        """
        # 将单个商品包装成列表，复用批量删除逻辑
        item_detail = {'item_oe': item_oe}
        if item_barcode:
            item_detail['item_barcode'] = item_barcode
        
        return self.remove_multiple_items(store, [item_detail])
    
    def auto_remove_high_stock_items(self, store: str, threshold: int = 20) -> Dict[str, Any]:
        """
        自动删除高库存商品 - 改进的条件批量删除法
        适用场景：系统定时自动清理库存过高的商品
        优势：符合库存管理业务逻辑，自动化处理
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 方法1: 先获取购物车中所有具有有效条码的项目
            query_cart_sql = """
                SELECT id, barcode
                FROM crmapp_cart
                WHERE store = %s AND barcode IS NOT NULL AND barcode != ''
            """
            cursor.execute(query_cart_sql, (store,))
            cart_items = cursor.fetchall()
            
            if not cart_items:
                conn.close()
                return {
                    'code': 0,
                    'msg': '购物车中没有带条码的商品',
                    'deleted_count': 0,
                    'threshold': threshold
                }
            
            # 提取条码列表
            barcodes = [item['barcode'] for item in cart_items if item['barcode']]
            
            if not barcodes:
                conn.close()
                return {
                    'code': 0,
                    'msg': '购物车中没有有效的条码',
                    'deleted_count': 0,
                    'threshold': threshold
                }
            
            # 构建查询备货表的SQL
            barcode_placeholders = ','.join(['%s'] * len(barcodes))
            query_stock_sql = f"""
                SELECT `物料条码`, `库存数量`
                FROM crmapp_beihuo
                WHERE `物料条码` IN ({barcode_placeholders}) AND `company` = %s AND `库存数量` > %s
            """
            cursor.execute(query_stock_sql, barcodes + [store, threshold])
            high_stock_items = cursor.fetchall()
            
            # 获取高库存商品的条码
            high_stock_barcodes = {item['物料条码'] for item in high_stock_items}
            
            if high_stock_barcodes:
                # 获取购物车中对应条码的ID
                cart_ids_to_delete = []
                for item in cart_items:
                    if item['barcode'] in high_stock_barcodes:
                        cart_ids_to_delete.append(item['id'])
            
                if cart_ids_to_delete:
                    # 构建删除SQL
                    id_placeholders = ','.join(['%s'] * len(cart_ids_to_delete))
                    delete_sql = f"""
                        DELETE FROM crmapp_cart
                        WHERE id IN ({id_placeholders}) AND store = %s
                    """
                    cursor.execute(delete_sql, cart_ids_to_delete + [store])
                    deleted_count = cursor.rowcount
                else:
                    deleted_count = 0
            else:
                deleted_count = 0
        
            conn.commit()
            conn.close()
        
            return {
                'code': 0,
                'msg': f'成功自动删除 {deleted_count} 个库存大于 {threshold} 的商品',
                'deleted_count': deleted_count,
                'threshold': threshold
            }
        
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            return {
                'code': 1,
                'msg': f'自动删除高库存商品失败: {str(e)}'
            }