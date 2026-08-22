# -*- coding:utf-8 -*-
"""
通用数据导出核心模块

提供声明式导出配置、全量数据导出、搜索条件透传等能力。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol, Union

from flask import jsonify, Response

from .exporters import BaseExporter, ExcelExporter, get_exporter
from .formatters import FormatterRegistry


DataFetcher = Callable[..., List[Dict[str, Any]]]


class SearchParamNormalizer:
    """搜索参数归一化工具，统一处理前后端搜索条件。"""

    @staticmethod
    def from_request(request_obj) -> Dict[str, Any]:
        """
        从 Flask request 中提取所有查询参数。

        兼容 GET/POST，自动去除首尾空格，保留空字符串以支持"清空筛选"。
        """
        params = {}
        # GET 参数与 form 参数合并
        for key, value in request_obj.values.items(multi=True):
            if key in params:
                continue
            if isinstance(value, str):
                value = value.strip()
            params[key] = value
        return params

    @staticmethod
    def clean_empty(params: Dict[str, Any], keep_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """清理空值参数，但保留指定 key。"""
        keep_keys = set(keep_keys or [])
        return {
            k: v for k, v in params.items()
            if v not in (None, '', []) or k in keep_keys
        }


@dataclass
class ExportConfig:
    """
    导出配置类。

    通过声明式配置描述一次导出行为，包括字段、表头、格式、文件名、转换规则等。
    """

    # 字段顺序列表（决定 Excel/CSV 列顺序）
    fields: List[str]

    # 字段→中文表头映射
    headers: Dict[str, str]

    # 导出格式：当前标准组件仅支持 xlsx
    export_format: str = 'xlsx'

    # 文件名模板，支持 {timestamp} 占位符
    filename_template: str = '导出数据_{timestamp}.xlsx'

    # Excel 工作表名称
    sheet_name: str = '数据'

    # 字段转换器：field -> callable(value)
    transformers: Dict[str, Callable[[Any], Any]] = field(default_factory=dict)

    # 全局格式化注册表
    formatter_registry: Optional[FormatterRegistry] = None

    # Excel 列宽配置：列字母 -> 宽度
    column_widths: Optional[Dict[str, float]] = None

    # 是否冻结表头
    freeze_header: bool = True

    # 表头样式配置（默认使用蓝色比价模块风格）
    header_style: Optional[Dict[str, Any]] = None

    def get_header(self, field: str) -> str:
        """获取字段对应的中文表头。"""
        return self.headers.get(field, field)

    def get_filename(self) -> str:
        """生成最终文件名（标准组件仅输出 .xlsx）。"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.filename_template.format(timestamp=timestamp)

        if not filename.endswith('.xlsx'):
            filename += '.xlsx'
        return filename

    def transform_value(self, field: str, value: Any) -> Any:
        """
        对字段值进行转换。

        优先级：字段专属转换器 > 全局格式化注册表 > 原值
        """
        if field in self.transformers:
            return self.transformers[field](value)

        if self.formatter_registry:
            return self.formatter_registry.format_value(field, value)

        if value is None:
            return ''
        return value

    def prepare_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对原始数据进行转换和字段裁剪。"""
        result = []
        for item in data:
            row = {}
            for field in self.fields:
                value = item.get(field)
                row[field] = self.transform_value(field, value)
            result.append(row)
        return result

    def build_exporter(self) -> BaseExporter:
        """根据当前配置构建 Excel 导出引擎。"""
        options = {
            'column_widths': self.column_widths,
            'freeze_header': self.freeze_header,
        }

        if self.header_style:
            options['header_style'] = self.header_style

        return get_exporter(self.export_format, self.fields, self.headers, **options)


class DataProvider(Protocol):
    """数据提供者协议，业务模块按此协议实现全量数据查询。"""

    def fetch(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据搜索条件返回全量数据（不分页）。"""
        ...

    def get_config(self) -> ExportConfig:
        """返回导出配置。"""
        ...


def export_data(config: ExportConfig, data: List[Dict[str, Any]]) -> Response:
    """
    通用数据导出入口。

    Args:
        config: 导出配置
        data: 原始数据列表

    Returns:
        Flask Response 对象
    """
    if not data:
        return jsonify({'code': 1, 'msg': '没有数据可导出'}), 400

    prepared_data = config.prepare_data(data)
    exporter = config.build_exporter()
    return exporter.export(
        prepared_data,
        filename=config.get_filename(),
        sheet_name=config.sheet_name,
    )


def export_with_provider(provider: DataProvider, search_params: Dict[str, Any]) -> Response:
    """
    通过数据提供者执行导出。

    Args:
        provider: 实现 DataProvider 协议的对象
        search_params: 搜索条件
    """
    config = provider.get_config()
    data = provider.fetch(search_params)
    return export_data(config, data)


def export_from_request(
    config: ExportConfig,
    fetcher: DataFetcher,
    request_obj,
    clean_empty_params: bool = True,
    keep_params: Optional[List[str]] = None,
) -> Response:
    """
    从 Flask request 中自动提取搜索条件并导出。

    Args:
        config: 导出配置
        fetcher: 数据获取函数，接收 search_params 返回 List[dict]
        request_obj: Flask request 对象
        clean_empty_params: 是否清理空值参数
        keep_params: 即使为空也保留的参数 key
    """
    params = SearchParamNormalizer.from_request(request_obj)
    if clean_empty_params:
        params = SearchParamNormalizer.clean_empty(params, keep_keys=keep_params)

    data = fetcher(**params)
    return export_data(config, data)
