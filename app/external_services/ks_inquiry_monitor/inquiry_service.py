"""
开思询价单查询服务
"""
import requests
import time
from datetime import datetime
from typing import Dict, List

STORES = {'fs': '佛山', 'zs': '中山', 'zh': '珠海', 'hf': '合峰', 'by': '百业'}
COOKIE_API_URL = "http://113.45.176.129:8001/md_ks.get_cookies"
CASS_API_URL = "https://www.cassmall.com/inquiry/seller/quote/list/v1"
ALERT_THRESHOLD = 7

# 全局缓存
_cache = {'data': None, 'time': 0, 'alert': False}
CACHE_TTL = 600  # 10分钟


def get_store_cookie(md_code: str) -> dict:
    try:
        resp = requests.get(f"{COOKIE_API_URL}?md={md_code}", timeout=10)
        return resp.json().get('cookie', {}) if resp.status_code == 200 else {}
    except:
        return {}


def fetch_quote_list(cookie_dict: dict) -> dict:
    now = datetime.now()
    start = int(now.replace(hour=0, minute=0, second=0).timestamp() * 1000)
    end = int(now.replace(hour=23, minute=59, second=59).timestamp() * 1000)
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

    payload = {
        "inquiryType": "ALL", "navTab": "UNCLAIMED", "onlyViewOwner": False,
        "storeId": "ALL", "inquiryId": "", "statusId": "ALL",
        "garageCompanyId": "", "quoteUser": cookie_dict.get('security_userid', ''),
        "quoteType": "ALL", "systemQuoteReportStatus": "", "quoteScope": "ALL",
        "limitQuoteRange": False, "saasGroupLabels": ["ALL"],
        "startDate": start, "endDate": end, "pageNum": 1, "pageSize": 20
    }

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Cookie': cookie_str,
        'Referer': 'https://www.cassmall.com/seller',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        resp = requests.post(CASS_API_URL, json=payload, headers=headers, timeout=30)
        return resp.json() if 'application/json' in resp.headers.get('Content-Type', '') else {}
    except:
        return {}


def get_store_stats(md_code: str) -> dict:
    cookie = get_store_cookie(md_code)
    if not cookie:
        return {'store_name': STORES[md_code], 'md_code': md_code, 'unclaimed_count': 0, 'quoted_count': 0, 'unquoted_count': 0}

    data = fetch_quote_list(cookie)
    d = data.get('data', {}) if data.get('code') == 200 else {}

    return {
        'store_name': STORES[md_code],
        'md_code': md_code,
        'unclaimed_count': d.get('unclaimedCount', 0),
        'quoted_count': d.get('quotedCount', 0),
        'unquoted_count': d.get('unquotedCount', 0)
    }


def get_all_stats(force_refresh: bool = False) -> dict:
    """获取所有门店数据，带缓存"""
    global _cache

    now = time.time()
    if not force_refresh and _cache['data'] and now - _cache['time'] < CACHE_TTL:
        return _cache['data']

    stores = [get_store_stats(md) for md in STORES.keys()]
    alert = any(s['unclaimed_count'] > ALERT_THRESHOLD for s in stores)

    result = {
        'stores': stores,
        'alert': alert,
        'update_time': datetime.now().strftime('%H:%M:%S')
    }

    _cache = {'data': result, 'time': now, 'alert': alert}
    return result


def get_cached_stats() -> dict:
    """获取缓存数据（供WebSocket使用）"""
    return _cache['data'] or get_all_stats()
