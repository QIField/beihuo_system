# -*- coding:utf-8 -*-
# @Time    : 2026/10/12 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : amap_customer_import_service.py
# @Software: PyCharm
# 高德导出Excel导入服务：一个Excel两个sheet，数据处理分开
#   - "标记位置"sheet → 客户档案（解析见 amap_customer_excel_parser.py，入库见 visit_amap_customer_dao.py）
#   - "记录"sheet → 拜访记录（解析见 visit_record_excel_parser.py，入库见 visit_record_dao.py）
# 两个 sheet 各自独立事务、独立统计，互不影响。

import os
from datetime import datetime

import pandas as pd

from app.dao.visit_dao import visit_amap_customer_dao, visit_record_dao
from app.models.orm_models.visit import gen_manual_poi_id
from app.services.visit_service import amap_customer_excel_parser as marker_parser
from app.services.visit_service import visit_record_excel_parser as record_parser
from app.utils.orm import orm_session

# sheet 名常量（引用各 parser 常量，避免魔法字符串散落）
SHEET_MARKER = marker_parser.AMAP_MARKER_SHEET    # "标记位置"
SHEET_RECORD = record_parser.VISIT_RECORD_SHEET   # "记录"

SOURCE_EXCEL = 2  # 1-高德小程序同步 2-后台补录（Excel导入）


