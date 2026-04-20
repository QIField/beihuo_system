# from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
# from app.utils.orm import Base
from .base_models import BaseModels

class WmsOrders(BaseModels):
    """
    订单主表 ORM 模型
    
    对应数据库表：wms_orders
    与旧系统 raw_sql_models.wms_orders_raw 对应同一个表
    但使用 SQLAlchemy ORM 方式操作
    """
    
    # 数据库表名（必须与实际表名一致）
    __tablename__ = "wms_orders"

    # 主键 ID
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    # 订单 ID
    order_id = Column(Integer, nullable=True, comment="订单ID")
    # 订单编号
    order_no = Column(String(255), nullable=True, comment="订单编号")
    # 出库单号
    out_no = Column(String(255), nullable=True, comment="出库单号")
    # 客户名称
    customer = Column(String(255), nullable=True, comment="客户名称")
    # 订单日期
    order_date = Column(String(255), nullable=True, comment="订单日期")
    # 订单状态
    status = Column(String(255), nullable=True, comment="订单状态")
    # 订单金额
    amount = Column(String(255), nullable=True, comment="订单金额")
    # SKU 数量
    sku_count = Column(Float, nullable=True, comment="SKU数量")
    # 总数量
    total_quantity = Column(String(255), nullable=True, comment="总数量")
    # 发货日期
    ship_date = Column(String(255), nullable=True, comment="发货日期")
    # 发货人
    shipper = Column(String(255), nullable=True, comment="发货人")
    # 创建时间
    created_at = Column(DateTime, nullable=True, comment="创建时间")
    # 照片（JSON 或文本格式）
    photos = Column(Text, nullable=True, comment="照片")

    @classmethod
    def get_by_id(cls, session, id_):
        """
        根据 ID 获取订单（ORM 版本）
        
        :param session: SQLAlchemy Session 对象
        :param id_: 订单 ID
        :return: WmsOrders 对象或 None
        """
        return session.query(cls).filter_by(id=id_).first()

    @classmethod
    def get_by_order_no(cls, session, order_no):
        """
        根据订单编号获取订单（ORM 版本）
        
        :param session: SQLAlchemy Session 对象
        :param order_no: 订单编号
        :return: WmsOrders 对象或 None
        """
        return session.query(cls).filter_by(order_no=order_no).first()

    @classmethod
    def get_by_out_nos(cls, session, out_no_list):
        """
        根据 out_no 数组获取多条数据（ORM 版本）
        
        :param session: SQLAlchemy Session 对象
        :param out_no_list: out_no 列表
        :return: WmsOrders 对象列表
        """
        if not out_no_list:
            return []
        return session.query(cls).filter(cls.out_no.in_(out_no_list)).all()

    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<WmsOrders {self.order_no}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "id": self.id,
            "order_id": self.order_id,
            "order_no": self.order_no,
            "out_no": self.out_no,
            "customer": self.customer,
            "order_date": self.order_date,
            "status": self.status,
            "amount": self.amount,
            "sku_count": self.sku_count,
            "total_quantity": self.total_quantity,
            "ship_date": self.ship_date,
            "shipper": self.shipper,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "photos": self.photos,
        }