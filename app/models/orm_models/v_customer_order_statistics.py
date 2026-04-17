# -*- coding:utf-8 -*-
# @Time    : 2026/4/15 17:02
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : v_customer_order_statistics.py
# @Software: PyCharm


from sqlalchemy import Column, Integer, String, Numeric, func

from .base_models import BaseModels


# 视图对应的实体类
class CustomerOrderStatistics(BaseModels):
    """
    客户订单统计视图 ORM 模型
    
    对应数据库视图：v_customer_order_statistics
    """
    
    __tablename__ = "v_customer_order_statistics"

    # 主键必须写（视图没有主键，选 customer_id 当主键）
    customer_id = Column(String(50), primary_key=True, comment="客户ID")

    # 统计字段
    order_count = Column(Integer, comment="订单数量")
    total_price_sum = Column(Numeric(20, 2), comment="总金额")
    sfje_sum = Column(Numeric(20, 2), comment="实付金额")
    no_receive_amount_sum = Column(Numeric(20, 2), comment="未收金额")

    # 客户信息字段
    level_id = Column(Integer, comment="等级ID")
    level_name = Column(String(50), comment="等级名称")
    fullname = Column(String(100), comment="客户全称")
    contacts_phone = Column(String(20), comment="联系电话")
    payment_description = Column(String(100), comment="付款描述")
    payment_method = Column(String(50), comment="付款方式")
    real_name = Column(String(50), comment="真实姓名")
    sap_no = Column(String(50), comment="SAP编号")
    street = Column(String(255), comment="地址")

    @classmethod
    def get_by_customer_id(cls, session, customer_id):
        """
        根据 customer_id 获取客户订单统计信息
        
        :param session: SQLAlchemy Session 对象
        :param customer_id: 客户 ID
        :return: CustomerOrderStatistics 对象或 None
        """
        return session.query(cls).filter_by(customer_id=customer_id).first()

    @classmethod
    def get_by_sap_no(cls, session, sap_no):
        """
        根据 sap_no 获取客户订单统计信息
        
        :param session: SQLAlchemy Session 对象
        :param sap_no: SAP编号
        :return: CustomerOrderStatistics 对象或 None
        """
        return session.query(cls).filter_by(sap_no=sap_no).first()

    @classmethod
    def get_by_fullname(cls, session, fullname):
        """
        根据 fullname 获取客户订单统计信息列表
        
        :param session: SQLAlchemy Session 对象
        :param fullname: 客户全称
        :return: CustomerOrderStatistics 对象列表
        """
        return session.query(cls).filter_by(fullname=fullname).all()


    @classmethod
    def get_paged(
            cls,
            session,
            page: int = 1,
            limit: int = 20,
            # 改为支持 字符串 / 列表，兼容单字段+多字段
            order_by: str | list = "order_count",
            # 支持 布尔 / 列表，对应每个字段的排序方式
            desc: bool | list = True,
            **filters,
    ):
        """
        通用分页查询方法（支持过滤、排序、分页）
        适用于SQLAlchemy ORM模型，返回分页数据 + 总记录数

        :param session: SQLAlchemy 数据库会话
        :param page: 页码，默认1（必须≥1）
        :param limit: 每页条数，默认20（范围1~100，防止超大查询）
        :param order_by: 排序字段名（字符串），默认 order_count
        :param desc: 是否降序，True=降序，False=升序
        :param filters: 动态过滤条件，key=模型字段名，value=过滤值
        :return: (当前页数据列表, 总记录数)
        """
        # ===================== 1. 核心参数校验（防止非法分页）=====================
        # 页码最小为1
        page = max(1, page)
        # 限制每页条数（1~100，避免全表扫描/内存溢出）
        limit = max(1, min(limit, 100))

        # ===================== 2. 构建基础查询 =====================
        query = session.query(cls)



        # ===================== 3. 应用动态过滤条件 =====================
        # ===================== 过滤条件（支持：精确 + 模糊 ）=====================
        for key, value in filters.items():
            if value is not None:
                if key.endswith('_like'):
                    column = getattr(cls, key.replace('_like', ''))
                    query = query.filter(column.like(f'%{value}%'))
                else:
                    column = getattr(cls, key)
                    query = query.filter(column == value)

        # ===================== 4. 优化总条数查询（大数据表性能更高）=====================
        # 替代原生 query.count()，效率更高，兼容所有数据库
        total = query.with_entities(func.count(cls.customer_id)).scalar() or 0

        # ===================== 5. 安全排序 =====================
        # ===================== 【核心改造】多字段排序 =====================
        # 统一转成列表（兼容单字段/多字段）
        order_fields = [order_by] if isinstance(order_by, str) else order_by
        order_descs = [desc] if isinstance(desc, bool) else desc

        sorted_flag = False  # 是否成功排序

        # 循环应用所有排序条件
        for i, field in enumerate(order_fields):
            try:
                column = getattr(cls, field)
                # 取对应索引的排序方式，没有则默认降序
                current_desc = order_descs[i] if i < len(order_descs) else True
                query = query.order_by(column.desc() if current_desc else column.asc())
                sorted_flag = True
            except AttributeError:
                # 字段不存在则跳过，保证不报错
                continue

        # 只有在排序完全失败时，才兜底
        if not sorted_flag:
            query = query.order_by(cls.order_count.desc())

        # ===================== 6. 分页执行查询 =====================
        offset = (page - 1) * limit
        results = query.offset(offset).limit(limit).all()

        return results, total


    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<CustomerOrderStatistics customer_id={self.customer_id} fullname={self.fullname}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        Numeric 类型会转换为 float
        
        :return: 包含所有字段的字典
        """
        return {
            "customer_id": self.customer_id,
            "order_count": self.order_count,
            "total_price_sum": float(self.total_price_sum) if self.total_price_sum else None,
            "sfje_sum": float(self.sfje_sum) if self.sfje_sum else None,
            "no_receive_amount_sum": float(self.no_receive_amount_sum) if self.no_receive_amount_sum else None,
            "level_id": self.level_id,
            "level_name": self.level_name,
            "fullname": self.fullname,
            "contacts_phone": self.contacts_phone,
            "payment_description": self.payment_description,
            "payment_method": self.payment_method,
            "real_name": self.real_name,
            "sap_no": self.sap_no,
            "street": self.street,
        }
