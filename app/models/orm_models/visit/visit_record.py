# -*- coding:utf-8 -*-
# @Time    : 2026/10/13 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_record.py
# @Software: PyCharm
# 客访-拜访记录表 ORM 模型

from sqlalchemy import Column, String, DateTime, BigInteger, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.mysql import TINYINT

from ..base_models import BaseModels


class VisitRecord(BaseModels):
    """
    对应数据库表：visit_record（设计文档 doc/客访管理/01-主设计文档.md 4.3）
    物理主键 id 自增；幂等去重键为复合唯一键 uk_visit_dedup (amap_customer_id, visit_time)
    （同位置 + 同一秒 = 同一次拜访）；external_record_id 为预留的高德同步渠道幂等键（渠道内防重）。
    recorder 存 Excel"记录人"文案（我方业务人员，展示用，不参与去重）；
    content 存 Excel"记录文字"列原样字符串；images 存 Excel"记录照片"列原样字符串；
    CRM 关联经 visit_customer_relation 桥接查询，本表不冗余 partner_id；
    转化标记由订单数据实时统计，本表不落库 converted。
    本期唯一写入渠道为 Excel 导入（source=2），见 amap_customer_import_service.py；
    数据库操作见 app/dao/visit_dao/visit_record_dao.py
    """

    __tablename__ = "visit_record"

    # 幂等约束：业务复合唯一键（同位置 + 同一秒 = 同一次拜访）+ 预留同步幂等键
    __table_args__ = (
        UniqueConstraint("amap_customer_id", "visit_time", name="uk_visit_dedup"),
        UniqueConstraint("external_record_id", name="uk_external_record_id"),
        {"comment": "客访-拜访记录表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    amap_customer_id = Column(String(128), nullable=False,
                              comment="高德客户POI编码（Excel记录内容位置编码）→ visit_amap_customer.amap_poi_id")
    recorder = Column(String(50), comment="记录人（Excel\"记录人\"原样，我方业务人员文案，展示用）")
    visit_time = Column(DateTime, nullable=False, comment="记录时间（Excel记录时间）")
    content = Column(Text, comment='记录文字，Excel"记录文字"列原样字符串，直接存入不做结构化')
    images = Column(Text, comment='记录照片，Excel 照片列原样字符串（url 逗号分隔），直接存入不做结构化')
    external_record_id = Column(String(128), comment="预留：小程序端记录唯一ID（同步幂等键）")
    source = Column(TINYINT, nullable=False, default=1, comment="1-高德小程序同步 2-后台补录（Excel导入）")
    status = Column(TINYINT, nullable=False, default=1, comment="1-正常 0-作废")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                        comment="更新时间")

    def to_dict(self):
        """ORM 对象 → dict（时间格式化为秒级字符串，须在会话内调用）"""
        return {
            "id": self.id,
            "amap_customer_id": self.amap_customer_id,
            "recorder": self.recorder,
            "visit_time": self.visit_time.strftime("%Y-%m-%d %H:%M:%S") if self.visit_time else None,
            "content": self.content,
            "images": self.images,
            "external_record_id": self.external_record_id,
            "source": self.source,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
