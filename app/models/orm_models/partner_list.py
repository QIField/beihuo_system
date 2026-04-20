# -*- coding:utf-8 -*-
# @Time    : 2026/4/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : partner_list.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels
from app.utils.orm.type_decorators import StringToIntType


class PartnerList(BaseModels):
    """
    合作伙伴表 ORM 模型
    
    对应数据库表：partner
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

    @classmethod
    def get_by_partner_id(cls, session, partner_id):
        """
        根据 partner_id 获取合作伙伴
        
        :param session: SQLAlchemy Session 对象
        :param partner_id: 合作伙伴 ID
        :return: Partner 对象或 None
        """
        return session.query(cls).filter_by(partner_id=partner_id).first()

    @classmethod
    def get_by_sap_no(cls, session, sap_no):
        """
        根据 sap_no 获取合作伙伴
        
        :param session: SQLAlchemy Session 对象
        :param sap_no: SAP编号
        :return: Partner 对象或 None
        """
        return session.query(cls).filter_by(sap_no=sap_no).first()

    @classmethod
    def get_by_fullname(cls, session, fullname):
        """
        根据 fullname 获取合作伙伴列表
        
        :param session: SQLAlchemy Session 对象
        :param fullname: 全名
        :return: Partner 对象列表
        """
        return session.query(cls).filter_by(fullname=fullname).all()

    @classmethod
    def bulk_insert(cls, session, data_list):
        """
        批量插入数据
        
        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :return: 插入的记录数
        """
        if not data_list:
            return 0
        
        objects = [cls(**data) for data in data_list]
        session.bulk_save_objects(objects)
        return len(objects)

    @classmethod
    def bulk_upsert(cls, session, data_list):
        """
        批量插入或更新数据（以 partner_id 为唯一索引）
        
        使用 SQLAlchemy 的 insert ... on_duplicate_key_update 方法
        底层调用 MySQL 的 INSERT ... ON DUPLICATE KEY UPDATE
        一次插入多条数据，性能更优

        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :return: 处理的记录数
        """
        if not data_list:
            return 0

        # 构建插入语句
        stmt = insert(cls).values(data_list)

        # 构建更新字典：排除不需要更新的列
        update_dict = {}
        for column in cls.__table__.columns:
            col_name = column.name
            if col_name not in ['partner_id', 'created_at']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)

        # 使用 on_duplicate_key_update
        stmt = stmt.on_duplicate_key_update(update_dict)

        # 执行批量插入
        session.execute(stmt)
        
        return len(data_list)

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
