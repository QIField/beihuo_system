"""
比价导入结果快照服务

把导入计算出的 OECompareResult 序列化为 JSON 快照存入
crmapp_compare_import_result，供网页结果视图查看。

设计：
- 快照不可变，与历史导出 Excel 语义一致（记录计算当时的价格/销量）
- 一个导入批次（log_id）对应一行 JSON
- 表通过 CREATE TABLE IF NOT EXISTS 幂等创建，无需手动建表
"""
import json
from typing import List, Dict, Optional, Set

import pymysql

from app.utils.database_connection import get_db_connection
from app.models.purchase_history_compare_models import OECompareResult


class CompareResultSnapshotService:
    """比价导入结果快照存取"""

    TABLE_NAME = 'crmapp_compare_import_result'
    _table_ensured = False

    # ── 建表 ──

    @classmethod
    def ensure_table(cls):
        """幂等建表（IF NOT EXISTS），每进程只执行一次"""
        if cls._table_ensured:
            return
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {cls.TABLE_NAME} (
                        id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                        company      VARCHAR(32)  NOT NULL COMMENT '公司代码',
                        log_id       INT UNSIGNED NOT NULL COMMENT '关联导入日志ID（应用层关联，无外键）',
                        file_name    VARCHAR(255) NOT NULL DEFAULT '' COMMENT '原始文件名',
                        result_json  LONGTEXT     COMMENT '比对结果快照JSON',
                        created_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_log_id (log_id),
                        KEY idx_company_created (company, created_time)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='比价导入结果快照'
                """)
            conn.commit()
            cls._table_ensured = True
        finally:
            conn.close()

    # ── 序列化 ──

    @staticmethod
    def _serialize_purchase_record(record) -> Dict:
        """单条采购记录 → 前端浮窗使用的结构"""
        return {
            'date': f'{record.year}-{record.month:02d}',
            'supplier': record.supplier or '',
            'price': record.price,
        }

    @classmethod
    def serialize_results(cls, results: List[OECompareResult]) -> str:
        """
        将 OECompareResult 列表序列化为 JSON 字符串。
        月份明细来自 MonthSummary.all_records（已按价格升序），不额外查库。
        """
        payload = []
        for r in results:
            months = {}
            all_records = []
            for month, summary in r.month_summaries.items():
                records = [cls._serialize_purchase_record(rec) for rec in summary.all_records]
                months[str(month)] = {
                    'lowest_price': summary.lowest_price,
                    'records': records,
                }
                all_records.extend(records)

            all_records.sort(key=lambda x: x['date'], reverse=True)

            payload.append({
                'group_index': r.group_index,
                'search_oe': r.search_oe or '',
                'search_brand': r.search_brand or '',
                'brand_code': r.brand_code or '',
                'oe': r.oe or '',
                'price': r.price,
                'price_4s_cost': r.price_4s_cost,
                'price_4s_sale': r.price_4s_sale,
                'brand': r.brand or '',
                'product_name': r.product_name if r.product_name else ('未匹配到数据' if not r.frey_no and not r.month_summaries else ''),
                'spec': r.spec or '',
                'replace_name': r.replace_name or '',
                'stock_quantity': r.stock_quantity,
                'replace_stock_text': r.replace_stock_text or '',
                'tag': r.tag or '',
                'inquiry_1m': r.inquiry_1m,
                'inquiry_3m_avg': r.inquiry_3m_avg,
                'sales_6m_avg': r.sales_6m_avg,
                'inquiry_1m_national': r.inquiry_1m_national,
                'inquiry_3m_avg_national': r.inquiry_3m_avg_national,
                'sales_today': r.sales_today,
                'sales_yesterday': r.sales_yesterday,
                'sales_7d': r.sales_7d,
                'sales_month': r.sales_month,
                'sales_6m': r.sales_6m,
                'sales_12m': r.sales_12m,
                'overall_lowest': list(r.overall_lowest) if r.overall_lowest and r.overall_lowest[0] else None,
                'overall_highest': list(r.overall_highest) if r.overall_highest and r.overall_highest[0] else None,
                'months': months,
                'all_records': all_records,
            })
        return json.dumps(payload, ensure_ascii=False)

    # ── 存取 ──

    @classmethod
    def save_snapshot(cls, company: str, log_id: int, file_name: str,
                      results: List[OECompareResult]) -> None:
        """保存一个导入批次的结果快照"""
        cls.ensure_table()
        result_json = cls.serialize_results(results)
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"INSERT INTO {cls.TABLE_NAME} "
                    f"(company, log_id, file_name, result_json, created_time) "
                    f"VALUES (%s, %s, %s, %s, NOW())",
                    (company, log_id, file_name, result_json)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def get_snapshot(cls, log_id: int, company: str) -> Optional[List[Dict]]:
        """按日志ID+公司读取快照结果，不存在返回 None"""
        cls.ensure_table()
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
                cursor.execute(
                    f"SELECT result_json FROM {cls.TABLE_NAME} "
                    f"WHERE log_id = %s AND company = %s LIMIT 1",
                    (log_id, company)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return json.loads(row[0])
        finally:
            conn.close()

    @classmethod
    def existing_log_ids(cls, company: str, log_ids: List[int]) -> Set[int]:
        """在给定日志ID中，筛出已有快照的ID集合"""
        if not log_ids:
            return set()
        cls.ensure_table()
        placeholders = ', '.join(['%s'] * len(log_ids))
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
                cursor.execute(
                    f"SELECT log_id FROM {cls.TABLE_NAME} "
                    f"WHERE company = %s AND log_id IN ({placeholders})",
                    [company] + list(log_ids)
                )
                return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()
