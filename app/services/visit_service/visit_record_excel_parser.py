# -*- coding:utf-8 -*-
# @Time    : 2026/10/13 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_record_excel_parser.py
# @Software: PyCharm
# 拜访记录Excel解析（高德导出Excel的"记录"sheet，与客户档案"标记位置"sheet同属一个文件）：
# 负责数据处理与数据清洗（表头映射、单元格清洗、时间解析、文字/照片清洗、行构建）
# 不含任何数据库操作；sheet 读取见 amap_customer_import_service.py，入库见 visit_record_dao.py

from datetime import datetime

import pandas as pd

# 拜访记录数据所在sheet（与客户档案"标记位置"sheet 同属一个导出文件）
VISIT_RECORD_SHEET = "记录"

# Excel列名 → 表字段（精确匹配；表头去除前导*号后匹配）
EXACT_COLUMN_MAPPING = {
    "记录所属内容": "customer_name",   # 导入时用于 visit_amap_customer 建档/展示，不落 visit_record
    "记录人": "recorder",              # 我方业务人员文案，原样存 recorder 展示，不映射系统账号
    "记录文字": "content",
    "记录时间": "visit_time",
}

# 前缀匹配列（列名可带括号说明，如"记录照片[照片间以逗号分隔，复制链接至浏览器下载/查看]"）
PREFIX_COLUMN_MAPPING = {
    "记录照片": "photos",
    "记录内容位置编码": "amap_customer_id",
}

# 复合唯一键必需列（表字段名），缺任一列则该文件不可导入
REQUIRED_FIELDS = ("amap_customer_id", "recorder", "visit_time")

TIME_FORMATS = (
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%Y年%m月%d日 %H:%M", "%Y年%m月%d日",
)


def _clean(value):
    """单元格清洗：NaN/空串 → None"""
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    return s


def _parse_datetime(value):
    """
    记录时间解析：兼容 openpyxl 已解析的 datetime 与字符串文案

    :return: datetime 或 None（调用方对 None 按异常行处理）
    """
    if isinstance(value, datetime):
        return value.replace(microsecond=0)  # 秒级精度，与复合唯一键口径一致
    s = _clean(value)
    if s is None:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).to_pydatetime().replace(microsecond=0)
    except Exception:
        return None


def _parse_photos(value):
    """
    照片列清洗：Excel 原样字符串直接入库（不做 JSON 结构化）

    :return: 照片字符串 或 None（无照片）
    """
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def match_columns(columns):
    """
    将Excel表头映射到表字段

    匹配规则（互斥，按序生效）：
    1. 精确匹配 EXACT_COLUMN_MAPPING
    2. 前缀匹配 PREFIX_COLUMN_MAPPING（照片/位置编码列名带括号说明）

    :param columns: 表头列表
    :return: {Excel列名: 表字段名}
    """
    mapping = {}
    for col in columns:
        col_norm = str(col).strip().lstrip("*＊").strip()
        if not col_norm:
            continue
        if col_norm in EXACT_COLUMN_MAPPING:
            mapping[col] = EXACT_COLUMN_MAPPING[col_norm]
            continue
        for prefix, field in PREFIX_COLUMN_MAPPING.items():
            if col_norm.startswith(prefix):
                mapping[col] = field
                break
    return mapping


def _missing_required(mapping):
    """必需字段缺失的中文列名列表（用于报错提示）"""
    label_by_field = {f: c for c, f in
                      list(EXACT_COLUMN_MAPPING.items()) + list(PREFIX_COLUMN_MAPPING.items())}
    return [label_by_field[f] for f in REQUIRED_FIELDS
            if f not in mapping.values()]


def build_rows(df):
    """
    DataFrame → 行字典列表（数据清洗）

    跳过规则：
    - 整行全空 → 计入 empty_rows
    - 位置编码/记录人为空、记录时间无法解析 → 计入 error_rows
      （三者均为复合唯一键成员或非空约束，缺一不可入库）

    行内 _excel_row 为 Excel 实际行号（表头占第1行），用于错误/冲突定位，
    入库前由导入服务剔除。

    :return: (rows, stats) stats 含 empty_rows/error_rows
    """
    col_mapping = match_columns(list(df.columns))
    missing = _missing_required(col_mapping)
    if missing:
        raise ValueError(f"Excel表头缺少必需列: {', '.join(missing)}")

    rows = []
    empty_rows = 0
    error_rows = []

    for idx, row in df.iterrows():
        excel_row = idx + 2  # 表头占第1行，DataFrame索引从0起
        values = {field: _clean(row.get(col)) for col, field in col_mapping.items()}

        if all(v is None for v in values.values()):
            empty_rows += 1
            continue

        poi_id = values.get("amap_customer_id")
        recorder = values.get("recorder")
        visit_time = _parse_datetime(values.get("visit_time"))

        if not poi_id:
            error_rows.append({"row": excel_row, "reason": "记录内容位置编码为空"})
            continue
        if not recorder:
            error_rows.append({"row": excel_row, "reason": "记录人为空"})
            continue
        if visit_time is None:
            error_rows.append({"row": excel_row, "reason": "记录时间为空或格式无法解析"})
            continue

        rows.append({
            "_excel_row": excel_row,
            "amap_customer_id": poi_id,
            "customer_name": values.get("customer_name"),  # 记录所属内容，客户建档用
            "recorder": recorder,
            "visit_time": visit_time,
            "content": values.get("content"),
            "images": _parse_photos(values.get("photos")),
        })

    stats = {
        "empty_rows": empty_rows,
        "error_rows": error_rows,
    }
    return rows, stats
