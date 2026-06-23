# -*- coding:utf-8 -*-
# @Time    : 2026/6/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_bmw_stock.py
# @Software: PyCharm
# 华晨宝马零件库表（零件基础信息 + 多仓库库存）
# 对应爬虫接口：query_part_stock（库存查询）
# 数据库设计参考 demo/test 输出
# ===============================================================


from sqlalchemy import Column, String, DateTime
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CarPartsLibraryBmwStock(BaseModels):
    __tablename__ = 'car_parts_library_bmw_stock'

    # ===================== 主键与基础信息 =====================
    part_number = Column(String(510), primary_key=True, comment='配件编号(OE号)')
    part_name = Column(String(510), nullable=True, comment='零件名称')
    discount_code = Column(String(50), nullable=True, comment='折扣代码')
    retail_price = Column(String(50), nullable=True, comment='零售价(爬虫返回的原始含税价格)')
    sales_unit = Column(String(50), nullable=True, comment='销售单位')

    # ===================== 仓库 - 北京 =====================
    warehouse_beijing = Column(String(100), nullable=True, comment='库房-北京')
    in_transit_beijing = Column(String(100), nullable=True, comment='在途-北京')
    reorder_point_beijing = Column(String(100), nullable=True, comment='再定购点-北京')
    main_warehouse_beijing = Column(String(100), nullable=True, comment='主仓-北京')

    # ===================== 仓库 - 上海 =====================
    warehouse_shanghai = Column(String(100), nullable=True, comment='库房-上海')
    in_transit_shanghai = Column(String(100), nullable=True, comment='在途-上海')
    reorder_point_shanghai = Column(String(100), nullable=True, comment='再定购点-上海')
    main_warehouse_shanghai = Column(String(100), nullable=True, comment='主仓-上海')

    # ===================== 仓库 - 佛山 =====================
    warehouse_foshan = Column(String(100), nullable=True, comment='库房-佛山')
    in_transit_foshan = Column(String(100), nullable=True, comment='在途-佛山')
    reorder_point_foshan = Column(String(100), nullable=True, comment='再定购点-佛山')
    main_warehouse_foshan = Column(String(100), nullable=True, comment='主仓-佛山')

    # ===================== 仓库 - 成都 =====================
    warehouse_chengdu = Column(String(100), nullable=True, comment='库房-成都')
    in_transit_chengdu = Column(String(100), nullable=True, comment='在途-成都')
    reorder_point_chengdu = Column(String(100), nullable=True, comment='再定购点-成都')
    main_warehouse_chengdu = Column(String(100), nullable=True, comment='主仓-成都')

    # ===================== 仓库 - 沈阳 =====================
    warehouse_shenyang = Column(String(100), nullable=True, comment='库房-沈阳')
    in_transit_shenyang = Column(String(100), nullable=True, comment='在途-沈阳')
    reorder_point_shenyang = Column(String(100), nullable=True, comment='再定购点-沈阳')
    main_warehouse_shenyang = Column(String(100), nullable=True, comment='主仓-沈阳')

    # ===================== 仓库 - 合肥 =====================
    warehouse_hefei = Column(String(100), nullable=True, comment='库房-合肥')
    in_transit_hefei = Column(String(100), nullable=True, comment='在途-合肥')
    reorder_point_hefei = Column(String(100), nullable=True, comment='再定购点-合肥')
    main_warehouse_hefei = Column(String(100), nullable=True, comment='主仓-合肥')

    # ===================== 仓库 - 宁波 =====================
    warehouse_ningbo = Column(String(100), nullable=True, comment='库房-宁波')
    in_transit_ningbo = Column(String(100), nullable=True, comment='在途-宁波')
    reorder_point_ningbo = Column(String(100), nullable=True, comment='再定购点-宁波')
    main_warehouse_ningbo = Column(String(100), nullable=True, comment='主仓-宁波')

    # ===================== 时间字段 =====================
    data_collect_time = Column(String(50), nullable=True, comment='采集时间(原始字符串)')
    # ===================== 数据来源 =====================
    data_source = Column(String(50), nullable=True, comment='数据来源')
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
            'discount_code': self.discount_code,
            'retail_price': self.retail_price,
            'sales_unit': self.sales_unit,
            'warehouse_beijing': self.warehouse_beijing,
            'in_transit_beijing': self.in_transit_beijing,
            'reorder_point_beijing': self.reorder_point_beijing,
            'main_warehouse_beijing': self.main_warehouse_beijing,
            'warehouse_shanghai': self.warehouse_shanghai,
            'in_transit_shanghai': self.in_transit_shanghai,
            'reorder_point_shanghai': self.reorder_point_shanghai,
            'main_warehouse_shanghai': self.main_warehouse_shanghai,
            'warehouse_foshan': self.warehouse_foshan,
            'in_transit_foshan': self.in_transit_foshan,
            'reorder_point_foshan': self.reorder_point_foshan,
            'main_warehouse_foshan': self.main_warehouse_foshan,
            'warehouse_chengdu': self.warehouse_chengdu,
            'in_transit_chengdu': self.in_transit_chengdu,
            'reorder_point_chengdu': self.reorder_point_chengdu,
            'main_warehouse_chengdu': self.main_warehouse_chengdu,
            'warehouse_shenyang': self.warehouse_shenyang,
            'in_transit_shenyang': self.in_transit_shenyang,
            'reorder_point_shenyang': self.reorder_point_shenyang,
            'main_warehouse_shenyang': self.main_warehouse_shenyang,
            'warehouse_hefei': self.warehouse_hefei,
            'in_transit_hefei': self.in_transit_hefei,
            'reorder_point_hefei': self.reorder_point_hefei,
            'main_warehouse_hefei': self.main_warehouse_hefei,
            'warehouse_ningbo': self.warehouse_ningbo,
            'in_transit_ningbo': self.in_transit_ningbo,
            'reorder_point_ningbo': self.reorder_point_ningbo,
            'main_warehouse_ningbo': self.main_warehouse_ningbo,
            'data_collect_time': self.data_collect_time,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

