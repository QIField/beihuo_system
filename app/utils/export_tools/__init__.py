# -*- coding:utf-8 -*-
"""
数据导出工具包

提供统一的数据导出功能，支持复合搜索条件、全量数据导出、异步导出等能力。
当前标准导出组件仅支持 Excel (.xlsx) 格式，默认使用蓝色表头样式。

使用示例（新版核心模块）:
    from app.utils.export_tools import ExportConfig, export_data, export_from_request
    from app.utils.export_tools.formatters import format_price, format_number

    # 1. 声明导出配置
    config = ExportConfig(
        fields=['oe', 'brand', 'price', 'stock'],
        headers={
            'oe': 'OE号',
            'brand': '品牌',
            'price': '价格',
            'stock': '库存',
        },
        filename_template='备货数据_{timestamp}.xlsx',
        transformers={
            'price': format_price,
            'stock': format_number,
        },
    )

    # 2. 直接导出已有数据
    response = export_data(config, data)

    # 3. 从 request 自动提取搜索条件并导出
    def fetch_data(**search_params):
        # 根据 search_params 查询全量数据
        return query_all_data(**search_params)

    response = export_from_request(config, fetch_data, request)

旧版兼容入口（备货/购物车）:
    from app.utils.export_tools import handle_export_request
    response = handle_export_request('beihuo', store='fsbbr', search_params={'oe': '123'})
"""

# 旧版兼容导出
from .export_utils import (
    handle_export_request,
    export_beihuo,
    export_cart,
    export_data_to_excel,
)

# 新版核心模块
from .core import (
    ExportConfig,
    DataProvider,
    SearchParamNormalizer,
    export_data,
    export_multi_sheets,
    export_with_provider,
    export_from_request,
)

# 格式化工具
from .formatters import (
    FormatterRegistry,
    format_price,
    format_number,
    format_date,
    truncate_text,
    replace_newline,
    default_if_none,
    chain,
)

# 导出引擎
from .exporters import (
    BaseExporter,
    ExcelExporter,
    get_exporter,
)

# 比价模块统一样式
from .excel_styles import (
    apply_uniform_style,
    apply_header_style,
    apply_data_style,
    apply_freeze_panes,
    apply_auto_filter,
    HEADER_FONT,
    HEADER_FILL,
    HEADER_ALIGN,
    DATA_FONT,
    ALT_FILL,
)

# 异步导出
from .async_export import (
    submit_export_task,
    submit_multi_sheet_export_task,
    submit_provider_export_task,
)

__all__ = [
    # 旧版兼容
    'handle_export_request',
    'export_beihuo',
    'export_cart',
    'export_data_to_excel',

    # 新版核心
    'ExportConfig',
    'DataProvider',
    'SearchParamNormalizer',
    'export_data',
    'export_multi_sheets',
    'export_with_provider',
    'export_from_request',

    # 格式化
    'FormatterRegistry',
    'format_price',
    'format_number',
    'format_date',
    'truncate_text',
    'replace_newline',
    'default_if_none',
    'chain',

    # 导出引擎
    'BaseExporter',
    'ExcelExporter',
    'get_exporter',

    # 比价模块统一样式
    'apply_uniform_style',
    'apply_header_style',
    'apply_data_style',
    'apply_freeze_panes',
    'apply_auto_filter',
    'HEADER_FONT',
    'HEADER_FILL',
    'HEADER_ALIGN',
    'DATA_FONT',
    'ALT_FILL',

    # 异步导出
    'submit_export_task',
    'submit_multi_sheet_export_task',
    'submit_provider_export_task',
]
