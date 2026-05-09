import os
import sys
import pymysql
from pathlib import Path
import openpyxl
from openpyxl.styles import Font

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.db_config import _create_config

EXCEL_PATH = r"C:\Users\Administrator\Desktop\开思原厂品牌其他数据.xlsx"
OUTPUT_PATH = r"C:\Users\Administrator\Desktop\开思原厂品牌其他数据_结果.xlsx"

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


def process_oe(oe: str, brands_map: dict):
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

    oe_str = str(oe).strip()
    length = len(oe_str)
    if length == 10:
        return "奔驰"
    elif length == 11:
        return "宝马"
    else:
        return ""


def main():
    print(f"读取Excel: {EXCEL_PATH}")
    if not os.path.exists(EXCEL_PATH):
        print(f"文件不存在: {EXCEL_PATH}")
        return

    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb.active

    total_rows = ws.max_row
    print(f"总行数: {total_rows}")

    oe_list = []
    row_map = {}
    for row_idx in range(2, total_rows + 1):
        oe_value = ws.cell(row=row_idx, column=2).value
        oe_str = str(oe_value).strip() if oe_value else ""
        if oe_str:
            oe_list.append(oe_str)
            row_map[row_idx] = oe_str

    unique_oe_list = list(dict.fromkeys(oe_list))
    print(f"需要去重的OE数量: {len(unique_oe_list)}")

    batch_size = 500
    all_brands_map = {}
    for i in range(0, len(unique_oe_list), batch_size):
        batch = unique_oe_list[i:i + batch_size]
        batch_result = batch_query_vehicle_brands(batch)
        all_brands_map.update(batch_result)
        print(f"数据库查询进度: {min(i + batch_size, len(unique_oe_list))}/{len(unique_oe_list)}")

    result_col = ws.max_column + 1
    ws.cell(row=1, column=result_col, value="匹配结果")
    ws.cell(row=1, column=result_col).font = Font(bold=True)

    for row_idx in range(2, total_rows + 1):
        oe_str = row_map.get(row_idx, "")
        if oe_str:
            result = process_oe(oe_str, all_brands_map)
        else:
            result = ""

        ws.cell(row=row_idx, column=result_col, value=result)

        if (row_idx - 1) % 500 == 0 or row_idx == total_rows:
            print(f"写入进度: {row_idx - 1}/{total_rows - 1} | 当前OE: {oe_str} -> {result}")

    wb.save(OUTPUT_PATH)
    print(f"\n完成！结果已保存到: {OUTPUT_PATH}")
    print(f"新增列位置: 第{result_col}列")


if __name__ == "__main__":
    main()
