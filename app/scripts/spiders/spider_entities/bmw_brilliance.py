# -*- coding:utf-8 -*-
# @Time    : 2026/6/12
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_brilliance.py
# @Software : PyCharm
# 华晨宝马网站专用业务爬虫
# 职责：只负责发起 HTTP 请求，拿到原始 HTML 响应
# 解析/清洗逻辑：请见 pipeline_clean.bmw_brilliance_clear.py
# =====================================================================

import datetime

# ========== curl_cffi：伪造 Chrome TLS 指纹 ==========
try:
    from curl_cffi import requests as curl_cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️  未检测到 curl_cffi 库，请执行: pip install curl_cffi")


class BMWBrillianceSpider:
    """
    华晨宝马库存系统爬虫
    职责：构造请求头、发起 curl_cffi 请求
    不做任何解析（解析逻辑在 pipeline_clean 中）
    """

    # 网站固定配置
    BASE_URL = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev"

    def __init__(self, cookie, timeout=10, retry_count=3):
        """
        :param cookie: 从 Hoppscotch/浏览器复制的完整 Cookie
        :param timeout: 请求超时（秒）
        :param retry_count: 保留参数（暂未启用自动重试，可在外部实现）
        """
        self.cookie = cookie
        self.timeout = timeout
        self.retry_count = retry_count

    # ============= 内部工具 =============

    def _get_auth_header(self):
        """构造 Chrome 风格的请求头（含 Cookie）"""
        return {
            "Cookie": self.cookie,
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Authorization": "Basic NDc5ODhQQVI6MldTWDNFREM0UkZWNVRHQg==",
            "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "frame",
            "Referer": self.BASE_URL,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

    def _curl_cffi_request(self, url, method="GET", params=None, data=None, extra_headers=None):
        """
        通用请求入口（内部使用 curl_cffi）
        :param url: 请求 URL
        :param method: GET / POST
        :param params: GET 查询参数
        :param data: POST 表单数据
        :param extra_headers: 额外请求头（覆盖默认头）
        :return: curl_cffi Response 对象（API 与 requests.Response 兼容），失败返回 None
        """
        if not CURL_CFFI_AVAILABLE:
            return None

        headers = self._get_auth_header()
        if extra_headers:
            headers.update(extra_headers)

        try:
            method = method.upper()
            if method == "POST":
                resp = curl_cffi_requests.post(
                    url,
                    headers=headers,
                    data=data,
                    impersonate="chrome",   # ← 核心：伪造 Chrome TLS 指纹
                    timeout=self.timeout,
                    verify=False,
                    allow_redirects=True
                )
            elif method == "GET":
                resp = curl_cffi_requests.get(
                    url,
                    headers=headers,
                    params=params,
                    impersonate="chrome",   # ← 核心：伪造 Chrome TLS 指纹
                    timeout=self.timeout,
                    verify=False,
                    allow_redirects=True
                )
            else:
                print(f"⚠️  不支持的请求方法: {method}")
                return None

            if resp.status_code != 200:
                print(f"请求失败 | URL: {url} | 状态码: {resp.status_code}")

            return resp

        except Exception as e:
            print(f"请求异常 | URL: {url} | 错误: {e}")
            return None

    # ============= 业务接口 =============

    def get_stock_check(self, oe):
        """
        查询【库存查询】接口 —— 只发起请求，返回原始 HTML 响应
        :param oe: 零件号，如 "36121116326
        :return: curl_cffi Response 对象（.text 就是 HTML 原文）
        """
        url = f"{self.BASE_URL}/spp05_stock_check.htm"
        today = str(datetime.datetime.today())[:10]

        payload = (
            f"onInputProcessing=atp_all&contentClip=&req_date={today}"
            f"&material={oe}&x=7&y=5"
        )

        extra_headers = {
            "Origin": "https://www.dwp.bmw-brilliance.cn",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": url,
        }

        return self._curl_cffi_request(url, "POST", data=payload, extra_headers=extra_headers)

    def get_material_details(self, oe):
        """
        查询【零件详情】接口 —— 只发起请求，返回原始 HTML 响应
        :param oe: 零件号，如 "36121116326
        :return: curl_cffi Response 对象
        """
        url = f"{self.BASE_URL}/spp05_material_details.htm"
        params = {"if_material": str(oe)}

        extra_headers = {
            "Referer": f"{self.BASE_URL}/SPP05_Stock_RESULT.htm",
        }

        return self._curl_cffi_request(url, "GET", params=params, extra_headers=extra_headers)
