# -*- coding: utf-8 -*-
"""巴图鲁登录认证与 cookie 管理"""

import requests

from app.services.system_setting_service.beihuo_system_config_service import set_config_by_key
from config.config_list_manager.config_cache import get_config_value
from .btl_config import LOGIN_URL, LOGIN_PARAMS, COOKIE_CONFIG_KEY, logger, build_cookie_from_token


def _do_login():
    """调用登录接口，返回 token"""
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        )
    }
    resp = requests.post(LOGIN_URL, json=LOGIN_PARAMS, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    if not data.get('success') and data.get('code') != 0:
        raise RuntimeError(f"巴图鲁登录失败: {data.get('message', '未知错误')}")

    token = data.get('model', {}).get('token')
    if not token:
        raise RuntimeError('巴图鲁登录响应中未找到 token')

    return token


def _save_cookie(cookie):
    """保存 cookie 到 beihuo_system_config"""
    set_config_by_key(
        COOKIE_CONFIG_KEY,
        cookie,
        config_type='string',
        config_group='btl',
        label='巴图鲁佛山cookie',
        remark='巴图鲁自动登录后的请求cookie，失效后自动刷新'
    )


def refresh_btl_cookie():
    """强制重新登录并保存 cookie"""
    logger.info('[巴图鲁] 开始重新登录获取 cookie')
    token = _do_login()
    cookie = build_cookie_from_token(token)
    _save_cookie(cookie)
    logger.info('[巴图鲁] cookie 已更新并保存')
    return cookie


def get_btl_cookie():
    """
    获取巴图鲁 cookie
    - 优先从 beihuo_system_config 读取
    - 不存在时自动登录并保存
    """
    cookie = get_config_value(COOKIE_CONFIG_KEY)
    if cookie:
        return cookie

    logger.info('[巴图鲁] 未找到 cookie，自动登录获取')
    return refresh_btl_cookie()


def ensure_btl_cookie(force=False):
    """
    确保 cookie 可用
    :param force: 是否强制刷新
    """
    if force:
        return refresh_btl_cookie()
    return get_btl_cookie()
