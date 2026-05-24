# -*- coding:utf-8 -*-
# @Time    : 2026/5/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : mercedes_dalfsc.py
# @Software: PyCharm

from app.scripts.spiders.spider_tool import SpiderTool


class MercedesDalfscSpider:
    """
    奔驰大库网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """
    # 网站固定配置
    BASE_URL = "https://dalfsc.aftersales.mercedes-benz.com"

    def __init__(self, cookie, timeout=10, retry_count=3):
        # 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 必传Cookie（业务私有属性）
        self.cookie = cookie

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

    def validate_cookie(self, test_part_number="A0002521620", test_customer_id="193211390", test_sales_organization_id="O 50000741"):
        """
        验证 Cookie 是否有效或是否过期
        通过尝试请求一个简单的接口来验证
        
        :param test_part_number: 用于验证的零件编号
        :param test_customer_id: 用于验证的客户ID
        :param test_sales_organization_id: 用于验证的销售组织ID
        :return: (是否有效, 错误信息)
        """
        try:
            # 使用传入的参数验证cookie
            response = self.get_parts_informations(test_part_number, test_customer_id, test_sales_organization_id)
            
            if not response:
                return False, "请求失败，无法验证Cookie"
            
            # 检查响应状态码
            if response.status_code == 401:
                return False, "Cookie已过期或无效（401未授权）"
            elif response.status_code == 403:
                return False, "Cookie权限不足（403禁止访问）"
            elif response.status_code != 200:
                return False, f"请求返回异常状态码：{response.status_code}"
            
            # 尝试解析响应
            try:
                data = response.json()
                # 如果能正常解析JSON，说明cookie有效
                return True, ""
            except:
                # 即使不是JSON，只要状态码是200也认为cookie有效
                return True, ""
                
        except Exception as e:
            return False, f"验证Cookie时发生异常：{str(e)}"
    
    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()
