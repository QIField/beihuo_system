"""
数据库表管理模块
按功能分类管理各模块的表结构
"""

from .sales_tables import (
    init_sales_history_detail_table,
    init_quote_count_ks_table,
)

from .procurement_tables import (
    init_procurement_history_table,
)

from .procurement_detail_tables import (
    init_procurement_history_detail_table,
)

from .inventory_tables import (
    init_zhuozhixing_table,
    init_inventory_detail_table,
)

from .inquiry_tables import (
    init_ks_inquiry_detail_table,
    init_weixin_inquiry_detail_table,
    init_ks_inquiry_monitor_table,
    init_price_inquiry_direct_table,
)

from .virtual_inventory_stats_tables import (
    init_virtual_inventory_stats_log_table,
)

from .virtual_inventory_tables import (
    init_all_virtual_inventory_tables,
)

from .shop_event_tables import (
    init_shop_event_summary_table,
    init_shop_event_detail_table,
    init_shop_business_indicator_table,
)

from .safety_stock_tables import (
    init_safety_stock_calculation_table,
)

from .qpl_quote_tables import (
    init_qpl_quote_record_table,
)

__all__ = [
    'init_sales_history_detail_table',
    'init_quote_count_ks_table',
    'init_procurement_history_table',
    'init_procurement_history_detail_table',
    'init_zhuozhixing_table',
    'init_inventory_detail_table',
    'init_ks_inquiry_detail_table',
    'init_weixin_inquiry_detail_table',
    'init_virtual_inventory_stats_log_table',
    'init_ks_inquiry_monitor_table',
    'init_shop_event_summary_table',
    'init_shop_event_detail_table',
    'init_shop_business_indicator_table',
    'init_price_inquiry_direct_table',
    'init_safety_stock_calculation_table',
    'init_all_virtual_inventory_tables',
    'init_qpl_quote_record_table',
]
