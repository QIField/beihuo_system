# -*- coding:utf-8 -*-
# @Time    : 2026/5/13 17:25
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wechat_daily_quote_detail_service.py
# @Software: PyCharm

import re
import traceback
from datetime import datetime, timedelta
from app.models.orm_models.wechat_daily_quote_detail import WechatDailyQuoteDetail
from app.models.orm_models.weixin_decoding_result import WeixinDecodingResult
from app.utils.orm.session import orm_session
from app.dao.wechat_daily_quote_detail_dao import WechatDailyQuoteDetailDao
from app.models.orm_models.crmapp_sales_history_detail import CrmappSalesHistoryDetail
from .weixin_decoding_result_clear import fetch_data_and_save_to_database


def fetch_data_paged(start_date=None, end_date=None, groupname=None, nickname=None, deal_status=None, page=1, limit=20):
    """
    从数据库获取微信日报报价详情数据（使用原生SQL，带分页信息）
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        groupname: 群名称，可选
        nickname: 业务员，可选
        deal_status: 成交状态，可选 (0-未知, 1-成交, 2-未成交)
        page: 页码，从1开始
        limit: 每页条数
        
    Returns:
        包含分页信息的字典 {'result': [...], 'total': ..., 'page': ..., 'limit': ...}
    """
    with orm_session() as session:
        result = WechatDailyQuoteDetailDao.fetch_data_paged(
            session=session,
            start_date=start_date,
            end_date=end_date,
            groupname=groupname,
            nickname=nickname,
            deal_status=deal_status,
            page=page,
            limit=limit
        )

    expanded_result = []
    for record in result['result']:
        brand_price = record.get('brand_price', '')
        if not brand_price:
            record['brand'] = ''
            record['price'] = ''
            expanded_result.append(record)
            continue
        
        pairs = re.split(r'\s*/\s*', brand_price)
        for i, pair in enumerate(pairs):
            pair = pair.strip()
            if not pair:
                continue
            parts = pair.rsplit(' ', 1)
            if len(parts) == 2:
                brand = parts[0].strip()
                price = parts[1].strip()
            else:
                brand = pair.strip()
                price = ''
            
            new_record = record.copy()
            new_record['brand'] = brand
            new_record['price'] = price
            # new_record['rowId'] = f"{record['rowId']}_{i}" if i > 0 else record['rowId']
            expanded_result.append(new_record)

    result['result'] = expanded_result
    
    return result






def fetch_groupname_list():
    """
    获取所有群名称列表（去重）
    
    Returns:
        群名称列表
    """
    try:
        with orm_session() as session:
            # 构建查询条件
            query = session.query(
                CrmappSalesHistoryDetail.fullname,
                CrmappSalesHistoryDetail.total_price,
                CrmappSalesHistoryDetail.brand_name
            ).filter(
                CrmappSalesHistoryDetail.fullname.isnot(None),
                CrmappSalesHistoryDetail.fullname != ''
            )
            
            # 添加 OE 码条件
            
            # 去掉OE码前面的字母，只保留数字部分
            # 例如: "A12345" → "12345"
                
            oe_code_clean = re.sub(r'^[a-zA-Z]+', '', oe_code)  # pyright: ignore[reportArgumentType, reportCallIssue]
            if oe_code_clean:
                query = query.filter(
                    CrmappSalesHistoryDetail.number == oe_code_clean
                )
            
            # 添加日期条件
            try:
                # 提取日期部分（只取 yyyy-mm-dd）
                # 支持格式：2026-04-09 18:19:08 或 2026-04-09
                date_part = None
                if ' ' in create_date:  # pyright: ignore[reportOperatorIssue]
                    date_part = create_date.split(' ')[0]  # pyright: ignore[reportOptionalMemberAccess]
                elif 'T' in create_date:  # pyright: ignore[reportOperatorIssue]
                    date_part = create_date.split('T')[0]  # pyright: ignore[reportOptionalMemberAccess]
                else:
                    date_part = create_date
                
                # 确保日期格式正确（只保留前10个字符）
                if date_part and len(date_part) >= 10:
                    date_part = date_part[:10]
                
                if date_part:
                    # 例如 date_part='2026-01-05' → 匹配 >= '2026-01-05 00:00:00' and <= '2026-01-05 23:59:59'
                    query = query.filter(
                        CrmappSalesHistoryDetail.create_date >= f'{date_part} 00:00:00',
                        CrmappSalesHistoryDetail.create_date <= f'{date_part} 23:59:59'
                    )
            except Exception as e:
                print(f"处理日期条件时出错: {str(e)}")
                pass
            
            # 执行查询
            results = query.all()
            
            # 转换为需要的格式
            customer_list = []
            for i, row in enumerate(results, 1):
                if row[0]:
                    customer_list.append({
                        'id': i,
                        'fullname': row[0],
                        'total_price': float(row[1]) if row[1] is not None else None,
                        'brand_name': row[2]
                    })
            
            return customer_list
            
    except Exception as e:
        print(f"获取客户列表失败: {str(e)}")
        traceback.print_exc()
        return []


