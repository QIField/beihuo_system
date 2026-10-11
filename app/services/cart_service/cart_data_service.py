"""
购物车基础数据服务
处理购物车数据的查询和基础处理逻辑
"""

import re
from typing import List, Dict, Any, Tuple
from app.utils.database_connection import get_db_connection, db_cursor
from app.utils.search import parse_space, parse_comma
from app.services.cart_service.supplier_expander import expand_items_by_supplier


class CartDataService:
    """购物车基础数据服务类"""

    # 字段映射表，用于排序
    FIELD_MAPPING = {
        'oe': 'oe',
        'brand': 'brand',
        'material_name': 'material_name',
        'barcode': 'barcode',
        'brand_code': 'brand_code',
        'replace_no': 'replace_no',
        'car_brand': 'car_brand',
        'tag': 'tag',
        'car_model': 'car_model',
        'stock': 'stock',
        'on_way': 'on_way',
        'inquiry_1m': 'inquiry_1m',
        'inquiry_3m': 'inquiry_3m',
        'national_inquiry_1m': 'national_inquiry_1m',
        'national_inquiry_3m': 'national_inquiry_3m',
        'stock_amount': 'stock_amount',
        'sellable_days': 'sellable_days',
        'cost_price': 'cost_price',
        'warning_status': 'warning_status',
        'quantity': 'quantity',
        'added_time': 'added_time',
        'added_by': 'added_by',
        'today_sales': 'today_sales',
        'sales_yesterday': 'sales_yesterday',
        'sales_7d': 'sales_7d',
        'sales_month': 'sales_month',
        'avg_sales_6m': 'avg_sales_6m',
        'avg_sales_12m': 'avg_sales_12m',
        'purchase_records': 'purchase_records',
    }

    def get_cart_data(self, store: str, dimension: str = 'product',
                      search_params: Dict = None, page: int = 1, limit: int = 50,
                      sort_field: str = None, sort_order: str = None,
                      include_deleted: bool = False) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取购物车数据 - 支持产品维度和供应商维度，支持搜索过滤、排序和分页

        Args:
            store: 门店代码
            dimension: 维度类型，'product' 或 'supplier'
            search_params: 搜索参数字典，可包含 cart_barcode, cart_oe, cart_material_name, cart_brand, cart_tag
            page: 页码，从1开始
            limit: 每页数量
            sort_field: 排序字段
            sort_order: 排序方向，'asc' 或 'desc'
            include_deleted: 是否包含软删除数据，默认 False（仅管理后台可传 True）

        Returns:
            (数据列表, 总数量)
        """
        # 使用上下文管理器确保连接正确关闭，避免连接泄漏
        with db_cursor(dict_cursor=True) as cursor:
            # 构建基础SQL查询，默认过滤软删除数据
            sql = "SELECT * FROM crmapp_cart WHERE store = %s"
            count_sql = "SELECT COUNT(*) as total FROM crmapp_cart WHERE store = %s"
            params = [store]
            count_params = [store]

            if not include_deleted:
                sql += " AND is_deleted = 0"
                count_sql += " AND is_deleted = 0"

            # 复用搜索/筛选条件拼接逻辑
            sql, params = self._apply_search_conditions(sql, params, search_params)
            count_sql, count_params = self._apply_search_conditions(count_sql, count_params, search_params)

            # 处理排序
            order_clause = self._build_order_clause(sort_field, sort_order)
            sql += order_clause

            # 如果是供应商维度，需要先获取所有数据，拆分供应商后再分页
            if dimension == 'supplier':
                # 获取所有符合条件的数据（不分页）
                cursor.execute(sql, tuple(params))
                all_result = cursor.fetchall()

                # 拆分供应商数据（共享展开逻辑）
                expanded_result = expand_items_by_supplier(list(all_result))

                # 计算拆分后的总数量
                total_count = len(expanded_result)

                # 对拆分后的数据进行分页
                offset = (page - 1) * limit
                result = expanded_result[offset:offset + limit]
            else:
                # 产品维度：先查询总数量
                cursor.execute(count_sql, tuple(count_params))
                total_count = cursor.fetchone()['total']

                # 添加分页限制
                offset = (page - 1) * limit
                sql += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cursor.execute(sql, tuple(params))
                result = cursor.fetchall()

            # 确保时间格式正确
            for item in result:
                if isinstance(item['added_time'], object) and hasattr(item['added_time'], 'strftime'):
                    item['added_time'] = item['added_time'].strftime('%Y-%m-%d %H:%M:%S')
                elif item['added_time'] and isinstance(item['added_time'], str):
                    # 如果已经是字符串格式，保持不变
                    pass

        return list(result), total_count

    def get_cart_filter_values(self, store: str, dimension: str,
                               search_params: Dict, column: str) -> List[Any]:
        """
        获取指定列的全部去重值，供前端筛选面板使用

        Args:
            store: 门店代码
            dimension: 维度类型
            search_params: 搜索/筛选参数（会自动排除当前列的 filter_<column>）
            column: 要取去重值的字段名

        Returns:
            去重值列表
        """
        if not column:
            return []

        # 排除当前列自身的筛选条件，避免自己被自己过滤
        filtered_search_params = {k: v for k, v in (search_params or {}).items()
                                  if k != 'filter_' + column}

        # 其他列直接从基础表取去重值
        db_field = self.FIELD_MAPPING.get(column)
        if not db_field:
            return []

        with db_cursor(dict_cursor=True) as cursor:
            sql = f"SELECT DISTINCT {db_field} AS col_value FROM crmapp_cart WHERE store = %s AND is_deleted = 0"
            params = [store]
            sql, params = self._apply_search_conditions(sql, params, filtered_search_params)
            sql += f" ORDER BY {db_field}"

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

        values = []
        for row in rows:
            val = row.get('col_value')
            if val is not None and val != '':
                values.append(val)
        return values

    def _apply_search_conditions(self, sql: str, params: List, search_params: Dict) -> Tuple[str, List]:
        """
        通用搜索/筛选条件拼接，用于复用 get_cart_data 和 get_cart_filter_values 的过滤逻辑
        """
        if not search_params:
            return sql, params

        # 搜索参数
        if search_params.get('cart_barcode'):
            barcode_list = parse_space(search_params['cart_barcode'])
            if barcode_list:
                or_conditions = []
                for barcode in barcode_list:
                    or_conditions.append("(barcode LIKE %s OR oe LIKE %s)")
                    params.extend([f'%{barcode}%', f'%{barcode}%'])
                sql += " AND (" + " OR ".join(or_conditions) + ")"

        if search_params.get('cart_oe'):
            oe_list = parse_space(search_params['cart_oe'])
            if oe_list:
                or_conditions = []
                for oe in oe_list:
                    or_conditions.append("oe LIKE %s")
                    params.append(f'%{oe}%')
                sql += " AND (" + " OR ".join(or_conditions) + ")"

        if search_params.get('cart_material_name'):
            name_list = parse_comma(search_params['cart_material_name'])
            if name_list:
                or_conditions = []
                for name in name_list:
                    or_conditions.append("material_name LIKE %s")
                    params.append(f'%{name}%')
                sql += " AND (" + " OR ".join(or_conditions) + ")"

        if search_params.get('cart_brand'):
            brand_list = parse_space(search_params['cart_brand'])
            if brand_list:
                or_conditions = []
                for brand in brand_list:
                    or_conditions.append("brand LIKE %s")
                    params.append(f'%{brand}%')
                sql += " AND (" + " OR ".join(or_conditions) + ")"

        if search_params.get('cart_tag'):
            tag_list = parse_space(search_params['cart_tag'])
            if tag_list:
                or_conditions = []
                for tag in tag_list:
                    or_conditions.append("tag LIKE %s")
                    params.append(f'%{tag}%')
                sql += " AND (" + " OR ".join(or_conditions) + ")"

        if search_params.get('cart_car_model'):
            car_model_list = parse_space(search_params['cart_car_model'])
            if car_model_list:
                or_conditions = []
                for car_model in car_model_list:
                    or_conditions.append("car_model LIKE %s")
                    params.append(f'%{car_model}%')
                sql += " AND (" + " OR ".join(or_conditions) + ")"

        if search_params.get('cart_car_brand'):
            car_brand_list = parse_space(search_params['cart_car_brand'])
            if car_brand_list:
                or_conditions = []
                for car_brand in car_brand_list:
                    or_conditions.append("car_brand LIKE %s")
                    params.append(f'%{car_brand}%')
                sql += " AND (" + " OR ".join(or_conditions) + ")"

        # 筛选参数 - 通用 filter_<field>
        for key in list(search_params.keys()):
            if key.startswith('filter_') and search_params.get(key):
                field = key[7:]
                db_field = self.FIELD_MAPPING.get(field)
                if not db_field:
                    continue
                value_list = search_params[key].split(',')
                if value_list:
                    placeholders = ','.join(['%s'] * len(value_list))
                    sql += f" AND {db_field} IN ({placeholders})"
                    params.extend(value_list)

        return sql, params

    def _build_order_clause(self, sort_field: str, sort_order: str) -> str:
        """
        构建排序子句

        Args:
            sort_field: 排序字段
            sort_order: 排序方向

        Returns:
            排序子句字符串
        """
        # 默认按加入时间倒序
        if not sort_field:
            return " ORDER BY added_time DESC"

        # 检查字段是否在允许的映射中
        db_field = self.FIELD_MAPPING.get(sort_field)
        if not db_field:
            return " ORDER BY added_time DESC"

        # 确定排序方向
        order_direction = "DESC" if sort_order and sort_order.lower() == "desc" else "ASC"

        return f" ORDER BY {db_field} {order_direction}"
