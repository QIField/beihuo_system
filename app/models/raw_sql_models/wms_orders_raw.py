# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 15:57
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_orders_raw.py
# @Software: PyCharm

# app/models/wms_orders.py
from datetime import datetime
from app.utils.database_connection import db_query_one, db_query_all, db_execute


class WmsOrders:
    """
    订单主表模型
    对应数据库表：wms_orders
    字段完全按照SQL语句映射，无修改
    """
    # 数据库表名（必须与原表一致）
    __tablename__ = 'wms_orders'

    def __init__(self, id=None, order_id=None, order_no=None, out_no=None, customer=None,
                 order_date=None, status=None, amount=None, sku_count=None, total_quantity=None,
                 ship_date=None, shipper=None, created_at=None, photos=None):
        self.id = id
        self.order_id = order_id
        self.order_no = order_no
        self.out_no = out_no
        self.customer = customer
        self.order_date = order_date
        self.status = status
        self.amount = amount
        self.sku_count = sku_count
        self.total_quantity = total_quantity
        self.ship_date = ship_date
        self.shipper = shipper
        self.created_at = created_at
        self.photos = photos

    @classmethod
    def get_by_id(cls, order_id):
        """根据ID获取订单"""
        sql = """
              SELECT id, \
                     order_id, \
                     order_no, \
                     out_no, \
                     customer, \
                     order_date, \
                     status,
                     amount, \
                     sku_count, \
                     total_quantity, \
                     ship_date, \
                     shipper, \
                     created_at, \
                     photos
              FROM wms_orders
              WHERE id = %s \
              """
        result = db_query_one(sql, (order_id,))
        if result:
            return cls(
                id=result['id'],
                order_id=result['order_id'],
                order_no=result['order_no'],
                out_no=result['out_no'],
                customer=result['customer'],
                order_date=result['order_date'],
                status=result['status'],
                amount=result['amount'],
                sku_count=result['sku_count'],
                total_quantity=result['total_quantity'],
                ship_date=result['ship_date'],
                shipper=result['shipper'],
                created_at=result['created_at'],
                photos=result['photos']
            )
        return None

    @classmethod
    def get_by_order_no(cls, order_no):
        """根据订单编号获取订单"""
        sql = """
              SELECT id, \
                     order_id, \
                     order_no, \
                     out_no, \
                     customer, \
                     order_date, \
                     status,
                     amount, \
                     sku_count, \
                     total_quantity, \
                     ship_date, \
                     shipper, \
                     created_at, \
                     photos
              FROM wms_orders
              WHERE order_no = %s \
              """
        result = db_query_one(sql, (order_no,))
        if result:
            return cls(
                id=result['id'],
                order_id=result['order_id'],
                order_no=result['order_no'],
                out_no=result['out_no'],
                customer=result['customer'],
                order_date=result['order_date'],
                status=result['status'],
                amount=result['amount'],
                sku_count=result['sku_count'],
                total_quantity=result['total_quantity'],
                ship_date=result['ship_date'],
                shipper=result['shipper'],
                created_at=result['created_at'],
                photos=result['photos']
            )
        return None


    @classmethod
    def get_by_out_nos(cls, out_no_list):
        """根据 out_no 数组获取多条数据"""
        if not out_no_list:
            return []

        # 构建 SQL 查询，使用 IN 子句
        placeholders = ', '.join(['%s'] * len(out_no_list))
        sql = f"""
        SELECT id, order_id, order_no, out_no, customer, order_date, status, 
               amount, sku_count, total_quantity, ship_date, shipper, created_at, photos 
        FROM wms_orders 
        WHERE out_no IN ({placeholders})
        """

        results = db_query_all(sql, out_no_list)
        orders = []
        for result in results:
            orders.append(cls(
                id=result['id'],
                order_id=result['order_id'],
                order_no=result['order_no'],
                out_no=result['out_no'],
                customer=result['customer'],
                order_date=result['order_date'],
                status=result['status'],
                amount=result['amount'],
                sku_count=result['sku_count'],
                total_quantity=result['total_quantity'],
                ship_date=result['ship_date'],
                shipper=result['shipper'],
                created_at=result['created_at'],
                photos=result['photos']
            ))
        return orders


    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<WmsOrders {self.order_no}>"

    def to_dict(self):
        """
        模型转字典，方便接口返回数据
        可根据需求自行增删字段
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
            "photos": self.photos
        }