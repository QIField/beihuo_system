# -*- coding:utf-8 -*-
# @Project : beihuo_system
# @File    : column_preference_service.py
# @Description: 用户表格列偏好配置服务

from app.utils.orm.session import orm_session
from app.models.orm_models.system_models.crmapp_user_column_preference import CrmappUserColumnPreference


class ColumnPreferenceService:
    """
    用户表格列偏好配置服务

    用于读取/保存每个用户在指定页面、指定表格上的列状态。
    """

    @staticmethod
    def get_preference(user_id, page_key, grid_key):
        """
        获取用户在指定页面、指定表格上的列状态

        :param user_id: 用户ID
        :param page_key: 页面标识
        :param grid_key: 表格标识
        :return: list（AG Grid columnState 数组）或 None
        """
        if not user_id or not page_key or not grid_key:
            return None

        with orm_session() as session:
            record = session.query(CrmappUserColumnPreference).filter_by(
                user_id=user_id,
                page_key=page_key,
                grid_key=grid_key
            ).first()
            if record and record.column_state is not None:
                return record.column_state
            return None

    @staticmethod
    def save_preference(user_id, page_key, grid_key, column_state):
        """
        保存（或更新）用户在指定页面、指定表格上的列状态

        :param user_id: 用户ID
        :param page_key: 页面标识
        :param grid_key: 表格标识
        :param column_state: AG Grid columnState 数组（list）
        :return: True 表示成功
        """
        if not user_id or not page_key or not grid_key:
            return False

        with orm_session() as session:
            record = session.query(CrmappUserColumnPreference).filter_by(
                user_id=user_id,
                page_key=page_key,
                grid_key=grid_key
            ).first()

            if record:
                record.column_state = column_state
            else:
                record = CrmappUserColumnPreference(
                    user_id=user_id,
                    page_key=page_key,
                    grid_key=grid_key,
                    column_state=column_state
                )
                session.add(record)
            return True

    @staticmethod
    def delete_preference(user_id, page_key, grid_key):
        """
        删除用户在指定页面、指定表格上的列状态（恢复默认）
        """
        if not user_id or not page_key or not grid_key:
            return False

        with orm_session() as session:
            session.query(CrmappUserColumnPreference).filter_by(
                user_id=user_id,
                page_key=page_key,
                grid_key=grid_key
            ).delete()
            return True
