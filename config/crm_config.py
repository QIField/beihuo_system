import requests
import json


def get_crm_cookies():
    """
    获取 CRM 系统的认证 cookie
    
    Returns:
        str: CRM 系统的认证 cookie
    """
    url = "http://113.45.176.129:8001/get_crm_cookies?key=fs"
    payload = {}
    request_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }
    response = requests.request("GET", url, headers=request_headers, data=payload)
    cookies = json.loads(response.text)['cookie']

    return cookies
