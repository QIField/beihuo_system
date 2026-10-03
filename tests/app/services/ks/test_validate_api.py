# -*- coding:utf-8 -*-
"""
测试开思新验证 API: /member/seller/menu-plus-star?key=PLUS_STAR_MENU
验证三种场景：无 cookie、错误 cookie、有效 cookie
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import requests

VALIDATE_URL = "https://www.cassmall.com/member/seller/menu-plus-star"
PARAMS = {"key": "PLUS_STAR_MENU"}


BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.cassmall.com/seller/",
    "X-Requested-With": "XMLHttpRequest",
}


def test_case(name, cookie=""):
    print(f"\n{'='*50}")
    print(f"测试场景: {name}")
    print(f"Cookie: {cookie[:50] if cookie else '(空)'}...")
    headers = dict(BASE_HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    try:
        r = requests.get(VALIDATE_URL, params=PARAMS, headers=headers, timeout=15, allow_redirects=False)
        print(f"状态码: {r.status_code}")
        print(f"响应头 Location: {r.headers.get('Location', '(无)')}")
        body = r.text[:300]
        print(f"响应体: {body}")
        try:
            js = r.json()
            print(f"JSON code: {js.get('code')}, msg: {js.get('errorMessage')}")
        except Exception:
            print("响应非 JSON")
    except Exception as e:
        print(f"请求异常: {e}")


if __name__ == "__main__":
    test_case("1. 无 Cookie", "")
    test_case("2. 错误 Cookie", "PHPSESSID=invalid_fake_cookie_12345")
    test_case("3. 随机格式 Cookie", "did=4fb28d7c-e95c-4969-ab6f-30ec4cea08bb; gr_user_id=94d7c4cc-cd63-4130-9c8c-92aaebd2ba14; \143\150\145\143\153\123\145\164\164\154\145\151\156=\164\162\165\145; Hm_lvt_2f121731faa435df7b173e563ee84747=1787022510,1787622592,1787877679,1788508232; HWWAFSESID=fdd608e77d99e37bb6; HWWAFSESTIME=1788657604855; WSESSIONID=c005a2c5-cb87-4b61-abcd-f3368be899f7; company_id=ecO2szp3JSljt2Nlwbv; security_userid=65d1a2a93b53ad0001338c73; userLoginId=65d1a2a93b53ad0001338c73; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2265d1a2a93b53ad0001338c73%22%2C%22first_id%22%3A%2219dfc3fc53bd6c-0c20de7faf1763-26061e51-1327104-19dfc3fc53c152f%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E5%BC%95%E8%8D%90%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fpassport.casstime.com%2F%22%7D%2C%22%24device_id%22%3A%2219dfc3fc53bd6c-0c20de7faf1763-26061e51-1327104-19dfc3fc53c152f%22%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTlkZmM0MDI2MDhhNi0wZTQ2NTIyYzNmMzViYTgtMjYwNjFlNTEtMTMyNzEwNC0xOWRmYzQwMjYwOTEwYWEiLCIkaWRlbnRpdHlfbG9naW5faWQiOiI2NWQxYTJhOTNiNTNhZDAwMDEzMzhjNzMifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%2265d1a2a93b53ad0001338c73%22%7D%7D; ad")
    test_case("4. 有效 Cookie", "did=4fb28d7c-e95c-4969-ab6f-30ec4cea08bb; gr_user_id=94d7c4cc-cd63-4130-9c8c-92aaebd2ba14; \143\150\145\143\153\123\145\164\164\154\145\151\156=\164\162\165\145; Hm_lvt_2f121731faa435df7b173e563ee84747=1787022510,1787622592,1787877679,1788508232; HWWAFSESID=fdd608e77d99e37bb6; HWWAFSESTIME=1788657604855; WSESSIONID=c005a2c5-cb87-4b61-abcd-f3368be899f7; company_id=ecO2szp3JSljt2Nlwbv; security_userid=65d1a2a93b53ad0001338c73; userLoginId=65d1a2a93b53ad0001338c73; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2265d1a2a93b53ad0001338c73%22%2C%22first_id%22%3A%2219dfc3fc53bd6c-0c20de7faf1763-26061e51-1327104-19dfc3fc53c152f%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E5%BC%95%E8%8D%90%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fpassport.casstime.com%2F%22%7D%2C%22%24device_id%22%3A%2219dfc3fc53bd6c-0c20de7faf1763-26061e51-1327104-19dfc3fc53c152f%22%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTlkZmM0MDI2MDhhNi0wZTQ2NTIyYzNmMzViYTgtMjYwNjFlNTEtMTMyNzEwNC0xOWRmYzQwMjYwOTEwYWEiLCIkaWRlbnRpdHlfbG9naW5faWQiOiI2NWQxYTJhOTNiNTNhZDAwMDEzMzhjNzMifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%2265d1a2a93b53ad0001338c73%22%7D%7D; adv-statistics=%5B%7B%22code%22%3A%22undefined%22%2C%22id%22%3A%2215374345757506030000%22%2C%22displayNum%22%3A1%7D%5D; PSESSIONID=573af6e5-f63b-42eb-b344-5256413d6519; ssoAuthCode=uAvWpW; security_context=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjYXNzbWFsbC5jb20iLCJzdWIiOiI2NWQxYTJhOTNiNTNhZDAwMDEzMzhjNzMiLCJncm91cFVzZXIiOiJmYWxzZSIsInJlcHJlc2VudGF0aXZlQ29tcGFueUlkIjoiZWNPMnN6cDNKU2xqdDJObHdidiIsInJlZ2lzdGVyQ29tcGxldGVkIjoidHJ1ZSIsImNvbXBhbnlUeXBlIjoiU1VQUExJRVIiLCJjcmVkZW50aWFsc05vbkV4cGlyZWQiOiJ0cnVlIiwiYWRkaXRpb25hbEluZm8iOiJ7YWNjb3VudElkPTY1ZDFhMmE5NzBlZmI2MDAwMTVmZDRhMn0iLCJhY2NvdW50Tm9uRXhwaXJlZCI6InRydWUiLCJwcm9kdWN0U3RvcmVJZCI6IkZTQkJSMDAxIiwiZW5hYmxlZCI6InRydWUiLCJ1c2VybmFtZSI6IjY1ZDFhMmE5M2I1M2FkMDAwMTMzOGM3MyIsImFjY291bnROb25Mb2NrZWQiOiJ0cnVlIiwiYW5kIjoiY2Fzc21hbGwiLCJqdGkiOiJjb3Z3a2piRTJBUGQ3akpDR2pEanFrSlBkeUt0ZXh2YSIsImlhdCI6MTc4ODY2MDAwOCwiZXhwIjoxNzg4Njk2MDA3fQ.Si0qqMsYVo83VOCoyUQzsUefri5AwcVEg4I1wy3BvQEFgx0hA974YDhnlD5foRj46DK_ENVOUyOxjKCa77OGfUZKUCVs-Rzsnw9ui93zSr8STKWsF8wE97-dvVjZmA6it6oU2I03LmyUuGB_SM5si8G1oUcUZgQQ9Ofv4mJ_wqc; _seller_active_menu_id_=SELLER_HOME; _seller_active_menu_url_=/seller#/merchant/home")

