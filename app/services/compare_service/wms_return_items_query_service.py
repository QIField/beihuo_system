# -*- coding:utf-8 -*-
# @Time    : 2026/7/10
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_return_items_query_service.py
# @Software: PyCharm
# @Desc    : 为替换号对比功能查询 WMS 采购入库单明细编号

from typing import List

from pymysql.cursors import Cursor

from app.utils.database_connection import get_db_connection


class WmsReturnItemsQueryService:
    """WMS 入库明细查询服务（服务于替换号对比）"""

    TABLE_NAME = "wms_return_items_detail"

    @staticmethod
    def get_distinct_number_clean_by_date_range(
        start_date: str, end_date: str
    ) -> List[str]:
        """
        按订单日期范围查询去重后的 number_clean

        :param start_date: 开始日期，格式 yyyy-MM-dd
        :param end_date: 结束日期，格式 yyyy-MM-dd
        :return: number_clean 列表
        """
        if not start_date or not end_date:
            return []

        conn = get_db_connection()
        try:
            # 显式指定 Cursor，避免 DBUtils 连接池默认游标类型不稳定导致 KeyError
            with conn.cursor(Cursor) as cursor:
                sql = f"""
                    SELECT DISTINCT number_clean
                    FROM {WmsReturnItemsQueryService.TABLE_NAME}
                    WHERE orderdate BETWEEN %s AND %s
                      AND number_clean IS NOT NULL
                      AND number_clean != ''
                """
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                return [row[0] for row in rows if row]
        finally:
            conn.close()


def get_distinct_number_clean_by_date_range(
    start_date: str, end_date: str
) -> List[str]:
    """模块级便捷函数"""
    return WmsReturnItemsQueryService.get_distinct_number_clean_by_date_range(
        start_date, end_date
    )
