# -*- coding: utf-8 -*-
"""
OE 清洗、筛选、分组
"""

from typing import List, Set

from .models import OePair


def filter_valid_oe_codes(oe_codes: Set[str]) -> Set[str]:
    """
    筛选有效 OE：
    - 长度 10 位
    - 或以 A 开头（不区分大小写）
    """
    valid = set()
    for raw in oe_codes:
        oe = str(raw).strip()
        if not oe:
            continue
        if len(oe) == 10 or oe.upper().startswith('A'):
            valid.add(oe)
    return valid


def build_oe_pairs(oe_codes: Set[str]) -> List[OePair]:
    """
    将有效 OE 拆分成一一对应的两组。

    规则：
    - 以 A 开头的 → with_a 为原值，without_a 为去掉 A 后的值
    - 长度 10 位且不以 A 开头的 → without_a 为原值，with_a 为加上 A 后的值
    """
    pairs = []
    for oe in oe_codes:
        oe = str(oe).strip()
        if oe.upper().startswith('A'):
            pairs.append(OePair(with_a=oe, without_a=oe[1:]))
        else:
            pairs.append(OePair(with_a=f"A{oe}", without_a=oe))
    return pairs
