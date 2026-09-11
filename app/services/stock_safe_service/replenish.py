# -*- coding:utf-8 -*-
# @Time    : 2026/09/09
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : replenish.py
# @Software: trae-cn

"""
安全库存补货清单数据服务

从 stock_safe 表筛选出需要补货的记录，返回统一列结构（中文表头）的 DataFrame，
供后续 Excel 导出等场景使用。

筛选规则（固定，查询逻辑位于 replenish_dao）：
    - 销售状态：销量低、销量正常
    - 库存状态：需补货|可卖天数较少、需补货、紧急补货

说明：
    - 不过滤废弃数据（stock_safe_useless_data），即不做数据范围筛选。
    - 本模块只负责查询并组装 DataFrame，Excel 生成由调用方另行实现。

数据流：
    stock_safe ──(sales_status / stock_status 筛选)──► 组装 DataFrame
"""

import os
import sys
from typing import List, Dict, Any, Optional

import pandas as pd

# 项目根目录：replenish.py 位于 app/services/stock_safe_service/ 下，向上 4 级
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.utils.logger_config import get_task_logger
from app.utils.orm.session import orm_session
from app.dao.stock_safe_dao.replenish_dao import fetch_replenish_data

logger = get_task_logger('stock_safe')

# ---------- 常量配置 ----------

# 补货 Excel 导出目录（基于项目根目录，不依赖当前工作目录 CWD）
EXPORT_DIR = os.path.join(PROJECT_ROOT, "temp", "stock_safe_data")

# 下载链接基础地址（与线上环境一致，与 excel_download 蓝图同款域名）
DOWNLOAD_BASE_URL = "http://x.fsbbr.net"

# Excel 列配置：字段名 -> 中文表头（顺序即为 DataFrame / Excel 中的列顺序）
# 按补货场景的重点字段排序：商品标识、库存、上下限、可卖天数、状态
EXCEL_COLUMN_CONFIG: List[Dict[str, str]] = [
    {"field": "number",               "header": "OE号"},
    {"field": "brand_name",           "header": "品牌名"},
    {"field": "frey_no",              "header": "条码"},
    {"field": "pdname",               "header": "产品名称"},
    {"field": "abc_classification",   "header": "ABC分类"},
    {"field": "avg_daily_sales",      "header": "平均日销量"},
    {"field": "available_stock",      "header": "可用库存"},
    {"field": "transit_quantity",     "header": "在途数量"},
    {"field": "stock_lower_limit",    "header": "库存下限"},
    {"field": "stock_upper_limit",    "header": "库存上限"},
    {"field": "sellable_days",        "header": "可卖天数"},
    {"field": "safety_stock",         "header": "调整后安全库存"},
    {"field": "stock_status",         "header": "库存状态"},
    {"field": "sales_status",         "header": "销售状态"},
]


# ---------- 对外服务接口 ----------

def get_replenish_data() -> pd.DataFrame:
    """
    获取安全库存补货清单数据（DataFrame，中文表头）

    通过 replenish_dao 按固定补货条件查询，返回列顺序与 Excel 列配置一致、
    表头为中文的 DataFrame。空数据时返回空 DataFrame（保留列结构）。

    Returns:
        pd.DataFrame: 列名为中文表头的补货数据，无记录时返回空 DataFrame
    """
    with orm_session() as session:
        records = fetch_replenish_data(session)
    logger.info(f"[安全库存补货导出] 查询到 {len(records)} 条需补货记录")

    field_list = [col["field"] for col in EXCEL_COLUMN_CONFIG]
    header_map = {col["field"]: col["header"] for col in EXCEL_COLUMN_CONFIG}

    df_rows = []
    for rec in records:
        row = {f: rec.get(f, None) for f in field_list}
        df_rows.append(row)

    df = pd.DataFrame(df_rows, columns=field_list)
    df = df.rename(columns=header_map)

    return df


