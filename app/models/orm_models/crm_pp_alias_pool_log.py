# -*- coding:utf-8 -*-
"""
CRM 品牌别名池操作日志 ORM 模型
对应数据库表：crm_pp_alias_pool_log

日志格式（别名池模式）：
- pool_id:   别名池编号
- action:    操作类型 create/update/delete
- names_old: 修改前池内名称列表，逗号分隔
- names_new: 修改后池内名称列表，逗号分隔
- operator:  操作人
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.models.orm_models.base_models import BaseModels


class CrmPpAliasPoolLog(BaseModels):
    """
    CRM 品牌别名池操作日志表
    """

    __tablename__ = "crm_pp_alias_pool_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    pool_id = Column(Integer, nullable=True, comment="别名池编号")
    action = Column(String(20), nullable=False, comment="操作类型：create/update/delete")
    names_old = Column(Text, nullable=True, comment="修改前池内名称列表，逗号分隔")
    names_new = Column(Text, nullable=True, comment="修改后池内名称列表，逗号分隔")
    operator = Column(String(50), nullable=True, comment="操作人")
    created_at = Column(DateTime, nullable=True, default=func.now(), comment="操作时间")

    def to_dict(self):
        """将模型对象转换为字典"""
        return {
            "id": self.id,
            "pool_id": self.pool_id,
            "action": self.action,
            "names_old": self.names_old,
            "names_new": self.names_new,
            "operator": self.operator,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }

    @classmethod
    def list_to_dict_list(cls, items):
        """对象列表转字典列表"""
        return [item.to_dict() for item in items]

    @classmethod
    def create_log(cls, session, action, pool_id=None,
                   names_old=None, names_new=None, operator=None):
        """
        创建操作日志

        :param session: SQLAlchemy Session
        :param action: 操作类型 create/update/delete
        :param pool_id: 别名池编号
        :param names_old: 修改前名称列表（list 或 str）
        :param names_new: 修改后名称列表（list 或 str）
        :param operator: 操作人
        """
        def _fmt_names(val):
            if val is None:
                return None
            if isinstance(val, list):
                return ", ".join(str(v).strip() for v in val if v)
            return str(val)

        log = cls(
            pool_id=pool_id,
            action=action,
            names_old=_fmt_names(names_old),
            names_new=_fmt_names(names_new),
            operator=operator
        )
        session.add(log)
        session.flush()
        return log
