# -*- coding:utf-8 -*-
"""
飞书任务同步 - 回调事件解密与签名校验

飞书事件订阅默认对请求体进行 AES-CBC 加密，需用 Encrypt Key 解密。
"""

import base64
import json
from hashlib import sha256
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from app.utils.orm.session import orm_session
from app.models.orm_models import BeihuoSystemConfig
from .config import LARK_ENCRYPT_KEY, get_current_env


def _get_encrypt_key():
    with orm_session() as session:
        config = session.query(BeihuoSystemConfig).filter(
            BeihuoSystemConfig.config_key == LARK_ENCRYPT_KEY,
            BeihuoSystemConfig.env == get_current_env(),
            BeihuoSystemConfig.status == 1,
        ).first()
        return config.config_value if config else None


def decrypt_lark_event(encrypt_msg):
    """
    解密飞书回调事件。

    飞书当前使用 AES-256-CBC 加密：
    - key = sha256(encrypt_key) 的 32 字节
    - iv 为密文前 16 字节（base64 解码后）
    - 填充方式为 PKCS7
    - 完整密文格式：base64(iv + encrypted_event)

    :param encrypt_msg: 飞书推送的 encrypt 字段
    :return: 解密后的 JSON 字典
    """
    encrypt_key = _get_encrypt_key()
    if not encrypt_key:
        raise ValueError("缺少飞书配置: lark_encrypt_key")

    # key 为 encrypt_key SHA256 后的 32 字节（AES-256）
    key = sha256(encrypt_key.encode('utf-8')).digest()

    # 飞书密文格式：base64(iv + encrypted_event)
    cipher_bytes = base64.b64decode(encrypt_msg)
    if len(cipher_bytes) < 16:
        raise ValueError("飞书回调密文长度不足")

    iv = cipher_bytes[:16]
    encrypted_event = cipher_bytes[16:]

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    plain_padded = decryptor.update(encrypted_event) + decryptor.finalize()

    # 去除 PKCS7 填充
    pad_len = plain_padded[-1]
    if pad_len > len(plain_padded) or pad_len == 0:
        raise ValueError("飞书回调密文填充错误")
    plain = plain_padded[:-pad_len].decode('utf-8')

    return json.loads(plain)
