# -*- coding:utf-8 -*-
# @Time    : 2026/4/13 15:27
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : get_mergeOrderList.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Numeric, text, func
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels
from app.utils.orm.type_decorators import StringToIntType


class MergeOrderList(BaseModels):
    """
    合并订单表 ORM 模型
    
    对应数据库表：merge_order_list
    """
    
    __tablename__ = "merge_order_list"

    # 定义业务类型映射：销售订单=1，退货订单=2
    ORDER_SOURCE_NAME_MAPPING = {
        '销售订单': 1,
        '退货订单': 2
    }

    # 定义订单类型映射（后续可扩展）
    ORDER_TYPE_ID_MAPPING = {
        # 待补充实际的映射关系
    }

    # 定义业务类型映射：外购=1，普通=2，调货=3
    ORDER_SOURCE_NAME_MAPPING = {
        '外购': 1,
        '普通': 2,
        '调货': 3
    }

    orders_id = Column(Integer, primary_key=True, nullable=False, comment="主键ID")
    customer_id = Column(Integer, nullable=True, comment="客户ID")
    partner_id = Column(Integer, nullable=True, comment="合作伙伴ID")
    level_id = Column(Integer, nullable=True, comment="客户等级")
    is_wms = Column(Integer, nullable=True, comment="是否WMS")
    sap_no = Column(String(255), nullable=True, comment="订单号")
    d_sap_no = Column(String(255), nullable=True, comment="金蝶单号")
    fullname = Column(String(255), nullable=True, comment="客户名称")
    customer_phone = Column(String(50), nullable=True, comment="电话")
    sku_num = Column(Integer, nullable=True, comment="SKU数")
    total_quantity = Column(Integer, nullable=True, comment="产品件数")
    realqty = Column(Integer, nullable=True, comment="实发件数")
    total_price = Column(Numeric(10, 2), nullable=True, comment="订单金额")
    sfje = Column(Numeric(10, 2), nullable=True, comment="实发金额")
    no_receive_amount = Column(Numeric(10, 2), nullable=True, comment="未结算金额")
    status = Column(Integer, nullable=True, comment="订单状态")
    order_type_id = Column(StringToIntType(ORDER_TYPE_ID_MAPPING), nullable=True, comment="订单类型")
    order_source_name = Column(StringToIntType(ORDER_SOURCE_NAME_MAPPING), nullable=True, comment="业务类型")
    handler = Column(String(255), nullable=True, comment="经手人")
    create_date = Column(Integer, nullable=True, comment="创建时间（秒级时间戳）")
    user_id = Column(String(255), nullable=True, comment="创建人")
    remark = Column(Text, nullable=True, comment="备注")
    street = Column(String(500), nullable=True, comment="街道地址")
    warehouse = Column(String(255), nullable=True, comment="仓库")
    order_error = Column(Text, nullable=True, comment="订单错误信息")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    @classmethod
    def get_by_orders_id(cls, session, orders_id):
        """
        根据 orders_id 获取订单
        
        :param session: SQLAlchemy Session 对象
        :param orders_id: 订单 ID
        :return: MergeOrderList 对象或 None
        """
        return session.query(cls).filter_by(orders_id=orders_id).first()

    @classmethod
    def get_by_d_sap_no(cls, session, d_sap_no):
        """
        根据 d_sap_no 获取订单
        
        :param session: SQLAlchemy Session 对象
        :param d_sap_no: 金蝶单号
        :return: MergeOrderList 对象或 None
        """
        return session.query(cls).filter_by(d_sap_no=d_sap_no).first()

    @classmethod
    def get_by_customer_id(cls, session, customer_id):
        """
        根据 customer_id 获取订单列表
        
        :param session: SQLAlchemy Session 对象
        :param customer_id: 客户 ID
        :return: MergeOrderList 对象列表
        """
        return session.query(cls).filter_by(customer_id=customer_id).all()





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
        批量插入或更新数据（以 d_sap_no 为唯一索引）
        
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
            if col_name not in ['d_sap_no', 'orders_id', 'created_at']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)

        # 使用 on_duplicate_key_update
        stmt = stmt.on_duplicate_key_update(update_dict)

        # 执行批量插入
        session.execute(stmt)
        
        return len(data_list)

    @classmethod
    def list_to_dict_list(cls, obj_list):
        """
        将对象列表转换为字典列表
        
        支持两种输入类型：
        1. MergeOrderList 模型对象列表
        2. SQLAlchemy Row 对象列表（原生SQL查询结果）
        
        :param obj_list: MergeOrderList 对象列表 或 Row 对象列表
        :return: 字典列表
        """
        if not obj_list:
            return []
        
        result = []
        for obj in obj_list:
            if hasattr(obj, 'to_dict'):
                # 是模型对象，调用 to_dict 方法
                result.append(obj.to_dict())
            else:
                # 是 Row 对象，转换为字典并处理特殊类型
                try:
                    # 尝试使用 _asdict() 方法（适用于 SQLAlchemy 1.4+）
                    row_dict = obj._asdict()
                except AttributeError:
                    # 备用方法：手动构建字典
                    row_dict = {}
                    for key in obj.keys():
                        row_dict[key] = obj[key]
                # 处理 Numeric 类型，转换为 float
                for key, value in row_dict.items():
                    if hasattr(value, 'real') and hasattr(value, 'imag'):
                        # Decimal/Numeric 类型
                        row_dict[key] = float(value)
                result.append(row_dict)
        return result

    @classmethod
    def get_customer_total_price_sum(
            cls,
            session,
            page: int = 1,
            limit: int = 20,
            start_time: int = None,
            end_time: int = None,
            customer_name: str = None,
            level_id: int = None,
            payment_description: str = None,
            total_price_min: float = None,
            total_price_max: float = None
    ):
        """
        仿照通用分页函数 → 订单统计专用分页（执行原生SQL）
        返回：当前页数据列表, 总记录数
        """
        # ===================== 1. 参数校验 =====================
        page = max(1, page)
        limit = max(1, min(limit, 100))
        offset = (page - 1) * limit

        # ===================== 2. 你的统计SQL（带分页占位符） =====================
        sql = text("""
                   SELECT t.customer_id,
                          t.order_count,
                          t.total_price_sum,
                          t.sfje_sum,
                          t.no_receive_amount_sum,
                          p.level_id,
                          p.level_name,
                          p.fullname,
                          p.contacts_phone,
                          p.payment_description,
                          p.payment_method,
                          p.real_name,
                          p.sap_no,
                          p.street
                   FROM (SELECT customer_id,
                                COUNT(*)               AS order_count,
                                SUM(total_price)       AS total_price_sum,
                                SUM(sfje)              AS sfje_sum,
                                SUM(no_receive_amount) AS no_receive_amount_sum
                         FROM merge_order_list m
                         WHERE 1 = 1
                           AND (:start_time IS NULL OR m.create_date >= :start_time)
                           AND (:end_time IS NULL OR m.create_date <= :end_time)
                           AND (:customer_name IS NULL OR m.fullname LIKE :customer_name)
                         GROUP BY customer_id
                         HAVING 1 = 1
                           AND (:total_price_min IS NULL OR SUM(total_price) >= :total_price_min)
                           AND (:total_price_max IS NULL OR SUM(total_price) <= :total_price_max)) t
                            INNER JOIN (
                                SELECT partner_id,
                                       level_id,
                                       level_name,
                                       fullname,
                                       contacts_phone,
                                       payment_description,
                                       payment_method,
                                       real_name,
                                       sap_no,
                                       street
                                FROM partner_list
                                WHERE 1 = 1
                                  AND (:payment_description IS NULL OR payment_description = :payment_description)
                                  AND (:level_id IS NULL OR level_id = :level_id)
                            ) p ON t.customer_id = p.partner_id
                   ORDER BY p.level_id DESC,
                            p.payment_description DESC,
                            t.total_price_sum DESC LIMIT :limit
                   OFFSET :offset
                   """)

        # 统计总数SQL（去掉ORDER BY + LIMIT）
        count_sql = text("""
                         SELECT COUNT(*)
                         FROM (SELECT customer_id
                               FROM merge_order_list m
                               WHERE 1 = 1
                                 AND (:start_time IS NULL OR m.create_date >= :start_time)
                                 AND (:end_time IS NULL OR m.create_date <= :end_time)
                                 AND (:customer_name IS NULL OR m.fullname LIKE :customer_name)
                               GROUP BY customer_id
                               HAVING 1 = 1
                                 AND (:total_price_min IS NULL OR SUM(total_price) >= :total_price_min)
                                 AND (:total_price_max IS NULL OR SUM(total_price) <= :total_price_max)) t
                                    INNER JOIN (
                                        SELECT partner_id,
                                               level_id,
                                               payment_description
                                        FROM partner_list
                                        WHERE  1 = 1
                                          AND (:payment_description IS NULL OR payment_description = :payment_description)
                                          AND (:level_id IS NULL OR level_id = :level_id)
                                    ) p ON t.customer_id = p.partner_id
                         """)

        # ===================== 3. 参数绑定 =====================
        params = {
            "start_time": start_time,
            "end_time": end_time,
            "customer_name": f"%{customer_name}%" if customer_name else None,
            "level_id": level_id,
            "payment_description": payment_description,
            "total_price_min": total_price_min,
            "total_price_max": total_price_max,
            "limit": limit,
            "offset": offset
        }

        # ===================== 4. 查询总数 =====================
        total = session.execute(count_sql, params).scalar() or 0

        # ===================== 5. 查询当前页数据 =====================
        results = session.execute(sql, params).all()

        return total,results









    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<MergeOrderList orders_id={self.orders_id} d_sap_no={self.d_sap_no}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "orders_id": self.orders_id,
            "customer_id": self.customer_id,
            "partner_id" :self.partner_id,
            "level_id": self.level_id,
            "is_wms": self.is_wms,
            "sap_no": self.sap_no,
            "d_sap_no": self.d_sap_no,
            "fullname": self.fullname,
            "customer_phone": self.customer_phone,
            "sku_num": self.sku_num,
            "total_quantity": self.total_quantity,
            "realqty": self.realqty,
            "total_price": float(self.total_price) if self.total_price else None,
            "sfje": float(self.sfje) if self.sfje else None,
            "no_receive_amount": float(self.no_receive_amount) if self.no_receive_amount else None,
            "status": self.status,
            "order_type_id": self.order_type_id,
            "order_source_name": self.order_source_name,
            "handler": self.handler,
            "create_date": self.create_date,
            "user_id": self.user_id,
            "remark": self.remark,
            "street": self.street,
            "warehouse": self.warehouse,
            "order_error": self.order_error,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

