# -*- coding:utf-8 -*-
"""
飞书任务同步 - 认证与 token 缓存

使用项目现有 app/core/cache_utils.py 做进程内缓存。
当前 uwsgi.ini 为 processes=1，单进程多线程场景下安全。
"""

import requests

from app.core.cache_utils import get_default_cache
from app.models.orm_models import BeihuoSystemConfig
from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from .config import (
    TENANT_ACCESS_TOKEN_URL,
    LARK_APP_ID_KEY,
    LARK_APP_SECRET_KEY,
    TOKEN_CACHE_KEY_PREFIX,
    REQUEST_TIMEOUT,
    get_current_env,
)

logger = get_task_logger('lark_task_sync')
cache = get_default_cache()


def _get_config_value(session, key):
    """从 beihuo_system_config 表读取当前环境配置"""
    config = session.query(BeihuoSystemConfig).filter(
        BeihuoSystemConfig.config_key == key,
        BeihuoSystemConfig.env == get_current_env(),
        BeihuoSystemConfig.status == 1,
    ).first()
    return config.config_value if config else None


def get_app_id():
    """
    获取当前环境配置的飞书应用 app_id。

    :return: app_id 字符串
    :raises: 配置缺失时抛出异常
    """
    with orm_session() as session:
        app_id = _get_config_value(session, LARK_APP_ID_KEY)
    if not app_id:
        raise ValueError("缺少飞书应用配置: lark_app_id")
    return app_id


def get_tenant_access_token():
    """
    获取 tenant_access_token，使用内存缓存，有效期约 2 小时。

    :return: token 字符串
    :raises: 获取失败时抛出异常
    """
    with orm_session() as session:
        app_id = _get_config_value(session, LARK_APP_ID_KEY)
        app_secret = _get_config_value(session, LARK_APP_SECRET_KEY)

    if not app_id or not app_secret:
        raise ValueError("缺少飞书应用配置: lark_app_id 或 lark_app_secret")

    cache_key = f"{TOKEN_CACHE_KEY_PREFIX}:{app_id}"
    token = cache.get(cache_key)
    if token:
        return token

    logger.info("[飞书token] 缓存未命中，重新获取")
    resp = requests.post(
        TENANT_ACCESS_TOKEN_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书token失败: {data}")

    token = data["tenant_access_token"]
    expire = data.get("expire", 7200)
    # 留 200 秒余量
    cache.set(cache_key, token, ttl=expire - 200)
    logger.info(f"[飞书token] 获取成功，缓存 {expire - 200} 秒")
    return token
