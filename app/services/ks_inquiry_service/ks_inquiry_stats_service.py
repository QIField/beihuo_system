# -*- coding:utf-8 -*-
"""
开思询价统计服务
处理 crmapp_ks_inquiry_detail 表的聚合统计业务逻辑
"""

from typing import List, Dict, Any, Optional
import json
import time
from app.utils.database_connection import db_cursor, db_query_one
from app.utils.common_util_module.sql_builder import build_order_by


def _get_row_value(row, key_index, key_name):
    """兼容字典游标与元组游标读取行数据"""
    if isinstance(row, dict):
        return row.get(key_name) or ''
    return row[key_index] if row else ''


class KsInquiryStatsService:
    """
    开思询价统计服务
    """

    @staticmethod
    def get_oe_stats(
        inquiry_id: str = '',
        parts_num: str = '',
        parts_name: str = '',
        brand_name: str = '',
        brand: str = '',
        seller_status: str = '',
        begin_date: str = '',
        end_date: str = '',
        company: str = '',
        page: int = 1,
        page_size: int = 200,
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        获取OE号统计维度（按partsNum分组聚合）

        Args:
            sort_column: 排序列名
            sort_dir: 排序方向 (asc/desc)
            column_filters: 列头下拉多选筛选，格式 {前端列名: [选中值列表]}

        Returns:
            Dict: {list: 数据列表, total: 总条数, page: 当前页, page_size: 每页条数}
        """
        start_time = time.time()

        conditions, params = [], []

        # 基础查询条件
        if inquiry_id:    conditions.append("inquiryId LIKE %s");           params.append(f"%{inquiry_id}%")
        if parts_num:     conditions.append("partsNum LIKE %s");            params.append(f"%{parts_num}%")
        if parts_name:    conditions.append("resolve_parts_name LIKE %s");  params.append(f"%{parts_name}%")
        if brand_name:    conditions.append("brandName LIKE %s");           params.append(f"%{brand_name}%")
        if brand:         conditions.append("brandNormalized = %s");        params.append(brand)
        if seller_status: conditions.append("display_seller_status LIKE %s"); params.append(f"%{seller_status}%")
        if begin_date:    conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:      conditions.append("quote_date <= %s");            params.append(end_date)
        if company:       conditions.append("company = %s");                params.append(company)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 列头下拉全量筛选（非聚合列进 WHERE，聚合列进 HAVING）
        having_conditions = []
        having_params = []
        if column_filters:
            for col_id, values in column_filters.items():
                placeholders = ', '.join(['%s'] * len(values))
                if col_id == 'partsNum':
                    conditions.append(f"partsNum IN ({placeholders})")
                    params.extend(values)
                elif col_id == 'partsName':
                    conditions.append(f"resolve_parts_name IN ({placeholders})")
                    params.extend(values)
                elif col_id in ('count', 'unquotedProducts'):
                    having_conditions.append(f"{col_id} IN ({placeholders})")
                    having_params.extend(values)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        having_clause = "HAVING " + " AND ".join(having_conditions) if having_conditions else ""

        # 查询不同OE号的总数量
        count_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT
                    partsNum,
                    COUNT(DISTINCT inquiryId) as count,
                    MAX(unquoted_products) as unquotedProducts
                FROM crmapp_ks_inquiry_detail
                WHERE {where_clause}
                GROUP BY partsNum
                {having_clause}
            ) t
        """

        # OE统计排序：白名单映射（前端列名 -> SQL列名）
        oe_column_map = {
            'partsNum': 'partsNum',
            'count': 'count',
            'partsName': 'partsName',
            'unquotedProducts': 'unquotedProducts'
        }
        order_by = build_order_by(
            sort_column, sort_dir, oe_column_map,
            numeric_columns={'count', 'unquotedProducts'},
            default='count DESC'
        )

        # 查询分组聚合数据
        data_sql = f"""
            SELECT * FROM (
                SELECT
                    partsNum,
                    COUNT(DISTINCT inquiryId) as count,
                    MAX(resolve_parts_name) as partsName,
                    MAX(unquoted_products) as unquotedProducts
                FROM crmapp_ks_inquiry_detail
                WHERE {where_clause}
                GROUP BY partsNum
                {having_clause}
            ) t
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """

        # 查询总条数
        count_params = params.copy()
        count_params.extend(having_params)
        count_result = db_query_one(count_sql, tuple(count_params), dict_cursor=False)
        if count_result is None:
            total = 0
        elif isinstance(count_result, dict):
            total = count_result.get('COUNT(*)', 0) or count_result.get('count', 0)
        else:
            total = count_result[0] if count_result else 0

        # 查询分页数据
        offset = (page - 1) * page_size
        data_params = params.copy()
        data_params.extend(having_params)
        data_params.append(page_size)
        data_params.append(offset)

        with db_cursor() as cursor:
            cursor.execute(data_sql, data_params)
            rows = cursor.fetchall()

            columns = ['partsNum', 'count', 'partsName', 'unquotedProducts']
            result = []
            for row in rows:
                if isinstance(row, dict):
                    record = row
                else:
                    record = dict(zip(columns, row))
                result.append(record)

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryStatsService] OE统计查询完成: 耗时 {elapsed_time:.2f} ms, 总条数: {total}, 返回 {len(result)} 条记录")

            return {
                'list': result,
                'total': total,
                'page': page,
                'page_size': page_size
            }

    @staticmethod
    def get_customer_stats_by_oe(
        parts_num: str = '',
        inquiry_id: str = '',
        parts_name: str = '',
        brand_name: str = '',
        brand: str = '',
        seller_status: str = '',
        begin_date: str = '',
        end_date: str = '',
        company: str = '',
        page: int = 1,
        page_size: int = 200,
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        获取指定OE号在日期范围内各客户的出现次数（按次数降序）

        Returns:
            Dict: {list: [{customerName, count}], total, page, page_size}
        """
        start_time = time.time()

        conditions, params = [], []

        # 基础查询条件
        if inquiry_id:    conditions.append("inquiryId LIKE %s");           params.append(f"%{inquiry_id}%")
        if parts_num:     conditions.append("partsNum = %s");               params.append(parts_num)
        if parts_name:    conditions.append("resolve_parts_name LIKE %s");  params.append(f"%{parts_name}%")
        if brand_name:    conditions.append("brandName LIKE %s");           params.append(f"%{brand_name}%")
        if brand:         conditions.append("brandNormalized = %s");        params.append(brand)
        if seller_status: conditions.append("display_seller_status LIKE %s"); params.append(f"%{seller_status}%")
        if begin_date:    conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:      conditions.append("quote_date <= %s");            params.append(end_date)
        if company:       conditions.append("company = %s");                params.append(company)

        # 客户名称不能为空
        conditions.append("COALESCE(TRIM(garage_company_name), '') != ''")

        # 列头下拉全量筛选（非聚合列进 WHERE，聚合列进 HAVING）
        having_conditions = []
        having_params = []
        if column_filters:
            for col_id, values in column_filters.items():
                placeholders = ', '.join(['%s'] * len(values))
                if col_id == 'customerName':
                    conditions.append(f"garage_company_name IN ({placeholders})")
                    params.extend(values)
                elif col_id == 'count':
                    having_conditions.append(f"count IN ({placeholders})")
                    having_params.extend(values)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        having_clause = "HAVING " + " AND ".join(having_conditions) if having_conditions else ""

        # 排序白名单（前端列名 -> SQL列名）
        customer_column_map = {
            'customerName': 'customerName',
            'count': 'count'
        }
        order_by = build_order_by(
            sort_column, sort_dir, customer_column_map,
            numeric_columns={'count'},
            default='count DESC, customerName ASC'
        )

        count_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT garage_company_name,
                       COUNT(DISTINCT inquiryId) as count
                FROM crmapp_ks_inquiry_detail
                WHERE {where_clause}
                GROUP BY garage_company_name
                {having_clause}
            ) t
        """

        data_sql = f"""
            SELECT
                garage_company_name AS customerName,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY garage_company_name
            {having_clause}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """

        count_params = params.copy()
        count_params.extend(having_params)
        count_result = db_query_one(count_sql, tuple(count_params), dict_cursor=False)
        if count_result is None:
            total = 0
        elif isinstance(count_result, dict):
            total = count_result.get('COUNT(*)', 0) or count_result.get('count', 0)
        else:
            total = count_result[0] if count_result else 0

        offset = (page - 1) * page_size
        data_params = params.copy()
        data_params.extend(having_params)
        data_params.append(page_size)
        data_params.append(offset)

        with db_cursor() as cursor:
            cursor.execute(data_sql, data_params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append(row)
                else:
                    result.append(dict(zip(['customerName', 'count'], row)))

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryStatsService] OE客户统计查询完成: OE={parts_num}, 耗时 {elapsed_time:.2f} ms, 总条数: {total}, 返回 {len(result)} 条记录")

            return {
                'list': result,
                'total': total,
                'page': page,
                'page_size': page_size
            }

    @staticmethod
    def get_customer_stats(
        garage_name: str = '',
        begin_date: str = '',
        end_date: str = '',
        company: str = '',
        page: int = 1,
        page_size: int = 200,
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        获取客户维度列表（按garage_company_name分组聚合，询价次数按inquiryId去重）

        Returns:
            Dict: {list: [{customerName, count}], total, page, page_size}
        """
        start_time = time.time()

        conditions, params = [], []

        # 基础查询条件
        if garage_name:
            conditions.append("garage_company_name LIKE %s")
            params.append(f"%{garage_name}%")

        if begin_date:
            conditions.append("quote_date >= %s")
            params.append(begin_date)

        if end_date:
            conditions.append("quote_date <= %s")
            params.append(end_date)

        if company:
            conditions.append("company = %s")
            params.append(company)

        # 客户名称不能为空
        conditions.append("COALESCE(TRIM(garage_company_name), '') != ''")

        # 列头下拉筛选（非聚合列）
        customer_filter_column_map = {
            'customerName': 'garage_company_name'
        }
        if column_filters:
            if isinstance(column_filters, str):
                try:
                    column_filters = json.loads(column_filters)
                except Exception:
                    column_filters = {}
            for col_id, values in column_filters.items():
                if not values:
                    continue
                if col_id in customer_filter_column_map:
                    db_col = customer_filter_column_map[col_id]
                    placeholders = ', '.join(['%s'] * len(values))
                    conditions.append(f"{db_col} IN ({placeholders})")
                    params.extend(values)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        count_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT garage_company_name
                FROM crmapp_ks_inquiry_detail
                WHERE {where_clause}
                GROUP BY garage_company_name
            ) t
        """

        # 排序列映射
        customer_column_map = {
            'customerName': 'customerName',
            'count': 'COUNT(DISTINCT inquiryId)'
        }
        order_by = build_order_by(
            sort_column, sort_dir, customer_column_map,
            numeric_columns={'count'},
            default='COUNT(DISTINCT inquiryId) DESC, customerName ASC'
        )

        data_sql = f"""
            SELECT
                garage_company_name AS customerName,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY garage_company_name
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """

        count_result = db_query_one(count_sql, tuple(params), dict_cursor=False)
        if count_result is None:
            total = 0
        elif isinstance(count_result, dict):
            total = count_result.get('COUNT(*)', 0) or count_result.get('count', 0)
        else:
            total = count_result[0] if count_result else 0

        offset = (page - 1) * page_size
        data_params = params.copy()
        data_params.append(page_size)
        data_params.append(offset)

        with db_cursor() as cursor:
            cursor.execute(data_sql, data_params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append(row)
                else:
                    result.append(dict(zip(['customerName', 'count'], row)))

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryStatsService] 客户统计查询完成: 耗时 {elapsed_time:.2f} ms, 总条数: {total}, 返回 {len(result)} 条记录")

            return {
                'list': result,
                'total': total,
                'page': page,
                'page_size': page_size
            }

    @staticmethod
    def get_engine_chassis_list(
        engine: str = '',
        chassis: str = '',
        vin: str = '',
        begin_date: str = '',
        end_date: str = '',
        company: str = '',
        page: int = 1,
        page_size: int = 200
    ) -> Dict[str, Any]:
        """
        获取发动机及底盘维度列表（按engine+chassis组合展示，不去重）

        Returns:
            Dict: {list: 数据列表, total: 总条数, page: 当前页, page_size: 每页条数}
        """
        start_time = time.time()

        conditions = []
        params = []

        if engine:
            conditions.append("engine LIKE %s")
            params.append(f"%{engine}%")

        if chassis:
            conditions.append("chassis LIKE %s")
            params.append(f"%{chassis}%")

        if vin:
            conditions.append("vin LIKE %s")
            params.append(f"%{vin}%")

        if begin_date:
            conditions.append("quote_date >= %s")
            params.append(begin_date)

        if end_date:
            conditions.append("quote_date <= %s")
            params.append(end_date)

        if company:
            conditions.append("company = %s")
            params.append(company)

        conditions.append("""
            (
                COALESCE(TRIM(engine), '') != ''
                OR COALESCE(TRIM(chassis), '') != ''
                OR COALESCE(TRIM(vin), '') != ''
                OR COALESCE(TRIM(production_date), '') != ''
            )
        """)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        count_sql = f"""
            SELECT COUNT(*) FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
        """

        data_sql = f"""
            SELECT
                engine,
                chassis,
                vin,
                production_date AS vehicleProductionDate
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            ORDER BY engine, chassis, vin
            LIMIT %s OFFSET %s
        """

        count_result = db_query_one(count_sql, tuple(params), dict_cursor=False)
        if count_result is None:
            total = 0
        elif isinstance(count_result, dict):
            total = count_result.get('COUNT(*)', 0) or count_result.get('count', 0)
        else:
            total = count_result[0] if count_result else 0

        offset = (page - 1) * page_size
        data_params = params.copy()
        data_params.append(page_size)
        data_params.append(offset)

        with db_cursor() as cursor:
            cursor.execute(data_sql, data_params)
            rows = cursor.fetchall()

            columns = ['engine', 'chassis', 'vin', 'vehicleProductionDate']
            result = []
            for row in rows:
                if isinstance(row, dict):
                    record = row
                else:
                    record = dict(zip(columns, row))
                result.append(record)

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryStatsService] 发动机底盘查询完成: 耗时 {elapsed_time:.2f} ms, 总条数: {total}, 返回 {len(result)} 条记录")

            return {
                'list': result,
                'total': total,
                'page': page,
                'page_size': page_size
            }

    @staticmethod
    def get_garage_chassis_stats(
        garage_name: str = '',
        company: str = '',
        begin_date: str = '',
        end_date: str = '',
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        按修理厂统计底盘出现次数

        Args:
            garage_name: 修理厂名称
            company: 用户门店/组织
            begin_date: 开始日期
            end_date: 结束日期
            sort_column: 排序列名
            sort_dir: 排序方向 (asc/desc)
            column_filters: 列头下拉多选筛选，格式 {前端列名: [选中值列表]}

        Returns:
            Dict: {list: 统计列表}
        """
        start_time = time.time()

        conditions = ["COALESCE(TRIM(garage_company_name), '') != ''"]
        params = []

        if garage_name: conditions.append("garage_company_name LIKE %s"); params.append(f"%{garage_name}%")
        if company:     conditions.append("company = %s");                params.append(company)
        if begin_date:  conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:    conditions.append("quote_date <= %s");            params.append(end_date)
        conditions.append("COALESCE(TRIM(chassis), '') != ''")

        # 列头下拉全量筛选
        having_conditions = []
        if column_filters:
            for col_id, values in column_filters.items():
                placeholders = ', '.join(['%s'] * len(values))
                if col_id in ('carBrandName', 'chassis'):
                    db_col = 'car_brand_name' if col_id == 'carBrandName' else col_id
                    conditions.append(f"{db_col} IN ({placeholders})")
                    params.extend(values)
                elif col_id == 'count':
                    having_conditions.append(f"COUNT(DISTINCT inquiryId) IN ({placeholders})")
                    params.extend(values)

        where_clause = " AND ".join(conditions)
        having_clause = "HAVING " + " AND ".join(having_conditions) if having_conditions else ""

        chassis_column_map = {
            'carBrandName': 'car_brand_name',
            'chassis': 'chassis',
            'count': 'COUNT(DISTINCT inquiryId)'
        }
        order_by = build_order_by(
            sort_column, sort_dir, chassis_column_map,
            numeric_columns={'count'},
            default='COUNT(DISTINCT inquiryId) DESC, car_brand_name, chassis'
        )

        sql = f"""
            SELECT
                car_brand_name AS carBrandName,
                chassis,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY car_brand_name, chassis
            {having_clause}
            ORDER BY {order_by}
        """

        with db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            result = [{
                'carBrandName': _get_row_value(r, 0, 'carBrandName'),
                'chassis': _get_row_value(r, 1, 'chassis'),
                'count': _get_row_value(r, 2, 'count') or 0
            } for r in rows]

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryStatsService] 修理厂底盘统计完成: 耗时 {elapsed_time:.2f} ms, 返回 {len(result)} 条记录")

            return {'list': result}

    @staticmethod
    def get_garage_engine_stats(
        garage_name: str = '',
        company: str = '',
        begin_date: str = '',
        end_date: str = '',
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        按修理厂统计发动机出现次数

        Args:
            garage_name: 修理厂名称
            company: 用户门店/组织
            begin_date: 开始日期
            end_date: 结束日期
            sort_column: 排序列名
            sort_dir: 排序方向 (asc/desc)
            column_filters: 列头下拉多选筛选，格式 {前端列名: [选中值列表]}

        Returns:
            Dict: {list: 统计列表}
        """
        start_time = time.time()

        conditions = ["COALESCE(TRIM(garage_company_name), '') != ''"]
        params = []

        if garage_name:
            conditions.append("garage_company_name LIKE %s")
            params.append(f"%{garage_name}%")

        if company:
            conditions.append("company = %s")
            params.append(company)

        if begin_date:  conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:    conditions.append("quote_date <= %s");            params.append(end_date)
        conditions.append("COALESCE(TRIM(engine), '') != ''")

        # 列头下拉全量筛选
        having_conditions = []
        if column_filters:
            for col_id, values in column_filters.items():
                placeholders = ', '.join(['%s'] * len(values))
                if col_id in ('carBrandName', 'engine'):
                    db_col = 'car_brand_name' if col_id == 'carBrandName' else col_id
                    conditions.append(f"{db_col} IN ({placeholders})")
                    params.extend(values)
                elif col_id == 'count':
                    having_conditions.append(f"COUNT(DISTINCT inquiryId) IN ({placeholders})")
                    params.extend(values)

        where_clause = " AND ".join(conditions)
        having_clause = "HAVING " + " AND ".join(having_conditions) if having_conditions else ""

        engine_column_map = {
            'carBrandName': 'car_brand_name',
            'engine': 'engine',
            'count': 'COUNT(DISTINCT inquiryId)'
        }
        order_by = build_order_by(
            sort_column, sort_dir, engine_column_map,
            numeric_columns={'count'},
            default='COUNT(DISTINCT inquiryId) DESC, car_brand_name, engine'
        )

        sql = f"""
            SELECT
                car_brand_name AS carBrandName,
                engine,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY car_brand_name, engine
            {having_clause}
            ORDER BY {order_by}
        """

        with db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            result = [{
                'carBrandName': _get_row_value(r, 0, 'carBrandName'),
                'engine': _get_row_value(r, 1, 'engine'),
                'count': _get_row_value(r, 2, 'count') or 0
            } for r in rows]

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryStatsService] 修理厂发动机统计完成: 耗时 {elapsed_time:.2f} ms, 返回 {len(result)} 条记录")

            return {'list': result}

    @staticmethod
    def get_garage_oenum_stats(
        garage_name: str = '',
        company: str = '',
        begin_date: str = '',
        end_date: str = '',
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        按修理厂统计OE号码出现次数

        Args:
            garage_name: 修理厂名称
            company: 用户门店/组织
            begin_date: 开始日期
            end_date: 结束日期
            sort_column: 排序列名
            sort_dir: 排序方向 (asc/desc)
            column_filters: 列头下拉多选筛选，格式 {前端列名: [选中值列表]}

        Returns:
            Dict: {list: 统计列表}
        """
        start_time = time.time()

        conditions = ["COALESCE(TRIM(garage_company_name), '') != ''"]
        params = []

        if garage_name:
            conditions.append("garage_company_name LIKE %s")
            params.append(f"%{garage_name}%")

        if company:     conditions.append("company = %s");                params.append(company)
        if begin_date:  conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:    conditions.append("quote_date <= %s");            params.append(end_date)
        conditions.append("COALESCE(TRIM(partsNum), '') != ''")

        # 列头下拉全量筛选
        having_conditions = []
        if column_filters:
            for col_id, values in column_filters.items():
                placeholders = ', '.join(['%s'] * len(values))
                if col_id in ('carBrandName', 'partsNum'):
                    db_col = 'car_brand_name' if col_id == 'carBrandName' else col_id
                    conditions.append(f"{db_col} IN ({placeholders})")
                    params.extend(values)
                elif col_id == 'count':
                    having_conditions.append(f"COUNT(DISTINCT inquiryId) IN ({placeholders})")
                    params.extend(values)

        where_clause = " AND ".join(conditions)
        having_clause = "HAVING " + " AND ".join(having_conditions) if having_conditions else ""

        oenum_column_map = {
            'carBrandName': 'car_brand_name',
            'partsNum': 'partsNum',
            'count': 'COUNT(DISTINCT inquiryId)'
        }
        order_by = build_order_by(
            sort_column, sort_dir, oenum_column_map,
            numeric_columns={'count'},
            default='COUNT(DISTINCT inquiryId) DESC, car_brand_name, partsNum'
        )

        sql = f"""
            SELECT
                car_brand_name AS carBrandName,
                partsNum,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY car_brand_name, partsNum
            {having_clause}
            ORDER BY {order_by}
        """

        with db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            result = [{
                'carBrandName': _get_row_value(r, 0, 'carBrandName'),
                'partsNum': _get_row_value(r, 1, 'partsNum'),
                'count': _get_row_value(r, 2, 'count') or 0
            } for r in rows]

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryStatsService] 修理厂OE号码统计完成: 耗时 {elapsed_time:.2f} ms, 返回 {len(result)} 条记录")

            return {'list': result}

    @staticmethod
    def get_customer_oenum_stats(
        garage_name: str = '',
        company: str = '',
        begin_date: str = '',
        end_date: str = '',
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        按客户统计OE号码出现次数（使用 resolve_parts_num / resolve_parts_name）

        Args:
            garage_name: 客户名称
            company: 用户门店/组织
            begin_date: 开始日期
            end_date: 结束日期
            sort_column: 排序列名
            sort_dir: 排序方向 (asc/desc)
            column_filters: 列头下拉多选筛选，格式 {前端列名: [选中值列表]}

        Returns:
            Dict: {list: 统计列表}
        """
        start_time = time.time()

        conditions = ["COALESCE(TRIM(garage_company_name), '') != ''"]
        params = []

        if garage_name:
            conditions.append("garage_company_name LIKE %s")
            params.append(f"%{garage_name}%")

        if company:     conditions.append("company = %s");                params.append(company)
        if begin_date:  conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:    conditions.append("quote_date <= %s");            params.append(end_date)
        conditions.append("COALESCE(TRIM(resolve_parts_num), '') != ''")

        # 列头下拉全量筛选
        having_conditions = []
        if column_filters:
            for col_id, values in column_filters.items():
                if not values:
                    continue
                placeholders = ', '.join(['%s'] * len(values))
                if col_id == 'carBrandName':
                    conditions.append(f"car_brand_name IN ({placeholders})")
                    params.extend(values)
                elif col_id == 'partsNum':
                    conditions.append(f"resolve_parts_num IN ({placeholders})")
                    params.extend(values)
                elif col_id == 'partsName':
                    conditions.append(f"resolve_parts_name IN ({placeholders})")
                    params.extend(values)
                elif col_id == 'count':
                    having_conditions.append(f"COUNT(DISTINCT inquiryId) IN ({placeholders})")
                    params.extend(values)

        where_clause = " AND ".join(conditions)
        having_clause = "HAVING " + " AND ".join(having_conditions) if having_conditions else ""

        oenum_column_map = {
            'carBrandName': 'car_brand_name',
            'partsNum': 'resolve_parts_num',
            'partsName': 'resolve_parts_name',
            'count': 'COUNT(DISTINCT inquiryId)'
        }
        order_by = build_order_by(
            sort_column, sort_dir, oenum_column_map,
            numeric_columns={'count'},
            default='COUNT(DISTINCT inquiryId) DESC, car_brand_name, resolve_parts_num'
        )

        sql = f"""
            SELECT
                car_brand_name AS carBrandName,
                resolve_parts_num AS partsNum,
                MAX(resolve_parts_name) AS partsName,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY car_brand_name, resolve_parts_num
            {having_clause}
            ORDER BY {order_by}
        """

        with db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            result = [{
                'carBrandName': _get_row_value(r, 0, 'carBrandName'),
                'partsNum': _get_row_value(r, 1, 'partsNum'),
                'partsName': _get_row_value(r, 2, 'partsName'),
                'count': _get_row_value(r, 3, 'count') or 0
            } for r in rows]

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryStatsService] 客户OE号码统计完成: 耗时 {elapsed_time:.2f} ms, 返回 {len(result)} 条记录")

            return {'list': result}
