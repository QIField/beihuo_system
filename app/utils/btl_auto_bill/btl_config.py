# -*- coding: utf-8 -*-
"""巴图鲁自动报价配置"""

import logging

# 登录接口
LOGIN_URL = 'https://merchant.qipeipu.com/api/account/login'

# 登录参数
# password 为明文密码的 MD5 小写
LOGIN_PARAMS = {
    'loginName': '17817579302',
    'secretKey': '02a5615e3798f8e3db7d061278bbb0f1',
    'password': '23ce9650c0c3a3ec2bd2bdd32bd8789f',
    'machineId': '79944084-a5e8-4231-b628-1cb72762f5e7',
    'isRememberAccountOnClient': True,
    'loginSource': 1
}

# cookie 在 beihuo_system_config 中的配置键
COOKIE_CONFIG_KEY = 'btl_cookie_fs'

# logger
logger = logging.getLogger('btl_auto_bill')


def build_cookie_from_token(token):
    """根据 token 构造请求 cookie"""
    return (
        'auth.strategy=local; '
        'auth._refresh_token.local=false; '
        f'auth._token.local={token}'
    )
