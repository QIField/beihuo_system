# -*- coding:utf-8 -*-
# @Time    : 2026/4/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : partner_list.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text

from app.models.orm_models.base_models import BaseModels
from app.utils.orm.type_decorators import StringToIntType


class PartnerList(BaseModels):
    """
    合作伙伴表 ORM 模型

    对应数据库表：partner_list

    数据访问方法统一收敛到 app/dao/crm/partner_list_dao.py
    """

    __tablename__ = "partner_list"

    # 定义客户等级映射（可根据实际业务需求补充）
    LEVEL_ID_MAPPING = {
        # 待补充实际的映射关系
        '开思':22,
        '缤汽库':105,
        '维修厂':27,
        '同行':25,
        '车主':20,
        '线上-途虎养车（汽配龙）':30,
        '线上-F6':28,
        '集群车宝':101,
        '天猫':26,
        '一级代理':102,
        '巴博瑞价格':103,
        '总代理':104,
        '前置仓':106,
        '地级市含税价':107,
        '维修厂大客户':109,
    }

    partner_id = Column(Integer, primary_key=True, nullable=False, comment="合作伙伴ID")
    contacts = Column(String(255), nullable=True, comment="联系人")
    contacts_phone = Column(String(20), nullable=True, comment="联系电话")
    country = Column(String(255), nullable=True, comment="国家")
    create_time = Column(Integer, nullable=True, comment="创建时间（秒级时间戳）")
    currency_name = Column(String(255), nullable=True, comment="货币名称")
    fullname = Column(String(255), nullable=True, comment="全名")
    is_disabled = Column(Integer, nullable=True, comment="是否禁用")
    language_types = Column(String(255), nullable=True, comment="语言类型")
    level_id = Column(StringToIntType(LEVEL_ID_MAPPING), nullable=True, comment="客户等级id")
    level_name = Column(String(255), nullable=True, comment="客户等级名称")
    orderTimes = Column(Integer, nullable=True, comment="订单统计（份）")
    payment_description = Column(Text, nullable=True, comment="付款说明")
    payment_method = Column(String(255), nullable=True, comment="付款方式")
    real_name = Column(String(255), nullable=True, comment="所属业务员")
    region = Column(String(255), nullable=True, comment="区域")
    remenber_code = Column(String(255), nullable=True, comment="记忆代码")
    sap_no = Column(String(255), nullable=True, comment="SAP编号")
    short_name = Column(String(255), nullable=True, comment="简称")
    street = Column(String(500), nullable=True, comment="街道")
    upload_sap = Column(String(255), nullable=True, comment="上传SAP")
    user_name = Column(String(255), nullable=True, comment="创建人")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<Partner partner_id={self.partner_id} fullname={self.fullname}>"

    def to_dict(self):
        """
        将模型对象转换为字典

        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串

        :return: 包含所有字段的字典
        """
        return {
            "partner_id": self.partner_id,
            "contacts": self.contacts,
            "contacts_phone": self.contacts_phone,
            "country": self.country,
            "create_time": self.create_time,
            "currency_name": self.currency_name,
            "fullname": self.fullname,
            "is_disabled": self.is_disabled,
            "language_types": self.language_types,
            "level_id": self.level_id,
            "orderTimes": self.orderTimes,
            "payment_description": self.payment_description,
            "payment_method": self.payment_method,
            "real_name": self.real_name,
            "region": self.region,
            "remenber_code": self.remenber_code,
            "sap_no": self.sap_no,
            "short_name": self.short_name,
            "street": self.street,
            "upload_sap": self.upload_sap,
            "user_name": self.user_name,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }