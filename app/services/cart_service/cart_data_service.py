"""
购物车基础数据服务
处理购物车数据的查询和基础处理逻辑
"""

import pymysql
import re
from typing import List, Dict, Any
from app.utils.database_connection import get_db_connection, db_cursor
from app.utils.search import parse_space, parse_comma


class CartDataService:
    """购物车基础数据服务类"""

    def get_cart_data(self, store: str, is_admin: bool = False, dimension: str = 'product', search_params: Dict = None) -> List[Dict[str, Any]]:
        """
        获取购物车数据 - 支持产品维度和供应商维度，支持搜索过滤

        Args:
            store: 门店代码
            is_admin: 是否为管理员
            dimension: 维度类型，'product' 或 'supplier'
            search_params: 搜索参数字典，可包含 cart_barcode, cart_oe, cart_material_name, cart_brand, cart_tag
        """
        # 使用上下文管理器确保连接正确关闭，避免连接泄漏
        with db_cursor(dict_cursor=True) as cursor:
            # 构建基础SQL查询
            sql = "SELECT * FROM crmapp_cart WHERE store = %s"
            params = [store]

            # 添加搜索条件
            if search_params:
                # 物料条码或品牌号码搜索 (cart_barcode) - 支持多行
                if search_params.get('cart_barcode'):
                    barcode_list = parse_space(search_params['cart_barcode'])
                    if barcode_list:
                        or_conditions = []
                        for barcode in barcode_list:
                            or_conditions.append("(barcode LIKE %s OR oe LIKE %s)")
                            params.extend([f'%{barcode}%', f'%{barcode}%'])
                        sql += " AND (" + " OR ".join(or_conditions) + ")"

                # OE号搜索 (cart_oe) - 支持多行
                if search_params.get('cart_oe'):
                    oe_list = parse_space(search_params['cart_oe'])
                    if oe_list:
                        or_conditions = []
                        for oe in oe_list:
                            or_conditions.append("oe LIKE %s")
                            params.append(f'%{oe}%')
                        sql += " AND (" + " OR ".join(or_conditions) + ")"

                # 物料名称搜索 (cart_material_name) - 支持多行
                if search_params.get('cart_material_name'):
                    name_list = parse_comma(search_params['cart_material_name'])
                    if name_list:
                        or_conditions = []
                        for name in name_list:
                            or_conditions.append("material_name LIKE %s")
                            params.append(f'%{name}%')
                        sql += " AND (" + " OR ".join(or_conditions) + ")"

                # 品牌搜索 (cart_brand) - 支持多行
                if search_params.get('cart_brand'):
                    brand_list = parse_space(search_params['cart_brand'])
                    if brand_list:
                        or_conditions = []
                        for brand in brand_list:
                            or_conditions.append("brand LIKE %s")
                            params.append(f'%{brand}%')
                        sql += " AND (" + " OR ".join(or_conditions) + ")"

                # 标签搜索 (cart_tag) - 支持多行
                if search_params.get('cart_tag'):
                    tag_list = parse_space(search_params['cart_tag'])
                    if tag_list:
                        or_conditions = []
                        for tag in tag_list:
                            or_conditions.append("tag LIKE %s")
                            params.append(f'%{tag}%')
                        sql += " AND (" + " OR ".join(or_conditions) + ")"

                # 车型搜索 (cart_car_model) - 支持多行
                if search_params.get('cart_car_model'):
                    car_model_list = parse_space(search_params['cart_car_model'])
                    if car_model_list:
                        or_conditions = []
                        for car_model in car_model_list:
                            or_conditions.append("car_model LIKE %s")
                            params.append(f'%{car_model}%')
                        sql += " AND (" + " OR ".join(or_conditions) + ")"

            # 添加排序
            sql += " ORDER BY added_time DESC"

            cursor.execute(sql, tuple(params))
            result = cursor.fetchall()

            # 确保时间格式正确
            for item in result:
                if isinstance(item['added_time'], object) and hasattr(item['added_time'], 'strftime'):
                    item['added_time'] = item['added_time'].strftime('%Y-%m-%d %H:%M:%S')
                elif item['added_time'] and isinstance(item['added_time'], str):
                    # 如果已经是字符串格式，保持不变
                    pass

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
