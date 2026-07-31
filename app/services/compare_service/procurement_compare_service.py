"""
采购历史比价服务层
用于查询 crmapp_procurement_history 表的采购记录
"""
import re
from typing import List, Dict, Tuple, Optional
import pymysql
from app.utils.database_connection import get_db_connection
from app.models.purchase_history_compare_models import PurchaseRecord, MonthSummary, OECompareResult


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
        原厂/原厂国内4s件 互相匹配，其余品牌一对一
        """
        if brand in ProcurementCompareService.OEM_BRANDS:
            return ProcurementCompareService.OEM_BRANDS
        return [brand]

    @staticmethod
    def _oe_in_replace_number(search_oe: str, replace_number: str) -> bool:
        """
        判断搜索OE是否包含在replace_number的逗号分隔号码中
        支持中英文逗号
        """
        if not replace_number:
            return False
        numbers = [n.strip() for n in re.split(r'[，,]', replace_number) if n.strip()]
        return search_oe in numbers

    @staticmethod
    def query_compare_summary_rows(oe: str, brand: str, company: str) -> List[Dict]:
        """
        查询 crmapp_compare_summary 中所有匹配行
        匹配条件：
        - OE 匹配：oe = search_oe 或 replace_number 中包含 search_oe
        - 品牌匹配：原厂/原厂国内4s件 互相匹配，其余品牌一对一
        """
        match_brands = ProcurementCompareService._get_match_brands(brand)
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                brand_placeholders = ', '.join(['%s'] * len(match_brands))
                # 先按 oe 或 replace_number 包含 oe 模糊查询，再在Python中精确校验
                sql = f"""
                    SELECT oe, brand, product_name, l_model_zh, replace_number, frey_no
                    FROM crmapp_compare_summary
                    WHERE company = %s
                      AND (oe = %s OR replace_number LIKE %s)
                      AND brand IN ({brand_placeholders})
                """
                params = [company, oe, f"%{oe}%"]
                params.extend(match_brands)
                cursor.execute(sql, params)
                rows = cursor.fetchall()

                # 精确过滤：oe 完全匹配 或 replace_number 中包含 search_oe
                result = []
                for row in rows:
                    row_oe = row.get('oe') or ''
                    row_replace = row.get('replace_number') or ''
                    if row_oe == oe or ProcurementCompareService._oe_in_replace_number(oe, row_replace):
                        result.append(row)
                return result
        finally:
            conn.close()
    
    @staticmethod
    def _empty_beihuo_data() -> Dict:
        """返回空的备货数据字典"""
        return {
            'stock_quantity': None,
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
    def query_beihuo_by_barcode(barcode: str, company: str) -> Dict:
        """
        根据物料条码 + 公司查询备货数据
        """
        if not barcode:
            return ProcurementCompareService._empty_beihuo_data()

        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                    SELECT
                        `库存数量`, `标签`, `近1个月询价量`, `近3个月月均询价量`,
                        `近6个月月均销量`, `全国近1个月询价量`, `全国近3个月月均询价量`,
                        `今日销量`, `昨日销量`, `近7天销量`, `本月销量`,
                        `近6个月销量`, `近12个月销量`
                    FROM crmapp_beihuo
                    WHERE `物料条码` = %s AND company = %s
                    LIMIT 1
                """
                cursor.execute(sql, (barcode, company))
                row = cursor.fetchone()

                if row:
                    return {
                        'stock_quantity': row['库存数量'],
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
                else:
                    return ProcurementCompareService._empty_beihuo_data()
        finally:
            conn.close()
    
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
        price: Optional[float] = None
    ) -> OECompareResult:
        """
        根据已有数据构建 OECompareResult
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
                stock_quantity=beihuo_data.get('stock_quantity'),
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
                sales_12m=beihuo_data.get('sales_12m')
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
            stock_quantity=beihuo_data.get('stock_quantity'),
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
            sales_12m=beihuo_data.get('sales_12m')
        )
    
    @staticmethod
    def generate_compare_result(
        search_oe: str, brand: str, company: str, price: Optional[float] = None
    ) -> List[OECompareResult]:
        """
        生成单个OE的比对结果列表

        逻辑：
        1. 在 crmapp_compare_summary 中查询 OE/替换号 + 品牌匹配的所有行
        2. 对每一行用 frey_no + company 查询采购历史
        3. 用 frey_no（即物料条码）+ company 查询备货数据
        4. 兆配云价格仍按原始搜索 OE 查询
        5. replace_number 匹配到的产品，表格 OE 列显示 compare_summary.oe
        6. 汇总 replace_number 匹配且有库存的产品到 replace_stock_text

        Args:
            search_oe: 导入文件中的OE号
            brand: 品牌（不能为空）
            company: 公司代码
            price: 导入文件中的价格

        Returns:
            List[OECompareResult]: 匹配到的比对结果列表
        """
        # 不再支持品牌为空
        if not brand or not brand.strip():
            return []

        # 查询 compare_summary 所有匹配行
        summary_rows = ProcurementCompareService.query_compare_summary_rows(search_oe, brand, company)
        if not summary_rows:
            return []

        # 预查每行备货数据，并汇总替换号有库存信息（仅主号需要）
        rows_with_beihuo = []
        replace_stock_items = []
        for row in summary_rows:
            frey_no = row.get('frey_no') or ''
            beihuo_data = ProcurementCompareService.query_beihuo_by_barcode(frey_no, company)
            rows_with_beihuo.append((row, beihuo_data))

            # 通过 replace_number 匹配到的行（非直接OE匹配），且有库存
            if row.get('oe') != search_oe:
                stock = beihuo_data.get('stock_quantity')
                try:
                    stock_int = int(stock) if stock is not None else 0
                except (ValueError, TypeError):
                    stock_int = 0
                if stock_int > 0:
                    replace_stock_items.append({'oe': row['oe'], 'stock': stock_int})

        replace_stock_text = ProcurementCompareService._format_replace_stock_text(replace_stock_items)

        results = []
        for row, beihuo_data in rows_with_beihuo:
            frey_no = row.get('frey_no') or ''
            row_brand = row.get('brand') or brand
            # replace_number 匹配到的产品，显示 compare_summary.oe
            display_oe = row.get('oe') if row.get('oe') else search_oe
            is_main_oe = (display_oe == search_oe)

            # 用 frey_no + company 匹配采购历史
            records = ProcurementCompareService.query_procurement_by_frey_no(frey_no, company) if frey_no else []

            # 兆配云价格按各自匹配到的OE查询
            price_4s_cost, price_4s_sale = ProcurementCompareService.query_4s_price(display_oe)

            # 替换号有库存仅在主号行显示
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
                price=price
            )
            results.append(result)

        # 组内排序：主号行在前，replace_number匹配行按oe排序在后
        results.sort(key=lambda r: (r.oe != search_oe, r.oe or ''))

        return results

    @staticmethod
    def batch_generate_compare_results(items: List[Dict], company: str) -> List[OECompareResult]:
        """
        批量生成比对结果

        Args:
            items: OE和品牌列表，格式: [{"oe": "123", "brand": "博世", "price": "100"}, ...]
            company: 公司代码

        Returns:
            List[OECompareResult]: 比对结果列表
        """
        groups = []
        for item in items:
            oe = item.get('oe', '')
            brand = item.get('brand', '')
            price_str = item.get('price', '')
            if not oe or not brand:
                continue

            price = None
            if price_str:
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    price = None

            oe_results = ProcurementCompareService.generate_compare_result(oe, brand, company, price=price)
            if oe_results:
                groups.append((oe, oe_results))

        # 按主号OE排序后展平，并设置组号（每组共享一个序号）
        groups.sort(key=lambda x: x[0])
        results = []
        for group_index, (_, group_results) in enumerate(groups, start=1):
            for result in group_results:
                result.group_index = group_index
            results.extend(group_results)
        return results
