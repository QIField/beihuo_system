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

INPUT_FILE = r"C:\Users\Administrator\Desktop\开思原厂品牌其他数据.xlsx"
OUTPUT_FILE = r"C:\Users\Administrator\Desktop\开思原厂品牌其他数据_结果_complete.xlsx"

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


def process_and_get_result(oe, brands_map, use_length_rule=True, original_oe="", stage=""):
    """
    返回: (result, description)
    """
    if not oe:
        return "", ""

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
            brand_str = ",".join(unique)
            # 根据阶段生成不同的说明
            if stage == "stage1":
                desc = f"原始OE直接匹配数据库: {brand_str}"
            elif stage == "stage2":
                desc = f"删除前后缀到第一个/最后一个数字后匹配数据库: {brand_str}"
            elif stage == "stage3":
                desc = f"删除末尾01-19后匹配数据库: {brand_str}"
            else:
                desc = f"数据库匹配: {brand_str}"
            return brand_str, desc

    if use_length_rule:
        # 优先检查开头是否是LR（不区分大小写）
        check_oe = original_oe if original_oe else oe
        if check_oe.upper().startswith("LR"):
            if stage == "stage2":
                return "路虎", "删除前后缀到第一个/最后一个数字后，LR开头: 路虎"
            else:
                return "路虎", "LR开头: 路虎"
        
        # 然后检查长度
        oe_str = str(oe).strip()
        length = len(oe_str)
        if length == 10:
            if stage == "stage2":
                return "奔驰", "删除前后缀到第一个/最后一个数字后，长度10位: 奔驰"
            else:
                return "奔驰", "长度10位: 奔驰"
        elif length == 11:
            if stage == "stage2":
                return "宝马", "删除前后缀到第一个/最后一个数字后，长度11位: 宝马"
            else:
                return "宝马", "长度11位: 宝马"

    return "", ""


def is_all_chinese(s):
    """检查字符串是否全是中文"""
    if not s:
        return False
    s = str(s).strip()
    for c in s:
        if not ('\u4e00' <= c <= '\u9fff'):
            return False
    return True


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


