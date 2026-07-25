# -*- coding:utf-8 -*-
"""
data.gzbbr.com API 客户端

封装 Product.CompanyPrice 相关接口调用。
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional

import requests

from config.config_list_manager.config_cache import get_config_value
from app.utils.logger_config import get_task_logger


BASE_URL = "https://data.gzbbr.com"
INDEX_URL = f"{BASE_URL}/admin/Product.CompanyPrice/index"
UPDATE_URL = f"{BASE_URL}/admin/Product.CompanyPrice/update"

# 门店代码 -> 数据库配置键映射
STORE_CONFIG_KEY_MAP = {
    "fsbbr": "data_gzbbr_com_fs",
    "zhbbr": "data_gzbbr_com_zh",
    "zsbbr": "data_gzbbr_com_zs",
    "dgby": "data_gzbbr_com_by",
    "dghf": "data_gzbbr_com_hf",
}

DEFAULT_TIMEOUT = 30
RETRY_TIMES = 2


def _resolve_cookie(store_code: str) -> str:
    """根据门店代码从配置中心获取 Cookie 字符串"""
    config_key = STORE_CONFIG_KEY_MAP.get(store_code)
    if not config_key:
        raise ValueError(f"不支持的门店代码: {store_code}")

    raw = get_config_value(config_key)
    if raw is None:
        raise ValueError(f"未找到 {config_key} 的 Cookie 配置")

    if isinstance(raw, dict):
        return "; ".join([f"{k}={v}" for k, v in sorted(raw.items(), key=lambda x: x[0])])

    return str(raw)


def _timestamp_to_datetime_str(ts: Optional[Any]) -> str:
    """将 Unix 时间戳转换为 update 接口需要的字符串格式"""
    if ts is None or ts == "":
        return ""
    try:
        timestamp = int(ts)
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return str(ts)


class CookieExpiredError(Exception):
    """data.gzbbr.com Cookie 过期"""
    pass


# 登录跳转脚本，精确匹配则判定为 Cookie 过期
_LOGIN_REDIRECT_SCRIPT = '<script type="text/javascript">top.parent.frames.location.href="/admin/Login/index.html";</script>'


class DataGzbbrApiClient:
    """data.gzbbr.com 价格接口客户端"""

    def __init__(self, store_code: str, timeout: int = DEFAULT_TIMEOUT, logger=None):
        self.store_code = store_code
        self.timeout = timeout
        self.logger = logger or get_task_logger('data_gzbbr')
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/admin/Product.CompanyPrice/index.html",
            "Cookie": _resolve_cookie(store_code),
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        })

    def get_company_price(self, product_id: str) -> Dict[str, Any]:
        """
        查询产品公司价格信息

        :param product_id: 产品 ID
        :return: 接口返回的 JSON 数据
        """
        params = {"product_id": str(product_id)}
        data = {"order": "desc", "offset": 0, "limit": 20}
        return self._post(INDEX_URL, params=params, data=data)

    def update_company_price(self, base_info: Dict[str, Any], price: str, peer_price: str):
        """
        更新产品公司价格

        :param base_info: get_company_price 返回的 rows[0] 原始数据
        :param price: 开思价
        :param peer_price: 同行价
        :return: (payload_dict, response_dict) 元组
        """
        payload = {
            "status": base_info.get("status", 1),
            "company_price_id": base_info.get("company_price_id"),
            "product_id": base_info.get("product_id"),
            "company_id": base_info.get("company_id"),
            "price": price,
            "min_quantity": base_info.get("min_quantity", 1),
            "start_date": _timestamp_to_datetime_str(base_info.get("start_date")),
            "end_date": _timestamp_to_datetime_str(base_info.get("end_date")),
            "peer_price": peer_price,
            "maintenance_price": base_info.get("maintenance_price", "0.00"),
        }
        response = self._post(UPDATE_URL, data=payload)
        return payload, response

    def _post(self, url: str, data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """统一 POST 请求入口，带重试"""
        last_error = None
        for attempt in range(RETRY_TIMES + 1):
            try:
                self.logger.info("POST %s | params=%s | data=%s | attempt=%d", url, params, data, attempt + 1)
                response = self.session.post(url, params=params, data=data, timeout=self.timeout, verify=False)
                self.logger.info("response status=%d | text=%s", response.status_code, response.text[:1000])
                response.raise_for_status()

                text = response.text.strip()
                if text == _LOGIN_REDIRECT_SCRIPT:
                    raise CookieExpiredError("data.gzbbr.com Cookie 已过期，请联系管理员更新配置")

                return response.json()
            except Exception as e:
                last_error = e
                self.logger.error("request error: %s", e)
                if attempt < RETRY_TIMES:
                    time.sleep(1)

        raise last_error
