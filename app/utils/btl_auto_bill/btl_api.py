# -*- coding: utf-8 -*-
"""巴图鲁业务接口"""

from datetime import datetime, timedelta

import urllib.parse

import requests

from .btl_auth import get_btl_cookie
from .btl_config import logger


def _get_btl_token():
    """从 cookie 中提取 token"""
    cookie = get_btl_cookie()
    token = cookie.split('auth._token.local=')[-1]
    return urllib.parse.unquote(token)


def _get_btl_headers():
    """构造巴图鲁请求 headers"""
    return {
        'Content-Type': 'application/json',
        'Token': _get_btl_token(),
        'Cookie': get_btl_cookie(),
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        ),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Origin': 'https://merchant.qipeipu.com',
        'Referer': 'https://merchant.qipeipu.com/'
    }


def query_inquiry_list(
    inquiry_view_status=1,
    page=0,
    count=20,
    begin_date=None,
    end_date=None,
    inquiry_no='',
    btr_org_id='',
    business_type='',
    parts_code='',
    car_brand_name='',
    car_system='',
    external_no=''
):
    """
    查询巴图鲁询价单列表

    :param inquiry_view_status: 询价视图状态，默认 1
    :param page: 页码，默认 0
    :param count: 每页数量，默认 20
    :param begin_date: 发布开始日期，格式 YYYY-MM-DD，默认 30 天前
    :param end_date: 发布结束日期，格式 YYYY-MM-DD，默认今天
    :param inquiry_no: 询价单号
    :param btr_org_id: 组织 ID
    :param business_type: 业务类型
    :param parts_code: 配件编码
    :param car_brand_name: 车辆品牌
    :param car_system: 车系
    :param external_no: 外部单号
    :return: dict，接口响应数据
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if begin_date is None:
        begin_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    url = 'https://merchant.qipeipu.com/api/quote/queryInquiryList'
    payload = {
        'inquiryViewStatus': inquiry_view_status,
        'inquiryNo': inquiry_no,
        'btrOrgId': btr_org_id,
        'businessType': business_type,
        'partsCode': parts_code,
        'carBrandName': car_brand_name,
        'carSystem': car_system,
        'externalNo': external_no,
        'times': [begin_date, end_date],
        'publishStartTime': begin_date,
        'publishEndTime': end_date,
        'pageDTO': {
            'page': page,
            'count': count
        }
    }

    logger.info(f'[巴图鲁] 查询询价单列表: page={page}, count={count}, status={inquiry_view_status}')
    resp = requests.post(url, headers=_get_btl_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()
