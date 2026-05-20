"""
采购历史比价服务层
用于查询 crmapp_procurement_history 表的采购记录
"""
from typing import List, Dict, Tuple, Optional
import pymysql
from app.utils.database_connection import get_db_connection
from app.models.purchase_history_compare_models import PurchaseRecord, MonthSummary, OECompareResult


class ProcurementCompareService:
    """采购历史比价服务类"""

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
        根据OE+品牌查询采购历史明细
        查询 crmapp_procurement_history_detail 表
        如果brand为空，则只用OE查询
        
        Args:
            oe: OE号
            brand: 品牌（可选）
            company: 公司代码
            
        Returns:
            List[PurchaseRecord]: 采购记录列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 根据是否有品牌决定SQL
                if brand and brand.strip():
                    sql = """
                        SELECT number, brand, fullname, unit_cost, create_date, `year_month`
                        FROM crmapp_procurement_history_detail
                        WHERE number = %s AND brand = %s AND company = %s
                        ORDER BY create_date DESC
                    """
                    cursor.execute(sql, (oe, brand, company))
                else:
                    sql = """
                        SELECT number, brand, fullname, unit_cost, create_date, `year_month`
                        FROM crmapp_procurement_history_detail
                        WHERE number = %s AND company = %s
                        ORDER BY create_date DESC
                    """
                    cursor.execute(sql, (oe, company))
                rows = cursor.fetchall()
                
                records = []
                for row in rows:
                    if row['year_month']:
                        # 解析 year_month 格式: 2025-01
                        year_month_parts = str(row['year_month']).split('-')
                        year = int(year_month_parts[0])
                        month = int(year_month_parts[1])
                    else:
                        # 从 create_date 解析
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
    def query_product_info(oe: str, brand: str, company: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        查询产品信息（名称、规格、替换号）
        从 crmapp_compare_summary 表查询
        
        Args:
            oe: OE号
            brand: 品牌（可选）
            company: 公司代码
            
        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: (名称, 规格, 替换号)
            查不到返回 (None, None, None)
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 根据是否有品牌决定SQL
                if brand and brand.strip():
                    sql = """
                        SELECT product_name, l_model_zh, replace_number
                        FROM crmapp_compare_summary
                        WHERE oe = %s AND brand = %s AND company = %s
                        LIMIT 1
                    """
                    cursor.execute(sql, (oe, brand, company))
                else:
                    sql = """
                        SELECT product_name, l_model_zh, replace_number
                        FROM crmapp_compare_summary
                        WHERE oe = %s AND company = %s
                        LIMIT 1
                    """
                    cursor.execute(sql, (oe, company))
                
                row = cursor.fetchone()
                
                if row:
                    return (
                        row['product_name'] if row['product_name'] else None,
                        row['l_model_zh'] if row['l_model_zh'] else None,
                        row['replace_number'] if row['replace_number'] else None
                    )
                else:
                    return (None, None, None)
        finally:
            conn.close()
    
    @staticmethod
    def query_beihuo_data(oe: str, brand: str, company: str) -> Dict:
        """
        从crmapp_beihuo表查询备货数据
        
        Args:
            oe: OE号
            brand: 品牌（可选）
            company: 公司代码
            
        Returns:
            Dict: 备货数据字典
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 根据是否有品牌决定SQL
                if brand and brand.strip():
                    sql = """
                        SELECT 
                            `库存数量`, `标签`, `近1个月询价量`, `近3个月月均询价量`,
                            `近6个月月均销量`, `全国近1个月询价量`, `全国近3个月月均询价量`,
                            `今日销量`, `昨日销量`, `近7天销量`, `本月销量`,
                            `近6个月销量`, `近12个月销量`
                        FROM crmapp_beihuo
                        WHERE oe = %s AND `品牌` = %s AND company = %s
                        LIMIT 1
                    """
                    cursor.execute(sql, (oe, brand, company))
                else:
                    sql = """
                        SELECT 
                            `库存数量`, `标签`, `近1个月询价量`, `近3个月月均询价量`,
                            `近6个月月均销量`, `全国近1个月询价量`, `全国近3个月月均询价量`,
                            `今日销量`, `昨日销量`, `近7天销量`, `本月销量`,
                            `近6个月销量`, `近12个月销量`
                        FROM crmapp_beihuo
                        WHERE oe = %s AND company = %s
                        LIMIT 1
                    """
                    cursor.execute(sql, (oe, company))
                
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
        finally:
            conn.close()
    
    @staticmethod
    def _generate_compare_result_with_default_brands(oe: str, company: str) -> OECompareResult:
        """
        当品牌为空时，使用"原厂"和"原厂国内4s件"两个品牌搜索
        优先使用有采购历史的品牌，如果都有则选最低价更低的
        如果没有采购历史，优先使用"原厂"，原厂没有再用"原厂国内4s件"
        
        Args:
            oe: OE号
            company: 公司代码
            
        Returns:
            OECompareResult: 比对结果
        """
        DEFAULT_BRANDS = ["原厂", "原厂国内4s件"]
        
        # 分别查询两个品牌的数据
        brand_results = []
        for default_brand in DEFAULT_BRANDS:
            records = ProcurementCompareService.query_by_oe_brand(oe, default_brand, company)
            # 计算该品牌的最低价（无论是否有记录）
            if records:
                all_records_sorted = sorted(records, key=lambda x: x.price)
                lowest_price = all_records_sorted[0].price
            else:
                lowest_price = float('inf')
            brand_results.append({
                'brand': default_brand,
                'records': records,
                'lowest_price': lowest_price,
                'has_records': bool(records)
            })
        
        # 查询4S价格
        price_4s_cost, price_4s_sale = ProcurementCompareService.query_4s_price(oe)
        
        # 选择品牌逻辑：
        # 1. 优先选择有采购历史的品牌
        # 2. 如果都有采购历史，选最低价更低的
        # 3. 如果都没有采购历史，优先选"原厂"
        brands_with_records = [b for b in brand_results if b['has_records']]
        
        if brands_with_records:
            # 有采购历史的品牌，选最低价更低的
            best_result = min(brands_with_records, key=lambda x: x['lowest_price'])
        else:
            # 都没有采购历史，优先使用"原厂"
            best_result = brand_results[0]  # 第一个是"原厂"
        
        selected_brand = best_result['brand']
        records = best_result['records']
        
        # 查询选中品牌的产品信息和备货数据
        product_name, spec, replace_name = ProcurementCompareService.query_product_info(oe, selected_brand, company)
        beihuo_data = ProcurementCompareService.query_beihuo_data(oe, selected_brand, company)
        
        # 如果没有采购历史数据
        if not records:
            return OECompareResult(
                oe=oe,
                brand=selected_brand,
                month_summaries={},
                overall_lowest=("", "", 0.0),
                overall_highest=("", "", 0.0),
                price_4s_cost=price_4s_cost,
                price_4s_sale=price_4s_sale,
                product_name=product_name,
                spec=spec,
                replace_name=replace_name,
                stock_quantity=beihuo_data['stock_quantity'],
                tag=beihuo_data['tag'],
                inquiry_1m=beihuo_data['inquiry_1m'],
                inquiry_3m_avg=beihuo_data['inquiry_3m_avg'],
                sales_6m_avg=beihuo_data['sales_6m_avg'],
                inquiry_1m_national=beihuo_data['inquiry_1m_national'],
                inquiry_3m_avg_national=beihuo_data['inquiry_3m_avg_national'],
                sales_today=beihuo_data['sales_today'],
                sales_yesterday=beihuo_data['sales_yesterday'],
                sales_7d=beihuo_data['sales_7d'],
                sales_month=beihuo_data['sales_month'],
                sales_6m=beihuo_data['sales_6m'],
                sales_12m=beihuo_data['sales_12m']
            )
        
        # 按月份聚合
        month_summaries = ProcurementCompareService.aggregate_by_month(records)
        
        # 过滤价格为0的记录，计算整体最低价和最高价
        valid_records = ProcurementCompareService._filter_valid_records(records)
        if valid_records:
            all_records_sorted = sorted(valid_records, key=lambda x: x.price)
            lowest = all_records_sorted[0]
            # 如果只有一个有效记录，最高和最低相同
            highest = all_records_sorted[-1] if len(all_records_sorted) > 1 else lowest
            
            overall_lowest = (f"{lowest.year}-{lowest.month:02d}", lowest.supplier, lowest.price)
            overall_highest = (f"{highest.year}-{highest.month:02d}", highest.supplier, highest.price)
        else:
            # 没有有效记录（价格都<=0）
            overall_lowest = ("", "", 0.0)
            overall_highest = ("", "", 0.0)
        
        return OECompareResult(
            oe=oe,
            brand=selected_brand,
            month_summaries=month_summaries,
            overall_lowest=overall_lowest,
            overall_highest=overall_highest,
            price_4s_cost=price_4s_cost,
            price_4s_sale=price_4s_sale,
            product_name=product_name,
            spec=spec,
            replace_name=replace_name,
            stock_quantity=beihuo_data['stock_quantity'],
            tag=beihuo_data['tag'],
            inquiry_1m=beihuo_data['inquiry_1m'],
            inquiry_3m_avg=beihuo_data['inquiry_3m_avg'],
            sales_6m_avg=beihuo_data['sales_6m_avg'],
            inquiry_1m_national=beihuo_data['inquiry_1m_national'],
            inquiry_3m_avg_national=beihuo_data['inquiry_3m_avg_national'],
            sales_today=beihuo_data['sales_today'],
            sales_yesterday=beihuo_data['sales_yesterday'],
            sales_7d=beihuo_data['sales_7d'],
            sales_month=beihuo_data['sales_month'],
            sales_6m=beihuo_data['sales_6m'],
            sales_12m=beihuo_data['sales_12m']
        )
    
    @staticmethod
    def generate_compare_result(oe: str, brand: str, company: str) -> OECompareResult:
        """
        生成单个OE的比对结果
        
        Args:
            oe: OE号
            brand: 品牌
            company: 公司代码
            
        Returns:
            OECompareResult: 比对结果
        """
        # 如果品牌为空，使用"原厂"和"原厂国内4s件"两个品牌搜索
        if not brand or not brand.strip():
            return ProcurementCompareService._generate_compare_result_with_default_brands(oe, company)
        
        # 查询采购历史
        records = ProcurementCompareService.query_by_oe_brand(oe, brand, company)
        
        # 查询4S价格
        price_4s_cost, price_4s_sale = ProcurementCompareService.query_4s_price(oe)
        
        # 查询产品信息（添加company过滤）
        product_name, spec, replace_name = ProcurementCompareService.query_product_info(oe, brand, company)
        
        # 查询备货数据（新增）
        beihuo_data = ProcurementCompareService.query_beihuo_data(oe, brand, company)
        
        if not records:
            # 无采购历史数据，但可能有其他信息
            return OECompareResult(
                oe=oe,
                brand=brand,
                month_summaries={},
                overall_lowest=("", "", 0.0),
                overall_highest=("", "", 0.0),
                price_4s_cost=price_4s_cost,
                price_4s_sale=price_4s_sale,
                product_name=product_name,
                spec=spec,
                replace_name=replace_name,
                stock_quantity=beihuo_data['stock_quantity'],
                tag=beihuo_data['tag'],
                inquiry_1m=beihuo_data['inquiry_1m'],
                inquiry_3m_avg=beihuo_data['inquiry_3m_avg'],
                sales_6m_avg=beihuo_data['sales_6m_avg'],
                inquiry_1m_national=beihuo_data['inquiry_1m_national'],
                inquiry_3m_avg_national=beihuo_data['inquiry_3m_avg_national'],
                sales_today=beihuo_data['sales_today'],
                sales_yesterday=beihuo_data['sales_yesterday'],
                sales_7d=beihuo_data['sales_7d'],
                sales_month=beihuo_data['sales_month'],
                sales_6m=beihuo_data['sales_6m'],
                sales_12m=beihuo_data['sales_12m']
            )
        
        # 按月份聚合
        month_summaries = ProcurementCompareService.aggregate_by_month(records)
        
        # 过滤价格为0的记录，计算整体最低价和最高价
        valid_records = ProcurementCompareService._filter_valid_records(records)
        if valid_records:
            all_records_sorted = sorted(valid_records, key=lambda x: x.price)
            lowest = all_records_sorted[0]
            # 如果只有一个有效记录，最高和最低相同
            highest = all_records_sorted[-1] if len(all_records_sorted) > 1 else lowest
            
            overall_lowest = (f"{lowest.year}-{lowest.month:02d}", lowest.supplier, lowest.price)
            overall_highest = (f"{highest.year}-{highest.month:02d}", highest.supplier, highest.price)
        else:
            # 没有有效记录（价格都<=0）
            overall_lowest = ("", "", 0.0)
            overall_highest = ("", "", 0.0)
        
        return OECompareResult(
            oe=oe,
            brand=brand,
            month_summaries=month_summaries,
            overall_lowest=overall_lowest,
            overall_highest=overall_highest,
            price_4s_cost=price_4s_cost,
            price_4s_sale=price_4s_sale,
            product_name=product_name,
            spec=spec,
            replace_name=replace_name,
            stock_quantity=beihuo_data['stock_quantity'],
            tag=beihuo_data['tag'],
            inquiry_1m=beihuo_data['inquiry_1m'],
            inquiry_3m_avg=beihuo_data['inquiry_3m_avg'],
            sales_6m_avg=beihuo_data['sales_6m_avg'],
            inquiry_1m_national=beihuo_data['inquiry_1m_national'],
            inquiry_3m_avg_national=beihuo_data['inquiry_3m_avg_national'],
            sales_today=beihuo_data['sales_today'],
            sales_yesterday=beihuo_data['sales_yesterday'],
            sales_7d=beihuo_data['sales_7d'],
            sales_month=beihuo_data['sales_month'],
            sales_6m=beihuo_data['sales_6m'],
            sales_12m=beihuo_data['sales_12m']
        )
    
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
        results = []
        for item in items:
            oe = item.get('oe', '')
            brand = item.get('brand', '')
            price_str = item.get('price', '')
            if oe:
                result = ProcurementCompareService.generate_compare_result(oe, brand, company)
                # 设置价格（从导入文件读取）
                if price_str:
                    try:
                        result.price = float(price_str)
                    except (ValueError, TypeError):
                        result.price = None
                results.append(result)
        return results
