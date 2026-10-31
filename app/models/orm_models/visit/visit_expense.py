# -*- coding:utf-8 -*-
# @Time    : 2026/10/29 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_expense.py
# @Software: PyCharm
# 客访-拜访费用明细表 ORM 模型

from sqlalchemy import Column, String, DateTime, BigInteger, Date, Integer, func, text
from sqlalchemy.dialects.mysql import TINYINT, DECIMAL

from ..base_models import BaseModels


class VisitExpense(BaseModels):
    """
    对应数据库表：visit_expense（设计文档 doc/客访管理/09-费用分析.md）
    物理主键 id 自增；无业务唯一键（费用是事实数据，不做自动去重）。
    source_type 枚举: 1-拜访记录(visit_record) 2-跟进记录(visit_follow_record)
    3-订单(crm_sales_order.orders_id) 4-手动输入(无关联记录)；
    source_type=1/2/3 时 source_id 为对应记录主键，=4 时 source_id 为空。
    amap_customer_id 必填，冗余存储高德客户 POI 编码，按客户/时间维度直接索引，
    费用表不冗余 partner_id，CRM 关联经 visit_customer_relation 桥接查询。
    expense_type 为枚举文本（VARCHAR(50)），应用层仅允许：
    拜访投入/礼品物料投入/接待投入/服务投入/索赔/其他（校验见 visit_expense_service.EXPENSE_TYPES）。
    数据库操作见 app/dao/visit_dao/visit_expense_dao.py
    """

    __tablename__ = "visit_expense"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    source_type = Column(TINYINT, nullable=False,
                         comment="关联来源类型: 1-拜访记录 2-跟进记录 3-订单 4-手动输入")
    source_id = Column(BigInteger, comment="关联记录ID(记录主键或orders_id); source_type=4时为空")
    amap_customer_id = Column(String(128), nullable=False, comment="高德客户POI编码(冗余)")
    expense_date = Column(Date, nullable=False, comment="费用发生日期")
    expense_type = Column(String(50), nullable=False,
                          comment="费用类型(枚举文本: 拜访投入/礼品物料投入/接待投入/服务投入/索赔/其他)")
    amount = Column(DECIMAL(12, 2), nullable=False, comment="金额(元),>0")
    description = Column(String(500), comment="费用说明/备注")
    recorder_id = Column(Integer, nullable=False, comment="录入人ID")
    status = Column(TINYINT, nullable=False, default=1, comment="1-正常 0-作废")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                        comment="更新时间")

    def to_dict(self):
        """ORM 对象 → dict（时间格式化为秒级字符串，须在会话内调用）"""
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "amap_customer_id": self.amap_customer_id,
            "expense_date": self.expense_date.strftime("%Y-%m-%d") if self.expense_date else None,
            "expense_type": self.expense_type,
            "amount": float(self.amount) if self.amount is not None else None,
            "description": self.description,
            "recorder_id": self.recorder_id,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