def generate_replenish_excel() -> str:
    """
    将补货清单数据导出为 Excel 文件（相对项目根目录 temp/stock_safe_data）

    调用 get_replenish_data() 获取数据并写入 Excel，文件保存在项目根目录的
    temp/stock_safe_data 目录下，文件名附带时间戳（YYYYMMDD_HHMMSS）。

    返回：
        str: 生成的 Excel 文件相对路径（相对项目根目录）
    """
    import time

    # 生成前先清理过期文件，避免目录堆积
    cleanup_old_files()

    df = get_replenish_data()

    os.makedirs(EXPORT_DIR, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    file_name = f"补货清单_{ts}.xlsx"
    file_path = os.path.join(EXPORT_DIR, file_name)

    df.to_excel(file_path, index=False)
    logger.info(f"[安全库存补货导出] 已生成 Excel: {file_path}，记录数: {len(df)}")

    return file_path


def generate_replenish_download_url() -> Dict[str, Any]:
    """
    生成补货清单 Excel 并返回下载链接

    调用 generate_replenish_excel() 生成 Excel 文件后，组装带业务时间戳的下载链接
    （指向 stock_safe_web 蓝图的下载路由），供前端下载 / 微信推送等场景使用。

    Returns:
        dict: {
            'success': bool,
            'file_path': str,      # 本地文件绝对路径
            'file_name': str,      # 文件名
            'download_url': str,   # 完整下载链接
            'msg': str,            # 错误信息（失败时）
        }
    """
    try:
        file_path = generate_replenish_excel()
        file_name = os.path.basename(file_path)

        # 从文件名解析业务时间戳（补货清单_YYYYMMDD_HHMMSS.xlsx），
        # 下载链接以时间戳路径形式拼装，无需对中文文件名做 URL 编码
        import re
        m = re.search(r"_(\d{8}_\d{6})\.xlsx$", file_name)
        ts = m.group(1) if m else ""
        download_url = (
            f"{DOWNLOAD_BASE_URL}/web/stock_safe_web/"
            f"download_replenish_excel/{ts}"
        )

        return {
            'success': True,
            'file_path': file_path,
            'file_name': file_name,
            'download_url': download_url,
            'msg': '生成成功',
        }

    except Exception as e:
        logger.exception(f"[安全库存补货导出] 生成下载链接失败: {e}")
        return {
            'success': False,
            'file_path': None,
            'file_name': None,
            'download_url': None,
            'msg': f'生成失败: {str(e)}',
        }


def get_replenish_file_path(file_name: str) -> Optional[str]:
    """
    获取 temp/stock_safe_data 目录下指定补货 Excel 文件的完整绝对路径

    供下载接口调用：对文件名做合法性校验（拒绝空值及包含路径分隔符的
    文件名，防止路径穿越），并在 EXPORT_DIR 下解析出真实文件路径。

    Args:
        file_name: 文件名，如 补货清单_20260910_120000.xlsx

    Returns:
        str | None: 文件绝对路径；文件名非法或文件不存在时返回 None
    """
    if not file_name:
        logger.warning("[安全库存补货下载] 文件名为空")
        return None

    # 文件名中不允许出现路径分隔符（/ 或 \），防止路径穿越
    if os.path.basename(file_name) != file_name:
        logger.warning(f"[安全库存补货下载] 非法文件名: {file_name}")
        return None

    file_path = os.path.join(EXPORT_DIR, file_name)
    if not os.path.isfile(file_path):
        logger.warning(f"[安全库存补货下载] 文件不存在: {file_path}")
        return None

    return file_path


def _parse_file_ts(file_name: str):
    """
    从补货文件名中解析业务时间戳

    文件名格式：补货清单_YYYYMMDD_HHMMSS.xlsx，解析其中的 YYYYMMDD_HHMMSS。

    Args:
        file_name: 文件名

    Returns:
        datetime | None: 解析成功返回对应时间，无法解析返回 None
    """
    import re
    from datetime import datetime

    m = re.search(r"_(\d{8})_(\d{6})\.xlsx$", file_name)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")


def cleanup_old_files(days: int = 30) -> int:
    """
    清理 temp/stock_safe_data 目录下过期（超过指定天数）的补货 Excel 文件

    仅处理本模块生成的补货清单文件（文件名格式：补货清单_YYYYMMDD_HHMMSS.xlsx），
    按文件名中的业务时间戳判断；文件名格式不符的文件一律跳过，不删除。
    文件时间早于 (当前时间 - days 天) 即清理。

    Args:
        days: 保留天数，默认 30 天

    Returns:
        int: 实际删除的文件数量
    """
    from datetime import datetime, timedelta

    if not os.path.isdir(EXPORT_DIR):
        logger.info(f"[安全库存补货清理] 目录不存在，跳过: {EXPORT_DIR}")
        return 0

    cutoff_dt = datetime.now() - timedelta(days=days)
    removed = 0

    for name in os.listdir(EXPORT_DIR):
        file_path = os.path.join(EXPORT_DIR, name)
        if not os.path.isfile(file_path):
            continue
        # 仅处理本模块生成的补货清单文件，文件名格式不符的一律跳过
        file_dt = _parse_file_ts(name)
        if file_dt is None:
            continue
        try:
            if file_dt < cutoff_dt:
                os.remove(file_path)
                removed += 1
                logger.info(f"[安全库存补货清理] 已删除过期文件: {file_path}")
        except OSError as e:
            logger.warning(f"[安全库存补货清理] 删除失败 {file_path}: {e}")

    logger.info(f"[安全库存补货清理] 清理完成，共删除 {removed} 个文件")
    return removed






# if __name__ == "__main__":
#     # 本地测试：先清理过期文件，再生成 Excel
#     # cleanup_old_files()
#     generate_replenish_excel()
