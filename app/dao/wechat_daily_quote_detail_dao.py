# -*- coding:utf-8 -*-
# @Time    : 2026/7/3
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wechat_daily_quote_detail_dao.py
# @Software: PyCharm

"""
微信日报报价详情数据访问层
负责处理 wechat_daily_quote_detail 表与 crmapp_sales_history_detail 表的连接查询
使用 SQLAlchemy ORM 方式执行查询
"""

from typing import List, Dict, Optional
from sqlalchemy import func
from sqlalchemy.dialects.mysql import insert
from app.models.orm_models.wechat_daily_quote_detail import WechatDailyQuoteDetail
from app.models.orm_models.crmapp_sales_history_detail import CrmappSalesHistoryDetail


class WechatDailyQuoteDetailDao:
    """
    微信日报报价详情数据访问类
    """

    @staticmethod
    def fetch_data_paged(session, start_date=None, end_date=None, groupname=None, nickname=None, deal_status=None, page=1, limit=20):
        """
        从数据库获取微信日报报价详情数据（使用SQLAlchemy ORM，带分页信息）

        Args:
            session: 数据库会话
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
        id_query = session.query(WechatDailyQuoteDetail.weixin_decoding_result_id).distinct()

        if start_date:
            id_query = id_query.filter(WechatDailyQuoteDetail.create_date >= f'{start_date} 00:00:00')
        if end_date:
            id_query = id_query.filter(WechatDailyQuoteDetail.create_date <= f'{end_date} 23:59:59')
        if groupname:
            id_query = id_query.filter(WechatDailyQuoteDetail.group_name == groupname)
        if nickname:
            id_query = id_query.filter(WechatDailyQuoteDetail.user_name.like(f'%{nickname}%'))
        if deal_status is not None:
            id_query = id_query.filter(WechatDailyQuoteDetail.deal_status == deal_status)

        id_query = id_query.order_by(WechatDailyQuoteDetail.weixin_decoding_result_id.desc())

        total = id_query.count()

        id_list = []
        if page and limit:
            offset = (page - 1) * limit
            id_list = [row[0] for row in id_query.offset(offset).limit(limit).all()]
        else:
            id_list = [row[0] for row in id_query.all()]

        if not id_list:
            items = []
        else:
            query = session.query(WechatDailyQuoteDetail).filter(
                WechatDailyQuoteDetail.weixin_decoding_result_id.in_(id_list)
            )
            if deal_status is not None:
                query = query.filter(WechatDailyQuoteDetail.deal_status == deal_status)
            query = query.order_by(
                WechatDailyQuoteDetail.weixin_decoding_result_id.desc(),
                WechatDailyQuoteDetail.quote_number.asc()
            )
            items = query.all()

        result_list = []
        for item in items:
            record = item.to_dict()
            record['rowId'] = str(record['weixin_decoding_result_id']) if record['weixin_decoding_result_id'] else ''
            result_list.append(record)

        return {
            'result': result_list,
            'total': total,
            'page': page or 1,
            'limit': limit or 20
        }

    @staticmethod
    def fetch_backfill_candidates(session, start_date=None, end_date=None,weixin_decoding_result_id=None):
        """
        获取待回填成交信息的报价详情记录
        
        :param session: 数据库会话
        :param weixin_decoding_result_id: 微信解码结果ID（可选，为空则处理所有未成交记录）
        :param start_date: 开始日期 (YYYY-MM-DD)，可选
        :param end_date: 结束日期 (YYYY-MM-DD)，可选
        :return: 待回填记录列表
        """
        query = session.query(WechatDailyQuoteDetail).filter(
            WechatDailyQuoteDetail.inquiry_customer.isnot(None),
            WechatDailyQuoteDetail.inquiry_customer != '',
            WechatDailyQuoteDetail.oe_code.isnot(None),
            WechatDailyQuoteDetail.oe_code != '',
            WechatDailyQuoteDetail.deal_status == 0
        )
        
        if weixin_decoding_result_id:
            query = query.filter(WechatDailyQuoteDetail.weixin_decoding_result_id == weixin_decoding_result_id)
        
       
        if start_date:
            query = query.filter(WechatDailyQuoteDetail.create_date >= f'{start_date} 00:00:00')
        
        if end_date:
            query = query.filter(WechatDailyQuoteDetail.create_date <= f'{end_date} 23:59:59')
        
        return query.all()

    @staticmethod
    def fetch_sales_info(session, inquiry_customer, oe_code, create_date=None):
        """
        根据询价客户、OE码、日期查询销售记录
        
        :param session: 数据库会话
        :param inquiry_customer: 询价客户名称
        :param oe_code: OE码
        :param create_date: 创建日期（可选）
        :return: 销售信息字典 {'deal_amount', 'deal_brand', 'fullname'} 或 None
        """
        inquiry_customer = inquiry_customer.strip()
        oe_code = oe_code.strip()
        
        sales_query = session.query(
            CrmappSalesHistoryDetail.total_price,
            CrmappSalesHistoryDetail.brand_name,
            CrmappSalesHistoryDetail.fullname
        ).filter(
            CrmappSalesHistoryDetail.fullname.like(f'%{inquiry_customer}%'),
            CrmappSalesHistoryDetail.number == oe_code
        )
        
        if create_date:
            create_date_str = str(create_date).strip()
            if len(create_date_str) >= 10:
                date_part = create_date_str[:10]
                sales_query = sales_query.filter(
                    CrmappSalesHistoryDetail.create_date >= f'{date_part} 00:00:00',
                    CrmappSalesHistoryDetail.create_date <= f'{date_part} 23:59:59'
                )
        
        results = sales_query.all()
        
        if not results:
            return None
        
        total_amount = sum(r.total_price or 0 for r in results)
        brand_names = ', '.join(set(r.brand_name for r in results if r.brand_name))
        fullnames = ', '.join(set(r.fullname for r in results if r.fullname))
        
        return {
            'deal_amount': total_amount,
            'deal_brand': brand_names,
            'fullname': fullnames
        }

    @staticmethod
    def bulk_upsert(session, data_list):
        """
        批量插入或更新数据（以 id 为唯一索引）
        
        使用 SQLAlchemy 的 insert ... on_duplicate_key_update 方法
        底层调用 MySQL 的 INSERT ... ON DUPLICATE KEY UPDATE
        一次插入多条数据，性能更优

        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :return: 处理的记录数
        """
        if not data_list:
            return 0

        stmt = insert(WechatDailyQuoteDetail).values(data_list)

        update_dict = {}
        for column in WechatDailyQuoteDetail.__table__.columns:
            col_name = column.name
            if col_name not in ['id', 'created_at', 'deal_customer_id', 'deal_customer', 'deal_brand', 'deal_amount', 'deal_status', 'inquiry_customer_id', 'inquiry_customer']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)

        stmt = stmt.on_duplicate_key_update(update_dict)

        session.execute(stmt)
        
        return len(data_list)

    @staticmethod
    def update_deal_info(session, records, sales_info_map):
        """
        更新报价详情的成交信息
        
        :param session: 数据库会话
        :param records: 待更新的记录列表
        :param sales_info_map: 销售信息映射字典，key为(inquiry_customer, oe_code, create_date)
        :return: 更新的记录数
        """
        updated_count = 0
        
        for record in records:
            inquiry_customer = record.inquiry_customer.strip()
            key = (inquiry_customer, record.oe_code.strip(), record.create_date)
            sales_info = sales_info_map.get(key)
            
            if sales_info:
                record.deal_customer = sales_info['fullname']
                record.deal_brand = sales_info['deal_brand']
                record.deal_amount = sales_info['deal_amount']
                record.deal_status = 1
                updated_count += 1
        
        return updated_count
