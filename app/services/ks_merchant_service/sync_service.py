"""
开思商家数据同步服务

负责协调数据获取、解析和保存的完整流程
"""

from typing import Dict, Any
from datetime import datetime

from app.utils.ks_merchant import fetch_all_data, parse_all_data
from app.models.ks_merchant_models import (
    ShopEventSummaryModel,
    ShopEventDetailModel,
    ShopBusinessIndicatorModel,
)


def sync_ks_merchant_data(cookies: Dict[str, str]) -> Dict[str, Any]:
    """
    同步开思商家数据
    
    完整流程：
    1. 调用API获取三个接口的原始数据
    2. 解析数据为结构化格式
    3. 保存到数据库（存在则更新，不存在则插入）
    
    Args:
        cookies: 登录后的cookies，用于接口认证
        
    Returns:
        同步结果统计
        {
            'summary_count': int,      # 事件汇总记录数
            'detail_count': int,       # 事件明细记录数
            'indicator_count': int,    # 经营指标记录数
            'sync_time': str           # 同步时间
        }
    """
    print(f"[SyncService] 开始同步开思商家数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 获取原始数据
    print("[SyncService] 1. 获取接口数据...")
    raw_data = fetch_all_data(cookies)
    
    # 检查数据有效性
    if not raw_data['event_summary'] or raw_data['event_summary'].get('code') != 200:
        raise Exception(f"事件汇总接口失败: {raw_data['event_summary']}")
    if not raw_data['event_detail'] or raw_data['event_detail'].get('code') != 200:
        raise Exception(f"事件明细接口失败: {raw_data['event_detail']}")
    if not raw_data['business_indicator'] or raw_data['business_indicator'].get('code') != 200:
        raise Exception(f"经营指标接口失败: {raw_data['business_indicator']}")
    
    # 2. 解析数据
    print("[SyncService] 2. 解析数据...")
    parsed_data = parse_all_data(
        raw_data['event_summary'],
        raw_data['event_detail'],
        raw_data['business_indicator']
    )
    
    # 3. 保存到数据库
    print("[SyncService] 3. 保存到数据库...")
    
    # 3.1 保存事件汇总
    summary_model = ShopEventSummaryModel()
    summary_count = summary_model.batch_insert(parsed_data['event_summary'])
    print(f"[SyncService]   - 事件汇总: {summary_count} 条")
    
    # 3.2 保存事件明细
    detail_model = ShopEventDetailModel()
    detail_count = detail_model.batch_insert(parsed_data['event_detail'])
    print(f"[SyncService]   - 事件明细: {detail_count} 条")
    
    # 3.3 保存经营指标
    indicator_model = ShopBusinessIndicatorModel()
    indicator_count = indicator_model.batch_insert(parsed_data['business_indicator'])
    print(f"[SyncService]   - 经营指标: {indicator_count} 条")
    
    result = {
        'summary_count': len(parsed_data['event_summary']),
        'detail_count': len(parsed_data['event_detail']),
        'indicator_count': len(parsed_data['business_indicator']),
        'sync_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    print(f"[SyncService] 同步完成: {result}")
    return result
