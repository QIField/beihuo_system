# -*- coding: utf-8 -*-
"""
CRM 产品价格同步 API 客户端

封装 Product.Product/list、view、updateView 三个接口的调用。
"""

import time

import requests

from config.cookie_config import create_crm_session
from app.utils.crm_updateview_logger import execute_update_view_with_log


CRM_BASE_URL = "https://crm.gzbbr.com"
LIST_URL = f"{CRM_BASE_URL}/api/Product.Product/list"
VIEW_URL = f"{CRM_BASE_URL}/api/Product.Product/view"

DEFAULT_PAGE_SIZE = 200
REQUEST_DELAY = 0.3


class CrmPriceSyncApiClient:
    """CRM 价格同步专用 API 客户端"""

    def __init__(self, store_code):
        self.store_code = store_code
        self.session = create_crm_session(store_code)

    def list_stock_products(self):
        """
        使用 is_stock=1 查询有库存产品，自动分页。

        :return: list[dict] data['data'][0]['child'] 中的原始产品字典
        """
        products = []
        page = 1
        last_page = 1

        while page <= last_page:
            payload = {
                "page": page,
                "limit": DEFAULT_PAGE_SIZE,
                "is_stock": "1",
            }
            response = self.session.post(LIST_URL, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != 200:
                raise RuntimeError(
                    f"[{self.store_code}] list 接口返回异常: {data.get('msg')}"
                )

            page_data = data.get("data", {})
            last_page = page_data.get("last_page", 1)
            items = page_data.get("data", [])

            if items and isinstance(items, list) and len(items) > 0:
                child = items[0].get("child", [])
                products.extend(child)

            page += 1
            time.sleep(REQUEST_DELAY)

        return products

    def get_product_view(self, product_id):
        """
        查询单个产品视图详情。

        :param product_id: 产品ID
        :return: dict 接口 data 字段
        """
        response = self.session.get(
            VIEW_URL, params={"product_id": product_id}, timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != 200:
            raise RuntimeError(
                f"[{self.store_code}] view 接口返回异常: {data.get('msg')}"
            )

        return data.get("data", {})

    def update_product_view(self, payload):
        """
        更新产品视图信息。

        :param payload: dict 更新字段
        :return: (success: bool, msg: str)
        """
        return execute_update_view_with_log(
            session=self.session,
            payload=payload,
            source="crm_price_sync",
            store_code=self.store_code,
            timeout=30,
        )