def _load_book(file_obj, filename):
    """格式校验 + 读取Excel工作簿

    :return: (ExcelFile 或 None, 错误信息 或 None)
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        return None, f"文件格式不支持: {ext}，请使用高德导出的 .xlsx 文件"
    try:
        engine = "openpyxl" if ext == ".xlsx" else "xlrd"
        return pd.ExcelFile(file_obj, engine=engine), None
    except Exception as e:
        return None, f"Excel文件读取失败: {e}"


def _parse_sheet(book, sheet, parser):
    """读取指定sheet并构建清洗后的行数据（sheet 缺失或表头缺列抛 ValueError）"""
    if sheet not in book.sheet_names:
        raise ValueError(f'文件中未找到"{sheet}"sheet，实际sheet: {book.sheet_names}')
    df = book.parse(sheet, dtype=str)
    return parser.build_rows(df)


# ------------------- "标记位置"sheet：客户档案 -------------------

def _resolve_no_code_poi_ids(session, rows):
    """
    位置编码为空的行：按"名称+地址"查重（设计文档 2.2 手工客户防重规则）
    - 命中已有客户 → 复用其 amap_poi_id（走更新，不重复插入）
    - 未命中 → 生成 MANUAL_ 伪编码（新增）

    :return: 本轮新生成伪编码的行数
    """
    generated = 0
    for r in rows:
        if r["amap_poi_id"]:
            continue
        existing_poi_id = visit_amap_customer_dao.find_poi_id_by_name_address(
            session, r["customer_name"], r["address"])
        if existing_poi_id:
            r["amap_poi_id"] = existing_poi_id
        else:
            r["amap_poi_id"] = gen_manual_poi_id()
            generated += 1
    return generated


def _import_marker_sheet(book):
    """
    导入"标记位置"sheet → 客户档案（幂等：位置编码已存在则更新档案字段）

    :param book: ExcelFile 工作簿
    :return: 客户档案导入结果统计 dict
    """
    visit_amap_customer_dao.ensure_table()

    rows, stats = _parse_sheet(book, SHEET_MARKER, marker_parser)

    insert_count = 0
    update_count = 0
    manual_generated = 0
    if rows:
        with orm_session() as session:
            manual_generated = _resolve_no_code_poi_ids(session, rows)
            poi_ids = [r["amap_poi_id"] for r in rows]
            existing_ids = visit_amap_customer_dao.get_existing_poi_ids(session, poi_ids)
            visit_amap_customer_dao.bulk_upsert(session, rows)
            insert_count = sum(1 for p in poi_ids if p not in existing_ids)
            update_count = len(poi_ids) - insert_count

    return {
        "total_rows": len(rows) + len(stats["error_rows"]) + stats["empty_rows"],
        "import_count": insert_count + update_count,
        "insert_count": insert_count,
        "update_count": update_count,
        "empty_rows": stats["empty_rows"],
        "error_rows": stats["error_rows"],
        "no_code_rows": stats["no_code_rows"],
        "manual_generated": manual_generated,
    }


# ------------------- "记录"sheet：拜访记录 -------------------
# 导入流程（设计文档 doc/客访管理/01-主设计文档.md 4.3）：
# 1. 客户档案 upsert：以「记录所属内容」写入 visit_amap_customer（仅更新名称，不覆盖其他档案字段）
# 2. 拜访记录 upsert：不预查、不区分新增/更新，直接交数据库按唯一键
#    uk_visit_dedup 自动插入/更新（status/source 不被覆盖，人工与渠道状态保留）
# 3. 回写客户最近拜访时间 last_visit_time（仅增大）
#    记录人为我方业务人员，Excel"记录人"原样存 recorder 展示，不映射、不参与去重

def _upsert_customers(session, rows):
    """
    以「记录所属内容」写入客户档案（upsert 幂等，无需检查编码是否存在）

    :return: 本次写入的客户数（按 POI 去重）
    """
    name_by_poi = {}
    for r in rows:
        name_by_poi.setdefault(r["amap_customer_id"], r["customer_name"])
    poi_rows = [{"amap_poi_id": poi, "customer_name": name or "未知客户"}
                for poi, name in name_by_poi.items()]
    # update_fields 仅名称：记录 sheet 的 customer_name 不覆盖档案的地址/坐标等采集字段
    visit_amap_customer_dao.bulk_upsert(
        session, poi_rows, update_fields=("customer_name",))
    return len(poi_rows)


def _import_record_sheet(book):
    """
    导入"记录"sheet → 拜访记录（upsert：位置+时间已存在则更新照片/记录人，不存在则插入）

    :param book: ExcelFile 工作簿
    :return: 拜访记录导入结果统计 dict
    """
    visit_amap_customer_dao.ensure_table()  # 第 1 步客户建档需要
    visit_record_dao.ensure_table()

    rows, stats = _parse_sheet(book, SHEET_RECORD, record_parser)

    import_count = 0
    customer_count = 0

    if rows:
        now = datetime.now()
        with orm_session() as session:
            # 1. 客户档案 upsert（无需检查编码是否存在）
            customer_count = _upsert_customers(session, rows)

            # 2. 拜访记录 upsert：不预查、不区分新增/更新，由数据库按唯一键
            #    uk_visit_dedup 自动判定（不存在插入 / 已存在更新），同键多行取最后一行
            row_by_key = {(r["amap_customer_id"], r["visit_time"]): r for r in rows}
            visit_record_dao.bulk_upsert(session, [{
                "amap_customer_id": r["amap_customer_id"],
                "recorder": r["recorder"],
                "visit_time": r["visit_time"],
                "content": r["content"],
                "images": r["images"],
                "source": SOURCE_EXCEL,
                "status": 1,
                "created_at": now,
                "updated_at": now,
            } for r in row_by_key.values()])
            import_count = len(row_by_key)

            # 3. 回写客户最近拜访时间（仅增大，旧数据不回拨）
            poi_max_times = {}
            for row in row_by_key.values():
                poi = row["amap_customer_id"]
                if poi not in poi_max_times or row["visit_time"] > poi_max_times[poi]:
                    poi_max_times[poi] = row["visit_time"]
            visit_amap_customer_dao.bump_last_visit_times(session, poi_max_times)

    return {
        "total_rows": len(rows) + len(stats["error_rows"]) + stats["empty_rows"],
        "import_count": import_count,
        "error_rows": stats["error_rows"],
        "empty_rows": stats["empty_rows"],
        "customer_count": customer_count,
    }


# ------------------- 统一入口 -------------------

def import_amap_excel(file_obj, filename):
    """
    导入高德导出Excel（统一入口）："标记位置"sheet 客户档案 + "记录"sheet 拜访记录

    两个 sheet 各自独立事务、独立统计；任一 sheet 缺失或表头缺列则整体报错。

    :param file_obj: 上传的Excel文件对象
    :param filename: 文件名
    :return: {'sheet_names': [...], 'marker': {...}, 'record': {...}}
    """
    book, err = _load_book(file_obj, filename)
    if err:
        raise ValueError(err)

    marker_result = _import_marker_sheet(book)
    record_result = _import_record_sheet(book)

    return {
        "sheet_names": book.sheet_names,  # pyright: ignore[reportOptionalMemberAccess]
        "marker": marker_result,
        "record": record_result,
    }
