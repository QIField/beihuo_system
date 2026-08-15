# -*- coding:utf-8 -*-
"""
CRM 品牌别名池 ORM 模型
对应数据库表：crm_pp_alias_pool

设计说明：
- pool_id 相同的行属于同一别名池
- name 加唯一索引，保证一个名称只能属于一个池
- 不设主名/别名区分，池内所有名称查询时等价
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.models.orm_models.base_models import BaseModels


class CrmPpAliasPool(BaseModels):
    """
    CRM 品牌别名池成员表
    """

    __tablename__ = "crm_pp_alias_pool"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    pool_id = Column(Integer, nullable=False, comment="别名池编号")
    name = Column(String(255), nullable=False, unique=True, comment="池内品牌名称")
    created_at = Column(DateTime, nullable=True, default=func.now(), comment="创建时间")

    def to_dict(self):
        """
        将模型对象转换为字典
        """
        return {
            "id": self.id,
            "pool_id": self.pool_id,
            "name": self.name,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }

    @classmethod
    def list_to_dict_list(cls, items):
        """
        对象列表转字典列表
        """
        return [item.to_dict() for item in items]

    @classmethod
    def get_by_name(cls, session, name):
        """
        根据名称查询池成员
        """
        return session.query(cls).filter(cls.name == name).first()

    @classmethod
    def get_by_pool_id(cls, session, pool_id):
        """
        根据池 ID 查询所有成员
        """
        return session.query(cls).filter(cls.pool_id == pool_id).all()

    @classmethod
    def get_all_pools(cls, session):
        """
        获取所有别名池（按 pool_id 分组）
        返回: dict{pool_id: [CrmPpAliasPool, ...]}
        """
        rows = session.query(cls).all()
        grouped = {}
        for row in rows:
            grouped.setdefault(row.pool_id, []).append(row)
        return grouped

    @classmethod
    def delete_by_pool_id(cls, session, pool_id):
        """
        根据池 ID 删除所有成员
        """
        result = session.query(cls).filter(cls.pool_id == pool_id).delete(synchronize_session=False)
        return result

    @classmethod
    def create(cls, session, pool_id, name):
        """
        创建池成员
        """
        member = cls(pool_id=pool_id, name=name)
        session.add(member)
        session.flush()
        return member
