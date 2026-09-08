"""
采购记录服务模块
用于解析 purchasing_record 字符串

核心功能:
    1. 解析 purchasing_record 字符串
    2. 添加询价记录到 crmapp_procurement_history 表
    3. 查询采购记录

数据格式示例:
    [
        {"supplier_name": "上海福宝盟汽配", "purchase_price": 112.00, "purchase_quantity": 5, "purchase_date": "2026-01-12"},
        {"supplier_name": "上海佳配电子商务有限公司", "purchase_price": 115.00, "purchase_quantity": 2, "purchase_date": "2025-12-20"}
    ]

使用示例:
    from procurement_record_service import add_inquiry_record
    
    # 添加询价导入的采购记录
    add_inquiry_record('11427585403', '原厂', '上海福宝盟汽配', 112.00, 'fsbbr')
"""

import re
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.utils.database_connection import get_db_connection


# 表名
TABLE_NAME = 'crmapp_compare_summary'


def parse_purchasing_record(purchasing_record: str) -> List[Dict]:
    """
    解析 purchasing_record 字符串，拆分为多条记录
    
    Args:
        purchasing_record: 原始采购记录字符串
        
    Returns:
        解析后的记录列表，每条记录包含：
        {
            'supplier_name': '上海福宝盟汽配',   # 供应商名称
            'purchase_price': 112.00,            # 采购单价
            'purchase_quantity': 5,              # 采购数量
            'purchase_date': '2026-01-12'        # 采购日期
        }
    
    示例:
        >>> record = "2026-01-12佛山采购专用,供应商:上海福宝盟汽配,采购:5,单价:112.00"
        >>> parse_purchasing_record(record)
        [{
            'supplier_name': '上海福宝盟汽配',
            'purchase_price': 112.00,
            'purchase_quantity': 5,
            'purchase_date': '2026-01-12'
        }]
    """
    if not purchasing_record:
        return []
    
    records = []
    
    # 按 <br/> 或 <br> 或换行分割多条记录
    raw_records = re.split(r'<br\s*/?>|\n', purchasing_record)
    
    for raw_record in raw_records:
        raw_record = raw_record.strip()
        if not raw_record:
            continue
        
        # 解析单条记录
        parsed = parse_single_record(raw_record)
        if parsed:
            records.append(parsed)
    
    return records


def parse_single_record(record: str) -> Optional[Dict]:
    """
    解析单条采购记录
    
    格式: "2026-01-12佛山采购专用,供应商:上海福宝盟汽配,采购:5,单价:112.00"
    
    Args:
        record: 单条记录字符串
        
    Returns:
        解析后的字典（包含供应商、价格、数量、日期），解析失败返回 None
    """
    try:
        # 提取日期（前10位）
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', record)
        if not date_match:
            return None
        
        purchase_date = date_match.group(1)
        
        # 提取供应商名称
        supplier_match = re.search(r'供应商:([^,]+)', record)
        if not supplier_match:
            return None
        supplier_name = supplier_match.group(1).strip()
        
        # 提取采购单价
        price_match = re.search(r'单价:([\d.]+)', record)
        purchase_price = float(price_match.group(1)) if price_match else 0.0
        
        # 提取采购数量
        quantity_match = re.search(r'采购:([\d.]+)', record)
        purchase_quantity = int(float(quantity_match.group(1))) if quantity_match else 0
        
        return {
            'supplier_name': supplier_name,
            'purchase_price': purchase_price,
            'purchase_quantity': purchase_quantity,
            'purchase_date': purchase_date
        }
        
    except Exception as e:
        print(f"解析采购记录失败: {record}, 错误: {e}")
        return None


def get_existing_records(oe: str, brand: str, company: str) -> List[Dict]:
    """
    获取现有的采购记录
    从 crmapp_procurement_history 表查询
    
    Args:
        oe: OE 号
        brand: 品牌
        company: 公司/组织
        
    Returns:
        现有的记录列表，不存在返回空列表
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT supplier_name, unit_price, purchase_date
                FROM crmapp_procurement_history
                WHERE oe = %s AND brand = %s AND company = %s
                ORDER BY purchase_date DESC
            """
            cursor.execute(sql, (oe, brand, company))
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                records.append({
                    'supplier_name': row[0],
                    'purchase_price': float(row[1]) if row[1] else 0.0,
                    'purchase_date': row[2].strftime('%Y-%m-%d') if hasattr(row[2], 'strftime') else str(row[2])
                })
            return records
    except Exception as e:
        print(f"获取现有记录失败: {e}")
        return []
    finally:
        conn.close()


