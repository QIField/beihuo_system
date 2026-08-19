# -*- coding:utf-8 -*-
# @Time    : 2026/7/3
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : data_gzbbr.py
# @Software: PyCharm

import logging

from app.scripts.spiders.spider_tool import SpiderTool
from config.config_list_manager.config_cache import get_config_value


class DataGzbbrSpider:
    """
    data.gzbbr.com 网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """

    BASE_URL = "https://data.gzbbr.com"

    # 门店代码 -> 数据库配置键映射
    STORE_CONFIG_KEY_MAP = {
        "fsbbr": "data_gzbbr_com_fs",
        "zhbbr": "data_gzbbr_com_zh",
        "zsbbr": "data_gzbbr_com_zs",
        "dgby": "data_gzbbr_com_by",
        "dghf": "data_gzbbr_com_hf",
    }

    def __init__(self, cookie=None, config_key=None, store_code="fsbbr", timeout=10, retry_count=3, logger=None):
        # 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 解析并保存 Cookie 字符串
        self.cookie = self._resolve_cookie(cookie, config_key, store_code)
        # 日志记录器：调用方传入则使用调用方的，否则使用统一的 data_gzbbr logger
        self.logger = logger or logging.getLogger('data_gzbbr')

    def _resolve_cookie(self, cookie, config_key, store_code):
        """
        将传入的 cookie、配置键或门店代码统一解析为 Cookie 字符串
        :param cookie: 直接传入的 Cookie 字符串或字典
        :param config_key: 数据库配置键
        :param store_code: 门店代码
        :return: Cookie 字符串
        """
        if cookie:
            raw = cookie
        else:
            key = config_key or self.STORE_CONFIG_KEY_MAP.get(store_code, "data_gzbbr_com_fs")
            raw = get_config_value(key)

        if raw is None:
            raise ValueError("未找到 data.gzbbr.com 的 Cookie 配置")

        # 如果是字典，按 key 排序后拼接为浏览器 Cookie 格式
        if isinstance(raw, dict):
            return "; ".join([f"{k}={v}" for k, v in sorted(raw.items(), key=lambda x: x[0])])

        return str(raw)

    def _get_auth_header(self):
        """私有方法：统一生成认证请求头（复用）"""
        return {
            "Cookie": self.cookie,
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.BASE_URL}/admin/Product.Quoteprice/index.html",
        }

    # ===================== 业务接口 =====================

    # https://data.gzbbr.com/admin/Product.Quoteprice/index
    def get_quote_price_index(self, order="desc", offset=0, limit=500,
                              supplier_name="", number="", pdname="",
                              frey_no="", price="", create_date_start="",
                              create_date_end="", remark=""):
        """
        查询报价列表
        :param order: 排序方式，默认 desc
        :param offset: 分页偏移量，默认 0
        :param limit: 每页数量，默认 500
        :param supplier_name: 供应商名称
        :param number: 配件编码/OE号
        :param pdname: 产品名称
        :param frey_no: Frey 编号
        :param price: 价格
        :param create_date_start: 创建开始日期
        :param create_date_end: 创建结束日期
        :param remark: 备注
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/admin/Product.Quoteprice/index"

        data = {
            "order": order,
            "offset": offset,
            "limit": limit,
            "supplier_name": supplier_name,
            "number": number,
            "pdname": pdname,
            "frey_no": frey_no,
            "price": price,
            "create_date_start": create_date_start,
            "create_date_end": create_date_end,
            "remark": remark,
        }

        # ========== 记录请求信息 ==========
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求方法】POST")
        self.logger.info(f"【请求参数】{data}")
        # ==================================

        return self.spider_tool.fetch(
            url=url,
            method="POST",
            data=data,
            headers=self._get_auth_header()
        )

    # https://data.gzbbr.com/admin/Product.Quoteprice/update
    def update_quote_price(self, quote_price_id, cass_warehouse_id, supplier_name,
                           number, brand_name, price, stock, lose_date, remark=""):
        """
        更新报价
        :param quote_price_id: 报价记录ID
        :param cass_warehouse_id: 仓库ID
        :param supplier_name: 供应商名称
        :param number: 配件编码/OE号
        :param brand_name: 品牌名称
        :param price: 价格
        :param stock: 库存数量
        :param lose_date: 失效时间
        :param remark: 备注
        :return: 响应对象
        """
        url = f"{self.BASE_URL}/admin/Product.Quoteprice/update"

        data = {
            "quote_price_id": quote_price_id,
            "cass_warehouse_id": cass_warehouse_id,
            "supplier_name": supplier_name,
            "number": number,
            "brand_name": brand_name,
            "price": price,
            "stock": stock,
            "lose_date": lose_date,
            "remark": remark,
        }

        # ========== 记录请求信息 ==========
        self.logger.info(f"【请求API地址】{url}")
        self.logger.info(f"【请求方法】POST")
        self.logger.info(f"【请求参数】{data}")
        # ==================================

        return self.spider_tool.fetch(
            url=url,
            method="POST",
            data=data,
            headers=self._get_auth_header()
        )

    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()
