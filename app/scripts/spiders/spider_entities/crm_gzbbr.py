from urllib.parse import urlencode

from app.scripts.spiders.spider_tool import SpiderTool

class CrmGzbbrSpider:
    """
    某网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """
    # 网站固定配置
    BASE_URL = "https://crm.gzbbr.com"

    def __init__(self, token, timeout=10, retry_count=3):
        # 🔥 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 必传Token（业务私有属性）
        self.token = token

    def _get_auth_header(self):
        """私有方法：统一生成认证请求头（复用）"""
        return {"Authorization": self.token}

    # ===================== 业务接口 =====================
    # def get_user_info(self):
    #     """获取用户信息"""
    #     url = f"{self.BASE_URL}/user/info"
    #     return self.spider_tool.fetch(url, headers=self._get_auth_header())

    



    # https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList
    # level_id 客户等级 维修厂（27）、同行（25）
    # page 分页页码 
    # limit 分页每页数量 默认200
    # status 订单状态
    # order_type_id 订单类型
    # order_source_type 业务类型
    # is_wms 是否WMS订单
    def get_mergeOrderList(self, page=1, limit=200, orderdate_start=None, orderdate_end=None,
                            status=None, order_type_id=None, level_id=None,
                            is_wms=None, order_source_type=None):
        """获取合并订单列表"""
        url = f"{self.BASE_URL}/api/Crm.Orders/mergeOrderList"
        params = {
            "page": page,
            "limit": limit,
            "status": status,
            "order_type_id": order_type_id,
            "level_id": level_id,
            "is_wms": is_wms,
            "order_source_type": order_source_type,
        }
        if orderdate_start and orderdate_end:
            params["orderdate[]"] = [orderdate_start, orderdate_end]
        # query_string = urlencode(params, doseq=True)
        # full_url = f"{url}?{query_string}"
        # print("【完整请求URL】", full_url)
         # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求参数】", params)
        # ==================================
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())



    #https://crm.gzbbr.com/api/Crm.Partner/partnerList?page=1&limit=200
    def get_partnerList(self, page=1, limit=200):
        """获取合作伙伴列表"""
        url = f"{self.BASE_URL}/api/Crm.Partner/partnerList"
        params = {
            "page": page,
            "limit": limit,
        }
        # query_string = urlencode(params, doseq=True)
        # full_url = f"{url}?{query_string}"
        # print("【完整请求URL】", full_url)
         # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求参数】", params)
        # ==================================
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())





    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()