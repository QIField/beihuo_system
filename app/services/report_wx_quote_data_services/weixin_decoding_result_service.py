# -*- coding:utf-8 -*-
# @Time    : 2026/4/27 13:11
# @Author  : xingkongtub
# @Project  : beihuo_system
# @File  : weixin_decoding_result_service.py
# @Software: PyCharm

import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import pandas as pd


from app.utils.orm.session import orm_session
from app.models.orm_models.weixin_decoding_result import WeixinDecodingResult


def fetch_data(start_date=None, end_date=None, page=None, limit=None, convert_format=False):
    """
    从数据库获取微信解码结果数据（使用 ORM）
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        page: 页码，从1开始，可选
        limit: 每页条数，可选
        convert_format: 是否转换为 demo.json 格式并返回分页信息
        
    Returns:
        如果 convert_format=False，返回原始记录列表
        如果 convert_format=True，返回包含分页信息的字典 {'result': [...], 'total': ..., 'page': ..., 'limit': ...}
    """
    from sqlalchemy import func
    
    records = []
    total = 0
    
    with orm_session() as session:
        # 构建查询
        query = session.query(WeixinDecodingResult).filter(
            WeixinDecodingResult.result.isnot(None),
            WeixinDecodingResult.result != ''
        )
        
        # 添加时间范围筛选 - 使用 DATE() 函数只比较日期部分
        if start_date:
            query = query.filter(func.date(WeixinDecodingResult.creation_date) >= start_date)
        
        if end_date:
            query = query.filter(func.date(WeixinDecodingResult.creation_date) <= end_date)
        
        # 如果需要分页且需要返回 total，先获取总数
        if convert_format:
            total = query.count()
        
        # 按创建时间倒序
        query = query.order_by(WeixinDecodingResult.creation_date.desc())
        
        # 添加分页
        if page and limit:
            offset = (page - 1) * limit
            query = query.offset(offset).limit(limit)
        elif limit:
            query = query.limit(limit)
        
        # 获取数据
        items = query.all()
        
        # 转换为字典
        for item in items:
            records.append(item.to_dict())
    
    # 如果不需要格式转换，直接返回原始数据
    if not convert_format:
        return records
    
    # 否则转换为demo格式并返回带分页信息的数据
    demo_data = convert_to_demo_format(records)
    
    return {
        'result': demo_data,
        'total': total,
        'page': page or 1,
        'limit': limit or 20
    }


def fetch_data_paged(start_date=None, end_date=None, page=1, limit=20):
    """
    从数据库获取微信解码结果数据（使用 ORM，带分页信息）
    这是专门给API层调用的包装函数
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        page: 页码，从1开始
        limit: 每页条数
        
    Returns:
        包含分页信息的字典
    """
    return fetch_data(start_date, end_date, page, limit, convert_format=True)


def convert_to_demo_format(records):
    """
    将数据库记录转换为 demo.json 格式
    
    Args:
        records: 数据库记录列表
        
    Returns:
        demo.json 格式的列表
    """
    demo_data = []
    
    for record in records:
        # 解析 result 为数组
        result_text = record.get('result', '')
        result_array = parse_lines(result_text) if result_text else []
        
        # 检查是否应该跳过 result 第一个元素
        should_skip_first = True
        content = record.get('content', '')
        if content:
            content_lines = parse_lines(content)
            if content_lines:
                first_content_line = content_lines[0].strip()
                # 判断：如果 result 第一个元素和 content 第一行一样，就跳过（这通常是 VIN 码）
                if len(result_array) > 0 and result_array[0].strip() == first_content_line:
                    should_skip_first = True
                # 否则，如果 content 第一行是纯数字/字母（可能是 OE 码），就不跳过
                elif re.match(r'^[A-Za-z0-9]+$', first_content_line):
                    should_skip_first = False
        
        # 跳过第一个元素（如 VIN 码）
        if should_skip_first and len(result_array) > 0:
            result_array = result_array[1:]
        
        # 解析每个 result 项，提取 OE 码和缺货状态
        result_details = []
        oe_code_list = []
        
        for result_item in result_array:
            # 解析 OE 码：匹配 (31126775971) 或 (A2462402517) 这种格式
            oe_match = re.search(r'\(([A-Za-z0-9]+)\)', result_item)
            oe_code = oe_match.group(1) if oe_match else ''
            # 如果OE码是"0"，当作空处理
            if oe_code == '0':
                oe_code = ''
            if oe_code:
                oe_code_list.append(oe_code)
            
            # 检查是否缺货：=0 或 = 0 表示缺货
            is_out_of_stock = bool(re.search(r'=\s*0', result_item))
            
            result_details.append({
                'item': result_item,
                'oe_code': oe_code,
                'is_out_of_stock': is_out_of_stock
            })
        
        demo_item = {
            'id': str(record.get('id', '')),
            'create_time': record.get('creation_date', ''),
            'groupname': record.get('groupname', ''),
            'nickname': record.get('nickname', ''),
            'content': record.get('content', ''),
            'result': result_array,
            'result_details': result_details,
            'oe_code_list': oe_code_list
        }
        
        demo_data.append(demo_item)
    
    return demo_data


def parse_lines(text):
    """
    按行分割文本，过滤空行
    
    Args:
        text: 文本内容
        
    Returns:
        行列表
    """
    items = []
    
    if not text:
        return items
    
    # 按行分割
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        items.append(line)
    
    return items


def main():
    """
    示例用法（保留main函数作为示例
    """
    import json
    
    # 示例1：获取所有数据（不带日期过滤）
    print("\n" + "="*70)
    print("测试1：获取所有数据（不带日期过滤）")
    print("="*70)
    records_all = fetch_data(None, None)
    print(f"获取到 {len(records_all)} 条记录")
    
    if len(records_all) > 0:
        print("前2条数据：")
        for i, rec in enumerate(records_all[:2]):
            print(f"记录 {i+1}: {rec}")
    
    # 示例2：带分页获取所有数据
    print("\n" + "="*70)
    print("测试2：带分页获取所有数据（第1页，每页10条）")
    print("="*70)
    paged_result = fetch_data_paged(None, None, 1, 10)
    print(f"获取到 {len(paged_result['result'])} 条记录，总共有 {paged_result['total']} 条")
    
    # 3. 保存为 json 文件
    print("\n" + "="*70)
    print("保存为 demo.json...")
    output_path = os.path.join(os.path.dirname(__file__), 'demo.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(paged_result['result'], f, ensure_ascii=False, indent=4)
    print(f"文件已保存到: {output_path}")
    
    print("\n" + "="*70)
    print("完成!")
    print("="*70)


if __name__ == '__main__':
    main()
