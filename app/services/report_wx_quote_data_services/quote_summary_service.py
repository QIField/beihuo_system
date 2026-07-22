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
from .get_permission import get_user_group_permissions








def summarize_oe_codes_daily(start_date=None, end_date=None, groupname=None, page=1, limit=20, user_id=None):
    """
    按 groupname、oe_code 分组统计 oe 码的询价次数、缺货次数和成交次数（日统计）
    先按日期筛选明细，再分组统计，最后按群名称过滤分组结果
    
    Args:
        start_date: 开始日期字符串，如 "2026-02-21"
        end_date: 结束日期字符串，如 "2026-02-21"
        groupname: 群名称，可选（分组后过滤）；为 None 表示全部，会根据用户权限过滤
        page: 页码
        limit: 每页条数
        user_id: 用户ID，用于权限过滤，可选
        
    Returns:
        统计结果列表（带分页信息）
    """
    filtered_groupname = groupname  # 初始化过滤用的群名，默认等于传入的 groupname
    if groupname is None and user_id is not None:  # 选择了全部群且传入了用户ID时，按用户权限过滤
        user_perms = get_user_group_permissions(user_id)  # 获取用户拥有的群权限列表
        has_view_all = any(p['permission_code'] == 'wx_group:view_group_all' for p in user_perms)  # 检查是否有查看全部群的权限
        if not has_view_all:  # 没有全部权限时，用用户有权限的群列表过滤
            filtered_groupname = [p['group_name'] for p in user_perms if p['group_name']]  # 提取用户有权限的群名列表
            if not filtered_groupname:  # 用户一个群权限都没有
                return {'result': [], 'total': 0, 'page': page, 'limit': limit}  # 直接返回空结果

    with orm_session() as session:
        subquery = session.query(
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
        
        if start_date:
            subquery = subquery.filter(WechatDailyQuoteDetail.create_date >= f'{start_date} 00:00:00')
        if end_date:
            subquery = subquery.filter(WechatDailyQuoteDetail.create_date <= f'{end_date} 23:59:59')
        
        subquery = subquery.group_by(
            WechatDailyQuoteDetail.group_name,
            WechatDailyQuoteDetail.oe_code
        ).subquery()
        
        query = session.query(subquery)
        
        if filtered_groupname:
            if isinstance(filtered_groupname, list):
                query = query.filter(subquery.c.groupname.in_(filtered_groupname))
            else:
                query = query.filter(subquery.c.groupname == filtered_groupname)
        
        query = query.order_by(
            subquery.c.groupname,
            subquery.c.oe_code
        )
        
        total_query = session.query(func.count(subquery.c.oe_code))
        if filtered_groupname:
            if isinstance(filtered_groupname, list):
                total_query = total_query.filter(subquery.c.groupname.in_(filtered_groupname))
            else:
                total_query = total_query.filter(subquery.c.groupname == filtered_groupname)
        
        # 打印 SQL
        print("\n" + "="*100)
        print("查询 SQL:")
        print("="*100)
        print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))
        print("-"*100)
        print("COUNT SQL:")
        print("-"*100)
        print(str(total_query.statement.compile(compile_kwargs={"literal_binds": True})))
        print("="*100 + "\n")
        
        # 获取总数
        total = total_query.scalar()
        
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

def summarize_oe_codes_monthly(month_str, groupname=None, page=1, limit=20, user_id=None):
    """
    按 groupname、oe_code 分组统计 oe 码的询价次数、缺货次数和成交次数（月统计）
    将月份转换为该月的第一天和最后一天，调用日统计函数
    
    Args:
        month_str: 月份字符串，如 "2026-04"
        groupname: 群名称，可选
        page: 页码
        limit: 每页条数
        user_id: 用户ID，用于权限过滤，可选
        
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
        limit=limit,
        user_id=user_id
    )





# if __name__ == '__main__':
#     data = summarize_oe_codes_daily('2026-04-10', page=1, limit=20)
    
#     # print(data)
#     for item in data['result']:
#         print(item)
#         print("\n" + "="*100)