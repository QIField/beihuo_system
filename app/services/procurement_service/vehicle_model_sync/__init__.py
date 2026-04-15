"""
车型同步模块
用于CRM产品爬取时同步车型字段
"""

from .brand_priority import BrandPriority
from .vehicle_model_sync_service import VehicleModelSyncService

__all__ = ['BrandPriority', 'VehicleModelSyncService']
