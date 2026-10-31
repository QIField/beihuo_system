# -*- coding:utf-8 -*-
# @Time    : 2026/10/29
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : db_service.py
# @Desc    : OE替换号差异扫描结果表 oe_replace_diff_scan 的建表与读写
#
#            唯一键 (company, oe) 保证每个 oe 只记录一次：
#            无论是替换号一致还是有差异都写入，第二天任务自动跳过已扫描的 oe。
#            assigned_date / task_id 记录差异 oe 的每日发放（100条/天），发过的永不重复。

import pymysql

from app.utils.database_connection import get_db_connection

TABLE_NAME = 'oe_replace_diff_scan'


def ensure_table():
    """建表（不存在时）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                    oe VARCHAR(255) NOT NULL COMMENT '被扫描的OE号',
                    company VARCHAR(100) NOT NULL DEFAULT 'fsbbr' COMMENT '公司代码',
                    matched_count INT DEFAULT 0 COMMENT '匹配到的行数',
                    status VARCHAR(20) NOT NULL COMMENT '有差异/一致/单行/未匹配',
                    scanned_time DATETIME COMMENT '扫描时间',
                    assigned_date DATE NULL COMMENT '发放日期(NULL=未发放)',
                    task_id BIGINT NULL COMMENT '发放的业务任务ID',
                    UNIQUE KEY uk_company_oe (company, oe)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='OE替换号差异扫描结果表'
            """)
        conn.commit()
    finally:
        conn.close()


def fetch_unscanned_oes(company: str) -> list:
    """取尚未扫描过的 oe（LEFT JOIN 扫描表，避免重复计算）"""
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                f"""
                SELECT DISTINCT c.oe
                FROM crmapp_compare_summary c
                LEFT JOIN {TABLE_NAME} s
                       ON s.company = c.company AND s.oe = c.oe
                WHERE c.company = %s AND c.oe <> '' AND s.id IS NULL
                """,
                (company,),
            )
            return [row['oe'] for row in cursor.fetchall()]
    finally:
        conn.close()


def fetch_unassigned_diff_oes(company: str, limit: int = 100) -> list:
    """按入库先后取未发放的差异 oe（每天限量发放，发过的永不重复）"""
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                f"SELECT oe FROM {TABLE_NAME} "
                f"WHERE company = %s AND status = '有差异' AND assigned_date IS NULL "
                f"ORDER BY id LIMIT %s",
                (company, limit),
            )
            return [row['oe'] for row in cursor.fetchall()]
    finally:
        conn.close()


def fetch_pool_stats(company: str) -> dict:
    """差异池统计：总量 / 未发放量，供任务日志输出"""
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS total, "
                f"SUM(assigned_date IS NULL) AS unassigned "
                f"FROM {TABLE_NAME} WHERE company = %s AND status = '有差异'",
                (company,),
            )
            row = cursor.fetchone()
            return {
                'total_diff': row['total'] or 0,
                'unassigned': row['unassigned'] or 0,
            }
    finally:
        conn.close()


def mark_batch_assigned(company: str, oes: list, task_id, assigned_date):
    """标记本批差异 oe 已发放（发放日期 + 业务任务ID）"""
    if not oes:
        return
    placeholders = ', '.join(['%s'] * len(oes))
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"UPDATE {TABLE_NAME} SET assigned_date = %s, task_id = %s "
                f"WHERE company = %s AND oe IN ({placeholders})",
                [assigned_date, task_id, company] + list(oes),
            )
        conn.commit()
    finally:
        conn.close()


def upsert_scan_results(company: str, results: list, batch_size: int = 500):
    """
    批量写入扫描结果（存在则更新），分批提交，异常只影响当前批，重跑自动补缺口

    results: [{'oe','matched_count','status','scanned_time'}, ...]
    """
    sql = f"""
        INSERT INTO {TABLE_NAME}
            (oe, company, matched_count, status, scanned_time)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            matched_count = VALUES(matched_count),
            status = VALUES(status),
            scanned_time = VALUES(scanned_time)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for i in range(0, len(results), batch_size):
                batch = results[i:i + batch_size]
                data = [
                    (r['oe'], company, r['matched_count'], r['status'], r['scanned_time'])
                    for r in batch
                ]
                cursor.executemany(sql, data)
                conn.commit()
    finally:
        conn.close()
