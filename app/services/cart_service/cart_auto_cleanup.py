"""
购物车自动清理服务
处理定时更新后和用户打开购物车时的自动清理逻辑
"""

import time
from app.services.cart_service.cart_remove import CartRemoveService

# STORES 定义在主应用文件中，需要从主模块导入
import sys
import importlib

# 清理频率限制配置（内存级缓存）
_cleanup_cache = {}
CLEANUP_INTERVAL_SECONDS = 3600  # 同一门店1小时内只清理一次（3600秒=1小时）


def get_stores():
    """动态获取 STORES 配置"""
    try:
        # 尝试从主应用模块导入
        main_module = sys.modules.get('__main__')
        if hasattr(main_module, 'STORES'):
            return main_module.STORES
        
        # 如果不行，尝试导入 beihuo_system 模块
        beihuo_module = importlib.import_module('beihuo_system')
        if hasattr(beihuo_module, 'STORES'):
            return beihuo_module.STORES
        
        # 默认返回常见的门店列表
        return {
            'fsbbr': '佛山门店',
            'zsbbr': '中山门店',
            'zhbbr': '珠海门店',
            'dgby': '百业门店',
            'dghf': '合峰门店'
        }
    except Exception as e:
        print(f"[警告] 获取 STORES 失败: {str(e)}，使用默认配置")
        return {
            'fsbbr': '佛山门店',
            'zsbbr': '中山门店',
            'zhbbr': '珠海门店',
            'dgby': '百业门店',
            'dghf': '合峰门店'
        }


def should_cleanup(store: str) -> bool:
    """
    检查是否需要执行清理（基于频率限制）
    
    参数:
        store: 门店代码
    返回:
        True表示需要清理，False表示跳过
    """
    current_time = time.time()
    last_cleanup_time = _cleanup_cache.get(store, 0)
    
    # 如果距离上次清理超过间隔时间，则允许清理
    if current_time - last_cleanup_time >= CLEANUP_INTERVAL_SECONDS:
        _cleanup_cache[store] = current_time
        return True
    
    return False


class CartAutoCleanupService:
    """购物车自动清理服务类"""
    
    def __init__(self):
        self.cart_service = CartRemoveService()
        self.stores = get_stores()  # 获取所有门店代码
    
    def cleanup_after_data_update(self):
        """
        定时更新完成后触发的自动清理
        遍历所有门店，清理库存大于20的商品
        """
        total_start = time.time()
        results = []
        store_count = 0
        
        for store in self.stores:
            store_start = time.time()
            store_count += 1
            
            try:
                result = self.cart_service.auto_remove_high_stock_items(store, 20)
                store_end = time.time()
                store_elapsed_ms = (store_end - store_start) * 1000
                
                if result['code'] == 0:
                    if result['deleted_count'] > 0:
                        results.append({
                            'store': store,
                            'status': 'success',
                            'deleted_count': result['deleted_count'],
                            'message': result['msg'],
                            'elapsed_ms': store_elapsed_ms
                        })
                        print(f"[定时] 定时更新后清理 {store} 门店: 删除 {result['deleted_count']} 个高库存商品 (耗时: {store_elapsed_ms:.2f}ms)")
                    else:
                        results.append({
                            'store': store,
                            'status': 'no_action',
                            'message': f'{store} 门店无高库存商品需要清理',
                            'elapsed_ms': store_elapsed_ms
                        })
                else:
                    results.append({
                        'store': store,
                        'status': 'error',
                        'error': result['msg'],
                        'elapsed_ms': store_elapsed_ms
                    })
            except Exception as e:
                store_end = time.time()
                store_elapsed_ms = (store_end - store_start) * 1000
                results.append({
                    'store': store,
                    'status': 'exception',
                    'error': str(e),
                    'elapsed_ms': store_elapsed_ms
                })
                print(f"[定时] 定时清理 {store} 门店失败: {str(e)} (耗时: {store_elapsed_ms:.2f}ms)")
        
        total_end = time.time()
        total_elapsed_ms = (total_end - total_start) * 1000
        print(f"[耗时] 【定时更新后批量清理】共处理 {store_count} 个门店，总耗时: {total_elapsed_ms:.2f}ms")
        
        return results
    
    def cleanup_on_cart_open(self, store):
        """
        用户打开购物车时触发的自动清理
        清理指定门店库存大于20的商品
        
        优化：添加频率限制，避免频繁执行清理
        """
        total_start = time.time()
        
        # 检查是否需要执行清理（频率限制）
        if not should_cleanup(store):
            # 跳过清理，直接返回成功（不执行实际清理）
            return {
                'code': 0,
                'msg': '清理频率限制，跳过本次清理',
                'deleted_count': 0,
                'skipped': True
            }
        
        try:
            result = self.cart_service.auto_remove_high_stock_items(store, 20)
            total_end = time.time()
            total_elapsed_ms = (total_end - total_start) * 1000
            
            if result['code'] == 0 and result['deleted_count'] > 0:
                print(f"[购物车] 用户打开购物车时清理 {store} 门店: 删除 {result['deleted_count']} 个高库存商品 (总耗时: {total_elapsed_ms:.2f}ms)")
            elif result['code'] == 0:
                print(f"[购物车] 用户打开购物车时清理 {store} 门店: 无高库存商品需要清理 (总耗时: {total_elapsed_ms:.2f}ms)")
            else:
                print(f"[购物车] 打开购物车时清理 {store} 门店失败: {result['msg']} (总耗时: {total_elapsed_ms:.2f}ms)")
            
            # 将耗时信息添加到返回结果中
            result['elapsed_ms'] = total_elapsed_ms
            return result
            
        except Exception as e:
            total_end = time.time()
            total_elapsed_ms = (total_end - total_start) * 1000
            
            error_result = {
                'code': 1,
                'msg': f'清理失败: {str(e)}',
                'elapsed_ms': total_elapsed_ms
            }
            print(f"[购物车] 打开购物车时清理 {store} 门店失败: {str(e)} (总耗时: {total_elapsed_ms:.2f}ms)")
            return error_result
