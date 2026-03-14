# -*- coding: utf-8 -*-
"""
黑名单管理模块
负责黑名单的增删改查操作
"""

import pymysql
from app.utils.database_connection import get_db_connection
from typing import List, Dict, Optional, Tuple


def init_blacklist_table():
    """
    初始化黑名单表
    在应用启动时调用
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS inventory_blacklist (
            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
            supplier_name VARCHAR(100) NOT NULL COMMENT '供应商名称',
            oe_code VARCHAR(100) NOT NULL COMMENT 'OE码',
            brand VARCHAR(100) NOT NULL COMMENT '品牌',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            UNIQUE KEY unique_blacklist (supplier_name, oe_code, brand) COMMENT '唯一索引,防止重复'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='虚拟库存黑名单表';
        """
        cursor.execute(create_table_sql)
        conn.commit()
        print("[黑名单] 黑名单表初始化完成")
    except Exception as e:
        print(f"[黑名单] 初始化黑名单表失败: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def add_to_blacklist(supplier_name: str, oe_code: str, brand: str) -> Dict:
    """
    添加单条记录到黑名单
    
    Args:
        supplier_name: 供应商名称
        oe_code: OE码
        brand: 品牌
        
    Returns:
        {'success': True/False, 'msg': '提示信息'}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            INSERT INTO inventory_blacklist (supplier_name, oe_code, brand)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE supplier_name = supplier_name
        """
        cursor.execute(sql, (supplier_name, oe_code, brand))
        conn.commit()
        
        if cursor.rowcount > 0:
            return {'success': True, 'msg': '添加成功'}
        else:
            return {'success': False, 'msg': '该记录已存在于黑名单中'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'msg': f'添加失败: {str(e)}'}
    finally:
        cursor.close()
        conn.close()


def remove_from_blacklist(supplier_name: str, oe_code: str, brand: str) -> Dict:
    """
    从黑名单删除单条记录
    
    Args:
        supplier_name: 供应商名称
        oe_code: OE码
        brand: 品牌
        
    Returns:
        {'success': True/False, 'msg': '提示信息'}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            DELETE FROM inventory_blacklist 
            WHERE supplier_name = %s AND oe_code = %s AND brand = %s
        """
        cursor.execute(sql, (supplier_name, oe_code, brand))
        conn.commit()
        
        if cursor.rowcount > 0:
            return {'success': True, 'msg': '删除成功'}
        else:
            return {'success': False, 'msg': '该记录不存在于黑名单中'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'msg': f'删除失败: {str(e)}'}
    finally:
        cursor.close()
        conn.close()


def get_blacklist() -> List[Dict]:
    """
    获取所有黑名单记录
    
    Returns:
        黑名单记录列表,按创建时间倒序排列
    """
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        sql = """
            SELECT id, supplier_name, oe_code, brand, created_at 
            FROM inventory_blacklist 
            ORDER BY created_at DESC
        """
        cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print(f"[黑名单] 获取黑名单失败: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def batch_add_to_blacklist(records: List[Tuple[str, str, str]]) -> Dict:
    """
    批量添加黑名单记录
    
    Args:
        records: 记录列表,每个元素是 (supplier_name, oe_code, brand) 元组
        
    Returns:
        {'success': True/False, 'added': 成功添加数量, 'duplicate': 重复数量, 'msg': '提示信息'}
    """
    if not records:
        return {'success': True, 'added': 0, 'duplicate': 0, 'msg': '没有需要添加的记录'}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            INSERT INTO inventory_blacklist (supplier_name, oe_code, brand)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE supplier_name = supplier_name
        """
        cursor.executemany(sql, records)
        conn.commit()
        
        # 计算实际添加的数量(排除重复的)
        # cursor.rowcount 在 ON DUPLICATE KEY 时行为特殊,需要重新查询
        cursor.execute("SELECT COUNT(*) FROM inventory_blacklist")
        total_count = cursor.fetchone()[0]
        
        return {
            'success': True, 
            'added': cursor.rowcount,
            'total': total_count,
            'msg': f'成功添加 {cursor.rowcount} 条记录'
        }
    except Exception as e:
        conn.rollback()
        return {'success': False, 'added': 0, 'duplicate': 0, 'msg': f'批量添加失败: {str(e)}'}
    finally:
        cursor.close()
        conn.close()


def clear_blacklist() -> Dict:
    """
    清空所有黑名单记录
    
    Returns:
        {'success': True/False, 'msg': '提示信息'}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM inventory_blacklist")
        deleted_count = cursor.rowcount
        conn.commit()
        return {'success': True, 'msg': f'已清空 {deleted_count} 条黑名单记录'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'msg': f'清空失败: {str(e)}'}
    finally:
        cursor.close()
        conn.close()


def is_in_blacklist(supplier_name: str, oe_code: str, brand: str) -> bool:
    """
    检查指定记录是否在黑名单中
    
    Args:
        supplier_name: 供应商名称
        oe_code: OE码
        brand: 品牌
        
    Returns:
        True/False
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT 1 FROM inventory_blacklist 
            WHERE supplier_name = %s AND oe_code = %s AND brand = %s
            LIMIT 1
        """
        cursor.execute(sql, (supplier_name, oe_code, brand))
        return cursor.fetchone() is not None
    except Exception as e:
        print(f"[黑名单] 检查黑名单失败: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_blacklist_count() -> int:
    """
    获取黑名单记录总数
    
    Returns:
        黑名单记录数量
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM inventory_blacklist")
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"[黑名单] 获取黑名单数量失败: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()
