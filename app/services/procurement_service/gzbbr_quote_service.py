# -*- coding:utf-8 -*-
# @Time    : 2026/7/7
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : gzbbr_quote_service.py
# @Software: PyCharm

from app.scripts.spiders.spider_entities.data_gzbbr import DataGzbbrSpider
from app.utils.database_connection import get_db_connection


import logging
logger = logging.getLogger('data_gzbbr')


class GzbbrQuoteService:
    """
    data.gzbbr.com 报价管理服务
    职责：
      1. 封装 DataGzbbrSpider 搜索/更新接口
      2. 远程更新成功后同步本地 crmapp_price_inquiry 失效时间
    """

    LOCAL_INQUIRY_TABLE = "crmapp_price_inquiry"

    @staticmethod
    def _parse_rows(data):
        """从响应中解析 rows 和 total"""
        rows = data.get('rows') or data.get('list') or data.get('data') or []
        total = data.get('total')
        return rows, total

    @staticmethod
    def _fetch_total(spider, oe, supplier, create_date_start, create_date_end):
        """通过 limit=1 获取远程接口返回的总数"""
        resp = spider.get_quote_price_index(
            number=oe,
            supplier_name=supplier,
            limit=1,
            offset=0,
            create_date_start=create_date_start,
            create_date_end=create_date_end
        )
        resp.raise_for_status()
        _, total = GzbbrQuoteService._parse_rows(resp.json())
        return total

    @staticmethod
    def search_quote_prices(store_code, oe='', supplier='', brand='',
                            create_date_start='', create_date_end=''):
        """搜索 data.gzbbr.com 报价列表
        统一循环拉取全部数据，在服务端完成品牌过滤后一次性返回，由前端本地分页。
        :return: {'rows': [...], 'total': int}
        """
        spider = DataGzbbrSpider(store_code=store_code)
        try:
            total = GzbbrQuoteService._fetch_total(
                spider, oe, supplier, create_date_start, create_date_end
            ) or 0

            all_rows = []
            batch_size = 1000
            for batch_offset in range(0, total, batch_size):
                resp = spider.get_quote_price_index(
                    number=oe,
                    supplier_name=supplier,
                    limit=batch_size,
                    offset=batch_offset,
                    create_date_start=create_date_start,
                    create_date_end=create_date_end
                )
                resp.raise_for_status()
                rows, _ = GzbbrQuoteService._parse_rows(resp.json())
                all_rows.extend(rows)

            if brand:
                brand_lower = brand.lower()
                all_rows = [
                    r for r in all_rows
                    if brand_lower in (r.get('brand_name') or '').lower()
                ]

            return {'rows': all_rows, 'total': len(all_rows)}
        finally:
            spider.close()

    @staticmethod
    def update_quote_lose_date(store_code, record, lose_date):
        """更新单条报价失效时间，并同步本地询价表"""
        spider = DataGzbbrSpider(store_code=store_code)
        try:
            resp = spider.update_quote_price(
                quote_price_id=record.get('quote_price_id'),
                cass_warehouse_id=record.get('cass_warehouse_id'),
                supplier_name=record.get('supplier_name'),
                number=record.get('number'),
                brand_name=record.get('brand_name'),
                price=record.get('price'),
                stock=record.get('stock'),
                lose_date=lose_date,
                remark=record.get('remark', '')
            )
            resp.raise_for_status()
            result = resp.json()

            # 远程更新成功后，同步本地询价表
            synced_rows = GzbbrQuoteService.sync_local_inquiry_expire_time(
                company=store_code,
                record=record,
                lose_date=lose_date
            )

            return {
                'success': True,
                'data': result,
                'synced_rows': synced_rows
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'record': record
            }
        finally:
            spider.close()

    @staticmethod
    def batch_update_lose_date(store_code, records, lose_date):
        """批量更新失效时间"""
        results = []
        for record in records:
            result = GzbbrQuoteService.update_quote_lose_date(
                store_code, record, lose_date
            )
            results.append(result)

        success_count = sum(1 for r in results if r['success'])
        failed_count = len(results) - success_count
        failed_details = [r for r in results if not r['success']]
        total_synced_rows = sum(r.get('synced_rows', 0) for r in results)

        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'failed_details': failed_details,
            'total_synced_rows': total_synced_rows
        }

    @staticmethod
    def sync_local_inquiry_expire_time(company, record, lose_date):
        """
        同步本地 crmapp_price_inquiry 失效时间
        :return: 更新的行数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    UPDATE {GzbbrQuoteService.LOCAL_INQUIRY_TABLE}
                    SET expire_time = %s
                    WHERE company = %s
                      AND supplier = %s
                      AND oe = %s
                      AND brand = %s
                """
                cursor.execute(sql, (
                    lose_date,
                    company,
                    record.get('supplier_name'),
                    record.get('number'),
                    record.get('brand_name')
                ))
                conn.commit()
                return cursor.rowcount
        finally:
            conn.close()

