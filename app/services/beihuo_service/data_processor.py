"""
备货数据处理器

负责数据清洗、字段映射和品牌逻辑处理。
"""

import re
from datetime import datetime
from typing import Dict, Any, List

from .config import FIELD_MAPPING, DB_FIELDS


def clean_data(value: Any) -> Any:
    """
    清洗数据值
    
    处理特殊格式，如 '<3次' 转换为 '0'
    
    Args:
        value: 原始值
        
    Returns:
        清洗后的值
    """
    if isinstance(value, str):
        # 处理 '<N次' 格式
        match = re.search(r'<(\d+)次', value)
        if match:
            return str(int(match.group(1)) - 3)
    return value


def build_record(item: Dict[str, Any], company: str, gx_date: str = None) -> Dict[str, Any]:
    """
    构建单条记录字典
    
    将API返回的数据转换为数据库记录格式
    
    Args:
        item: API返回的单条数据
        company: 门店代码
        gx_date: 数据更新时间字符串
        
    Returns:
        数据库记录字典
    """
    # 初始化所有字段为None
    record = {field: None for field in DB_FIELDS}
    
    # 从API数据填充字段
    for api_key, db_key in FIELD_MAPPING.items():
        value = item.get(api_key)
        if value is not None:
            record[db_key] = clean_data(value)
    
    # 设置门店代码
    record["company"] = company
    
    # 特殊处理品牌逻辑
    current_brand = item.get("品牌", "")
    current_barcode = item.get("物料条码", "")
    
    # 如果品牌是"原厂 SJZX"且物料条码以"P"或"Y"开头，则根据条码前缀修改品牌
    if current_brand == "原厂 SJZX":
        if current_barcode and current_barcode.startswith("P"):
            record["品牌"] = "原厂国内4s件"
        elif current_barcode and current_barcode.startswith("Y"):
            record["品牌"] = "原厂"
    
    # 如果品牌是"菲尔"或者"菲尔 FREY"，将物料条码复制到品牌号
    if current_brand in ["菲尔", "菲尔 FREY"]:
        record["品牌号"] = record.get("物料条码")
    
    # 设置更新时间
    if gx_date:
        try:
            if ' ' in gx_date:
                parsed_date = datetime.strptime(gx_date, '%Y-%m-%d %H:%M:%S')
            else:
                parsed_date = datetime.strptime(gx_date, '%Y-%m-%d')
            record["更新时间"] = parsed_date
        except ValueError:
            record["更新时间"] = datetime.now()
    else:
        record["更新时间"] = datetime.now()
    
    # 替换号初始为None，后续由车型映射功能填充
    record["替换号"] = None
    
    return record


def transform_fetch_data(raw_data: List[Dict], company: str, gx_date: str = None) -> List[Dict[str, Any]]:
    """
    转换拉取的数据
    
    将API返回的原始数据列表转换为数据库记录列表
    
    Args:
        raw_data: API返回的数据列表
        company: 门店代码
        gx_date: 数据更新时间
        
    Returns:
        数据库记录字典列表
    """
    records = []
    for item in raw_data:
        record = build_record(item, company, gx_date)
        records.append(record)
    return records
