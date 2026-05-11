# -*- coding:utf-8 -*-
# @Time    : 2026/4/26
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_status_orders.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels


class WmsStatusOrders(BaseModels):
    """
    WMS状态订单表 ORM 模型
    
    对应数据库表：wms_status_orders
    """
    
    __tablename__ = "wms_status_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    type = Column(Integer, nullable=True, comment="类型")
    is_checkupdate = Column(Integer, nullable=True, comment="是否检查更新")
    orders_id = Column(Integer, nullable=True, comment="订单ID")
    orders_no = Column(String(255), nullable=True, comment="订单编号")
    pono = Column(String(255), nullable=True, comment="拣货单号")
    rid = Column(String(255), nullable=True, comment="RID")
    frey_no = Column(String(255), nullable=True, comment="Frey单号")
    status = Column(Integer, nullable=True, comment="状态")
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
    is_data_exists = Column(Integer, nullable=True, comment="数据是否存在")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    @classmethod
    def get_by_id(cls, session, id_):
        """
        根据 ID 获取订单
        
        :param session: SQLAlchemy Session 对象
        :param id_: 订单 ID
        :return: WmsStatusOrders 对象或 None
        """
        return session.query(cls).filter_by(id=id_).first()

    @classmethod
    def get_by_pono(cls, session, pono):
        """
        根据 pono 获取订单
        
        :param session: SQLAlchemy Session 对象
        :param pono: 拣货单号
        :return: WmsStatusOrders 对象或 None
        """
        return session.query(cls).filter_by(pono=pono).first()

    @classmethod
    def get_by_ponos(cls, session, pono_list):
        """
        根据 pono 数组获取多条数据
        
        :param session: SQLAlchemy Session 对象
        :param pono_list: pono 列表
        :return: WmsStatusOrders 对象列表
        """
        if not pono_list:
            return []
        return session.query(cls).filter(cls.pono.in_(pono_list)).all()

    @classmethod
    def bulk_insert(cls, session, data_list):
        """
        批量插入数据
        
        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :return: 插入的记录数
        """
        if not data_list:
            return 0
        
        objects = [cls(**data) for data in data_list]
        session.bulk_save_objects(objects)
        return len(objects)

    @classmethod
    def bulk_upsert(cls, session, data_list):
        """
        批量插入或更新数据（以 pono 为唯一索引）
        
        使用 SQLAlchemy 的 insert ... on_duplicate_key_update 方法
        底层调用 MySQL 的 INSERT ... ON DUPLICATE KEY UPDATE
        一次插入多条数据，性能更优

        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :return: 处理的记录数
        """
        if not data_list:
            return 0

        # 构建插入语句
        stmt = insert(cls).values(data_list)

        # 构建更新字典：排除不需要更新的列
        update_dict = {}
        for column in cls.__table__.columns:
            col_name = column.name
            if col_name not in ['id', 'created_at']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)

        # 使用 on_duplicate_key_update
        stmt = stmt.on_duplicate_key_update(update_dict)

        # 执行批量插入
        session.execute(stmt)
        
        return len(data_list)

    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<WmsStatusOrders pono={self.pono}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "id": self.id,
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
            "is_data_exists": self.is_data_exists,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
