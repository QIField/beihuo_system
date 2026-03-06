"""
搜索输入解析器
支持多行搜索、批量搜索的输入解析
"""

import re
from typing import List


def parse_space(input_str: str) -> List[str]:
    """
    解析空格分隔输入（支持换行）
    用于：OE、条码、编号等精确字段
    
    示例：
        "OE001 OE002"          -> ['OE001', 'OE002']
        "OE001\nOE002 OE003"   -> ['OE001', 'OE002', 'OE003']
    """
    if not input_str:
        return []
    
    lines = input_str.split('\n') if '\n' in input_str else [input_str]
    
    result = []
    for line in lines:
        for part in line.split():
            if part.strip():
                result.append(part.strip())
    return result


def parse_comma(input_str: str) -> List[str]:
    """
    解析逗号分隔输入（支持换行、中英文逗号）
    用于：物料名称、描述等字段
    
    示例：
        "刹车片,滤清器"           -> ['刹车片', '滤清器']
        "刹车片，滤清器\n机油"     -> ['刹车片', '滤清器', '机油']
    """
    if not input_str:
        return []
    
    lines = input_str.split('\n') if '\n' in input_str else [input_str]
    
    result = []
    for line in lines:
        for part in re.split(r'[,，]', line):
            if part.strip():
                result.append(part.strip())
    return result


def parse_mixed(input_str: str) -> List[str]:
    """
    解析混合分隔（空格、逗号、换行）
    用于：通用搜索框
    
    示例：
        "OE001, OE002 OE003\nOE004"  -> ['OE001', 'OE002', 'OE003', 'OE004']
    """
    if not input_str:
        return []
    
    normalized = input_str.replace(',', '\n').replace('，', '\n').replace(' ', '\n')
    return [s.strip() for s in normalized.split('\n') if s.strip()]