def update_deal_info(quote_number, weixin_decoding_result_id, deal_status=None, deal_customer=None, deal_brand=None, deal_amount=None):
    """
    更新成交信息
    
    Args:
        quote_number: 报价序号
        weixin_decoding_result_id: 微信解码结果表ID
        deal_status: 成交状态：0-未知，1-成交，2-未成交
        deal_customer: 成交客户
        deal_brand: 成交品牌
        deal_amount: 成交金额
        
    Returns:
        是否成功
    """
    try:
        with orm_session() as session:
            # 根据quote_number和weixin_decoding_result_id查找记录
            record = session.query(WechatDailyQuoteDetail).filter_by(
                quote_number=quote_number,
                weixin_decoding_result_id=weixin_decoding_result_id
            ).first()
            if not record:
                print(f"未找到quote_number为 {quote_number}, weixin_decoding_result_id为 {weixin_decoding_result_id} 的记录")
                return False
            
            # 更新字段
            if deal_status is not None:
                record.deal_status = deal_status
            if deal_customer is not None:
                record.deal_customer = deal_customer
            if deal_brand is not None:
                record.deal_brand = deal_brand
            if deal_amount is not None:
                record.deal_amount = deal_amount
            
            session.commit()
            return True
            
    except Exception as e:
        print(f"更新成交信息失败: {str(e)}")
        traceback.print_exc()
        return False

# 数据批量回填成交信息 - 处理单个日期
def process_single_day(day_date):
    """
    处理单个日期的成交信息回填
    
    Args:
        day_date: 日期字符串，格式 'YYYY-MM-DD'
        
    Returns:
        dict: 当天的处理统计信息
    """
    # 当天的统计信息
    day_stats = {
        'total': 0,           # 总处理记录数
        'updated': 0,         # 成功更新记录数（成交）
        'not_found': 0,       # 未找到匹配记录数
        'multi_found': 0,     # 匹配到多条记录数
        'no_oe_code': 0,      # 没有 OE 码的记录数
        'failed': 0           # 失败记录数
    }
    
    try:
        print(f"处理日期：{day_date}")
        
        with orm_session() as session:
            # 查询当天 deal_status=0 的记录
            records = session.query(WechatDailyQuoteDetail).filter(
                WechatDailyQuoteDetail.create_date >= f'{day_date} 00:00:00',
                WechatDailyQuoteDetail.create_date <= f'{day_date} 23:59:59',
                WechatDailyQuoteDetail.deal_status == 0
            ).all()
            
            if not records:
                print(f"  日期 {day_date} 没有需要处理的记录")
                return day_stats
            
            day_stats['total'] = len(records)
            print(f"  找到 {len(records)} 条记录")
            
            # 逐个处理记录
            for record in records:
                try:
                    # 如果是缺货，直接标记为未成交
                    if record.is_out_of_stock:  # pyright: ignore[reportGeneralTypeIssues]
                        record.deal_status = 2  # pyright: ignore[reportAttributeAccessIssue]
                        day_stats['not_found'] += 1
                        continue
                    
                    # 检查 OE 码
                    if not record.oe_code:  # pyright: ignore[reportGeneralTypeIssues]
                        day_stats['no_oe_code'] += 1
                        continue
                    
                    # 清理 OE 码（去掉前面的字母）
                    oe_code_clean = re.sub(r'^[a-zA-Z]+', '', record.oe_code)  # pyright: ignore[reportCallIssue, reportArgumentType]
                    if not oe_code_clean:
                        day_stats['no_oe_code'] += 1
                        continue
                    
                    # 按日期和 OE 一起查询
                    sales_records = session.query(CrmappSalesHistoryDetail).filter(
                        CrmappSalesHistoryDetail.number == oe_code_clean,
                        CrmappSalesHistoryDetail.create_date >= f'{day_date} 00:00:00',
                        CrmappSalesHistoryDetail.create_date <= f'{day_date} 23:59:59',
                        CrmappSalesHistoryDetail.fullname.isnot(None),
                        CrmappSalesHistoryDetail.fullname != ''
                    ).all()
                    
                    # 只有找到的数据条数为 1 时才回填
                    if len(sales_records) == 1:
                        sales_record = sales_records[0]
                        # 找到匹配，标记为成交
                        record.deal_status = 1  # pyright: ignore[reportAttributeAccessIssue]
                        record.deal_customer = sales_record.fullname
                        record.deal_brand = sales_record.brand_name
                        record.deal_amount = sales_record.total_price
                        day_stats['updated'] += 1
                    elif len(sales_records) == 0:
                        # 没找到匹配，标记为未成交
                        record.deal_status = 2  # pyright: ignore[reportAttributeAccessIssue]
                        day_stats['not_found'] += 1
                    else:
                        # 找到多条匹配，保持状态不变
                        day_stats['multi_found'] += 1
                        
                except Exception as e:
                    print(f"  处理记录失败：{str(e)}")
                    day_stats['failed'] += 1
            
            # 提交当天的更新
            session.commit()
            print(f"  日期 {day_date} 处理完成：更新 {day_stats['updated']}，未找到 {day_stats['not_found']}，多条匹配 {day_stats['multi_found']}，无OE码 {day_stats['no_oe_code']}，失败 {day_stats['failed']}")
        
        return day_stats
        
    except Exception as e:
        print(f"处理日期 {day_date} 失败：{str(e)}")
        traceback.print_exc()
        return day_stats


