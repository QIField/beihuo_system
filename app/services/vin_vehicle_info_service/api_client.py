#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VIN 车辆信息 API 客户端
封装开思 mall 爬虫，获取 catalog HTML
"""

import logging

from app.scripts.spiders.spider_entities.cassmall import CassmallSpider

logger = logging.getLogger('vin_vehicle_info_sync')


class VinVehicleInfoApiClient:
    """VIN 信息查询客户端"""

    def __init__(self, key='fs'):
        self.spider = CassmallSpider(key=key)

    def fetch_catalog_html(self, vin_code):
        """
        根据 VIN 码抓取 catalog 页面 HTML

        :param vin_code: VIN 码
        :return: HTML 字符串，失败返回 None
        """
        response = self.spider.get_maindata_catalog(vin_code)
        if response is None:
            logger.warning(f"[VIN API] 请求无响应，跳过: {vin_code}")
            return None
        response.raise_for_status()
        return response.text

    def close(self):
        """关闭底层会话"""
        self.spider.close()
