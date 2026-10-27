"""
卡思商城（cassmall.com）HTTP 请求封装

cookie 由调用方传入（页面填写的登录 cookie），不在本模块存储。
请求头与原脚本逐项一致。
"""

import json

import requests

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36')

LIST_URL = ('https://www.cassmall.com/market/inquirys?viewIndex={view_index}&inquirers=ALL'
            '&viewSize={view_size}&createdStartDate={start}&createdEndDate={end}')
GUIDE_URL = 'https://www.cassmall.com/inquiry/market/quotation-product/purchase-guide'
DETAIL_URL = 'https://www.cassmall.com/inquiryWeb/detail/{inquiryid}'
ARCHIVE_URL = 'https://www.cassmall.com/archiveinquiry/inquiryDetailData/{inquiryid}'


def _base_headers(cookie):
    return {
        'authority': 'www.cassmall.com',
        'user-agent': USER_AGENT,
        'accept-language': 'zh-CN,zh;q=0.9',
        'cookie': cookie,
    }


def fetch_list_page(session, cookie, view_index, view_size, start_date, end_date):
    """列表页（HTML）；返回响应文本，非 200 返回 None（由编排层决定终止）"""
    url = LIST_URL.format(view_index=view_index, view_size=view_size,
                          start=start_date, end=end_date)
    headers = _base_headers(cookie)
    headers.update({
        'cache-control': 'max-age=0',
        'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'upgrade-insecure-requests': '1',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': 'https://www.cassmall.com/market/portal',
    })
    response = session.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        return None
    return response.text


def fetch_purchase_guide(session, cookie, inquiryid):
    """采购指导（卖点标签映射）；任何异常返回空 dict（与原脚本一致）"""
    headers = _base_headers(cookie)
    headers.update({
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://www.cassmall.com',
        'referer': 'https://www.cassmall.com/garage/inquiry/',
    })
    try:
        response = session.post(GUIDE_URL, headers=headers,
                                data=json.dumps({'demandId': str(inquiryid)}), timeout=30)
        re_js = json.loads(response.text)
        if re_js['code'] == 200:
            return {str(item['quotationProductId']): item['sellingPoint']['sellingPointTag']
                    for item in re_js['data']}
    except Exception:
        pass
    return {}


def fetch_detail(session, cookie, inquiryid):
    """询单明细（JSON）；code != 200 返回 None（由编排层走归档接口）"""
    return _fetch_json(session, cookie, DETAIL_URL.format(inquiryid=inquiryid))


def fetch_archive_detail(session, cookie, inquiryid):
    """归档询单明细（JSON）；返回原始 json（由解析层判断 data.status）"""
    return _fetch_json(session, cookie, ARCHIVE_URL.format(inquiryid=inquiryid))


def _fetch_json(session, cookie, url):
    headers = _base_headers(cookie)
    headers.update({
        'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96"',
        'accept': 'application/json, text/plain, */*',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.cassmall.com/mall/inquiry/',
    })
    response = session.get(url, headers=headers, timeout=30)
    return json.loads(response.text)
