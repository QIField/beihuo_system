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

from datetime import datetime, timedelta
from typing import List, Dict

from sqlalchemy import and_, or_, select

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


def get_pending_images(session, days: int = 3) -> List[Dict]:
    """
    查询状态为空的待解析图片记录

    :param session: 数据库会话
    :param days: 近 N 天，默认 3 天；传 None 表示不限制创建时间
    :return: 待解析图片记录字典列表
    """
    conditions = [
        or_(
            WxChatImage.状态.is_(None),
            WxChatImage.状态 == ""
        )
    ]

    if days is not None:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        conditions.extend([
            WxChatImage.创建时间 >= start_time.strftime("%Y-%m-%d %H:%M:%S"),
            WxChatImage.创建时间 <= end_time.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    stmt = select(WxChatImage).where(and_(*conditions))
    result = session.execute(stmt).scalars().all()
    return [item.to_dict() for item in result]


def update_image_status(session, image_id: int, status: str) -> None:
    """
    更新 wx_chat_image 记录的状态和修改时间

    :param session: 数据库会话
    :param image_id: 图片记录主键序号
    :param status: 目标状态，如 "已解析" / "解析出错"
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    image = session.get(WxChatImage, image_id)
    if image:
        image.状态 = status
        image.修改时间 = now


# if __name__ == "__main__":
#     from app.utils.orm.session import orm_session
#     with orm_session() as session:
#         image_list = get_image_list(session)
#         print(image_list)