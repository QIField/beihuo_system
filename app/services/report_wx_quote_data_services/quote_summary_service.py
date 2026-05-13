# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 08:58
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : quote_summary_service.py
# @Software: PyCharm

import sys
import os
import json
import re
import calendar
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.report_wx_quote_data_services.weixin_decoding_result_service import fetch_data, convert_to_demo_format
from app.utils.orm.session import orm_session
from app.models.orm_models.weixin_decoding_alias import WeixinDecodingAlias


def load_alias_data(oe_code_list=None):
    """
    从 weixin_decoding_alias 表加载别名数据（只加载需要的 oe 码）
    
    Args:
        oe_code_list: 需要查询的 oe_code 列表，如果为 None 则加载全部
        
    Returns:
        字典: {oe_code: standardName}
    """
    alias_dict = {}
    
    with orm_session() as session:
        # 只查询需要的字段，提高查询效率
        query = session.query(WeixinDecodingAlias.oeCode, WeixinDecodingAlias.standardName).filter(
            WeixinDecodingAlias.oeCode.isnot(None),
            WeixinDecodingAlias.oeCode != ''
        )
        
        # 如果有指定的 oe_code 列表，只加载这些
        if oe_code_list:
            query = query.filter(WeixinDecodingAlias.oeCode.in_(oe_code_list))
        
        items = query.all()
        
        for oe_code, standard_name in items:
            if oe_code and standard_name:
                alias_dict[oe_code] = standard_name
    
    return alias_dict


def load_data_from_db(start_date=None, end_date=None, groupname=None, nickname=None):
    """
    从数据库加载数据并转换为 demo.json 格式
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        groupname: 群名称，可选
        nickname: 业务员，可选
        
    Returns:
        数据列表
    """
    # 从数据库获取数据
    print(f"从数据库获取数据: {start_date} ~ {end_date}, 群: {groupname}, 业务员: {nickname}")
    records = fetch_data(start_date, end_date, groupname, nickname)
    
    if not records:
        print("没有数据")
        return []
    
    print(f"获取到 {len(records)} 条记录")
    
    # 转换为 demo.json 格式
    data = convert_to_demo_format(records)
    
    return data


# 预编译正则表达式，避免每次循环重新编译（已不再需要，保留兼容性）
PART_NAME_PATTERN = re.compile(r'^\d+、(.+)\(')


def summarize_oe_codes_daily(date_str, groupname=None, nickname=None, page=1, limit=20, export_json=False):
    """
    按 groupname、oe_code、create_time（日期）分组统计 oe 码的询价次数和缺货次数（日统计）
    深度优化版本：第一次遍历完成统计和收集，第二次只遍历统计结果补充别名
    
    Args:
        date_str: 日期字符串，如 "2026-02-21"
        groupname: 群名称，可选
        nickname: 业务员，可选
        page: 页码
        limit: 每页条数
        export_json: 是否导出json文件
        
    Returns:
        统计结果列表（带分页信息）
    """
    # 1. 从数据库加载数据
    data = load_data_from_db(date_str, date_str, groupname, nickname)
    if not data:
        return {
            'result': [],
            'total': 0,
            'page': page,
            'limit': limit
        }
    
    # 2. 第一次遍历：完成统计 + 收集 oe_code + 保存第一个 detail（用于提取 part_name 和 quote_info）
    stats_dict = {}
    required_oe_codes = set()
    # 保存每个 key 对应的第一个 detail（用于提取 part_name 和 quote_info）
    first_detail_dict = {}
    
    for record in data:
        groupname = record.get('groupname', '')
        create_time = record.get('create_time', '')
        
        # 提取日期部分
        create_date = ''
        if create_time:
            create_date = create_time.split(' ')[0] if ' ' in create_time else create_time
        
        result_details = record.get('result_details', [])
        
        for detail in result_details:
            oe_code = detail.get('oe_code', '')
            # 如果OE码是"0"，当作空处理
            if oe_code == '0':
                oe_code = ''
            if not oe_code:
                continue
            
            is_out_of_stock = detail.get('is_out_of_stock', False)
            
            # 收集 oe_code
            required_oe_codes.add(oe_code)
            
            # 构建唯一 key
            key = f"{groupname}__{oe_code}"
            
            # 初始化统计数据
            if key not in stats_dict:
                stats_dict[key] = {
                    'create_date': create_date,
                    'groupname': groupname,
                    'part_name': '',  # 稍后补充
                    'oe_code': oe_code,
                    'quote_info': '',  # 稍后补充
                    'inquiry_count': 0,
                    'out_of_stock_count': 0
                }
                # 保存第一个 detail
                first_detail_dict[key] = detail
            
            # 更新计数
            stats_dict[key]['inquiry_count'] += 1
            if is_out_of_stock:
                stats_dict[key]['out_of_stock_count'] += 1
    
    # 3. 加载别名数据
    alias_dict = load_alias_data(list(required_oe_codes))
    
    # 4. 第二次遍历：只遍历统计结果（数量少很多），补充 part_name 和 quote_info
    for key, stat in stats_dict.items():
        oe_code = stat['oe_code']
        detail = first_detail_dict.get(key, {})
        
        # 提取配件名称和报价信息
        part_name = detail.get('part_name', '')
        quote_info = detail.get('quote_info', '')
        
        # 从别名表中查找 standardName 替换 part_name
        if oe_code in alias_dict:
            part_name = alias_dict[oe_code]
        
        stat['part_name'] = part_name
        stat['quote_info'] = quote_info
    
    # 5. 排序
    stats_list = list(stats_dict.values())
    stats_list.sort(key=lambda x: (x['create_date'], x['groupname']))
    
    # 6. 导出到 json
    if export_json:
        output_path = os.path.join(os.path.dirname(__file__), 'daily_summary.json')
        save_summary_to_json(stats_list, output_path)
    
    # 7. 分页
    total = len(stats_list)
    start = (page - 1) * limit
    end = start + limit
    result_list = stats_list[start:end]
    
    return {
        'result': result_list,
        'total': total,
        'page': page,
        'limit': limit
    }