def merge_records(existing_records: List[Dict], new_records: List[Dict]) -> List[Dict]:
    """
    合并现有记录和新记录
    
    同一供应商只保留最新价格（按日期比较）
    
    Args:
        existing_records: 现有记录列表
        new_records: 新记录列表
        
    Returns:
        合并后的记录列表
    """
    # 使用字典去重，key 为供应商名称
    records_map = {}
    
    # 先加入现有记录
    for record in existing_records:
        supplier = record.get('supplier_name', '')
        if supplier:
            records_map[supplier] = record
    
    # 处理新记录
    for new_record in new_records:
        supplier = new_record.get('supplier_name', '')
        if not supplier:
            continue
        
        if supplier in records_map:
            # 已存在，比较日期
            existing = records_map[supplier]
            existing_date = existing.get('purchase_date', '')
            new_date = new_record.get('purchase_date', '')
            
            # 新记录日期 >= 现有记录日期，替换
            if new_date and existing_date and new_date >= existing_date:
                records_map[supplier] = new_record
                print(f"  更新供应商: {supplier}, 日期={new_date}, 价格={new_record.get('purchase_price')}")
            else:
                print(f"  跳过供应商(日期较旧): {supplier}")
        else:
            # 不存在，添加
            records_map[supplier] = new_record
            print(f"  添加供应商: {supplier}, 日期={new_record.get('purchase_date')}, 价格={new_record.get('purchase_price')}")
    
    # 转回列表，按日期降序排序
    result = list(records_map.values())
    result.sort(key=lambda x: x.get('purchase_date', ''), reverse=True)
    
    return result


def calculate_max_min_price(records: List[Dict]) -> tuple:
    """
    计算最高价和最低价
    
    Args:
        records: 采购记录列表
        
    Returns:
        (最高价, 最低价)
    """
    if not records:
        return 0.0, 0.0
    
    prices = [r.get('purchase_price', 0) for r in records if r.get('purchase_price', 0) > 0]
    
    if not prices:
        return 0.0, 0.0
    
    return max(prices), min(prices)


def get_latest_price(records: List[Dict]) -> float:
    """
    获取最新日期的价格
    
    Args:
        records: 采购记录列表（已按日期降序排序）
        
    Returns:
        最新价格，没有则返回 0.0
    """
    if not records:
        return 0.0
    
    # 记录已按日期降序排序，取第一条
    latest_record = records[0]
    return latest_record.get('purchase_price', 0.0)


def add_inquiry_record(oe: str, brand: str, supplier: str, price: float, 
                       company: str) -> bool:
    """
    添加询价导入的记录到采购历史表
    
    将询价导入时自带的供应商和单价作为一条记录存入 crmapp_procurement_history 表
    日期使用当天日期
    
    Args:
        oe: OE 号
        brand: 品牌
        supplier: 供应商名称
        price: 单价
        company: 公司/组织
        
    Returns:
        True 表示成功
    """
    if not oe or not supplier:
        print("添加询价记录失败: OE 或供应商不能为空")
        return False
    
    from app.utils.database_connection import get_db_connection
    
    today = datetime.now()
    purchase_date = today.strftime('%Y-%m-%d')
    year_month = today.strftime('%Y-%m')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 插入到采购历史表，使用 ON DUPLICATE KEY UPDATE 去重
            sql = """
                INSERT INTO crmapp_procurement_history
                (`year_month`, `purchase_date`, `supplier_name`, `oe`, `brand`, `unit_price`, `company`)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `purchase_date` = VALUES(`purchase_date`)
            """
            cursor.execute(sql, (
                year_month,
                purchase_date,
                supplier,
                oe,
                brand or '',
                float(price) if price else 0.0,
                company
            ))
            conn.commit()
            
            print(f"添加询价记录成功: OE={oe}, 供应商={supplier}, 价格={price}")
            return True
            
    except Exception as e:
        conn.rollback()
        print(f"添加询价记录失败: OE={oe}, 错误={e}")
        return False
    finally:
        conn.close()


def get_procurement_records(oe: str, brand: str = '', company: str = '') -> List[Dict]:
    """
    查询采购记录
    
    Args:
        oe: OE 号
        brand: 品牌（可选）
        company: 公司（可选）
        
    Returns:
        记录列表（按日期降序）
    """
    records = get_existing_records(oe, brand, company)
    
    # 按日期降序排序
    records.sort(key=lambda x: x.get('purchase_date', ''), reverse=True)
    
    return records


def clear_procurement_records(oe: str, brand: str, company: str) -> bool:
    """
    清空采购记录
    从 crmapp_procurement_history 表删除记录
    
    Args:
        oe: OE 号
        brand: 品牌
        company: 公司
        
    Returns:
        True 表示成功
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                DELETE FROM crmapp_procurement_history
                WHERE oe = %s AND brand = %s AND company = %s
            """
            cursor.execute(sql, (oe, brand, company))
            conn.commit()
            print(f"清空采购记录成功: OE={oe}, 品牌={brand}")
            return True
    except Exception as e:
        conn.rollback()
        print(f"清空采购记录失败: {e}")
        return False
    finally:
        conn.close()


# 便捷函数
# 不再需要的函数（保留别名兼容）
init_table = lambda: True  # JSON 方案不需要单独建表
