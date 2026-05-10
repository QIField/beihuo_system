import os
import sys
import re
import pymysql
from pathlib import Path
import openpyxl
from openpyxl.styles import Font

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.db_config import _create_config

INPUT_FILE = r"C:\Users\Administrator\Desktop\开思原厂品牌其他数据_结果.xlsx"
OUTPUT_FILE = r"C:\Users\Administrator\Desktop\开思原厂品牌其他数据_结果_v2.xlsx"

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


def process_and_get_result(oe, brands_map, use_length_rule=True):
    if not oe:
        return ""

    brands = brands_map.get(oe, [])

    if brands:
        filtered = [b for b in brands if b != "其他"]
        if filtered:
            seen = set()
            unique = []
            for b in filtered:
                if b not in seen:
                    seen.add(b)
                    unique.append(b)
            return ",".join(unique)

    if use_length_rule:
        oe_str = str(oe).strip()
        length = len(oe_str)
        if length == 10:
            return "奔驰"
        elif length == 11:
            return "宝马"

    return ""


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

    # 检查末尾两位是否是数字
    last_two = oe_str[-2:]
    if not last_two.isdigit():
        return oe_str

    num = int(last_two)
    if 1 <= num <= 19:
        return oe_str[:-2]

    return oe_str


def main():
    print(f"读取文件: {INPUT_FILE}")
    wb = openpyxl.load_workbook(INPUT_FILE)
    ws = wb.active

    total_rows = ws.max_row
    print(f"总行数: {total_rows}")

    # ================== 第一轮处理（步骤A） ==================
    print("\n=== 第一轮处理（步骤A） ===")

    # 1. 找出G列为空且原始B列长度>9的行，收集B列原始数据
    rows_step1 = []
    for row_idx in range(2, total_rows + 1):
        g_val = ws.cell(row=row_idx, column=7).value
        if not g_val or str(g_val).strip() == "":
            b_val = ws.cell(row=row_idx, column=2).value
            b_str = str(b_val).strip() if b_val else ""
            # 只处理原始B列长度>9的
            if len(b_str) > 9:
                rows_step1.append((row_idx, b_str))

    print(f"需要处理的空结果行数（原始B列长度>9）: {len(rows_step1)}")

    # 2. 对B列数据进行步骤A清理
    cleaned_a_map = {}
    oe_list_a = []
    for row_idx, original_b in rows_step1:
        cleaned_a = clean_step_a(original_b)
        cleaned_a_map[row_idx] = (original_b, cleaned_a)
        if cleaned_a:
            oe_list_a.append(cleaned_a)

    oe_list_a_unique = list(dict.fromkeys(oe_list_a))
    print(f"步骤A去重后OE数: {len(oe_list_a_unique)}")

    # 3. 批量查询数据库
    batch_size = 500
    brands_map_a = {}
    for i in range(0, len(oe_list_a_unique), batch_size):
        batch = oe_list_a_unique[i:i + batch_size]
        batch_result = batch_query_vehicle_brands(batch)
        brands_map_a.update(batch_result)
        print(f"步骤A数据库查询进度: {min(i + batch_size, len(oe_list_a_unique))}/{len(oe_list_a_unique)}")

    # 4. 写入第一轮结果
    updated_count1 = 0
    for row_idx, (original_b, cleaned_a) in cleaned_a_map.items():
        if cleaned_a:
            result = process_and_get_result(cleaned_a, brands_map_a, use_length_rule=True)
            if result:
                ws.cell(row=row_idx, column=7, value=result)
                updated_count1 += 1

    print(f"第一轮处理后更新了 {updated_count1} 行")

    # ================== 第二轮处理（步骤C） ==================
    print("\n=== 第二轮处理（步骤C） ===")

    # 1. 找出经过第一轮后G列还为空的行
    rows_step2 = []
    for row_idx, original_b in [(r[0], r[1][0]) for r in cleaned_a_map.items()]:
        g_val = ws.cell(row=row_idx, column=7).value
        if not g_val or str(g_val).strip() == "":
            rows_step2.append((row_idx, original_b))

    print(f"仍需要处理的空结果行数: {len(rows_step2)}")

    # 2. 对B列原始数据进行步骤C清理
    cleaned_c_map = {}
    oe_list_c = []
    for row_idx, original_b in rows_step2:
        cleaned_c = clean_step_c(original_b)
        cleaned_c_map[row_idx] = (original_b, cleaned_c)
        if cleaned_c:
            oe_list_c.append(cleaned_c)

    oe_list_c_unique = list(dict.fromkeys(oe_list_c))
    print(f"步骤C去重后OE数: {len(oe_list_c_unique)}")

    # 3. 批量查询数据库
    brands_map_c = {}
    for i in range(0, len(oe_list_c_unique), batch_size):
        batch = oe_list_c_unique[i:i + batch_size]
        batch_result = batch_query_vehicle_brands(batch)
        brands_map_c.update(batch_result)
        print(f"步骤C数据库查询进度: {min(i + batch_size, len(oe_list_c_unique))}/{len(oe_list_c_unique)}")

    # 4. 写入第二轮结果
    updated_count2 = 0
    for row_idx, (original_b, cleaned_c) in cleaned_c_map.items():
        if cleaned_c:
            result = process_and_get_result(cleaned_c, brands_map_c, use_length_rule=False)
            if result:
                ws.cell(row=row_idx, column=7, value=result)
                updated_count2 += 1

    print(f"第二轮处理后更新了 {updated_count2} 行")

    # ================== 保存文件 ==================
    wb.save(OUTPUT_FILE)
    print(f"\n=== 完成 ===")
    print(f"结果已保存到: {OUTPUT_FILE}")
    print(f"总共更新了 {updated_count1 + updated_count2} 行")


if __name__ == "__main__":
    main()
