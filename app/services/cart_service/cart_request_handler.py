"""
购物车请求处理器
统一处理购物车相关的API请求
"""

import time
from typing import Dict, Any
from app.services.cart_service.cart_data_service import CartDataService


class CartRequestHandler:
    """购物车请求处理器"""

    def __init__(self):
        self.cart_data_service = CartDataService()

    def handle_get_cart_request(self, store: str, is_admin: bool, args: Dict = None) -> Dict[str, Any]:
        """
        处理获取购物车数据的请求

        Args:
            store: 门店代码
            is_admin: 是否为管理员
            args: 请求参数，可包含 dimension 参数（'product' 或 'supplier'）和搜索参数
        """
        total_start = time.time()

        # 从参数中获取维度，默认为产品维度
        dimension = 'product'
        # 提取搜索参数
        search_params = {}
        if args and isinstance(args, dict):
            dimension = args.get('dimension', 'product')
            # 提取搜索参数
            search_keys = ['cart_barcode', 'cart_oe', 'cart_material_name', 'cart_brand', 'cart_tag', 'cart_car_model']
            for key in search_keys:
                if args.get(key):
                    search_params[key] = args.get(key)

        # 获取购物车数据
        try:
            # 使用CartDataService中的get_cart_data方法，传入维度参数和搜索参数
            cart_data = self.cart_data_service.get_cart_data(store, is_admin, dimension, search_params)

            total_end = time.time()
            total_elapsed_ms = (total_end - total_start) * 1000

            print(f"⏱️ 【获取购物车请求】查询耗时: {total_elapsed_ms:.2f}ms")

            # 返回符合API接口格式的结果
            result = {
                'code': 0,
                'msg': '查询成功',
                'count': len(cart_data),
                'data': cart_data
            }

            return result
        except Exception as e:
            total_end = time.time()
            total_elapsed_ms = (total_end - total_start) * 1000
            print(f"⏱️ 【获取购物车请求】失败，总耗时: {total_elapsed_ms:.2f}ms")
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
