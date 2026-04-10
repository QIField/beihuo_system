"""
虚拟库存统计日志服务层
处理统计日志的业务逻辑
"""
import pymysql
from app.utils.database_connection import get_db_connection


def save_daily_statistics(start_time, end_time):
    """
    保存当日统计数据到日志表

    参数:
        start_time: 业务日开始时间
        end_time: 业务日结束时间

    返回:
        dict: 包含code、msg、data的字典
    """
    business_date = start_time.date()

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 获取当日统计数据
        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        total_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status = '上传成功' AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        upload_success_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status IN ('新建成功-已存在', '新建成功-新创建')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        new_create_success_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status IN ('新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        new_create_fail_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status != '上传成功' AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        upload_fail_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status IN ('新建成功-已存在', '新建成功-新创建', '新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        no_record_count = cursor.fetchone()['count']

        # 插入或更新
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

        business_time_range = f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}"

        cursor.execute(upsert_sql, (
            business_date, business_time_range, total_count, upload_success_count,
            new_create_success_count, new_create_fail_count, upload_fail_count, no_record_count
        ))
        conn.commit()

        print(f"[统计日志] 已保存 {business_date} 数据: 总计 {total_count} 条")

        return {
            'code': 0,
            'msg': '统计数据保存成功',
            'data': {'business_date': str(business_date), 'total_count': total_count}
        }

    except Exception as e:
        print(f"[统计日志] 保存失败: {e}")
        conn.rollback()
        return {'code': 1, 'msg': f'保存失败: {str(e)}'}
    finally:
        cursor.close()
        conn.close()


def get_stats_log_list(days=30):
    """
    获取统计日志列表

    参数:
        days: 查询最近多少天的数据，默认30天

    返回:
        list: 统计日志列表
    """
    days = min(days, 365)  # 最多查询一年

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT business_date, business_time_range, total_count,
                   upload_success_count, new_create_success_count,
                   new_create_fail_count, upload_fail_count, no_record_count,
                   created_at
            FROM virtual_inventory_stats_log
            WHERE business_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY business_date DESC
        """, (days,))

        rows = cursor.fetchall()

        # 格式化日期
        for row in rows:
            row['business_date'] = str(row['business_date'])
            if row['created_at']:
                row['created_at'] = row['created_at'].strftime('%Y-%m-%d %H:%M:%S')

        return rows

    finally:
        cursor.close()
        conn.close()
