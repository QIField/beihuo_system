import logging
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

    def __init__(self, token=None, timeout=10, retry_count=3, cookies_key='fs', logger=None):
        """
        初始化爬虫实例

        :param token: 认证Token，优先使用Token认证
        :param timeout: 请求超时时间（秒）
        :param retry_count: 重试次数
        :param cookies_key: Cookies的key，可选值：fs, zs, zh, hf, by，当token为空时使用
        :param logger: 外部传入的日志记录器，未传入时使用默认的 'crm_gzbbr' logger
        """
        # 🔥 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 必传Token（业务私有属性）
        self.token = token

        # 日志记录器：调用方传入则使用调用方的，否则使用统一的 crm_gzbbr logger
        self.logger = logger or logging.getLogger('crm_gzbbr')

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

    # https://crm.gzbbr.com/api/Crm.Orders/salesOrderHistory
    # page 分页页码
    # limit 分页每页数量
    # customer 客户
    # create_date 创建时间范围 格式：[开始时间, 结束时间] 如 [1782835200000, 1782921599000]
    def get_sales_order_history(self, page=1, limit=200, customer=None,
                                create_date_start=None, create_date_end=None):
        """
        获取销售订单历史记录

        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认200
        :param customer: 客户
        :param create_date_start: 创建开始时间戳
        :param create_date_end: 创建结束时间戳
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/Crm.Orders/salesOrderHistory"
        params = {
            "page": page,
            "limit": limit,
            "customer": customer,
        }
        if create_date_start and create_date_end:
            params["create_date[]"] = [create_date_start, create_date_end]
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{params}")
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())

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
        # ========== 记录请求信息 ==========
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{params}")
        # ==================================
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())

    # https://crm.gzbbr.com/api/Crm.Orders/orders_view?orders_id=2075261&page=1&limit=50
    def get_orders_view(self, orders_id, page=1, limit=50):
        """
        获取订单详情视图

        :param orders_id: CRM 订单 ID
        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认50
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/Crm.Orders/orders_view"
        params = {
            "orders_id": orders_id,
            "page": page,
            "limit": limit,
        }
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{params}")
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())

    # https://crm.gzbbr.com/api/Crm.Delivery/deliveryView?delivery_id=1919278&page=1&limit=20
    def get_delivery_view(self, delivery_id, page=1, limit=20):
        """
        获取发货单详情视图

        :param delivery_id: 发货单 ID
        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认20
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/Crm.Delivery/deliveryView"
        params = {
            "delivery_id": delivery_id,
            "page": page,
            "limit": limit,
        }
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{params}")
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
        # ========== 记录请求信息 ==========
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{params}")
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
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{data}")
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
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{data}")
        return self.spider_tool.fetch(url, method="POST", json=data, headers=self._get_auth_header())

    # https://crm.gzbbr.com/api/crm.Product/getProductList
    # brand_id 品牌ID
    # warehouse_id 仓库ID
    # kw_id 库位ID
    # type 类型
    # page 分页页码
    # limit 分页每页数量
    def get_product_list(self, page=1, limit=400, brand_id="", warehouse_id="",
                         kw_id="", product_type="1", kw_nos=""):
        """
        获取产品列表（库存数据）

        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认400
        :param brand_id: 品牌ID
        :param warehouse_id: 仓库ID
        :param kw_id: 库位ID
        :param product_type: 类型，默认"1"
        :param kw_nos: 库位号列表，逗号分隔，如 "01-01-01-01-01,01-09-09-09-08"
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/crm.Product/getProductList"
        data = {
            "page": page,
            "limit": limit,
            "brand_id": brand_id,
            "warehouse_id": warehouse_id,
            "kw_id": kw_id,
            "type": product_type,
            "kw_nos": kw_nos,
        }
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{data}")
        return self.spider_tool.fetch(url, method="POST", json=data, headers=self._get_auth_header())

    # https://crm.gzbbr.com/api/crm.Product/inventoryRecordList
    # orders_no 订单号
    # kw_no 库位号
    # warehouse_id 仓库ID
    # page 分页页码
    # limit 分页每页数量
    # type 类型 1=入库，-1=出库
    # product_id 产品ID
    def get_inventory_record_list(self, product_id, page=1, limit=20, record_type=1,
                                  orders_no="", kw_no="", warehouse_id=""):
        """
        获取产品库存变动记录列表

        :param product_id: 产品ID（必填）
        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认20
        :param record_type: 变动类型，1=入库/增加，-1=出库/减少
        :param orders_no: 订单号
        :param kw_no: 库位号
        :param warehouse_id: 仓库ID
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/crm.Product/inventoryRecordList"
        params = {
            "orders_no": orders_no,
            "kw_no": kw_no,
            "warehouse_id": warehouse_id,
            "page": page,
            "limit": limit,
            "type": record_type,
            "product_id": product_id,
        }
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求参数】{params}")
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())


    # https://crm.gzbbr.com/api/Product.Product/list
    # page 分页页码
    # limit 分页每页数量
    # keyword 关键词
    # number OE号
    # numberlist OE号列表，逗号分隔
    # brand_id 品牌ID
    # warehouse_id 仓库ID
    # customer_id 客户ID
    # is_stock 是否有库存
    # is_dangerstock 是否危险库存
    # is_nostock 是否无库存
    # sale_type 销售类型
    # is_zaitu 是否在途
    # product_type_id 产品类型ID
    # make_id 品牌ID
    # series_id 系列ID
    # car_id 车型ID
    # chassis_id 底盘ID
    # engine_id 发动机ID
    def get_product_product_list(self, page=1, limit=200, keyword=None, number=None,
                                 numberlist=None, brand_id=None, warehouse_id=None,
                                 customer_id=None, is_stock=None, is_dangerstock=None,
                                 is_nostock=None, sale_type=None, is_zaitu=None,
                                 product_type_id=None, make_id=None, series_id=None,
                                 car_id=None, chassis_id=None, engine_id=None,
                                 aikeyword=None):
        """
        获取产品列表（开思产品数据）

        :param page: 分页页码，默认1
        :param limit: 分页每页数量，默认20
        :param keyword: 关键词
        :param number: OE号
        :param numberlist: OE号列表，逗号分隔
        :param brand_id: 品牌ID
        :param warehouse_id: 仓库ID
        :param customer_id: 客户ID
        :param is_stock: 是否有库存
        :param is_dangerstock: 是否危险库存
        :param is_nostock: 是否无库存
        :param sale_type: 销售类型
        :param is_zaitu: 是否在途
        :param product_type_id: 产品类型ID
        :param make_id: 品牌ID
        :param series_id: 系列ID
        :param car_id: 车型ID
        :param chassis_id: 底盘ID
        :param engine_id: 发动机ID
        :param aikeyword: 品牌编码
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/Product.Product/list"
        data = {
            "page": page,
            "limit": limit,
            "keyword": keyword,
            "number": number,
            "numberlist": numberlist,
            "brand_id": brand_id,
            "warehouse_id": warehouse_id,
            "customer_id": customer_id,
            "is_stock": is_stock,
            "is_dangerstock": is_dangerstock,
            "is_nostock": is_nostock,
            "sale_type": sale_type,
            "is_zaitu": is_zaitu,
            "product_type_id": product_type_id,
            "make_id": make_id,
            "series_id": series_id,
            "car_id": car_id,
            "chassis_id": chassis_id,
            "engine_id": engine_id,
            "aikeyword": aikeyword,
        }
        print("【请求API地址】", url)
        print("【请求参数】", data)
        return self.spider_tool.fetch(url, method="POST", json=data, headers=self._get_auth_header())


    # https://crm.gzbbr.com/api/Crm.Pdcart/cartAddToOrders
    def get_cart_add_to_orders(self, product_id=None, partner_id=None):
        """
        将购物车商品添加到订单
        
        :param product_id: 产品ID列表，如 ["269140"]
        :param partner_id: 合作伙伴ID
        """
        url = f"{self.BASE_URL}/api/Crm.Pdcart/cartAddToOrders"
        data = {
            "product_id": product_id,
            "partner_id": partner_id,
        }
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求参数】", data)
        # ==================================
        return self.spider_tool.fetch(url, method="POST", json=data, headers=self._get_auth_header())


    # https://crm.gzbbr.com/api/Crm.Cart/addcart?search_no=31108854990&pid=6131&num=10&sales_price=279.99
    def get_add_cart(self, search_no=None, pid=None, num=None, sales_price=None):
        """
        添加商品到购物车

        :param search_no: 搜索编号
        :param pid: 产品ID
        :param num: 数量
        :param sales_price: 销售价格
        :return: 请求响应对象
        """
        url = f"{self.BASE_URL}/api/Crm.Cart/addcart"
        params = {
            "search_no": search_no,
            "pid": pid,
            "num": num,
            "sales_price": sales_price,
        }
        # ========== 打印请求信息 ==========
        print("【请求API地址】", url)
        print("【请求参数】", params)
        # ==================================
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())


    def close(self):
        """
        关闭会话连接，释放资源
        """
        self.spider_tool.close()