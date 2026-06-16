# -*- coding:utf-8 -*-
# @Time    : 2026/6/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_bmw.py
# @Software: PyCharm
# 华晨宝马零件详情表（零件详细信息 + 价格信息）
# 对应爬虫接口：query_part_detail（零件详情查询）
# 数据库设计参考 demo/test 输出
# ===============================================================


from sqlalchemy import Column, String, DateTime
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CarPartsLibraryBmw(BaseModels):
    __tablename__ = 'car_parts_library_bmw'

    # ===================== 主键与基础信息 =====================
    part_number = Column(String(510), primary_key=True, comment='配件编号(OE号)')
    part_name = Column(String(510), nullable=True, comment='零件名称')
    sales_unit = Column(String(50), nullable=True, comment='基本单位/销售单位')
    material_group = Column(String(100), nullable=True, comment='族组/物料组')

    # ===================== 重量/体积信息 =====================
    gross_weight = Column(String(50), nullable=True, comment='毛重(含原始单位如1.067KG)')
    net_weight = Column(String(50), nullable=True, comment='净重(含原始单位如1.067KG)')
    volume = Column(String(50), nullable=True, comment='体积(含原始单位如22.040CDM)')

    # ===================== 价格信息（数据库存储原始值，均为varchar） =====================
    retail_price = Column(String(50), nullable=True, comment='零售价(爬虫返回的原始含税价格)')
    discount_stock = Column(String(50), nullable=True, comment='经销商折扣(Stock, 含%如25%)')
    discount_rush = Column(String(50), nullable=True, comment='经销商折扣(Rush, 含%如25%)')
    dealer_net_stock = Column(String(50), nullable=True, comment='经销商净值(Stock订单，含税)')
    dealer_net_rush = Column(String(50), nullable=True, comment='经销商净值(Rush订单，含税)')

    # ===================== 库存信息 =====================
    available_stock = Column(String(50), nullable=True, comment='可用库存(含单位如35件)')

    # ===================== 时间字段 =====================
    data_collect_time = Column(String(50), nullable=True, comment='采集时间(原始字符串)')
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def to_dict(self):
        """
        单个对象转字典（返回数据库原始字段）
        :return: 字典形式的对象数据
        """
        return {
            'part_number': self.part_number,
            'part_name': self.part_name,
            'sales_unit': self.sales_unit,
            'material_group': self.material_group,
            'gross_weight': self.gross_weight,
            'net_weight': self.net_weight,
            'volume': self.volume,
            'retail_price': self.retail_price,
            'discount_stock': self.discount_stock,
            'discount_rush': self.discount_rush,
            'dealer_net_stock': self.dealer_net_stock,
            'dealer_net_rush': self.dealer_net_rush,
            'available_stock': self.available_stock,
            'data_collect_time': self.data_collect_time,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

