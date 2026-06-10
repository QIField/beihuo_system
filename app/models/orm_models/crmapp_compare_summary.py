from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, Text
from .base_models import BaseModels


class CrmappCompareSummary(BaseModels):
    """
    CRM APP 比价数据汇总表 ORM 模型
    
    对应数据库表：crmapp_compare_summary
    用途：存储各品牌OE号的比价、销量、替换号等汇总数据
    """
    
    __tablename__ = "crmapp_compare_summary"
    
    # 主键 ID
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    
    # 产品ID
    product_id = Column(String(100), nullable=True, comment="产品ID")
    
    # OE 号（产品编号）
    oe = Column(String(255), nullable=False, comment="OE号")
    
    # 品牌
    brand = Column(String(255), nullable=True, comment="品牌")
    
    # 公司/门店代码
    company = Column(String(100), nullable=True, default="fsbbr", comment="公司/门店代码")
    
    # 产品名称
    product_name = Column(String(500), nullable=True, comment="产品名称")
    
    # 车辆品牌
    vehicle_brand = Column(String(255), nullable=True, comment="车辆品牌")
    
    # 替换号
    replace_number = Column(String(255), nullable=True, comment="替换号")
    
    # 替换号（含key信息，格式key1:num1;key2:num2）
    replace_number_with_keys = Column(String(500), nullable=True, comment="替换号(含key信息，格式key1:num1;key2:num2)")
    
    # 品牌编码
    brand_code = Column(String(255), nullable=True, comment="品牌编码")
    
    # 询价次数
    inquiry_count = Column(Integer, nullable=True, default=0, comment="询价次数")
    
    # 产品等级
    product_level = Column(String(50), nullable=True, comment="产品等级")
    
    # 销量最好的月份
    best_sales_month = Column(String(20), nullable=True, comment="销量最好的月份")
    
    # 销量最好的季节
    best_sales_season = Column(String(20), nullable=True, comment="销量最好的季节")
    
    # 最高价
    max_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="最高价")
    
    # 最低价
    min_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="最低价")
    
    # 供应商价格
    supplier_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="供应商价格")
    
    # 4S含税进价
    dealer_purchase_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="4S含税进价")
    
    # 4S含税售价
    dealer_sale_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="4S含税售价")
    
    # 更新价格时间
    price_update_time = Column(DateTime, nullable=True, comment="更新价格时间")
    
    # 今日销量
    today_sales = Column(Integer, nullable=True, default=0, comment="今日销量")
    
    # 昨日销量
    yesterday_sales = Column(Integer, nullable=True, default=0, comment="昨日销量")
    
    # 本月销量
    month_sales = Column(Integer, nullable=True, default=0, comment="本月销量")
    
    # 近12个月月均销量
    avg_sales_12m = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="近12个月月均销量")
    
    # 近6个月月均销量
    avg_sales_6m = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="近6个月月均销量")
    
    # 近7天销量
    sales_7d = Column(Integer, nullable=True, default=0, comment="近7天销量")
    
    # 近6个月总销量
    sales_6m = Column(Integer, nullable=True, default=0, comment="近6个月总销量")
    
    # 近12个月总销量
    sales_12m = Column(Integer, nullable=True, default=0, comment="近12个月总销量")
    
    # 系统产品备注
    product_remark = Column(Text, nullable=True, comment="系统产品备注")
    
    # 是否同步开思
    is_cass = Column(String(10), nullable=True, comment="是否同步开思")
    
    # 车型中文名
    l_model_zh = Column(Text, nullable=True, comment="车型中文名")
    
    # Frey 编号
    frey_no = Column(String(255), nullable=True, comment="Frey编号")
    
    # 在途库存列表
    stock_zaitu_list = Column(Text, nullable=True, comment="在途库存列表(JSON格式)")
    
    # 公司备注
    company_remark = Column(Text, nullable=True, comment="公司备注")
    
    # 等待时间
    waiting_time = Column(String(50), nullable=True, comment="等待时间")
    
    # QPL价格
    qpl_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="QPL价格")
    
    # 成本价
    cost_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="成本价")
    
    # 存储CASS价格
    store_cass_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="存储CASS价格")
    
    # 创建时间
    created_time = Column(DateTime, nullable=True, comment="创建时间")
    
    # 更新时间
    updated_time = Column(DateTime, nullable=True, comment="更新时间")
    
    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<CrmappCompareSummary {self.oe} - {self.brand}>"
    
    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 和 DECIMAL 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "id": self.id,
            "product_id": self.product_id,
            "oe": self.oe,
            "brand": self.brand,
            "company": self.company,
            "product_name": self.product_name,
            "vehicle_brand": self.vehicle_brand,
            "replace_number": self.replace_number,
            "replace_number_with_keys": self.replace_number_with_keys,
            "brand_code": self.brand_code,
            "inquiry_count": self.inquiry_count,
            "product_level": self.product_level,
            "best_sales_month": self.best_sales_month,
            "best_sales_season": self.best_sales_season,
            "max_price": float(self.max_price) if self.max_price else 0.00,
            "min_price": float(self.min_price) if self.min_price else 0.00,
            "supplier_price": float(self.supplier_price) if self.supplier_price else 0.00,
            "dealer_purchase_price": float(self.dealer_purchase_price) if self.dealer_purchase_price else 0.00,
            "dealer_sale_price": float(self.dealer_sale_price) if self.dealer_sale_price else 0.00,
            "price_update_time": self.price_update_time.strftime("%Y-%m-%d %H:%M:%S") if self.price_update_time else None,
            "today_sales": self.today_sales,
            "yesterday_sales": self.yesterday_sales,
            "month_sales": self.month_sales,
            "avg_sales_12m": float(self.avg_sales_12m) if self.avg_sales_12m else 0.00,
            "avg_sales_6m": float(self.avg_sales_6m) if self.avg_sales_6m else 0.00,
            "sales_7d": self.sales_7d,
            "sales_6m": self.sales_6m,
            "sales_12m": self.sales_12m,
            "product_remark": self.product_remark,
            "is_cass": self.is_cass,
            "l_model_zh": self.l_model_zh,
            "frey_no": self.frey_no,
            "stock_zaitu_list": self.stock_zaitu_list,
            "company_remark": self.company_remark,
            "waiting_time": self.waiting_time,
            "qpl_price": float(self.qpl_price) if self.qpl_price else 0.00,
            "cost_price": float(self.cost_price) if self.cost_price else 0.00,
            "store_cass_price": float(self.store_cass_price) if self.store_cass_price else 0.00,
            "created_time": self.created_time.strftime("%Y-%m-%d %H:%M:%S") if self.created_time else None,
            "updated_time": self.updated_time.strftime("%Y-%m-%d %H:%M:%S") if self.updated_time else None,
        }
    
    @classmethod
    def get_by_oe(cls, session, oe):
        """
        根据 OE 号获取数据列表
        
        :param session: SQLAlchemy Session 对象
        :param oe: OE 号
        :return: CrmappCompareSummary 对象列表
        """
        return session.query(cls).filter_by(oe=oe).all()
    
    @classmethod
    def get_by_oe_and_brand(cls, session, oe, brand):
        """
        根据 OE 号和品牌获取单条数据
        
        :param session: SQLAlchemy Session 对象
        :param oe: OE 号
        :param brand: 品牌
        :return: CrmappCompareSummary 对象或 None
        """
        return session.query(cls).filter_by(oe=oe, brand=brand).first()
