"""
购物车请求处理器
统一处理购物车相关的API请求，集成自动清理等功能
"""

from typing import Dict, Any
from app.services.cart_service.cart_data_service import CartDataService
from app.services.cart_service.cart_auto_cleanup import CartAutoCleanupService


class CartRequestHandler:
    """购物车请求处理器"""
    
    def __init__(self):
        self.cart_data_service = CartDataService()
        self.auto_cleanup_service = CartAutoCleanupService()
        self.last_cleanup_result = None  # 保存最后一次清理结果
    
    def handle_get_cart_request(self, store: str, is_admin: bool, args: Dict = None) -> Dict[str, Any]:
        """
        处理获取购物车数据的请求
        包含自动清理功能
        
        Args:
            store: 门店代码
            is_admin: 是否为管理员
            args: 请求参数，可包含 dimension 参数（'product' 或 'supplier'）
        """
        # 从参数中获取维度，默认为产品维度
        dimension = 'product'
        if args and isinstance(args, dict):
            dimension = args.get('dimension', 'product')
        
        # 先执行自动清理（如果需要）
        try:
            cleanup_result = self.auto_cleanup_service.cleanup_on_cart_open(store)
            self.last_cleanup_result = cleanup_result
            
            if cleanup_result['code'] == 0 and cleanup_result['deleted_count'] > 0:
                print(f"🛒 用户打开购物车时清理：删除 {cleanup_result['deleted_count']} 个高库存商品")
            elif cleanup_result['code'] == 1:
                print(f"🛒 用户打开购物车时清理失败：{cleanup_result['msg']}")
        except Exception as e:
            self.last_cleanup_result = {
                'code': 1,
                'msg': f'清理过程出错: {str(e)}',
                'deleted_count': 0
            }
            print(f"❌ 购物车清理异常: {str(e)}")
        
        # 获取购物车数据
        try:
            # 使用CartDataService中的get_cart_data方法，传入维度参数
            cart_data = self.cart_data_service.get_cart_data(store, is_admin, dimension)
            
            # 返回符合API接口格式的结果
            result = {
                'code': 0,
                'msg': '查询成功',
                'count': len(cart_data),
                'data': cart_data
            }
            
            if self.last_cleanup_result:
                result['cleanup_result'] = self.last_cleanup_result
                
            return result
        except Exception as e:
            return {
                'code': 1,
                'msg': f'获取购物车数据失败: {str(e)}',
                'count': 0,
                'data': []
            }
    
    def handle_add_to_cart_request(self, store: str, item_details: Dict) -> Dict[str, Any]:
        """处理添加到购物车的请求"""
        try:
            return self.cart_data_service.add_to_cart(store, item_details)
        except Exception as e:
            return {
                'code': 1,
                'msg': f'添加购物车失败: {str(e)}'
            }
    
    def handle_remove_from_cart_request(self, store: str, item_details: Dict) -> Dict[str, Any]:
        """处理从购物车移除的请求"""
        try:
            return self.cart_data_service.remove_from_cart(store, item_details)
        except Exception as e:
            return {
                'code': 1,
                'msg': f'移除购物车失败: {str(e)}'
            }
    
    def handle_clear_cart_request(self, store: str, can_delete_cart: bool) -> Dict[str, Any]:
        """处理清空购物车的请求"""
        try:
            return self.cart_data_service.clear_cart(store, can_delete_cart)
        except Exception as e:
            return {
                'code': 1,
                'msg': f'清空购物车失败: {str(e)}'
            }
    
    def handle_get_cart_summary(self, store: str, is_admin: bool) -> Dict[str, Any]:
        """获取购物车摘要信息"""
        try:
            # 使用CartDataService中现有的get_cart_data方法
            cart_data = self.cart_data_service.get_cart_data(store, is_admin)
            
            # 添加清理结果信息
            summary = {
                'total_items': len(cart_data),
                'store': store,
                'is_admin': is_admin
            }
            
            if self.last_cleanup_result:
                summary['last_cleanup_result'] = self.last_cleanup_result
                
            return {
                'code': 0,
                'msg': '获取摘要成功',
                'data': summary
            }
        except Exception as e:
            return {
                'code': 1,
                'msg': f'获取摘要失败: {str(e)}'
            }