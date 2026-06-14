# -*- coding:utf-8 -*-
# @Time    : 2026/06/09 17:38
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : cache_utils.py
# @Software: trae-cn

"""
cache_utils.py - 轻量级内存缓存模块 (Redis-like)
省内存设计：__slots__ 节点 + LRU + TTL
线程安全可选。
"""

import time
import threading
import pickle
from functools import wraps
from typing import Any, Optional, Dict, List, Union


class _CacheNode:
    """双向链表节点，使用 __slots__ 减少内存开销"""
    __slots__ = ('key', 'value', 'expire_at', 'prev', 'next')

    def __init__(self, key: Any, value: Any, expire_at: Optional[float] = None):
        self.key = key
        self.value = value
        self.expire_at = expire_at  # None 表示永不过期，否则为 Unix 时间戳
        self.prev: Optional['_CacheNode'] = None
        self.next: Optional['_CacheNode'] = None


class Cache:
    """
    本地内存缓存，类似 Redis 基础功能。

    特性：
    - O(1) 的 get/set/delete
    - 支持最大容量 (maxsize)，超出时 LRU 淘汰
    - 支持全局默认 TTL 和单键 TTL
    - 线程安全（可选锁）
    - 省内存：节点使用 __slots__
    """

    def __init__(self, maxsize: int = 1024, default_ttl: Optional[int] = None, thread_safe: bool = False):
        """
        :param maxsize: 最大缓存键数，超出后淘汰最久未使用的键
        :param default_ttl: 默认过期时间（秒），None 为永不过期
        :param thread_safe: 是否启用线程锁
        """
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._thread_safe = thread_safe
        self._lock = threading.Lock() if thread_safe else None

        self._store: Dict[Any, _CacheNode] = {}  # key -> node
        self._head: Optional[_CacheNode] = None  # 最近使用 (MRU)
        self._tail: Optional[_CacheNode] = None  # 最久未使用 (LRU)

    def _acquire(self):
        if self._lock:
            self._lock.acquire()

    def _release(self):
        if self._lock:
            self._lock.release()

    def _remove_node(self, node: _CacheNode):
        """从链表中移除节点，不清理字典"""
        if node.prev:
            node.prev.next = node.next
        else:
            self._head = node.next

        if node.next:
            node.next.prev = node.prev
        else:
            self._tail = node.prev

    def _add_to_head(self, node: _CacheNode):
        """将节点添加到链表头部（最近使用）"""
        node.prev = None
        node.next = self._head
        if self._head:
            self._head.prev = node
        self._head = node
        if self._tail is None:
            self._tail = node

    def _move_to_head(self, node: _CacheNode):
        """将已存在的节点移到头部"""
        if self._head is node:
            return
        self._remove_node(node)
        self._add_to_head(node)

    def _pop_tail(self):
        """移除并返回尾部节点（最久未使用）"""
        if self._tail is None:
            return None
        node = self._tail
        self._remove_node(node)
        return node

    def _is_expired(self, node: _CacheNode) -> bool:
        """检查节点是否过期"""
        if node.expire_at is None:
            return False
        return time.time() > node.expire_at

    def _purge_expired(self):
        """
        主动清理所有过期键（调用时遍历）。
        注意：get/set 时只会被动删除遇到的过期键，此为辅助全量清理。
        """
        # 遍历时直接基于字典键快照进行删除
        keys = list(self._store.keys())
        for key in keys:
            node = self._store.get(key)
            if node and self._is_expired(node):
                self._remove_node(node)
                del self._store[key]

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置键值，可指定过期时间（秒）。
        ttl 为 None 则使用 default_ttl，若 ttl=None 且 default_ttl=None 则永不过期。
        返回 True 表示设置成功。
        """
        self._acquire()
        try:
            now = time.time()
            expire_at = None
            effective_ttl = ttl if ttl is not None else self._default_ttl
            if effective_ttl is not None:
                expire_at = now + effective_ttl

            # 如果 key 已存在，更新值并移到头部
            if key in self._store:
                node = self._store[key]
                node.value = value
                node.expire_at = expire_at
                self._move_to_head(node)
                return True

            # 如果容量已满，先淘汰尾部
            if len(self._store) >= self._maxsize:
                tail = self._pop_tail()
                if tail:
                    del self._store[tail.key]

            # 创建新节点，放入 store 并添加到头部
            node = _CacheNode(key, value, expire_at)
            self._store[key] = node
            self._add_to_head(node)
            return True
        finally:
            self._release()

    def get(self, key: Any, default: Any = None) -> Any:
        """获取键值，若不存在或已过期返回 default"""
        self._acquire()
        try:
            node = self._store.get(key)
            if node is None:
                return default
            if self._is_expired(node):
                # 被动删除过期键
                self._remove_node(node)
                del self._store[key]
                return default
            # 移到头部（最近使用）
            self._move_to_head(node)
            return node.value
        finally:
            self._release()

    def delete(self, key: Any) -> bool:
        """删除一个键，成功返回 True，键不存在返回 False"""
        self._acquire()
        try:
            node = self._store.pop(key, None)
            if node is None:
                return False
            self._remove_node(node)
            return True
        finally:
            self._release()

    def exists(self, key: Any) -> bool:
        """判断键是否存在且未过期"""
        self._acquire()
        try:
            node = self._store.get(key)
            if node is None:
                return False
            if self._is_expired(node):
                self._remove_node(node)
                del self._store[key]
                return False
            return True
        finally:
            self._release()

    def expire(self, key: Any, ttl: int) -> bool:
        """为已存在的键设置过期时间（秒），键不存在返回 False"""
        self._acquire()
        try:
            node = self._store.get(key)
            if node is None:
                return False
            if self._is_expired(node):
                self._remove_node(node)
                del self._store[key]
                return False
            node.expire_at = time.time() + ttl
            return True
        finally:
            self._release()

    def ttl(self, key: Any) -> int:
        """
        返回键剩余生存时间（秒），若键不存在或已过期返回 -2，
        若键永不过期返回 -1。
        """
        self._acquire()
        try:
            node = self._store.get(key)
            if node is None:
                return -2
            if self._is_expired(node):
                self._remove_node(node)
                del self._store[key]
                return -2
            if node.expire_at is None:
                return -1
            remaining = int(node.expire_at - time.time())
            return max(remaining, 0)
        finally:
            self._release()

    def keys(self, pattern: Optional[str] = None) -> List[Any]:
        """
        返回所有未过期键的列表。
        注意：pattern 为简单字符串包含匹配，类似 Redis 的 keys *pattern*，
             仅支持 '*' 通配符，不实现完整 glob。
        """
        self._acquire()
        try:
            # 先清理所有过期键
            self._purge_expired()
            all_keys = list(self._store.keys())
            if pattern is None:
                return all_keys
            # 简单转换：将 * 替换为任意字符的判定
            # 仅支持前后或中间的 *
            import fnmatch
            return [k for k in all_keys if fnmatch.fnmatch(str(k), pattern)]
        finally:
            self._release()

    def clear(self):
        """清空全部缓存"""
        self._acquire()
        try:
            self._store.clear()
            self._head = None
            self._tail = None
        finally:
            self._release()

    def __len__(self) -> int:
        """返回当前未过期缓存数量（会触发一次清理）"""
        self._acquire()
        try:
            self._purge_expired()
            return len(self._store)
        finally:
            self._release()

    def __contains__(self, key: Any) -> bool:
        return self.exists(key)

    def __repr__(self) -> str:
        return f"<Cache size={len(self._store)}/{self._maxsize}>"


# ============================================================
# 应用级默认缓存实例（进程内共享）
# ============================================================

_app_level_cache_instance: Optional["Cache"] = None


def get_default_cache(maxsize: int = 2048, default_ttl: int = 600,
                      thread_safe: bool = True) -> "Cache":
    """获取应用级默认缓存（懒加载单例）

    Flask + 定时任务多线程场景下默认 thread_safe=True。
    第一次调用时才真正创建实例，后续调用直接复用。

    Args:
        maxsize: 最大键数，超出后 LRU 淘汰。默认 2048
        default_ttl: 默认过期秒数，默认 600 秒（1 分钟）
        thread_safe: 是否启用线程锁，默认 True

    Returns:
        全局共享的 Cache 实例
    """
    global _app_level_cache_instance
    if _app_level_cache_instance is None:
        _app_level_cache_instance = Cache(maxsize=maxsize,
                                          default_ttl=default_ttl,
                                          thread_safe=thread_safe)
    return _app_level_cache_instance


def reset_default_cache(maxsize: int = 2048, default_ttl: int = 300,
                        thread_safe: bool = True) -> "Cache":
    """重建默认缓存（主要用于测试或配置变更后重置）"""
    global _app_level_cache_instance
    _app_level_cache_instance = Cache(maxsize=maxsize,
                                      default_ttl=default_ttl,
                                      thread_safe=thread_safe)
    return _app_level_cache_instance


# ============================================================
# 缓存装饰器：给任意函数/方法加缓存
# ============================================================

def _make_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """根据函数名和参数生成缓存 key"""
    try:
        # 优先尝试 pickle 序列化（支持大多数对象）
        key_payload = pickle.dumps((args, sorted(kwargs.items(),
                                                 key=lambda kv: kv[0])))
        return f"{func_name}:" + key_payload.hex()
    except Exception:
        # 不可 pickle 的对象回退到字符串（可能会有碰撞，但够用）
        return f"{func_name}:{repr(args)}:{repr(sorted(kwargs.items()))}"


def cache_function_result(ttl: Optional[int] = None,
                          cache_obj: Optional["Cache"] = None,
                          *, skip_none: bool = True):
    """函数级缓存装饰器：缓存函数的返回值

    用法示例:
        @cache_function_result(ttl=300)        # 缓存 5 分钟
        def query_report(company_id):
            ...

        @cache_function_result(ttl=60, cache_obj=my_cache)  # 指定自己的 Cache 实例
        def slow_function(a, b):
            ...

    Args:
        ttl: 过期秒数；None 则使用 Cache 实例的 default_ttl
        cache_obj: 指定 Cache 实例；None 则使用 get_default_cache()
        skip_none: 函数返回 None 时是否不缓存，默认 True（避免缓存空结果）
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            c = cache_obj or get_default_cache()
            key = _make_key(func.__qualname__, args, kwargs)
            hit = c.get(key)
            if hit is not None:
                return hit
            result = func(*args, **kwargs)
            if skip_none and result is None:
                return result
            c.set(key, result, ttl=ttl)
            return result

        return wrapper

    return decorator