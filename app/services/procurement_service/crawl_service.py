"""
CRM数据全量爬取服务
用于定时任务调用
"""

import time
import json
import re
from typing import List, Dict, Any, Tuple

from config import create_crm_session
from app.utils.database_connection import get_db_connection


# 配置参数
LIMIT = 500
BATCH_SIZE = 5000
MAX_RETRY = 3
RETRY_DELAY = 2
COMPANY = 'fsbbr'
CRM_PRODUCT_LIST_URL = 'https://crm.gzbbr.com/api/Product.Product/list'

# 产品等级映射
PRODUCT_GRADE_MAP = {
    '1': 'A类',
    '2': 'B类',
    '3': 'C类',
    '4': 'D类',
    '5': '淘汰品',
    '6': '无'
}


class CRMDataCrawlService:
    """CRM数据全量爬取服务类"""

    def __init__(self):
        self.session = None
        self.total_saved = 0
        self.total_failed = 0

    def get_total_pages(self) -> Tuple[int, int]:
        """
        获取第1页数据，返回 (total, last_page)
        同时初始化session
        """
        self.session = create_crm_session()
        params = {'page': 1, 'limit': LIMIT}

        for attempt in range(MAX_RETRY):
            try:
                response = self.session.get(CRM_PRODUCT_LIST_URL, params=params, timeout=30)
                response.raise_for_status()
                result = response.json()

                if result.get('status') == 200 or result.get('msg') == '操作成功':
                    data = result.get('data', {})
                    total = data.get('total', 0)
                    last_page = data.get('last_page', 0)
                    return total, last_page
                else:
                    print(f"API返回错误: {result.get('msg')}")
            except Exception as e:
                print(f"[{attempt + 1}/{MAX_RETRY}] 获取总页数失败: {e}")
                if attempt < MAX_RETRY - 1:
                    time.sleep(RETRY_DELAY)
                    # 重建session
                    try:
                        self.session = create_crm_session()
                    except:
                        pass
                    continue
                else:
                    raise Exception(f"多次重试后仍无法获取总页数: {e}")

        return 0, 0

    def crawl_page(self, page: int) -> List[Dict]:
        """爬取指定页，返回产品列表"""
        params = {'page': page, 'limit': LIMIT}

        for attempt in range(MAX_RETRY):
            try:
                response = self.session.get(CRM_PRODUCT_LIST_URL, params=params, timeout=30)
                response.raise_for_status()
                result = response.json()

                if result.get('status') == 200 or result.get('msg') == '操作成功':
                    data = result.get('data', {})
                    return data.get('data', [])
                else:
                    print(f"[第{page}页] API返回错误: {result.get('msg')}")
            except Exception as e:
                print(f"[第{page}页][{attempt + 1}/{MAX_RETRY}] 请求失败: {e}")
                if attempt < MAX_RETRY - 1:
                    time.sleep(RETRY_DELAY)
                    # 尝试重建session
                    try:
                        self.session = create_crm_session()
                    except:
                        pass
                    continue

        print(f"[第{page}页] 多次重试后仍失败，跳过该页")
        return []

    def parse_product(self, product: Dict) -> Dict[str, Any]:
        """解析单个产品数据"""
        # 转换产品等级
        product_grade = str(product.get('product_grade', '6'))
        product_level = PRODUCT_GRADE_MAP.get(product_grade, '无')

        # 解析采购记录
        purchasing_record = product.get('purchasing_record', '')
        procurement_records = self._parse_purchasing_record(purchasing_record)

        # 计算价格
        purchase_summary = float(product.get('purchase_summary', 0)) if product.get('purchase_summary') else 0.0
        max_price, min_price = self._calculate_max_min_price(procurement_records)

        # 如果没有采购记录，使用purchase_summary作为supplier_price
        if not procurement_records:
            supplier_price = purchase_summary
        else:
            supplier_price = self._get_latest_price(procurement_records)

        return {
            'oe': product.get('number', ''),
            'brand': product.get('brand_name', ''),
            'company': COMPANY,
            'product_name': product.get('l_name_zh', ''),
            'vehicle_brand': product.get('cass_oebrand_name', ''),
            'replace_number': product.get('number_list', ''),
            'brand_code': product.get('brand_code', ''),
            'is_cass': product.get('is_cass', ''),
            'product_remark': product.get('company_remark', ''),
            'product_level': product_level,
            'supplier_price': supplier_price,
            'max_price': max_price,
            'min_price': min_price,
            'procurement_records': json.dumps(procurement_records, ensure_ascii=False) if procurement_records else None
        }

    def _parse_purchasing_record(self, purchasing_record: str) -> List[Dict]:
        """解析采购记录字符串"""
        if not purchasing_record:
            return []

        records = []
        raw_records = re.split(r'<br\s*/?>|\n', purchasing_record)

        for raw_record in raw_records:
            raw_record = raw_record.strip()
            if not raw_record:
                continue

            try:
                # 提取日期
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', raw_record)
                if not date_match:
                    continue
                purchase_date = date_match.group(1)

                # 提取供应商
                supplier_match = re.search(r'供应商:([^,]+)', raw_record)
                if not supplier_match:
                    continue
                supplier_name = supplier_match.group(1).strip()

                # 提取单价
                price_match = re.search(r'单价:([\d.]+)', raw_record)
                purchase_price = float(price_match.group(1)) if price_match else 0.0

                records.append({
                    'supplier_name': supplier_name,
                    'purchase_price': purchase_price,
                    'purchase_date': purchase_date
                })
            except:
                continue

        return records

    def _calculate_max_min_price(self, records: List[Dict]) -> Tuple[float, float]:
        """计算最高价和最低价"""
        if not records:
            return 0.0, 0.0

        prices = [r.get('purchase_price', 0) for r in records if r.get('purchase_price', 0) > 0]
        if not prices:
            return 0.0, 0.0

        return max(prices), min(prices)

    def _get_latest_price(self, records: List[Dict]) -> float:
        """获取最新价格"""
        if not records:
            return 0.0

        sorted_records = sorted(records, key=lambda x: x.get('purchase_date', ''), reverse=True)
        return sorted_records[0].get('purchase_price', 0.0)

    def batch_save(self, products: List[Dict]) -> int:
        """
        批量保存到数据库
        使用 INSERT ... ON DUPLICATE KEY UPDATE
        """
        if not products:
            return 0

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                columns = [
                    'oe', 'brand', 'company', 'product_name', 'vehicle_brand',
                    'replace_number', 'brand_code', 'is_cass', 'product_remark',
                    'product_level', 'supplier_price', 'max_price', 'min_price',
                    'procurement_records'
                ]

                placeholders = ', '.join(['%s'] * len(columns))
                columns_str = ', '.join(columns)

                update_parts = [f"{col} = VALUES({col})" for col in columns if col not in ['oe', 'brand', 'company']]
                update_str = ', '.join(update_parts)

                sql = f"""
                    INSERT INTO crmapp_compare_summary ({columns_str})
                    VALUES ({placeholders})
                    ON DUPLICATE KEY UPDATE {update_str}
                """

                values = []
                for product in products:
                    row = [
                        product.get('oe', ''),
                        product.get('brand', ''),
                        product.get('company', COMPANY),
                        product.get('product_name', ''),
                        product.get('vehicle_brand', ''),
                        product.get('replace_number', ''),
                        product.get('brand_code', ''),
                        product.get('is_cass', ''),
                        product.get('product_remark', ''),
                        product.get('product_level', ''),
                        product.get('supplier_price', 0.0),
                        product.get('max_price', 0.0),
                        product.get('min_price', 0.0),
                        product.get('procurement_records')
                    ]
                    values.append(row)

                cursor.executemany(sql, values)
                conn.commit()

                return len(products)

        except Exception as e:
            conn.rollback()
            print(f"批量保存失败: {e}")
            return 0
        finally:
            conn.close()

    def crawl_all(self) -> Dict[str, int]:
        """
        主入口：爬取所有产品并保存

        Returns:
            {'total': 总记录数, 'saved': 成功保存数, 'failed': 失败数}
        """
        print("=" * 80)
        print("开始CRM全量爬取")
        print("=" * 80)

        try:
            # 获取总页数
            total, last_page = self.get_total_pages()
            print(f"\n📊 总记录数: {total}")
            print(f"📄 总页数: {last_page}")
            print(f"📦 每页数量: {LIMIT}")

            batch_buffer = []
            total_processed = 0
            page_failed = 0

            # 遍历所有页
            for page in range(1, last_page + 1):
                print(f"\n{'=' * 80}")
                print(f"📄 正在处理第 {page}/{last_page} 页")
                print(f"{'=' * 80}")

                # 获取页面数据
                data_list = self.crawl_page(page)
                if not data_list:
                    page_failed += 1
                    continue

                # 解析产品
                page_products = []
                for group in data_list:
                    for product in group.get('child', []):
                        try:
                            parsed = self.parse_product(product)
                            page_products.append(parsed)
                        except Exception as e:
                            print(f"⚠️  解析产品失败: {e}")
                            self.total_failed += 1

                print(f"✅ 本页解析成功: {len(page_products)} 条")

                # 加入批量缓存
                batch_buffer.extend(page_products)
                total_processed += len(page_products)
                print(f"📦 当前缓存: {len(batch_buffer)} 条")

                # 检查是否需要批量保存
                if len(batch_buffer) >= BATCH_SIZE:
                    print(f"\n💾 批量保存 {len(batch_buffer)} 条数据...")
                    saved = self.batch_save(batch_buffer)
                    self.total_saved += saved
                    print(f"✅ 保存成功: {saved} 条")
                    batch_buffer = []

                # 每10页暂停
                if page % 10 == 0:
                    print(f"\n⏸️  已处理10页，暂停2秒...")
                    time.sleep(2)

            # 保存最后一批
            if batch_buffer:
                print(f"\n💾 保存最后一批数据: {len(batch_buffer)} 条...")
                saved = self.batch_save(batch_buffer)
                self.total_saved += saved
                print(f"✅ 保存成功: {saved} 条")

            # 输出统计
            print("\n" + "=" * 80)
            print("爬取完成统计")
            print("=" * 80)
            print(f"📊 总记录数: {total}")
            print(f"✅ 成功保存: {self.total_saved} 条")
            print(f"❌ 失败: {self.total_failed} 条")
            print(f"📄 总页数: {last_page}")
            print(f"⚠️  失败页数: {page_failed}")

            result = {
                'total': total,
                'saved': self.total_saved,
                'failed': self.total_failed
            }
            
            # 全量爬取完成后，串行执行销量同步
            print("\n" + "=" * 80)
            print("CRM全量爬取完成，开始销量明细同步...")
            print("=" * 80)
            self._sync_sales_history()
            
            return result

        except Exception as e:
            print(f"\n❌ 爬取过程出错: {e}")
            import traceback
            traceback.print_exc()
            return {'total': 0, 'saved': self.total_saved, 'failed': self.total_failed}

        finally:
            if self.session:
                self.session.close()
    
    def _sync_sales_history(self):
        """
        串行执行销量明细同步
        在CRM全量爬取完成后自动调用
        """
        try:
            from app.services.sales_history_service import SalesHistorySyncService
            
            service = SalesHistorySyncService()
            sync_result = service.sync_recent_days(days=30)
            
            print(f"\n[销量同步] 完成:")
            print(f"  - 总页数: {sync_result['total_pages']}")
            print(f"  - 总条目: {sync_result['total_items']}")
            print(f"  - 保存记录: {sync_result['saved']}")
            
        except Exception as e:
            print(f"\n[销量同步] 失败: {e}")
            import traceback
            traceback.print_exc()
