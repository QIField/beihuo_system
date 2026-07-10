# -*- coding:utf-8 -*-
# @Time    : 2026/7/2
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : weixin_decoding_result_clear.py
# @Software: PyCharm

import re
import traceback
from datetime import datetime, timedelta
from app.utils.orm.session import orm_session
from app.models.orm_models.weixin_decoding_result import WeixinDecodingResult
from app.models.orm_models.wechat_daily_quote_detail import WechatDailyQuoteDetail
from app.dao.wechat_daily_quote_detail_dao import WechatDailyQuoteDetailDao


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
    
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        items.append(line)
    
    return items


def convert_to_database_format(records):
    """
    将 weixin_decoding_result 字典列表转换为 wechat_daily_quote_detail 表格式
    
    Args:
        records: weixin_decoding_result 字典列表
        
    Returns:
        适合插入 wechat_daily_quote_detail 表的数据列表
    """
    database_data = []
    
    for record in records:
        source_id = record.get('id')
        
        result_text = record.get('result', '')
        result_array = parse_lines(result_text) if result_text else []
        
        should_skip_first = True
        content = record.get('content', '')
        if content:
            content_lines = parse_lines(content)
            if content_lines:
                first_content_line = content_lines[0].strip()
                
                if len(result_array) > 0 and result_array[0].strip() == first_content_line:
                    should_skip_first = True
                
                elif re.match(r'^[A-Za-z0-9]+$', first_content_line):
                    should_skip_first = False
        
        if should_skip_first and len(result_array) > 0:
            result_array = result_array[1:]
        
        for result_item in result_array:
            quote_number = None
            part_name = ''
            oe_code = ''
            brand_price = ''
            original_quote = result_item
            
            quote_num_match = re.match(r'^(\d+)[、.,]\s*', result_item)
            if quote_num_match:
                quote_number = int(quote_num_match.group(1))
            
            part_name_match = re.match(r'^(?:\d+[、.,])?\s*(.*?)(?=\s*\(|=|$)', result_item)
            if part_name_match:
                part_name = part_name_match.group(1).strip()
            
            oe_match = re.search(r'\(([A-Za-z0-9]+)\)', result_item)
            oe_code = oe_match.group(1) if oe_match else ''
            if oe_code == '0':
                oe_code = ''
            
            quote_match = re.search(r'=\s*(.*)$', result_item)
            if quote_match:
                brand_price = quote_match.group(1).strip()
            
            is_out_of_stock = bool(re.search(r'=\s*0', result_item))
            
            db_item = {
                'weixin_decoding_result_id': source_id,
                'quote_number': quote_number,
                'create_date': record.get('creation_date'),
                'group_name': record.get('groupname'),
                'user_name': record.get('nickname'),
                'inquiry': content,
                'part_name': part_name,
                'oe_code': oe_code,
                'brand_price': brand_price,
                'original_quote': original_quote,
                'is_out_of_stock': is_out_of_stock,
                'deal_customer_id': None,
                'deal_customer': None,
                'deal_brand': None,
                'deal_amount': None,
                'deal_status': 0
            }
            
            database_data.append(db_item)
    
    return database_data


def get_weixin_decoding_result(start_date=None, end_date=None):
    """
    从 weixin_decoding_result 表获取数据
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        
    Returns:
        weixin_decoding_result 字典列表
    """
    records = []
    
    with orm_session() as session:
        query = session.query(WeixinDecodingResult).filter(
            WeixinDecodingResult.result.isnot(None),
            WeixinDecodingResult.result != ''
        )
        
        if start_date:
            query = query.filter(WeixinDecodingResult.creation_date >= f'{start_date} 00:00:00')
        if end_date:
            query = query.filter(WeixinDecodingResult.creation_date <= f'{end_date} 23:59:59')
        
        query = query.order_by(WeixinDecodingResult.creation_date.desc())
        
        items = query.all()
        
        for item in items:
            records.append(item.to_dict())
    
    return records


def batch_save_to_database(data_list):
    """
    批量保存数据到 wechat_daily_quote_detail 表
    
    Args:
        data_list: 转换后的数据列表
        
    Returns:
        保存的记录数
    """
    if not data_list:
        return 0
    
    with orm_session() as session:
        result = WechatDailyQuoteDetailDao.bulk_upsert(session, data_list)
        session.commit()
        return result


def fetch_data_and_save_to_database(start_date, end_date):
    """
    微信解码结果数据批量ETL主函数
    
    将 weixin_decoding_result 表中的解码结果数据按10天为一批进行处理：
    1. 从源表获取数据
    2. 转换为 wechat_daily_quote_detail 表格式
    3. 批量保存到目标表
    4. 最后调用 backfill_deal_info 补充成交信息
    
    Args:
        start_date: 开始日期字符串，如 "2026-01-01"
        end_date: 结束日期字符串，如 "2026-04-20"
    """

    from app.services.report_wx_quote_data_services.wechat_daily_quote_detail_subsidiary import backfill_deal_info
    
    print("\n" + "="*70)
    print("开始批量获取并保存数据")
    print("="*70)
    print(f"日期范围: {start_date} 至 {end_date}")
    
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    total_records = 0
    
    current_start = start_dt
    
    batch_count = 0
    while current_start <= end_dt:
        batch_count += 1
        
        current_end = current_start + timedelta(days=9)
        if current_end > end_dt:
            current_end = end_dt
        
        batch_start_str = current_start.strftime('%Y-%m-%d')
        batch_end_str = current_end.strftime('%Y-%m-%d')
        
        print(f"\n[批次 {batch_count}] 处理日期: {batch_start_str} 至 {batch_end_str}")
        
        try:
            db_data_list = get_weixin_decoding_result(batch_start_str, batch_end_str)
            
            data_list = convert_to_database_format(db_data_list)
            
            if data_list:
                save_stats = batch_save_to_database(data_list)
                print(f"批次 {batch_count} 完成: 获取 {len(data_list)} 条记录，保存统计: {save_stats}")
                total_records += len(data_list)
            else:
                print(f"批次 {batch_count} 完成: 无数据")
        
        except Exception as e:
            print(f"  ✗ 批次 {batch_count} 处理失败: {str(e)}")
            traceback.print_exc()
        
        current_start = current_end + timedelta(days=1)
    
    print("\n" + "="*70)
    print(f"全部完成！总共处理 {total_records} 条记录")
    print("="*70)

    backfill_deal_info(start_date, end_date)
    print("\n" + "="*70)
    print("backfill_deal_info处理完成！")