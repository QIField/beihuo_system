# -*- coding:utf-8 -*-
"""
去重 FIFO 队列

底层用单个 OrderedDict 实现"队列 + 去重"：
- key 由 key_func 从元素中提取（必须可哈希），作为去重依据
- OrderedDict 保持插入顺序，插入顺序即队列顺序
- popitem(last=False) 从最早插入的一端弹出，实现 FIFO 出队
- 配合 threading.Lock 保护复合操作，保证多线程并发安全
"""
from threading import Lock
from typing import Callable, Hashable, Optional, OrderedDict, TypeVar

T = TypeVar("T")


class UniqueQueue:
    """
    线程安全的去重 FIFO 队列

    元素按入队先后排队；key_func 提取的 key 相同视为重复元素，
    重复入队时丢弃新元素、保留最早入队的版本；出队时原样返回入队元素。

    用法示例:
        queue = UniqueQueue(key_func=lambda it: (it["number"], it["brand_name"]))
        queue.put({"number": "A001", "brand_name": "XX"})  # -> True
        queue.put({"number": "A001", "brand_name": "XX"})  # -> False（重复，丢弃）
        queue.pop()  # -> {"number": "A001", "brand_name": "XX"}
    """

    def __init__(self, key_func: Callable[[T], Hashable]):
        """
        Args:
            key_func: 从元素中提取去重 key 的函数，返回值必须可哈希
                （单字段: lambda it: it["task_id"]，多字段: lambda it: (it["a"], it["b"])）
        """
        self._key_func = key_func
        # key -> 入队元素；插入顺序即队列顺序，value 保存源数据引用
        self._data: OrderedDict[Hashable, T] = OrderedDict()  # pyright: ignore[reportGeneralTypeIssues]
        self._lock = Lock()

    def put(self, item: T) -> bool:  # pyright: ignore[reportInvalidTypeVarUse]
        """
        入队。key 重复时丢弃新元素。

        Args:
            item: 入队元素

        Returns:
            bool: 新增成功返回 True；key 重复被丢弃返回 False
        """
        with self._lock:
            key = self._key_func(item)  # pyright: ignore[reportArgumentType]
            if key in self._data:
                return False
            self._data[key] = item
            return True

    def pop(self) -> Optional[T]:
        """
        出队（FIFO），返回最早入队的元素。

        Returns:
            队首元素；队列为空时返回 None
        """
        with self._lock:
            if not self._data:
                return None
            _, item = self._data.popitem(last=False)
            return item

    def contains(self, item: T) -> bool:  # pyright: ignore[reportInvalidTypeVarUse]
        """
        判断元素是否已在队列中（按 key_func 提取的 key 判断）

        Args:
            item: 待判断的元素

        Returns:
            bool: 队列中存在相同 key 的元素返回 True
        """
        with self._lock:
            return self._key_func(item) in self._data  # pyright: ignore[reportArgumentType]

    def remove(self, item: T) -> bool:  # pyright: ignore[reportInvalidTypeVarUse]
        """
        按元素（key_func 提取的 key）从队列中移除

        Args:
            item: 待移除的元素

        Returns:
            bool: 移除成功返回 True；元素不在队列中返回 False
        """
        with self._lock:
            key = self._key_func(item)  # pyright: ignore[reportArgumentType]
            if key in self._data:
                del self._data[key]
                return True
            return False

    def clear(self) -> None:
        """清空队列"""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


