#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""配置"""

# 基础URL
BASE_URL = 'https://qpl-gateway.qipeilong.cn'

# Token缓存
_token_cache = None


def get_qpl_token():
    """获取Token（延迟加载，从数据库配置获取）"""
    global _token_cache
    if _token_cache is None:
        from config.config_list_manager.config_cache import get_config_value
        _token_cache = get_config_value('QPL_AUTH_TOKEN_fs')
    return _token_cache


def get_headers():
    """获取Headers（延迟加载token）"""
    return {
        'Content-Type': 'application/json',
        'Authorization': get_qpl_token(),
        'authtype': 'qpl_merchant',
        'origin': 'https://s.qipeilong.cn',
        'referer': 'https://s.qipeilong.cn/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'qpl-info': 'QPL/WEB-BIZ',
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9'
    }
