# -*- coding:utf-8 -*-
"""
飞书任务同步 - 回调事件解密与签名校验

飞书事件订阅默认对请求体进行 AES-CBC 加密，需用 Encrypt Key 解密。
"""

import base64
import json
from hashlib import md5
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

    :param encrypt_msg: 飞书推送的 encrypt 字段
    :return: 解密后的 JSON 字典
    """
    encrypt_key = _get_encrypt_key()
    if not encrypt_key:
        raise ValueError("缺少飞书配置: lark_encrypt_key")

    # key 为 encrypt_key 的 MD5 前 16 字节
    key = md5(encrypt_key.encode('utf-8')).digest()[:16]

    # 飞书加密数据为 base64(AES密文)
    cipher_bytes = base64.b64decode(encrypt_msg)

    # AES-CBC，IV 固定为 16 字节 0
    iv = bytes(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    plain_padded = decryptor.update(cipher_bytes) + decryptor.finalize()

    # 去除 PKCS7 填充
    pad_len = plain_padded[-1]
    plain = plain_padded[:-pad_len].decode('utf-8')

    return json.loads(plain)
