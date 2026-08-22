# -*- coding:utf-8 -*-
"""
导出字段格式化工具

提供统一的字段值转换与格式化能力，避免各业务模块重复实现。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Optional, Union


Formatter = Callable[[Any], Any]


def identity(value: Any) -> Any:
    """原值返回，用于不需要格式化的字段。"""
    return value


def default_if_none(default: Any = '') -> Formatter:
    """将 None 替换为默认值。"""
    def _formatter(value: Any) -> Any:
        return default if value is None else value
    return _formatter


def format_price(value: Any, default: Any = '') -> Any:
    """
    格式化为价格数值。

    规则：
    - None / 空字符串 / 0 返回 default
    - 数字类型转为 float
    - 其他类型原样返回
    """
    if value is None or value == '' or value == 0:
        return default
    try:
        if isinstance(value, (int, float, Decimal)):
            return float(value)
        return float(str(value).replace(',', ''))
    except (ValueError, TypeError):
        return value


def format_number(value: Any, default: Any = '', as_int: bool = True) -> Any:
    """
    格式化为数值。

    Args:
        value: 原始值
        default: 空值时的默认值
        as_int: 是否转为整数（True：int；False：float）
    """
    if value is None or value == '' or value == 0:
        return default
    try:
        num = float(value)
        return int(num) if as_int else num
    except (ValueError, TypeError):
        return value


def format_date(fmt: str = '%Y-%m-%d %H:%M:%S') -> Formatter:
    """将日期/时间对象格式化为字符串。"""
    def _formatter(value: Any) -> Any:
        if value is None:
            return ''
        if isinstance(value, (datetime, date)):
            return value.strftime(fmt)
        return value
    return _formatter


def truncate_text(max_length: int = 100, suffix: str = '...') -> Formatter:
    """截断超长文本。"""
    def _formatter(value: Any) -> Any:
        if value is None:
            return ''
        text = str(value)
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    return _formatter


def replace_newline(replacement: str = ' ') -> Formatter:
    """将换行符替换为指定字符，常用于 CSV 导出。"""
    def _formatter(value: Any) -> Any:
        if value is None:
            return ''
        return str(value).replace('\r\n', replacement).replace('\n', replacement).replace('\r', replacement)
    return _formatter


def chain(*formatters: Formatter) -> Formatter:
    """将多个格式化函数串联执行。"""
    def _formatter(value: Any) -> Any:
        for fn in formatters:
            value = fn(value)
        return value
    return _formatter


class FormatterRegistry:
    """格式化函数注册表，支持按字段名或字段类型注册默认格式化器。"""

    def __init__(self):
        self._field_formatters: dict[str, Formatter] = {}
        self._type_formatters: list[tuple[type, Formatter]] = []

    def register(self, field: str, formatter: Formatter) -> 'FormatterRegistry':
        """为指定字段名注册格式化器。"""
        self._field_formatters[field] = formatter
        return self

    def register_type(self, field_type: type, formatter: Formatter) -> 'FormatterRegistry':
        """为指定数据类型注册默认格式化器。"""
        self._type_formatters.append((field_type, formatter))
        return self

    def get(self, field: str) -> Optional[Formatter]:
        """获取字段对应的格式化器。"""
        return self._field_formatters.get(field)

    def format_value(self, field: str, value: Any) -> Any:
        """
        对字段值进行格式化。

        优先级：字段级格式化器 > 类型级格式化器 > 原值
        """
        formatter = self._field_formatters.get(field)
        if formatter:
            return formatter(value)

        for field_type, type_formatter in self._type_formatters:
            if isinstance(value, field_type):
                return type_formatter(value)

        return value
