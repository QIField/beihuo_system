# -*- coding:utf-8 -*-
# @Time    : 2026/06/15 08:52
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_picking_list.py
# @Software: trae-cn


from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.base_models import BaseModels


class WmsPickingList(BaseModels):
    # """
    # WMS拣货单表 ORM 模型 
    # 对应数据库表：wms_picking_list
    # """
    
    __tablename__ = "wms_picking_list"

    type = Column(Integer, nullable=True, comment="类型")
    is_checkupdate = Column(Integer, nullable=True, comment="是否检查更新")
    orders_id = Column(Integer, nullable=True, comment="订单ID")
    orders_no = Column(String(255), nullable=True, comment="订单编号")
    pono = Column(String(255), primary_key=True, nullable=False, comment="拣货单号")
    rid = Column(String(255), nullable=True, comment="RID")
    frey_no = Column(String(255), nullable=True, comment="Frey单号")
    status = Column(Integer, nullable=True, comment="状态") # 0: 未开始, 1: 正在拣货, 2: 已完成
    partner_sapno = Column(String(255), nullable=True, comment="合作伙伴SAP编号")
    fullname = Column(String(255), nullable=True, comment="全名")
    orderdate = Column(String(255), nullable=True, comment="订单日期")
    name = Column(String(255), nullable=True, comment="名称")
    dhdate = Column(String(255), nullable=True, comment="到货日期")
    jhdate = Column(String(255), nullable=True, comment="拣货日期")
    qty = Column(Integer, nullable=True, comment="数量")
    toqty = Column(Integer, nullable=True, comment="总数量")
    l_name_zh = Column(String(255), nullable=True, comment="商品名称")
    wait_pick_num = Column(Integer, nullable=True, comment="待拣数量")
    already_pick_num = Column(Integer, nullable=True, comment="已拣数量")
    supplier_short_name = Column(String(255), nullable=True, comment="供应商名称")
    data_flag = Column(Integer, nullable=True, default=0, comment="有问题的数据标志")  # 0: 无, 1: 有  默认无
    store = Column(String(255), nullable=True, comment="门店标识")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

  


    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<WmsPickingList pono={self.pono}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "type": self.type,
            "is_checkupdate": self.is_checkupdate,
            "orders_id": self.orders_id,
            "orders_no": self.orders_no,
            "pono": self.pono,
            "rid": self.rid,
            "frey_no": self.frey_no,
            "status": self.status,
            "partner_sapno": self.partner_sapno,
            "fullname": self.fullname,
            "orderdate": self.orderdate,
            "name": self.name,
            "dhdate": self.dhdate,
            "jhdate": self.jhdate,
            "qty": self.qty,
            "toqty": self.toqty,
            "l_name_zh": self.l_name_zh,
            "wait_pick_num": self.wait_pick_num,
            "already_pick_num": self.already_pick_num,
            "supplier_short_name": self.supplier_short_name,
            "data_flag": self.data_flag,
            "store": self.store,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
