from urllib.parse import urlencode

from app.scripts.spiders.spider_tool import SpiderTool
from config.crm_config import get_crm_cookies


class CrmGzbbrSpider:
    """
    某网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """
    # 网站固定配置
    BASE_URL = "https://crm.gzbbr.com"

    def __init__(self, token=None, timeout=10, retry_count=3, cookies_key='fs'):
        """
        初始化爬虫实例

        :param token: 认证Token，优先使用Token认证
        :param timeout: 请求超时时间（秒）
        :param retry_count: 重试次数
        :param cookies_key: Cookies的key，可选值：fs, zs, zh, hf, by，当token为空时使用
        """
        # 🔥 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 必传Token（业务私有属性）
        self.token = token
        
        # 如果没有token，使用cookies认证（实际上是headers认证）
        self.auth_headers = {}
        if not self.token:
            cookies = get_crm_cookies(cookies_key)
            if cookies:
                # 设置cookies到session中
                self.spider_tool.session.headers.update(cookies)

    def _get_auth_header(self):
        """
        私有方法：统一生成认证请求头（复用）

        :return: 认证请求头字典
        """
        if self.token:
            return {"Authorization": self.token}
        # 没有token时返回空headers，使用cookies认证
        return {}

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
        """
        获取合并订单列表

        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认200
        :param orderdate_start: 订单开始时间戳
        :param orderdate_end: 订单结束时间戳
        :param status: 订单状态
        :param order_type_id: 订单类型
        :param level_id: 客户等级，维修厂（27）、同行（25）
        :param is_wms: 是否WMS订单
        :param order_source_type: 业务类型
        :return: 请求响应对象
        """
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


    # https://crm.gzbbr.com/api/Crm.Partner/partnerList?page=1&limit=200
    def get_partnerList(self, page=1, limit=200):
        """
        获取合作伙伴列表

        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认200
        :return: 请求响应对象
        """
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





    # https://crm.gzbbr.com/api/Crm.PurchaseOrder/mergeOrderList
    # page 分页页码
    # limit 分页每页数量
    # orders_no 订单号
    # supplier 供应商
    # orderdate 创建时间范围 格式：[开始时间, 结束时间] 如 [1780675200000, 1780761599000]
    # status 订单状态
    # company_id 公司ID
    # product 产品
    # is_wms 是否WMS订单
    # name 名称
    # ordertype 订单类型
    # order_source_type 订单来源类型
    # e_date 入库时间范围 格式：[开始时间, 结束时间] 如 [1780675200000, 1780761599000]
    # supplier_phone 供应商电话
    # delivery_status 发货状态
    def get_purchaseOrder_mergeOrderList(self, page=1, limit=200, orders_no=None, supplier=None,
                                         orderdate=None, status=None,
                                         company_id=None, product=None, is_wms=None, name=None,
                                         ordertype=None, order_source_type=None, e_date=None,
                                         supplier_phone=None, delivery_status=None):
        """
        获取采购订单合并列表

        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认200
        :param orders_no: 订单号
        :param supplier: 供应商
        :param orderdate: 创建时间范围，格式：[开始时间, 结束时间]
        :param status: 订单状态
        :param company_id: 公司ID
        :param product: 产品
        :param is_wms: 是否WMS订单
        :param name: 名称
        :param ordertype: 订单类型
        :param order_source_type: 订单来源类型
        :param e_date: 入库时间范围，格式：[开始时间, 结束时间]
        :param supplier_phone: 供应商电话
        :param delivery_status: 发货状态
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/Crm.PurchaseOrder/mergeOrderList"
        data = {
            "page": page,
            "limit": limit,
            "orders_no": orders_no,
            "supplier": supplier,
            "status": status,
            "company_id": company_id,
            "product": product,
            "is_wms": is_wms,
            "name": name,
            "ordertype": ordertype,
            "order_source_type": order_source_type,
            "supplier_phone": supplier_phone,
            "delivery_status": delivery_status,
            "orderdate": orderdate,
            "e_date": e_date
        }
        print("【请求API地址】", url)
        print("【请求参数】", data)
        return self.spider_tool.fetch(url, method="POST", json=data, headers=self._get_auth_header())

    # https://crm.gzbbr.com/api/Crm.PurchaseOrder/orders_view
    # purchase_order_id 采购订单ID
    # page 分页页码
    # limit 分页每页数量
    def get_purchaseOrder_orders_view(self, purchase_order_id, page=1, limit=200):
        """
        获取采购订单详情视图

        :param purchase_order_id: 采购订单ID
        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认200
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/Crm.PurchaseOrder/orders_view"
        data = {
            "purchase_order_id": purchase_order_id,
            "page": page,
            "limit": limit
        }
        print("【请求API地址】", url)
        print("【请求参数】", data)
        return self.spider_tool.fetch(url, method="POST", json=data, headers=self._get_auth_header())

    def close(self):
        """
        关闭会话连接，释放资源
        """
        self.spider_tool.close()