"""
采购数据同步服务
用于将采购历史数据同步到 crmapp_compare_summary 表
支持从三个表查询价格：procurement_history, price_inquiry, price_inquiry_direct
"""

import pymysql
from datetime import datetime
from typing import List, Dict, Any, Tuple

from app.utils.database_connection import get_db_connection


COMPANY = 'fsbbr'


def _get_field(row, field_name: str, index: int):
    """
    从数据库行中获取字段值，兼容字典游标和元组游标

    Args:
        row: 数据库行（字典或元组）
        field_name: 字段名（用于字典游标）
        index: 字段索引（用于元组游标）

    Returns:
        字段值
    """
    if isinstance(row, dict):
        return row.get(field_name)
    else:
        return row[index] if index < len(row) else None


class PurchaseSyncService:
    """采购数据同步服务类"""

    def __init__(self):
        self.total_synced = 0
        self.total_duplicates = 0

    def sync_to_compare_summary(self, company: str = COMPANY) -> Dict[str, int]:
        """
        将采购历史数据同步到比价汇总表
        使用批量 SQL 替代逐条处理，提升性能

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

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 使用批量 SQL 一次性计算并更新所有价格数据
                # 1. 先创建临时表存储基础价格数据
                create_temp_sql = """
                    CREATE TEMPORARY TABLE IF NOT EXISTS temp_all_prices (
                        oe VARCHAR(255),
                        brand VARCHAR(255),
                        unit_price DECIMAL(10,2),
                        purchase_date DATETIME,
                        src INT,
                        INDEX idx_oe_brand (oe, brand),
                        INDEX idx_date (purchase_date)
                    )
                """
                cursor.execute(create_temp_sql)

                # 2. 将三个表的数据插入临时表
                insert_prices_sql = """
                    INSERT INTO temp_all_prices (oe, brand, unit_price, purchase_date, src)
                    SELECT oe, brand, unit_price, purchase_date, 1 as src
                    FROM crmapp_procurement_history
                    WHERE company = %s AND unit_price > 0
                    UNION ALL
                    SELECT oe, brand, original_price as unit_price, import_time as purchase_date, 2 as src
                    FROM crmapp_price_inquiry
                    WHERE company = %s AND original_price > 0
                    UNION ALL
                    SELECT oe, brand, original_price as unit_price, import_time as purchase_date, 3 as src
                    FROM crmapp_price_inquiry_direct
                    WHERE company = %s AND original_price > 0
                """
                cursor.execute(insert_prices_sql, (company, company, company))

                # 3. 创建临时表存储统计结果
                create_stats_sql = """
                    CREATE TEMPORARY TABLE IF NOT EXISTS temp_price_stats (
                        oe VARCHAR(255),
                        brand VARCHAR(255),
                        max_price DECIMAL(10,2),
                        min_price DECIMAL(10,2),
                        supplier_price DECIMAL(10,2),
                        PRIMARY KEY (oe, brand)
                    )
                """
                cursor.execute(create_stats_sql)

                # 4. 计算最高和最低价格
                insert_stats_sql = """
                    INSERT INTO temp_price_stats (oe, brand, max_price, min_price, supplier_price)
                    SELECT 
                        oe,
                        brand,
                        MAX(unit_price) as max_price,
                        MIN(unit_price) as min_price,
                        0 as supplier_price
                    FROM temp_all_prices
                    GROUP BY oe, brand
                """
                cursor.execute(insert_stats_sql)

                # 5. 更新最新价格（使用关联子查询）
                update_latest_sql = """
                    UPDATE temp_price_stats tps
                    SET supplier_price = (
                        SELECT unit_price 
                        FROM temp_all_prices tap 
                        WHERE tap.oe = tps.oe 
                        AND tap.brand = tps.brand
                        ORDER BY tap.purchase_date DESC, tap.src ASC 
                        LIMIT 1
                    )
                """
                cursor.execute(update_latest_sql)

                # 6. 获取统计数量
                cursor.execute("SELECT COUNT(*) as cnt FROM temp_price_stats")
                count_result = cursor.fetchone()
                temp_count = count_result['cnt'] if isinstance(count_result, dict) else count_result[0]
                print(f"计算出 {temp_count} 条价格统计")

                # 7. 批量更新到比价汇总表（使用 INSERT ... ON DUPLICATE KEY UPDATE）
                upsert_sql = """
                    INSERT INTO crmapp_compare_summary 
                    (oe, brand, company, max_price, min_price, supplier_price, updated_time)
                    SELECT oe, brand, %s, max_price, min_price, supplier_price, NOW()
                    FROM temp_price_stats
                    ON DUPLICATE KEY UPDATE
                        max_price = VALUES(max_price),
                        min_price = VALUES(min_price),
                        supplier_price = VALUES(supplier_price),
                        updated_time = VALUES(updated_time)
                """
                cursor.execute(upsert_sql, (company,))
                affected_rows = cursor.rowcount

                # 8. 清理临时表
                cursor.execute("DROP TEMPORARY TABLE IF EXISTS temp_all_prices")
                cursor.execute("DROP TEMPORARY TABLE IF EXISTS temp_price_stats")

                conn.commit()

                result['saved'] = temp_count
                result['duplicate'] = 0

                print(f"同步完成: 计算 {temp_count} 条, 影响 {affected_rows} 条")

        except Exception as e:
            conn.rollback()
            print(f"批量同步失败: {e}")
            import traceback
            traceback.print_exc()
            result['duplicate'] = 1
        finally:
            conn.close()

        print(f"\n{'='*60}")
        print(f"采购数据同步完成!")
        print(f"同步记录数: {result['saved']}")
        print(f"重复/失败: {result['duplicate']}")
        print(f"{'='*60}")

        return result

    def _get_all_oe_brand(self, company: str) -> List[Tuple[str, str]]:
        """
        获取所有唯一的 OE+品牌 组合
        从 procurement_history 表获取（聚合后的数据）

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
                rows = cursor.fetchall()
                # 使用字段映射获取数据，兼容字典游标和元组游标
                return [
                    (_get_field(row, 'oe', 0), _get_field(row, 'brand', 1))
                    for row in rows
                ]
        finally:
            conn.close()

    def _calculate_max_min_price(self, oe: str, brand: str, company: str) -> Tuple[float, float]:
        """
        计算同一OE+品牌的最高和最低采购价
        从三个表查询：procurement_history, price_inquiry, price_inquiry_direct

        Args:
            oe: OE号
            brand: 品牌
            company: 公司代码

        Returns:
            (最高价, 最低价)
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 从三个表 UNION ALL 查询价格
                sql = """
                    SELECT 
                        MAX(unit_price) as max_price, 
                        MIN(unit_price) as min_price
                    FROM (
                        -- 从采购汇总表查询
                        SELECT unit_price 
                        FROM crmapp_procurement_history
                        WHERE oe = %s AND brand = %s AND company = %s AND unit_price > 0
                        
                        UNION ALL
                        
                        -- 从正常询价表查询
                        SELECT original_price as unit_price 
                        FROM crmapp_price_inquiry
                        WHERE oe = %s AND brand = %s AND company = %s AND original_price > 0
                        
                        UNION ALL
                        
                        -- 从直接入库表查询
                        SELECT original_price as unit_price 
                        FROM crmapp_price_inquiry_direct
                        WHERE oe = %s AND brand = %s AND company = %s AND original_price > 0
                    ) t
                """
                cursor.execute(sql, (
                    oe, brand, company,
                    oe, brand, company,
                    oe, brand, company
                ))
                result = cursor.fetchone()

                if result:
                    # 使用字段映射获取数据，兼容字典游标和元组游标
                    max_price = _get_field(result, 'max_price', 0)
                    min_price = _get_field(result, 'min_price', 1)
                    if max_price is not None:
                        return float(max_price), float(min_price)
                return 0.0, 0.0
        finally:
            conn.close()

    def _get_latest_price(self, oe: str, brand: str, company: str) -> float:
        """
        获取同一OE+品牌最新日期的采购价
        从三个表查询，取日期最新的价格

        Args:
            oe: OE号
            brand: 品牌
            company: 公司代码

        Returns:
            最新价格
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 从三个表查询最新价格
                sql = """
                    SELECT unit_price, purchase_date
                    FROM (
                        -- 从采购汇总表查询
                        SELECT 
                            unit_price,
                            purchase_date,
                            1 as source_order
                        FROM crmapp_procurement_history
                        WHERE oe = %s AND brand = %s AND company = %s AND unit_price > 0
                        
                        UNION ALL
                        
                        -- 从正常询价表查询
                        SELECT 
                            original_price as unit_price,
                            import_time as purchase_date,
                            2 as source_order
                        FROM crmapp_price_inquiry
                        WHERE oe = %s AND brand = %s AND company = %s AND original_price > 0
                        
                        UNION ALL
                        
                        -- 从直接入库表查询
                        SELECT 
                            original_price as unit_price,
                            import_time as purchase_date,
                            3 as source_order
                        FROM crmapp_price_inquiry_direct
                        WHERE oe = %s AND brand = %s AND company = %s AND original_price > 0
                    ) t
                    ORDER BY purchase_date DESC, source_order ASC
                    LIMIT 1
                """
                cursor.execute(sql, (
                    oe, brand, company,
                    oe, brand, company,
                    oe, brand, company
                ))
                result = cursor.fetchone()

                if result:
                    # 使用字段映射获取数据，兼容字典游标和元组游标
                    unit_price = _get_field(result, 'unit_price', 0)
                    if unit_price is not None:
                        return float(unit_price)
                return 0.0
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
            with conn.cursor() as cursor:
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
