"""
CRM Product Package - CRM产品处理包
包含CRM产品新建、处理等相关功能
"""

# 导出主要功能函数
from .crm新建产品 import (
    main,
    main_excel_mode,
    process_excel_file_mode,
    identify_columns,
    add_result_column,
    create_zip_package,
    load_alias_data,
    load_product_data,
    get_db_connection,
    DatabaseManager,
    # 新增的多工作表处理函数
    process_excel_two_column_mode,
    process_excel_three_column_mode,
    filter_sheets_by_mode,
    process_single_sheet,
    identify_columns_extended,
    # 新增的批量处理相关函数
    process_single_item_batch,
    find_matching_product_id_simple
)

# 导出配置和常量
from .crm新建产品 import (
    API_CONFIG,
    MYSQL_CONFIG,
    headers,
    PRODUCT_DF,
    ALIAS_DF,
    GLOBAL_SESSION
)

__version__ = "1.0.0"
__author__ = "BBR Team"
__all__ = [
    'main',
    'main_excel_mode', 
    'process_excel_file_mode',
    'identify_columns',
    'add_result_column',
    'create_zip_package',
    'load_alias_data',
    'load_product_data',
    'get_db_connection',
    'DatabaseManager',
    # 新增函数
    'process_excel_two_column_mode',
    'process_excel_three_column_mode',
    'filter_sheets_by_mode',
    'process_single_sheet',
    'identify_columns_extended',
    'process_single_item_batch',
    'find_matching_product_id_simple',
    'API_CONFIG',
    'MYSQL_CONFIG',
    'headers',
    'PRODUCT_DF',
    'ALIAS_DF',
    'GLOBAL_SESSION'
]