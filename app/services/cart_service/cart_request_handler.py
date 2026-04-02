"""
购物车请求处理器
统一处理购物车相关的API请求
"""

from typing import Dict, Any
from app.services.cart_service.cart_data_service import CartDataService


class CartRequestHandler:
    """购物车请求处理器"""

    def __init__(self):
        self.cart_data_service = CartDataService()

    def handle_get_cart_request(self, store: str, is_admin: bool, args: Dict = None) -> Dict[str, Any]:
        """
        处理获取购物车数据的请求，支持分页和排序

        Args:
            store: 门店代码
            is_admin: 是否为管理员
            args: 请求参数，可包含 dimension 参数（'product' 或 'supplier'）、搜索参数、分页参数、排序参数
        """
        # 从参数中获取维度，默认为产品维度
        dimension = 'product'
        # 提取搜索参数
        search_params = {}
        # 分页参数
        page = 1
        limit = 50
        # 排序参数
        sort_field = None
        sort_order = None

        if args and isinstance(args, dict):
            dimension = args.get('dimension', 'product')

            # 提取分页参数
            try:
                page = int(args.get('page', 1))
                limit = int(args.get('limit', 50))
                # 限制最大每页数量，防止性能问题（但允许获取全部数据）
                if limit > 9999:
                    limit = 9999
                if limit < 1:
                    limit = 50
                if page < 1:
                    page = 1
            except (ValueError, TypeError):
                page = 1
                limit = 50

            # 提取排序参数（Layui表格传递的参数）
            sort_field = args.get('field')  # 排序字段
            sort_order = args.get('order')  # 排序方向：asc 或 desc

            # 提取搜索参数
            search_keys = ['cart_barcode', 'cart_oe', 'cart_material_name', 'cart_brand', 'cart_tag', 'cart_car_model']
            for key in search_keys:
                if args.get(key):
                    search_params[key] = args.get(key)

        # 获取购物车数据
        try:
            # 使用CartDataService中的get_cart_data方法，传入维度参数、搜索参数、分页参数和排序参数
            cart_data, total_count = self.cart_data_service.get_cart_data(
                store, is_admin, dimension, search_params, page, limit, sort_field, sort_order
            )

            # 返回符合API接口格式的结果（包含分页信息）
            result = {
                'code': 0,
                'msg': '查询成功',
                'count': total_count,  # 总数量
                'data': cart_data      # 当前页数据
            }

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
            # 使用CartDataService中现有的get_cart_data方法，不分页获取总数
            cart_data, total_count = self.cart_data_service.get_cart_data(store, is_admin, 'product', None, 1, 1)

            # 添加清理结果信息
            summary = {
                'total_items': total_count,
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
