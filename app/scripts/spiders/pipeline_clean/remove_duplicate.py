# -*- coding:utf-8 -*-
# @Time    : 2026/4/11 14:46
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : remove_duplicate.py
# @Software: PyCharm

from typing import List, Dict, Any, Callable, Optional
import hashlib


class GlobalFingerprintPool:
    """
    全局指纹去重池
    基于内存的指纹去重，不查询数据库
    """

    _instance = None
    _pools = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_pool(cls, pool_name: str) -> 'GlobalFingerprintPool':
        """
        获取指定名称的去重池

        Args:
            pool_name: 去重池名称，不同爬虫使用不同的池

        Returns:
            GlobalFingerprintPool 实例
        """
        if pool_name not in cls._pools:
            cls._pools[pool_name] = set()
        return cls._instance

    def __init__(self):
        self.pool_name = None
        self.fingerprint_set = None

    def init_pool(self, pool_name: str):
        """
        初始化去重池

        Args:
            pool_name: 去重池名称
        """
        self.pool_name = pool_name
        if pool_name not in self._pools:
            self._pools[pool_name] = set()
        self.fingerprint_set = self._pools[pool_name]

    def _generate_fingerprint(self, data: Dict[str, Any], unique_key_fields: List[str]) -> str:
        """
        生成数据指纹

        Args:
            data: 数据字典
            unique_key_fields: 唯一键字段列表

        Returns:
            指纹字符串（MD5哈希）
        """
        key_values = []
        for field in unique_key_fields:
            value = data.get(field, '')
            key_values.append(f"{field}:{value}")
        key_str = '|'.join(key_values)
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    def is_duplicate(self, data: Dict[str, Any], unique_key_fields: List[str]) -> bool:
        """
        检查数据是否重复

        Args:
            data: 数据字典
            unique_key_fields: 唯一键字段列表

        Returns:
            True表示重复，False表示不重复
        """
        if self.fingerprint_set is None:
            raise RuntimeError("请先调用 init_pool() 初始化去重池")

        fingerprint = self._generate_fingerprint(data, unique_key_fields)
        return fingerprint in self.fingerprint_set

    def add_fingerprint(self, data: Dict[str, Any], unique_key_fields: List[str]):
        """
        添加数据指纹到去重池

        Args:
            data: 数据字典
            unique_key_fields: 唯一键字段列表
        """
        if self.fingerprint_set is None:
            raise RuntimeError("请先调用 init_pool() 初始化去重池")

        fingerprint = self._generate_fingerprint(data, unique_key_fields)
        self.fingerprint_set.add(fingerprint)

    def deduplicate_list(self, data_list: List[Dict[str, Any]], unique_key_fields: List[str]) -> List[Dict[str, Any]]:
        """
        对数据列表进行去重

        Args:
            data_list: 数据列表
            unique_key_fields: 唯一键字段列表

        Returns:
            去重后的数据列表
        """
        if self.fingerprint_set is None:
            raise RuntimeError("请先调用 init_pool() 初始化去重池")

        deduplicated = []
        for data in data_list:
            if not self.is_duplicate(data, unique_key_fields):
                deduplicated.append(data)
                self.add_fingerprint(data, unique_key_fields)
        return deduplicated

    def clear_pool(self):
        """
        清空去重池
        """
        if self.pool_name and self.pool_name in self._pools:
            self._pools[self.pool_name].clear()
        self.fingerprint_set = None

    @classmethod
    def clear_all_pools(cls):
        """
        清空所有去重池
        """
        cls._pools.clear()


class DeduplicationPipeline:
    """
    通用去重管道类
    封装 GlobalFingerprintPool，提供更便捷的接口
    """

    def __init__(self, pool_name: str, unique_key_fields: List[str]):
        """
        初始化去重管道

        Args:
            pool_name: 去重池名称
            unique_key_fields: 唯一键字段列表
        """
        self.pool_name = pool_name
        self.unique_key_fields = unique_key_fields
        self.fingerprint_pool = GlobalFingerprintPool()
        self.fingerprint_pool.init_pool(pool_name)

    def deduplicate(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对数据列表进行去重

        Args:
            data_list: 原始数据列表

        Returns:
            去重后的数据列表
        """
        return self.fingerprint_pool.deduplicate_list(data_list, self.unique_key_fields)

    def is_duplicate(self, data: Dict[str, Any]) -> bool:
        """
        检查单条数据是否重复

        Args:
            data: 数据字典

        Returns:
            True表示重复，False表示不重复
        """
        return self.fingerprint_pool.is_duplicate(data, self.unique_key_fields)

    def add_fingerprint(self, data: Dict[str, Any]):
        """
        添加单条数据的指纹

        Args:
            data: 数据字典
        """
        self.fingerprint_pool.add_fingerprint(data, self.unique_key_fields)

    def clear(self):
        """
        清空当前去重池
        """
        self.fingerprint_pool.clear_pool()


def deduplicate_data(
    data_list: List[Dict[str, Any]],
    pool_name: str,
    unique_key_fields: List[str]
) -> List[Dict[str, Any]]:
    """
    便捷函数：直接对数据列表进行去重

    Args:
        data_list: 原始数据列表
        pool_name: 去重池名称
        unique_key_fields: 唯一键字段列表

    Returns:
        去重后的数据列表
    """
    pipeline = DeduplicationPipeline(pool_name, unique_key_fields)
    return pipeline.deduplicate(data_list)
