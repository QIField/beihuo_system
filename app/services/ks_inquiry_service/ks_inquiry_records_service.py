# -*- coding:utf-8 -*-
"""
开思询价明细查询服务
处理 crmapp_ks_inquiry_detail 表的查询业务逻辑
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import time
from app.utils.database_connection import db_cursor, db_query_one, db_query_all
from app.utils.common_util_module.sql_builder import build_order_by
from app.services.ks_inquiry_service.ks_inquiry_stats_service import _build_code_display_exprs


class KsInquiryRecordsService:
    """
    开思询价明细查询服务
    """

    # 前端列名 -> 数据库列名
    _DETAIL_FILTER_MAP = {
        'inquiryId': 'inquiryId',
        'customerName': 'garage_company_name',
        'partsNum': 'partsNum',
        'resolve_parts_name': 'resolve_parts_name',
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

    # 主表（询价单维度）列名映射
    _MASTER_FILTER_MAP = {
        'inquiryId': 'inquiryId',
        'customerName': 'garage_company_name',
        'carBrandName': 'car_brand_name',
        'vin': 'vin',
        'engine': 'engine',
        'productionDate': 'production_date',
        'chassis': 'chassis'
    }

    _MASTER_GROUP_BY_FIELDS = (
        "inquiryId, garage_company_name, car_brand_name, vin, engine, production_date, chassis"
    )

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
    def _get_engine_mappings(company: str) -> Dict[tuple, str]:
        """获取指定公司的发动机展示名称映射"""
        sql = """
            SELECT car_brand_name, original_code, display_code
            FROM ks_part_mapping
            WHERE company = %s AND mapping_type = 'engine'
        """
        rows = db_query_all(sql, (company,), dict_cursor=True)
        mappings = {}
        for row in rows or []:
            key = (row.get('car_brand_name') or '', row.get('original_code') or '')
            mappings[key] = row.get('display_code') or ''
        return mappings

    @staticmethod
    def _map_engine_value(car_brand_name: str, engine: str, mappings: Dict[tuple, str]) -> str:
        """根据映射规则计算发动机展示值（先截取后映射）"""
        if not engine:
            return engine
        if car_brand_name == '奔驰' and len(engine) > 6:
            base = engine[:6]
        else:
            base = engine
        display = mappings.get((car_brand_name, base))
        return display if display else base

    @staticmethod
    def _build_detail_where_clause(
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
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[str, List[Any], str]:
        """构建明细查询的 WHERE 子句、参数列表和 ORDER BY 子句。"""
        conditions, params = [], []

        if inquiry_id:    conditions.append("d.inquiryId LIKE %s");           params.append(f"%{inquiry_id}%")
        if parts_num:     conditions.append("d.partsNum LIKE %s");            params.append(f"%{parts_num}%")
        if parts_name:    conditions.append("d.resolve_parts_name LIKE %s");  params.append(f"%{parts_name}%")
        if brand_name:    conditions.append("d.brandName LIKE %s");           params.append(f"%{brand_name}%")
        if brand:         conditions.append("d.brandNormalized = %s");        params.append(brand)
        if seller_status:
            conditions.append("d.display_seller_status = %s")
            params.append(seller_status)
        if car_brand_name: conditions.append("d.car_brand_name = %s");        params.append(car_brand_name)
        if garage_name:   conditions.append("d.garage_company_name LIKE %s");  params.append(f"%{garage_name}%")
        if begin_date:    conditions.append("d.quote_date >= %s");            params.append(begin_date)
        if end_date:      conditions.append("d.quote_date <= %s");            params.append(end_date)
        if company:       conditions.append("d.company = %s");                params.append(company)

        detail_filter_map = {k: f"d.{v}" for k, v in KsInquiryRecordsService._DETAIL_FILTER_MAP.items()}
        KsInquiryRecordsService._apply_filters(column_filters, detail_filter_map, conditions, params)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        records_column_map = {
            'inquiryId': 'd.inquiryId',
            'partsNum': 'd.partsNum',
            'resolve_parts_name': 'd.resolve_parts_name',
            'partsName': 'd.partsName',
            'brandName': 'd.brandName',
            'brandNormalized': 'd.brandNormalized',
            'brandId': 'd.brandId',
            'sellerBtPrice': 'd.sellerBtPrice',
            'sellerPrice': 'd.sellerPrice',
            'displaySellerStatus': 'd.display_seller_status',
            'vin': 'd.vin',
            'engine': 'd.engine',
            'productionDate': 'd.production_date',
            'chassis': 'd.chassis',
            'carBrandName': 'd.car_brand_name',
            'customerName': 'd.garage_company_name',
            'locationName': 'd.location_name',
            'arrivalTime': 'd.arrival_time'
        }
        order_by = build_order_by(
            sort_column, sort_dir, records_column_map,
            numeric_columns={'sellerBtPrice', 'sellerPrice'},
            default='d.inquiryId ASC, d.content_item_index ASC'
        )

        return where_clause, params, order_by

    @staticmethod
    def _fetch_detail_rows(
        where_clause: str,
        params: List[Any],
        order_by: str,
        company: str = '',
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        batch_size: int = 5000,
    ) -> List[Dict[str, Any]]:
        """
        根据 WHERE 条件查询明细数据；limit/offset 为 None 时不分页。
        全量导出时按 batch_size 分批查询 id，避免超长 IN 子句。
        """
        id_params = list(params)

        with db_cursor() as cursor:
            if limit is not None:
                # 分页场景：只查询当前页 id
                base_id_sql = f"""
                    SELECT d.id
                    FROM crmapp_ks_inquiry_detail d
                    WHERE {where_clause}
                    ORDER BY {order_by}
                """
                cursor.execute(base_id_sql + " LIMIT %s OFFSET %s", tuple(id_params + [limit, offset or 0]))
                id_batches = [[row[0] for row in cursor.fetchall()]]
            else:
                # 全量导出：使用游标分页按 id 分批查询，避免 OFFSET 深翻页
                id_batches = []
                last_id = None
                while True:
                    if last_id is None:
                        sql = f"""
                            SELECT d.id
                            FROM crmapp_ks_inquiry_detail d
                            WHERE {where_clause}
                            ORDER BY d.id ASC
                            LIMIT %s
                        """
                        q_params = tuple(id_params + [batch_size])
                    else:
                        sql = f"""
                            SELECT d.id
                            FROM crmapp_ks_inquiry_detail d
                            WHERE {where_clause} AND d.id > %s
                            ORDER BY d.id ASC
                            LIMIT %s
                        """
                        q_params = tuple(id_params + [last_id, batch_size])
                    cursor.execute(sql, q_params)
                    rows = cursor.fetchall()
                    if not rows:
                        break
                    ids = [row[0] for row in rows]
                    id_batches.append(ids)
                    if len(rows) < batch_size:
                        break
                    last_id = ids[-1]

            columns = [
                'inquiryId', 'customerName', 'partsNum', 'resolve_parts_num', 'resolve_parts_name', 'partsName', 'brandName', 'brandNormalized',
                'brandId', 'sellerBtPrice', 'sellerPrice', 'displaySellerStatus', 'remark',
                'vin', 'engine', 'productionDate', 'chassis', 'carBrandName',
                'locationName', 'arrivalTime', 'content_item_index'
            ]
            result = []

            for ids in id_batches:
                if not ids:
                    continue
                detail_sql = f"""
                    SELECT
                        d.inquiryId,
                        d.garage_company_name AS customerName,
                        d.partsNum,
                        d.resolve_parts_num,
                        d.resolve_parts_name,
                        d.partsName,
                        d.brandName,
                        d.brandNormalized,
                        d.brandId,
                        d.sellerBtPrice,
                        d.sellerPrice,
                        d.display_seller_status AS displaySellerStatus,
                        d.remark,
                        d.vin,
                        d.engine,
                        d.production_date AS productionDate,
                        d.chassis,
                        d.car_brand_name AS carBrandName,
                        d.location_name AS locationName,
                        d.arrival_time AS arrivalTime,
                        d.content_item_index
                    FROM crmapp_ks_inquiry_detail d
                    WHERE d.id IN ({', '.join(['%s'] * len(ids))})
                    ORDER BY d.inquiryId ASC, d.content_item_index ASC
                """
                cursor.execute(detail_sql, tuple(ids))
                rows = cursor.fetchall()
                for row in rows:
                    if isinstance(row, dict):
                        record = row
                    else:
                        record = dict(zip(columns, row))
                    result.append(record)

            if company:
                engine_mappings = KsInquiryRecordsService._get_engine_mappings(company)
                for record in result:
                    record['engine'] = KsInquiryRecordsService._map_engine_value(
                        record.get('carBrandName') or '',
                        record.get('engine') or '',
                        engine_mappings
                    )

            return result

    @staticmethod
    def get_records(
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
        where_clause, params, order_by = KsInquiryRecordsService._build_detail_where_clause(
            inquiry_id, parts_num, parts_name, brand_name, brand, seller_status,
            car_brand_name, garage_name, begin_date, end_date, company,
            sort_column, sort_dir, column_filters
        )

        count_sql = f"""
            SELECT COUNT(*) FROM crmapp_ks_inquiry_detail d
            WHERE {where_clause}
        """
        count_result = db_query_one(count_sql, tuple(params), dict_cursor=False)
        if count_result is None:
            total = 0
        elif isinstance(count_result, dict):
            total = count_result.get('COUNT(*)', 0) or count_result.get('count', 0)
        else:
            total = count_result[0] if count_result else 0

        offset = (page - 1) * page_size
        result = KsInquiryRecordsService._fetch_detail_rows(
            where_clause, params, order_by, company, limit=page_size, offset=offset
        )

        return {
            'list': result,
            'total': total,
            'page': page,
            'page_size': page_size
        }

    @staticmethod
    def get_all_records(
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
        sort_column: str = '',
        sort_dir: str = '',
        column_filters: Optional[Dict[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取开思询价明细完整数据（不分页，用于导出）
        """
        where_clause, params, order_by = KsInquiryRecordsService._build_detail_where_clause(
            inquiry_id, parts_num, parts_name, brand_name, brand, seller_status,
            car_brand_name, garage_name, begin_date, end_date, company,
            sort_column, sort_dir, column_filters
        )
        return KsInquiryRecordsService._fetch_detail_rows(where_clause, params, order_by, company)

    @staticmethod
    def get_master_records(
        inquiry_id: str = '',
        garage_name: str = '',
        car_brand_name: str = '',
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
        """获取询价单维度主表（按 inquiryId 去重）"""
        conditions, params = [], []

        if inquiry_id:     conditions.append("inquiryId LIKE %s");          params.append(f"%{inquiry_id}%")
        if garage_name:    conditions.append("garage_company_name LIKE %s"); params.append(f"%{garage_name}%")
        if car_brand_name: conditions.append("car_brand_name = %s");        params.append(car_brand_name)
        if company:        conditions.append("company = %s");               params.append(company)
        if begin_date:     conditions.append("quote_date >= %s");           params.append(begin_date)
        if end_date:       conditions.append("quote_date <= %s");           params.append(end_date)

        # 按订单状态过滤：只保留包含该状态的订单
        if seller_status:
            status_condition = "display_seller_status = %s"
            params.append(seller_status)
            conditions.append(f"inquiryId IN (SELECT DISTINCT inquiryId FROM crmapp_ks_inquiry_detail WHERE {status_condition})")

        KsInquiryRecordsService._apply_filters(column_filters, KsInquiryRecordsService._MASTER_FILTER_MAP, conditions, params)
        where = " AND ".join(conditions) if conditions else "1=1"
        group_by = KsInquiryRecordsService._MASTER_GROUP_BY_FIELDS
        order_by = build_order_by(sort_column, sort_dir, KsInquiryRecordsService._MASTER_FILTER_MAP, default="inquiryId ASC")

        count_sql = f"SELECT COUNT(*) FROM (SELECT 1 FROM crmapp_ks_inquiry_detail WHERE {where} GROUP BY {group_by}) t"
        data_sql = f"""
            SELECT inquiryId, garage_company_name AS customerName, car_brand_name AS carBrandName,
                   vin, engine, production_date AS productionDate, chassis
            FROM crmapp_ks_inquiry_detail
            WHERE {where} GROUP BY {group_by} ORDER BY {order_by} LIMIT %s OFFSET %s
        """

        count_result = db_query_one(count_sql, tuple(params), dict_cursor=True)
        total = (count_result.get('COUNT(*)') or 0) if isinstance(count_result, dict) else (count_result[0] if count_result else 0)

        with db_cursor(dict_cursor=True) as cursor:
            cursor.execute(data_sql, tuple(params + [page_size, (page - 1) * page_size]))
            return {'list': cursor.fetchall(), 'total': total, 'page': page, 'page_size': page_size}

    @staticmethod
    def get_column_values(
        column: str,
        grid_type: str = 'detail',
        inquiry_id: str = '',
        resolve_parts_num: str = '',
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
    ) -> List[Dict[str, Any]]:
        """
        获取指定列的全量不重复值（用于列头下拉筛选）

        Args:
            column: 前端列名
            grid_type: 网格类型：detail / master / oe_stats / garage_chassis / garage_engine / garage_oenum
            column_filters: 当前已激活的列筛选，查询时会排除 column 本身

        Returns:
            List[Dict]: 不重复值列表（已排序），每项 {value, count}
        """
        start_time = time.time()

        conditions, params = [], []

        # 基础查询条件
        if inquiry_id:    conditions.append("inquiryId LIKE %s");           params.append(f"%{inquiry_id}%")
        # customer_stats_by_oe 限定单个 OE，使用精确匹配
        if grid_type == 'customer_stats_by_oe' and resolve_parts_num:
            conditions.append("resolve_parts_num = %s")
            params.append(resolve_parts_num)
        elif resolve_parts_num:
            conditions.append("resolve_parts_num LIKE %s")
            params.append(f"%{resolve_parts_num}%")
        if parts_name:    conditions.append("resolve_parts_name LIKE %s");  params.append(f"%{parts_name}%")
        if brand_name:    conditions.append("brandName LIKE %s");           params.append(f"%{brand_name}%")
        if brand:         conditions.append("brandNormalized = %s");        params.append(brand)
        if seller_status:
            conditions.append("display_seller_status = %s")
            params.append(seller_status)
        if car_brand_name: conditions.append("car_brand_name LIKE %s");     params.append(f"%{car_brand_name}%")
        if garage_name:   conditions.append("garage_company_name LIKE %s");  params.append(f"%{garage_name}%")
        if begin_date:    conditions.append("quote_date >= %s");            params.append(begin_date)
        if end_date:      conditions.append("quote_date <= %s");            params.append(end_date)
        if company:       conditions.append("company = %s");                params.append(company)

        # 不同网格的列映射与聚合配置
        grid_configs = {
            'detail':       {'columns': KsInquiryRecordsService._DETAIL_FILTER_MAP, 'aggregated': set()},
            'master':       {'columns': KsInquiryRecordsService._MASTER_FILTER_MAP, 'aggregated': set()},
            'oe_stats':     {'columns': {'resolve_parts_num': 'resolve_parts_num', 'partsName': 'resolve_parts_name', 'count': 'count', 'unquotedProducts': 'unquotedProducts', 'carBrandName': 'car_brand_name'}, 'aggregated': {'count', 'unquotedProducts'}, 'group_by': 'resolve_parts_num'},
            'garage_chassis': {'columns': {'carBrandName': 'car_brand_name', 'chassis': 'chassis', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'car_brand_name, chassis'},
            'garage_engine':  {'columns': {'carBrandName': 'car_brand_name', 'engine': 'engine', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'car_brand_name, engine'},
            'garage_oenum':   {'columns': {'carBrandName': 'car_brand_name', 'partsNum': 'partsNum', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'car_brand_name, partsNum'},
            'customer_stats': {
                'columns': {
                    'customerName': 'garage_company_name',
                    'count': 'count',
                    'orderedCount': 'orderedCount',
                    'unorderedCount': 'unorderedCount',
                    'conversionRate': 'conversionRate'
                },
                'aggregated': {'count', 'orderedCount', 'unorderedCount', 'conversionRate'}
            },
            'customer_stats_by_oe': {'columns': {'customerName': 'garage_company_name', 'count': 'count'}, 'aggregated': {'count'}, 'group_by': 'garage_company_name'},
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

        # 发动机/底盘统计：下拉值使用映射后的展示名称（先截取后映射）
        if grid_type in ('garage_engine', 'detail') and column == 'engine':
            _, display_expr, join_match_expr = _build_code_display_exprs(
                'engine', 'car_brand_name', 'engine'
            )
            mapping_type = 'engine'
        elif grid_type == 'garage_chassis' and column == 'chassis':
            _, display_expr, join_match_expr = _build_code_display_exprs(
                'chassis', 'car_brand_name', 'chassis'
            )
            mapping_type = 'chassis'
        else:
            display_expr = None

        if display_expr:
            sql = f"""
                SELECT value, COUNT(*) AS count
                FROM (
                    SELECT {display_expr} AS value,
                           COUNT(DISTINCT d.inquiryId) AS cnt
                    FROM crmapp_ks_inquiry_detail d
                    LEFT JOIN ks_part_mapping m
                        ON m.company = %s
                        AND m.mapping_type = '{mapping_type}'
                        AND m.car_brand_name = d.car_brand_name
                        AND m.original_code = {join_match_expr}
                    WHERE {where_clause}
                    GROUP BY {display_expr}
                ) t
                WHERE value IS NOT NULL AND TRIM(value) != ''
                GROUP BY value ORDER BY value LIMIT 1000
            """
            params.insert(0, company)

            with db_cursor() as cursor:
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
                values = []
                for r in rows:
                    if isinstance(r, dict):
                        values.append({'value': str(r.get('value', '')), 'count': int(r.get('count', 0))})
                    else:
                        values.append({'value': str(r[0]), 'count': int(r[1])})

                end_time = time.time()
                elapsed_time = (end_time - start_time) * 1000
                print(f"[KsInquiryRecordsService] 列 {grid_type}.{column} 全量不重复值查询完成: "
                      f"耗时 {elapsed_time:.2f} ms, 返回 {len(values)} 条")
                return values

        if grid_type == 'master':
            # 主表按 inquiryId 去重，下拉计数应为“订单数”
            sql = f"""
                SELECT {db_col} AS value, COUNT(DISTINCT inquiryId) AS count
                FROM crmapp_ks_inquiry_detail
                WHERE {where_clause} AND {db_col} IS NOT NULL AND TRIM({db_col}) != ''
                GROUP BY {db_col} ORDER BY {db_col} LIMIT 1000
            """
        elif grid_type == 'customer_stats' and column in config['aggregated']:
            # 客户统计：按 客户+询价单号+resolve_parts_num 去重后计算聚合值
            dedup_key = "CONCAT(COALESCE(garage_company_name, ''), '_', COALESCE(inquiryId, ''), '_', COALESCE(resolve_parts_num, ''))"
            sql = f"""
                SELECT {db_col} AS value, COUNT(*) AS count
                FROM (
                    SELECT
                        garage_company_name,
                        COUNT(DISTINCT {dedup_key}) AS count,
                        COUNT(DISTINCT CASE WHEN has_ordered = 1 THEN {dedup_key} END) AS orderedCount,
                        COUNT(DISTINCT CASE WHEN has_unordered = 1 AND has_ordered = 0 THEN {dedup_key} END) AS unorderedCount,
                        ROUND(
                            COUNT(DISTINCT CASE WHEN has_ordered = 1 THEN {dedup_key} END) * 100.0
                            / NULLIF(COUNT(DISTINCT {dedup_key}), 0),
                            2
                        ) AS conversionRate
                    FROM (
                        SELECT
                            garage_company_name,
                            inquiryId,
                            resolve_parts_num,
                            MAX(CASE WHEN display_seller_status = '本店下单' THEN 1 ELSE 0 END) AS has_ordered,
                            MAX(CASE WHEN display_seller_status IN ('未下单', '非本店下单') THEN 1 ELSE 0 END) AS has_unordered
                        FROM crmapp_ks_inquiry_detail
                        WHERE {where_clause}
                        GROUP BY garage_company_name, inquiryId, resolve_parts_num
                    ) t2
                    GROUP BY garage_company_name
                ) t
                WHERE {db_col} IS NOT NULL
                GROUP BY {db_col} ORDER BY {db_col} LIMIT 1000
            """
        elif column in config['aggregated']:
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
            values = []
            for r in rows:
                if isinstance(r, dict):
                    values.append({'value': str(r.get('value', '')), 'count': int(r.get('count', 0))})
                else:
                    values.append({'value': str(r[0]), 'count': int(r[1])})

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
            values = []
            for row in rows:
                if isinstance(row, dict):
                    val = row.get('display_seller_status')
                else:
                    val = row[0]
                if val:
                    values.append(val)
            return values

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
