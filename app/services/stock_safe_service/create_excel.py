# -*- coding:utf-8 -*-
# @Time    : 2026/08/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : create_excel.py
# @Software: trae-cn

"""
安全库存 Excel 导出服务

将 stock_safe 表数据导出为 Excel 文件，供前端下载或定时推送使用。
- 生成的文件存储于 static/exports/ 目录
- 文件名遵循通用命名约定：{category}_{company}_{date_str}.xlsx
- 可通过 excel_download 蓝图的通用路由 /download_excel/<category>/<company>/<date_str> 下载
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any

import pandas as pd
from openpyxl.styles import Font, Alignment, PatternFill

from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.models.orm_models.stock_safe_models.stock_safe import StockSafe

logger = get_task_logger('stock_safe')

# ---------- 常量配置 ----------

# 业务分类标识（用于通用 Excel 路由和文件命名）
CATEGORY = "stock_safe"

# 默认门店代码（安全库存目前为全公司维度数据，此处留作扩展）
DEFAULT_COMPANY = "fsbbr"

# 导出目录与下载 URL 模板
EXPORT_DIR = os.path.join("static", "exports")
DOWNLOAD_URL_TEMPLATE = "http://x.fsbbr.net/web/download_excel/{category}/{company}/{date_str}"

# Excel 列配置：字段名 -> 中文表头
# 顺序即为 Excel 中的列顺序
EXCEL_COLUMN_CONFIG: List[Dict[str, str]] = [
    {"field": "number",               "header": "OE号"},
    {"field": "brand_name",           "header": "品牌名"},
    {"field": "frey_no",              "header": "条码"},
    {"field": "pdname",               "header": "产品名称"},
    {"field": "abc_classification",   "header": "ABC分类"},
    {"field": "avg_daily_sales",      "header": "平均日销量"},
    {"field": "base_safety_stock",    "header": "基础安全库存"},
    {"field": "season_coefficient",   "header": "季节系数"},
    {"field": "safety_stock",         "header": "调整后安全库存"},
    {"field": "stock_lower_limit",    "header": "库存下限"},
    {"field": "stock_upper_limit",    "header": "库存上限"},
    {"field": "available_stock",      "header": "可用库存"},
    {"field": "sellable_days",        "header": "可卖天数"},
    {"field": "stock_status",         "header": "库存状态"},
    {"field": "created_at",           "header": "创建时间"},
    {"field": "updated_at",           "header": "更新时间"},
]

# 表头样式填充颜色（浅灰色）
HEADER_FILL_COLOR = "E0E0E0"


# ---------- 数据查询 ----------

def _fetch_stock_safe_data(
    keyword: str = '',
    stock_status: str = '',
    abc_classification: str = '',
    sort_field: str = '',
    sort_order: str = 'asc',
) -> List[Dict[str, Any]]:
    """
    从 stock_safe 表查询数据并转换为字典列表

    支持与前端列表页相同的筛选条件（关键词搜索、状态、ABC分类）和排序，
    确保导出内容与页面展示一致。

    Args:
        keyword: 搜索关键词（匹配 OE号/品牌/产品名称/条码）
        stock_status: 库存状态筛选
        abc_classification: ABC 分类筛选（A/B/C）
        sort_field: 排序字段名
        sort_order: 排序方向 'asc' / 'desc'

    Returns:
        list[dict]: 符合条件的记录列表，每项为字段名->值的字典
    """
    from sqlalchemy import or_

    with orm_session() as session:
        query = session.query(StockSafe)

        # 关键词搜索（多字段 LIKE 匹配）
        if keyword:
            kw = f'%{keyword}%'
            query = query.filter(
                or_(
                    StockSafe.number.like(kw),
                    StockSafe.brand_name.like(kw),
                    StockSafe.pdname.like(kw),
                    StockSafe.frey_no.like(kw),
                )
            )

        # 库存状态筛选
        if stock_status:
            query = query.filter(StockSafe.stock_status == stock_status)

        # ABC 分类筛选
        if abc_classification:
            query = query.filter(StockSafe.abc_classification == abc_classification)

        # 排序
        if sort_field:
            sort_col = getattr(StockSafe, sort_field, None)
            if sort_col is not None:
                if sort_order == 'desc':
                    query = query.order_by(sort_col.desc())
                else:
                    query = query.order_by(sort_col.asc())
        else:
            # 默认排序：按ABC分类(A→B→C) + 可用库存升序
            from sqlalchemy import case
            query = query.order_by(
                case(
                    (StockSafe.abc_classification == 'A', 1),
                    (StockSafe.abc_classification == 'B', 2),
                    (StockSafe.abc_classification == 'C', 3),
                    else_=4,
                ).asc(),
                StockSafe.available_stock.asc(),
            )

        records = query.all()
        logger.info(f"[安全库存Excel导出] 查询到 {len(records)} 条记录")

        # 调用 ORM 的 to_dict() 方法转为字典（保持 datetime 格式化等逻辑一致）
        return [r.to_dict() for r in records]


# ---------- Excel 生成 ----------

def _style_header(ws) -> None:
    """
    为表头行设置统一样式：加粗、居中、浅灰背景

    Args:
        ws: openpyxl Worksheet 对象
    """
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color=HEADER_FILL_COLOR, end_color=HEADER_FILL_COLOR, fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment


def _auto_fit_columns(ws) -> None:
    """
    根据单元格内容自动调整列宽，上限 50 字符

    Args:
        ws: openpyxl Worksheet 对象
    """
    from openpyxl.utils import get_column_letter

    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        for cell in column:
            value = cell.value
            if value is None:
                continue
            try:
                cell_length = len(str(value))
                if cell_length > max_length:
                    max_length = cell_length
            except Exception:
                continue
        adjusted_width = min(max_length + 2, 50)
        if adjusted_width > 0:
            ws.column_dimensions[column_letter].width = adjusted_width


def _export_to_excel(
    records: List[Dict[str, Any]],
    company: str,
    date_str: Optional[str] = None,
) -> str:
    """
    将记录导出为 Excel 文件并保存到 static/exports/

    Args:
        records: 数据记录列表（每项为字段名->值的字典）
        company: 门店/组织代号，用于文件名
        date_str: 日期字符串（YYYY-MM-DD），默认使用当天日期

    Returns:
        str: 生成的 Excel 文件绝对/相对路径
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # 确保导出目录存在
    os.makedirs(EXPORT_DIR, exist_ok=True)

    file_name = f"{CATEGORY}_{company}_{date_str}.xlsx"
    file_path = os.path.join(EXPORT_DIR, file_name)

    # 构造 DataFrame：按配置的列顺序和中文表头
    field_list = [col["field"] for col in EXCEL_COLUMN_CONFIG]
    header_map = {col["field"]: col["header"] for col in EXCEL_COLUMN_CONFIG}

    # 按列顺序提取字段，缺失字段填 None
    df_rows = []
    for rec in records:
        row = {}
        for f in field_list:
            row[f] = rec.get(f, None)
        df_rows.append(row)

    df = pd.DataFrame(df_rows, columns=field_list)
    df = df.rename(columns=header_map)

    sheet_name = "安全库存"

    # 使用 openpyxl 引擎写入，以便后续样式调整
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]

        # 表头样式
        _style_header(ws)

        # 冻结首行
        ws.freeze_panes = "A2"

        # 自动列宽
        _auto_fit_columns(ws)

    logger.info(f"[安全库存Excel导出] 已生成文件: {file_path}，记录数: {len(records)}")
    return file_path


