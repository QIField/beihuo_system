# -*- coding:utf-8 -*-
# @Time    : 2026/6/9
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : crmapp_beihuo.py
# @Software: PyCharm
# @Description: 备货数据表 ORM 模型


from sqlalchemy import Column, String, Integer, Text, DECIMAL, DateTime, Index
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CrmappBeihuo(BaseModels):
    """
    备货数据表模型
    对应数据库表：crmapp_beihuo
    注意：数据库列名为中文，需在Column第一个参数中显式指定
    """
    __tablename__ = 'crmapp_beihuo'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 基础信息字段（数据库列为中文名）
    oe = Column(String(255), nullable=False, comment='OE号')
    brand = Column('品牌', String(255), nullable=True, comment='品牌')
    brand_number = Column('品牌号', String(255), nullable=True, comment='品牌号')
    material_name = Column('物料名称', String(500), nullable=True, comment='物料名称')
    material_barcode = Column('物料条码', String(255), nullable=True, comment='物料条码')
    car_model_brand = Column('车型品牌', String(255), nullable=True, comment='车型品牌')
    car_model = Column('车型', Text, nullable=True, comment='车型')
    replacement_number = Column('替换号', Text, nullable=True, comment='替换号')
    supplier = Column('供应商', Text, nullable=True, comment='供应商')
    purchase_records = Column('purchase_records', Text, nullable=True, comment='采购记录(JSON格式)')
    tags = Column('标签', String(255), nullable=True, comment='标签')
    internal_remark = Column('内部备注', Text, nullable=True, comment='内部备注')
    company = Column(String(100), nullable=True, comment='公司')  # 英文列名
    warning_status = Column('预警状态', String(255), nullable=True, comment='预警状态')
    # today_sales_str = Column('今日销售', String(255), nullable=True, comment='今日销售')

    # 库存相关字段（数据库列为中文名）
    stock_quantity = Column('库存数量', Integer, default=0, comment='库存数量')
    stock_amount = Column('库存金额', DECIMAL(10, 2), default=0.00, comment='库存金额')
    cost_price = Column('成本价', DECIMAL(10, 2), default=0.00, comment='成本价')
    days_available = Column('成品可卖天数', Integer, default=0, comment='成品可卖天数')
    transit_quantity = Column('在途数量', Integer, default=0, comment='在途数量')

    # 销量统计字段（数据库列为中文名）
    today_sales = Column('今日销量', Integer, default=0, comment='今日销量')
    yesterday_sales = Column('昨日销量', Integer, default=0, comment='昨日销量')
    month_sales = Column('本月销量', Integer, default=0, comment='本月销量')
    recent_7_days_sales = Column('近7天销量', Integer, default=0, comment='近7天销量')
    recent_6_months_sales = Column('近6个月销量', Integer, default=0, comment='近6个月销量')
    recent_6_months_avg_sales = Column('近6个月月均销量', Integer, default=0, comment='近6个月月均销量')
    recent_12_months_sales = Column('近12个月销量', Integer, default=0, comment='近12个月销量')
    recent_12_months_avg_sales = Column('近12个月月均销量', Integer, default=0, comment='近12个月月均销量')

    # 询价量统计字段（数据库列为中文名）
    recent_1_month_inquiry = Column('近1个月询价量', Integer, default=0, comment='近1个月询价量')
    national_recent_1_month_inquiry = Column('全国近1个月询价量', Integer, default=0, comment='全国近1个月询价量')
    recent_3_months_avg_inquiry = Column('近3个月月均询价量', Integer, default=0, comment='近3个月月均询价量')
    national_recent_3_months_avg_inquiry = Column('全国近3个月月均询价量', Integer, default=0, comment='全国近3个月月均询价量')

    # 时间字段（数据库列为中文名）
    updated_at = Column('更新时间', DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 定义索引（与数据库中的索引保持一致，使用数据库实际列名）
    __table_args__ = (
        Index('idx_oe', 'oe'),
        Index('idx_barcode', '物料条码'),
        Index('idx_company', 'company'),
        Index('idx_oe_barcode', 'oe', '物料条码'),
        Index('idx_updated_time', '更新时间'),
        {
            'comment': '备货数据表'
        }
    )

    def to_dict(self):
        """
        将对象转换为字典
        :return: 字典形式的对象数据
        """
        return {
            'id': self.id,
            'oe': self.oe,
            'brand': self.brand,
            'brand_number': self.brand_number,
            'material_name': self.material_name,
            'material_barcode': self.material_barcode,
            'car_model_brand': self.car_model_brand,
            'car_model': self.car_model,
            'replacement_number': self.replacement_number,
            'supplier': self.supplier,
            'purchase_records': self.purchase_records,
            'tags': self.tags,
            'internal_remark': self.internal_remark,
            'company': self.company,
            'warning_status': self.warning_status,
            # 'today_sales_str': self.today_sales_str,
            'stock_quantity': self.stock_quantity,
            'stock_amount': str(self.stock_amount) if self.stock_amount else '0.00',  # pyright: ignore[reportGeneralTypeIssues]
            'cost_price': str(self.cost_price) if self.cost_price else '0.00',  # pyright: ignore[reportGeneralTypeIssues]
            'days_available': self.days_available,
            'transit_quantity': self.transit_quantity,
            'today_sales': self.today_sales,
            'yesterday_sales': self.yesterday_sales,
            'month_sales': self.month_sales,
            'recent_7_days_sales': self.recent_7_days_sales,
            'recent_6_months_sales': self.recent_6_months_sales,
            'recent_6_months_avg_sales': self.recent_6_months_avg_sales,
            'recent_12_months_sales': self.recent_12_months_sales,
            'recent_12_months_avg_sales': self.recent_12_months_avg_sales,
            'recent_1_month_inquiry': self.recent_1_month_inquiry,
            'national_recent_1_month_inquiry': self.national_recent_1_month_inquiry,
            'recent_3_months_avg_inquiry': self.recent_3_months_avg_inquiry,
            'national_recent_3_months_avg_inquiry': self.national_recent_3_months_avg_inquiry,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None  # pyright: ignore[reportGeneralTypeIssues]
        }
