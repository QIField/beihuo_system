# -*- coding:utf-8 -*-
# @Time    : 2026/5/5 08:53
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_status_orders_type.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, UniqueConstraint
from sqlalchemy.dialects.mysql import insert
from .base_models import BaseModels


class WmsStatusOrdersType(BaseModels):
    """
    订单状态类型表 ORM 模型

    对应数据库表：wms_status_orders_type
    用于存储订单状态相关数据
    """

    # 数据库表名（必须与实际表名一致）
    __tablename__ = "wms_status_orders_type"

    # 唯一索引：pono
    __table_args__ = (
        UniqueConstraint('pono', name='idx_pono'),
    )

    # 主键 ID
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    # 类型
    type = Column(String(255), nullable=True, comment="类型")
    # 是否检查更新
    is_checkupdate = Column(String(255), nullable=True, comment="是否检查更新")
    # 订单ID
    orders_id = Column(Integer, nullable=True, comment="订单ID")
    # 订单编号
    orders_no = Column(String(255), nullable=True, comment="订单编号")
    # 拣货单号
    pono = Column(String(255), nullable=True, comment="拣货单号")
    # 关系ID
    rid = Column(String(255), nullable=True, comment="关系ID")
    # 货运单号
    frey_no = Column(String(255), nullable=True, comment="货运单号")
    # 状态
    status = Column(String(255), nullable=True, comment="状态")
    # 合作伙伴SAP编号
    partner_sapno = Column(String(255), nullable=True, comment="合作伙伴SAP编号")
    # 全名
    fullname = Column(String(255), nullable=True, comment="全名")
    # 订单日期
    orderdate = Column(String(255), nullable=True, comment="订单日期")
    # 名称
    name = Column(String(255), nullable=True, comment="名称")
    # 到货日期
    dhdate = Column(String(255), nullable=True, comment="到货日期")
    # 计划日期
    jhdate = Column(String(255), nullable=True, comment="计划日期")
    # 打印时间
    printtime = Column(String(255), nullable=True, comment="打印时间")
    # 公司名称
    companyname = Column(String(255), nullable=True, comment="公司名称")
    # 数量
    qty = Column(Integer, nullable=True, comment="数量")
    # 总数量
    toqty = Column(Integer, nullable=True, comment="总数量")
    # 中文名称
    l_name_zh = Column(String(255), nullable=True, comment="中文名称")
    # 产品ID
    product_id = Column(String(255), nullable=True, comment="产品ID")
    # 订单来源类型
    order_source_type = Column(String(255), nullable=True, comment="订单来源类型")
    # 供应商简称
    supplier_short_name = Column(String(255), nullable=True, comment="供应商简称")
    # 待拣数量
    wait_pick_num = Column(Integer, nullable=True, comment="待拣数量")
    # 已拣数量
    already_pick_num = Column(Integer, nullable=True, comment="已拣数量")
    # 发货状态
    delivery_status = Column(String(255), nullable=True, comment="发货状态")
    # 是否转运订单
    is_transfer_order = Column(String(255), nullable=True, comment="是否转运订单")
    # 创建时间
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    # 更新时间
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    @classmethod
    def get_by_id(cls, session, id_):
        """
        根据 ID 获取订单状态记录

        :param session: SQLAlchemy Session 对象
        :param id_: 主键 ID
        :return: WmsStatusOrdersType 对象或 None
        """
        return session.query(cls).filter_by(id=id_).first()

    @classmethod
    def get_by_orders_no(cls, session, orders_no):
        """
        根据订单编号获取订单状态记录

        :param session: SQLAlchemy Session 对象
        :param orders_no: 订单编号
        :return: WmsStatusOrdersType 对象或 None
        """
        return session.query(cls).filter_by(orders_no=orders_no).first()

    @classmethod
    def get_by_pono(cls, session, pono):
        """
        根据拣货单号获取订单状态记录

        :param session: SQLAlchemy Session 对象
        :param pono: 拣货单号
        :return: WmsStatusOrdersType 对象列表
        """
        return session.query(cls).filter_by(pono=pono).all()

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
            if col_name not in ['id', 'created_at', 'pono']:
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
        return f"<WmsStatusOrdersType {self.orders_no}>"

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
            "printtime": self.printtime,
            "companyname": self.companyname,
            "qty": self.qty,
            "toqty": self.toqty,
            "l_name_zh": self.l_name_zh,
            "product_id": self.product_id,
            "order_source_type": self.order_source_type,
            "supplier_short_name": self.supplier_short_name,
            "wait_pick_num": self.wait_pick_num,
            "already_pick_num": self.already_pick_num,
            "delivery_status": self.delivery_status,
            "is_transfer_order": self.is_transfer_order,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
