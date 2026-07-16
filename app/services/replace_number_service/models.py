"""
更新替换号数据模型
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class MatchedProduct:
    product_id: str
    number: str
    brand_name: str
    display_numbers: List[str] = field(default_factory=list)


@dataclass
class ReplaceNumberRow:
    row_index: int
    oe: str
    brand: str
    new_numbers: List[str] = field(default_factory=list)
    matched_products: List[MatchedProduct] = field(default_factory=list)
    updated_numbers: List[str] = field(default_factory=list)
    status: str = ""
    brand_codes: List[str] = field(default_factory=list)
