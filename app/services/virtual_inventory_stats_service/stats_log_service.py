"""
虚拟库存统计日志服务层
处理统计日志的业务逻辑
"""
import pymysql
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection


COMPANY_TABLES = [
    ('fsbbr', 'virtual_inventory'),
    ('zhbbr', 'virtual_inventory_zhbbr'),
    ('zsbbr', 'virtual_inventory_zsbbr'),
    ('dgby', 'virtual_inventory_dgby'),
    ('dghf', 'virtual_inventory_dghf'),
]


def save_recent_statistics(days=1):
    """保存最近指定天数的统计数据，按 business_date 和 company 覆盖更新"""
    results = []
    current_time = datetime.now()

    for offset in range(days):
        business_start = (current_time - timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        business_end = business_start.replace(hour=23, minute=59, second=59, microsecond=0)
        results.extend(save_daily_statistics(business_start, business_end))

    return results


def save_daily_statistics(start_time, end_time):
    """
    保存当日五个门店统计数据到日志表

    参数:
        start_time: 业务日开始时间
        end_time: 业务日结束时间

    返回:
        list: 每个门店的保存结果
    """
    results = []

    for company, table_name in COMPANY_TABLES:
        results.append(save_company_daily_statistics(company, table_name, start_time, end_time))

    return results


def save_company_daily_statistics(company, table_name, start_time, end_time):
    """保存单个门店当日统计数据"""
    business_date = start_time.date()

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute(f"""
            SELECT COUNT(*) as count FROM {table_name}
            WHERE fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        total_count = cursor.fetchone()['count']

        cursor.execute(f"""
            SELECT COUNT(*) as count FROM {table_name}
            WHERE update_status = '上传成功' AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        upload_success_count = cursor.fetchone()['count']

        cursor.execute(f"""
            SELECT COUNT(*) as count FROM {table_name}
            WHERE update_status IN ('新建成功-已存在', '新建成功-新创建')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        new_create_success_count = cursor.fetchone()['count']

        cursor.execute(f"""
            SELECT COUNT(*) as count FROM {table_name}
            WHERE update_status IN ('新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        new_create_fail_count = cursor.fetchone()['count']

        cursor.execute(f"""
            SELECT COUNT(*) as count FROM {table_name}
            WHERE update_status != '上传成功' AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        upload_fail_count = cursor.fetchone()['count']

        cursor.execute(f"""
            SELECT COUNT(*) as count FROM {table_name}
            WHERE update_status IN ('新建成功-已存在', '新建成功-新创建', '新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')
            AND fetch_time >= %s AND fetch_time < %s
        """, (start_time, end_time))
        no_record_count = cursor.fetchone()['count']

        upsert_sql = """
            INSERT INTO virtual_inventory_stats_log
            (business_date, company, business_time_range, total_count, upload_success_count,
             new_create_success_count, new_create_fail_count, upload_fail_count, no_record_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            business_date, company, business_time_range, total_count, upload_success_count,
            new_create_success_count, new_create_fail_count, upload_fail_count, no_record_count
        ))
        conn.commit()

        print(f"[统计日志] 已保存 {business_date} {company} 数据: 总计 {total_count} 条")

        return {
            'code': 0,
            'msg': '统计数据保存成功',
            'data': {
                'business_date': str(business_date),
                'company': company,
                'total_count': total_count,
                'upload_success_count': upload_success_count,
                'new_create_success_count': new_create_success_count,
                'new_create_fail_count': new_create_fail_count,
                'upload_fail_count': upload_fail_count,
                'no_record_count': no_record_count,
            }
        }

    except Exception as e:
        print(f"[统计日志] 保存失败: {company} {e}")
        conn.rollback()
        return {'code': 1, 'msg': f'{company} 保存失败: {str(e)}'}
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
            SELECT business_date, company, business_time_range, total_count,
                   upload_success_count, new_create_success_count,
                   new_create_fail_count, upload_fail_count, no_record_count,
                   created_at
            FROM virtual_inventory_stats_log
            WHERE business_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY business_date DESC, company ASC
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
