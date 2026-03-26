import requests
import time

COOKIE_API_URL = "http://113.45.176.129:8001/md_ks.get_cookies?md=fs"


def login_with_cookie_api():
    """使用 Cookie 接口登录"""
    try:
        print("[开思登录] 尝试使用 Cookie 接口登录...")
        response = requests.get(COOKIE_API_URL, timeout=10)
        if response.status_code != 200:
            print(f"[开思登录] Cookie 接口请求失败，状态码: {response.status_code}")
            return None

        data = response.json()
        cookie_dict = data.get("cookie", {})

        if not cookie_dict:
            print("[开思登录] Cookie 接口返回空 cookie")
            return None

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
        })

        for key, value in cookie_dict.items():
            session.cookies.set(key, value, domain=".cassmall.com")

        session.get("https://www.cassmall.com/seller")
        session.cookies.set("_seller_active_menu_id_", "myOrder", domain=".cassmall.com")
        session.cookies.set("_seller_active_menu_url_", "/orders/seller/order/list", domain=".cassmall.com")

        print("[开思登录] Cookie 接口登录成功")
        return session
    except Exception as e:
        print(f"[开思登录] Cookie 接口登录失败: {e}")
        return None


def login():
    """登录开思平台，使用 Cookie 接口"""
    return login_with_cookie_api()
