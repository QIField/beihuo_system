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


def fetch_data(start_date=None, end_date=None, groupname=None, nickname=None, page=None, limit=None, convert_format=False):
    """
    从数据库获取微信解码结果数据（使用 ORM）
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        groupname: 群名称，可选
        nickname: 业务员，可选
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
        
        # 添加群名称筛选
        if groupname:
            query = query.filter(WeixinDecodingResult.groupname == groupname)
        
        # 添加业务员筛选（模糊查询）
        if nickname:
            query = query.filter(WeixinDecodingResult.nickname.like(f'%{nickname}%'))
        
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


def fetch_data_paged(start_date=None, end_date=None, groupname=None, nickname=None, page=1, limit=20):
    """
    从数据库获取微信解码结果数据（使用 ORM，带分页信息）
    这是专门给API层调用的包装函数
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        groupname: 群名称，可选
        nickname: 业务员，可选
        page: 页码，从1开始
        limit: 每页条数
        
    Returns:
        包含分页信息的字典
    """
    return fetch_data(start_date, end_date, groupname, nickname, page, limit, convert_format=True)


def fetch_groupname_list():
    """
    获取所有群名称列表（去重）
    
    Returns:
        群名称列表
    """
    from sqlalchemy import distinct
    
    with orm_session() as session:
        # 查询所有不重复的群名称
        groupnames = session.query(distinct(WeixinDecodingResult.groupname)).filter(
            WeixinDecodingResult.groupname.isnot(None),
            WeixinDecodingResult.groupname != ''
        ).all()
        
        # 转换为列表并排序
        groupname_list = [gn[0] for gn in groupnames]
        groupname_list.sort()
        
        return groupname_list


def fetch_nickname_list():
    """
    获取所有业务员（nickname）列表（去重）
    
    Returns:
        业务员列表
    """
    from sqlalchemy import distinct
    
    with orm_session() as session:
        # 查询所有不重复的业务员
        nicknames = session.query(distinct(WeixinDecodingResult.nickname)).filter(
            WeixinDecodingResult.nickname.isnot(None),
            WeixinDecodingResult.nickname != ''
        ).all()
        
        # 转换为列表并排序
        nickname_list = [nn[0] for nn in nicknames]
        nickname_list.sort()
        
        return nickname_list


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
        
        # 解析每个 result 项，提取配件名称、OE 码、报价信息和缺货状态
        result_details = []
        oe_code_list = []
        
        for result_item in result_array:
            # 初始化各个字段
            part_name = ''
            oe_code = ''
            quote_info = ''
            
            # 1. 解析配件名称：提取到括号或等号前的内容
            part_name_match = re.match(r'^(?:\d+[、.,])?\s*(.*?)(?=\s*\(|=|$)', result_item)
            if part_name_match:
                part_name = part_name_match.group(1).strip()
            
            # 2. 解析 OE 码：匹配 (31126775971) 或 (A2462402517) 这种格式
            oe_match = re.search(r'\(([A-Za-z0-9]+)\)', result_item)
            oe_code = oe_match.group(1) if oe_match else ''
            # 如果OE码是"0"，当作空处理
            if oe_code == '0':
                oe_code = ''
            if oe_code:
                oe_code_list.append(oe_code)
            
            # 3. 解析报价信息：匹配等号后面的内容，如 "= 菲尔 75 / 猫头鹰 110"
            quote_match = re.search(r'=\s*(.*)$', result_item)
            if quote_match:
                quote_info = quote_match.group(1).strip()
            
            # 检查是否缺货：=0 或 = 0 表示缺货
            is_out_of_stock = bool(re.search(r'=\s*0', result_item))
            
            result_details.append({
                'item': result_item,
                'part_name': part_name,
                'oe_code': oe_code,
                'quote_info': quote_info,
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
    print("保存为 解释后的数据.json...")
    # 使用项目根目录下的 demo 文件夹（相对于当前脚本位置向上3层）
    demo_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'demo')
    os.makedirs(demo_dir, exist_ok=True)
    output_path = os.path.join(demo_dir, '解释后的数据.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(paged_result['result'], f, ensure_ascii=False, indent=4)
    print(f"文件已保存到: {output_path}")
    
    print("\n" + "="*70)
    print("完成!")
    print("="*70)


if __name__ == '__main__':
    main()
