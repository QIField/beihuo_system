# -*- coding:utf-8 -*-
# @Time    : 2026/10/12 11:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : amap_customer_excel_parser.py
# @Software: PyCharm
# 高德客户档案Excel解析（"标记位置"sheet）：负责数据处理与数据清洗
# （表头映射、单元格清洗、时间解析、行构建）
# 不含任何数据库操作；sheet 读取见 amap_customer_import_service.py，入库见 visit_amap_customer_dao.py

import re
from datetime import datetime

import pandas as pd

# 高德导出Excel中客户数据所在sheet（导出文件含多个sheet，本期只处理该sheet）
AMAP_MARKER_SHEET = "标记位置"

# Excel列名 → 表字段（精确匹配）
SIMPLE_COLUMN_MAPPING = {
    "名称": "customer_name",
    "颜色": "color",
    "描述": "description",
    "文件夹": "folder",
    "地址": "address",
    "所属商圈": "business_circle",
    "创建人": "created_by",
    "创建时间": "created_at",
}

# 前缀匹配列（列名带括号说明，如"位置编码(导出的内容若需再次导入，请不要修改此列)"）
PREFIX_COLUMN_MAPPING = {
    "位置编码": "amap_poi_id",
    "照片": "photo_url",
}

# 基础信息子字段（列名形如"基础信息:524560010026310425/采购负责人"，数字ID每次导出可能变化，按"/"后缀匹配）
BASIC_INFO_SUFFIX_MAPPING = {
    "采购负责人": "contact_person",
    "客户类型": "customer_type",
    "员工数量": "staff_count",
    "工位数量": "station_count",
    "拿货方式": "purchase_channels",
    "用货习惯": "goods_habit",
    "常合作商家": "coop_merchants",
    "客户侧重点": "focus_points",
    "客户信息补充": "remark",
    "拜访时间": "visit_time",
}

# 入库不做字段长度截断（高德导出数据字段长度稳定；description/photo_url/remark 为 TEXT 不限长）

TIME_FORMATS = (
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%Y年%m月%d日 %H:%M", "%Y年%m月%d日",
)

# 多值字段分隔符归一：、，,;； → | （与设计文档同步契约一致，如"开思|线下"）
_MULTI_SEP_RE = re.compile(r"[、，,;；]+")


def _clean(value):
    """单元格清洗：NaN/空串 → None"""
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    return s


def _parse_datetime(value):
    """解析高德导出的时间文案（创建时间/拜访时间），失败返回 None 保留原文可查"""
    s = _clean(value)
    if s is None:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).to_pydatetime()
    except Exception:
        return None


def _parse_color(value):
    """颜色列清洗："#8CFF18=线下合作客户" → ("#8CFF18", "线下合作客户")

    高德导出颜色列可带"=标签"后缀（如 线下合作客户/未合作客户/需二次拜访客户），
    标签部分拆入 tag 字段；无"="后缀时 tag 为 None
    :return: (color, tag)
    """
    s = _clean(value)
    if s is None:
        return None, None
    if "=" not in s:
        return s, None
    color, _, tag = s.partition("=")
    return (color.strip() or None), (tag.strip() or None)


def _normalize_multi_value(value):
    """多值字段清洗：分隔符归一（、，,;； → |）+ 去重 + 按 Unicode 码点排序（保证同值入库顺序固定）"""
    s = _clean(value)
    if s is None:
        return None
    v = _MULTI_SEP_RE.sub("|", s)
    v = re.sub(r"\s*\|\s*", "|", v).strip("|")
    if not v:
        return None
    seen = set()
    parts = []
    for seg in v.split("|"):
        if seg and seg not in seen:
            seen.add(seg)
            parts.append(seg)
    return "|".join(sorted(parts))


