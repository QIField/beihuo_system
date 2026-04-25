# -*- coding:utf-8 -*-
# @Time    : 2026/4/24 08:59
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_quota_model.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Numeric, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels


class CustomerQuota(BaseModels):
    """
    客户额度表 ORM 模型
    
    对应数据库表：customer_quota
    用于管理客户的交易额度和授信额度
    """
    
    __tablename__ = "customer_quota"
    
    # 额度状态映射
    QUOTA_STATUS_MAPPING = {
        'normal': '正常',
        'frozen': '冻结',
        'restricted': '限制使用',
        'expired': '已过期'
    }
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID，自增，无业务含义")
    partner_id = Column(Integer, nullable=False, comment="合作伙伴ID，唯一键，关联partner_list.partner_id")
    remenber_code = Column(String(255), nullable=True, comment="客户编码，外键，关联partner_list.remenber_code")
    fullname = Column(String(255), nullable=True, comment="客户名称")
    max_trade_quota = Column(Numeric(16, 2), nullable=False, default=0.00, comment="客户交易额度（累计交易额上限）")
    credit_quota = Column(Numeric(16, 2), nullable=False, default=0.00, comment="客户授信总额度（最大可欠款额度）")
    quota_status = Column(String(20), nullable=False, default='normal', comment="额度状态：normal-正常，frozen-冻结，restricted-限制使用，expired-已过期")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="最后更新时间")
    remark = Column(Text, nullable=True, comment="备注（额度调整说明、风控记录）")
    operator = Column(String(50), nullable=True, comment="最后操作人（管理员姓名/ID）")
    is_deleted = Column(Integer, nullable=False, default=0, comment="软删除标记：0-正常，1-删除")
    
    # 唯一约束和索引
    __table_args__ = (
        UniqueConstraint('partner_id', name='uk_partner_id'),
        Index('idx_remenber_code', 'remenber_code'),
        Index('idx_quota_status', 'quota_status'),
        Index('idx_is_deleted', 'is_deleted'),
    )
    
    @classmethod
    def get_by_partner_id(cls, session, partner_id):
        """
        根据 partner_id 获取客户额度记录
        
        :param session: SQLAlchemy Session 对象
        :param partner_id: 合作伙伴 ID
        :return: CustomerQuota 对象或 None
        """
        return session.query(cls).filter_by(partner_id=partner_id, is_deleted=0).first()
    
    @classmethod
    def get_by_remenber_code(cls, session, remenber_code):
        """
        根据 remenber_code 获取客户额度记录
        
        :param session: SQLAlchemy Session 对象
        :param remenber_code: 客户编码
        :return: CustomerQuota 对象或 None
        """
        return session.query(cls).filter_by(remenber_code=remenber_code, is_deleted=0).first()
    
    @classmethod
    def get_paginated_list(cls, session, page=1, limit=20, fullname=None, quota_status=None):
        """
        分页查询客户额度列表
        
        :param session: SQLAlchemy Session 对象
        :param page: 页码
        :param limit: 每页条数
        :param fullname: 客户名称（可选，模糊查询）
        :param quota_status: 额度状态（可选）
        :return: (total: 总数, result: 数据列表)
        """
        # 构建查询
        query = session.query(cls).filter_by(is_deleted=0)
        
        # 添加查询条件
        if fullname:
            query = query.filter(cls.fullname.like(f"%{fullname}%"))
        
        if quota_status:
            query = query.filter_by(quota_status=quota_status)
        
        # 统计总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * limit
        items = query.order_by(cls.id.desc()).limit(limit).offset(offset).all()
        
        return total, items
    
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
            if col_name not in ['id', 'created_at', 'is_deleted']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)
        
        # 使用 on_duplicate_key_update
        stmt = stmt.on_duplicate_key_update(update_dict)
        
        # 执行批量插入
        session.execute(stmt)
        
        return len(data_list)
    
    @classmethod
    def list_to_dict_list(cls, obj_list):
        """
        将对象列表转换为字典列表
        
        支持两种输入类型：
        1. CustomerQuota 模型对象列表
        2. SQLAlchemy Row 对象列表（原生SQL查询结果）
        
        :param obj_list: CustomerQuota 对象列表 或 Row 对象列表
        :return: 字典列表
        """
        if not obj_list:
            return []
        
        result = []
        for obj in obj_list:
            if hasattr(obj, 'to_dict'):
                # 是模型对象，调用 to_dict 方法
                result.append(obj.to_dict())
            else:
                # 是 Row 对象，转换为字典并处理特殊类型
                try:
                    # 尝试使用 _asdict() 方法（适用于 SQLAlchemy 1.4+）
                    row_dict = obj._asdict()
                except AttributeError:
                    # 备用方法：手动构建字典
                    row_dict = {}
                    for key in obj.keys():
                        row_dict[key] = obj[key]
                # 处理 Numeric 类型，转换为 float
                for key, value in row_dict.items():
                    if hasattr(value, 'real') and hasattr(value, 'imag'):
                        # Decimal/Numeric 类型
                        row_dict[key] = float(value)
                result.append(row_dict)
        return result
    
    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<CustomerQuota id={self.id} partner_id={self.partner_id} quota_status={self.quota_status}>"
    
    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        Numeric 类型会转换为 float
        
        :return: 包含所有字段的字典
        """
        return {
            "id": self.id,
            "partner_id": self.partner_id,
            "remenber_code": self.remenber_code,
            "fullname": self.fullname,
            "max_trade_quota": float(self.max_trade_quota) if self.max_trade_quota else 0.00,
            "credit_quota": float(self.credit_quota) if self.credit_quota else 0.00,
            "quota_status": self.quota_status,
            "quota_status_desc": self.QUOTA_STATUS_MAPPING.get(self.quota_status, self.quota_status),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
            "remark": self.remark,
            "operator": self.operator,
            "is_deleted": self.is_deleted,
        }
    
    @classmethod
    def get_by_id(cls, session, id):
        """
        根据 id 获取客户额度记录
        
        :param session: SQLAlchemy Session 对象
        :param id: 主键 ID
        :return: CustomerQuota 对象或 None
        """
        return session.query(cls).filter_by(id=id, is_deleted=0).first()
    
    @classmethod
    def create(cls, session, data):
        """
        创建客户额度记录
        
        :param session: SQLAlchemy Session 对象
        :param data: 数据字典
        :return: CustomerQuota 对象
        """
        obj = cls(**data)
        session.add(obj)
        session.flush()
        return obj
    
    @classmethod
    def update(cls, session, id, data):
        """
        更新客户额度记录
        
        :param session: SQLAlchemy Session 对象
        :param id: 主键 ID
        :param data: 更新数据字典
        :return: CustomerQuota 对象或 None
        """
        obj = session.query(cls).filter_by(id=id, is_deleted=0).first()
        if obj:
            for key, value in data.items():
                if hasattr(obj, key) and key not in ['id', 'created_at']:
                    setattr(obj, key, value)
            session.flush()
        return obj
    
    @classmethod
    def delete(cls, session, id):
        """
        软删除客户额度记录
        
        :param session: SQLAlchemy Session 对象
        :param id: 主键 ID
        :return: 是否删除成功
        """
        obj = session.query(cls).filter_by(id=id, is_deleted=0).first()
        if obj:
            obj.is_deleted = 1
            session.flush()
            return True
        return False
