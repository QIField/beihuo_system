# -*- coding:utf-8 -*-
"""
开思询价明细查询服务
处理 crmapp_ks_inquiry_detail 表的查询业务逻辑
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import time
from app.utils.database_connection import db_cursor, db_query_one
from app.utils.common_util_module.sql_builder import build_order_by


class KsInquiryRecordsService:
    """
    开思询价明细查询服务
    """

    # 前端列名 -> 数据库列名
    _DETAIL_FILTER_MAP = {
        'inquiryId': 'inquiryId',
        'customerName': 'garage_company_name',
        'partsNum': 'partsNum',
        'partsName': 'partsName',
        'carBrandName': 'car_brand_name',
        'brandName': 'brandName',
        'brandNormalized': 'brandNormalized',
        'brandId': 'brandId',
        'sellerPrice': 'sellerPrice',
        'sellerBtPrice': 'sellerBtPrice',
        'displaySellerStatus': 'display_seller_status',
        'locationName': 'location_name',
        'arrivalTime': 'arrival_time',
        'remark': 'remark',
        'vin': 'vin',
        'engine': 'engine',
        'productionDate': 'production_date',
        'chassis': 'chassis'
    }

    @staticmethod
    def _apply_filters(column_filters, filter_map, conditions, params):
        """将列头下拉筛选条件追加到 WHERE 中，不防御空值或无效列"""
        if not column_filters:
            return
        for col_id, values in column_filters.items():
            db_col = filter_map[col_id]
            placeholders = ', '.join(['%s'] * len(values))
            conditions.append(f"{db_col} IN ({placeholders})")
            params.extend(values)

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
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
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
            column_filters: 列头下拉多选筛选，格式 {前端列名: [选中值列表]}

        Returns:
            Dict: {list: 数据列表, total: 总条数, page: 当前页, page_size: 每页条数}
        """
        start_time = time.time()

        conditions, params = [], []

        # 基础查询条件
        if inquiry_id:    conditions.append("inquiryId LIKE %s");           params.append(f"%{inquiry_id}%")
        if parts_num:     conditions.append("partsNum LIKE %s");            params.append(f"%{parts_num}%")
        if parts_name:    conditions.append("partsName LIKE %s");           params.append(f"%{parts_name}%")
        if brand_name:    conditions.append("brandName LIKE %s");           params.append(f"%{brand_name}%")
        if brand:         conditions.append("brandNormalized = %s");        params.append(brand)
        if seller_status: conditions.append("display_seller_status LIKE %s"); params.append(f"%{seller_status}%")
        if car_brand_name: conditions.append("car_brand_name = %s");        params.append(car_brand_name)
        if garage_name:   conditions.append("garage_company_name LIKE %s");  params.append(f"%{garage_name}%")
        if begin_date:    conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:      conditions.append("quote_date <= %s");            params.append(end_date)
        if company:       conditions.append("company = %s");                params.append(company)

        # 列头下拉全量筛选
        KsInquiryRecordsService._apply_filters(column_filters, KsInquiryRecordsService._DETAIL_FILTER_MAP, conditions, params)

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
            default='inquiryId ASC, content_item_index ASC'
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
                arrival_time AS arrivalTime,
                content_item_index
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
                'inquiryId', 'customerName', 'partsNum', 'partsName', 'brandName', 'brandNormalized',
                'brandId', 'sellerBtPrice', 'sellerPrice', 'displaySellerStatus', 'remark',
                'vin', 'engine', 'productionDate', 'chassis', 'carBrandName',
                'locationName', 'arrivalTime', 'content_item_index'
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
    def get_column_values(
        column: str,
        grid_type: str = 'detail',
        inquiry_id: str = '',
        parts_num: str = '',
        parts_name: str = '',
        brand_name: str = '',
        brand: str = '',
        seller_status: str = '',
        car_brand_name: str = '',
        garage_name: str = '',
        begin_date: str = '',
        end_date: str = '',
        company: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> List[str]:
        """
        获取指定列的全量不重复值（用于列头下拉筛选）

        Args:
            column: 前端列名
            grid_type: 网格类型：detail / oe_stats / garage_chassis / garage_engine / garage_oenum
            column_filters: 当前已激活的列筛选，查询时会排除 column 本身

        Returns:
            List[str]: 不重复值列表（已排序）
        """
        start_time = time.time()

        conditions, params = [], []

        # 基础查询条件
        if inquiry_id:    conditions.append("inquiryId LIKE %s");           params.append(f"%{inquiry_id}%")
        if parts_num:     conditions.append("partsNum LIKE %s");            params.append(f"%{parts_num}%")
        if parts_name:    conditions.append("partsName LIKE %s");           params.append(f"%{parts_name}%")
        if brand_name:    conditions.append("brandName LIKE %s");           params.append(f"%{brand_name}%")
        if brand:         conditions.append("brandNormalized = %s");        params.append(brand)
        if seller_status: conditions.append("display_seller_status LIKE %s"); params.append(f"%{seller_status}%")
        if car_brand_name: conditions.append("car_brand_name LIKE %s");     params.append(f"%{car_brand_name}%")
        if garage_name:   conditions.append("garage_company_name LIKE %s");  params.append(f"%{garage_name}%")
        if begin_date:    conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:      conditions.append("quote_date <= %s");            params.append(end_date)
        if company:       conditions.append("company = %s");                params.append(company)

        # 不同网格的列映射与聚合配置
        grid_configs = {
            'detail':       {'columns': KsInquiryRecordsService._DETAIL_FILTER_MAP, 'aggregated': set()},
            'oe_stats':     {'columns': {'partsNum': 'partsNum', 'partsName': 'partsName', 'count': 'count', 'unquotedProducts': 'unquotedProducts'}, 'aggregated': {'count', 'unquotedProducts'}, 'group_by': 'partsNum'},
            'garage_chassis': {'columns': {'carBrandName': 'car_brand_name', 'chassis': 'chassis', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'car_brand_name, chassis'},
            'garage_engine':  {'columns': {'carBrandName': 'car_brand_name', 'engine': 'engine', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'car_brand_name, engine'},
            'garage_oenum':   {'columns': {'carBrandName': 'car_brand_name', 'partsNum': 'partsNum', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'car_brand_name, partsNum'},
            'customer_stats': {'columns': {'customerName': 'garage_company_name', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'garage_company_name'},
            'customer_oenum': {'columns': {'carBrandName': 'car_brand_name', 'partsNum': 'resolve_parts_num', 'partsName': 'resolve_parts_name', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'car_brand_name, resolve_parts_num'}
        }

        config = grid_configs.get(grid_type)
        if not config or column not in config['columns']:
            return []

        # 应用已激活的列筛选（排除当前列本身）
        if column_filters:
            for col_id, values in column_filters.items():
                if col_id == column:
                    continue
                db_col = config['columns'].get(col_id)
                if not db_col:
                    continue
                placeholders = ', '.join(['%s'] * len(values))
                conditions.append(f"{db_col} IN ({placeholders})")
                params.extend(values)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        db_col = config['columns'][column]

        if column in config['aggregated']:
            group_by = config['group_by']
            sql = f"""
                SELECT {db_col} AS value, COUNT(*) AS count
                FROM (
                    SELECT {group_by}, COUNT(DISTINCT inquiryId) AS count, MAX(unquoted_products) AS unquotedProducts
                    FROM crmapp_ks_inquiry_detail WHERE {where_clause} GROUP BY {group_by}
                ) t
                WHERE {db_col} IS NOT NULL
                GROUP BY {db_col} ORDER BY {db_col} LIMIT 1000
            """
        else:
            sql = f"""
                SELECT {db_col} AS value, COUNT(*) AS count
                FROM crmapp_ks_inquiry_detail
                WHERE {where_clause} AND {db_col} IS NOT NULL AND TRIM({db_col}) != ''
                GROUP BY {db_col} ORDER BY {db_col} LIMIT 1000
            """

        with db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            values = [{'value': str(r[0]), 'count': int(r[1])} for r in rows]

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"[KsInquiryRecordsService] 列 {grid_type}.{column} 全量不重复值查询完成: "
                  f"耗时 {elapsed_time:.2f} ms, 返回 {len(values)} 条")
            return values

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
