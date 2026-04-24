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
from app.services.procurement_service.vehicle_model_sync import VehicleModelSyncService


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
        self.model_sync_service = VehicleModelSyncService()

    def get_total_pages(self) -> Tuple[int, int]:
        """
        获取第1页数据，返回 (total, last_page)
        同时初始化session
        """
        self.session = create_crm_session()
        payload = {'page': 1, 'limit': LIMIT}

        for attempt in range(MAX_RETRY):
            try:
                response = self.session.post(CRM_PRODUCT_LIST_URL, json=payload, timeout=30)
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
        payload = {'page': page, 'limit': LIMIT}

        for attempt in range(MAX_RETRY):
            try:
                response = self.session.post(CRM_PRODUCT_LIST_URL, json=payload, timeout=30)
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

    def _extract_replace_numbers(self, display_number):
        """
        从 display_number 数组中提取通用号，用中文逗号分隔
        """
        if not display_number or not isinstance(display_number, list):
            return ''

        numbers = []
        for item in display_number:
            if isinstance(item, dict):
                num = item.get('number', '').strip()
                if num:
                    numbers.append(num)

        # 去重并保持顺序
        unique_numbers = list(dict.fromkeys(numbers))
        return '，'.join(unique_numbers)

    def _extract_replace_numbers_with_keys(self, display_number):
        """
        从 display_number 数组中提取key和number
        格式: key1:number1;key2:number2
        """
        if not display_number or not isinstance(display_number, list):
            return ''

        pairs = []
        for item in display_number:
            if isinstance(item, dict):
                key = item.get('key', '').strip()
                num = item.get('number', '').strip()
                if key and num:
                    pairs.append(f"{key}:{num}")

        return ';'.join(pairs)

    def parse_product(self, product: Dict) -> Dict[str, Any]:
        """解析单个产品数据"""
        # 转换产品等级
        product_grade = str(product.get('product_grade', '6'))
        product_level = PRODUCT_GRADE_MAP.get(product_grade, '无')

        # 解析在途库存列表
        stock_zaitu_list = product.get('stock_zaitu_list', [])
        if stock_zaitu_list:
            stock_zaitu_list = json.dumps(stock_zaitu_list, ensure_ascii=False)
        else:
            stock_zaitu_list = None

        return {
            'product_id': product.get('product_id', ''),
            'oe': product.get('number', ''),
            'brand': product.get('brand_name', ''),
            'company': COMPANY,
            'product_name': product.get('l_name_zh', ''),
            'vehicle_brand': product.get('cass_oebrand_name', ''),
            'replace_number': self._extract_replace_numbers(product.get('display_number')),
            'replace_number_with_keys': self._extract_replace_numbers_with_keys(product.get('display_number')),
            'brand_code': product.get('brand_code', ''),
            'is_cass': product.get('is_cass', ''),
            'product_remark': product.get('company_remark', ''),
            'product_level': product_level,
            'l_model_zh': product.get('l_model_zh', ''),
            'stock_zaitu_list': stock_zaitu_list,
            'frey_no': product.get('frey_no', ''),
            'supplier_price': 0.0,
            'max_price': 0.0,
            'min_price': 0.0
        }

    def clear_table(self) -> bool:
        """清空 crmapp_compare_summary 表（重置自增ID）"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE crmapp_compare_summary")
                conn.commit()
                print("✅ 已清空 crmapp_compare_summary 表")
                return True
        except Exception as e:
            conn.rollback()
            print(f"❌ 清空表失败: {e}")
            return False
        finally:
            conn.close()

    def batch_save(self, products: List[Dict]) -> Dict[str, int]:
        """
        批量保存到数据库 - 分块处理，异常块逐条重试
        将大批量分成小块，哪块失败就单独处理那块
        """
        if not products:
            return {'saved': 0, 'failed': 0}

        CHUNK_SIZE = 500
        total_saved = 0
        total_failed = 0
        conn = get_db_connection()

        columns = [
            'product_id', 'oe', 'brand', 'company', 'product_name', 'vehicle_brand',
            'replace_number', 'replace_number_with_keys', 'brand_code', 'is_cass', 'product_remark',
            'product_level', 'l_model_zh', 'stock_zaitu_list', 'frey_no',
            'supplier_price', 'max_price', 'min_price'
        ]
        sql = f"INSERT INTO crmapp_compare_summary ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"

        def make_row(p):
            return (
                p.get('product_id', ''),
                p.get('oe', ''),
                p.get('brand', ''),
                p.get('company', COMPANY),
                p.get('product_name', ''),
                p.get('vehicle_brand', ''),
                p.get('replace_number', ''),
                p.get('replace_number_with_keys', ''),
                p.get('brand_code', ''),
                p.get('is_cass', ''),
                p.get('product_remark', ''),
                p.get('product_level', ''),
                p.get('l_model_zh', ''),
                p.get('stock_zaitu_list') or None,
                p.get('frey_no', ''),
                p.get('supplier_price', 0.0),
                p.get('max_price', 0.0),
                p.get('min_price', 0.0)
            )

        try:
            with conn.cursor() as cursor:
                for i in range(0, len(products), CHUNK_SIZE):
                    chunk = products[i:i + CHUNK_SIZE]

                    try:
                        # 整块批量插入
                        cursor.executemany(sql, [make_row(p) for p in chunk])
                        total_saved += len(chunk)

                    except Exception:
                        # 整块失败，逐条重试
                        conn.rollback()
                        for p in chunk:
                            try:
                                cursor.execute(sql, make_row(p))
                                total_saved += 1
                            except Exception:
                                total_failed += 1

                conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"批量保存失败: {e}")
        finally:
            conn.close()

        if total_failed > 0:
            print(f"  📊 保存统计: 成功{total_saved}条, 失败{total_failed}条")

        return {'saved': total_saved, 'failed': total_failed}

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

            # 清空表（全量爬取前清空旧数据）
            if not self.clear_table():
                return {'total': 0, 'saved': 0, 'failed': 0}

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

                            # 收集车型映射（用于后续同步）
                            oe = product.get('number', '')
                            brand = product.get('brand_name', '')
                            model = product.get('l_model_zh', '')
                            self.model_sync_service.collect_model_mapping(oe, brand, model)

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
                    result = self.batch_save(batch_buffer)
                    self.total_saved += result['saved']
                    print(f"✅ 保存成功: {result['saved']} 条")
                    batch_buffer = []

                # 每10页暂停
                if page % 10 == 0:
                    print(f"\n⏸️  已处理10页，暂停2秒...")
                    time.sleep(2)

            # 保存最后一批
            if batch_buffer:
                print(f"\n💾 保存最后一批数据: {len(batch_buffer)} 条...")
                result = self.batch_save(batch_buffer)
                self.total_saved += result['saved']
                print(f"✅ 保存成功: {result['saved']} 条")

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
            
            # 全量爬取完成后，同步车型数据
            print("\n" + "="*80)
            print("CRM全量爬取完成，开始同步车型数据...")
            print("="*80)
            self.model_sync_service.sync_to_database(company=COMPANY)

            # 从备货表同步销量数据
            print("\n" + "="*80)
            print("开始从备货表同步销量数据...")
            print("="*80)
            self._sync_sales_from_beihuo()

            return result

        except Exception as e:
            print(f"\n❌ 爬取过程出错: {e}")
            import traceback
            traceback.print_exc()
            return {'total': 0, 'saved': self.total_saved, 'failed': self.total_failed}

        finally:
            if self.session:
                self.session.close()

    def _sync_sales_from_beihuo(self):
        """
        从 crmapp_beihuo 表同步销量数据到 crmapp_compare_summary
        """
        try:
            from app.utils.database_connection import get_db_connection

            conn = get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                    UPDATE crmapp_compare_summary s
                    JOIN crmapp_beihuo b ON s.oe = b.oe COLLATE utf8mb4_unicode_ci
                        AND s.brand = b.`品牌` COLLATE utf8mb4_unicode_ci
                    SET
                        s.today_sales = b.today_sales,
                        s.yesterday_sales = b.sales_yesterday,
                        s.month_sales = b.sales_month,
                        s.sales_7d = b.sales_7d,
                        s.avg_sales_6m = b.avg_sales_6m,
                        s.avg_sales_12m = b.avg_sales_12m,
                        s.sales_6m = b.`近6个月销量`,
                        s.sales_12m = b.`近12个月销量`
                    WHERE s.company = %s
                """
                cursor.execute(sql, (COMPANY,))
                conn.commit()
                affected = cursor.rowcount

                print(f"\n[销量同步] 完成:")
                print(f"  - 更新记录数: {affected}")

        except Exception as e:
            print(f"\n[销量同步] 失败: {e}")
            import traceback
            traceback.print_exc()


