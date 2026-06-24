# -*- coding:utf-8 -*-
# @Time    : 2026/6/23
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : zpy_token.py
# @Software: trae-cn
# @Description: 凭证表 ORM 模型

from sqlalchemy import Column, String, Text

from app.models.orm_models.base_models import BaseModels


class ZpyToken(BaseModels):
    """
    凭证表模型
    对应数据库表：zpy_token

    用于存储外部系统的访问凭证信息。
    """
    __tablename__ = 'zpy_token'

    # 主键
    id = Column(String(255), primary_key=True, comment='主键ID')

    # 凭证信息
    access_token = Column(Text, nullable=True, comment='访问令牌')
    update_date = Column(String(255), nullable=True, comment='更新日期')

    def to_dict(self):
        """
        将凭证对象转换为字典
        :return: 字典形式的凭证数据
        """
        return {
            'id': self.id,
            'access_token': self.access_token,
            'update_date': self.update_date,
        }
