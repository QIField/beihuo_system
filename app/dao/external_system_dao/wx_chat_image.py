# -*- coding:utf-8 -*-
# @Time    : 2026/08/23
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : image_processor_dao.py
# @Software : trae-cn

"""
图片处理器数据访问层
负责处理 wx_chat_image 表的数据库操作（目前仅提供列表读取功能）
"""

from typing import List, Dict

from sqlalchemy import select

from app.models.orm_models.external_system_models.wx_chat_image import WxChatImage





def get_image_list(session) -> List[Dict]:
    """
    查询 wx_chat_image 表中的全部图片记录列表

    使用 SQLAlchemy 语法，仅作读取操作，不修改数据

    :param session: 数据库会话
    :return: 图片记录字典列表
    """
    # 构建查询语句
    stmt = select(WxChatImage)
        # 执行查询并获取结果列表
    result = session.execute(stmt).scalars().all()
    # 将 ORM 对象转换为字典列表返回
    return [item.to_dict() for item in result]


# if __name__ == "__main__":
#     from app.utils.orm.session import orm_session
#     with orm_session() as session:
#         image_list = get_image_list(session)
#         print(image_list)