# -*- coding:utf-8 -*-
# @Time    : 2026/09/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : handler_phone_service.py
# @Software: trae-cn

"""
经手人联系电话解析服务

职责：根据订单经手人（handler）在 crmapp_users 中匹配 username，
      返回对应 order_mobile。未匹配返回 None。
"""

import logging

from sqlalchemy import text

from app.utils.orm.session import orm_session

logger = logging.getLogger("order_share")

_HANDLER_PHONE_SQL = text("""
    SELECT order_mobile
    FROM crmapp_users
    WHERE username = :handler
    LIMIT 1
""")


def resolve_handler_phone(handler):
    """
    根据经手人解析联系电话。

    :param handler: 经手人名称/账号
    :return: 手机号字符串；未匹配或异常返回 None
    """
    if not handler:
        return None

    try:
        with orm_session() as session:
            row = session.execute(_HANDLER_PHONE_SQL, {"handler": handler}).mappings().first()
            if row and row.get("order_mobile"):
                return row["order_mobile"]
    except Exception:
        logger.exception("[订单分享] 查询经手人用户表失败 handler=%s", handler)

    return None