def match_columns(columns):
    """
    将Excel表头映射到表字段

    匹配规则（互斥，按序生效）：
    1. 精确匹配 SIMPLE_COLUMN_MAPPING（表头去除前导*号后匹配，如"*创建人"）
    2. 前缀匹配 PREFIX_COLUMN_MAPPING（位置编码/照片 列名带括号说明）
    3. 基础信息子字段按"/"后缀匹配 BASIC_INFO_SUFFIX_MAPPING
    其余列（图标外轮廓/图标填充物/审核结果/不通过原因等）忽略

    :param columns: 表头列表
    :return: {Excel列名: 表字段名}
    """
    mapping = {}
    for col in columns:
        col_clean = str(col).strip()
        col_norm = col_clean.lstrip("*＊").strip()
        if not col_norm:
            continue
        if col_norm in SIMPLE_COLUMN_MAPPING:
            mapping[col] = SIMPLE_COLUMN_MAPPING[col_norm]
            continue
        matched = False
        for prefix, field in PREFIX_COLUMN_MAPPING.items():
            if col_norm.startswith(prefix):
                mapping[col] = field
                matched = True
                break
        if matched:
            continue
        if "/" in col_norm:
            suffix = col_norm.rsplit("/", 1)[-1].strip()
            if suffix in BASIC_INFO_SUFFIX_MAPPING:
                mapping[col] = BASIC_INFO_SUFFIX_MAPPING[suffix]
    return mapping


def build_rows(df):
    """
    DataFrame → 表字段字典列表（数据清洗）

    跳过规则：
    - 整行全空 → 计入 empty_rows
    - 客户名称为空 → 计入 error_rows（customer_name 非空约束）
    - 位置编码为空 → amap_poi_id 置空，由入库流程按"名称+地址"查重后
      复用已有 MANUAL_ 编码或生成新编码（设计文档 2.2：手工客户防重靠名称+地址）

    :return: (rows, stats) stats 含 empty_rows/error_rows/no_code_rows
    """
    col_mapping = match_columns(list(df.columns))
    if "customer_name" not in col_mapping.values():
        raise ValueError('Excel表头缺少"名称"列，请确认上传的是高德地图导出的标记位置文件')

    rows = []
    empty_rows = 0
    error_rows = []
    no_code_rows = 0

    for idx, row in df.iterrows():
        excel_row = idx + 2  # 表头占第1行，DataFrame索引从0起
        values = {field: _clean(row.get(col)) for col, field in col_mapping.items()}

        if all(v is None for v in values.values()):
            empty_rows += 1
            continue

        customer_name = values.get("customer_name")
        if not customer_name:
            error_rows.append({"row": excel_row, "reason": "名称为空"})
            continue

        poi_id = values.get("amap_poi_id")
        if not poi_id:
            no_code_rows += 1

        color_value, color_tag = _parse_color(values.get("color"))
        rows.append({
            "amap_poi_id": poi_id,
            "customer_name": values.get("customer_name"),
            "address": values.get("address"),
            "color": color_value,
            "tag": color_tag,
            "description": values.get("description"),
            "folder": values.get("folder"),
            "business_circle": values.get("business_circle"),
            "created_by": values.get("created_by"),
            "photo_url": values.get("photo_url"),
            "contact_person": values.get("contact_person"),
            "customer_type": _normalize_multi_value(values.get("customer_type")),
            "staff_count": values.get("staff_count"),
            "station_count": values.get("station_count"),
            "purchase_channels": _normalize_multi_value(values.get("purchase_channels")),
            "goods_habit": _normalize_multi_value(values.get("goods_habit")),
            "coop_merchants": values.get("coop_merchants"),
            "focus_points": _normalize_multi_value(values.get("focus_points")),
            "remark": values.get("remark"),
            "visit_time": _parse_datetime(values.get("visit_time")),
            "created_at": _parse_datetime(values.get("created_at")),
        })

    stats = {
        "empty_rows": empty_rows,
        "error_rows": error_rows,
        "no_code_rows": no_code_rows,
    }
    return rows, stats
