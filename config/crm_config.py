import requests
import json


def get_crm_cookies(key='fs'):
    """
    获取 CRM 系统的认证 cookie
    
    Args:
        key: 门店key，可选值：fs, zs, zh, hf, by，默认为fs
    
    Returns:
        dict: CRM 系统的认证 cookie
    """
    url = f"http://113.45.176.129:8001/get_crm_cookies?key={key}"
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


if __name__ == '__main__':
    # 测试四个不同的key
    keys = ['zs', 'zh', 'hf', 'by']
    
    for key in keys:
        try:
            print(f"\n测试 key={key}:")
            cookies = get_crm_cookies(key)
            print(f"  成功！返回cookie: {cookies}")
        except Exception as e:
            print(f"  失败！错误: {e}")
