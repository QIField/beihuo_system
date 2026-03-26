"""
采购模块服务包

用于从 CRM 获取产品信息并同步到比价汇总表

主要功能:
    - 根据 OE 号和品牌从 CRM 获取产品信息
    - 提取产品名称、车辆品牌、是否同步开思等字段
    - 更新到 crmapp_compare_summary 表

使用示例:
    # 方式1: 处理单个 OE
    from app.services.procurement_service import process_single_oe
    process_single_oe('11427585403', '原厂', 'fsbbr')
    
    # 方式2: 批量处理
    from app.services.procurement_service import process_oe_list
    oe_list = [('11427585403', '原厂'), ('11427585404', '品牌A')]
    process_oe_list(oe_list, 'fsbbr')
    
    # 方式3: 处理所有待处理 OE
    from app.services.procurement_service import process_all_pending_oes
    process_all_pending_oes('fsbbr')
"""

from .main import (
    process_single_oe,
    process_oe_list,
    process_all_pending_oes,
    get_crm_session
)

from .api_client import (
    fetch_product_info,
    fetch_product_info_batch
)

from .db_service import (
    update_product_fields,
    batch_update_product_fields,
    get_pending_oe_list
)

from .procurement_record_service import (
    parse_purchasing_record,
    get_procurement_records,
    init_table,
    add_inquiry_record
)

# 兼容别名
init_procurement_table = init_table

__all__ = [
    # 主函数
    'process_single_oe',
    'process_oe_list',
    'process_all_pending_oes',
    'get_crm_session',
    
    # API 客户端
    'fetch_product_info',
    'fetch_product_info_batch',
    
    # 数据库服务
    'update_product_fields',
    'batch_update_product_fields',
    'get_pending_oe_list',
    
    # 采购记录服务
    'parse_purchasing_record',
    'get_procurement_records',
    'init_table',
    'init_procurement_table',
    'add_inquiry_record'
]
