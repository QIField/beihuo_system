# -*- coding:utf-8 -*-
# @Time    : 2026/06/24 11:41
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : cassmall_login.py
# @Software: trae-cn



import requests

from app.utils.ks_auto_bill_model import get_company_key


def get_cookie_dict(key='fs'):
    """使用 Cookie 接口登录指定公司"""
   
    cookie_api_url = f"http://113.45.176.129:8001/md_ks.get_cookies?md={key}"

    try:
        print(f"[开思登录][{key}] 尝试使用 Cookie 接口登录...")
        response = requests.get(cookie_api_url, timeout=10)
        if response.status_code != 200:
            print(f"[开思登录][{key}] Cookie 接口请求失败，状态码: {response.status_code}")
            return None

        data = response.json()
        cookie_dict = data.get("cookie", {})
      
        if not cookie_dict:
            print(f"[开思登录][{key}] Cookie 接口返回空 cookie")
            return None

       

        print(f"[开思登录][{key}] Cookie 接口登录成功")
        return cookie_dict
    except Exception as e:
        print(f"[开思登录][{key}] Cookie 接口登录失败: {e}")
        return None

