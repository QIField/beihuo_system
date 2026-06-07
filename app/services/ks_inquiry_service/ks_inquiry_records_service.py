# -*- coding:utf-8 -*-
"""
开思询价明细查询服务
处理 crmapp_ks_inquiry_detail 表的查询业务逻辑
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import time
from app.utils.database_connection import db_cursor, db_query_one


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
        begin_date: str = '',
        end_date: str = '',
        company: str = '',
        page: int = 1,
        page_size: int = 200
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
            begin_date: 开始日期 (yyyy-MM-dd)
            end_date: 结束日期 (yyyy-MM-dd)
            company: 用户门店/组织
            page: 页码（从1开始）
            page_size: 每页条数

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
            conditions.append("sellerStatus LIKE %s")
            params.append(f"%{seller_status}%")

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

        # 查询数据（带分页）- 已删除：quote_date, partType, partsBrandQuality, company, created_at, updated_at
        data_sql = f"""
            SELECT
                inquiryId,
                partsNum,
                partsName,
                brandName,
                brandNormalized,
                brandId,
                sellerBtPrice,
                sellerPrice,
                sellerStatus,
                remark
            FROM crmapp_ks_inquiry_detail
            WHERE {where_clause}
            ORDER BY quote_date DESC, created_at DESC
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
                'brandId', 'sellerBtPrice', 'sellerPrice', 'sellerStatus', 'remark'
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
    def get_distinct_seller_status() -> List[str]:
        """
        获取所有不重复的卖家状态列表（用于筛选下拉）

        Returns:
            List[str]: 卖家状态列表
        """
        sql = """
            SELECT DISTINCT sellerStatus
            FROM crmapp_ks_inquiry_detail
            WHERE sellerStatus IS NOT NULL AND sellerStatus != ''
            ORDER BY sellerStatus
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
