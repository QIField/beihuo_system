# -*- coding:utf-8 -*-
"""
CRM 零件品牌别名操作日志 ORM 模型
对应数据库表：crm_pp_name_log
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.models.orm_models.base_models import BaseModels


class CrmPpNameLog(BaseModels):
    """
    CRM 零件品牌别名操作日志表
    """

    __tablename__ = "crm_pp_name_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    record_id = Column(Integer, nullable=True, comment="对应 crm_pp_name.id")
    action = Column(String(20), nullable=False, comment="操作类型：create/update/delete")
    pp_name_old = Column(String(255), nullable=True, comment="修改前主名")
    alias_name_old = Column(String(255), nullable=True, comment="修改前别名")
    pp_name_new = Column(String(255), nullable=True, comment="修改后主名")
    alias_name_new = Column(String(255), nullable=True, comment="修改后别名")
    operator = Column(String(50), nullable=True, comment="操作人")
    created_at = Column(DateTime, nullable=True, default=func.now(), comment="操作时间")

    def to_dict(self):
        """
        将模型对象转换为字典
        """
        return {
            "id": self.id,
            "record_id": self.record_id,
            "action": self.action,
            "pp_name_old": self.pp_name_old,
            "alias_name_old": self.alias_name_old,
            "pp_name_new": self.pp_name_new,
            "alias_name_new": self.alias_name_new,
            "operator": self.operator,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }

    @classmethod
    def list_to_dict_list(cls, items):
        """
        对象列表转字典列表
        """
        return [item.to_dict() for item in items]

    @classmethod
    def create_log(cls, session, record_id, action,
                   pp_name_old=None, alias_name_old=None,
                   pp_name_new=None, alias_name_new=None,
                   operator=None):
        """
        创建操作日志
        """
        log = cls(
            record_id=record_id,
            action=action,
            pp_name_old=pp_name_old,
            alias_name_old=alias_name_old,
            pp_name_new=pp_name_new,
            alias_name_new=alias_name_new,
            operator=operator
        )
        session.add(log)
        session.flush()
        return log
