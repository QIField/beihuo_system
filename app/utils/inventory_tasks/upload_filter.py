# -*- coding: utf-8 -*-
"""
上传过滤模块
使用内存哈希表实现高效的黑名单过滤
"""

import time
from typing import List, Dict, Set, Tuple
from app.utils.database_connection import get_db_connection


class BlacklistFilter:
    """
    黑名单过滤器
    使用内存哈希表实现O(1)时间复杂度的黑名单查询
    """
    
    def __init__(self):
        # 使用set存储黑名单组合键,实现O(1)查询
        # key格式: (supplier_name, oe_code, brand)
        self._blacklist_set: Set[Tuple[str, str, str]] = set()
        self._last_load_time: float = 0
        self._cache_duration: int = 300  # 缓存5分钟(300秒)
        
    def load_from_db(self, force: bool = False) -> int:
        """
        从数据库加载黑名单到内存
        
        Args:
            force: 是否强制刷新缓存
            
        Returns:
            加载的黑名单数量
        """
        current_time = time.time()
        
        # 检查缓存是否过期
        if not force and self._blacklist_set and (current_time - self._last_load_time) < self._cache_duration:
            return len(self._blacklist_set)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 清空旧数据
            self._blacklist_set.clear()
            
            # 从数据库加载
            cursor.execute("SELECT supplier_name, oe_code, brand FROM inventory_blacklist")
            rows = cursor.fetchall()
            
            # 构建哈希集合
            for row in rows:
                # 使用元组作为key,支持组合匹配
                key = (row[0], row[1], row[2])
                self._blacklist_set.add(key)
            
            self._last_load_time = current_time
            
            print(f"[黑名单过滤] 已加载 {len(self._blacklist_set)} 条黑名单到内存")
            return len(self._blacklist_set)
            
        except Exception as e:
            print(f"[黑名单过滤] 加载黑名单失败: {e}")
            return 0
        finally:
            cursor.close()
            conn.close()
    
    def is_blacklisted(self, supplier_name: str, oe_code: str, brand: str) -> bool:
        """
        检查指定记录是否在黑名单中
        
        Args:
            supplier_name: 供应商名称
            oe_code: OE码
            brand: 品牌
            
        Returns:
            True表示在黑名单中,False表示不在
        """
        # 确保数据已加载
        if not self._blacklist_set:
            self.load_from_db()
        
        # O(1)时间复杂度的哈希查询
        key = (supplier_name, oe_code, brand)
        return key in self._blacklist_set
    
    def filter_data(self, data_list: List[Dict]) -> Dict:
        """
        过滤数据,剔除黑名单中的记录
        
        Args:
            data_list: 待过滤的数据列表,每个元素是字典,包含 supplier_name, oe_code, brand 字段
            
        Returns:
            {
                'filtered_data': 过滤后的数据列表,
                'removed_count': 剔除的黑名单数量,
                'total_count': 原始数据总数,
                'removed_items': 被剔除的记录列表(用于日志)
            }
        """
        start_time = time.time()
        
        # 确保黑名单已加载
        if not self._blacklist_set:
            self.load_from_db()
        
        filtered_data = []
        removed_items = []
        
        for item in data_list:
            # 获取三个关键字段
            supplier_name = item.get('supplier_name', '')
            oe_code = item.get('oe_code', '')
            brand = item.get('brand', '')
            
            # 构建组合键进行查询
            key = (supplier_name, oe_code, brand)
            
            if key in self._blacklist_set:
                # 在黑名单中,记录并跳过
                removed_items.append({
                    'supplier_name': supplier_name,
                    'oe_code': oe_code,
                    'brand': brand
                })
            else:
                # 不在黑名单中,保留
                filtered_data.append(item)
        
        elapsed_time = (time.time() - start_time) * 1000  # 转换为毫秒
        
        result = {
            'filtered_data': filtered_data,
            'removed_count': len(removed_items),
            'total_count': len(data_list),
            'removed_items': removed_items[:10],  # 只保留前10条用于日志展示
            'elapsed_ms': elapsed_time
        }
        
        print(f"[黑名单过滤] 过滤完成: 原始 {result['total_count']} 条, 剔除 {result['removed_count']} 条, 剩余 {len(filtered_data)} 条, 耗时 {elapsed_time:.2f}ms")
        
        return result
    
    def get_stats(self) -> Dict:
        """
        获取过滤器统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'blacklist_count': len(self._blacklist_set),
            'last_load_time': self._last_load_time,
            'cache_duration': self._cache_duration
        }
    
    def clear_cache(self):
        """清空内存缓存"""
        self._blacklist_set.clear()
        self._last_load_time = 0
        print("[黑名单过滤] 内存缓存已清空")


# 全局过滤器实例(单例模式)
_blacklist_filter = BlacklistFilter()


def load_blacklist_to_memory(force: bool = False) -> int:
    """
    加载黑名单到内存
    
    Args:
        force: 是否强制刷新
        
    Returns:
        加载的黑名单数量
    """
    return _blacklist_filter.load_from_db(force)


def filter_by_blacklist(data_list: List[Dict]) -> List[Dict]:
    """
    过滤数据,剔除黑名单中的记录
    
    Args:
        data_list: 待过滤的数据列表
        
    Returns:
        过滤后的数据列表
    """
    result = _blacklist_filter.filter_data(data_list)
    return result['filtered_data']


def get_filter_stats() -> Dict:
    """
    获取过滤器统计信息
    
    Returns:
        统计信息字典
    """
    return _blacklist_filter.get_stats()


def is_in_blacklist_memory(supplier_name: str, oe_code: str, brand: str) -> bool:
    """
    检查指定记录是否在黑名单中(内存查询)
    
    Args:
        supplier_name: 供应商名称
        oe_code: OE码
        brand: 品牌
        
    Returns:
        True/False
    """
    return _blacklist_filter.is_blacklisted(supplier_name, oe_code, brand)


def refresh_blacklist_cache():
    """刷新黑名单缓存"""
    _blacklist_filter.clear_cache()
    return _blacklist_filter.load_from_db(force=True)
