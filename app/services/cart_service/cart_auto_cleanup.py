"""
购物车自动清理服务
处理定时更新后和用户打开购物车时的自动清理逻辑
"""

from app.services.cart_service.cart_remove import CartRemoveService

# STORES 定义在主应用文件中，需要从主模块导入
import sys
import importlib

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
        print(f"⚠️ 获取 STORES 失败: {str(e)}，使用默认配置")
        return {
            'fsbbr': '佛山门店',
            'zsbbr': '中山门店',
            'zhbbr': '珠海门店',
            'dgby': '百业门店',
            'dghf': '合峰门店'
        }


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
        results = []
        for store in self.stores:
            try:
                result = self.cart_service.auto_remove_high_stock_items(store, 20)
                if result['code'] == 0:
                    if result['deleted_count'] > 0:
                        results.append({
                            'store': store,
                            'status': 'success',
                            'deleted_count': result['deleted_count'],
                            'message': result['msg']
                        })
                        print(f"🕒 定时更新后清理 {store} 门店: 删除 {result['deleted_count']} 个高库存商品")
                    else:
                        results.append({
                            'store': store,
                            'status': 'no_action',
                            'message': f'{store} 门店无高库存商品需要清理'
                        })
                else:
                    results.append({
                        'store': store,
                        'status': 'error',
                        'error': result['msg']
                    })
            except Exception as e:
                results.append({
                    'store': store,
                    'status': 'exception',
                    'error': str(e)
                })
                print(f"🕒 定时清理 {store} 门店失败: {str(e)}")
        
        return results
    
    def cleanup_on_cart_open(self, store):
        """
        用户打开购物车时触发的自动清理
        清理指定门店库存大于20的商品
        """
        try:
            result = self.cart_service.auto_remove_high_stock_items(store, 20)
            if result['code'] == 0 and result['deleted_count'] > 0:
                print(f"🛒 用户打开购物车时清理 {store} 门店: 删除 {result['deleted_count']} 个高库存商品")
            return result
        except Exception as e:
            error_result = {
                'code': 1,
                'msg': f'清理失败: {str(e)}'
            }
            print(f"🛒 打开购物车时清理 {store} 门店失败: {str(e)}")
            return error_result