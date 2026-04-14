"""
虚拟库存统计日志历史数据初始化脚本
一次性运行，将历史数据按天汇总导入到统计日志表
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import pymysql
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection


def get_business_date_range_for_date(target_date):
    """
    获取指定日期的业务时间范围
    业务时间：当天00:00到23:59
    """
    # 当天00:00
    start_time = datetime.combine(target_date, datetime.min.time())
    # 当天23:59:59
    end_time = datetime.combine(target_date, datetime.max.time().replace(microsecond=0))
    return start_time, end_time


def init_stats_log_table():
    """确保表存在"""
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
                UNIQUE KEY uk_business_date (business_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='虚拟库存统计日志表';
            """
            cursor.execute(create_table_sql)
        conn.commit()
        print("✓ 统计日志表已就绪")
    finally:
        conn.close()


def get_all_business_dates():
    """获取虚拟库存表中所有业务日期"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 查询所有不重复的日期（按fetch_time的日期部分）
        cursor.execute("""
            SELECT DISTINCT DATE(fetch_time) as business_date
            FROM virtual_inventory
            WHERE fetch_time IS NOT NULL
            ORDER BY business_date ASC
        """)
        rows = cursor.fetchall()
        return [row['business_date'] for row in rows]
    finally:
        cursor.close()
        conn.close()


def calculate_stats_for_date(business_date):
    """计算指定日期的统计数据"""
    start_time, end_time = get_business_date_range_for_date(business_date)

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 总记录数
        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        total_count = cursor.fetchone()['count']

        if total_count == 0:
            return None  # 该日期没有数据

        # 上传成功
        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status = '上传成功' AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        upload_success_count = cursor.fetchone()['count']

        # 新建成功
        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status IN ('新建成功-已存在', '新建成功-新创建')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        new_create_success_count = cursor.fetchone()['count']

        # 新建失败
        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status IN ('新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        new_create_fail_count = cursor.fetchone()['count']

        # 上传失败
        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status != '上传成功' AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        upload_fail_count = cursor.fetchone()['count']

        # 没有档案
        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status IN ('新建成功-已存在', '新建成功-新创建', '新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        no_record_count = cursor.fetchone()['count']

        return {
            'business_date': business_date,
            'business_time_range': f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            'total_count': total_count,
            'upload_success_count': upload_success_count,
            'new_create_success_count': new_create_success_count,
            'new_create_fail_count': new_create_fail_count,
            'upload_fail_count': upload_fail_count,
            'no_record_count': no_record_count,
        }

    finally:
        cursor.close()
        conn.close()


def save_stats_to_log(stats):
    """保存统计数据到日志表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        upsert_sql = """
            INSERT INTO virtual_inventory_stats_log
            (business_date, business_time_range, total_count, upload_success_count,
             new_create_success_count, new_create_fail_count, upload_fail_count, no_record_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            business_time_range = VALUES(business_time_range),
            total_count = VALUES(total_count),
            upload_success_count = VALUES(upload_success_count),
            new_create_success_count = VALUES(new_create_success_count),
            new_create_fail_count = VALUES(new_create_fail_count),
            upload_fail_count = VALUES(upload_fail_count),
            no_record_count = VALUES(no_record_count),
            created_at = CURRENT_TIMESTAMP
        """

        cursor.execute(upsert_sql, (
            stats['business_date'], stats['business_time_range'],
            stats['total_count'], stats['upload_success_count'],
            stats['new_create_success_count'], stats['new_create_fail_count'],
            stats['upload_fail_count'], stats['no_record_count']
        ))
        conn.commit()

    finally:
        cursor.close()
        conn.close()


def main():
    print("=" * 60)
    print("虚拟库存统计日志历史数据初始化")
    print("=" * 60)

    # 确保表存在
    init_stats_log_table()

    # 获取所有业务日期
    print("\n正在查询历史数据...")
    business_dates = get_all_business_dates()
    print(f"发现 {len(business_dates)} 个业务日期的数据")

    if not business_dates:
        print("没有找到历史数据，脚本结束")
        return

    # 逐个日期处理
    print("\n开始导入数据...")
    success_count = 0
    skip_count = 0

    for i, business_date in enumerate(business_dates, 1):
        print(f"\n[{i}/{len(business_dates)}] 处理日期: {business_date}")

        stats = calculate_stats_for_date(business_date)

        if stats is None:
            print(f"  - 该日期无数据，跳过")
            skip_count += 1
            continue

        print(f"  - 总记录: {stats['total_count']}")
        print(f"  - 上传成功: {stats['upload_success_count']}")
        print(f"  - 新建成功: {stats['new_create_success_count']}")
        print(f"  - 新建失败: {stats['new_create_fail_count']}")
        print(f"  - 上传失败: {stats['upload_fail_count']}")
        print(f"  - 没有档案: {stats['no_record_count']}")

        save_stats_to_log(stats)
        print(f"  ✓ 已保存")
        success_count += 1

    print("\n" + "=" * 60)
    print("初始化完成")
    print(f"成功导入: {success_count} 天")
    print(f"跳过: {skip_count} 天")
    print("=" * 60)


if __name__ == '__main__':
    main()
