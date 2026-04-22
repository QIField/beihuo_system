# -*- coding:utf-8 -*-
# @Time    : 2026/4/18 16:27
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : beihuo_system_config_service.py
# @Software: PyCharm
from app.models.orm_models.beihuo_system_config import BeihuoSystemConfig
from app.utils.orm import orm_session


def get_paged_configs(page, page_size):
    page=int(page)
    page_size=int(page_size)

    page = max(1, page)
    limit = max(1, min(page_size, 100))

    with orm_session() as session:
        total,data_list=BeihuoSystemConfig.get_paged_configs(session, page, limit)
        data_list=BeihuoSystemConfig.list_to_dict_list(data_list)

        json_data={
            "total":total,
            "data_list":data_list
        }

        return json_data

def create_config(data):
    """
    创建新配置
    :param data: 配置数据字典
    :return: 创建的配置字典
    """
    with orm_session() as session:
        config = BeihuoSystemConfig.create(session, data)
        session.commit()
        return config.to_dict()

def update_config(config_id,data):
    """
    更新配置
    :param config_id: 配置ID
    :param data: 更新数据字典
    :return: 更新后的配置字典或 None
    """
    with orm_session() as session:
        config = BeihuoSystemConfig.update(session, config_id, data)
        if config:
            session.commit()
            return config.to_dict()
        return None

