# -*- coding:utf-8 -*-
# @Time    : 2026/5/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : mercedes_dalfsc.py
# @Software: PyCharm

from app.scripts.spiders.spider_tool import SpiderTool
from app.scripts.spiders.spider_entities.mercedes_login import MercedesLoginService


class MercedesDalfscSpider:
    """
    奔驰大库网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """
    # 网站固定配置
    BASE_URL = "https://dalfsc.aftersales.mercedes-benz.com"

    def __init__(self, timeout=10, retry_count=3):
        # 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 直接通过 MercedesLoginService 获取验证通过的 cookie
        self.cookie = MercedesLoginService.get_valid_config()

    def _get_auth_header(self):
        """私有方法：统一生成认证请求头（复用）"""
        return {"Cookie": self.cookie}

    # ===================== 业务接口 =====================

    # https://dalfsc.aftersales.mercedes-benz.com/api/sop-china/parts-informations
    def get_parts_informations(self, part_number, customer_id, sales_organization_id):
        """
        获取零件信息
        :param part_number: 零件编号
        :param customer_id: 客户ID
        :param sales_organization_id: 销售组织ID
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/api/sop-china/parts-informations"
        params = {
            "partNumber": part_number,
            "customerId": customer_id,
            "salesOrganizationId": sales_organization_id
        }
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求参数】", params)
        # ==================================
        return self.spider_tool.fetch(url, method="GET", params=params, headers=self._get_auth_header())

    # https://dalfsc.aftersales.mercedes-benz.com/api/sop-china/stockinformation
    def get_stock_information(self, part_numbers):
        """
        获取库存信息
        :param part_numbers: 零件编号列表
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/api/sop-china/stockinformation"
        
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求方法】", "POST")
        print("【请求负载】", part_numbers)
        # ==================================
        
        return self.spider_tool.fetch(
            url=url,
            method="POST",
            json=part_numbers,
            headers=self._get_auth_header()
        )


    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()
