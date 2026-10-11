"""
购物车删除服务模块 - 精简版
只保留核心的四个必要删除方法
"""

import pymysql
import time
from typing import List, Dict, Any, Optional
from app.utils.database_connection import get_db_connection


def log_step(step_name: str, start_time: float, end_time: float):
    """
    记录步骤执行时间
    
    参数:
        step_name: 步骤名称
        start_time: 开始时间戳（秒）
        end_time: 结束时间戳（秒）
    """
    elapsed_ms = (end_time - start_time) * 1000
    print(f"[耗时] [{step_name}] 耗时: {elapsed_ms:.2f}ms")


class CartRemoveService:
    """购物车删除服务类 - 精简核心功能"""
    
    def clear_cart(self, store: str, deleted_by: Optional[str] = None) -> Dict[str, Any]:
        """
        清空购物车 - 软删除（UPDATE标记法）
        适用场景：用户一键清空当前门店购物车
        数据安全：通过store参数确保只标记当前门店数据，物理行保留
        """
        total_start = time.time()
        step_start = total_start
        
        try:
            conn = get_db_connection()
            step_end = time.time()
            log_step("获取数据库连接", step_start, step_end)
            step_start = step_end
            
            cursor = conn.cursor()
            step_end = time.time()
            log_step("创建游标", step_start, step_end)
            step_start = step_end
            
            # 明确指定只标记当前门店的未删除数据
            sql = """
                UPDATE crmapp_cart
                SET is_deleted = 1, deleted_time = NOW(), deleted_by = %s
                WHERE store = %s AND is_deleted = 0
            """
            cursor.execute(sql, (deleted_by, store))
            step_end = time.time()
            log_step("执行软删除UPDATE语句", step_start, step_end)
            step_start = step_end
            
            deleted_count = cursor.rowcount
            conn.commit()
            step_end = time.time()
            log_step("提交事务", step_start, step_end)
            step_start = step_end
            
            conn.close()
            step_end = time.time()
            log_step("关闭连接", step_start, step_end)
            
            total_end = time.time()
            log_step("【清空购物车】总耗时", total_start, total_end)
            
            return {
                'code': 0,
                'msg': f'成功清空{store}门店购物车，删除 {deleted_count} 个商品',
                'deleted_count': deleted_count
            }
            
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            total_end = time.time()
            log_step("【清空购物车】失败总耗时", total_start, total_end)
            return {
                'code': 1,
                'msg': f'清空购物车失败: {str(e)}'
            }
    
    def remove_multiple_items(self, store: str, item_details: List[Dict[str, Any]],
                              deleted_by: Optional[str] = None) -> Dict[str, Any]:
        """
        用户主动批量删除 - 逐条精确软删除
        适用场景：用户明确选择要删除的具体商品
        有 item_barcode 时按 OE+条码 精确匹配，否则仅按 OE 删除（兼容旧逻辑）
        """
        if not item_details:
            return {'code': 1, 'msg': '没有要删除的商品'}

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            deleted_count = 0

            # 逐条软删，保证 (oe, barcode) 精确配对，避免 IN 列表交叉匹配误删
            for item in item_details:
                item_oe = item.get('item_oe')
                item_barcode = item.get('item_barcode')

                if item_barcode:
                    sql = """
                        UPDATE crmapp_cart
                        SET is_deleted = 1, deleted_time = NOW(), deleted_by = %s
                        WHERE oe = %s AND barcode = %s AND store = %s AND is_deleted = 0
                    """
                    cursor.execute(sql, (deleted_by, item_oe, item_barcode, store))
                else:
                    sql = """
                        UPDATE crmapp_cart
                        SET is_deleted = 1, deleted_time = NOW(), deleted_by = %s
                        WHERE oe = %s AND store = %s AND is_deleted = 0
                    """
                    cursor.execute(sql, (deleted_by, item_oe, store))

                deleted_count += cursor.rowcount

            conn.commit()

            return {
                'code': 0,
                'msg': f'成功删除 {deleted_count} 个用户选择的商品',
                'deleted_count': deleted_count
            }
        except Exception as e:
            return {'code': 1, 'msg': f'批量删除失败: {str(e)}'}
        finally:
            conn.close()

    def remove_single_item(self, store: str, item_oe: str, item_barcode: Optional[str] = None,
                           deleted_by: Optional[str] = None) -> Dict[str, Any]:
        """
        删除单个商品 - 逐条软删的单条包装
        适用场景：用户删除单个明确的商品
        """
        # 将单个商品包装成列表，复用批量删除逻辑
        item_detail = {'item_oe': item_oe}
        if item_barcode:
            item_detail['item_barcode'] = item_barcode

        return self.remove_multiple_items(store, [item_detail], deleted_by)
    
    def auto_remove_high_stock_items(self, store: str, threshold: int = 20,
                                     deleted_by: str = 'system') -> Dict[str, Any]:
        """
        自动软删除高库存商品 - 条件批量标记法
        适用场景：系统定时自动清理库存过高的商品
        优势：符合库存管理业务逻辑，自动化处理，物理行保留可追溯
        """
        total_start = time.time()
        step_start = total_start
        
        try:
            conn = get_db_connection()
            step_end = time.time()
            log_step("获取数据库连接", step_start, step_end)
            step_start = step_end
            
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            step_end = time.time()
            log_step("创建游标", step_start, step_end)
            step_start = step_end
            
            # 方法1: 先获取购物车中所有具有有效条码的未删除项目
            query_cart_sql = """
                SELECT id, barcode
                FROM crmapp_cart
                WHERE store = %s AND barcode IS NOT NULL AND barcode != '' AND is_deleted = 0
            """
            cursor.execute(query_cart_sql, (store,))
            cart_items = cursor.fetchall()
            
            step_end = time.time()
            log_step(f"查询购物车商品({len(cart_items)}条)", step_start, step_end)
            step_start = step_end
            
            if not cart_items:
                conn.close()
                step_end = time.time()
                log_step("关闭连接", step_start, step_end)
                total_end = time.time()
                log_step("【自动删除高库存商品】总耗时(无商品)", total_start, total_end)
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
                step_end = time.time()
                log_step("关闭连接", step_start, step_end)
                total_end = time.time()
                log_step("【自动删除高库存商品】总耗时(无条码)", total_start, total_end)
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
            
            step_end = time.time()
            log_step(f"查询高库存商品({len(high_stock_items)}条)", step_start, step_end)
            step_start = step_end
            
            # 获取高库存商品的条码
            high_stock_barcodes = {item['物料条码'] for item in high_stock_items}
            
            if high_stock_barcodes:
                # 获取购物车中对应条码的ID
                cart_ids_to_delete = []
                for item in cart_items:
                    if item['barcode'] in high_stock_barcodes:
                        cart_ids_to_delete.append(item['id'])
            
                if cart_ids_to_delete:
                    # 构建软删除SQL
                    id_placeholders = ','.join(['%s'] * len(cart_ids_to_delete))
                    delete_sql = f"""
                        UPDATE crmapp_cart
                        SET is_deleted = 1, deleted_time = NOW(), deleted_by = %s
                        WHERE id IN ({id_placeholders}) AND store = %s AND is_deleted = 0
                    """
                    cursor.execute(delete_sql, [deleted_by] + cart_ids_to_delete + [store])
                    deleted_count = cursor.rowcount

                    step_end = time.time()
                    log_step(f"执行软删除({deleted_count}条)", step_start, step_end)
                    step_start = step_end
                else:
                    deleted_count = 0
            else:
                deleted_count = 0
        
            conn.commit()
            step_end = time.time()
            log_step("提交事务", step_start, step_end)
            step_start = step_end
            
            conn.close()
            step_end = time.time()
            log_step("关闭连接", step_start, step_end)
            
            total_end = time.time()
            log_step("【自动删除高库存商品】总耗时", total_start, total_end)
        
            return {
                'code': 0,
                'msg': f'成功自动删除 {deleted_count} 个库存大于 {threshold} 的商品',
                'deleted_count': deleted_count,
                'threshold': threshold
            }
        
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            total_end = time.time()
            log_step("【自动删除高库存商品】失败总耗时", total_start, total_end)
            return {
                'code': 1,
                'msg': f'自动删除高库存商品失败: {str(e)}'
            }

    def purge_deleted_items(self, retention_days: int = 90) -> Dict[str, Any]:
        """
        物理清理超过保留期的软删除数据 - 定时任务调用
        适用场景：每日定时清理 is_deleted=1 且 deleted_time 超过保留期的行
        注意：物理删除不可恢复；deleted_time 为空的行不清理，避免误删历史脏数据
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            sql = """
                DELETE FROM crmapp_cart
                WHERE is_deleted = 1
                  AND deleted_time IS NOT NULL
                  AND deleted_time < DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            cursor.execute(sql, (retention_days,))
            purged_count = cursor.rowcount
            conn.commit()

            return {
                'code': 0,
                'msg': f'成功物理清理 {purged_count} 条软删除超过 {retention_days} 天的数据',
                'purged_count': purged_count,
                'retention_days': retention_days
            }
        except Exception as e:
            return {'code': 1, 'msg': f'物理清理软删除数据失败: {str(e)}'}
        finally:
            conn.close()