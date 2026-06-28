# -*- coding:utf-8 -*-
# @Time    : 2026/5/6 16:04
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : cassmall.py
# @Software: PyCharm


from app.scripts.spiders.spider_entities.cassmall_login import get_cookie_dict
from app.scripts.spiders.spider_tool import SpiderTool


class CassmallSpider:
    """
    开思mall网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """
    # 网站固定配置
    BASE_URL = "https://www.cassmall.com"

    def __init__(self, cookie=None, key="fs", timeout=10, retry_count=3):
        # 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 必传Cookie（业务私有属性）
        if cookie is None:
            self.cookie = self._set_cookie(key)
        else:
            self.cookie = cookie



    def _set_cookie(self,key):
        """
        设置Cookie
        :param cookie: Cookie字符串
        """
        cookie_dict = get_cookie_dict(key)

        # 按Cookie键名的字母顺序排序，模拟浏览器发送Cookie的顺序
        # 使用sorted()对字典项按key排序，确保生成的Cookie字符串顺序一致
        cookie = "; ".join([f"{k}={v}" for k, v in sorted(cookie_dict.items(), key=lambda x: x[0])])    # pyright: ignore[reportOptionalMemberAccess]
        return cookie
        
        
    def _get_auth_header(self):
        """私有方法：统一生成认证请求头（复用）"""
        return {"Cookie": self.cookie}

    # ===================== 业务接口 =====================

    # https://www.cassmall.com/sellerMgr/product/all/listByPage
    def get_product_list(self, internal_name="", parts_no="", brand_ids=None, status_id="",
                         start_date="", end_date="", product_name="", product_scope="N",
                         product_tag="ALL", page_num=1, page_size=20):
        """
        获取产品列表
        :param internal_name: 内部名称
        :param parts_no: 零件号
        :param brand_ids: 品牌ID列表
        :param status_id: 状态ID
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param product_name: 产品名称
        :param product_scope: 产品范围
        :param product_tag: 产品标签
        :param page_num: 页码
        :param page_size: 每页数量
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/sellerMgr/product/all/listByPage"
        
        # 构建请求负载
        payload = {
            "internalName": internal_name,
            "partsNo": parts_no,
            "brandIds": brand_ids if brand_ids is not None else [],
            "statusId": status_id,
            "startDate": start_date,
            "endDate": end_date,
            "productName": product_name,
            "productScope": product_scope,
            "productTag": product_tag,
            "pageNum": page_num,
            "pageSize": page_size
        }
        
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求方法】", "POST")
        print("【请求负载】", payload)
        # ==================================
        
        return self.spider_tool.fetch(
            url=url,
            method="POST",
            json=payload,
            headers=self._get_auth_header()
        )

    def test_cookie(self):
        """
        测试 Cookie 是否有效
        :return: (是否有效, 错误信息
        """
        try:
            # 使用一个简单的接口来测试 cookie，比如获取产品列表的第一页
            url = f"{self.BASE_URL}/sellerMgr/product/all/listByPage"
            payload = {
                "pageNum": 1,
                "pageSize": 1
            }
            
            response = self.spider_tool.fetch(
                url=url,
                method="POST",
                json=payload,
                headers=self._get_auth_header()
            )
            
            if not response:
                return False, "请求失败"
            
            # 检查状态码
            if response.status_code == 401 or response.status_code == 403:
                return False, f"Cookie 已过期或无效 (HTTP状态码: {response.status_code}"
            
            try:
                json_data = response.json()
                # 根据实际响应结构判断是否成功
                # 这里假设如果有 code 字段或者能正常解析 JSON 就认为成功
                # 如果响应中有错误信息也可以判断
                if isinstance(json_data, dict):
                    code = json_data.get("code")
                    message = json_data.get("message", "")
                    if code and str(code) not in ["0", "200", "success"]:
                        return False, f"接口返回错误: {message} (code: {code})"
                return True, "Cookie 有效"
            except Exception as e:
                return False, f"解析响应失败: {str(e)}"
                
        except Exception as e:
            return False, f"测试 Cookie 时发生异常: {str(e)}"

    def get_inventorys(self, product_ids):
        """
        获取产品库存信息
        :param product_ids: 产品ID列表
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/sellerMgr/product/inventorysV2"
        
        # 构建请求负载
        payload = {
            "productIds": product_ids
        }
        
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求方法】", "POST")
        print("【请求负载】", payload)
        # ==================================
        
        return self.spider_tool.fetch(
            url=url,
            method="POST",
            json=payload,
            headers=self._get_auth_header()
        )

    def update_inventory_batch(self, inventory_list):
        """
        更新产品库存（支持单个产品多仓库或多个产品多仓库更新）
        :param inventory_list: 库存列表，每个元素包含 facilityId, availableToPromiseTotal, safeToPromiseTotal, productId
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/sellerMgr/product/updateInventoryBatchByProductId"
        
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求方法】", "POST")
        print("【请求负载】", inventory_list)
        # ==================================
        
        return self.spider_tool.fetch(
            url=url,
            method="POST",
            json=inventory_list,
            headers=self._get_auth_header()
        )

 


    def update_product_status(self, product_ids):
        """
        批量上架产品
        :param product_ids: 产品ID列表，如 ["21600375463843921950"]
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/sellerMgr/product/status/PRODUCT_ADDED"
        
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求方法】", "POST")
        print("【请求负载】", product_ids)
        # ==================================
        
        return self.spider_tool.fetch(
            url=url,
            method="POST",
            json=product_ids,
            headers=self._get_auth_header()
        )

    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()
