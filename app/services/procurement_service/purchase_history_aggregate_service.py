"""
采购历史聚合服务
用于从新表 crmapp_procurement_history_detail 聚合数据到旧表 crmapp_procurement_history
确保价格-供应商一一对应，取每组最低价且最新的一条记录
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

    def aggregate_and_update(self, company: str = COMPANY) -> Dict[str, int]:
        """
        聚合并更新采购历史数据
        主入口方法

        Args:
            company: 公司代码

        Returns:
            {'deleted': 删除条数, 'inserted': 插入条数}
        """
        print(f"\n{'='*60}")
        print(f"开始采购历史数据聚合")
        print(f"{'='*60}")

        # 计算上个月和本月的年月字符串
        year_months, start_date, end_date = self._calculate_date_range()
        print(f"处理月份: {', '.join(year_months)}")
        print(f"时间范围: {start_date} ~ {end_date}")

        # 从新表聚合数据
        records = self._aggregate_from_detail(company, start_date, end_date)
        print(f"聚合记录数: {len(records)}")

        # 更新旧表
        result = self._update_old_table(company, year_months, records)

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

    def _aggregate_from_detail(self, company: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        从 crmapp_procurement_history_detail 表聚合数据
        使用 Python 聚合：取每组 (year_month, oe, brand) 最低价且最新的一条

        Args:
            company: 公司代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            聚合后的记录列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 先查询所有数据，然后在 Python 中聚合
                sql = """
                    SELECT 
                        create_date,
                        fullname,
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
                
                # 在 Python 中聚合：每组 (year_month, oe, brand) 取第一条（最低价且最新）
                from collections import defaultdict
                
                # 按 (year_month, oe, brand) 分组，保留最低价且最新的
                groups = defaultdict(list)
                for row in rows:
                    create_date = row[0]
                    year_month = create_date.strftime('%Y-%m') if hasattr(create_date, 'strftime') else str(create_date)[:7]
                    key = (year_month, row[2], row[3])  # (year_month, oe, brand)
                    groups[key].append(row)
                
                # 每组按单价升序、日期降序排序，取第一条
                seen = {}
                for key, group_rows in groups.items():
                    # 排序：单价升序，日期降序
                    sorted_rows = sorted(group_rows, key=lambda x: (x[4], -x[0].timestamp() if hasattr(x[0], 'timestamp') else 0))
                    seen[key] = sorted_rows[0]

                records = []
                for key, row in seen.items():
                    create_date = row[0]
                    year_month = key[0]
                    records.append({
                        'year_month': year_month,
                        'purchase_date': create_date.strftime('%Y-%m-%d') if hasattr(create_date, 'strftime') else str(create_date)[:10],
                        'fullname': row[1],
                        'oe': row[2],
                        'brand': row[3],
                        'unit_price': float(row[4]) if row[4] else 0.0
                    })

                return records
        finally:
            conn.close()

    def _update_old_table(self, company: str, year_months: List[str], records: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        覆盖式更新旧表 crmapp_procurement_history
        先删除旧数据，再插入新聚合的数据

        Args:
            company: 公司代码
            year_months: 年月列表，如 ['2026-02', '2026-03']
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
                # 开启事务
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
                            record['fullname'],
                            record['oe'],
                            record['brand'],
                            record['unit_price'],
                            company
                        ))

                    cursor.executemany(insert_sql, values)
                    result['inserted'] = len(records)
                    print(f"插入新记录: {result['inserted']} 条")

                # 提交事务
                conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"更新旧表失败: {e}")
            raise
        finally:
            conn.close()

        return result
