# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 11:42
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : weixin_decoding_alias.py
# @Software: PyCharm

from sqlalchemy import Column, Integer, String, DateTime
from .base_models import BaseModels


class WeixinDecodingAlias(BaseModels):
    """
    微信解码别名 ORM 模型
    对应数据库表：weixin_decoding_alias
    """
    
    __tablename__ = "weixin_decoding_alias"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    creation_date = Column(DateTime, nullable=True, comment="创建时间")
    vin = Column(String(255), nullable=True, comment="车架号")
    partsName = Column(String(255), nullable=True, comment="查询名称")
    standardName = Column(String(255), nullable=True, comment="匹配名称")
    oeCode = Column(String(255), nullable=True, comment="匹配OEM")

    def to_dict(self):
        """
        将模型对象转换为字典
        DateTime 类型会转换为字符串
        """
        return {
            "id": self.id,
            "creation_date": self.creation_date.strftime("%Y-%m-%d %H:%M:%S") if self.creation_date else None,
            "vin": self.vin,
            "partsName": self.partsName,
            "standardName": self.standardName,
            "oeCode": self.oeCode,
        }
