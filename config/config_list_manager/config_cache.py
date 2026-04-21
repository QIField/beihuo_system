# -*- coding:utf-8 -*-
# @Time    : 2026/4/17 16:39
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : config_cache.py
# @Software: PyCharm
import os
from functools import lru_cache

from app.models.orm_models.beihuo_system_config import BeihuoSystemConfig
from app.utils.orm import orm_session

# 系统环境配置
FLASK_SYS_ENV = os.getenv("FLASK_SYS_ENV", "prod")


def _load_all_config_from_db():
    """从数据库加载所有启用的配置，返回 { config_key: config_value }"""
    with orm_session() as session:
        config_list = session.query(BeihuoSystemConfig).filter(
            BeihuoSystemConfig.env == FLASK_SYS_ENV,
            BeihuoSystemConfig.status == 1
        ).all()

        config_dict = {}
        for cfg in config_list:
            config_dict[cfg.config_key] = cfg.config_value

        return config_dict


@lru_cache(maxsize=1)
def get_sys_config():
    """获取全部系统配置（全局缓存）"""
    return _load_all_config_from_db()


def get_config_value(config_key):
    """
    根据 key 获取配置值
    :param config_key: 配置key（必填）
    :return: 配置值 / None（不存在返回空）
    """
    all_config = get_sys_config()
    return all_config.get(config_key)


def refresh_sys_config():
    """刷新配置缓存（修改数据库后调用）"""
    get_sys_config.cache_clear()