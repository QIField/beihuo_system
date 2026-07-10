# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 08:58
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : quote_summary_service.py
# @Software: PyCharm

# import sys
# import os
import calendar
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from app.utils.orm.session import orm_session
from app.models.orm_models.wechat_daily_quote_detail import WechatDailyQuoteDetail
from sqlalchemy import func, Integer








def summarize_oe_codes_daily(start_date=None, end_date=None, groupname=None, nickname=None, page=1, limit=20):
    """
    按 groupname、oe_code、create_time（日期）分组统计 oe 码的询价次数、缺货次数和成交次数（日统计）
    直接用 SQL 从 wechat_daily_quote_detail 表进行 GROUP BY 查询
    
    Args:
        start_date: 开始日期字符串，如 "2026-02-21"
        end_date: 结束日期字符串，如 "2026-02-21"
        groupname: 群名称，可选
        nickname: 业务员，可选
        page: 页码
        limit: 每页条数
        
    Returns:
        统计结果列表（带分页信息）
    """
    with orm_session() as session:
        # 一次查询搞定：统计数据 + 取第一条记录的详情
        query = session.query(
            WechatDailyQuoteDetail.group_name.label('groupname'),
            WechatDailyQuoteDetail.oe_code,
            func.cast(func.count(WechatDailyQuoteDetail.id), Integer).label('inquiry_count'),
            func.cast(func.sum(func.cast(WechatDailyQuoteDetail.is_out_of_stock, Integer)), Integer).label('out_of_stock_count'),
            func.cast(func.sum(func.cast(
                WechatDailyQuoteDetail.deal_status == 1, 
                Integer
            )), Integer).label('deal_count'),
            func.min(WechatDailyQuoteDetail.create_date).label('create_date'),
            func.max(WechatDailyQuoteDetail.part_name).label('part_name'),
            func.max(WechatDailyQuoteDetail.brand_price).label('quote_info')
        ).filter(
            WechatDailyQuoteDetail.oe_code.isnot(None),
            WechatDailyQuoteDetail.oe_code != '',
            WechatDailyQuoteDetail.oe_code != '0'
        )
        
        # 添加筛选条件
        if start_date:
            # 例如 start_date='2026-01-05' → 匹配 >= '2026-01-05 00:00:00'
            query = query.filter(WechatDailyQuoteDetail.create_date >= f'{start_date} 00:00:00')
        if end_date:
            # 例如 end_date='2026-01-05' → 匹配 <= '2026-01-05 23:59:59'
            query = query.filter(WechatDailyQuoteDetail.create_date <= f'{end_date} 23:59:59')
        if groupname:
            query = query.filter(WechatDailyQuoteDetail.group_name == groupname)
        if nickname:
            query = query.filter(WechatDailyQuoteDetail.user_name.like(f'%{nickname}%'))
        
        # 分组
        query = query.group_by(
            WechatDailyQuoteDetail.group_name,
            WechatDailyQuoteDetail.oe_code
        ).order_by(
            WechatDailyQuoteDetail.group_name,
            WechatDailyQuoteDetail.oe_code
        )
        
        # 打印 SQL
        print("\n" + "="*100)
        # print("SQL 语句:")
        # print("="*100)
        # print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))
        print("="*100 + "\n")
        
        # 获取总数
        total = query.count()
        
        if total == 0:
            return {
                'result': [],
                'total': 0,
                'page': page,
                'limit': limit
            }
        
        # 分页
        start = (page - 1) * limit
        end = start + limit
        items = query.slice(start, end).all()

        
        
        
        # 直接转换成字典列表
        stats_list = [item._asdict() for item in items]
        
        return {
            'result': stats_list,
            'total': total
        }

def summarize_oe_codes_monthly(month_str, groupname=None, page=1, limit=20):
    """
    按 groupname、oe_code 分组统计 oe 码的询价次数、缺货次数和成交次数（月统计）
    将月份转换为该月的第一天和最后一天，调用日统计函数
    
    Args:
        month_str: 月份字符串，如 "2026-04"
        groupname: 群名称，可选
        page: 页码
        limit: 每页条数
        
    Returns:
        统计结果列表（带分页信息）
    """
    # 解析月份
    year, month = map(int, month_str.split('-'))
    
    # 获取该月的第一天
    start_date = f"{year}-{month:02d}-01"
    
    # 获取该月的最后一天
    _, last_day = calendar.monthrange(year, month)
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    
    # 调用日统计函数
    return summarize_oe_codes_daily(
        start_date=start_date,
        end_date=end_date,
        groupname=groupname,
        page=page,
        limit=limit
    )





# if __name__ == '__main__':
#     data = summarize_oe_codes_daily('2026-04-10', page=1, limit=20)
    
#     # print(data)
#     for item in data['result']:
#         print(item)
#         print("\n" + "="*100)