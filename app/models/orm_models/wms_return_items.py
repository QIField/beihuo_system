# -*- coding:utf-8 -*-
# @Time    : 2026/5/5 09:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_return_items.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.dialects.mysql import insert
from .base_models import BaseModels


class WmsReturnItems(BaseModels):
    """
    采购入库单表 ORM 模型

    对应数据库表：wms_return_items
    用于存储采购入库单相关数据
    """

    # 数据库表名（必须与实际表名一致）
    __tablename__ = "wms_return_items"

    # 主键 ID
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    # 品牌代码
    brand_code = Column(String(255), nullable=True, comment="品牌代码")
    # 品牌英文名称
    brand_name_en = Column(String(255), nullable=True, comment="品牌英文名称")
    # 后缀
    suffix = Column(String(255), nullable=True, comment="后缀")
    # 退货数量
    return_qty = Column(String(255), nullable=True, comment="退货数量")
    # 货运单号
    frey_no = Column(String(255), nullable=True, comment="货运单号")
    # 编号
    number = Column(String(255), nullable=True, comment="编号")
    # 数量
    qty = Column(String(255), nullable=True, comment="数量")
    # 库位号
    kw_no = Column(String(255), nullable=True, comment="库位号")
    # 仓库名称
    warehouse_name = Column(String(255), nullable=True, comment="仓库名称")
    # 库存
    kc = Column(String(255), nullable=True, comment="库存")
    # 需求数量
    needqty = Column(Integer, nullable=True, comment="需求数量")
    # 品牌名称
    brandname = Column(String(255), nullable=True, comment="品牌名称")
    # 中文名称
    l_name_zh = Column(String(255), nullable=True, comment="中文名称")
    # 产品备注
    product_remark = Column(String(255), nullable=True, comment="产品备注")
    # 拣货单号
    pono = Column(String(255), nullable=True, comment="拣货单号")
    # 订单编号
    orders_no = Column(String(255), nullable=True, comment="订单编号")
    # 订单ID
    orders_id = Column(String(255), nullable=True, comment="订单ID")
    # 状态
    status = Column(Integer, nullable=True, comment="状态")
    # 类型
    type_param = Column(Integer, nullable=True, comment="类型")
    # 供应商名称
    fullname = Column(String(255), nullable=True, comment="供应商名称")
    # 是否已推送至快手
    has_pushed_ks = Column(Integer, nullable=True, default=0, comment="是否已推送至快手（0:未推送，1:已推送）")
    # 创建时间
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    # 更新时间
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    @classmethod
    def get_by_id(cls, session, id_):
        """
        根据 ID 获取采购入库单记录

        :param session: SQLAlchemy Session 对象
        :param id_: 主键 ID
        :return: WmsReturnItems 对象或 None
        """
        return session.query(cls).filter_by(id=id_).first()

    @classmethod
    def get_by_orders_no(cls, session, orders_no):
        """
        根据订单编号获取采购入库单记录

        :param session: SQLAlchemy Session 对象
        :param orders_no: 订单编号
        :return: WmsReturnItems 对象列表
        """
        return session.query(cls).filter_by(orders_no=orders_no).all()

    @classmethod
    def get_by_pono(cls, session, pono):
        """
        根据拣货单号获取采购入库单记录

        :param session: SQLAlchemy Session 对象
        :param pono: 拣货单号
        :return: WmsReturnItems 对象列表
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
        批量插入或更新数据（以 orders_no 和 number 为唯一索引）

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

        # 构建更新字典：排除不需要更新的列（包括 has_pushed_ks，该字段不允许批量更新）
        update_dict = {}
        for column in cls.__table__.columns:
            col_name = column.name
            if col_name not in ['id', 'created_at', 'has_pushed_ks']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)

        # 使用 on_duplicate_key_update
        stmt = stmt.on_duplicate_key_update(update_dict)

        # 执行批量插入
        session.execute(stmt)

        return len(data_list)

    @classmethod
    def update_all_status(cls, session, status):
        """
        将表中所有记录的 status 字段更新为指定值

        :param session: SQLAlchemy Session 对象
        :param status: 要设置的状态值
        :return: 更新的记录数
        """
        # 使用 SQLAlchemy 的 update 语句
        result = session.query(cls).update({cls.status: status})
        return result

    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<WmsReturnItems {self.orders_no} - {self.number}>"

    def to_dict(self):
        """
        将模型对象转换为字典

        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串

        :return: 包含所有字段的字典
        """
        return {
            "id": self.id,
            "brand_code": self.brand_code,
            "brand_name_en": self.brand_name_en,
            "suffix": self.suffix,
            "return_qty": self.return_qty,
            "frey_no": self.frey_no,
            "number": self.number,
            "qty": self.qty,
            "kw_no": self.kw_no,
            "warehouse_name": self.warehouse_name,
            "kc": self.kc,
            "needqty": self.needqty,
            "brandname": self.brandname,
            "l_name_zh": self.l_name_zh,
            "product_remark": self.product_remark,
            "pono": self.pono,
            "orders_no": self.orders_no,
            "orders_id": self.orders_id,
            "fullname": self.fullname,
            "status": self.status,
            "type_param": self.type_param,
            "has_pushed_ks": self.has_pushed_ks,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
