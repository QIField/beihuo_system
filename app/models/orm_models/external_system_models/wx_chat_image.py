# -*- coding:utf-8 -*-
# @Time    : 2026/8/23
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : wx_chat_image.py
# @Software: trae-cn
# @Description: 微信群聊天图片表 ORM 模型

from sqlalchemy import Column, Integer, String

from app.models.orm_models.base_models import BaseModels


class WxChatImage(BaseModels):
    """
    微信群聊天图片表模型
    对应数据库表：wx_chat_image

    用于存储微信群聊中图片的抓取与管理信息。
    """
    __tablename__ = 'wx_chat_image'

    # 主键，自增序号
    序号 = Column(Integer, primary_key=True, autoincrement=True, comment='序号（主键，自增）')

    # 图片信息
    创建时间 = Column(String(255), nullable=True, comment='创建时间')
    群名称 = Column(String(255), nullable=True, comment='群名称')
    图片名称 = Column(String(255), nullable=True, comment='图片名称')

    # 状态信息
    状态 = Column(String(255), nullable=True, comment='状态')
    修改时间 = Column(String(255), nullable=True, comment='修改时间')

    def to_dict(self):
        """
        将图片对象转换为字典
        :return: 字典形式的图片数据
        """
        return {
            '序号': self.序号,
            '创建时间': self.创建时间,
            '群名称': self.群名称,
            '图片名称': self.图片名称,
            '状态': self.状态,
            '修改时间': self.修改时间,
        }
