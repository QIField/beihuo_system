"""
数据库表管理模块
按功能分类管理各模块的表结构
"""

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
)

__all__ = [
    'init_procurement_history_table',
    'init_procurement_history_detail_table',
    'init_zhuozhixing_table',
    'init_inventory_detail_table',
    'init_ks_inquiry_detail_table',
    'init_weixin_inquiry_detail_table',
]
