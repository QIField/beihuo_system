import requests
import time

USERNAME = "15699181808"
PASSWORD = "Bbr15699181808" 

def login(username=None, password=None):
    """登录开思平台，返回 session"""
    username = username or USERNAME
    password = password or PASSWORD
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
    })
    
    timestamp = int(time.time() * 1000)
    session.get(f"https://www.cassmall.com/passport/captcha/need?userName={username}&data={timestamp}")
    
    session.post(
        "https://www.cassmall.com/passport/agreements/save-client-agreement-record",
        json={"clientId": "CLIENT_CASS_WEB", "source": "LOGIN", "templateIds": ["695cdb1b91feb6000184644f", "6960a51527905000016b00ca", "66149865c7748b0001616030"], "userIdType": "USER_NAME", "userId": username, "userAgent": session.headers["User-Agent"]}
    )
    
    session.post(
        "https://www.cassmall.com/passport/login",
        data={"logintype": "PASSWORD", "username": username, "password": password, "msg": "", "cellphone": "", "verifycode": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        allow_redirects=False
    )
    
    session.get("https://www.cassmall.com/seller")
    session.cookies.set("_seller_active_menu_id_", "myOrder", domain=".cassmall.com")
    session.cookies.set("_seller_active_menu_url_", "/orders/seller/order/list", domain=".cassmall.com")
    
    return session