"""
购物车请求处理器
统一处理购物车相关的API请求
"""

from typing import Dict, Any
from app.services.cart_service.cart_data_service import CartDataService


class CartRequestHandler:
    """购物车请求处理器"""

    SEARCH_KEYS = [
        'cart_barcode', 'cart_oe', 'cart_material_name',
        'cart_brand', 'cart_tag', 'cart_car_model', 'cart_car_brand'
    ]

    def __init__(self):
        self.cart_data_service = CartDataService()

    def _extract_search_params(self, args: Dict) -> Dict:
        """从请求参数中提取搜索和筛选条件"""
        search_params = {}
        if not args or not isinstance(args, dict):
            return search_params

        for key in self.SEARCH_KEYS:
            if args.get(key):
                search_params[key] = args.get(key)

        # 筛选参数（支持任意 filter_<field>）
        for key in args.keys():
            if key.startswith('filter_') and args.get(key):
                search_params[key] = args.get(key)

        return search_params

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

        # 提取搜索和筛选参数
        search_params = self._extract_search_params(args)

        # 获取购物车数据
        try:
            # 使用CartDataService中的get_cart_data方法，传入维度参数、搜索参数、分页参数和排序参数
            cart_data, total_count = self.cart_data_service.get_cart_data(
                store, dimension, search_params, page, limit, sort_field, sort_order
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

    def handle_get_cart_filter_values_request(self, store: str, is_admin: bool, args: Dict = None) -> Dict[str, Any]:
        """
        处理获取购物车某列全部去重值的请求
        """
        try:
            dimension = 'product'
            column = ''

            if args and isinstance(args, dict):
                dimension = args.get('dimension', 'product')
                column = args.get('column', '')

            search_params = self._extract_search_params(args)

            values = self.cart_data_service.get_cart_filter_values(store, dimension, search_params, column)

            return {
                'code': 0,
                'msg': '查询成功',
                'data': values
            }
        except Exception as e:
            return {
                'code': 1,
                'msg': f'获取筛选值失败: {str(e)}',
                'data': []
            }