def summarize_oe_codes_monthly(month_str, groupname=None, nickname=None, page=1, limit=20, export_json=False):
    """
    按 groupname、oe_code、月份分组统计 oe 码的询价次数和缺货次数（月统计）
    深度优化版本：第一次遍历完成统计和收集，第二次只遍历统计结果补充别名
    
    Args:
        month_str: 月份字符串，如 "2026-01"
        groupname: 群名称，可选
        nickname: 业务员，可选
        page: 页码
        limit: 每页条数
        export_json: 是否导出json文件
        
    Returns:
        统计结果列表（带分页信息）
    """
    # 1. 计算月份范围
    year, month = month_str.split('-')
    year = int(year)
    month = int(month)
    start_date = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    month_display = f"{year}年{month}月"
    
    # 2. 从数据库加载数据
    data = load_data_from_db(start_date, end_date, groupname, nickname)
    if not data:
        return {
            'result': [],
            'total': 0,
            'page': page,
            'limit': limit
        }
    
    # 3. 第一次遍历：完成统计 + 收集 oe_code + 保存第一个 detail（用于提取 part_name 和 quote_info）
    stats_dict = {}
    required_oe_codes = set()
    # 保存每个 key 对应的第一个 detail（用于提取 part_name 和 quote_info）
    first_detail_dict = {}
    
    for record in data:
        groupname = record.get('groupname', '')
        result_details = record.get('result_details', [])
        
        for detail in result_details:
            oe_code = detail.get('oe_code', '')
            # 如果OE码是"0"，当作空处理
            if oe_code == '0':
                oe_code = ''
            if not oe_code:
                continue
            
            is_out_of_stock = detail.get('is_out_of_stock', False)
            
            # 收集 oe_code
            required_oe_codes.add(oe_code)
            
            # 构建唯一 key
            key = f"{groupname}__{oe_code}"
            
            # 初始化统计数据
            if key not in stats_dict:
                stats_dict[key] = {
                    'month': month_display,
                    'groupname': groupname,
                    'part_name': '',  # 稍后补充
                    'oe_code': oe_code,
                    'quote_info': '',  # 稍后补充
                    'inquiry_count': 0,
                    'out_of_stock_count': 0
                }
                # 保存第一个 detail
                first_detail_dict[key] = detail
            
            # 更新计数
            stats_dict[key]['inquiry_count'] += 1
            if is_out_of_stock:
                stats_dict[key]['out_of_stock_count'] += 1
    
    # 4. 加载别名数据
    alias_dict = load_alias_data(list(required_oe_codes))
    
    # 5. 第二次遍历：只遍历统计结果（数量少很多），补充 part_name 和 quote_info
    for key, stat in stats_dict.items():
        oe_code = stat['oe_code']
        detail = first_detail_dict.get(key, {})
        
        # 提取配件名称和报价信息
        part_name = detail.get('part_name', '')
        quote_info = detail.get('quote_info', '')
        
        # 从别名表中查找 standardName 替换 part_name
        if oe_code in alias_dict:
            part_name = alias_dict[oe_code]
        
        stat['part_name'] = part_name
        stat['quote_info'] = quote_info
    
    # 6. 排序
    stats_list = list(stats_dict.values())
    stats_list.sort(key=lambda x: (x['month'], x['groupname']))
    
    # 7. 导出到 json
    if export_json:
        output_path = os.path.join(os.path.dirname(__file__), 'monthly_summary.json')
        save_summary_to_json(stats_list, output_path)
    
    # 8. 分页
    total = len(stats_list)
    start = (page - 1) * limit
    end = start + limit
    result_list = stats_list[start:end]
    
    return {
        'result': result_list,
        'total': total,
        'page': page,
        'limit': limit
    }


def save_summary_to_json(summary_list, output_path):
    """
    保存统计结果到 json 文件
    
    Args:
        summary_list: 统计结果列表
        output_path: 输出文件路径
        
    Returns:
        输出文件路径
    """
    if not summary_list:
        print("没有数据可保存")
        return None
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary_list, f, ensure_ascii=False, indent=4)
    
    return output_path


def main():
    """
    主函数：统计 OE 码并导出 json（日统计和月统计）
    """
    # 1. 日统计
    summarize_oe_codes_daily("2026-01-01")
    
    # 2. 月统计
    summarize_oe_codes_monthly("2026-01")
    
    print("\n" + "="*70)
    print("完成!")
    print("="*70)


if __name__ == '__main__':
    main()
