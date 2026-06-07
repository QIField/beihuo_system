# -*- coding:utf-8 -*-
# @Time    : 2026/6/5
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_brilliance.py
# @Software: PyCharm

import datetime
from app.scripts.spiders.spider_tool import SpiderTool


class BMWBrillianceSpider:
    """
    华晨宝马网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """
    # 网站固定配置
    BASE_URL = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev"

    def __init__(self, cookie, timeout=10, retry_count=3):
        # 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        self.session = self.spider_tool.session
        # 必传Cookie（业务私有属性）
        self.cookie = cookie

    def _direct_request(self, url, method="GET", params=None, json=None, data=None, headers=None, verify=True):
        """
        直接使用 requests 发送请求，支持更多参数
        
        Args:
            url: 请求URL
            method: 请求方法
            params: 查询参数
            json: JSON数据
            data: 表单数据
            headers: 请求头
            verify: 是否验证SSL证书
            
        Returns:
            Response对象
        """
        req_headers = self.session.headers.copy()  # pyright: ignore[reportAttributeAccessIssue]
        if headers:
            req_headers.update(headers)

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json,
                data=data,
                headers=req_headers,
                timeout=self.spider_tool.timeout,
                verify=verify
            )

            if response.status_code != 200:
                print(f"请求失败 | URL: {url} | 状态码: {response.status_code}")

            return response

        except Exception as e:
            print(f"请求异常 | URL: {url} | 错误: {str(e)}")
        
        return None

    def _get_auth_header(self):
        """私有方法：统一生成认证请求头（复用）"""
        return {
            "Cookie": self.cookie,
            "Connection": "keep-alive",
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
            "Accept-Language": "zh-CN,zh;q=0.9"
        }

    # ===================== 业务接口 =====================

    def get_stock_check(self, oe):
        """
        查询零件库存信息
        :param oe: 零件号
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/spp05_stock_check.htm"
        today = str(datetime.datetime.today())[:10]
        
        payload = {
            "onInputProcessing": "atp_all",
            "contentClip": "",
            "req_date": today,
            "material": oe,
            "x": "7",
            "y": "5"
        }
        
        headers = self._get_auth_header()
        headers["Cache-Control"] = "max-age=0"
        headers["Origin"] = "https://www.dwp.bmw-brilliance.cn"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Referer"] = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/spp05_stock_check.htm"
        
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求方法】", "POST")
        print("【请求负载】", payload)
        # ==================================
        
        return self._direct_request(
            url=url,
            method="POST",
            data=payload,
            headers=headers,
            verify=False
        )

    def get_material_details(self, oe):
        """
        查询零件详细信息
        :param oe: 零件号
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/spp05_material_details.htm"
        params = {
            "if_material": str(oe)
        }
        
        headers = self._get_auth_header()
        headers["Referer"] = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/SPP05_Stock_RESULT.htm"
        
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求参数】", params)
        # ==================================
        
        return self._direct_request(
            url=url,
            method="GET",
            params=params,
            headers=headers,
            verify=False
        )

    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()


