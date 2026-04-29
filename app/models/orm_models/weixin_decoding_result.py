# -*- coding:utf-8 -*-
# @Time    : 2026/4/27 13:04
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : weixin_decoding_result.py
# @Software: PyCharm

from sqlalchemy import Column, Integer, String, DateTime, Text
from .base_models import BaseModels


class WeixinDecodingResult(BaseModels):
    """
    微信解码结果 ORM 模型
    对应数据库表：weixin_decoding_result
    """
    
    __tablename__ = "weixin_decoding_result"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    creation_date = Column(DateTime, nullable=True, comment="创建时间")
    groupname = Column(String(255), nullable=True, comment="群名称")
    nickname = Column(String(255), nullable=True, comment="好友备注")
    content = Column(String(1000), nullable=True, comment="查询号码")
    result = Column(Text, nullable=True, comment="返回结果")

    @classmethod
    def get_paginated_by_time(cls, session, page=1, limit=20, start_time=None, end_time=None, 
                              nickname=None, groupname=None, content=None):
        """
        按时间分页查询解码结果列表
        
        :param session: SQLAlchemy Session 对象
        :param page: 页码，默认1
        :param limit: 每页条数，默认20
        :param start_time: 开始时间（可选，DateTime类型）
        :param end_time: 结束时间（可选，DateTime类型）
        :param nickname: 好友备注（可选，模糊查询）
        :param groupname: 群名称（可选，模糊查询）
        :param content: 查询号码（可选，模糊查询）
        :return: (total: 总数, result: 数据列表)
        """
        # 构建查询
        query = session.query(cls)
        
        # 添加时间范围查询条件
        if start_time:
            query = query.filter(cls.creation_date >= start_time)
        
        if end_time:
            query = query.filter(cls.creation_date <= end_time)
        
        # 添加其他查询条件
        if nickname:
            query = query.filter(cls.nickname.like(f"%{nickname}%"))
        
        if groupname:
            query = query.filter(cls.groupname.like(f"%{groupname}%"))
        
        if content:
            query = query.filter(cls.content.like(f"%{content}%"))
        
        # 统计总数
        total = query.count()
        
        # 分页查询，按创建时间倒序排列（最新的在前）
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
            "content": self.content,
            "result": self.result,
        }
