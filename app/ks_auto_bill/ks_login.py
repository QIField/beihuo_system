import requests
import time
import sys
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

# 从 model 导入配置
from app.utils.ks_auto_bill_model import COMPANY_CONFIG, COMPANIES, get_company_key
from app.ks_auto_bill.log import ks_log


def login_with_cookie_api(company='fsbbr'):
    """使用 Cookie 接口登录指定公司"""
    key = get_company_key(company)
    cookie_api_url = f"http://113.45.176.129:8001/md_ks.get_cookies?md={key}"

    try:
        ks_log("尝试使用 Cookie 接口登录...", module="登录")
        response = requests.get(cookie_api_url, timeout=10)
        if response.status_code != 200:
            ks_log(f"Cookie 接口请求失败，状态码: {response.status_code}", module="登录")
            return None

        data = response.json()
        cookie_dict = data.get("cookie", {})

        if not cookie_dict:
            ks_log("Cookie 接口返回空 cookie", module="登录")
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

        ks_log("Cookie 接口登录成功", module="登录")
        return session
    except Exception as e:
        ks_log(f"Cookie 接口登录失败: {e}", module="登录")
        return None


def login(company='fsbbr'):
    """登录开思平台，使用 Cookie 接口"""
    return login_with_cookie_api(company)
