"""
开思询价明细爬取与统计服务
用于从开思平台爬取询价明细数据并保存到数据库

处理逻辑：
    - 按天分天爬取近N天的数据
    - 每天独立爬取、保存明细（联合唯一键去重）
    - 从明细表统计并更新到统计表（只更新上月和本月）
    - 支持登录状态失效重试和网络重试机制
    - 使用API接口获取开思平台cookie进行认证
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import time
import requests
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from app.utils.database_connection import db_cursor



def get_ks_cookies_from_api() -> dict:
    """
    从API接口获取开思平台的cookie

    Returns:
        dict: 包含cookie信息的字典
    """
    url = "http://113.45.176.129:8001/md_ks.get_cookies?md=fs"
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json()
    if 'cookie' in data:
        return data['cookie']
    else:
        return data


class QuoteCountSyncService:
    """
    开思询价明细爬取与统计服务

    功能：
    1. 从开思平台按天爬取询价订单列表
    2. 遍历每个订单获取完整询价明细
    3. 保存明细到 crmapp_ks_inquiry_detail 表（联合唯一键去重）
    4. 从明细表统计并更新到 crmapp_quote_count_ks 表（只更新上月和本月）
    """

    QUOTATION_LIST_URL = "https://www.cassmall.com/inquiry/seller/quote/list/v1"
    PAGE_SIZE = 50
    MAX_RETRY = 3
    RETRY_DELAY = 2
    COMPANY = 'fsbbr'

    # company -> storeId 映射
    COMPANY_TO_STORE_ID = {
        'fsbbr': 'FSBBR001',
        'zhbbr': '4400004937',
        'dgby': '4400002594',
        'dghf': '4400002204',
        'zsbbr': '4400000670',
    }

    # company -> inquiry basic token 映射
    COMPANY_TO_INQUIRY_TOKEN = {
        'fsbbr': 'ecO2szp3JSljt2Nlwbv',
        'zhbbr': 'maBLBxO4UB4wyfz3KGE',
        'dgby': 'dFKGLCEYkGRkZd5Kp5Z',
        'dghf': 'sLpvQE7IqOcQBYjQbla',
        'zsbbr': 'W5eWV8OPpIMnYpU4iOm',
    }

    # company -> quoteUser 映射
    COMPANY_TO_QUOTE_USER = {
        'fsbbr': '65d1a2a93b53ad0001338c73',
        'zhbbr': '609b54f4d4753a0001f291b4',
        'dgby': '616e3fd3a7157800017cefbf',
        'dghf': '6101116ad28c230001afa74c',
        'zsbbr': '669c6c3efbe2d50001def2b5',
    }

    # AES 解密配置
    AES_KEY = "QUOTE_LIST#ABCDE".encode("utf-8")
    AES_IV = "asdfghjklzxcvbnm".encode("utf-8")

    # 需要特殊处理的品牌（宝马/奔驰）
    SPECIAL_BRANDS = {'宝马', '奔驰'}
    # 品质映射表
    QUALITY_MAP = {
        'ORIGINAL_CURRENCY': '原厂',
        'ORIGINAL_INLAND_4S': '原厂国内4s件'
    }

    @staticmethod
    def _aes_decrypt(cipher_b64: str) -> str:
        """AES-CBC 解密"""
        if not cipher_b64:
            return ''
        try:
            cipher_data = base64.b64decode(cipher_b64)
            aes = AES.new(QuoteCountSyncService.AES_KEY, AES.MODE_CBC, QuoteCountSyncService.AES_IV)
            plain_bytes = unpad(aes.decrypt(cipher_data), AES.block_size)
            return plain_bytes.decode("utf-8")
        except Exception:
            return ''

    @staticmethod
    def _extract_show_address(decrypted_json: str) -> str:
        """从解密后的JSON中提取showAddress"""
        if not decrypted_json:
            return ''
        try:
            import json
            data = json.loads(decrypted_json)
            return data.get('showAddress', '')
        except Exception:
            return ''

    @staticmethod
    def _extract_garage_company_name(decrypted_json: str) -> str:
        """从解密后的JSON中提取garageCompanyName"""
        if not decrypted_json:
            return ''
        try:
            import json
            data = json.loads(decrypted_json)
            return data.get('garageCompanyName', '')
        except Exception:
            return ''

    @staticmethod
    def normalize_brand(brand_name: str, parts_brand_quality: str) -> str:
        """
        品牌标准化处理
        宝马/奔驰直接使用品质映射后的名称（如"原厂"），不加品牌前缀
        其他品牌保持原样

        Args:
            brand_name: 原始品牌名称
            parts_brand_quality: 配件品质

        Returns:
            标准化后的品牌名称
        """
        brand = brand_name.strip() if brand_name else ''

        # 宝马/奔驰直接使用品质名称（如"原厂"）
        if brand in QuoteCountSyncService.SPECIAL_BRANDS:
            quality = parts_brand_quality.strip() if parts_brand_quality else ''
            mapped_quality = QuoteCountSyncService.QUALITY_MAP.get(quality, quality)

            # 返回品质名称，如：原厂
            if mapped_quality:
                return mapped_quality

        return brand

    def __init__(self):
        self.session = None
        self._init_session()

    def _init_session(self):
        """初始化session，使用API获取cookie"""
        ks_cookies = get_ks_cookies_from_api()
        self.session = self._create_session_from_cookies(ks_cookies)

    def _refresh_session(self):
        """刷新session"""
        self._init_session()

    def _create_session_from_cookies(self, cookies: dict) -> requests.Session:
        """使用cookie字典创建session"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Referer': 'https://www.cassmall.com/seller',
            'Origin': 'https://www.cassmall.com',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        })

        if isinstance(cookies, dict):
            for key, value in cookies.items():
                if key.lower() not in ['user-agent', 'accept', 'accept-language', 'referer', 'content-type', 'origin', 'cache-control', 'pragma']:
                    session.cookies.set(key, value, domain='.cassmall.com')

        return session

    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """带重试机制的HTTP请求"""
        for attempt in range(self.MAX_RETRY):
            try:
                if method.lower() == 'get':
                    response = self.session.get(url, timeout=30, **kwargs)
                else:
                    response = self.session.post(url, timeout=30, **kwargs)

                response.raise_for_status()
                
                result = response.json()

                if result.get('code') == 401 or result.get('msg') == '登录已过期':
                    print(f"[请求] 登录状态失效，尝试刷新cookie...")
                    self._refresh_session()
                    if attempt < self.MAX_RETRY - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    else:
                        return None

                return result

            except requests.exceptions.HTTPError as e:
                if '401' in str(e):
                    print(f"[请求][{attempt+1}/{self.MAX_RETRY}] 认证失败(401)，尝试刷新cookie...")
                    try:
                        self._refresh_session()
                        if attempt < self.MAX_RETRY - 1:
                            time.sleep(self.RETRY_DELAY)
                            continue
                    except Exception as refresh_err:
                        print(f"[请求] 刷新cookie失败：{refresh_err}")
                else:
                    print(f"[请求][{attempt+1}/{self.MAX_RETRY}] HTTP错误: {e}")

                if attempt < self.MAX_RETRY - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                else:
                    return None

            except Exception as e:
                print(f"[请求][{attempt+1}/{self.MAX_RETRY}] 请求失败: {e}")
                if attempt < self.MAX_RETRY - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                else:
                    return None

        return None

    def _fetch_quotation_list(self, start_ts: int, end_ts: int) -> List[Dict]:
        """获取指定时间范围内的所有订单列表（包含加密字段）"""
        orders = []
        page_num = 1
        quote_user = self.COMPANY_TO_QUOTE_USER.get(self.COMPANY, '')

        while True:
            payload = {
                "inquiryType": "ALL",
                "navTab": "ALL",
                "onlyViewOwner": False,
                "storeId": "ALL",
                "inquiryId": "",
                "statusId": "ALL",
                "garageCompanyId": "",
                "quoteUser": quote_user,
                "quoteType": "ALL",
                "systemQuoteReportStatus": "",
                "quoteScope": "ALL",
                "limitQuoteRange": False,
                "saasGroupLabels": ["ALL"],
                "startDate": start_ts,
                "endDate": end_ts,
                "pageNum": page_num,
                "pageSize": self.PAGE_SIZE,
                "isHighQualityLargeOrder": ""
            }

            result = self._make_request_with_retry(
                'post',
                self.QUOTATION_LIST_URL,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )

            if not result:
                print(f"[订单列表] 第{page_num}页请求失败，跳过")
                break

            if result.get('code') != 200:
                print(f"[订单列表] API返回错误: {result.get('msg')}")
                break

            data = result.get('data', {})
            quotation_list = data.get('quotationList', [])

            if not quotation_list:
                break

            for item in quotation_list:
                order_id = item.get('id')
                if order_id:
                    encrypt_address = item.get('encryptAddress', '')
                    encrypt_user_infos = item.get('encryptInquiryUserInfos', '')
                    car_brand_name = item.get('carBrandName', '')
                    decrypted_address = self._aes_decrypt(encrypt_address)
                    decrypted_user_infos = self._aes_decrypt(encrypt_user_infos)
                    show_address = self._extract_show_address(decrypted_address)
                    garage_company_name = self._extract_garage_company_name(decrypted_user_infos)
                    orders.append({
                        'order_id': order_id,
                        'show_address': show_address,
                        'garage_company_name': garage_company_name,
                        'car_brand_name': car_brand_name,
                    })

            print(f"[订单列表] 第{page_num}页获取 {len(quotation_list)} 条订单")

            total_elements = data.get('totalElements', 0)
            total_pages = (total_elements + self.PAGE_SIZE - 1) // self.PAGE_SIZE
            if page_num >= total_pages or len(quotation_list) < self.PAGE_SIZE:
                break

            page_num += 1
            time.sleep(0.5)  # 翻页间隔0.5秒

        print(f"[订单列表] 共获取 {len(orders)} 个订单")
        return orders

    def _fetch_inquiry_basic(self, order_id: str) -> Optional[str]:
        """
        调用 inquiry/read/inquirybasic 接口获取车架号 vin
        """
        token = self.COMPANY_TO_INQUIRY_TOKEN.get(self.COMPANY)
        if not token:
            return None

        url = f"https://www.cassmall.com/inquiry/seller/inquiry/read/inquirybasic/{order_id}/{token}"
        result = self._make_request_with_retry('get', url)

        if not result or result.get('code') != 200:
            return None

        data = result.get('data', {})
        inquiry_car_infos = data.get('inquiryCarInfos', {})
        vin = inquiry_car_infos.get('vin', '')
        return vin if vin else None

    def _fetch_car_config(self, vin: str) -> Dict[str, str]:
        """
        调用 getCarConfigInformation 接口获取车辆配置信息
        返回: {"engine": "", "production_date": "", "chassis": ""}
        """
        url = f"https://www.cassmall.com/agentBuy/seller/admin/inquirys/getCarConfigInformation/{vin}"
        result = self._make_request_with_retry('get', url)

        config = {"engine": "", "production_date": "", "chassis": ""}
        if not result or result.get('code') != 200:
            return config

        data = result.get('data', [])
        if not isinstance(data, list):
            return config

        for item in data:
            name = item.get('name', '')
            value = item.get('value', '')
            # 发动机：优先"发动机"，其次"发动机编码"
            if name in ["发动机", "发动机编码"]:
                config["engine"] = value
            elif name == "车辆生产日期":
                config["production_date"] = value
            # 底盘：优先"底盘"，其次"车型编码"
            elif name in ["底盘", "车型编码"]:
                config["chassis"] = value

        return config

    def _fetch_quotation_detail(self, order_id: str, show_address: str = '', garage_company_name: str = '', car_brand_name: str = '') -> List[Dict]:
        """
        获取指定订单的询价明细，返回完整字段
        联合唯一键：inquiryId + brandName + partsNum + company
        """
        items = []

        url_configs = [
            {
                'url': f"https://www.cassmall.com/inquiryWeb/quotation/{order_id}/quoting/items",
                'json': {
                    "isViewPage": True,
                    "listHistoryQuoteResult": False,
                    "onlyUnquote": False,
                    "userNeedsItemPositiveOrder": False,
                    "page": 1,
                    "size": 50
                },
                'name': 'inquiryWeb'
            },
            {
                'url': f"https://www.cassmall.com/archiveinquiry/quotation/{order_id}/quoting/items",
                'json': None,
                'name': 'archiveinquiry'
            }
        ]
        
        for i, config in enumerate(url_configs, 1):
            url = config['url']
            json_data = config['json']
            
            if json_data:
                result = self._make_request_with_retry(
                    'post', url, json=json_data,
                    headers={'Content-Type': 'application/json'}
                )
            else:
                result = self._make_request_with_retry(
                    'post', url,
                    headers={'Content-Type': 'application/json'}
                )

            if not result:
                if i < len(url_configs):
                    continue
                else:
                    return items

            if result.get('code') == 404:
                if i < len(url_configs):
                    continue
                else:
                    return items

            if result.get('code') != 200:
                if i < len(url_configs):
                    continue
                else:
                    return items

            data = result.get('data', {})
            content_list = data.get('content', [])

            # 提取真正的 inquiryId（B 开头），用于获取车辆信息
            real_inquiry_id = ''
            for content in content_list:
                sqir = content.get('storeQuoteItemResults', [])
                if sqir:
                    real_inquiry_id = sqir[0].get('inquiryId', '')
                    if real_inquiry_id:
                        break

            # 获取车辆信息
            vin = ''
            car_config = {"engine": "", "production_date": "", "chassis": ""}
            if real_inquiry_id:
                vin = self._fetch_inquiry_basic(real_inquiry_id)
                if vin:
                    car_config = self._fetch_car_config(vin)

            # === 调用 resolveitems/detail 获取 content 级别下单状态与 resolve_parts_num ===
            resolve_result_ids = []
            for content in content_list:
                store_resolve_item = content.get('storeResolveItem', {})
                resolve_result_id = store_resolve_item.get('resolveResultId', '')
                if resolve_result_id:
                    resolve_result_ids.append(resolve_result_id)

            ordered_resolve_ids = set()
            resolve_parts_map = {}
            if resolve_result_ids:
                store_id = self.COMPANY_TO_STORE_ID.get(self.COMPANY, 'FSBBR001')
                resolve_payload = {
                    "inquiryId": order_id,
                    "storeId": store_id,
                    "resolveResultIds": resolve_result_ids
                }
                resolve_result = self._make_request_with_retry(
                    'post',
                    'https://www.cassmall.com/inquiryWeb/quotation/resolveitems/detail',
                    json=resolve_payload,
                    headers={'Content-Type': 'application/json'}
                )
                if resolve_result and resolve_result.get('code') == 200:
                    for item_data in resolve_result.get('data', []):
                        resolve_id = item_data.get('resolveResultId', '')
                        if item_data.get('orderStatusId') == 'ORDERED':
                            ordered_resolve_ids.add(resolve_id)
                        # 收集 resolveResultId -> {partsNum, partsName} 映射
                        pn = item_data.get('partsNum', '')
                        p_name = item_data.get('partsName', '')
                        if pn or p_name:
                            resolve_parts_map[resolve_id] = {
                                'partsNum': pn.strip().upper().replace(' ', '') if pn else '',
                                'partsName': p_name.strip() if p_name else ''
                            }
            # === 结束 ===

            # 遍历所有content，收集所有storeQuoteItemResults
            for content_index, content in enumerate(content_list, 1):
                store_quote_item_results = content.get('storeQuoteItemResults', [])

                if not store_quote_item_results:
                    continue

                # === 计算该 content 的显示状态 ===
                store_resolve_item = content.get('storeResolveItem', {})
                resolve_result_id = store_resolve_item.get('resolveResultId', '')
                content_order_status = '已下单' if resolve_result_id in ordered_resolve_ids else '未下单'
                resolve_parts = resolve_parts_map.get(resolve_result_id, {})
                resolve_parts_num = resolve_parts.get('partsNum', '')
                resolve_parts_name = resolve_parts.get('partsName', '')

                ordered_item_keys = set()
                has_ordered_in_content = False
                for sqir in store_quote_item_results:
                    if sqir.get('sellerStatus') == 'ORDERED':
                        has_ordered_in_content = True
                        ordered_item_keys.add((
                            sqir.get('brandName', '').strip(),
                            sqir.get('partsNum', '').strip().upper().replace(' ', '')
                        ))

                if content_order_status == '未下单':
                    content_display_status = '未下单'
                elif has_ordered_in_content:
                    content_display_status = '本店下单'
                else:
                    content_display_status = '非本店下单'
                # === 新增结束 ===

                for item_index, item in enumerate(store_quote_item_results, 1):
                    # 去除OE号中的空格并转为大写
                    parts_num = item.get('partsNum', '').strip().upper().replace(' ', '')
                    brand_name = item.get('brandName', '').strip()
                    parts_name = item.get('partsName', '').strip()
                    parts_brand_quality = item.get('partsBrandQuality', '')
                    # 从明细数据中获取inquiryId（如"B26040246308"），如果没有则使用order_id
                    inquiry_id = item.get('inquiryId', '') or order_id

                    # 标准化品牌（处理宝马/奔驰的品质映射）
                    brand_normalized = self.normalize_brand(brand_name, parts_brand_quality)

                    # === 新增：仓库位置名称 与 到货时间 ===
                    location_name = (item.get('locationName') or '').strip()
                    arrival_time_raw = item.get('arrivalTime')
                    arrival_time_desc = ''
                    if arrival_time_raw is not None and arrival_time_raw != '':
                        try:
                            arrival_days = int(arrival_time_raw)
                            if arrival_days <= 0:
                                arrival_time_desc = '现货'
                            else:
                                arrival_time_desc = f'调货+{arrival_days}天'
                        except (ValueError, TypeError):
                            arrival_time_desc = ''
                    # === 新增结束 ===

                    # 只保存有完整数据的记录
                    if parts_num and brand_name and parts_name:
                        item_display_status = content_display_status
                        if content_display_status == '本店下单' and (brand_name, parts_num) in ordered_item_keys:
                            item_display_status = '本店下单！'

                        items.append({
                            'inquiryId': inquiry_id,
                            'partsNum': parts_num,
                            'partsName': parts_name,
                            'brandName': brand_name,
                            'brandNormalized': brand_normalized,
                            'brandId': item.get('brandId', ''),
                            'partType': item.get('partType', ''),
                            'partsBrandQuality': parts_brand_quality,
                            'remark': item.get('remark', ''),
                            'sellerBtPrice': item.get('sellerBtPrice', ''),
                            'sellerPrice': item.get('sellerPrice', ''),
                            'sellerStatus': item.get('sellerStatus', ''),
                            'orderStatus': content_order_status,
                            'displaySellerStatus': item_display_status,
                            'vin': vin or '',
                            'engine': car_config.get('engine', ''),
                            'productionDate': car_config.get('production_date', ''),
                            'chassis': car_config.get('chassis', ''),
                            'showAddress': show_address,
                            'garageCompanyName': garage_company_name,
                            'carBrandName': car_brand_name,
                            'locationName': location_name,
                            'arrivalTime': arrival_time_desc,
                            'contentItemIndex': f'{content_index}_{item_index}',
                            'resolvePartsNum': resolve_parts_num,
                            'resolvePartsName': resolve_parts_name,
                        })

            # 如果第一个接口有数据，直接返回（不切换到第二个接口）
            if items:
                return items

        return items

    def _save_inquiry_details(self, items: List[Dict]) -> int:
        """
        批量保存询价明细到数据库
        联合唯一键：inquiryId + brandName + partsNum + company
        重复时用新数据覆盖
        """
        if not items:
            return 0

        with db_cursor() as cursor:
            insert_sql = """
                INSERT INTO crmapp_ks_inquiry_detail
                (inquiryId, partsNum, partsName, brandName, brandNormalized, brandId, partType,
                 partsBrandQuality, remark, sellerBtPrice, sellerPrice, sellerStatus, order_status, display_seller_status,
                 vin, engine, production_date, chassis, show_address, garage_company_name, car_brand_name,
                 location_name, arrival_time, content_item_index, resolve_parts_num, resolve_parts_name, company, quote_date, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    partsName = VALUES(partsName),
                    brandNormalized = VALUES(brandNormalized),
                    brandId = VALUES(brandId),
                    partType = VALUES(partType),
                    partsBrandQuality = VALUES(partsBrandQuality),
                    remark = VALUES(remark),
                    sellerBtPrice = VALUES(sellerBtPrice),
                    sellerPrice = VALUES(sellerPrice),
                    sellerStatus = VALUES(sellerStatus),
                    order_status = VALUES(order_status),
                    display_seller_status = VALUES(display_seller_status),
                    vin = VALUES(vin),
                    engine = VALUES(engine),
                    production_date = VALUES(production_date),
                    chassis = VALUES(chassis),
                    show_address = VALUES(show_address),
                    garage_company_name = VALUES(garage_company_name),
                    car_brand_name = VALUES(car_brand_name),
                    location_name = VALUES(location_name),
                    arrival_time = VALUES(arrival_time),
                    content_item_index = VALUES(content_item_index),
                    resolve_parts_num = VALUES(resolve_parts_num),
                    resolve_parts_name = VALUES(resolve_parts_name),
                    quote_date = VALUES(quote_date),
                    updated_at = NOW()
            """

            values = []
            for item in items:
                row = (
                    item.get('inquiryId', ''),
                    item.get('partsNum', ''),
                    item.get('partsName', ''),
                    item.get('brandName', ''),
                    item.get('brandNormalized', ''),
                    item.get('brandId', ''),
                    item.get('partType', ''),
                    item.get('partsBrandQuality', ''),
                    item.get('remark', ''),
                    item.get('sellerBtPrice', ''),
                    item.get('sellerPrice', ''),
                    item.get('sellerStatus', ''),
                    item.get('orderStatus', '未下单'),
                    item.get('displaySellerStatus', '未下单'),
                    item.get('vin', ''),
                    item.get('engine', ''),
                    item.get('productionDate', ''),
                    item.get('chassis', ''),
                    item.get('showAddress', ''),
                    item.get('garageCompanyName', ''),
                    item.get('carBrandName', ''),
                    item.get('locationName', ''),
                    item.get('arrivalTime', ''),
                    item.get('contentItemIndex', ''),
                    item.get('resolvePartsNum', ''),
                    item.get('resolvePartsName', ''),
                    item.get('company', self.COMPANY),
                    item.get('quote_date', '')
                )
                values.append(row)

            cursor.executemany(insert_sql, values)
            return len(values)

    def sync_recent_days(self, days: int = 5) -> Dict[str, Any]:
        """
        爬取近N天的询价明细，按天分天爬取
        
        Args:
            days: 爬取天数，默认5天
            
        Returns:
            dict: 包含处理结果的字典
        """
        today = datetime.now().date()
        
        all_results = {
            'dates': [],
            'total_orders': 0,
            'total_items': 0,
            'saved': 0
        }
        
        print(f"\n{'='*70}")
        print(f"开思询价明细爬取服务")
        print(f"开始时间: {datetime.now()}")
        print(f"爬取范围: 近{days}天")
        print(f"{'='*70}")
        
        # 倒序处理（今天 → 昨天 → ...）
        for i in range(days):
            target_date = today - timedelta(days=i)
            date_str = target_date.strftime('%Y-%m-%d')
            
            # 计算时间戳范围
            start_ts = int(datetime.combine(target_date, datetime.min.time()).timestamp() * 1000)
            end_ts = int(datetime.combine(target_date, datetime.max.time()).timestamp() * 1000)
            
            print(f"\n{'='*60}")
            print(f"[每日爬取] 处理日期: {date_str}")
            print(f"{'='*60}")
            
            # 1. 获取该日期的所有订单
            orders = self._fetch_quotation_list(start_ts, end_ts)
            if not orders:
                print(f"[每日爬取] {date_str} 无订单数据")
                continue

            print(f"[每日爬取] 获取 {len(orders)} 个订单")

            # 2. 获取每个订单的明细
            all_items = []
            for idx, order in enumerate(orders, 1):
                order_id = order.get('order_id')
                show_address = order.get('show_address', '')
                garage_company_name = order.get('garage_company_name', '')
                car_brand_name = order.get('car_brand_name', '')
                items = self._fetch_quotation_detail(order_id, show_address, garage_company_name, car_brand_name)
                
                # 为每条明细添加 quote_date 和 company
                for item in items:
                    item['quote_date'] = date_str
                    item['company'] = self.COMPANY
                
                all_items.extend(items)
                
                if idx % 50 == 0:
                    print(f"[进度] 已处理 {idx}/{len(orders)} 个订单，获取 {len(all_items)} 条明细")
                
                time.sleep(0.2)  # 订单明细请求间隔0.2秒
            
            # 3. 批量保存明细
            if all_items:
                saved = self._save_inquiry_details(all_items)
                print(f"[保存] {date_str} 完成: 保存 {saved} 条明细")
                
                all_results['dates'].append(date_str)
                all_results['total_orders'] += len(orders)
                all_results['total_items'] += len(all_items)
                all_results['saved'] += saved
            
            # 4. 日期之间暂停
            if i < days - 1:
                print(f"[暂停] 等待1秒后继续下一天...")
                time.sleep(1)
        
        print(f"\n{'='*70}")
        print(f"询价明细爬取完成!")
        print(f"处理日期: {', '.join(all_results['dates'])}")
        print(f"总订单数: {all_results['total_orders']}")
        print(f"总明细数: {all_results['total_items']}")
        print(f"保存记录: {all_results['saved']}")
        print(f"{'='*70}")
        
        return all_results

    def update_stats_from_details(self) -> Dict[str, Any]:
        """
        从明细表统计并更新到统计表
        只更新上个月和本月的数据
        
        Returns:
            dict: 包含更新结果的字典
        """
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        
        # 计算上个月
        if current_month == 1:
            last_year = current_year - 1
            last_month = 12
        else:
            last_year = current_year
            last_month = current_month - 1
        
        months_to_update = [
            (last_year, last_month),
            (current_year, current_month)
        ]
        
        print(f"\n{'='*70}")
        print(f"询价统计更新服务")
        print(f"开始时间: {datetime.now()}")
        print(f"{'='*70}")
        
        results = []
        with db_cursor() as cursor:
            for year, month in months_to_update:
                year_month = f"{year}-{month:02d}"
                start_date = f"{year_month}-01"
                if month == 12:
                    next_month = f"{year + 1}-01-01"
                else:
                    next_month = f"{year}-{month + 1:02d}-01"
                
                print(f"\n[统计] 处理 {year_month} 的数据...")
                
                # 先删除该月的旧统计数据
                cursor.execute(
                    "DELETE FROM crmapp_quote_count_ks WHERE `year_month` = %s AND company = %s",
                    (year_month, self.COMPANY)
                )
                deleted = cursor.rowcount
                if deleted > 0:
                    print(f"[统计] 已删除 {year_month} 旧数据 {deleted} 条")
                
                # 从明细表统计并插入（合并开思和微信数据）
                stats_sql = """
                    INSERT INTO crmapp_quote_count_ks
                    (`year_month`, brand, oe, quote_count, company, created_at, updated_at)
                    SELECT
                        %s as `year_month`,
                        brand,
                        oe,
                        SUM(quote_count) as `quote_count`,
                        company,
                        NOW() as `created_at`,
                        NOW() as `updated_at`
                    FROM (
                        -- 开思询价数据
                        SELECT
                            COALESCE(brandNormalized, brandName) as brand,
                            partsNum as oe,
                            COUNT(*) as quote_count,
                            company
                        FROM crmapp_ks_inquiry_detail
                        WHERE quote_date >= %s
                          AND quote_date < %s
                          AND company = %s
                        GROUP BY COALESCE(brandNormalized, brandName), partsNum, company

                        UNION ALL

                        -- 微信询价数据
                        SELECT
                            brand,
                            oe,
                            COUNT(*) as quote_count,
                            company
                        FROM crmapp_weixin_inquiry_detail
                        WHERE creation_date >= %s
                          AND creation_date < %s
                          AND company = %s
                        GROUP BY brand, oe, company
                    ) combined
                    GROUP BY brand, oe, company
                """

                cursor.execute(stats_sql, (
                    year_month,
                    start_date, next_month, self.COMPANY,
                    start_date, next_month, self.COMPANY
                ))
                affected = cursor.rowcount

                print(f"[统计] {year_month} 更新完成: {affected} 条记录")
                
                results.append({
                    'year_month': year_month,
                    'updated_records': affected
                })
        
        print(f"\n{'='*70}")
        print(f"询价统计更新完成!")
        for r in results:
            print(f"  - {r['year_month']}: {r['updated_records']} 条")
        print(f"{'='*70}")
        
        return {
            'months': [r['year_month'] for r in results],
            'details': results
        }

    def sync_recent_two_months(self) -> Dict[str, Any]:
        """
        同步近两个月的询价数据（开思+微信）
        1. 爬取近60天的开思询价明细
        2. 更新统计表（上月+本月）
        
        Returns:
            dict: 包含开思爬取结果和统计更新结果
        """
        print(f"\n{'='*70}")
        print(f"开思询价同步服务")
        print(f"开始时间: {datetime.now()}")
        print(f"{'='*70}")
        
        # 1. 爬取近5天的开思询价明细
        sync_days = 5
        crawl_result = self.sync_recent_days(days=sync_days)

        # 2. 计算并写回未报价产品（近2天）
        try:
            from app.services.ks_inquiry_service.ks_unquoted_products_service import KsUnquotedProductsService
            unquoted_result = KsUnquotedProductsService.calculate_recent_days(days=2)
        except Exception as e:
            print(f"[QuoteCountSyncService] 计算未报价产品失败: {e}")
            unquoted_result = {'matched_parts': 0, 'updated_rows': 0, 'error': str(e)}
        
        # 3. 更新统计表（上月+本月）
        stats_result = self.update_stats_from_details()
        
        return {
            'total_items': crawl_result.get('total_items', 0),
            'saved': crawl_result.get('saved', 0),
            'dates': crawl_result.get('dates', []),
            'unquoted_products': unquoted_result,
            'stats': stats_result
        }

    def sync_date_range(self, begin_date: str, end_date: str) -> Dict[str, Any]:
        """
        爬取指定日期范围的开思询价明细，按天分天爬取

        Args:
            begin_date: 开始日期 (yyyy-MM-dd)
            end_date: 结束日期 (yyyy-MM-dd)

        Returns:
            dict: 包含处理结果的字典
        """
        from datetime import date

        start_date = date.fromisoformat(begin_date)
        end_date = date.fromisoformat(end_date)

        if start_date > end_date:
            raise ValueError(f"开始日期 {begin_date} 不能晚于结束日期 {end_date}")

        all_results = {
            'dates': [],
            'total_orders': 0,
            'total_items': 0,
            'saved': 0
        }

        print(f"\n{'='*70}")
        print(f"开思询价明细日期范围爬取服务")
        print(f"开始时间: {datetime.now()}")
        print(f"爬取范围: {begin_date} ~ {end_date}")
        print(f"{'='*70}")

        current = start_date
        day_count = 0
        while current <= end_date:
            date_str = current.strftime('%Y-%m-%d')
            day_count += 1

            start_ts = int(datetime.combine(current, datetime.min.time()).timestamp() * 1000)
            end_ts = int(datetime.combine(current, datetime.max.time()).timestamp() * 1000)

            print(f"\n{'='*60}")
            print(f"[每日爬取] 处理日期: {date_str}")
            print(f"{'='*60}")

            orders = self._fetch_quotation_list(start_ts, end_ts)
            if not orders:
                print(f"[每日爬取] {date_str} 无订单数据")
                current += timedelta(days=1)
                continue

            print(f"[每日爬取] 获取 {len(orders)} 个订单")

            all_items = []
            for idx, order in enumerate(orders, 1):
                order_id = order.get('order_id')
                show_address = order.get('show_address', '')
                garage_company_name = order.get('garage_company_name', '')
                car_brand_name = order.get('car_brand_name', '')
                items = self._fetch_quotation_detail(order_id, show_address, garage_company_name, car_brand_name)

                for item in items:
                    item['quote_date'] = date_str
                    item['company'] = self.COMPANY

                all_items.extend(items)

                if idx % 50 == 0:
                    print(f"[进度] 已处理 {idx}/{len(orders)} 个订单，获取 {len(all_items)} 条明细")

                time.sleep(0.2)

            if all_items:
                saved = self._save_inquiry_details(all_items)
                print(f"[保存] {date_str} 完成: 保存 {saved} 条明细")

                all_results['dates'].append(date_str)
                all_results['total_orders'] += len(orders)
                all_results['total_items'] += len(all_items)
                all_results['saved'] += saved

            if current < end_date:
                print(f"[暂停] 等待1秒后继续下一天...")
                time.sleep(1)

            current += timedelta(days=1)

        print(f"\n{'='*70}")
        print(f"询价明细日期范围爬取完成!")
        print(f"处理日期: {', '.join(all_results['dates'])}")
        print(f"总订单数: {all_results['total_orders']}")
        print(f"总明细数: {all_results['total_items']}")
        print(f"保存记录: {all_results['saved']}")
        print(f"{'='*70}")

        return all_results