# ---------- 对外服务接口 ----------

def generate_stock_safe_excel(
    company: str = DEFAULT_COMPANY,
    date_str: Optional[str] = None,
    keyword: str = '',
    stock_status: str = '',
    abc_classification: str = '',
    sort_field: str = '',
    sort_order: str = 'asc',
) -> Dict[str, Any]:
    """
    生成安全库存 Excel 文件（对外主入口）

    流程：查询数据 -> 导出到 static/exports/ -> 返回文件信息和下载链接

    Args:
        company: 门店/组织代号，默认 fsbbr
        date_str: 日期字符串（YYYY-MM-DD），默认当天
        keyword: 搜索关键词（匹配 OE号/品牌/产品名称/条码）
        stock_status: 库存状态筛选
        abc_classification: ABC 分类筛选（A/B/C）
        sort_field: 排序字段名
        sort_order: 排序方向 'asc' / 'desc'

    Returns:
        dict: {
            'success': bool,
            'file_path': str,        # 本地文件路径
            'file_name': str,        # 文件名
            'download_url': str,     # 下载URL（供推送使用）
            'record_count': int,     # 导出记录数
            'msg': str,              # 错误信息（失败时）
        }
    """
    try:
        # 1. 查询数据
        records = _fetch_stock_safe_data(
            keyword=keyword,
            stock_status=stock_status,
            abc_classification=abc_classification,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        if not records:
            logger.warning("[安全库存Excel导出] 查询结果为空，未生成文件")
            return {
                'success': False,
                'file_path': None,
                'file_name': None,
                'download_url': None,
                'record_count': 0,
                'msg': '没有可导出的数据',
            }

        # 2. 生成 Excel
        file_path = _export_to_excel(records, company=company, date_str=date_str)
        file_name = os.path.basename(file_path)

        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # 3. 构造下载 URL
        download_url = DOWNLOAD_URL_TEMPLATE.format(
            category=CATEGORY,
            company=company,
            date_str=date_str,
        )

        return {
            'success': True,
            'file_path': file_path,
            'file_name': file_name,
            'download_url': download_url,
            'record_count': len(records),
            'msg': '导出成功',
        }

    except Exception as e:
        logger.exception(f"[安全库存Excel导出] 导出失败: {e}")
        return {
            'success': False,
            'file_path': None,
            'file_name': None,
            'download_url': None,
            'record_count': 0,
            'msg': f'导出失败: {str(e)}',
        }
