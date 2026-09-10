# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test_crypto_service.py
# @Software: trae-cn

"""
订单分享 - 加密服务单元测试（核心业务）

测试范围（mock 数据库配置，不触网、不触库）：
1. 加密后可解密还原（含中文/数字/特殊字符订单号）
2. 同一订单号两次加密密文不同（随机 IV），但均可解密
3. 非法/被篡改/为空的密文解密返回 None，不抛异常
4. generate_key 生成合法密钥；换钥后旧密文失效、新密文可用

运行方式：
    python -m tests.order_share.test_crypto_service
"""

import os
import sys
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from cryptography.fernet import Fernet

_TEST_KEY = Fernet.generate_key().decode()

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[通过] {name}")
    else:
        FAIL += 1
        print(f"[失败] {name}")


def _mock_get_config_value(key):
    """mock：从数据库配置表读取密钥"""
    return _TEST_KEY


@patch("app.services.order_share_service.crypto_service.get_config_value", _mock_get_config_value)
def test_roundtrip():
    """加密后可解密还原"""
    from app.services.order_share_service import crypto_service
    crypto_service._fernet = None

    cases = ["DD20260903001", "订单-2026-测试", "ABC#123/abc", "000000", "x"]
    for order_no in cases:
        token = crypto_service.encrypt_order_no(order_no)
        check(f"加密后可解密还原: {order_no}",
              crypto_service.decrypt_order_no(token) == order_no)


@patch("app.services.order_share_service.crypto_service.get_config_value", _mock_get_config_value)
def test_random_iv():
    """同一订单号两次加密密文不同（随机 IV），但均可解密"""
    from app.services.order_share_service import crypto_service
    crypto_service._fernet = None

    t1 = crypto_service.encrypt_order_no("DD001")
    t2 = crypto_service.encrypt_order_no("DD001")
    check("同一订单号两次加密密文不同", t1 != t2)
    check("两个密文均可解密",
          crypto_service.decrypt_order_no(t1) == "DD001"
          and crypto_service.decrypt_order_no(t2) == "DD001")


@patch("app.services.order_share_service.crypto_service.get_config_value", _mock_get_config_value)
def test_invalid_token():
    """非法/被篡改/为空的密文解密返回 None，不抛异常"""
    from app.services.order_share_service import crypto_service
    crypto_service._fernet = None

    check("空字符串返回 None", crypto_service.decrypt_order_no("") is None)
    check("None 返回 None", crypto_service.decrypt_order_no(None) is None)
    check("乱码返回 None", crypto_service.decrypt_order_no("not-a-valid-token!!!") is None)

    token = crypto_service.encrypt_order_no("DD001")
    tampered = ("A" if token[0] != "A" else "B") + token[1:]
    check("被篡改的密文返回 None", crypto_service.decrypt_order_no(tampered) is None)


@patch("app.services.order_share_service.crypto_service.get_config_value", _mock_get_config_value)
def test_key_rotation():
    """换钥场景：旧密文失效、新密文可用"""
    global _TEST_KEY
    from app.services.order_share_service import crypto_service
    crypto_service._fernet = None

    old_token = crypto_service.encrypt_order_no("DD001")

    new_key = crypto_service.generate_key()
    check("generate_key 生成合法密钥", isinstance(new_key, str) and len(new_key) >= 40)

    # 模拟换钥：更新 mock 返回的新密钥并重置缓存实例
    _TEST_KEY = new_key
    crypto_service._fernet = None
    check("换钥后旧密文解密失败", crypto_service.decrypt_order_no(old_token) is None)

    new_token = crypto_service.encrypt_order_no("DD001")
    check("新密钥下新密文可解密", crypto_service.decrypt_order_no(new_token) == "DD001")


if __name__ == "__main__":
    test_roundtrip()
    test_random_iv()
    test_invalid_token()
    test_key_rotation()
    print("=" * 40)
    print(f"测试结果：通过 {PASS} 项，失败 {FAIL} 项")
    sys.exit(1 if FAIL else 0)
