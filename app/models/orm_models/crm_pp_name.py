# -*- coding:utf-8 -*-
"""
CRM 零件品牌别名 ORM 模型
对应数据库表：crm_pp_name
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.models.orm_models.base_models import BaseModels


class CrmPpName(BaseModels):
    """
    CRM 零件品牌别名映射表
    """

    __tablename__ = "crm_pp_name"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    pp_name = Column(String(255), nullable=False, comment="品牌主名")
    alias_name = Column(String(255), nullable=False, comment="别名")
    created_at = Column(DateTime, nullable=True, default=func.now(), comment="创建时间")

    def to_dict(self):
        """
        将模型对象转换为字典
        """
        return {
            "id": self.id,
            "pp_name": self.pp_name,
            "alias_name": self.alias_name,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }

    @classmethod
    def list_to_dict_list(cls, items):
        """
        对象列表转字典列表
        """
        return [item.to_dict() for item in items]

    @classmethod
    def get_paged_aliases(cls, session, page=1, page_size=10, pp_name=None, alias_name=None):
        """
        分页查询别名列表
        """
        query = session.query(cls)

        if pp_name:
            query = query.filter(cls.pp_name.like(f"%{pp_name}%"))
        if alias_name:
            query = query.filter(cls.alias_name.like(f"%{alias_name}%"))

        total = query.count()
        items = (
            query.order_by(cls.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
            .all()
        )

        return total, items

    @classmethod
    def get_by_id(cls, session, alias_id):
        """
        根据 ID 查询
        """
        return session.query(cls).filter(cls.id == alias_id).first()

    @classmethod
    def create(cls, session, pp_name, alias_name):
        """
        创建新别名
        """
        alias = cls(pp_name=pp_name, alias_name=alias_name)
        session.add(alias)
        session.flush()
        return alias

    @classmethod
    def update(cls, session, alias_id, pp_name, alias_name):
        """
        更新别名
        """
        alias = session.query(cls).filter(cls.id == alias_id).first()
        if alias:
            alias.pp_name = pp_name
            alias.alias_name = alias_name
            session.flush()
        return alias

    @classmethod
    def delete(cls, session, alias_id):
        """
        删除别名
        """
        alias = session.query(cls).filter(cls.id == alias_id).first()
        if alias:
            session.delete(alias)
            session.flush()
            return True
        return False
