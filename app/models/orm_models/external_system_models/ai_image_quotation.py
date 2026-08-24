# -*- coding:utf-8 -*-
# @Time    : 2026/8/23
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : ai_image_quotation.py
# @Software: trae-cn
# @Description: AI图片报价识别记录表 ORM 模型

from sqlalchemy import Column, Integer, String, DateTime, Text, func

from app.models.orm_models.base_models import BaseModels


class AiImageQuotation(BaseModels):
    """
    AI图片报价识别记录表模型
    对应数据库表：ai_image_quotation

    存储 image_processor.py 从微信群聊天截图识别出的"询价-报价"记录。
    同一条询价 + 同一报价人合并为一条记录；
    该记录下的多条报价以 JSON 数组形式存放在 quote_json_data 字段中
    （元素为 {"报价OE","品质","价格"}）。
    """
    __tablename__ = 'ai_image_quotation'

    # 主键，自增序号
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 来源图片信息
    image_name = Column(String(255), nullable=True, comment='来源图片名称（关联 wx_chat_image.图片名称）')

    wx_chat_image_id = Column(Integer, nullable=True, comment='关联 wx_chat_image 表的 ID')

    # 询价-报价记录
    seq_no = Column(Integer, nullable=True, comment='序号（图片内记录顺序编号，从1开始递增）')
    inquiry_person = Column(String(255), nullable=True, comment='询价人')
    inquiry_oe = Column(String(255), nullable=True, comment='询价OE')
    quote_person = Column(String(255), nullable=True, comment='报价人')

    quote_json_data = Column(Text, nullable=True, comment='JSON 格式的报价记录数据')



    # 审计字段
    created_at = Column(DateTime, server_default=func.now(), comment='数据创建时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment='数据更新时间')

    def to_dict(self):
        """
        将记录对象转换为字典
        :return: 字典形式的记录数据
        """
        return {
            'id': self.id,
            'image_name': self.image_name,
            '序号': self.seq_no,
            '询价人': self.inquiry_person,
            '询价OE': self.inquiry_oe,
            '报价人': self.quote_person,
            '报价信息': self.quote_json_data,
        }