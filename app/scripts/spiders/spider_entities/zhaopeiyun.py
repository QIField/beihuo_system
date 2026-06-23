# -*- coding:utf-8 -*-
# @Time    : 2026/6/22
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : zhaopeiyun.py
# @Software : PyCharm

import time
from app.scripts.spiders.spider_tool import SpiderTool


class ZhaoPeiYunSpider:
    """
    找配云(zhaopeiyun.com) 网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """

    # 网站固定配置
    BASE_URL = "https://www.zhaopeiyun.com"

    def __init__(self, token=None, timeout=10, retry_count=3):
        # 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 可选：业务 Token（如果接口需要鉴权则传入）
        self.token = token

    def _get_auth_header(self):
        """私有方法：统一生成认证请求头（复用）"""
        headers = {}
        if self.token:
            headers["Authorization"] = self.token
        return headers

    def _get_timestamp(self):
        """生成当前时间戳（毫秒级）"""
        return str(int(time.time() * 1000))

    # ===================== 业务接口 =====================

    # https://www.zhaopeiyun.com/zpc/b2b/stock/oe/detail
    def get_oe_detail(self, brand_code=None, part_code=None, from_source=2, silence=True):
        """
        获取 OE 零件库存详情
        :param brand_code: 品牌编码，如 "bmw"
        :param part_code: 零件号，如 "16117474992"
        :param from_source: 来源标识，默认 2
        :param silence: 静默模式标识，默认 true
        :return: requests.Response 对象
        """
        url = f"{self.BASE_URL}/zpc/b2b/stock/oe/detail"
        params = {
            "brandCode": brand_code,
            "partCode": part_code,
            "from": from_source,
            "silence": str(silence).lower() if isinstance(silence, bool) else silence,
            "t": self._get_timestamp(),
        }
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求参数】", params)
        # ==================================
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())

    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()
