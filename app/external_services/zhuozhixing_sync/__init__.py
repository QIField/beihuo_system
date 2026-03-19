# -*- coding: utf-8 -*-
"""
卓之星库存数据同步模块

功能：
1. 从卓之星API获取广星、鑫峰供应商的库存数据
2. 数据预处理后存入数据库
3. 支持定时任务自动同步和手动触发

使用：
    from app.external_services.zhuozhixing_sync.sync_service import sync_all_suppliers
    sync_all_suppliers()  # 手动触发同步
"""

from .sync_service import sync_all_suppliers, sync_supplier
from .config import SUPPLIERS

__all__ = ['sync_all_suppliers', 'sync_supplier', 'SUPPLIERS']