def main():
    print(f"读取文件: {INPUT_FILE}")
    wb = openpyxl.load_workbook(INPUT_FILE)
    ws = wb.active

    total_rows = ws.max_row
    print(f"总行数: {total_rows}")

    # 确定新增列的位置
    result_col = ws.max_column + 1
    desc_col = result_col + 1
    ws.cell(row=1, column=result_col, value="匹配结果")
    ws.cell(row=1, column=result_col).font = Font(bold=True)
    ws.cell(row=1, column=desc_col, value="处理说明")
    ws.cell(row=1, column=desc_col).font = Font(bold=True)

    # ================== 第一阶段：直接匹配原始OE ==================
    print("\n=== 第一阶段：直接匹配原始OE ===")

    rows_stage1 = []
    for row_idx in range(2, total_rows + 1):
        b_val = ws.cell(row=row_idx, column=2).value
        b_str = str(b_val).strip() if b_val else ""
        # 跳过全是中文的行
        if b_str and not is_all_chinese(b_str):
            rows_stage1.append((row_idx, b_str))
        elif b_str and is_all_chinese(b_str):
            # 记录全是中文的行
            ws.cell(row=row_idx, column=desc_col, value="全是中文: 跳过")

    print(f"第一阶段需要处理的行数: {len(rows_stage1)}")

    oe_list_stage1 = [b_str for _, b_str in rows_stage1 if b_str]
    oe_list_stage1_unique = list(dict.fromkeys(oe_list_stage1))
    print(f"第一阶段去重后OE数: {len(oe_list_stage1_unique)}")

    batch_size = 500
    brands_map_stage1 = {}
    for i in range(0, len(oe_list_stage1_unique), batch_size):
        batch = oe_list_stage1_unique[i:i + batch_size]
        batch_result = batch_query_vehicle_brands(batch)
        brands_map_stage1.update(batch_result)
        print(f"第一阶段数据库查询进度: {min(i + batch_size, len(oe_list_stage1_unique))}/{len(oe_list_stage1_unique)}")

    updated_count1 = 0
    for row_idx, original_b in rows_stage1:
        result, desc = process_and_get_result(original_b, brands_map_stage1, use_length_rule=True, original_oe=original_b, stage="stage1")
        if result:
            ws.cell(row=row_idx, column=result_col, value=result)
            ws.cell(row=row_idx, column=desc_col, value=desc)
            updated_count1 += 1

    print(f"第一阶段更新了 {updated_count1} 行")

    # ================== 第二阶段：步骤A处理 ==================
    print("\n=== 第二阶段：步骤A处理（原始B列长度>9位）===")

    rows_stage2 = []
    for row_idx in range(2, total_rows + 1):
        g_val = ws.cell(row=row_idx, column=result_col).value
        if not g_val or str(g_val).strip() == "":
            b_val = ws.cell(row=row_idx, column=2).value
            b_str = str(b_val).strip() if b_val else ""
            if b_str and len(b_str) > 9 and not is_all_chinese(b_str):
                rows_stage2.append((row_idx, b_str))

    print(f"第二阶段需要处理的行数: {len(rows_stage2)}")

    cleaned_a_map = {}
    oe_list_stage2 = []
    for row_idx, original_b in rows_stage2:
        cleaned_a = clean_step_a(original_b)
        cleaned_a_map[row_idx] = (original_b, cleaned_a)
        if cleaned_a:
            oe_list_stage2.append(cleaned_a)

    oe_list_stage2_unique = list(dict.fromkeys(oe_list_stage2))
    print(f"第二阶段去重后OE数: {len(oe_list_stage2_unique)}")

    brands_map_stage2 = {}
    for i in range(0, len(oe_list_stage2_unique), batch_size):
        batch = oe_list_stage2_unique[i:i + batch_size]
        batch_result = batch_query_vehicle_brands(batch)
        brands_map_stage2.update(batch_result)
        print(f"第二阶段数据库查询进度: {min(i + batch_size, len(oe_list_stage2_unique))}/{len(oe_list_stage2_unique)}")

    updated_count2 = 0
    for row_idx, (original_b, cleaned_a) in cleaned_a_map.items():
        if cleaned_a:
            result, desc = process_and_get_result(cleaned_a, brands_map_stage2, use_length_rule=True, original_oe=original_b, stage="stage2")
            if result:
                ws.cell(row=row_idx, column=result_col, value=result)
                ws.cell(row=row_idx, column=desc_col, value=desc)
                updated_count2 += 1

    print(f"第二阶段更新了 {updated_count2} 行")

    # ================== 第三阶段：步骤C处理 ==================
    print("\n=== 第三阶段：步骤C处理（原始B列长度>9位）===")

    rows_stage3 = []
    for row_idx in range(2, total_rows + 1):
        g_val = ws.cell(row=row_idx, column=result_col).value
        if not g_val or str(g_val).strip() == "":
            b_val = ws.cell(row=row_idx, column=2).value
            b_str = str(b_val).strip() if b_val else ""
            if b_str and len(b_str) > 9 and not is_all_chinese(b_str):
                rows_stage3.append((row_idx, b_str))

    print(f"第三阶段需要处理的行数: {len(rows_stage3)}")

    cleaned_c_map = {}
    oe_list_stage3 = []
    for row_idx, original_b in rows_stage3:
        cleaned_c = clean_step_c(original_b)
        cleaned_c_map[row_idx] = (original_b, cleaned_c)
        if cleaned_c:
            oe_list_stage3.append(cleaned_c)

    oe_list_stage3_unique = list(dict.fromkeys(oe_list_stage3))
    print(f"第三阶段去重后OE数: {len(oe_list_stage3_unique)}")

    brands_map_stage3 = {}
    for i in range(0, len(oe_list_stage3_unique), batch_size):
        batch = oe_list_stage3_unique[i:i + batch_size]
        batch_result = batch_query_vehicle_brands(batch)
        brands_map_stage3.update(batch_result)
        print(f"第三阶段数据库查询进度: {min(i + batch_size, len(oe_list_stage3_unique))}/{len(oe_list_stage3_unique)}")

    updated_count3 = 0
    for row_idx, (original_b, cleaned_c) in cleaned_c_map.items():
        if cleaned_c:
            result, desc = process_and_get_result(cleaned_c, brands_map_stage3, use_length_rule=False, original_oe=original_b, stage="stage3")
            if result:
                ws.cell(row=row_idx, column=result_col, value=result)
                ws.cell(row=row_idx, column=desc_col, value=desc)
                updated_count3 += 1

    print(f"第三阶段更新了 {updated_count3} 行")

    # ================== 保存文件 ==================
    wb.save(OUTPUT_FILE)
    print(f"\n=== 完成 ===")
    print(f"结果已保存到: {OUTPUT_FILE}")
    print(f"总共更新了 {updated_count1 + updated_count2 + updated_count3} 行")


if __name__ == "__main__":
    main()
