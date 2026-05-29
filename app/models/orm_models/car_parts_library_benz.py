# -*- coding:utf-8 -*-
# @Time    : 2026/5/20 15:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library.py
# @Software: PyCharm


from sqlalchemy import Column, String, Float, BigInteger, DateTime, DECIMAL, Text
from datetime import datetime
from sqlalchemy.dialects.mysql import insert, LONGTEXT

from app.models.orm_models.base_models import BaseModels


class CarPartsLibraryBenz(BaseModels):
    __tablename__ = 'car_parts_library_benz'

    # 基础字段
    part_number = Column(String(510), primary_key=True, comment='配件编号')
    descriptions = Column(String(510), nullable=True, comment='英文描述')
    description_cn = Column(String(510), nullable=True, comment='中文描述')
    marketing_code = Column(String(510), nullable=True, comment='营销代码')
    dealer_discount_group = Column(String(510), nullable=True, comment='经销商折扣组')
    msrp = Column(Float, nullable=True, comment='建议零售价')
    dealer_fixed_nominal_margin = Column(Float, nullable=True, comment='经销商固定名义利润')
    wholesale_price = Column(Float, nullable=True, comment='批发价格')
    marketing_code_description = Column(String(510), nullable=True, comment='营销代码描述')
    quantity_unit = Column(String(510), nullable=True, comment='数量单位')
    sales_pack_size = Column(String(510), nullable=True, comment='销售包装规格')
    weight = Column(BigInteger, nullable=True, comment='重量')
    length = Column(String(510), nullable=True, comment='长度')
    width = Column(String(510), nullable=True, comment='宽度')
    height = Column(String(510), nullable=True, comment='高度')
    effective_date = Column(String(510), nullable=True, comment='生效日期')
    data_source = Column(String(100), nullable=True, comment='数据来源')
    l_model_zh = Column(Text, nullable=True, comment='车型中文名')

    # 截图新增字段
    brand = Column(String(100), nullable=True, comment='品牌')
    category = Column(String(100), nullable=True, comment='分类')
    ccc_mark = Column(String(50), nullable=True, comment='CCC标识')
    volume = Column(DECIMAL(10, 3), nullable=True, comment='体积')
    hazmat_code = Column(String(50), nullable=True, comment='危险货物代码')
    origin_country = Column(String(50), nullable=True, comment='原产地')
    shelf_life = Column(String(100), nullable=True, comment='存储期限')
    is_hazmat = Column(String(10), nullable=True, comment='防盗标识/危险品')
    purchase_price = Column(DECIMAL(18, 2), nullable=True, comment='巴博瑞采购价')
    
    # 零件替代关系信息（JSON格式）
    part_nr_info_super_session = Column(LONGTEXT, nullable=True, comment='零件替代关系信息')

    # 时间字段
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def to_dict(self):
        """
        单个对象转字典
        :return: 字典形式的对象数据
        """
        return {
            'part_number': self.part_number,
            'descriptions': self.descriptions,
            'description_cn': self.description_cn,
            'marketing_code': self.marketing_code,
            'dealer_discount_group': self.dealer_discount_group,
            'msrp': self.msrp,
            'dealer_fixed_nominal_margin': self.dealer_fixed_nominal_margin,
            'wholesale_price': self.wholesale_price,
            'marketing_code_description': self.marketing_code_description,
            'quantity_unit': self.quantity_unit,
            'sales_pack_size': self.sales_pack_size,
            'weight': self.weight,
            'length': self.length,
            'width': self.width,
            'height': self.height,
            'effective_date': self.effective_date,
            'data_source': self.data_source,
            'l_model_zh': self.l_model_zh,
            'brand': self.brand,
            'category': self.category,
            'ccc_mark': self.ccc_mark,
            'volume': self.volume,
            'hazmat_code': self.hazmat_code,
            'origin_country': self.origin_country,
            'shelf_life': self.shelf_life,
            'is_hazmat': self.is_hazmat,
            'purchase_price': self.purchase_price,
            'part_nr_info_super_session': self.part_nr_info_super_session,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


    def to_web_dict(self, tax_rate: float = 1.13, discount_rate: float = 0.87):
        """
        单个对象转字典（专门给前端使用）
        :param tax_rate: 税率，默认 1.13
        :param discount_rate: 折扣率，默认 0.87
        :return: 字典形式的对象数据
        """
        wholesale_price = self.wholesale_price
        price_4s_tax_in = None
        price_baborui = None
        
        if wholesale_price is not None:
            # 4s含税进价 = 批发价 * 税率
            price_4s_tax_in = wholesale_price * tax_rate   # pyright: ignore[reportArgumentType, reportCallIssue]
            # 巴博瑞采购价 = 批发价 * 税率 * 折扣
            price_baborui = wholesale_price * tax_rate * discount_rate   # pyright: ignore[reportArgumentType, reportCallIssue]

        return {
            'part_number': self.part_number,
            'descriptions': self.descriptions,
            'description_cn': self.description_cn,
            'marketing_code': self.marketing_code,
            'dealer_discount_group': self.dealer_discount_group,
            'msrp': self.msrp,
            'dealer_fixed_nominal_margin': self.dealer_fixed_nominal_margin,
            'wholesale_price': wholesale_price,
            'marketing_code_description': self.marketing_code_description,
            'quantity_unit': self.quantity_unit,
            'sales_pack_size': self.sales_pack_size,
            'weight': self.weight,
            'length': self.length,
            'width': self.width,
            'height': self.height,
            'effective_date': self.effective_date,
            'data_source': self.data_source,
            'l_model_zh': self.l_model_zh,
            'brand': self.brand,
            'category': self.category,
            'ccc_mark': self.ccc_mark,
            'volume': self.volume,
            'hazmat_code': self.hazmat_code,
            'origin_country': self.origin_country,
            'shelf_life': self.shelf_life,
            'is_hazmat': self.is_hazmat,
            'part_nr_info_super_session': self.part_nr_info_super_session,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            # 新增前端显示的价格字段
            'price_4s_tax_in': price_4s_tax_in,
            'price_baborui': price_baborui,
        }

 