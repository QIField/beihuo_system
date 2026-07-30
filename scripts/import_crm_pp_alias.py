# -*- coding:utf-8 -*-
"""
导入 CRM 零件品牌别名到数据库

数据来源：static/excel/crm可用别名.xlsx
表结构：单表扁平设计 crm_pp_name
    - pp_name：品牌主名
    - alias_name：别名
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

import pandas as pd
import pymysql

from app.utils.database_connection import get_db_connection


EXCEL_PATH = Path(__file__).resolve().parent.parent / "static" / "excel" / "crm可用别名.xlsx"

TABLE_NAME = "crm_pp_name"


def parse_aliases(df: pd.DataFrame):
    """
    解析 Excel，按主名拆分别名并去重

    :return: list[tuple[main_name, alias_name]]
    """
    pairs = []
    seen = set()

    for _, row in df.iterrows():
        main_name = str(row.get("pp_name", "")).strip()
        if not main_name:
            continue

        raw_aliases = str(row.get("pp_names", "")).split(",")
        for raw in raw_aliases:
            alias = raw.strip()
            if not alias:
                continue

            key = (main_name, alias)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(key)

    return pairs


def create_table():
    """自动创建 crm_pp_name 表"""
    sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
        pp_name VARCHAR(255) NOT NULL COMMENT '品牌主名',
        alias_name VARCHAR(255) NOT NULL COMMENT '别名',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        UNIQUE KEY uk_pp_alias (pp_name, alias_name),
        KEY idx_alias_name (alias_name),
        KEY idx_pp_name (pp_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='CRM零件品牌别名映射表';
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
        print(f"[成功] 数据表 {TABLE_NAME} 已创建或已存在")
    finally:
        conn.close()


def import_to_database(pairs):
    """
    将解析后的别名写入 crm_pp_name 表

    利用唯一索引跳过重复数据，可重复执行
    """
    if not pairs:
        print("[提示] 没有可导入的数据")
        return

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            inserted = 0
            for main_name, alias in pairs:
                cursor.execute(
                    f"INSERT IGNORE INTO {TABLE_NAME} (pp_name, alias_name) VALUES (%s, %s)",
                    (main_name, alias),
                )
                if cursor.rowcount > 0:
                    inserted += 1

        conn.commit()
        print(f"[成功] 新增 {inserted} 条记录")
        print(f"[统计] 本次共处理 {len(pairs)} 个（主名, 别名）组合")

    except Exception as e:
        conn.rollback()
        print(f"[失败] 导入出错: {e}")
        raise
    finally:
        conn.close()


def main():
    print(f"[开始] 读取 Excel: {EXCEL_PATH}")
    df = pd.read_excel(EXCEL_PATH)
    print(f"[读取] Excel 共 {len(df)} 行，列: {df.columns.tolist()}")

    pairs = parse_aliases(df)
    print(f"[解析] 去重后共 {len(pairs)} 个（主名, 别名）组合")

    create_table()
    import_to_database(pairs)
    print("[完成]")


if __name__ == "__main__":
    main()
