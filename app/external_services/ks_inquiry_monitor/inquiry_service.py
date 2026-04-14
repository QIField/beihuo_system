"""
开思询价单查询服务 - 数据库版
使用数据库替代内存缓存
"""
import requests
import time
from datetime import datetime
from typing import Dict, List

from app.utils.database_connection import get_db_connection, db_cursor

STORES = {'fs': '佛山', 'zs': '中山', 'zh': '珠海', 'hf': '合峰', 'by': '百业'}
COOKIE_API_URL = "http://113.45.176.129:8001/md_ks.get_cookies"
CASS_API_URL = "https://www.cassmall.com/inquiry/seller/quote/list/v1"
ALERT_THRESHOLD = 7


def init_monitor_table():
    """初始化监控表（如果不存在）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_ks_inquiry_monitor (
                id INT AUTO_INCREMENT PRIMARY KEY,
                store_code VARCHAR(10) NOT NULL,
                store_name VARCHAR(50) NOT NULL,
                unclaimed_count INT DEFAULT 0,
                quoted_count INT DEFAULT 0,
                unquoted_count INT DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_store (store_code),
                INDEX idx_updated_at (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_table_sql)
    finally:
        conn.close()


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
        "storeId": "ALL", "inquiryId": "", "statusId": "UNCLAIMED",
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
    """获取单个门店统计数据（复用原函数）"""
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


def save_stats_to_db(stores_data: list):
    """保存统计数据到数据库（先清空再插入）"""
    init_monitor_table()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 清空表
            cursor.execute("TRUNCATE TABLE crmapp_ks_inquiry_monitor")
            
            # 插入新数据
            sql = """
                INSERT INTO crmapp_ks_inquiry_monitor 
                (store_code, store_name, unclaimed_count, quoted_count, unquoted_count)
                VALUES (%s, %s, %s, %s, %s)
            """
            for store in stores_data:
                cursor.execute(sql, (
                    store['md_code'],
                    store['store_name'],
                    store['unclaimed_count'],
                    store['quoted_count'],
                    store['unquoted_count']
                ))
        conn.commit()
    except Exception as e:
        print(f"[询价单监控] 保存数据到数据库失败: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_stats_from_db() -> list:
    """从数据库获取统计数据"""
    try:
        with db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT store_code as md_code, store_name, 
                       unclaimed_count, quoted_count, unquoted_count
                FROM crmapp_ks_inquiry_monitor
                ORDER BY store_code
            """)
            results = cursor.fetchall()
            print(f"[询价单监控] 从数据库读取到 {len(results)} 条数据: {results}")
            return results
    except Exception as e:
        print(f"[询价单监控] 从数据库读取数据失败: {e}")
        return []


def get_all_stats(force_refresh: bool = False) -> dict:
    """
    获取所有门店数据
    优先从数据库读取，如果数据库为空或强制刷新，则实时获取并保存到数据库
    """
    stores = []

    if not force_refresh:
        # 先尝试从数据库读取
        stores = get_stats_from_db()
        print(f"[询价单监控] get_all_stats 从数据库获取: {len(stores)} 条")

    # 如果数据库没有数据或强制刷新，实时获取
    if not stores or force_refresh:
        print(f"[询价单监控] 数据库为空或强制刷新，实时获取数据...")
        stores = [get_store_stats(md) for md in STORES.keys()]
        print(f"[询价单监控] 实时获取到 {len(stores)} 条数据")
        if stores:
            save_stats_to_db(stores)

    alert = any(s['unclaimed_count'] > ALERT_THRESHOLD for s in stores)

    result = {
        'stores': stores,
        'alert': alert,
        'update_time': datetime.now().strftime('%H:%M:%S')
    }
    print(f"[询价单监控] 返回数据: stores={len(stores)}, alert={alert}")
    return result


def get_cached_stats() -> dict:
    """获取缓存数据（供WebSocket使用）- 现在从数据库读取"""
    return get_all_stats()
