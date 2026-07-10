# -*- coding:utf-8 -*-
# @Time    : 2026/5/13
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wechat_daily_quote_detail.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, DECIMAL, UniqueConstraint, Boolean

from .base_models import BaseModels


class WechatDailyQuoteDetail(BaseModels):
    """
    微信日报报价详情表 ORM 模型
    
    对应数据库表：wechat_daily_quote_detail
    """
    
    __tablename__ = "wechat_daily_quote_detail"
    __table_args__ = (
        UniqueConstraint('quote_number', 'weixin_decoding_result_id', name='uk_quote_result'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_general_ci'},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    weixin_decoding_result_id = Column(Integer, nullable=True, comment="微信解码结果表ID")
    quote_number = Column(Integer, nullable=True, comment="报价序号")
    create_date = Column(String(50), nullable=True, comment="创建日期")
    group_name = Column(String(255), nullable=True, comment="群名称")
    user_name = Column(String(255), nullable=True, comment="用户")
    inquiry_customer_id = Column(Integer, nullable=True, comment="询价客户ID")
    inquiry_customer = Column(String(255), nullable=True, comment="询价客户")
    inquiry = Column(Text, nullable=True, comment="询价")
    part_name = Column(String(255), nullable=True, comment="配件名称")
    oe_code = Column(String(255), nullable=True, comment="OE码")
    brand_price = Column(Text, nullable=True, comment="品牌价格")
    original_quote = Column(Text, nullable=True, comment="原始报价")
    is_out_of_stock = Column(Boolean, nullable=True, comment="缺货（true/false）")
    draft_link = Column(Text, nullable=True, comment="草稿链接")
    deal_customer_id = Column(Integer, nullable=True, comment="成交客户ID")
    deal_customer = Column(String(255), nullable=True, comment="成交客户")
    deal_brand = Column(String(255), nullable=True, comment="成交品牌")
    deal_amount = Column(DECIMAL(10, 2), nullable=True, comment="成交金额")
    deal_status = Column(Integer, nullable=True, default=0, comment="成交状态：0-未知，1-成交，2-未成交")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

  

    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<WechatDailyQuoteDetail id={self.id} group_name={self.group_name}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "id": self.id,
            "weixin_decoding_result_id": self.weixin_decoding_result_id,
            "quote_number": self.quote_number,
            "create_date": self.create_date,
            "group_name": self.group_name,
            "user_name": self.user_name,
            "inquiry_customer_id": self.inquiry_customer_id,
            "inquiry_customer": self.inquiry_customer,
            "inquiry": self.inquiry,
            "part_name": self.part_name,
            "oe_code": self.oe_code,
            "brand_price": self.brand_price,
            "original_quote": self.original_quote,
            "is_out_of_stock": self.is_out_of_stock,
            "draft_link": self.draft_link,
            "deal_customer_id": self.deal_customer_id,
            "deal_brand": self.deal_brand,
            "deal_amount": float(self.deal_amount) if self.deal_amount else None,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
            "deal_status": self.deal_status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }