"""
采购历史比价服务层
用于查询 crmapp_procurement_history 表的采购记录
"""
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pymysql
from sqlalchemy.dialects.mysql import insert
from app.utils.database_connection import get_db_connection
from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.utils.replace_number.crm_api_client import search_products_by_numberlist
from app.models.purchase_history_compare_models import PurchaseRecord, MonthSummary, OECompareResult
from app.models.orm_models.car_parts_library_bmw import CarPartsLibraryBmw
from app.models.orm_models.car_parts_library_bmw_stock import CarPartsLibraryBmwStock
from app.models.orm_models.car_parts_library_benz import CarPartsLibraryBenz
from app.models.orm_models.crm_pp_name import CrmPpName
from app.services.pp_alias_service.pp_alias_pool_service import get_match_brands
from app.services.car_parts_library_service.bmw_crawler import (
    external_data_crawler,
    map_detail_cn_to_db,
    map_stock_cn_to_db,
)
from app.services.car_parts_library_service.mercedes_dalfsc_service import fetch_mercedes_data
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from config.config_list_manager.config_cache import get_config_value

logger = get_task_logger('purchase_history_compare')


class ProcurementCompareService:
    """采购历史比价服务类"""

    # 原厂品牌组：查询其中一个时同时匹配另一个
    OEM_BRANDS = ["原厂", "原厂国内4s件"]

    @staticmethod
    def search_procurement_history(
        company: str,
        oe_list: List[str] = None,
        supplier_list: List[str] = None,
        brand_list: List[str] = None,
        start_date: str = '',
        end_date: str = ''
    ) -> List[Dict]:
        """
        搜索采购历史记录
        根据OE、供应商、品牌、日期范围搜索
        不限制返回条数
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 基础SQL
                sql = """
                    SELECT id, oe, brand, supplier_name, unit_price,
                           purchase_date, `year_month`, company, created_at
                    FROM crmapp_procurement_history
                    WHERE company = %s
                """
                params = [company]

                # OE列表筛选
                if oe_list and isinstance(oe_list, list) and len(oe_list) > 0:
                    placeholders = ', '.join(['%s'] * len(oe_list))
                    sql += f" AND oe IN ({placeholders})"
                    params.extend(oe_list)

                # 供应商模糊匹配
                if supplier_list and isinstance(supplier_list, list) and len(supplier_list) > 0:
                    or_conditions = []
                    for supplier in supplier_list:
                        or_conditions.append("supplier_name LIKE %s")
                        params.append(f"%{supplier}%")
                    sql += " AND (" + " OR ".join(or_conditions) + ")"

                # 品牌列表筛选
                if brand_list and isinstance(brand_list, list) and len(brand_list) > 0:
                    placeholders = ', '.join(['%s'] * len(brand_list))
                    sql += f" AND brand IN ({placeholders})"
                    params.extend(brand_list)

                # 日期范围筛选
                if start_date:
                    sql += " AND purchase_date >= %s"
                    params.append(start_date)
                if end_date:
                    sql += " AND purchase_date <= %s"
                    params.append(end_date)

                # 排序
                sql += " ORDER BY purchase_date DESC, oe ASC, brand ASC"

                # 执行查询（不限制条数）
                cursor.execute(sql, params)
                rows = cursor.fetchall()

                # 格式化数据
                result_data = []
                for row in rows:
                    result_data.append({
                        'id': row['id'],
                        'oe': row['oe'],
                        'brand': row['brand'],
                        'supplier_name': row['supplier_name'],
                        'unit_price': float(row['unit_price']) if row['unit_price'] else 0,
                        'purchase_date': row['purchase_date'].strftime('%Y-%m-%d') if row['purchase_date'] else '',
                        'year_month': row['year_month'],
                        'company': row['company'],
                        'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row['created_at'] else ''
                    })

                return result_data

        finally:
            conn.close()

    @staticmethod
    def query_by_oe_brand(oe: str, brand: str, company: str) -> List[PurchaseRecord]:
        """
        根据OE+品牌查询采购历史明细（旧逻辑，保留兼容）
        查询 crmapp_procurement_history_detail 表
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                    SELECT number, brand, fullname, unit_cost, create_date, `year_month`
                    FROM crmapp_procurement_history_detail
                    WHERE number = %s AND brand = %s AND company = %s
                    ORDER BY create_date DESC
                """
                cursor.execute(sql, (oe, brand, company))
                rows = cursor.fetchall()
                return ProcurementCompareService._rows_to_purchase_records(rows)
        finally:
            conn.close()

    @staticmethod
    def _rows_to_purchase_records(rows: List[Dict]) -> List[PurchaseRecord]:
        """将数据库行转换为 PurchaseRecord 列表"""
        records = []
        for row in rows:
            if row['year_month']:
                year_month_parts = str(row['year_month']).split('-')
                year = int(year_month_parts[0])
                month = int(year_month_parts[1])
            else:
                create_date = row['create_date']
                if create_date:
                    year = create_date.year
                    month = create_date.month
                else:
                    continue

            records.append(PurchaseRecord(
                year=year,
                month=month,
                supplier=row['fullname'] or '',
                price=float(row['unit_cost']) if row['unit_cost'] else 0.0
            ))
        return records

    @staticmethod
    def query_procurement_by_frey_no(frey_no: str, company: str) -> List[PurchaseRecord]:
        """
        根据 frey_no + 公司查询采购历史明细
        查询 crmapp_procurement_history_detail 表
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                    SELECT number, brand, fullname, unit_cost, create_date, `year_month`
                    FROM crmapp_procurement_history_detail
                    WHERE frey_no = %s AND company = %s
                    ORDER BY create_date DESC
                """
                cursor.execute(sql, (frey_no, company))
                rows = cursor.fetchall()
                return ProcurementCompareService._rows_to_purchase_records(rows)
        finally:
            conn.close()
    
    @staticmethod
    def _filter_valid_records(records: List[PurchaseRecord]) -> List[PurchaseRecord]:
        """
        过滤掉价格为0的记录
        
        Args:
            records: 原始采购记录列表
            
        Returns:
            List[PurchaseRecord]: 过滤后的记录列表（价格>0）
        """
        return [r for r in records if r.price > 0]
    
    @staticmethod
    def aggregate_by_month(records: List[PurchaseRecord]) -> Dict[int, MonthSummary]:
        """
        按月份聚合数据
        
        Args:
            records: 采购记录列表
            
        Returns:
            Dict[int, MonthSummary]: 月份汇总数据，key为月份(1-12)
        """
        # 过滤价格为0的记录
        valid_records = ProcurementCompareService._filter_valid_records(records)
        
        # 按月份分组
        month_groups: Dict[int, List[PurchaseRecord]] = {i: [] for i in range(1, 13)}
        
        for record in valid_records:
            if 1 <= record.month <= 12:
                month_groups[record.month].append(record)
        
        # 生成月份汇总
        month_summaries = {}
        for month in range(1, 13):
            month_records = month_groups[month]
            if month_records:
                # 按价格排序获取最低价
                sorted_records = sorted(month_records, key=lambda x: x.price)
                lowest_price = sorted_records[0].price if sorted_records else 0.0
                
                month_summaries[month] = MonthSummary(
                    month=month,
                    lowest_price=lowest_price,
                    all_records=month_records
                )
        
        return month_summaries
    
    @staticmethod
    def query_4s_price(oe: str) -> Tuple[Optional[float], Optional[float]]:
        """
        查询4S价格（含税进价和售价）
        从zhaopeiyun表查询
        
        Args:
            oe: OE号（对应配件编号）
            
        Returns:
            Tuple[Optional[float], Optional[float]]: (4S含税进价, 4S含税售价)
            查不到返回 (None, None)
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 查询zhaopeiyun表，使用配件编号匹配OE
                sql = """
                    SELECT `4S含税进价`, `4S含税售价`
                    FROM zhaopeiyun
                    WHERE `配件编号` = %s
                    LIMIT 1
                """
                cursor.execute(sql, (oe,))
                row = cursor.fetchone()
                
                if row:
                    cost = float(row['4S含税进价']) if row['4S含税进价'] is not None else None
                    sale = float(row['4S含税售价']) if row['4S含税售价'] is not None else None
                    return (cost, sale)
                else:
                    return (None, None)
        finally:
            conn.close()
    
    @staticmethod
    def _get_match_brands(brand: str) -> List[str]:
        """
        获取需要匹配的品牌列表
        原厂/原厂国内4s件 互相匹配，其余品牌查别名池
        """
        return get_match_brands(brand, oem_brands=ProcurementCompareService.OEM_BRANDS)

    @staticmethod
    def _empty_beihuo_data() -> Dict:
        """返回空的备货数据字典（库存数量已改由 CRM 实时接口提供，不在此表取）"""
        return {
            'tag': None,
            'inquiry_1m': None,
            'inquiry_3m_avg': None,
            'sales_6m_avg': None,
            'inquiry_1m_national': None,
            'inquiry_3m_avg_national': None,
            'sales_today': None,
            'sales_yesterday': None,
            'sales_7d': None,
            'sales_month': None,
            'sales_6m': None,
            'sales_12m': None
        }

    @staticmethod
    def _get_tax_rate(config_key: str) -> float:
        """从配置读取税率，失败返回默认 1.13"""
        try:
            config = get_config_value(config_key)
            if config and isinstance(config, dict):
                return float(config.get('tax_rate', 1.13))
        except Exception:
            pass
        return 1.13

    @staticmethod
    def _ensure_benz_oe_prefix(oe: str) -> str:
        """奔驰 OE 统一加 A 前缀"""
        if oe and not str(oe).upper().startswith('A'):
            return 'A' + str(oe)
        return str(oe) if oe else oe

    @staticmethod
    def _get_vehicle_brand(oe: str, company: str, summary_map: Dict = None) -> Optional[str]:
        """
        根据 CRM 返回的 cass_oebrand_name 判断品牌
        不使用 crmapp_compare_summary.vehicle_brand 数据库查询
        不使用 OE 前缀兜底；取不出直接返回 None，由调用方处理
        """
        if summary_map:
            # 优先精确匹配 oe 作为 key
            if oe in summary_map:
                rows = summary_map[oe]
                if isinstance(rows, list):
                    for row in rows:
                        v = str(row.get('cass_oebrand_name') or row.get('vehicle_brand') or '').strip()
                        if v:
                            if '奔驰' in v:
                                return '奔驰'
                            if '宝马' in v:
                                return '宝马'
            # 再遍历所有 key 的 rows 查找该 OE
            for rows in summary_map.values():
                if isinstance(rows, list):
                    for row in rows:
                        if row.get('oe') != oe:
                            continue
                        v = str(row.get('cass_oebrand_name') or row.get('vehicle_brand') or '').strip()
                        if v:
                            if '奔驰' in v:
                                return '奔驰'
                            if '宝马' in v:
                                return '宝马'
        return None

    @staticmethod
    def _query_bmw_price_from_local(oe: str) -> Tuple[Optional[float], Optional[float]]:
        """从 car_parts_library_bmw 查近两天的价格"""
        cutoff = datetime.now() - timedelta(days=2)
        tax_rate = ProcurementCompareService._get_tax_rate('bmw_car_parts_libray')
        with orm_session() as session:
            part = session.query(CarPartsLibraryBmw).filter(
                CarPartsLibraryBmw.part_number == oe,
                CarPartsLibraryBmw.updated_at >= cutoff
            ).first()
            if not part:
                return (None, None)
            cost = None
            sale = None
            if part.dealer_net_stock is not None:
                try:
                    cost = float(part.dealer_net_stock) * tax_rate
                except (ValueError, TypeError):
                    cost = None
            if part.retail_price is not None:
                try:
                    sale = float(part.retail_price) * tax_rate
                except (ValueError, TypeError):
                    sale = None
            return (cost, sale)

    @staticmethod
    def _query_benz_price_from_local(oe: str) -> Tuple[Optional[float], Optional[float]]:
        """从 car_parts_library_benz 查近两天的价格"""
        cutoff = datetime.now() - timedelta(days=2)
        tax_rate = ProcurementCompareService._get_tax_rate('mercedes_benz')
        with orm_session() as session:
            part = session.query(CarPartsLibraryBenz).filter(
                CarPartsLibraryBenz.part_number == oe,
                CarPartsLibraryBenz.updated_at >= cutoff
            ).first()
            if not part:
                return (None, None)
            cost = None
            sale = None
            if part.wholesale_price is not None:
                try:
                    cost = float(part.wholesale_price) * tax_rate
                except (ValueError, TypeError):
                    cost = None
            if part.msrp is not None:
                try:
                    sale = float(part.msrp) * tax_rate
                except (ValueError, TypeError):
                    sale = None
            return (cost, sale)

    @staticmethod
    def _refresh_bmw_price(oe: str) -> bool:
        """调用宝马官网接口更新本地库，不走兆配云回退"""
        try:
            data = external_data_crawler(oe, is_unit=False)
            if not data or not isinstance(data, dict):
                return False
            detail = map_detail_cn_to_db(data.get('detail', {}))
            stock = map_stock_cn_to_db(data.get('stock', {}))
            if not detail and not stock:
                return False
            with orm_session() as session:
                if detail and detail.get('part_number'):
                    detail_stmt = insert(CarPartsLibraryBmw).values(**detail)
                    detail_update = {
                        c.name: c for c in detail_stmt.inserted
                        if c.name not in ['part_number', 'created_at', 'updated_at']
                    }
                    detail_stmt = detail_stmt.on_duplicate_key_update(**detail_update)
                    session.execute(detail_stmt)
                if stock and stock.get('part_number'):
                    stock_stmt = insert(CarPartsLibraryBmwStock).values(**stock)
                    stock_update = {
                        c.name: c for c in stock_stmt.inserted
                        if c.name not in ['part_number', 'created_at', 'updated_at']
                    }
                    stock_stmt = stock_stmt.on_duplicate_key_update(**stock_update)
                    session.execute(stock_stmt)
            return True
        except Exception as e:
            logger.warning(f"[BMW] 远程更新失败: {oe}, {e}")
            return False

    @staticmethod
    def _refresh_benz_price(oe: str) -> bool:
        """调用奔驰接口更新本地库"""
        try:
            result = fetch_mercedes_data([oe])
            if result and result.get('status'):
                return True
            logger.warning(f"[Benz] 远程更新失败: {oe}, {result}")
            return False
        except Exception as e:
            logger.warning(f"[Benz] 远程更新失败: {oe}, {e}")
            return False

    @staticmethod
    def _format_replace_stock_text(items: List[Dict]) -> str:
        """
        格式化替换号有库存文本
        单条：OE：库存
        多条：1. OE：库存\n2. OE：库存
        """
        if not items:
            return ""
        if len(items) == 1:
            return f"{items[0]['oe']}：{items[0]['stock']}"
        lines = []
        for idx, item in enumerate(items, start=1):
            lines.append(f"{idx}. {item['oe']}：{item['stock']}")
        return "\n".join(lines)

    @staticmethod
    def _build_oe_compare_result(
        oe: str,
        search_oe: str,
        brand: str,
        company: str,
        product_name: Optional[str],
        spec: Optional[str],
        replace_name: Optional[str],
        frey_no: Optional[str],
        records: List[PurchaseRecord],
        price_4s_cost: Optional[float],
        price_4s_sale: Optional[float],
        beihuo_data: Dict,
        replace_stock_text: Optional[str],
        price: Optional[float] = None,
        search_brand: Optional[str] = None,
        brand_code: Optional[str] = None,
        stock: Optional[int] = None,
        stock_zaitu: Optional[int] = None,
        safe_stock: Optional[int] = None
    ) -> OECompareResult:
        """
        根据已有数据构建 OECompareResult
        库存三字段（库存/在途/安全库存）来自 CRM 实时接口，其余备货字段来自 beihuo_data
        """
        if not records:
            return OECompareResult(
                oe=oe,
                search_oe=search_oe,
                brand=brand,
                month_summaries={},
                overall_lowest=("", "", 0.0),
                overall_highest=("", "", 0.0),
                price_4s_cost=price_4s_cost,
                price_4s_sale=price_4s_sale,
                product_name=product_name,
                spec=spec,
                replace_name=replace_name,
                frey_no=frey_no,
                price=price,
                replace_stock_text=replace_stock_text,
                stock_quantity=stock,
                stock_zaitu=stock_zaitu,
                safe_stock=safe_stock,
                tag=beihuo_data.get('tag'),
                inquiry_1m=beihuo_data.get('inquiry_1m'),
                inquiry_3m_avg=beihuo_data.get('inquiry_3m_avg'),
                sales_6m_avg=beihuo_data.get('sales_6m_avg'),
                inquiry_1m_national=beihuo_data.get('inquiry_1m_national'),
                inquiry_3m_avg_national=beihuo_data.get('inquiry_3m_avg_national'),
                sales_today=beihuo_data.get('sales_today'),
                sales_yesterday=beihuo_data.get('sales_yesterday'),
                sales_7d=beihuo_data.get('sales_7d'),
                sales_month=beihuo_data.get('sales_month'),
                sales_6m=beihuo_data.get('sales_6m'),
                sales_12m=beihuo_data.get('sales_12m'),
                search_brand=search_brand,
                brand_code=brand_code
            )

        month_summaries = ProcurementCompareService.aggregate_by_month(records)
        valid_records = ProcurementCompareService._filter_valid_records(records)
        if valid_records:
            all_records_sorted = sorted(valid_records, key=lambda x: x.price)
            lowest = all_records_sorted[0]
            highest = all_records_sorted[-1] if len(all_records_sorted) > 1 else lowest
            overall_lowest = (f"{lowest.year}-{lowest.month:02d}", lowest.supplier, lowest.price)
            overall_highest = (f"{highest.year}-{highest.month:02d}", highest.supplier, highest.price)
        else:
            overall_lowest = ("", "", 0.0)
            overall_highest = ("", "", 0.0)

        return OECompareResult(
            oe=oe,
            search_oe=search_oe,
            brand=brand,
            month_summaries=month_summaries,
            overall_lowest=overall_lowest,
            overall_highest=overall_highest,
            price_4s_cost=price_4s_cost,
            price_4s_sale=price_4s_sale,
            product_name=product_name,
            spec=spec,
            replace_name=replace_name,
            frey_no=frey_no,
            price=price,
            replace_stock_text=replace_stock_text,
            stock_quantity=stock,
            stock_zaitu=stock_zaitu,
            safe_stock=safe_stock,
            tag=beihuo_data.get('tag'),
            inquiry_1m=beihuo_data.get('inquiry_1m'),
            inquiry_3m_avg=beihuo_data.get('inquiry_3m_avg'),
            sales_6m_avg=beihuo_data.get('sales_6m_avg'),
            inquiry_1m_national=beihuo_data.get('inquiry_1m_national'),
            inquiry_3m_avg_national=beihuo_data.get('inquiry_3m_avg_national'),
            sales_today=beihuo_data.get('sales_today'),
            sales_yesterday=beihuo_data.get('sales_yesterday'),
            sales_7d=beihuo_data.get('sales_7d'),
            sales_month=beihuo_data.get('sales_month'),
            sales_6m=beihuo_data.get('sales_6m'),
            sales_12m=beihuo_data.get('sales_12m'),
            search_brand=search_brand,
            brand_code=brand_code
        )
    
    @staticmethod
    def _query_crm_summary_by_brand_code(brand_code: str) -> List[Dict]:
        """
        通过 CRM Product.Product/list 接口用品牌号查询产品信息
        匹配 child.brand_code == brand_code（去除首尾空格）
        返回: [匹配行列表]，结构和 crmapp_compare_summary 查询结果一致
        """
        if not brand_code:
            return []
        target_code = str(brand_code).strip()
        try:
            spider = CrmGzbbrSpider()
            resp = spider.get_product_product_list(aikeyword=target_code, limit=200)
            if not resp or not hasattr(resp, 'json'):
                logger.warning(f"[CRM-brand_code] 步骤2-发起请求: 失败，响应为空或不可解析")
                return []
            data = resp.json()
            if not data or (data.get('code') != 0 and data.get('status') != 200):
                logger.warning(f"[CRM-brand_code] 步骤2-发起请求: 失败，响应状态异常: code={data.get('code')}, status={data.get('status')}")
                return []

            result = []
            product_list = data.get('data', {}).get('data', [])
            total_child_count = 0
            for product in product_list:
                for child in product.get('child', []):
                    total_child_count += 1
                    child_brand_code = str(child.get('brand_code') or '').strip()
                    child_frey_no = str(child.get('frey_no') or '').strip()
                    child_number = str(child.get('number') or '').strip()
                    child_brand_name = str(child.get('brand_name') or '').strip()
                    # 匹配规则：先 brand_code 精确匹配，兜底用 frey_no 精确匹配
                    matched_brand_code = (child_brand_code == target_code)
                    matched_frey = (child_frey_no and child_frey_no == target_code)
                    matched = matched_brand_code or matched_frey
                    if not matched:
                        continue
                    cass_oebrand = str(child.get('cass_oebrand_name') or '').strip()
                    row = {
                        'oe': child_number,
                        'brand': child_brand_name,
                        'product_name': str(child.get('l_name_zh') or '').strip(),
                        'l_model_zh': str(child.get('l_model_zh') or '').strip(),
                        'replace_number': '',
                        'frey_no': child_frey_no,
                        'cass_oebrand_name': cass_oebrand,
                    }
                    row.update(ProcurementCompareService._extract_crm_stock_fields(child))
                    result.append(row)
            return result
        except Exception as e:
            logger.exception(f"[CRM-brand_code] 异常: {e}")
            return []

    # CRM numberlist 搜索并发数
    CRM_OE_MAX_WORKERS = 5

    @staticmethod
    def _to_int_or_none(value) -> Optional[int]:
        """CRM 库存类字段统一转 int；空值/无法解析返回 None"""
        if value is None or value == '':
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_crm_stock_fields(child: Dict) -> Dict:
        """提取 CRM child 的三个库存字段：库存/在途/安全库存"""
        return {
            'stock': ProcurementCompareService._to_int_or_none(child.get('stock')),
            'stock_zaitu': ProcurementCompareService._to_int_or_none(child.get('stock_zaitu')),
            'safe_stock': ProcurementCompareService._to_int_or_none(child.get('safe_stock')),
        }

    @staticmethod
    def _extract_display_number_text(display_number) -> str:
        """从 display_number 数组提取通用号，中文逗号拼接，去重保序"""
        if not display_number or not isinstance(display_number, list):
            return ''
        numbers = []
        for item in display_number:
            if isinstance(item, dict):
                num = str(item.get('number') or '').strip()
                if num and num not in numbers:
                    numbers.append(num)
        return '，'.join(numbers)

    @staticmethod
    def _crm_child_to_summary_row(child: Dict) -> Dict:
        """把 CRM child 产品映射为比价统一行结构（与品牌号查询分支一致）"""
        row = {
            'oe': str(child.get('number') or '').strip(),
            'brand': str(child.get('brand_name') or '').strip(),
            'product_name': str(child.get('l_name_zh') or '').strip(),
            'l_model_zh': str(child.get('l_model_zh') or '').strip(),
            'replace_number': ProcurementCompareService._extract_display_number_text(
                child.get('display_number')
            ),
            'frey_no': str(child.get('frey_no') or '').strip(),
            'cass_oebrand_name': str(child.get('cass_oebrand_name') or '').strip(),
        }
        row.update(ProcurementCompareService._extract_crm_stock_fields(child))
        return row

    @staticmethod
    def _query_crm_children_by_oe(company: str, oe: str) -> List[Dict]:
        """
        单个 OE 调用 CRM Product.Product/list（numberlist 不支持多 OE 逗号分隔）
        返回接口原始 child 列表；请求失败返回空列表
        """
        try:
            api_data = search_products_by_numberlist(company, oe)
        except Exception as e:
            logger.warning(f"[CRM-numberlist] OE={oe} 查询失败: {e}")
            return []
        if not api_data:
            return []
        children = []
        for group in api_data.get('data', []):
            children.extend(group.get('child', []))
        return children

    @staticmethod
    def _batch_query_crm_by_oe(items: List[Dict], company: str) -> Dict[str, List[Dict]]:
        """
        用 CRM numberlist 接口批量匹配无品牌号的 OE
        - numberlist 每次只传一个 OE，多线程并发调用
        - 不再按 OE 长度区分匹配方式，也不做替换号比对
        - 接口返回的 child 只需品牌命中规则（原厂互通/别名池）即选取
        返回: {search_oe: [匹配行列表]}
        """
        oe_brand_map: Dict[str, set] = {}
        for item in items:
            oe = (item.get('oe') or '').strip()
            brand = (item.get('brand') or '').strip()
            if not oe or not brand:
                continue
            brands = set(ProcurementCompareService._get_match_brands(brand))
            if oe in oe_brand_map:
                oe_brand_map[oe].update(brands)
            else:
                oe_brand_map[oe] = brands

        result: Dict[str, List[Dict]] = {oe: [] for oe in oe_brand_map}
        if not oe_brand_map:
            return result

        with ThreadPoolExecutor(max_workers=ProcurementCompareService.CRM_OE_MAX_WORKERS) as executor:
            future_to_oe = {
                executor.submit(ProcurementCompareService._query_crm_children_by_oe, company, oe): oe
                for oe in oe_brand_map
            }
            for future in as_completed(future_to_oe):
                oe = future_to_oe[future]
                try:
                    children = future.result()
                except Exception as e:
                    logger.warning(f"[CRM-numberlist] OE={oe} 线程异常: {e}")
                    continue
                match_brands = oe_brand_map[oe]
                for child in children:
                    row = ProcurementCompareService._crm_child_to_summary_row(child)
                    if row['brand'] and row['brand'] in match_brands:
                        result[oe].append(row)
        return result

    @staticmethod
    def _batch_query_procurement(frey_nos: List[str], company: str) -> Dict[str, List[PurchaseRecord]]:
        """批量查询采购历史，返回 {frey_no: [PurchaseRecord列表]}"""
        if not frey_nos:
            return {}

        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                placeholders = ', '.join(['%s'] * len(frey_nos))
                sql = f"""
                    SELECT number, brand, fullname, unit_cost, create_date, `year_month`, frey_no
                    FROM crmapp_procurement_history_detail
                    WHERE frey_no IN ({placeholders}) AND company = %s
                    ORDER BY create_date DESC
                """
                cursor.execute(sql, list(frey_nos) + [company])
                rows = cursor.fetchall()

                grouped = {}
                for row in rows:
                    fn = row.get('frey_no') or ''
                    if fn not in grouped:
                        grouped[fn] = []
                    grouped[fn].append(row)

                return {
                    fn: ProcurementCompareService._rows_to_purchase_records(rlist)
                    for fn, rlist in grouped.items()
                }
        finally:
            conn.close()

    @staticmethod
    def _batch_query_beihuo(barcodes: List[str], company: str) -> Dict[str, Dict]:
        """批量查询备货数据，返回 {barcode: beihuo_data}"""
        if not barcodes:
            return {}

        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                placeholders = ', '.join(['%s'] * len(barcodes))
                sql = f"""
                    SELECT
                        `标签`, `近1个月询价量`, `近3个月月均询价量`,
                        `近6个月月均销量`, `全国近1个月询价量`, `全国近3个月月均询价量`,
                        `今日销量`, `昨日销量`, `近7天销量`, `本月销量`,
                        `近6个月销量`, `近12个月销量`, `物料条码`
                    FROM crmapp_beihuo
                    WHERE `物料条码` IN ({placeholders}) AND company = %s
                """
                cursor.execute(sql, list(barcodes) + [company])
                rows = cursor.fetchall()

                result = {}
                for row in rows:
                    barcode = row.get('物料条码') or ''
                    result[barcode] = {
                        'tag': row['标签'],
                        'inquiry_1m': row['近1个月询价量'],
                        'inquiry_3m_avg': row['近3个月月均询价量'],
                        'sales_6m_avg': row['近6个月月均销量'],
                        'inquiry_1m_national': row['全国近1个月询价量'],
                        'inquiry_3m_avg_national': row['全国近3个月月均询价量'],
                        'sales_today': row['今日销量'],
                        'sales_yesterday': row['昨日销量'],
                        'sales_7d': row['近7天销量'],
                        'sales_month': row['本月销量'],
                        'sales_6m': row['近6个月销量'],
                        'sales_12m': row['近12个月销量']
                    }
                return result
        finally:
            conn.close()

    @staticmethod
    def _batch_query_4s_prices(oes: List[str]) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
        """批量查询4S价格，返回 {oe: (cost, sale)}"""
        if not oes:
            return {}

        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                placeholders = ', '.join(['%s'] * len(oes))
                sql = f"""
                    SELECT `配件编号`, `4S含税进价`, `4S含税售价`
                    FROM zhaopeiyun
                    WHERE `配件编号` IN ({placeholders})
                """
                cursor.execute(sql, list(oes))
                rows = cursor.fetchall()

                result = {}
                for row in rows:
                    oe = row.get('配件编号') or ''
                    cost = float(row['4S含税进价']) if row['4S含税进价'] is not None else None
                    sale = float(row['4S含税售价']) if row['4S含税售价'] is not None else None
                    result[oe] = (cost, sale)
                return result
        finally:
            conn.close()

    @staticmethod
    def batch_generate_compare_results(
        items: List[Dict],
        company: str,
        progress_callback=None
    ) -> List[OECompareResult]:
        """
        批量生成比对结果（重构版：批量查询，大幅减少数据库往返）

        Args:
            items: OE和品牌列表，格式: [{"oe": "123", "brand": "博世", "price": "100"}, ...]
            company: 公司代码
            progress_callback: 进度回调函数，签名为 (current, total, message)

        Returns:
            List[OECompareResult]: 比对结果列表
        """
        def _report(current: int, total: int, message: str):
            if progress_callback:
                try:
                    progress_callback(current, total, message)
                except Exception:
                    pass

        total_start = time.time()

        # 1. 收集有效 items
        step_start = time.time()
        valid_items = []
        skipped_empty = 0
        for item in items:
            oe = item.get('oe', '')
            brand = item.get('brand', '')
            price_str = item.get('price', '')
            brand_code = item.get('brand_code', '')
            # (oe+品牌) 或 brand_code 有值其一即可；优先使用 brand_code
            has_oe_brand = bool(oe and brand)
            has_brand_code = bool(brand_code)
            if not (has_oe_brand or has_brand_code):
                skipped_empty += 1
                continue

            price = None
            if price_str:
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    price = None

            valid_items.append({'oe': oe, 'brand': brand, 'price': price, 'brand_code': brand_code})

        if not valid_items:
            return []

        _report(10, 100, '正在查询基础数据...')

        # 2. 查询产品信息：有品牌号的走 CRM aikeyword，无品牌号的走 CRM numberlist
        step_start = time.time()
        summary_map = {}
        oe_query_items = []
        for idx, item in enumerate(valid_items, start=1):
            if item.get('brand_code'):
                bc = item['brand_code']
                rows = ProcurementCompareService._query_crm_summary_by_brand_code(bc)
                # 若上传时未填 oe，用 CRM 返回的第一个 oe 作为后续 key
                if rows and not item['oe']:
                    item['oe'] = rows[0].get('oe') or ''
                if item['oe']:
                    summary_map[item['oe']] = rows
                else:
                    summary_map[item['brand_code']] = rows
            else:
                oe_query_items.append(item)
        if oe_query_items:
            crm_summary_map = ProcurementCompareService._batch_query_crm_by_oe(oe_query_items, company)
            summary_map.update(crm_summary_map)
        _report(20, 100, '正在查询采购与备货数据...')

        # 3. 收集所有 frey_no 和 display_oe（仅 list 接口匹配成功的产品 OE 才查4S价）
        step_start = time.time()
        all_frey_nos = set()
        all_display_oes = set()
        for item in valid_items:
            search_oe = item['oe']
            brand_code = item.get('brand_code', '')
            if not search_oe:
                # 仅有品牌号但未从 CRM 拿到 oe 时，跳过 4S 价格查询
                continue
            rows = summary_map.get(search_oe, [])
            for row in rows:
                fn = row.get('frey_no') or ''
                if fn:
                    all_frey_nos.add(fn)
                display_oe = row.get('oe') or search_oe
                all_display_oes.add(display_oe)

        # 4. 批量查询采购历史、备货、4S价格
        step_start = time.time()
        procurement_map = ProcurementCompareService._batch_query_procurement(list(all_frey_nos), company)

        step_start = time.time()
        beihuo_map = ProcurementCompareService._batch_query_beihuo(list(all_frey_nos), company)

        step_start = time.time()
        price_4s_map = ProcurementCompareService._batch_query_4s_prices(list(all_display_oes))
        _report(40, 100, '正在补全 4S 价格...')

        # 4d. 对缺失 4S 价格的 OE，先查本地库，再触发远程更新
        step_start = time.time()
        missing_4s_oes = list({
            oe for oe in all_display_oes
            if oe not in price_4s_map or price_4s_map.get(oe) == (None, None)
        })
        total_missing = len(missing_4s_oes)
        skip_no_brand = 0
        for idx, oe in enumerate(missing_4s_oes, start=1):
            vehicle_brand = ProcurementCompareService._get_vehicle_brand(oe, company, summary_map)
            if not vehicle_brand:
                skip_no_brand += 1
                continue
            price_pair = (None, None)
            if vehicle_brand == '宝马':
                price_pair = ProcurementCompareService._query_bmw_price_from_local(oe)
                if price_pair == (None, None):
                    ProcurementCompareService._refresh_bmw_price(oe)
                    price_pair = ProcurementCompareService._query_bmw_price_from_local(oe)
            elif vehicle_brand == '奔驰':
                normalized_oe = ProcurementCompareService._ensure_benz_oe_prefix(oe)
                price_pair = ProcurementCompareService._query_benz_price_from_local(normalized_oe)
                if price_pair == (None, None):
                    ProcurementCompareService._refresh_benz_price(normalized_oe)
                    price_pair = ProcurementCompareService._query_benz_price_from_local(normalized_oe)
            if price_pair != (None, None):
                price_4s_map[oe] = price_pair
            _report(
                int(40 + (idx / total_missing * 40)),
                100,
                f'正在补全 4S 价格 ({idx}/{total_missing})...'
            )

        # 5. 内存组装结果（无匹配的OE也保留，生成空行）
        step_start = time.time()
        groups = []
        no_summary_count = 0
        total_result_rows = 0
        for item_idx, item in enumerate(valid_items, start=1):
            search_oe = item['oe']
            brand = item['brand']
            price = item['price']
            brand_code = item.get('brand_code', '')
            search_key = search_oe or brand_code
            display_label = search_oe or brand_code
            is_bc_item = bool(brand_code)

            summary_rows = summary_map.get(search_key, [])
            if not summary_rows:
                # 无匹配：生成一行基础数据
                no_summary_count += 1
                price_4s_cost, price_4s_sale = price_4s_map.get(search_oe, (None, None)) if search_oe else (None, None)
                result = ProcurementCompareService._build_oe_compare_result(
                    oe=display_label,
                    search_oe=display_label,
                    brand=brand,
                    company=company,
                    product_name=None,
                    spec=None,
                    replace_name=None,
                    frey_no=None,
                    records=[],
                    price_4s_cost=price_4s_cost,
                    price_4s_sale=price_4s_sale,
                    beihuo_data=ProcurementCompareService._empty_beihuo_data(),
                    replace_stock_text=None,
                    price=price,
                    search_brand=brand,
                    brand_code=brand_code
                )
                groups.append((display_label, [result]))
                total_result_rows += 1
                continue

            # 预查备货并汇总替换号有库存（库存取 CRM 实时 stock）
            replace_stock_items = []
            rows_with_beihuo = []
            for row in summary_rows:
                frey_no = row.get('frey_no') or ''
                beihuo_data = beihuo_map.get(frey_no, ProcurementCompareService._empty_beihuo_data())
                rows_with_beihuo.append((row, beihuo_data))

                if row.get('oe') != search_oe:
                    stock_int = row.get('stock') or 0
                    if stock_int > 0:
                        replace_stock_items.append({'oe': row['oe'], 'stock': stock_int})

            replace_stock_text = ProcurementCompareService._format_replace_stock_text(replace_stock_items)

            results = []
            for row_idx, (row, beihuo_data) in enumerate(rows_with_beihuo, start=1):
                frey_no = row.get('frey_no') or ''
                row_brand = row.get('brand') or brand
                display_oe = row.get('oe') if row.get('oe') else search_oe
                is_main_oe = (display_oe == search_oe)

                records = procurement_map.get(frey_no, [])
                price_4s_cost, price_4s_sale = price_4s_map.get(display_oe, (None, None))
                row_replace_stock_text = replace_stock_text if is_main_oe else None

                result = ProcurementCompareService._build_oe_compare_result(
                    oe=display_oe,
                    search_oe=search_oe,
                    brand=row_brand,
                    company=company,
                    product_name=row.get('product_name') if row.get('product_name') else None,
                    spec=row.get('l_model_zh') if row.get('l_model_zh') else None,
                    replace_name=row.get('replace_number') if row.get('replace_number') else None,
                    frey_no=frey_no if frey_no else None,
                    records=records,
                    price_4s_cost=price_4s_cost,
                    price_4s_sale=price_4s_sale,
                    beihuo_data=beihuo_data,
                    replace_stock_text=row_replace_stock_text,
                    price=price,
                    search_brand=brand,
                    brand_code=brand_code,
                    stock=row.get('stock'),
                    stock_zaitu=row.get('stock_zaitu'),
                    safe_stock=row.get('safe_stock')
                )
                results.append(result)

            # 组内排序：主号行在前，replace_number匹配行按oe排序在后
            results.sort(key=lambda r: (r.oe != search_oe, r.oe or ''))
            groups.append((search_oe, results))
            total_result_rows += len(results)

        _report(90, 100, '正在整理比对结果...')

        # 6. 按主号OE排序后展平，并设置组号
        step_start = time.time()
        groups.sort(key=lambda x: x[0])
        results = []
        for group_index, (_, group_results) in enumerate(groups, start=1):
            for result in group_results:
                result.group_index = group_index
            results.extend(group_results)
        _report(100, 100, '比对结果生成完成')
        return results
