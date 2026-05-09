import os
import sys
import re
import pymysql
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.db_config import _create_config

DB_CONFIG = _create_config("online")


def get_db_connection():
    return pymysql.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        charset=DB_CONFIG['charset'],
        autocommit=DB_CONFIG['autocommit'],
        use_unicode=DB_CONFIG['use_unicode']
    )


def batch_query_vehicle_brands(oe_list):
    if not oe_list:
        return {}

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(oe_list))
            sql = f"""
                SELECT oe, vehicle_brand
                FROM crmapp_compare_summary
                WHERE oe IN ({placeholders})
            """
            cursor.execute(sql, tuple(oe_list))
            rows = cursor.fetchall()

            result = {}
            for oe, vehicle_brand in rows:
                if oe not in result:
                    result[oe] = []
                if vehicle_brand:
                    result[oe].append(vehicle_brand)
            return result
    finally:
        conn.close()


def clean_step_a(oe_str):
    """删除开头和结尾的中文/字母/符号，保留从第一个数字到最后一个数字的内容"""
    if not oe_str:
        return ""

    oe_str = str(oe_str).strip()

    # 从开头找第一个数字的位置
    start = 0
    while start < len(oe_str):
        if oe_str[start].isdigit():
            break
        start += 1

    # 从结尾找最后一个数字的位置
    end = len(oe_str)
    while end > start:
        if oe_str[end - 1].isdigit():
            break
        end -= 1

    return oe_str[start:end].strip()


def clean_step_c(oe_str):
    """删除末尾两位数，前提是这两位数是01-19之间"""
    if not oe_str:
        return ""

    oe_str = str(oe_str).strip()

    if len(oe_str) < 2:
        return oe_str

    last_two = oe_str[-2:]
    if not last_two.isdigit():
        return oe_str

    num = int(last_two)
    if 1 <= num <= 19:
        return oe_str[:-2]

    return oe_str


test_cases = [
    (43, "GJ000001"),
    (44, "G11"),
    (48, "G15"),
    (53, "L06J260849G/F"),
    (81, "L5QD199262B/ESQ"),
    (83, "L8KD407152B/G"),
    (102, "06J998907BDA"),
    (120, "WHT007212BN910"),
    (167, "06H103483D/F"),
    (172, "06J109021B/G"),
]

print("=== 清理过程分析 ===")
all_cleaned_a = []
for row, oe in test_cases:
    cleaned_a = clean_step_a(oe)
    cleaned_c = clean_step_c(oe)
    print(f"行{row}:")
    print(f"  原始: {oe}")
    print(f"  步骤A清理后: {cleaned_a} (长度: {len(cleaned_a)})")
    print(f"  步骤C清理后: {cleaned_c} (长度: {len(cleaned_c)})")
    if cleaned_a:
        all_cleaned_a.append(cleaned_a)
    print()

print("\n=== 查询数据库 ===")
brands_map = batch_query_vehicle_brands(all_cleaned_a)
for oe in all_cleaned_a:
    if oe in brands_map:
        print(f"OE: {oe}")
        print(f"  匹配到: {brands_map[oe]}")
        filtered = [b for b in brands_map[oe] if b != "其他"]
        print(f"  去重去'其他'后: {list(dict.fromkeys(filtered))}")
    else:
        print(f"OE: {oe} - 未匹配到")
