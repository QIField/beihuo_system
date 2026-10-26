# -*- coding:utf-8 -*-
# @Time    : 2026/10/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_follow_record.py
# @Software: PyCharm
# 客访-跟进记录表 ORM 模型

from sqlalchemy import Column, String, DateTime, BigInteger, Integer, Text, func, text
from sqlalchemy.dialects.mysql import TINYINT

from ..base_models import BaseModels


class VisitFollowRecord(BaseModels):
    """
    对应数据库表：visit_follow_record（设计文档 doc/客访管理/04-跟进记录模块设计.md 第二节）
    客户维度的全渠道沟通流水，纯手动写入（唯一渠道为后台表单），与拜访记录
    visit_record 完全独立：无字段关联、无自动联动、互不引用。
    channel 为固定枚举（微信/电话/线上平台/上门/其他），channel_desc 为时间轴标题
    （后端按 channel 映射默认值，前端可覆盖）；作废走 status=0 软删，不做物理删除；
    纯手动写入无幂等诉求，无唯一键。
    数据库操作见 app/dao/visit_dao/visit_follow_record_dao.py
    """

    __tablename__ = "visit_follow_record"

    __table_args__ = (
        {"comment": "客访-跟进记录表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    amap_customer_id = Column(String(128), nullable=False,
                              comment="高德客户POI编码 → visit_amap_customer.amap_poi_id")
    channel = Column(String(50), nullable=False, comment="跟进渠道：微信/电话/线上平台/上门/其他")
    channel_desc = Column(String(100), comment="时间轴标题，后端按 channel 映射默认值，前端可覆盖")
    content = Column(Text, nullable=False, comment="跟进内容")
    follow_time = Column(DateTime, nullable=False, comment="跟进时间，缺省当前时间，允许补录过去时间")
    creator_id = Column(Integer, comment="记录人ID → crmapp_users.id（会话无用户ID时为空）")
    creator_name = Column(String(50), nullable=False, comment="记录人（登录用户名 session.username）")
    status = Column(TINYINT, nullable=False, default=1, comment="1-正常 0-作废")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                        comment="更新时间")

    def to_dict(self):
        """ORM 对象 → dict（时间格式化为秒级字符串，须在会话内调用）"""
        return {
            "id": self.id,
            "amap_customer_id": self.amap_customer_id,
            "channel": self.channel,
            "channel_desc": self.channel_desc,
            "content": self.content,
            "follow_time": self.follow_time.strftime("%Y-%m-%d %H:%M:%S") if self.follow_time else None,
            "creator_id": self.creator_id,
            "creator_name": self.creator_name,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
