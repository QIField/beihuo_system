# -*- coding: utf-8 -*-
"""
奔驰报价 OE 替换号自动同步数据模型
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class OePair:
    """OE 一一对应分组"""
    with_a: str      # 带 A 的完整号，如 A21286075857F03
    without_a: str   # 不带 A 的号，如 21286075857F03


@dataclass
class UpdateRecord:
    """CRM 替换号更新记录"""
    oe: str                      # 搜索用的 OE（不带 A）
    brand_name: str              # 产品品牌
    product_id: str              # CRM product_id
    numbers_before: List[str] = field(default_factory=list)   # 更新前替换号
    numbers_after: List[str] = field(default_factory=list)    # 更新后替换号
    status: str = ""             # 成功 / 失败
    message: str = ""            # 失败原因或备注
