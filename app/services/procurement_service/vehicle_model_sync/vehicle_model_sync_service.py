"""
车型同步服务
用于CRM产品爬取完成后同步车型字段
"""

from typing import Dict, Tuple, Optional
from app.utils.database_connection import get_db_connection
from .brand_priority import BrandPriority


class VehicleModelSyncService:
    """车型同步服务类"""

    def __init__(self):
        self.oe_model_map: Dict[str, Tuple[str, int]] = {}

    def collect_model_mapping(self, oe: str, brand: str, model: str):
        """
        收集OE-车型映射关系

        Args:
            oe: OE号
            brand: 品牌
            model: 车型
        """
        if not oe or not model:
            return

        priority = BrandPriority.get_priority(brand)

        # 只收集高优先级的车型（原厂国内4s件或原厂）
        if priority > 2:
            return

        # 如果该OE已有记录，保留优先级更高的
        if oe in self.oe_model_map:
            existing_model, existing_priority = self.oe_model_map[oe]
            if priority < existing_priority:
                self.oe_model_map[oe] = (model, priority)
        else:
            self.oe_model_map[oe] = (model, priority)

    def sync_to_database(self, company: str = 'fsbbr') -> Dict[str, int]:
        """
        将收集的车型映射同步到数据库

        Args:
            company: 公司代码

        Returns:
            {'updated': 更新记录数}
        """
        if not self.oe_model_map:
            print("[车型同步] 没有需要同步的车型数据")
            return {'updated': 0}

        print(f"\n{'='*60}")
        print("开始车型同步")
        print(f"{'='*60}")
        print(f"共有 {len(self.oe_model_map)} 个OE需要同步")

        total_updated = 0
        conn = get_db_connection()

        try:
            with conn.cursor() as cursor:
                # 分批处理，每批1000个OE
                batch_size = 1000
                oe_items = list(self.oe_model_map.items())

                for i in range(0, len(oe_items), batch_size):
                    batch = oe_items[i:i + batch_size]
                    updated = self._update_batch(cursor, batch, company)
                    total_updated += updated

                    if (i // batch_size + 1) % 10 == 0:
                        print(f"  已处理 {min(i + batch_size, len(oe_items))}/{len(oe_items)} 个OE...")

                conn.commit()

            print(f"\n[车型同步] 完成:")
            print(f"  - 更新记录数: {total_updated}")
            print(f"{'='*60}")

            return {'updated': total_updated}

        except Exception as e:
            conn.rollback()
            print(f"\n[车型同步] 失败: {e}")
            import traceback
            traceback.print_exc()
            return {'updated': 0}

        finally:
            conn.close()

    def _update_batch(self, cursor, batch: list, company: str) -> int:
        """
        批量更新一批OE的车型（参数化查询，无SQL注入风险）

        实现方式：使用临时表 + JOIN 更新，避免字符串拼接SQL。
        所有数据通过 executemany 参数化传入，即使OE或车型包含特殊字符也安全。

        Args:
            cursor: 数据库游标
            batch: [(oe, (model, priority)), ...]
            company: 公司代码

        Returns:
            更新的记录数
        """
        if not batch:
            return 0

        # 1. 创建临时表（SESSION 级别，连接关闭自动清理）
        cursor.execute("""
            CREATE TEMPORARY TABLE IF NOT EXISTS temp_oe_model (
                oe VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
                l_model_zh TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                PRIMARY KEY (oe)
            ) ENGINE=InnoDB
        """)

        # 2. 清空临时表（确保当前批次无脏数据）
        cursor.execute("TRUNCATE TABLE temp_oe_model")

        # 3. 批量插入到临时表（完全参数化，无注入风险）
        insert_sql = "INSERT INTO temp_oe_model (oe, l_model_zh) VALUES (%s, %s)"
        data = [(oe, model) for oe, (model, priority) in batch]
        cursor.executemany(insert_sql, data)

        # 4. 通过 JOIN 更新目标表（参数化查询）
        update_sql = """
            UPDATE crmapp_compare_summary t
            INNER JOIN temp_oe_model tmp ON t.oe = tmp.oe
            SET t.l_model_zh = tmp.l_model_zh
            WHERE t.company = %s
        """
        cursor.execute(update_sql, (company,))
        return cursor.rowcount

    def get_stats(self) -> Dict[str, any]:
        """
        获取收集的统计信息

        Returns:
            统计信息字典
        """
        priority_1_count = sum(1 for _, p in self.oe_model_map.values() if p == 1)
        priority_2_count = sum(1 for _, p in self.oe_model_map.values() if p == 2)

        return {
            'total_oe': len(self.oe_model_map),
            'priority_1_count': priority_1_count,  # 原厂国内4s件
            'priority_2_count': priority_2_count,  # 原厂
        }

    def clear(self):
        """清空收集的映射数据"""
        self.oe_model_map.clear()
