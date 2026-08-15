

from sqlalchemy import DateTime, Integer, String, Text, Column

from app.models.orm_models.base_models import BaseModels

class SalesOrderHistoryProto(BaseModels):
    """
    销售订单历史原始数据模型
    """


    __tablename__ = "sales_order_history_proto"

    id = Column(Integer, primary_key=True, nullable=False, comment="主键ID")

    ##时间批次ID
    time_batch_id = Column(String(255), nullable=True, comment="时间批次ID")

    ##批次id
    batch_id = Column(String(255), nullable=True, comment="批次ID")


    ##销售订单ID
    sales_order_id = Column(String(255), nullable=True, comment="销售订单ID")
    ##订单商品ID
    orders_items_id = Column(String(255), nullable=True, comment="订单商品ID")

    json_text = Column(Text, nullable=True, comment="原始JSON文本")
    create_time = Column(DateTime, nullable=True, comment="创建时间")
    update_time = Column(DateTime, nullable=True, comment="更新时间")