# -*- coding:utf-8 -*-
# @Time    : 2026/4/18 16:27
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : beihuo_system_config_service.py
# @Software: PyCharm
from app.models.orm_models.beihuo_system_config import BeihuoSystemConfig
from app.utils.orm import orm_session
from config.config_list_manager.config_cache import refresh_sys_config


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
        # 刷新缓存
        refresh_sys_config(data.get('config_key'))
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
            # 刷新缓存
            refresh_sys_config(config.config_key)
            return config.to_dict()
        return None


def set_config_by_key(config_key, config_value, env='prod', **kwargs):
    """
    根据 config_key 设置配置（如果不存在则创建，存在则更新）
    :param config_key: 配置键
    :param config_value: 配置值
    :param env: 环境，默认 prod
    :param kwargs: 其他配置参数（config_type, config_group, label, remark, sort, status）
    :return: 设置后的配置字典
    """
    with orm_session() as session:
        # 先检查是否存在
        config = BeihuoSystemConfig.get_by_key(session, config_key, env)
        
        if config:
            # 更新
            update_data = {'config_value': config_value}
            for key in ['config_type', 'config_group', 'label', 'remark', 'sort', 'status']:
                if key in kwargs:
                    update_data[key] = kwargs[key]
            config = BeihuoSystemConfig.update(session, config.id, update_data)
        else:
            # 创建
            create_data = {
                'config_key': config_key,
                'config_value': config_value,
                'env': env
            }
            for key in ['config_type', 'config_group', 'label', 'remark', 'sort', 'status']:
                if key in kwargs:
                    create_data[key] = kwargs[key]
                else:
                    # 设置默认值
                    if key == 'config_type':
                        create_data[key] = 'string'
                    elif key == 'config_group':
                        create_data[key] = 'default'
                    elif key == 'label':
                        create_data[key] = config_key
                    elif key == 'sort':
                        create_data[key] = 1
                    elif key == 'status':
                        create_data[key] = 1
            config = BeihuoSystemConfig.create(session, create_data)
        
        session.commit()
        # 刷新缓存
        refresh_sys_config(config_key)
        return config.to_dict()


def update_json_config(config_key: str, update_dict: dict, env: str = 'prod', **kwargs) -> dict:
    """
    更新JSON类型的配置，支持增量更新
    传入什么属性就更新什么属性，如果数据库没有的属性就新加上去

    :param config_key: 配置键
    :param update_dict: 要更新的字典，包含要修改的属性
    :param env: 环境，默认 prod
    :param kwargs: 其他配置参数（config_type, config_group, label, remark, sort, status）
                   仅在创建新配置时使用
    :return: 更新结果字典，包含 code 和 message
    """
    try:
        import json
        from config.config_list_manager.config_cache import get_config_value
        
        # 获取现有配置
        existing_config = get_config_value(config_key)
        
        # 如果现有配置不是字典，初始化为空字典
        config_dict = existing_config if isinstance(existing_config, dict) else {}
        
        # 增量更新：只更新传入的属性，保留原有属性
        config_dict.update(update_dict)
        
        # 将配置保存为 JSON 格式
        config_value = json.dumps(config_dict, ensure_ascii=False)
        
        # 调用 set_config_by_key 保存
        set_config_by_key(
            config_key,
            config_value,
            env=env,
            config_type='json',
            **kwargs
        )
        
        return {
            'code': 200,
            'message': f'配置 {config_key} 更新成功'
        }
    except Exception as e:
        return {
            'code': 500,
            'message': f'配置 {config_key} 更新失败: {str(e)}'
        }

