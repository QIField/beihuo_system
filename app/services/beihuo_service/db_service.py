"""
备货数据数据库服务

负责数据库操作，包括清空数据和批量插入。
"""

from typing import Dict, Any, List

from app.utils.database_connection import get_db_connection
from .config import BATCH_SIZE, COMMIT_INTERVAL, DB_FIELDS


def clear_company_data(company: str) -> bool:
    """
    清空指定门店的数据
    
    Args:
        company: 门店代码
        
    Returns:
        是否成功
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM crmapp_beihuo WHERE company = %s", (company,))
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"[失败] 清空门店 {company} 数据失败: {e}")
        return False
    finally:
        conn.close()


def batch_insert_records(company: str, records: List[Dict[str, Any]]) -> int:
    """
    批量插入记录
    
    使用配置中的字段映射（DB_FIELDS）构建SQL，确保字段顺序和完整性
    
    Args:
        company: 门店代码
        records: 记录字典列表
        
    Returns:
        成功插入的记录数
    """
    if not records:
        return 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        total = len(records)
        processed = 0
        batch_count = 0
        
        # 使用配置的字段列表构建SQL（显式字段映射）
        columns = DB_FIELDS
        columns_str = ", ".join([f"`{c}`" for c in columns])
        placeholders = ", ".join([f"%({c})s" for c in columns])
        
        # 构建INSERT SQL
        insert_sql = f"""
            INSERT INTO `crmapp_beihuo` ({columns_str})
            VALUES ({placeholders})
        """
        
        # 批量插入
        for i in range(0, total, BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            
            if batch:
                cursor.executemany(insert_sql, batch)
                processed += len(batch)
                batch_count += 1
                
                # 每 COMMIT_INTERVAL 批次提交一次
                if batch_count % COMMIT_INTERVAL == 0:
                    conn.commit()
                    print(f"[统计] 门店 {company} 插入进度: {processed}/{total} ({processed * 100 // total}%)")
        
        # 最后提交剩余数据
        conn.commit()
        print(f"[成功] 门店 {company} 数据插入完成，共 {processed} 条记录")
        
        return processed
        
    except Exception as e:
        conn.rollback()
        print(f"[失败] 插入门店 {company} 数据失败: {e}")
        raise  # 抛出异常让上层处理
    finally:
        cursor.close()
        conn.close()


def save_company_data(company: str, records: List[Dict[str, Any]]) -> int:
    """
    保存门店数据（清空+插入）

    原子性保证：DELETE 和 INSERT 在同一个数据库事务中执行。
    如果 INSERT 失败，DELETE 会自动回滚，避免门店数据被清空后无法恢复。

    Args:
        company: 门店代码
        records: 记录字典列表

    Returns:
        成功插入的记录数，失败返回 -1
    """
    if not records:
        print(f"[警告] 门店 {company} 没有数据需要保存")
        return 0

    print(f"[保存] 门店 {company} 原子性保存开始，准备替换为 {len(records)} 条记录")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. 在同一个事务中清空旧数据
        cursor.execute("DELETE FROM crmapp_beihuo WHERE company = %s", (company,))
        deleted = cursor.rowcount
        print(f"[保存] 门店 {company} 已清空 {deleted} 条旧数据")

        # 2. 在同一个事务中批量插入新数据
        columns = DB_FIELDS
        columns_str = ", ".join([f"`{c}`" for c in columns])
        placeholders = ", ".join([f"%({c})s" for c in columns])

        insert_sql = f"""
            INSERT INTO `crmapp_beihuo` ({columns_str})
            VALUES ({placeholders})
        """

        total = len(records)
        processed = 0
        batch_count = 0

        for i in range(0, total, BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]

            if batch:
                cursor.executemany(insert_sql, batch)
                processed += len(batch)
                batch_count += 1

                if batch_count % COMMIT_INTERVAL == 0:
                    print(f"[统计] 门店 {company} 插入进度: {processed}/{total} ({processed * 100 // total}%)")

        # 3. 全部成功后再统一提交
        conn.commit()
        print(f"[成功] 门店 {company} 数据原子性保存完成，共 {processed} 条记录")
        return processed

    except Exception as e:
        # 任何步骤失败都回滚整个事务，旧数据保留，不会出现空表
        conn.rollback()
        print(f"[失败] 门店 {company} 原子性保存失败，已回滚，旧数据保留: {e}")
        return -1

    finally:
        cursor.close()
        conn.close()


def update_vehicle_fields(company: str) -> int:
    """
    从 crmapp_compare_summary 表更新车型和替换号信息
    
    根据物料条码匹配，补充 crmapp_beihuo 表中的车型和替换号字段
    
    Args:
        company: 门店代码
        
    Returns:
        成功更新的记录数
    """
    import pymysql.cursors
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 1. 获取该门店在 crmapp_compare_summary 中的车型映射与采购记录数据
        cursor.execute("""
            SELECT frey_no, l_model_zh, replace_number, purchase_records
            FROM crmapp_compare_summary 
            WHERE company = %s AND frey_no IS NOT NULL AND frey_no != ''
        """, (company,))
        
        mapping_results = cursor.fetchall()
        
        if not mapping_results:
            print(f"[信息] 门店 {company} 没有车型映射数据")
            return 0
        
        # 2. 构建映射字典
        mapping = {}
        for row in mapping_results:
            frey_no = row['frey_no']
            mapping[frey_no] = {
                'l_model_zh': row['l_model_zh'] or '',  # 车型
                'replace_number': row['replace_number'] or '',  # 替换号
                'purchase_records': row['purchase_records'] or None  # 采购记录
            }
        
        # 3. 获取该门店在 crmapp_beihuo 中的物料条码列表
        cursor.execute("""
            SELECT id, 物料条码 
            FROM crmapp_beihuo 
            WHERE company = %s AND 物料条码 IS NOT NULL AND 物料条码 != ''
        """, (company,))
        
        beihuo_records = cursor.fetchall()
        
        if not beihuo_records:
            print(f"[信息] 门店 {company} 没有需要更新的备货数据")
            return 0
        
        # 4. 批量更新匹配的记录（使用 executemany 提升性能）
        update_data = []
        for record in beihuo_records:
            record_id = record['id']
            barcode = record['物料条码']
            
            if barcode in mapping:
                update_data.append((
                    mapping[barcode]['l_model_zh'],
                    mapping[barcode]['replace_number'],
                    mapping[barcode]['purchase_records'],
                    record_id
                ))
        
        if update_data:
            cursor.executemany("""
                UPDATE crmapp_beihuo 
                SET 车型 = %s, 替换号 = %s, purchase_records = %s
                WHERE id = %s
            """, update_data)
            conn.commit()
        
        updated_count = len(update_data)
        
        if updated_count > 0:
            print(f"[车型] 门店 {company} 车型映射完成，更新 {updated_count} 条记录")
        else:
            print(f"[信息] 门店 {company} 没有匹配到车型数据")
        
        return updated_count
        
    except Exception as e:
        conn.rollback()
        import traceback
        print(f"[失败] 更新门店 {company} 车型信息失败: {e}")
        traceback.print_exc()
        return -1
    finally:
        cursor.close()
        conn.close()
