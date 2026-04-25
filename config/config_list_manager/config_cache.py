# -*- coding:utf-8 -*-
# @Time    : 2026/4/17 16:39
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : config_cache.py
# @Software: PyCharm
import os
import json
from collections import OrderedDict

from app.models.orm_models.beihuo_system_config import BeihuoSystemConfig
from app.utils.orm import orm_session

# 系统环境配置
FLASK_SYS_ENV = os.getenv("FLASK_SYS_ENV", "prod")

# 手动管理的配置缓存，使用 OrderedDict 实现 LRU 效果
_config_cache = OrderedDict()
_MAX_CACHE_SIZE = 100


def _convert_value_by_type(config_value, config_type):
    """
    根据配置类型转换值
    :param config_value: 原始配置值
    :param config_type: 配置类型
    :return: 转换后的值
    """
    if config_value is None:
        return None
    
    try:
        if config_type == 'int':
            return int(config_value)
        elif config_type == 'bool':
            return config_value.lower() in ('true', '1', 'yes', 'on')
        elif config_type == 'json':
            return json.loads(config_value)
        else:  # string 或其他类型，直接返回
            return config_value
    except (ValueError, json.JSONDecodeError):
        # 转换失败时返回原始值
        return config_value


def get_config_value(config_key):
    """
    根据 key 获取配置值
    :param config_key: 配置key（必填）
    :return: 配置值 / None（不存在返回空）
    """
    # 检查缓存中是否存在
    if config_key in _config_cache:
        # 将访问的 key 移到末尾，表示最近使用
        _config_cache.move_to_end(config_key)
        return _config_cache[config_key]
    
    # 缓存未命中，从数据库查询
    with orm_session() as session:
        config = session.query(BeihuoSystemConfig).filter(
            BeihuoSystemConfig.config_key == config_key,
            BeihuoSystemConfig.env == FLASK_SYS_ENV,
            BeihuoSystemConfig.status == 1
        ).first()
        # print(config,"ck")
        if not config:
            return None
        
        # 根据类型转换值
        converted_value = _convert_value_by_type(config.config_value, config.config_type)
        
        # 添加到缓存
        _config_cache[config_key] = converted_value
        
        # 如果缓存超过最大大小，删除最久未使用的
        if len(_config_cache) > _MAX_CACHE_SIZE:
            _config_cache.popitem(last=False)
        
        return converted_value


def refresh_sys_config(config_key=None):
    """
    刷新配置缓存（修改数据库后调用）
    :param config_key: 指定刷新某个key的缓存，不传则刷新全部
    """
    global _config_cache
    if config_key:
        # 只清除指定key的缓存
        if config_key in _config_cache:
            del _config_cache[config_key]
    else:
        # 清除全部缓存
        _config_cache.clear()