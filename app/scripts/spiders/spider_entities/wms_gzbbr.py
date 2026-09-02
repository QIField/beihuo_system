# -*- coding:utf-8 -*-
# @Time    : 2026/4/26 10:04
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_gzbbr.py
# @Software: PyCharm

import logging

from app.scripts.spiders.spider_entities.wms_gzbbr_login import WmsGzbbrLoginService
from app.scripts.spiders.spider_tool import SpiderTool


class WmsGzbbrSpider:
    """
    WMS网站专用业务爬虫
    职责：仅定义接口、拼接参数、调用工具
    不写任何请求底层逻辑
    """
    # 网站固定配置
    BASE_URL = "https://wms.gzbbr.com"

    def __init__(self, token=None, timeout=10, retry_count=3, logger=None):
        # 核心：实例化独立爬虫工具（组合模式）
        self.spider_tool = SpiderTool(timeout, retry_count)
        # 必传Token（业务私有属性）
        if token is None:
            self.token = WmsGzbbrLoginService.get_valid_config()
        else:
            self.token = token
        # 日志器：可外部传入，否则使用默认 wms_gzbbr
        self.logger = logger or logging.getLogger('wms_gzbbr')

    def _get_auth_header(self):
        """私有方法：统一生成认证请求头（复用）"""
        return {"Authorization": self.token}

    # ===================== 业务接口 =====================

    # https://wms.gzbbr.com/api/Wms.Orders/get_status_orders
    def get_status_orders(self, type=None, status=None, page=None, keywd=None):
        """获取状态订单列表"""
        url = f"{self.BASE_URL}/api/Wms.Orders/get_status_orders"
        params = {
            "type": type,
            "status": status,
            "page": page,
            "keywd": keywd,
        }
        # ========== 打印请求信息 ==========
        self.logger.info("【请求API地址】%s", url)
        self.logger.info("【请求参数】%s", params)
        # ==================================
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())

    # https://wms.gzbbr.com/api/Wms.Orders/get_return_items
    def get_return_items(self, orders_no=None, is_self=None):
        """获取采购入库单列表"""
        url = f"{self.BASE_URL}/api/Wms.Orders/get_return_items"
        params = {
            "orders_no": orders_no,
        }
        if is_self is not None:
            params["is_self"] = is_self
        # ========== 打印请求信息 ==========
        self.logger.info("【请求API地址】%s", url)
        self.logger.info("【请求参数】%s", params)
        # ==================================
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())

    # https://wms.gzbbr.com/api/Wms.Orders/git_pick_work
    def get_pick_work(self, orders_id=None):
        """获取订单拣货/入库明细"""
        url = f"{self.BASE_URL}/api/Wms.Orders/git_pick_work"
        params = {
            "orders_id": orders_id,
        }
        # ========== 打印请求信息 ==========
        self.logger.info("【请求API地址】%s", url)
        self.logger.info("【请求参数】%s", params)
        # ==================================
        return self.spider_tool.fetch(url, params=params, headers=self._get_auth_header())

    # https://wms.gzbbr.com/api/Wms.Orders/addPurchaseToInventory
    def add_purchase_to_inventory(self, orders_id=None):
        """采购入库确认"""
        url = f"{self.BASE_URL}/api/Wms.Orders/addPurchaseToInventory"
        payload = {"orders_id": orders_id}
        # ========== 打印请求信息 ==========
        self.logger.info("【请求API地址】%s", url)
        self.logger.info("【请求参数】%s", payload)
        # ==================================
        return self.spider_tool.fetch(
            url,
            method="POST",
            json=payload,
            headers=self._get_auth_header(),
        )

    # https://wms.gzbbr.com/api/Wms.Orders/removePurchaseFromInventory
    def remove_purchase_from_inventory(self, orders_id=None):
        """采购移除确认"""
        url = f"{self.BASE_URL}/api/Wms.Orders/removePurchaseFromInventory"
        payload = {"orders_id": orders_id}
        # ========== 打印请求信息 ==========
        self.logger.info("【请求API地址】%s", url)
        self.logger.info("【请求参数】%s", payload)
        # ==================================
        return self.spider_tool.fetch(
            url,
            method="POST",
            json=payload,
            headers=self._get_auth_header(),
        )

    # https://wms.gzbbr.com/api/Wms.Orders/orders_workok
    def orders_workok(self, type=None, orders_id=None):
        """订单工作完成确认"""
        url = f"{self.BASE_URL}/api/Wms.Orders/orders_workok"
        payload = {
            "type": str(type) if type is not None else None,
            "orders_id": str(orders_id) if orders_id is not None else None,
        }
        # ========== 打印请求信息 ==========
        self.logger.info("【请求API地址】%s", url)
        self.logger.info("【请求参数】%s", payload)
        # ==================================
        return self.spider_tool.fetch(
            url,
            method="POST",
            json=payload,
            headers=self._get_auth_header(),
        )

    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()
