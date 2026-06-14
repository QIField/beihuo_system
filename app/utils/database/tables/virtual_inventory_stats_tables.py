"""
虚拟库存统计日志表
记录每天虚拟库存的统计数据
业务时间：当天00:00到23:59
"""
import pymysql
from app.utils.database_connection import get_db_connection


def init_virtual_inventory_stats_log_table():
    """初始化虚拟库存统计日志表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS virtual_inventory_stats_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                business_date DATE NOT NULL COMMENT '业务日期',
                business_time_range VARCHAR(100) COMMENT '业务时间范围',
                total_count INT DEFAULT 0 COMMENT '总记录数',
                upload_success_count INT DEFAULT 0 COMMENT '上传成功数',
                new_create_success_count INT DEFAULT 0 COMMENT '新建成功数',
                new_create_fail_count INT DEFAULT 0 COMMENT '新建失败数',
                upload_fail_count INT DEFAULT 0 COMMENT '上传失败数',
                no_record_count INT DEFAULT 0 COMMENT '没有档案数',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
                UNIQUE KEY uk_business_date_company (business_date, company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='虚拟库存统计日志表';
            """
            cursor.execute(create_table_sql)
        conn.commit()
        print("  ✓ 虚拟库存统计日志表")
    except Exception as e:
        print(f"  ✗ 虚拟库存统计日志表: {e}")
        raise
    finally:
        conn.close()