# 数据批量回填成交信息 - 处理日期范围
def batch_get_update_deal_info(start_date, end_date):
    """
    批量从 crmapp_sales_history_detail 表获取数据并更新数据库中的成交信息
    
    Args:
        start_date: 开始日期，字符串格式，如 '2026-01-04'
        end_date: 结束日期，字符串格式，如 '2026-01-10'
        
    Returns:
        dict: 包含处理统计信息的字典
    """
    # 总统计信息
    total_stats = {
        'total': 0,           # 总处理记录数
        'updated': 0,         # 成功更新记录数（成交）
        'not_found': 0,       # 未找到匹配记录数
        'multi_found': 0,     # 匹配到多条记录数
        'no_oe_code': 0,      # 没有 OE 码的记录数
        'failed': 0           # 失败记录数
    }
    
    try:
        # 获取需要处理的日期范围
        
        # 解析日期
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # 生成日期列表（支持同一天的情况）
        date_list = []
        current_dt = start_dt
        while current_dt <= end_dt:
            date_list.append(current_dt.strftime('%Y-%m-%d'))
            current_dt += timedelta(days=1)
        
        if not date_list:
            print("没有需要处理的日期")
            return total_stats
        
        print(f"开始处理，共 {len(date_list)} 天")
        
        # 按天循环调用处理单个日期的函数
        for day_date in date_list:
            day_stats = process_single_day(day_date)
            
            # 累加统计信息
            total_stats['total'] += day_stats['total']
            total_stats['updated'] += day_stats['updated']
            total_stats['not_found'] += day_stats['not_found']
            total_stats['multi_found'] += day_stats['multi_found']
            total_stats['no_oe_code'] += day_stats['no_oe_code']
            total_stats['failed'] += day_stats['failed']
        
        print(f"\n批量处理完成！统计：总 {total_stats['total']}，更新 {total_stats['updated']}，未找到匹配 {total_stats['not_found']}，多条匹配 {total_stats['multi_found']}，无OE码 {total_stats['no_oe_code']}，失败 {total_stats['failed']}")
        return total_stats
        
    except Exception as e:
        print(f"批量处理失败：{str(e)}")
        traceback.print_exc()
        return total_stats


# def test_batch_get_update_deal_info():
#     """
#     测试批量更新成交信息函数
#     """
#     # 测试批量更新成交信息函数
#     batch_get_update_deal_info("2026-01-05", "2026-01-15")


# if __name__ == '__main__':
#     batch_get_update_deal_info("2026-01-01", "2026-01-21")
