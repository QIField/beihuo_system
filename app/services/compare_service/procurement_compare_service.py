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
    def aggregate_by_month(records: List[PurchaseRecord]) -> Dict[int, MonthSummary]:
        """
        按月份聚合数据
        
        Args:
            records: 采购记录列表
            
        Returns:
            Dict[int, MonthSummary]: 月份汇总数据，key为月份(1-12)
        """
        # 按月份分组
        month_groups: Dict[int, List[PurchaseRecord]] = {i: [] for i in range(1, 13)}
        
        for record in records:
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
    def query_product_info(oe: str, brand: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        查询产品信息（名称、规格、替换号）
        从 crmapp_compare_summary 表查询
        
        Args:
            oe: OE号
            brand: 品牌（可选）
            
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
                        WHERE oe = %s AND brand = %s
                        LIMIT 1
                    """
                    cursor.execute(sql, (oe, brand))
                else:
                    sql = """
                        SELECT product_name, l_model_zh, replace_number
                        FROM crmapp_compare_summary
                        WHERE oe = %s
                        LIMIT 1
                    """
                    cursor.execute(sql, (oe,))
                
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
        # 查询采购历史
        records = ProcurementCompareService.query_by_oe_brand(oe, brand, company)
        
        # 查询4S价格
        price_4s_cost, price_4s_sale = ProcurementCompareService.query_4s_price(oe)
        
        # 查询产品信息
        product_name, spec, replace_name = ProcurementCompareService.query_product_info(oe, brand)
        
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
                replace_name=replace_name
            )
        
        # 按月份聚合
        month_summaries = ProcurementCompareService.aggregate_by_month(records)
        
        # 计算整体最低价和最高价
        all_records_sorted = sorted(records, key=lambda x: x.price)
        lowest = all_records_sorted[0]
        highest = all_records_sorted[-1]
        
        overall_lowest = (f"{lowest.year}-{lowest.month:02d}", lowest.supplier, lowest.price)
        overall_highest = (f"{highest.year}-{highest.month:02d}", highest.supplier, highest.price)
        
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
            replace_name=replace_name
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
