





from app.services.report_wx_quote_data_services.create_link import generate_link


def update_inquiry_customer(weixin_decoding_result_id, inquiry_customer_id, inquiry_customer):
    """
    更新询价客户信息
    只更新 inquiry_customer_id 和 inquiry_customer 字段
    根据 weixin_decoding_result_id 更新所有匹配的记录
    
    :param weixin_decoding_result_id: 微信解码结果ID
    :param inquiry_customer_id: 询价客户ID（来自CRM的partner_id）
    :param inquiry_customer: 询价客户名称
    :return: 更新的记录数
    """
    from app.models.orm_models.wechat_daily_quote_detail import WechatDailyQuoteDetail
    from app.utils.orm.session import orm_session
    records = []
    with orm_session() as session:
        records = session.query(WechatDailyQuoteDetail).filter(
            WechatDailyQuoteDetail.weixin_decoding_result_id == weixin_decoding_result_id
        ).all()
        
        for record in records:
            record.inquiry_customer_id = inquiry_customer_id
            record.inquiry_customer = inquiry_customer
        
        
    records = len(records)

    if records:
        backfill_deal_info(weixin_decoding_result_id)

    return records


def get_crm_customer(crm_customer_name):
    """
    获取CRM客户
    根据客户名称在 PartnerList（合作伙伴表）中进行模糊搜索
    只匹配 fullname（全名）
    
    :param crm_customer_name: 客户名称关键词
    :return: 匹配的客户列表，包含 partner_id、fullname、short_name 等字段
    """
    from app.models.orm_models.partner_list import PartnerList
    from app.utils.orm.session import orm_session
    
    if not crm_customer_name:
        return []
    
    with orm_session() as session:
        query = session.query(
            PartnerList.partner_id,
            PartnerList.fullname,
            PartnerList.short_name,
            PartnerList.contacts,
            PartnerList.contacts_phone
        ).filter(
            PartnerList.fullname.like(f"%{crm_customer_name}%")
        ).order_by(
            PartnerList.fullname
        ).limit(10).all()
        
        result = []
        for row in query:
            result.append({
                'partner_id': row.partner_id,
                'fullname': row.fullname,
                'short_name': row.short_name,
                'contacts': row.contacts,
                'contacts_phone': row.contacts_phone
            })
        
        return result


def backfill_deal_info( start_date=None, end_date=None,weixin_decoding_result_id=None):
    """
    回填成交客户、成交品牌、成交金额
    使用 inquiry_customer、oe_code、create_date 从 CrmappSalesHistoryDetail 搜索对应的数据
    
    :param weixin_decoding_result_id: 微信解码结果ID（可选，为空则处理所有未成交记录）
    :param start_date: 开始日期 (YYYY-MM-DD)，可选
    :param end_date: 结束日期 (YYYY-MM-DD)，可选
    :return: 回填的记录数
    """
    from app.dao.wechat_daily_quote_detail_dao import WechatDailyQuoteDetailDao
    from app.utils.orm.session import orm_session
    
    total_updated = 0
   
    with orm_session() as session:
        records = WechatDailyQuoteDetailDao.fetch_backfill_candidates(session, weixin_decoding_result_id, start_date, end_date)
        
        sales_info_map = {}
        for record in records:
            oe_code = record.oe_code[1:] if record.oe_code and record.oe_code.startswith('A') else record.oe_code
            
            sales_info = WechatDailyQuoteDetailDao.fetch_sales_info(
                session,
                record.inquiry_customer,
                oe_code,
                record.create_date
            )
            # print(record.inquiry_customer, record.oe_code, record.create_date, sales_info)
            # print(sales_info)
            if sales_info:
                inquiry_customer = record.inquiry_customer.strip()
                sales_info_map[(inquiry_customer, oe_code.strip(), record.create_date)] = sales_info
        
        total_updated = WechatDailyQuoteDetailDao.update_deal_info(session, records, sales_info_map)
        
        session.commit()
    
    return total_updated



def generate_draft_link(weixin_decoding_result_id, items, extra_items=None):
    """
    生成草稿链接
    
    :param weixin_decoding_result_id: 微信解码结果ID
    :param items: 选中的配件列表，每项包含 oe_code, brand, price, quantity, original_quote
    :param extra_items: 额外添加的配件列表，每项包含 product_id, quantity, price, oe_code
    :return: 生成的草稿链接字符串
    """
    from app.models.orm_models.wechat_daily_quote_detail import WechatDailyQuoteDetail
    from app.utils.orm.session import orm_session
    
    if not weixin_decoding_result_id:
        raise ValueError('weixin_decoding_result_id不能为空')
    
    if (not items or not isinstance(items, list)) and (not extra_items or not isinstance(extra_items, list)):
        raise ValueError('请选择至少一个配件')

    
   
    
    with orm_session() as session:
        records = session.query(WechatDailyQuoteDetail).filter(
            WechatDailyQuoteDetail.weixin_decoding_result_id == weixin_decoding_result_id
        ).all()
        
        if not records:
            raise ValueError('未找到对应的报价记录')
        if not records[0].inquiry_customer_id:  # pyright: ignore[reportGeneralTypeIssues]
            raise ValueError('未找到询价客户id')
        inquiry_customer_id = records[0].inquiry_customer_id

        
        link_code = generate_link(inquiry_customer_id, items, extra_items)
        
        # 临时占位：返回一个示例链接
        draft_link = f'https://crm.gzbbr.com/#/bills/generateOrderDetail?orders_id={link_code}'
        
        # 将草稿链接更新到所有相关记录
        for record in records:
            record.draft_link = draft_link  # pyright: ignore[reportAttributeAccessIssue]
        
        session.commit()
    
    return draft_link

