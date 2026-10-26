# -*- coding:utf-8 -*-
# @Time    : 2026/10/13 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_customer_relation.py
# @Software: PyCharm

from sqlalchemy import Column, String, DateTime, BIGINT, Integer, func, text

from ..base_models import BaseModels


class VisitCustomerRelation(BaseModels):
    """
    客访-高德客户与CRM客户关联表 ORM 模型

    对应数据库表：visit_customer_relation（设计文档 doc/客访管理/01-主设计文档.md 4.2）
    只存当前有效绑定（1:N），解绑即物理删除该行、不留历史；
    同一对（amap_customer_id, partner_id）重复绑定 = 更新原行，绑定时间由 created_at 承担。
    uk_partner_id 唯一键保证 CRM 侧 1:1（一条CRM仅归属一个高德客户）；
    高德侧为 1:N（一条高德客户可绑定多条CRM），amap_customer_id 仅普通索引。
    数据库操作见 app/dao/visit_dao/visit_customer_relation_dao.py
    """

    __tablename__ = "visit_customer_relation"

    id = Column(BIGINT, primary_key=True, autoincrement=True, comment="主键，自增")
    amap_customer_id = Column(String(128), nullable=False, comment="高德客户POI编码 → visit_amap_customer.amap_poi_id")
    partner_id = Column(Integer, nullable=False, comment="CRM客户ID → partner_list.partner_id")
    last_operator = Column(String(50), nullable=False, comment="最后操作人（绑定人）")
    bind_remark = Column(String(255), comment="绑定备注（名称差异说明）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间，即绑定时间")
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                        comment="更新时间，默认当前时间并随更新自动变更")

    def __repr__(self):
        return f"<VisitCustomerRelation amap_customer_id={self.amap_customer_id} partner_id={self.partner_id}>"
