"""
采购数据同步服务
用于将 crmapp_procurement_history 表的数据同步到 crmapp_compare_summary 表
"""

import json
import pymysql
from datetime import datetime
from typing import List, Dict, Any, Tuple

from app.utils.database_connection import get_db_connection


COMPANY = 'fsbbr'


class PurchaseSyncService:
    """采购数据同步服务类"""

    def __init__(self):
        self.total_synced = 0
        self.total_duplicates = 0

    def sync_to_compare_summary(self, company: str = COMPANY) -> Dict[str, int]:
        """
        将采购历史数据同步到比价汇总表
        主入口方法

        Args:
            company: 公司代码

        Returns:
            {'saved': 同步记录数, 'duplicate': 重复记录数}
        """
        print(f"\n{'='*60}")
        print(f"开始采购数据同步到比价表")
        print(f"{'='*60}")

        result = {
            'saved': 0,
            'duplicate': 0
        }

        # 获取所有需要同步的 OE+品牌 组合
        oe_brand_list = self._get_all_oe_brand(company)
        print(f"共有 {len(oe_brand_list)} 个 OE+品牌 组合需要同步")

        for idx, (oe, brand) in enumerate(oe_brand_list, 1):
            try:
                # 计算该 OE+品牌 的各项价格数据
                max_price, min_price = self._calculate_max_min_price(oe, brand, company)
                supplier_price = self._get_latest_price(oe, brand, company)

                # 更新比价表
                updated = self._update_compare_summary(
                    oe, brand, company,
                    max_price, min_price, supplier_price
                )

                if updated:
                    result['saved'] += 1
                else:
                    result['duplicate'] += 1

                # 每100条输出进度
                if idx % 100 == 0:
                    print(f"已处理 {idx}/{len(oe_brand_list)} 条...")

            except Exception as e:
                print(f"同步失败 OE={oe}, brand={brand}: {e}")
                result['duplicate'] += 1

        print(f"\n{'='*60}")
        print(f"采购数据同步完成!")
        print(f"同步记录数: {result['saved']}")
        print(f"重复/失败: {result['duplicate']}")
        print(f"{'='*60}")

        return result

    def _get_all_oe_brand(self, company: str) -> List[Tuple[str, str]]:
        """
        获取所有唯一的 OE+品牌 组合

        Args:
            company: 公司代码

        Returns:
            [(oe, brand), ...]
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT DISTINCT oe, brand 
                    FROM crmapp_procurement_history 
                    WHERE company = %s
                """
                cursor.execute(sql, (company,))
                return [(row['oe'], row['brand']) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _calculate_max_min_price(self, oe: str, brand: str, company: str) -> Tuple[float, float]:
        """
        计算同一OE+品牌的最高和最低采购价

        Args:
            oe: OE号
            brand: 品牌
            company: 公司代码

        Returns:
            (最高价, 最低价)
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                    SELECT MAX(unit_price) as max_price, MIN(unit_price) as min_price
                    FROM crmapp_procurement_history
                    WHERE oe = %s AND brand = %s AND company = %s
                    AND unit_price > 0
                """
                cursor.execute(sql, (oe, brand, company))
                result = cursor.fetchone()

                if result:
                    return float(result['max_price'] or 0.0), float(result['min_price'] or 0.0)
                return 0.0, 0.0
        finally:
            conn.close()

    def _get_latest_price(self, oe: str, brand: str, company: str) -> float:
        """
        获取同一OE+品牌最新日期的采购价

        Args:
            oe: OE号
            brand: 品牌
            company: 公司代码

        Returns:
            最新价格
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                    SELECT unit_price
                    FROM crmapp_procurement_history
                    WHERE oe = %s AND brand = %s AND company = %s
                    ORDER BY purchase_date DESC
                    LIMIT 1
                """
                cursor.execute(sql, (oe, brand, company))
                result = cursor.fetchone()

                if result:
                    return float(result['unit_price'] or 0.0)
                return 0.0
        finally:
            conn.close()

    def _build_procurement_records(self, oe: str, brand: str, company: str) -> List[Dict]:
        """
        构建采购记录JSON数组
        每个月份取最低价的记录

        Args:
            oe: OE号
            brand: 品牌
            company: 公司代码

        Returns:
            [{"supplier_name": "...", "purchase_price": 100, "purchase_date": "..."}, ...]
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 按年月分组，取每组最低价的记录
                sql = """
                    SELECT `year_month`, MIN(unit_price) as min_price
                    FROM crmapp_procurement_history
                    WHERE oe = %s AND brand = %s AND company = %s
                    AND unit_price > 0
                    GROUP BY `year_month`
                    ORDER BY `year_month` DESC
                """
                cursor.execute(sql, (oe, brand, company))
                monthly_min = cursor.fetchall()

                records = []
                for year_month, min_price in monthly_min:
                    # 获取该月最低价的详细记录（取第一条）
                    detail_sql = """
                        SELECT supplier_name, unit_price, purchase_date
                        FROM crmapp_procurement_history
                        WHERE oe = %s AND brand = %s AND company = %s
                        AND `year_month` = %s AND unit_price = %s
                        ORDER BY purchase_date DESC
                        LIMIT 1
                    """
                    cursor.execute(detail_sql, (oe, brand, company, year_month, min_price))
                    detail = cursor.fetchone()

                    if detail:
                        records.append({
                            'supplier_name': detail[0],
                            'purchase_price': float(detail[1]),
                            'purchase_date': detail[2].strftime('%Y-%m-%d') if hasattr(detail[2], 'strftime') else str(detail[2])
                        })

                return records
        finally:
            conn.close()

    def _update_compare_summary(self, oe: str, brand: str, company: str,
                                 max_price: float, min_price: float,
                                 supplier_price: float) -> bool:
        """
        更新比价汇总表

        Args:
            oe: OE号
            brand: 品牌
            company: 公司代码
            max_price: 最高价
            min_price: 最低价
            supplier_price: 供应商价格

        Returns:
            是否更新成功
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 检查记录是否存在
                check_sql = """
                    SELECT id FROM crmapp_compare_summary
                    WHERE oe = %s AND brand = %s AND company = %s
                """
                cursor.execute(check_sql, (oe, brand, company))
                existing = cursor.fetchone()

                if existing:
                    # 更新现有记录
                    update_sql = """
                        UPDATE crmapp_compare_summary
                        SET max_price = %s,
                            min_price = %s,
                            supplier_price = %s,
                            updated_time = NOW()
                        WHERE oe = %s AND brand = %s AND company = %s
                    """
                    cursor.execute(update_sql, (
                        max_price, min_price, supplier_price,
                        oe, brand, company
                    ))
                else:
                    # 插入新记录（只填充价格相关字段）
                    insert_sql = """
                        INSERT INTO crmapp_compare_summary
                        (oe, brand, company, max_price, min_price, supplier_price)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (
                        oe, brand, company, max_price, min_price, supplier_price
                    ))

                conn.commit()
                return True

        except Exception as e:
            conn.rollback()
            print(f"更新比价表失败 OE={oe}, brand={brand}: {e}")
            return False
        finally:
            conn.close()

    def sync_single_product(self, oe: str, brand: str, company: str = COMPANY) -> bool:
        """
        同步单个产品的采购数据
        用于询价导入后触发同步

        Args:
            oe: OE号
            brand: 品牌
            company: 公司代码

        Returns:
            是否同步成功
        """
        try:
            max_price, min_price = self._calculate_max_min_price(oe, brand, company)
            supplier_price = self._get_latest_price(oe, brand, company)

            return self._update_compare_summary(
                oe, brand, company,
                max_price, min_price, supplier_price
            )
        except Exception as e:
            print(f"同步单个产品失败 OE={oe}, brand={brand}: {e}")
            return False
