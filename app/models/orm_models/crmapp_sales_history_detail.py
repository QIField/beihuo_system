# -*- coding:utf-8 -*-
# @Time    : 2026/5/15
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crmapp_sales_history_detail.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, DECIMAL, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels


class CrmappSalesHistoryDetail(BaseModels):
    """
    销量明细表 ORM 模型
    
    对应数据库表：crmapp_sales_history_detail
    """
    
    __tablename__ = "crmapp_sales_history_detail"
    __table_args__ = (
        UniqueConstraint('ddno', 'frey_no', 'company', name='uk_ddno_frey_company'),
        Index('idx_create_date', 'create_date'),
        Index('idx_ddno', 'ddno'),
        Index('idx_number_brand', 'number', 'brand_name'),
        Index('idx_company_date', 'company', 'create_date'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    ddno = Column(String(50), nullable=False, comment="订单号")
    create_date = Column(DateTime, nullable=False, comment="创建时间")
    fullname = Column(String(100), nullable=True, default='', comment="客户全称")
    pdname = Column(String(200), nullable=True, default='', comment="产品名称")
    brand_name = Column(String(50), nullable=True, default='', comment="品牌名称")
    l_model_zh = Column(Text, nullable=True, comment="车型")
    frey_no = Column(String(200), nullable=True, default='', comment="Frey编号")
    number = Column(String(200), nullable=True, default='', comment="OE号")
    quantity = Column(Integer, nullable=True, default=0, comment="销售数量")
    sfqty = Column(Integer, nullable=True, default=0, comment="实发数量")
    price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="单价")
    total_price = Column(DECIMAL(12, 2), nullable=True, default=0.00, comment="总价")
    sfje = Column(DECIMAL(12, 2), nullable=True, default=0.00, comment="实发金额")
    remark = Column(Text, nullable=True, comment="备注")
    warehouse = Column(String(50), nullable=True, default='', comment="仓库")
    return_policy = Column(String(50), nullable=True, default='', comment="退货政策")
    company = Column(String(20), nullable=True, default='fsbbr', comment="公司")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="记录创建时间")
    updated_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    @classmethod
    def get_by_id(cls, session, id):
        """
        根据 ID 获取记录
        
        :param session: SQLAlchemy Session 对象
        :param id: 主键ID
        :return: CrmappSalesHistoryDetail 对象或 None
        """
        return session.query(cls).filter_by(id=id).first()

    @classmethod
    def get_by_ddno(cls, session, ddno):
        """
        根据 订单号 获取记录列表
        
        :param session: SQLAlchemy Session 对象
        :param ddno: 订单号
        :return: CrmappSalesHistoryDetail 对象列表
        """
        return session.query(cls).filter_by(ddno=ddno).all()

    @classmethod
    def get_by_company(cls, session, company):
        """
        根据 公司 获取记录列表
        
        :param session: SQLAlchemy Session 对象
        :param company: 公司
        :return: CrmappSalesHistoryDetail 对象列表
        """
        return session.query(cls).filter_by(company=company).all()

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
        批量插入或更新数据（以 ddno, frey_no, company 为唯一索引）
        
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
            if col_name not in ['id', 'created_at']:
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
        return f"<CrmappSalesHistoryDetail id={self.id} ddno={self.ddno}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            'id': self.id,
            'ddno': self.ddno,
            'create_date': self.create_date.strftime("%Y-%m-%d %H:%M:%S") if self.create_date else None,
            'fullname': self.fullname,
            'pdname': self.pdname,
            'brand_name': self.brand_name,
            'l_model_zh': self.l_model_zh,
            'frey_no': self.frey_no,
            'number': self.number,
            'quantity': self.quantity,
            'sfqty': self.sfqty,
            'price': float(self.price) if self.price else None,
            'total_price': float(self.total_price) if self.total_price else None,
            'sfje': float(self.sfje) if self.sfje else None,
            'remark': self.remark,
            'warehouse': self.warehouse,
            'return_policy': self.return_policy,
            'company': self.company,
            'created_at': self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            'updated_time': self.updated_time.strftime("%Y-%m-%d %H:%M:%S") if self.updated_time else None,
        }
