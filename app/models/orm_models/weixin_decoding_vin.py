# -*- coding:utf-8 -*-
# @Time    : 2026/8/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : weixin_decoding_vin.py
# @Software: PyCharm

from sqlalchemy import Column, Integer, String, DateTime
from .base_models import BaseModels


class WeixinDecodingVin(BaseModels):
    """
    微信解码 VIN ORM 模型
    对应数据库表：weixin_decoding_vin
    """

    __tablename__ = "weixin_decoding_vin"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    creation_date = Column(DateTime, nullable=True, comment="创建时间")
    groupname = Column(String(255), nullable=True, comment="群名称")
    nickname = Column(String(255), nullable=True, comment="好友备注")
    vin = Column(String(255), nullable=True, comment="车架号")
    content = Column(String(500), nullable=True, comment="车架号信息")

    @classmethod
    def get_paginated_by_date_range(cls, session, page=1, limit=20, start_date=None, end_date=None):
        """
        按创建日期范围分页查询 VIN 列表

        :param session: SQLAlchemy Session 对象
        :param page: 页码，默认 1
        :param limit: 每页条数，默认 20
        :param start_date: 开始日期（可选，DateTime 或字符串）
        :param end_date: 结束日期（可选，DateTime 或字符串）
        :return: (total: 总数, result: 数据列表)
        """
        query = session.query(cls)

        if start_date:
            query = query.filter(cls.creation_date >= start_date)

        if end_date:
            query = query.filter(cls.creation_date <= end_date)

        total = query.count()

        offset = (page - 1) * limit
        items = query.order_by(cls.creation_date.desc()).limit(limit).offset(offset).all()

        return total, items

    def to_dict(self):
        """
        将模型对象转换为字典
        DateTime 类型会转换为字符串
        """
        return {
            "id": self.id,
            "creation_date": self.creation_date.strftime("%Y-%m-%d %H:%M:%S") if self.creation_date else None,
            "groupname": self.groupname,
            "nickname": self.nickname,
            "vin": self.vin,
            "content": self.content,
        }
