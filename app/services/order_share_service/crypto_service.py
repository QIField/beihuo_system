# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crypto_service.py
# @Software: trae-cn

"""
订单号加解密服务（订单分享对客功能）

算法说明：
    Fernet（cryptography 库）= AES-128-CBC 加密 + HMAC-SHA256 签名
    - 密文自带随机 IV 与时间戳，同一订单号每次加密结果都不同，但均可解密
    - 输出为 URL 安全的 Base64 字符串，可直接作为 URL 参数（如 /ddxx?dd=密文）
    - 密文被篡改任意一位，解密都会失败

密钥管理：
    - 我方密钥存放于 .env 的 ORDER_SHARE_FERNET_KEY
    - 客户系统持有同一把密钥（线下交付）
    - 生成新密钥命令（写入 .env 并同步交付客户后使用）：
        python -m app.services.order_share_service.crypto_service genkey
"""

import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

# 项目根目录（order_share_service -> services -> app -> 根）
BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=BASE_DIR / ".env")

ENV_KEY_NAME = "ORDER_SHARE_FERNET_KEY"

_fernet = None


def _get_fernet():
    """懒加载 Fernet 实例（密钥从环境变量读取，避免导入期报错）"""
    global _fernet
    if _fernet is None:
        key = (os.getenv(ENV_KEY_NAME) or "").strip()
        if not key:
            raise RuntimeError(
                f"环境变量 {ENV_KEY_NAME} 未配置，请先执行 "
                f"python -m app.services.order_share_service.crypto_service genkey 生成密钥并写入 .env"
            )
        _fernet = Fernet(key.encode())
    return _fernet


def generate_key():
    """生成一把新的 Fernet 密钥（写入 .env 并交付客户后启用）"""
    return Fernet.generate_key().decode()


def encrypt_order_no(order_no):
    """加密订单号，返回 URL 安全的密文字符串"""
    return _get_fernet().encrypt(str(order_no).encode("utf-8")).decode("ascii")


def decrypt_order_no(token):
    """
    解密订单号

    解密失败（密文无效/被篡改/密钥不一致/为空）统一返回 None，
    由调用方负责友好提示，不向外抛异常。
    """
    if not token:
        return None
    try:
        return _get_fernet().decrypt(str(token).encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：")
        print("  生成密钥：python -m app.services.order_share_service.crypto_service genkey")
        print("  加密演示：python -m app.services.order_share_service.crypto_service <订单号>")
    elif sys.argv[1] == "genkey":
        print(generate_key())
    else:
        print(f"密文：{encrypt_order_no(sys.argv[1])}")
