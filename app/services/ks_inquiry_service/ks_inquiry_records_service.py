# -*- coding:utf-8 -*-
"""
开思询价明细查询服务
处理 crmapp_ks_inquiry_detail 表的查询业务逻辑
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import time
from app.utils.database_connection import db_cursor, db_query_one
from app.utils.common_util_module.sql_builder import build_order_by


class KsInquiryRecordsService:
    """
    开思询价明细查询服务
    """

    @staticmethod
    def get_records(
        inquiry_id: str = '',
        parts_num: str = '',
        parts_name: str = '',
        brand_name: str = '',
        brand: str = '',  # 品牌筛选（brandNormalized，精准匹配）
        seller_status: str = '',
        car_brand_name: str = '',  # 车辆品牌筛选
        garage_name: str = '',  # 客户名称筛选（garage_company_name）
        begin_date: str = '',
        end_date: str = '',
        company: str = '',
        page: int = 1,
        page_size: int = 200,
        sort_column: str = '',
        sort_dir: str = ''
    ) -> Dict[str, Any]:
        """
        获取开思询价明细列表（支持分页）

        Args:
            inquiry_id: 询价单号
            parts_num: OE号
            parts_name: 配件名称
            brand_name: 品牌
            brand: 品牌筛选（brandNormalized，精准匹配）
            seller_status: 卖家状态
            car_brand_name: 车辆品牌筛选
            garage_name: 客户名称筛选（garage_company_name）
            begin_date: 开始日期 (yyyy-MM-dd)
            end_date: 结束日期 (yyyy-MM-dd)
            company: 用户门店/组织
            page: 页码（从1开始）
            page_size: 每页条数
            sort_column: 排序列名
            sort_dir: 排序方向 (asc/desc)

        Returns:
            Dict: {list: 数据列表, total: 总条数, page: 当前页, page_size: 每页条数}
        """
        start_time = time.time()

        conditions = []
        params = []

        # 构建查询条件
        if inquiry_id:
            conditions.append("inquiryId LIKE %s")
            params.append(f"%{inquiry_id}%")

        if parts_num:
            conditions.append("partsNum LIKE %s")
            params.append(f"%{parts_num}%")

        if parts_name:
            conditions.append("partsName LIKE %s")
            params.append(f"%{parts_name}%")

        if brand_name:
            conditions.append("brandName LIKE %s")
            params.append(f"%{brand_name}%")

        if brand:
            # 品牌筛选（brandNormalized，精准匹配）
            conditions.append("brandNormalized = %s")
            params.append(brand)

        if seller_status:
            conditions.append("display_seller_status LIKE %s")
            params.append(f"%{seller_status}%")

        if car_brand_name:
            conditions.append("car_brand_name = %s")
            params.append(car_brand_name)

        if garage_name:
            conditions.append("garage_company_name LIKE %s")
            params.append(f"%{garage_name}%")

        if begin_date:
            conditions.append("quote_date >= %s")
            params.append(begin_date)

        if end_date:
            conditions.append("quote_date <= %s")
            params.append(end_date)

        # 添加门店/组织筛选（只展示用户对应门店的数据）
        if company:
            conditions.append("company = %s")
            params.append(company)

        # 构建 SQL
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 先查询总条数
        count_sql = f"""
            SELECT COUNT(*) FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
        """

        # 排序：白名单映射（前端列名 -> 数据库列名）
        records_column_map = {
            'inquiryId': 'inquiryId',
            'partsNum': 'partsNum',
            'partsName': 'partsName',
            'brandName': 'brandName',
            'brandNormalized': 'brandNormalized',
            'brandId': 'brandId',
            'sellerBtPrice': 'sellerBtPrice',
            'sellerPrice': 'sellerPrice',
            'displaySellerStatus': 'display_seller_status',
            'vin': 'vin',
            'engine': 'engine',
            'productionDate': 'production_date',
            'chassis': 'chassis',
            'carBrandName': 'car_brand_name',
            'customerName': 'garage_company_name',
            'locationName': 'location_name',
            'arrivalTime': 'arrival_time'
        }
        order_by = build_order_by(
            sort_column, sort_dir, records_column_map,
            numeric_columns={'sellerBtPrice', 'sellerPrice'},
            default='quote_date DESC, created_at DESC'
        )

        # 查询数据（带分页）
        data_sql = f"""
            SELECT
                inquiryId,
                garage_company_name AS customerName,
                partsNum,
                partsName,
                brandName,
                brandNormalized,
                brandId,
                sellerBtPrice,
                sellerPrice,
                display_seller_status AS displaySellerStatus,
                remark,
                vin,
                engine,
                production_date AS productionDate,
                chassis,
                car_brand_name AS carBrandName,
                location_name AS locationName,
                arrival_time AS arrivalTime
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """

        # 查询总条数
        count_result = db_query_one(count_sql, tuple(params), dict_cursor=False)
        if count_result is None:
            total = 0
        elif isinstance(count_result, dict):
            total = count_result.get('COUNT(*)', 0) or count_result.get('count', 0)
        else:
            total = count_result[0] if count_result else 0

        # 查询分页数据
        offset = (page - 1) * page_size
        data_params = params.copy()
        data_params.append(page_size)
        data_params.append(offset)

        with db_cursor() as cursor:
            cursor.execute(data_sql, data_params)
            rows = cursor.fetchall()

            # 硬编码列名（确保与 SQL 一致）- 已删除：quote_date, partType, partsBrandQuality, company, created_at, updated_at
            columns = [
                'inquiryId', 'partsNum', 'partsName', 'brandName', 'brandNormalized',
                'brandId', 'sellerBtPrice', 'sellerPrice', 'displaySellerStatus', 'remark',
                'vin', 'engine', 'productionDate', 'chassis', 'carBrandName',
                'locationName', 'arrivalTime'
            ]
            result = []
            for row in rows:
                # 如果 row 已经是字典，直接使用
                if isinstance(row, dict):
                    record = row
                else:
                    record = dict(zip(columns, row))
                result.append(record)

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000  # 毫秒
            print(f"[KsInquiryRecordsService] 查询完成: 耗时 {elapsed_time:.2f} ms, 总条数: {total}, 返回 {len(result)} 条记录")

            return {
                'list': result,
                'total': total,
                'page': page,
                'page_size': page_size
            }

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
        sort_dir: str = ''
    ) -> Dict[str, Any]:
        """
        获取OE号统计维度（按partsNum分组聚合）

        Args:
            sort_column: 排序列名
            sort_dir: 排序方向 (asc/desc)

        Returns:
            Dict: {list: 数据列表, total: 总条数, page: 当前页, page_size: 每页条数}
        """
        start_time = time.time()

        conditions = []
        params = []

        # 构建查询条件（与get_records一致）
        if inquiry_id:
            conditions.append("inquiryId LIKE %s")
            params.append(f"%{inquiry_id}%")

        if parts_num:
            conditions.append("partsNum LIKE %s")
            params.append(f"%{parts_num}%")

        if parts_name:
            conditions.append("partsName LIKE %s")
            params.append(f"%{parts_name}%")

        if brand_name:
            conditions.append("brandName LIKE %s")
            params.append(f"%{brand_name}%")

        if brand:
            conditions.append("brandNormalized = %s")
            params.append(brand)

        if seller_status:
            conditions.append("display_seller_status LIKE %s")
            params.append(f"%{seller_status}%")

        if begin_date:
            conditions.append("quote_date >= %s")
            params.append(begin_date)

        if end_date:
            conditions.append("quote_date <= %s")
            params.append(end_date)

        if company:
            conditions.append("company = %s")
            params.append(company)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 查询不同OE号的总数量
        count_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT partsNum FROM crmapp_ks_inquiry_detail
                WHERE {where_clause}
                GROUP BY partsNum
            ) t
        """

        # OE统计排序：白名单映射（前端列名 -> SQL列名）
        oe_column_map = {
            'partsNum': 'a.partsNum',
            'count': 'a.count',
            'partsName': 'partsName',
            'unquotedProducts': 'a.unquotedProducts'
        }
        order_by = build_order_by(
            sort_column, sort_dir, oe_column_map,
            numeric_columns={'count', 'unquotedProducts'},
            default='a.count DESC'
        )

        # 查询分组聚合数据
        # 配件名称优先取：原厂 > 原厂国内4S件 > 其他
        data_sql = f"""
            SELECT
                a.partsNum,
                a.count,
                COALESCE(b.partsName, c.partsName, d.partsName) as partsName,
                a.unquotedProducts
            FROM (
                SELECT
                    partsNum,
                    COUNT(DISTINCT inquiryId) as count,
                    MAX(unquoted_products) as unquotedProducts
                FROM crmapp_ks_inquiry_detail
                WHERE {where_clause}
                GROUP BY partsNum
            ) a
            LEFT JOIN (
                SELECT partsNum, partsName
                FROM crmapp_ks_inquiry_detail
                WHERE brandNormalized = '原厂'
                  AND ({where_clause})
                GROUP BY partsNum
            ) b ON a.partsNum = b.partsNum
            LEFT JOIN (
                SELECT partsNum, partsName
                FROM crmapp_ks_inquiry_detail
                WHERE brandNormalized = '原厂国内4S件'
                  AND ({where_clause})
                GROUP BY partsNum
            ) c ON a.partsNum = c.partsNum
            LEFT JOIN (
                SELECT partsNum, partsName
                FROM (
                    SELECT partsNum, partsName, COUNT(*) as name_count
                    FROM crmapp_ks_inquiry_detail
                    WHERE ({where_clause})
                    GROUP BY partsNum, partsName
                    ORDER BY name_count DESC
                    LIMIT 1
                ) t
                GROUP BY partsNum
            ) d ON a.partsNum = d.partsNum
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """

        # 查询总条数
        count_result = db_query_one(count_sql, tuple(params), dict_cursor=False)
        if count_result is None:
            total = 0
        elif isinstance(count_result, dict):
            total = count_result.get('COUNT(*)', 0) or count_result.get('count', 0)
        else:
            total = count_result[0] if count_result else 0

        # 查询分页数据
        # 注意：data_sql 中 where_clause 出现了 4 次，参数需要重复 4 次
        offset = (page - 1) * page_size
        data_params = params.copy() * 4  # 4个子查询都使用相同的where条件
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
            print(f"[KsInquiryRecordsService] OE统计查询完成: 耗时 {elapsed_time:.2f} ms, 总条数: {total}, 返回 {len(result)} 条记录")

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
            print(f"[KsInquiryRecordsService] 发动机底盘查询完成: 耗时 {elapsed_time:.2f} ms, 总条数: {total}, 返回 {len(result)} 条记录")

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
        sort_dir: str = ''
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

        if begin_date:
            conditions.append("quote_date >= %s")
            params.append(begin_date)

        if end_date:
            conditions.append("quote_date <= %s")
            params.append(end_date)

        conditions.append("COALESCE(TRIM(chassis), '') != ''")

        where_clause = " AND ".join(conditions)

        chassis_column_map = {
            'carBrandName': 'car_brand_name',
            'chassis': 'chassis',
            'count': 'count'
        }
        order_by = build_order_by(
            sort_column, sort_dir, chassis_column_map,
            numeric_columns={'count'},
            default='count DESC, car_brand_name, chassis'
        )

        sql = f"""
            SELECT
                car_brand_name AS carBrandName,
                chassis,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY car_brand_name, chassis
            ORDER BY {order_by}
        """

        with db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append({
                        'carBrandName': row.get('carBrandName') or '',
                        'chassis': row.get('chassis') or '',
                        'count': row.get('count') or 0
                    })
                else:
                    result.append({
                        'carBrandName': row[0] or '',
                        'chassis': row[1] or '',
                        'count': row[2] or 0
                    })

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryRecordsService] 修理厂底盘统计完成: 耗时 {elapsed_time:.2f} ms, 返回 {len(result)} 条记录")

            return {'list': result}

    @staticmethod
    def get_garage_engine_stats(
        garage_name: str = '',
        company: str = '',
        begin_date: str = '',
        end_date: str = '',
        sort_column: str = '',
        sort_dir: str = ''
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

        if begin_date:
            conditions.append("quote_date >= %s")
            params.append(begin_date)

        if end_date:
            conditions.append("quote_date <= %s")
            params.append(end_date)

        conditions.append("COALESCE(TRIM(engine), '') != ''")

        where_clause = " AND ".join(conditions)

        engine_column_map = {
            'carBrandName': 'car_brand_name',
            'engine': 'engine',
            'count': 'count'
        }
        order_by = build_order_by(
            sort_column, sort_dir, engine_column_map,
            numeric_columns={'count'},
            default='count DESC, car_brand_name, engine'
        )

        sql = f"""
            SELECT
                car_brand_name AS carBrandName,
                engine,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY car_brand_name, engine
            ORDER BY {order_by}
        """

        with db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append({
                        'carBrandName': row.get('carBrandName') or '',
                        'engine': row.get('engine') or '',
                        'count': row.get('count') or 0
                    })
                else:
                    result.append({
                        'carBrandName': row[0] or '',
                        'engine': row[1] or '',
                        'count': row[2] or 0
                    })

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryRecordsService] 修理厂发动机统计完成: 耗时 {elapsed_time:.2f} ms, 返回 {len(result)} 条记录")

            return {'list': result}

    @staticmethod
    def get_garage_oenum_stats(
        garage_name: str = '',
        company: str = '',
        begin_date: str = '',
        end_date: str = '',
        sort_column: str = '',
        sort_dir: str = ''
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

        if begin_date:
            conditions.append("quote_date >= %s")
            params.append(begin_date)

        if end_date:
            conditions.append("quote_date <= %s")
            params.append(end_date)

        conditions.append("COALESCE(TRIM(partsNum), '') != ''")

        where_clause = " AND ".join(conditions)

        oenum_column_map = {
            'carBrandName': 'car_brand_name',
            'partsNum': 'partsNum',
            'count': 'count'
        }
        order_by = build_order_by(
            sort_column, sort_dir, oenum_column_map,
            numeric_columns={'count'},
            default='count DESC, car_brand_name, partsNum'
        )

        sql = f"""
            SELECT
                car_brand_name AS carBrandName,
                partsNum,
                COUNT(DISTINCT inquiryId) AS count
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            GROUP BY car_brand_name, partsNum
            ORDER BY {order_by}
        """

        with db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append({
                        'carBrandName': row.get('carBrandName') or '',
                        'partsNum': row.get('partsNum') or '',
                        'count': row.get('count') or 0
                    })
                else:
                    result.append({
                        'carBrandName': row[0] or '',
                        'partsNum': row[1] or '',
                        'count': row[2] or 0
                    })

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryRecordsService] 修理厂OE号码统计完成: 耗时 {elapsed_time:.2f} ms, 返回 {len(result)} 条记录")

            return {'list': result}

    @staticmethod
    def get_distinct_seller_status() -> List[str]:
        """
        获取所有不重复的卖家状态列表（用于筛选下拉）

        Returns:
            List[str]: 卖家状态列表
        """
        sql = """
            SELECT DISTINCT display_seller_status
            FROM crmapp_ks_inquiry_detail
            WHERE display_seller_status IS NOT NULL AND display_seller_status != ''
            ORDER BY display_seller_status
        """

        with db_cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [row[0] for row in rows if row[0]]

    @staticmethod
    def get_distinct_brands(company: str = '') -> List[str]:
        """
        获取所有不重复的品牌列表（brandNormalized，用于筛选下拉）

        Args:
            company: 用户门店/组织，为空则返回所有

        Returns:
            List[str]: 品牌列表
        """
        if company:
            sql = """
                SELECT DISTINCT brandNormalized
                FROM crmapp_ks_inquiry_detail
                WHERE brandNormalized IS NOT NULL AND brandNormalized != '' AND company = %s
                ORDER BY brandNormalized
            """
            params = (company,)
        else:
            sql = """
                SELECT DISTINCT brandNormalized
                FROM crmapp_ks_inquiry_detail
                WHERE brandNormalized IS NOT NULL AND brandNormalized != ''
                ORDER BY brandNormalized
            """
            params = ()

        with db_cursor(dict_cursor=False) as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if rows and isinstance(rows[0], dict):
                return [row.get('brandNormalized') for row in rows if row.get('brandNormalized')]
            else:
                return [row[0] for row in rows if row[0]]
