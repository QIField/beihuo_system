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
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 开始清空门店 {company} 数据...")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 执行 DELETE...")
            cursor.execute("DELETE FROM crmapp_beihuo WHERE company = %s", (company,))
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] DELETE 完成，提交事务...")
            conn.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 清空门店 {company} 数据完成")
            return True
    except Exception as e:
        conn.rollback()
        print(f"❌ [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 清空门店 {company} 数据失败: {e}")
        import traceback
        traceback.print_exc()
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
                    print(f"📊 门店 {company} 插入进度: {processed}/{total} ({processed * 100 // total}%)")
        
        # 最后提交剩余数据
        conn.commit()
        print(f"✅ 门店 {company} 数据插入完成，共 {processed} 条记录")
        
        return processed
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 插入门店 {company} 数据失败: {e}")
        raise  # 抛出异常让上层处理
    finally:
        cursor.close()
        conn.close()


def save_company_data(company: str, records: List[Dict[str, Any]]) -> int:
    """
    保存门店数据（清空+插入）
    
    Args:
        company: 门店代码
        records: 记录字典列表
        
    Returns:
        成功插入的记录数，失败返回 -1
    """
    if not records:
        print(f"⚠️ 门店 {company} 没有数据需要保存")
        return 0
    
    print(f"🗑️ 已清空门店 {company} 的现有数据，准备插入 {len(records)} 条记录")
    
    # 1. 清空数据
    if not clear_company_data(company):
        return -1
    
    # 2. 插入新数据
    try:
        return batch_insert_records(company, records)
    except Exception as e:
        print(f"❌ 保存门店 {company} 数据失败: {e}")
        return -1


def update_vehicle_fields(company: str) -> int:
    """
    从 crmapp_compare_summary 表更新车型和替换号信息
    
    优化策略：使用INNER JOIN只查询beihuo表中实际存在的条码的映射数据，批量更新
    性能提升：从扫描12万条减少到几千条，避免长时间锁表
    
    Args:
        company: 门店代码
        
    Returns:
        成功更新的记录数
    """
    from datetime import datetime
    import threading
    import pymysql.cursors
    
    thread_id = threading.current_thread().ident
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] [线程{thread_id}] 开始车型映射...")
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 优化：使用INNER JOIN只获取beihuo表中存在的条码的映射数据
        # 避免扫描全部12万条映射记录
        # 使用BINARY强制统一字符集比较，避免collation冲突
        cursor.execute("""
            SELECT DISTINCT b.物料条码, c.l_model_zh, c.replace_number
            FROM crmapp_beihuo b
            INNER JOIN crmapp_compare_summary c 
                ON BINARY b.company = BINARY c.company 
                AND BINARY b.物料条码 = BINARY c.frey_no
            WHERE b.company = %s
              AND c.frey_no IS NOT NULL 
              AND c.frey_no != ''
        """, (company,))
        
        mappings = cursor.fetchall()
        
        if not mappings:
            print(f"ℹ️ [线程{thread_id}] 门店 {company} 没有匹配到车型映射数据")
            return 0
        
        # 批量更新
        updates = [
            (m['l_model_zh'] or '', m['replace_number'] or '', m['物料条码'], company)
            for m in mappings
        ]
        
        cursor.executemany("""
            UPDATE crmapp_beihuo 
            SET 车型 = %s, 替换号 = %s 
            WHERE 物料条码 = %s AND company = %s
        """, updates)
        
        conn.commit()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"🚗 [线程{thread_id}] 门店 {company} 车型映射完成，更新 {len(updates)} 条记录，耗时: {elapsed:.3f}s")
        
        return len(updates)
        
    except Exception as e:
        conn.rollback()
        import traceback
        print(f"❌ [线程{thread_id}] 更新门店 {company} 车型信息失败: {e}")
        traceback.print_exc()
        return -1
    finally:
        cursor.close()
        conn.close()
