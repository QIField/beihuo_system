"""
采购历史聚合服务
用于从多个数据源聚合数据到 crmapp_procurement_history
支持的数据源：procurement_history_detail, price_inquiry, price_inquiry_direct
"""

import calendar
from datetime import datetime
from typing import List, Dict, Any, Tuple

from app.utils.database_connection import get_db_connection


COMPANY = 'fsbbr'


class PurchaseHistoryAggregateService:
    """采购历史聚合服务类"""

    def __init__(self):
        self.total_deleted = 0
        self.total_inserted = 0

    def aggregate_and_update(
        self,
        sources: List[str] = None,
        company: str = COMPANY
    ) -> Dict[str, int]:
        """
        通用聚合函数 - 从多个数据源聚合采购记录

        Args:
            sources: 数据源列表，可选值：
                - 'procurement_detail': 采购明细表
                - 'price_inquiry': 正常询价表
                - 'price_inquiry_direct': 直接入库表
                默认为全部三个表
            company: 公司代码

        Returns:
            {'deleted': 删除条数, 'inserted': 插入条数}
        """
        if sources is None:
            sources = ['procurement_detail', 'price_inquiry', 'price_inquiry_direct']

        print(f"\n{'='*60}")
        print(f"开始采购历史数据聚合")
        print(f"数据源: {', '.join(sources)}")
        print(f"{'='*60}")

        # 计算上个月和本月的年月字符串
        year_months, start_date, end_date = self._calculate_date_range()
        print(f"处理月份: {', '.join(year_months)}")
        print(f"时间范围: {start_date} ~ {end_date}")

        # 从指定数据源聚合数据
        records = self._aggregate_from_sources(sources, company, start_date, end_date)
        print(f"聚合记录数: {len(records)}")

        # 更新目标表
        result = self._update_procurement_history(company, year_months, records)

        print(f"\n{'='*60}")
        print(f"采购历史聚合完成!")
        print(f"删除旧记录: {result['deleted']}")
        print(f"插入新记录: {result['inserted']}")
        print(f"{'='*60}")

        return result

    def _calculate_date_range(self) -> Tuple[List[str], str, str]:
        """
        计算上个月和本月的时间范围

        Returns:
            (年月列表, 开始日期, 结束日期)
            例如: (['2026-02', '2026-03'], '2026-02-01', '2026-03-31')
        """
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        # 计算上个月
        if current_month == 1:
            last_year = current_year - 1
            last_month = 12
        else:
            last_year = current_year
            last_month = current_month - 1

        # 年月字符串列表
        last_year_month = f"{last_year}-{last_month:02d}"
        current_year_month = f"{current_year}-{current_month:02d}"
        year_months = [last_year_month, current_year_month]

        # 上个月1号
        start_date = f"{last_year}-{last_month:02d}-01"

        # 本月最后一天
        last_day_of_current_month = calendar.monthrange(current_year, current_month)[1]
        end_date = f"{current_year}-{current_month:02d}-{last_day_of_current_month}"

        return year_months, start_date, end_date

    def _aggregate_from_sources(
        self,
        sources: List[str],
        company: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        从指定数据源聚合数据

        Args:
            sources: 数据源列表
            company: 公司代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            聚合后的记录列表
        """
        all_records = []

        for source in sources:
            if source == 'procurement_detail':
                records = self._query_procurement_detail(company, start_date, end_date)
            elif source == 'price_inquiry':
                records = self._query_price_inquiry(company, start_date, end_date)
            elif source == 'price_inquiry_direct':
                records = self._query_price_inquiry_direct(company, start_date, end_date)
            else:
                print(f"未知数据源: {source}, 跳过")
                continue

            all_records.extend(records)
            print(f"  - {source}: {len(records)} 条")

        # 统一聚合：按 (year_month, oe, brand) 分组，取最低价且最新的一条
        return self._deduplicate_records(all_records)

    def _query_procurement_detail(
        self,
        company: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """查询采购明细表"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        create_date as purchase_date,
                        fullname as supplier_name,
                        number as oe,
                        brand,
                        unit_cost as unit_price
                    FROM crmapp_procurement_history_detail
                    WHERE company = %s 
                        AND create_date BETWEEN %s AND %s
                        AND unit_cost > 0
                """
                cursor.execute(sql, (company, start_date, end_date))
                rows = cursor.fetchall()

                field_mapping = {
                    'purchase_date': ('purchase_date', 0),
                    'supplier_name': ('supplier_name', 1),
                    'oe': ('oe', 2),
                    'brand': ('brand', 3),
                    'unit_price': ('unit_price', 4),
                }

                records = []
                for row in rows:
                    record = self._row_to_record(row, field_mapping)
                    record['unit_price'] = float(record['unit_price']) if record['unit_price'] else 0.0
                    records.append(record)
                return records
        finally:
            conn.close()

    def _query_price_inquiry(
        self,
        company: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """查询正常询价表"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        import_time as purchase_date,
                        supplier as supplier_name,
                        oe,
                        brand,
                        original_price as unit_price
                    FROM crmapp_price_inquiry
                    WHERE company = %s 
                        AND import_time BETWEEN %s AND %s
                        AND original_price > 0
                """
                cursor.execute(sql, (company, start_date, end_date))
                rows = cursor.fetchall()

                field_mapping = {
                    'purchase_date': ('purchase_date', 0),
                    'supplier_name': ('supplier_name', 1),
                    'oe': ('oe', 2),
                    'brand': ('brand', 3),
                    'unit_price': ('unit_price', 4),
                }

                records = []
                for row in rows:
                    record = self._row_to_record(row, field_mapping)
                    record['unit_price'] = float(record['unit_price']) if record['unit_price'] else 0.0
                    records.append(record)
                return records
        finally:
            conn.close()

    def _query_price_inquiry_direct(
        self,
        company: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """查询直接入库表"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        import_time as purchase_date,
                        supplier as supplier_name,
                        oe,
                        brand,
                        original_price as unit_price
                    FROM crmapp_price_inquiry_direct
                    WHERE company = %s 
                        AND import_time BETWEEN %s AND %s
                        AND original_price > 0
                """
                cursor.execute(sql, (company, start_date, end_date))
                rows = cursor.fetchall()

                field_mapping = {
                    'purchase_date': ('purchase_date', 0),
                    'supplier_name': ('supplier_name', 1),
                    'oe': ('oe', 2),
                    'brand': ('brand', 3),
                    'unit_price': ('unit_price', 4),
                }

                records = []
                for row in rows:
                    record = self._row_to_record(row, field_mapping)
                    record['unit_price'] = float(record['unit_price']) if record['unit_price'] else 0.0
                    records.append(record)
                return records
        finally:
            conn.close()

    def _row_to_record(self, row, field_mapping: Dict[str, tuple]) -> Dict[str, Any]:
        """
        将数据库行转换为记录字典，兼容元组和字典两种格式
        
        Args:
            row: 数据库行（元组或字典）
            field_mapping: 字段映射 {目标字段名: (数据库字段名, 索引)}
        
        Returns:
            记录字典
        """
        def get_value(field_name: str, index: int):
            if isinstance(row, dict):
                return row.get(field_name)
            else:
                return row[index] if index < len(row) else None
        
        return {
            key: get_value(field_name, index)
            for key, (field_name, index) in field_mapping.items()
        }

    def _deduplicate_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重聚合：按 (year_month, oe, brand) 分组，取最低价且最新的一条

        Args:
            records: 原始记录列表

        Returns:
            聚合后的记录列表
        """
        from collections import defaultdict

        # 按 (year_month, oe, brand) 分组
        groups = defaultdict(list)
        for record in records:
            purchase_date = record['purchase_date']
            if hasattr(purchase_date, 'strftime'):
                year_month = purchase_date.strftime('%Y-%m')
            else:
                year_month = str(purchase_date)[:7]

            key = (year_month, record['oe'], record['brand'])
            groups[key].append(record)

        # 每组按单价升序、日期降序排序，取第一条
        result = []
        for key, group_records in groups.items():
            year_month = key[0]

            # 排序：单价升序，日期降序
            sorted_records = sorted(
                group_records,
                key=lambda x: (
                    x['unit_price'],
                    -x['purchase_date'].timestamp() if hasattr(x['purchase_date'], 'timestamp') else 0
                ),
                reverse=False
            )

            best_record = sorted_records[0]
            purchase_date = best_record['purchase_date']

            result.append({
                'year_month': year_month,
                'purchase_date': purchase_date.strftime('%Y-%m-%d') if hasattr(purchase_date, 'strftime') else str(purchase_date)[:10],
                'supplier_name': best_record['supplier_name'],
                'oe': best_record['oe'],
                'brand': best_record['brand'],
                'unit_price': best_record['unit_price']
            })

        return result

    def _update_procurement_history(
        self,
        company: str,
        year_months: List[str],
        records: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        覆盖式更新 crmapp_procurement_history 表

        Args:
            company: 公司代码
            year_months: 年月列表
            records: 聚合后的记录列表

        Returns:
            {'deleted': 删除条数, 'inserted': 插入条数}
        """
        result = {
            'deleted': 0,
            'inserted': 0
        }

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                conn.begin()

                # 1. 删除旧表中指定 company 和 year_months 的数据
                placeholders = ', '.join(['%s'] * len(year_months))
                delete_sql = f"""
                    DELETE FROM crmapp_procurement_history 
                    WHERE company = %s AND `year_month` IN ({placeholders})
                """
                delete_params = [company] + year_months
                cursor.execute(delete_sql, delete_params)
                result['deleted'] = cursor.rowcount
                print(f"删除旧记录: {result['deleted']} 条")

                # 2. 插入新聚合的数据
                if records:
                    insert_sql = """
                        INSERT INTO crmapp_procurement_history
                        (`year_month`, purchase_date, supplier_name, oe, brand, unit_price, company)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    values = []
                    for record in records:
                        values.append((
                            record['year_month'],
                            record['purchase_date'],
                            record['supplier_name'],
                            record['oe'],
                            record['brand'],
                            record['unit_price'],
                            company
                        ))

                    cursor.executemany(insert_sql, values)
                    result['inserted'] = len(records)
                    print(f"插入新记录: {result['inserted']} 条")

                conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"更新采购历史表失败: {e}")
            raise
        finally:
            conn.close()

        return result
