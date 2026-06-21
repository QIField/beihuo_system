# -*- coding:utf-8 -*-
"""
SQL 子句构建工具
用于安全地拼接 ORDER BY 等子句，防止 SQL 注入
"""


def build_order_by(
    sort_column: str,
    sort_dir: str,
    column_map: dict,
    numeric_columns: set = None,
    default: str = ""
) -> str:
    """
    构建安全的 ORDER BY 子句（通过白名单校验，防止 SQL 注入）

    Args:
        sort_column: 前端传来的列名（驼峰）
        sort_dir: 排序方向（asc/desc）
        column_map: {前端列名: 数据库列名} 的白名单映射
        numeric_columns: 数值列集合，此类列用 CAST(.. AS DECIMAL(20,2)) 按数值排序
        default: 默认 ORDER BY 子句（当未传排序参数时使用）

    Returns:
        str: ORDER BY 子句（不含 ORDER BY 关键字）
    """
    if not sort_column or sort_column not in column_map:
        return default
    if sort_dir not in ('asc', 'desc'):
        sort_dir = 'desc'
    db_col = column_map[sort_column]
    # 数值列 → CAST 成 DECIMAL 后再排序，避免字符串词典序（9 > 10）
    if numeric_columns and sort_column in numeric_columns:
        return f"CAST({db_col} AS DECIMAL(20,2)) {sort_dir.upper()}"
    return f"{db_col} {sort_dir.upper()}"
