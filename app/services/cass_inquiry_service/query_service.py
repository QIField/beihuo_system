"""
修理厂询价单查询服务

数据源：cass_inquiry_quote 表（fsbbr_data 线上库，由修理厂询单爬虫写入）
连接方式：PyMySQL get_db_connection，跟随启动菜单选择（选线上库才有数据）
"""

import json
from datetime import datetime, timedelta

from app.utils.database_connection import db_cursor


class CassInquiryQueryService:
    """修理厂询单报价数据查询服务"""

    # 允许排序的列白名单（数值型列用 col+0 排序，避免 varchar 字典序问题）
    NUMERIC_SORT_COLUMNS = {'num', 'price_4s', 'seller_price'}
    SORTABLE_COLUMNS = NUMERIC_SORT_COLUMNS | {
        'inquiry_date', 'inquiry_id', 'decode_num',
        'brand_name', 'quality_name', 'store_name', 'created_at',
    }

    # 允许列头菜单筛选的列白名单（全部业务数据列，排除前端行号与表外字段）
    FILTERABLE_COLUMNS = SORTABLE_COLUMNS | {
        'parts_name', 'merchant_parts_num', 'car_model', 'description', 'vin',
        'location_name', 'selling_point_tag', 'replacement', 'remark',
    }

    def query_quotes(self, page=1, page_size=50, inquiry_start=None, inquiry_end=None,
                     decode_num=None, brand_name=None, store_name=None, inquiry_id=None,
                     sort_column=None, sort_dir=None, column_filters=None):
        """
        分页查询修理厂询单报价数据

        :param page: 页码（从1开始）
        :param page_size: 每页条数
        :param inquiry_start: 询单日期范围-开始（YYYY-MM-DD）
        :param inquiry_end: 询单日期范围-结束（YYYY-MM-DD）
        :param decode_num: 译码OE号（模糊匹配）
        :param brand_name: 品牌名称（模糊匹配）
        :param store_name: 供应商名称（模糊匹配）
        :param inquiry_id: 询单ID（模糊匹配）
        :param sort_column: 排序列（白名单内）
        :param sort_dir: 排序方向（asc/desc）
        :param column_filters: 列头菜单筛选 JSON（如 {"brand_name": ["博世"]}，列间 AND）
        :return: {'code': 0, 'data': {'list': [...], 'total': n, 'page': p, 'page_size': s}}
        """
        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 50), 1), 200)

        where_sql, params = self._build_where(inquiry_start, inquiry_end, decode_num,
                                              brand_name, store_name, inquiry_id,
                                              column_filters=column_filters)
        order_sql = self._build_order(sort_column, sort_dir)

        total = self._count(where_sql, params)
        rows = []
        if total > 0:
            offset = (page - 1) * page_size
            sql = f"""
                SELECT id, crawl_date, inquiry_id, quote_id, num, vin, car_model,
                       description, inquiry_date, decode_num, merchant_parts_num,
                       price_4s, parts_name, brand_name, quality_name, store_name,
                       seller_price, remark, selling_point_tag, location_name,
                       replacement, created_at, updated_at
                FROM cass_inquiry_quote
                {where_sql}
                {order_sql}
                LIMIT %s OFFSET %s
            """
            with db_cursor(dict_cursor=True) as cursor:
                cursor.execute(sql, (*params, page_size, offset))
                rows = cursor.fetchall()

        for row in rows:
            self._format_row(row)

        return {
            'code': 0,
            'data': {
                'list': rows,
                'total': total,
                'page': page,
                'page_size': page_size,
            }
        }

    def _build_where(self, inquiry_start, inquiry_end, decode_num, brand_name, store_name, inquiry_id,
                     column_filters=None, exclude_filter_column=None):
        """
        构建查询条件 SQL 与参数

        询单日期为 varchar（如 2026-10-1522:31），按字符串前缀比较：
        开始日用 >=，结束日用 <（结束日+1天），保证结束日当天数据完整包含

        :param column_filters: 列头菜单筛选 JSON（列间 AND，白名单外字段忽略）
        :param exclude_filter_column: 从 column_filters 中排除的列（候选值级联时排除本列）
        :return: (where_sql, params)，where_sql 以 WHERE 开头或为空字符串
        """
        conditions = []
        params = []

        if inquiry_start:
            conditions.append("inquiry_date >= %s")
            params.append(self._validate_date(inquiry_start, 'inquiry_start'))
        if inquiry_end:
            end_next = datetime.strptime(self._validate_date(inquiry_end, 'inquiry_end'), '%Y-%m-%d') + timedelta(days=1)
            conditions.append("inquiry_date < %s")
            params.append(end_next.strftime('%Y-%m-%d'))
        if decode_num:
            conditions.append("decode_num LIKE %s")
            params.append(f"%{decode_num.strip()}%")
        if brand_name:
            conditions.append("brand_name LIKE %s")
            params.append(f"%{brand_name.strip()}%")
        if store_name:
            conditions.append("store_name LIKE %s")
            params.append(f"%{store_name.strip()}%")
        if inquiry_id:
            conditions.append("inquiry_id LIKE %s")
            params.append(f"%{inquiry_id.strip()}%")

        self._append_column_filter_conditions(conditions, params, column_filters, exclude_filter_column)

        if not conditions:
            return "", params
        return "WHERE " + " AND ".join(conditions), params

    def _append_column_filter_conditions(self, conditions, params, column_filters, exclude_column=None):
        """将 column_filters 解析为 IN 条件追加到查询（白名单外字段与非空值非法时忽略）"""
        for field, values in self._parse_column_filters(column_filters):
            if exclude_column and field == exclude_column:
                continue
            placeholders = ", ".join(["%s"] * len(values))
            conditions.append(f"`{field}` IN ({placeholders})")
            params.extend(values)

    def _parse_column_filters(self, column_filters):
        """
        解析 column_filters JSON 为 [(field, [values])]

        仅保留白名单列；值统一转字符串并剔除空值
        """
        if not column_filters:
            return []
        try:
            filters = json.loads(column_filters)
        except (TypeError, ValueError):
            return []
        if not isinstance(filters, dict):
            return []

        result = []
        for field, values in filters.items():
            if field not in self.FILTERABLE_COLUMNS or not isinstance(values, list):
                continue
            str_values = [str(v).strip() for v in values if v is not None and str(v).strip() != '']
            if str_values:
                result.append((field, str_values))
        return result

    def filter_values(self, column, inquiry_start=None, inquiry_end=None, decode_num=None,
                      brand_name=None, store_name=None, inquiry_id=None, column_filters=None):
        """
        查询某列的全量去重候选值及出现次数（供列头菜单筛选勾选）

        候选值按"其他列已生效筛选 + 左侧面板条件"级联，本列自身条件不参与

        :return: {'code': 0, 'data': {'values': [{'value': v, 'count': n}, ...]}}
        """
        if column not in self.FILTERABLE_COLUMNS:
            raise ValueError(f"不支持的筛选列: {column}")

        where_sql, params = self._build_where(inquiry_start, inquiry_end, decode_num,
                                              brand_name, store_name, inquiry_id,
                                              column_filters=column_filters,
                                              exclude_filter_column=column)
        sql = (f"SELECT `{column}`, COUNT(*) AS cnt FROM cass_inquiry_quote {where_sql} "
               f"GROUP BY `{column}` ORDER BY `{column}`")
        with db_cursor(dict_cursor=False) as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

        values = [
            {'value': row[0], 'count': row[1]}
            for row in rows
            if row[0] is not None and str(row[0]).strip() != ''
        ]
        return {'code': 0, 'data': {'values': values}}

    def _build_order(self, sort_column, sort_dir):
        """
        构建排序 SQL，非白名列或非法方向回落默认排序

        :return: ORDER BY 子句（含兜底排序列保证分页稳定）
        """
        default_order = "ORDER BY inquiry_date DESC, inquiry_id DESC, id DESC"
        if sort_column not in self.SORTABLE_COLUMNS:
            return default_order
        # 数值型 varchar 列用 col+0 转数值比较，避免 '9' > '128' 的字典序问题
        column = f"`{sort_column}` + 0" if sort_column in self.NUMERIC_SORT_COLUMNS else f"`{sort_column}`"
        direction = "DESC" if str(sort_dir or '').upper() == 'DESC' else "ASC"
        return f"ORDER BY {column} {direction}, id DESC"

    def _count(self, where_sql, params):
        """统计满足条件的总条数"""
        sql = f"SELECT COUNT(*) FROM cass_inquiry_quote {where_sql}"
        with db_cursor(dict_cursor=False) as cursor:
            cursor.execute(sql, tuple(params))
            return cursor.fetchone()[0]

    @staticmethod
    def _validate_date(value, field):
        """校验日期格式（YYYY-MM-DD），非法格式抛出 ValueError"""
        try:
            return datetime.strptime(value.strip(), '%Y-%m-%d').strftime('%Y-%m-%d')
        except (TypeError, ValueError):
            raise ValueError(f"{field} 日期格式错误，应为 YYYY-MM-DD")

    @staticmethod
    def _format_row(row):
        """格式化行数据：日期时间转字符串"""
        for key in ('crawl_date', 'created_at', 'updated_at'):
            if row.get(key) and hasattr(row[key], 'strftime'):
                row[key] = row[key].strftime('%Y-%m-%d') if key == 'crawl_date' \
                    else row[key].strftime('%Y-%m-%d %H:%M:%S')
