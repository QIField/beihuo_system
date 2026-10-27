# -*- coding:utf-8 -*-
# @Time    : 2026/10/12 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_amap_customer.py
# @Software: PyCharm

import uuid

from sqlalchemy import Column, String, DECIMAL, DateTime, Text, BigInteger, UniqueConstraint, func, text
from sqlalchemy.dialects.mysql import TINYINT

from ..base_models import BaseModels


def gen_manual_poi_id():
    """后台手工新建（无真实 POI）客户生成伪编码，MANUAL_ 前缀与真实 POI 天然不冲突"""
    return f"MANUAL_{uuid.uuid4().hex[:24]}"


class VisitAmapCustomer(BaseModels):
    """
    客访-高德端客户表 ORM 模型

    对应数据库表：visit_amap_customer（设计文档 doc/客访管理/01-主设计文档.md 4.1）
    物理主键 id 自增；amap_poi_id 为业务唯一键（同步/导入幂等键）。
    数据库操作见 app/dao/visit_dao/visit_amap_customer_dao.py
    """

    __tablename__ = "visit_amap_customer"

    # 业务唯一键（同步/导入幂等键），物理主键为自增 id
    __table_args__ = (UniqueConstraint("amap_poi_id", name="uk_amap_poi_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="物理主键，自增")
    amap_poi_id = Column(String(128), nullable=False, comment="业务主键（唯一键），高德位置编码")
    customer_name = Column(String(255), nullable=False, comment="客户名称（高德端）")
    address = Column(String(500), comment="地址")
    longitude = Column(DECIMAL(10, 6), comment="经度")
    latitude = Column(DECIMAL(10, 6), comment="纬度")
    color = Column(String(100), comment="颜色编码，如#FF7F81")
    tag = Column(String(100), comment="标签")
    description = Column(Text, comment="描述")
    folder = Column(String(100), comment="文件夹")
    business_circle = Column(String(100), comment="所属商圈，冗余字段")
    created_by = Column(String(100), comment="创建人")
    photo_url = Column(Text, comment="照片地址")
    contact_person = Column(String(100), comment="采购负责人")
    main_repair_brands = Column(String(255), comment="主修车型/品牌（多值，顿号分隔）")
    customer_type = Column(String(50), comment="客户类型")
    staff_count = Column(String(50), comment="员工数量（区间文案）")
    station_count = Column(String(50), comment="工位数量（区间文案）")
    purchase_channels = Column(String(255), comment="拿货方式（多值，| 分隔）")
    goods_habit = Column(String(255), comment="用货习惯（多值，| 分隔）")
    coop_merchants = Column(String(500), comment="常合作商家")
    focus_points = Column(String(255), comment="客户侧重点（多值，| 分隔）")
    remark = Column(Text, comment="客户信息补充")
    visit_time = Column(DateTime, comment="拜访时间（高德端采集原文，只读展示）")
    status = Column(TINYINT, nullable=False, default=0, comment="0-未关联CRM 1-已关联CRM 2-无效")
    last_visit_time = Column(DateTime, comment="最近拜访时间（冗余，系统维护）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                        comment="更新时间")

    def __repr__(self):
        return f"<VisitAmapCustomer amap_poi_id={self.amap_poi_id} name={self.customer_name}>"
