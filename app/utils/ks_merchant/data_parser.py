"""
开思商家平台数据解析器

提供接口数据的解析和转换功能
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from .config import INDICATOR_FIELD_MAPPING


def _parse_date(date_str: str, year: int = None) -> Optional[str]:
    """
    解析日期字符串为标准格式
    
    支持格式:
    - "04-09" -> "2026-04-09"
    - "4.8 周三" -> "2026-04-08"
    
    Args:
        date_str: 日期字符串
        year: 年份（可选，默认当前年）
        
    Returns:
        标准日期格式字符串 YYYY-MM-DD
    """
    if not year:
        year = datetime.now().year
    
    try:
        # 格式1: "04-09"
        if re.match(r'^\d{2}-\d{2}$', date_str):
            month, day = date_str.split('-')
            return f"{year}-{month}-{day}"
        
        # 格式2: "4.8 周三" 或 "4.15 周二"
        match = re.match(r'^(\d{1,2})\.(\d{1,2})', date_str)
        if match:
            month = match.group(1).zfill(2)
            day = match.group(2).zfill(2)
            return f"{year}-{month}-{day}"
            
    except Exception as e:
        print(f"日期解析失败: {date_str}, 错误: {e}")
    
    return None


def _convert_value(value_str: str) -> Any:
    """
    转换数值字符串
    
    - "60,834.07" -> 60834.07
    - "99.63%" -> "99.63%"
    - "暂不提供" -> None
    - "78" -> 78
    
    Args:
        value_str: 原始值字符串
        
    Returns:
        转换后的值
    """
    if not value_str or value_str == "暂不提供":
        return None
    
    # 移除千分位逗号
    cleaned = value_str.replace(',', '')
    
    # 百分比保持字符串
    if '%' in cleaned:
        return cleaned
    
    # 尝试转换为数字
    try:
        if '.' in cleaned:
            return float(cleaned)
        else:
            return int(cleaned)
    except ValueError:
        return cleaned


def parse_event_summary_data(
    api_response: Dict[str, Any],
    year: int = None
) -> List[Dict[str, Any]]:
    """
    解析事件汇总数据（接口1）
    
    Args:
        api_response: API原始响应数据
        year: 年份（可选）
        
    Returns:
        解析后的数据列表，每条记录包含:
        - event_date: 日期 (YYYY-MM-DD)
        - total_event_count: 事件总数
    """
    if not api_response or api_response.get('code') != 200:
        print(f"接口返回错误: {api_response.get('errorMessage') if api_response else '无数据'}")
        return []
    
    data = api_response.get('data', [])
    parsed_data = []
    
    for item in data:
        event_date = _parse_date(item.get('eventDate', ''), year)
        if event_date:
            parsed_data.append({
                'event_date': event_date,
                'total_event_count': item.get('eventCount', 0),
            })
    
    return parsed_data


def parse_event_detail_data(
    api_response: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    解析事件详情数据（接口2）
    
    Args:
        api_response: API原始响应数据
        
    Returns:
        解析后的数据列表，每条记录包含:
        - event_date: 日期
        - event_type_key: 事件类型标识
        - event_type_name: 事件类型名称
        - event_count: 事件数量
        - statistics_unit: 统计单位
        - event_influence: 影响说明
        - event_suggest: 处理建议
    """
    if not api_response or api_response.get('code') != 200:
        print(f"接口返回错误: {api_response.get('errorMessage') if api_response else '无数据'}")
        return []
    
    data = api_response.get('data', [])
    parsed_data = []
    
    for item in data:
        parsed_data.append({
            'event_date': item.get('eventDate'),
            'event_type_key': item.get('eventTypeKey'),
            'event_type_name': item.get('eventTypeName'),
            'event_count': item.get('eventCount', 0),
            'statistics_unit': item.get('statisticsUnit'),
            'event_influence': item.get('eventInfluence'),
            'event_suggest': item.get('eventSuggest'),
        })
    
    return parsed_data


def parse_business_indicator_data(
    api_response: Dict[str, Any],
    year: int = None
) -> List[Dict[str, Any]]:
    """
    解析经营指标数据（接口3）
    
    将横向数据转置为纵向，每天一条记录
    
    Args:
        api_response: API原始响应数据
        year: 年份（可选）
        
    Returns:
        解析后的数据列表，每条记录是一个日期的所有指标:
        - indicator_date: 日期
        - sales_amount: 销售额
        - system_quote_rate: 系统报价成交额比例
        - order_customer_count: 下单客户数
        - ...其他指标
    """
    if not api_response or api_response.get('code') != 200:
        print(f"接口返回错误: {api_response.get('errorMessage') if api_response else '无数据'}")
        return []
    
    data = api_response.get('data', {})
    heads = data.get('heads', [])
    rows = data.get('rows', [])
    
    if not heads or not rows:
        return []
    
    # 解析日期列（date1-date7对应的实际日期）
    date_columns = {}
    for head in heads:
        key = head.get('key')
        if key and key.startswith('date'):
            # 从 names 中提取日期，如 ["4.8 周三"]
            names = head.get('names', [])
            if names:
                date_str = _parse_date(names[0], year)
                if date_str:
                    date_columns[key] = date_str
    
    # 按日期组织数据
    daily_data = {}
    for date_key, date_str in date_columns.items():
        daily_data[date_str] = {'indicator_date': date_str}
    
    # 遍历每一行指标数据
    for row in rows:
        indicator_name = row.get('indicator')
        if not indicator_name:
            continue
        
        # 获取数据库字段名
        field_name = INDICATOR_FIELD_MAPPING.get(indicator_name)
        if not field_name:
            # 如果没有映射，使用指标名作为字段名（去除特殊字符）
            field_name = re.sub(r'[^\w]', '_', indicator_name)
        
        # 提取每个日期的值
        for date_key, date_str in date_columns.items():
            value = row.get(date_key)
            if value is not None:
                daily_data[date_str][field_name] = _convert_value(value)
    
    # 转换为列表
    return list(daily_data.values())


# 便捷函数：解析所有数据
def parse_all_data(
    event_summary_response: Dict[str, Any],
    event_detail_response: Dict[str, Any],
    business_indicator_response: Dict[str, Any],
    year: int = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    解析所有三个接口的数据
    
    Args:
        event_summary_response: 接口1响应
        event_detail_response: 接口2响应
        business_indicator_response: 接口3响应
        year: 年份（可选）
        
    Returns:
        解析后的数据字典
        {
            "event_summary": [...],
            "event_detail": [...],
            "business_indicator": [...]
        }
    """
    return {
        "event_summary": parse_event_summary_data(event_summary_response, year),
        "event_detail": parse_event_detail_data(event_detail_response),
        "business_indicator": parse_business_indicator_data(business_indicator_response, year),
    }