if __name__ == "__main__":
    # 测试代码
    print("=" * 50)
    print("BMWBrillianceSpider 测试")
    print("=" * 50)
    
    # 示例：这里需要填入真实的 Cookie
    test_cookie ='sap-contextid=SID%3aANON%3apcqpdi46_CQP_46%3abbo2ItjCpkL7ZP0Qa5rHXUnqul9TMzz5nB5tqhVQ-NEW; TS0190948c=014e90d2cd939a5eadf13a300ee0b6a628615d9453b6499a10aa961f65a75942ccbf4ecbaa1bb28699f768a10276494fabcbdedd6742d377c430c2fa1a33b4df9b4371ac0a81a13ea27925b75af2aa9366f3857be1d2bca3758da2847e9b99be14e695ff33604fb3e7d86e42f161af85aa3989adf8fc54e5d0f5f921dc1c294f124ff2547b9549a84cf1b3b67dfec898f070ef1cafc14b9a4579cf3e1e7c6a405334c6d7a1eaf01e779cb45160d10e8e914b5c3607d1d60106d089a1c8b094022723316eef28c4a887592555d5fb89f45f7ea74d94092ccd8e3eab5ca71f51f14dd41fa7df39107687a891684b17305f6c56887358; sap-appcontext=c2FwLXNlc3Npb25pZD1TSUQlM2FBTk9OJTNhcGNxcGRpNDZfQ1FQXzQ2JTNhYmJvMnAydjZpcVFjVFdUVm1UT0xwSDJPZ3RkUk16em9uQjRFZ0ZkYi1BVFQ%3d; TS01d0dca4=014e90d2cdd7a6a52c157d505d022f80b4a3b3dea4b6499a10aa961f65a75942ccbf4ecbaa1bb28699f768a10276494fabcbdedd6742d377c430c2fa1a33b4df9b4371ac0a81a13ea27925b75af2aa9366f3857be1d2bca3758da2847e9b99be14e695ff33604fb3e7d86e42f161af85aa3989adf8fc54e5d0f5f921dc1c294f124ff2547b18b2f91b5f646846d7686342aafbe4719768d5bd200d59b160f38eebb9390929; SelectedMaterials=; Order_Selected_materials=; _qimei_uuid42=1991c0f1f091000dd09c5505067aa9f81ee3184806; _qimei_i_3=5cf845d4925301d89593fd395e8d75e6a5eaa5a416525585e1897a5f72c7216b67613e943989e283d4aa; _qimei_h38=c79cc6f2d09c5505067aa9f80200000f21991c; sap-usercontext=sap-client=100; BIGipServercqpcn.bmwbrill.cn_pool_8443=2379141898.64288.0000; MYSAPSSO2=AjQxMDMBABhDAE0AMAA3ADcAOQAwACAAIAAgACAAIAACAAYxADAAMAADABBDAFEAUAAgACAAIAAgACAABAAYMgAwADIANgAwADYAMAA1ADAAMQA1ADkABQAEAAAACAkAAjEA%2fwFXMIIBUwYJKoZIhvcNAQcCoIIBRDCCAUACAQExCzAJBgUrDgMCGgUAMAsGCSqGSIb3DQEHATGCAR8wggEbAgEBMG8wZDELMAkGA1UEBhMCREUxHDAaBgNVBAoTE1NBUCBUcnVzdCBDb21tdW5pdHkxEzARBgNVBAsTClNBUCBXZWIgQVMxFDASBgNVBAsTC0kwMDIwNDc0MjYxMQwwCgYDVQQDEwNDUVACByAVCQIJU1kwCQYFKw4DAhoFAKBdMBgGCSqGSIb3DQEJAzELBgkqhkiG9w0BBwEwHAYJKoZIhvcNAQkFMQ8XDTI2MDYwNTAxNTkxMFowIwYJKoZIhvcNAQkEMRYEFMtFmOugjonHN5eqUCVsUOTCNHu%2fMAkGByqGSM44BAMEMDAuAhUAy4qjddu3SzOdPoWfoXYcRjRuFr8CFQDkFJnSTRS%21kH0toJ%21vtB8RKQunAw%3d%3d; SAP_SESSIONID_CQP_100=OUrG_ffxbhqsi84nuwtKiyQCgKlgghHxk9EbCxCGLek%3d; lf_actionspage=spp05_order_create.htm%3foninputprocessing(update); ordtype_create=; date_create=; po_create=; sppbasket=; back_page=SPP05_ORDER_CREATE_FRAME.htm; TS016675fd=014e90d2cd363e04af588030c81fccebf065da130036175652515755ac3668b8f08ab838a03c099c2a8ce008c875541a0b4804e1af020a24516036c926ba83e50a7ca71cbb32a36f8d86031e9ad92db3afa92f598f222c0fe6878995092fc0e3ebc28b1e571800a5f071655d330a392638134f385376637a5c0d61199c43131f892f697dad7b0fcc9eeafe330ab383e0d9eecf0bbf7a4818b2afd38e6d3faf83d6be11da448701816c66c1bdc79e7e1af0c6dee3c3e71eeef2b2fea8920ad497801a0c6919eb7500e705fab7dfd1f80ba3bfd5c81cb3e3816fd6747e0fe238b9b6bc4bad090b4e800857fdf1fc050526d91ff4398b6c9994ae749f85ad043b13e66ef71528; _qimei_fingerprint=54550af90219e3b56fc9224203a3db6d; _qimei_i_1=43c44dd192530388c7c1fc645b8d20e5f2eea1f1145c52d3bdd920582493206c616361973980ebdd8595c0c4'


    test_oe = "36121116326"  # 示例零件号
    
    print(f"\n测试零件号: {test_oe}")
    print(f"使用 Cookie: {test_cookie[:20]}...\n")
    
    try:
        # 初始化爬虫
        spider = BMWBrillianceSpider(cookie=test_cookie)
        
        print("-" * 50)
        print("测试 1: 查询零件库存")
        print("-" * 50)
        # 注意：实际使用时需要有效的 Cookie
        stock_response = spider.get_stock_check(test_oe)
        print(stock_response)
        
        if stock_response:
            print(f"库存查询成功，状态码: {stock_response.status_code}")
            # 可以进一步处理响应内容
        
        print("\n" + "-" * 50)
        print("测试 2: 查询零件详细信息")
        print("-" * 50)
        detail_response = spider.get_material_details(test_oe)
        print(detail_response)
        if detail_response:
            print(f"详情查询成功，状态码: {detail_response.status_code}")
            # 可以进一步处理响应内容
        
        # 关闭爬虫
        spider.close()
        print("\n" + "=" * 50)
        print("测试完成（注释状态，需要真实 Cookie 才能运行）")
        print("=" * 50)
        
    except Exception as e:
        print(f"测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()