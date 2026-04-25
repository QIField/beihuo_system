# -*- coding:utf-8 -*-
# @Time    : 2026/4/23 09:06
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : account_receivable_list.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Numeric, text
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels


class AccountReceivableList(BaseModels):
    """
    应收单列表 ORM 模型
    
    对应数据库表：account_receivable_list
    """
    
    __tablename__ = "account_receivable_list"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    receipt_no = Column(String(255), nullable=True, comment="单据编号")
    receipt_status = Column(String(50), nullable=True, comment="单据状态")
    customer_name = Column(String(255), nullable=True, comment="客户")
    tax_total_amount = Column(Numeric(10, 2), nullable=True, comment="价税合计")
    total_amount = Column(Numeric(10, 2), nullable=True, comment="总金额")
    received_amount = Column(Numeric(10, 2), nullable=True, comment="已收款金额")
    customer_code = Column(String(255), nullable=True, comment="客户编码")
    partner_id = Column(Integer, nullable=True, comment="合作伙伴ID（数据回填专用）")
    business_date = Column(String(50), nullable=True, comment="业务日期")
    due_date = Column(String(50), nullable=True, comment="到期日")
    payment_terms = Column(String(255), nullable=True, comment="收款条件")
    payment_org = Column(String(255), nullable=True, comment="收款组织")
    salesperson = Column(String(255), nullable=True, comment="销售员")
    remark = Column(Text, nullable=True, comment="备注")
    customer_group = Column(String(255), nullable=True, comment="客户分组")
    creator = Column(String(255), nullable=True, comment="创建人")
    create_date = Column(String(50), nullable=True, comment="创建日期")
    payment_type = Column(String(255), nullable=True, comment="支付类型")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    @classmethod
    def get_by_receipt_no(cls, session, receipt_no):
        """
        根据 receipt_no 获取应收单
        
        :param session: SQLAlchemy Session 对象
        :param receipt_no: 单据编号
        :return: AccountReceivableList 对象或 None
        """
        return session.query(cls).filter_by(receipt_no=receipt_no).first()

    @classmethod
    def get_by_customer_name(cls, session, customer_name):
        """
        根据 customer_name 获取应收单列表
        
        :param session: SQLAlchemy Session 对象
        :param customer_name: 客户名称
        :return: AccountReceivableList 对象列表
        """
        return session.query(cls).filter_by(customer_name=customer_name).all()

    @classmethod
    def get_by_customer_code(cls, session, customer_code):
        """
        根据 customer_code 获取应收单列表
        
        :param session: SQLAlchemy Session 对象
        :param customer_code: 客户编码
        :return: AccountReceivableList 对象列表
        """
        return session.query(cls).filter_by(customer_code=customer_code).all()
    
    @classmethod
    def get_paginated_by_customer_code(cls, session, customer_code, page=1, limit=20, payment_status=None):
        """
        根据 customer_code 分页获取应收单列表
        
        :param session: SQLAlchemy Session 对象
        :param customer_code: 客户编码
        :param page: 页码
        :param limit: 每页条数
        :param payment_status: 付款状态：'unpaid' 未结清，'paid' 已结清，None 全部
        :return: {total: 总数, result: 数据列表}
        """
        # 构建查询
        query = session.query(cls).filter_by(customer_code=customer_code)
        
        # 添加付款状态筛选
        if payment_status == 'paid':
            # 已结清：tax_total_amount <= received_amount
            query = query.filter(cls.tax_total_amount <= cls.received_amount)
        elif payment_status == 'unpaid':
            # 未结清：tax_total_amount > received_amount
            query = query.filter(cls.tax_total_amount > cls.received_amount)
        
        # 统计总数
        total = query.count()
        
        # 分页查询，按到期日从早到晚排序
        offset = (page - 1) * limit
        result = query.order_by(cls.due_date.asc()).limit(limit).offset(offset).all()
        
        # 转换为字典列表
        dict_list = []
        for item in result:
            dict_list.append(item.to_dict())
        
        return {
            'total': total,
            'result': dict_list
        }

    @classmethod
    def get_paginated_list(cls, session, page=1, limit=20, receipt_no=None, customer_name=None):
        """
        分页查询应收单列表
        
        :param session: SQLAlchemy Session 对象
        :param page: 页码
        :param limit: 每页条数
        :param receipt_no: 单据编号（可选）
        :param customer_name: 客户名称（可选，模糊查询）
        :return: (total: 总数, result: 数据列表)
        """
        # 构建查询
        query = session.query(cls)
        
        # 添加查询条件
        if receipt_no:
            query = query.filter(cls.receipt_no.like(f"%{receipt_no}%"))
        
        if customer_name:
            query = query.filter(cls.customer_name.like(f"%{customer_name}%"))
        
        # 统计总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * limit
        items = query.order_by(cls.id.desc()).limit(limit).offset(offset).all()
        
        return total, items

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
        批量插入或更新数据（以 receipt_no 为唯一索引）
        
        使用 SQLAlchemy 的 insert ... on_duplicate_key_update 方法
        底层调用 MySQL 的 INSERT ... ON DUPLICATE KEY UPDATE
        一次插入多条数据，性能更优

        注意：此方法不会更新 partner_id 字段，partner_id 只能通过专门的回填方法更新

        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :return: 处理的记录数
        """
        if not data_list:
            return 0

        # 构建插入语句
        stmt = insert(cls).values(data_list)

        # 构建更新字典：排除不需要更新的列，特别是 partner_id
        update_dict = {}
        for column in cls.__table__.columns:
            col_name = column.name
            if col_name not in ['id', 'created_at', 'partner_id']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)

        # 使用 on_duplicate_key_update
        stmt = stmt.on_duplicate_key_update(update_dict)

        # 执行批量插入
        session.execute(stmt)
        
        return len(data_list)

    @classmethod
    def backfill_partner_id(cls, session):
        """
        数据回填 partner_id
        
        通过 account_receivable_list.customer_code = partner_list.remenber_code
        连表查询，将 partner_list.partner_id 回填到 account_receivable_list.partner_id
        
        :param session: SQLAlchemy Session 对象
        :return: 回填成功的记录数
        """
        # 构建更新 SQL
        update_sql = text("""
            UPDATE account_receivable_list ar
            INNER JOIN partner_list p ON ar.customer_code = p.remenber_code
            SET ar.partner_id = p.partner_id,
                ar.updated_at = NOW()
            WHERE ar.customer_code IS NOT NULL 
              AND p.remenber_code IS NOT NULL
              AND (ar.partner_id IS NULL OR ar.partner_id != p.partner_id)
        """)
        
        # 执行更新
        result = session.execute(update_sql)
        
        # 获取影响的行数
        affected_rows = result.rowcount
        
        print(f"数据回填完成，共更新 {affected_rows} 条记录的 partner_id")
        
        return affected_rows

    @classmethod
    def get_unbackfilled_count(cls, session):
        """
        获取尚未回填 partner_id 的记录数
        
        :param session: SQLAlchemy Session 对象
        :return: 未回填的记录数
        """
        count_sql = text("""
            SELECT COUNT(*) 
            FROM account_receivable_list 
            WHERE partner_id IS NULL 
              AND customer_code IS NOT NULL
        """)
        
        result = session.execute(count_sql)
        count = result.scalar() or 0
        
        return count


    @classmethod
    def get_unpaid_customers(cls, session, page=1, limit=20, customer_name=None, level_name=None, payment_description=None):
        """
        查询一：以 customer_code 分组，查看有多少客户没有给够钱
        条件：(tax_total_amount - received_amount) > 0
        
        :param session: SQLAlchemy Session 对象
        :param page: 页码
        :param limit: 每页条数
        :param customer_name: 客户名称模糊查询
        :param level_name: 客户等级筛选
        :param payment_description: 付款说明筛选
        :return: {total: 总数, result: 客户列表}
        """
        # 构建account_receivable_list的WHERE条件
        ar_where_conditions = ["ar.customer_code IS NOT NULL"]
        params = {}
        
        if customer_name and customer_name.strip():
            ar_where_conditions.append("ar.customer_name LIKE :customer_name")
            params['customer_name'] = f"%{customer_name.strip()}%"
        
        ar_where_clause = " AND ".join(ar_where_conditions)
        
        # 构建partner_list的WHERE条件
        p_where_conditions = []
        
        if level_name and level_name.strip():
            p_where_conditions.append("p.level_name = :level_name")
            params['level_name'] = level_name.strip()
        
        if payment_description and payment_description.strip():
            p_where_conditions.append("p.payment_description = :payment_description")
            params['payment_description'] = payment_description.strip()
        
        p_where_clause = " AND ".join(p_where_conditions)
        if p_where_clause:
            p_where_clause = " AND " + p_where_clause
        
        # 查询总数
        count_sql = text(f"""
            SELECT COUNT(*) FROM (
                SELECT 1
                FROM (
                    SELECT 
                        customer_code,
                        customer_name,
                        partner_id
                    FROM account_receivable_list ar
                    WHERE {ar_where_clause}
                    GROUP BY customer_code, customer_name, partner_id
                    HAVING ABS(SUM(tax_total_amount) - SUM(received_amount)) > 0
                ) AS sub
                INNER JOIN partner_list p ON sub.partner_id = p.partner_id
                WHERE 1=1{p_where_clause}
            ) AS t
        """)
        
        count_result = session.execute(count_sql, params)
        total = count_result.scalar() or 0
        
        # 计算分页偏移
        offset = (page - 1) * limit
        
        # 查询数据
        data_sql = text(f"""
            SELECT 
                sub.customer_code,
                sub.customer_name,
                sub.total_tax_amount,
                sub.total_received_amount,
                sub.unpaid_amount,
                p.level_name,
                p.payment_description
            FROM (
                SELECT 
                    customer_code,
                    customer_name,
                    partner_id,
                    SUM(tax_total_amount) AS total_tax_amount,
                    SUM(received_amount) AS total_received_amount,
                    (SUM(tax_total_amount) - SUM(received_amount)) AS unpaid_amount
                FROM account_receivable_list ar
                WHERE {ar_where_clause}
                GROUP BY customer_code, customer_name, partner_id
                HAVING ABS(SUM(tax_total_amount) - SUM(received_amount)) > 0
            ) AS sub
            INNER JOIN partner_list p ON sub.partner_id = p.partner_id
            WHERE 1=1{p_where_clause}
            ORDER BY ABS(sub.unpaid_amount) DESC
            LIMIT :limit OFFSET :offset
        """)
        
        params['limit'] = limit
        params['offset'] = offset
        
        result = session.execute(data_sql, params)
        rows = result.fetchall()
        
        # 转换为字典列表
        customer_list = []
        for row in rows:
            customer_list.append({
                'customer_code': row[0],
                'customer_name': row[1],
                'total_tax_amount': float(row[2]) if row[2] else 0,
                'total_received_amount': float(row[3]) if row[3] else 0,
                'unpaid_amount': float(row[4]) if row[4] else 0,
                'level_name': row[5],
                'payment_description': row[6]
            })
        
        return {
            'total': total,
            'result': customer_list
        }


    @classmethod
    def get_overdue_unpaid_customers(cls, session, page=1, limit=20, customer_name=None, level_name=None, payment_description=None, today=None):
        """
        查询二：以今天为准，查看到期日过了，且没有给够钱的顾客数据（按客户分组）
        条件：due_date < 今天 AND (tax_total_amount - received_amount) > 0
        
        :param session: SQLAlchemy Session 对象
        :param page: 页码
        :param limit: 每页条数
        :param customer_name: 客户名称模糊查询
        :param level_name: 客户等级筛选
        :param payment_description: 付款说明筛选
        :param today: 今天的日期（字符串格式）
        :return: {total: 总数, result: 客户列表}
        """
        # 构建account_receivable_list的WHERE条件
        ar_where_conditions = [
            "ar.customer_code IS NOT NULL",
            "ar.due_date IS NOT NULL",
            "STR_TO_DATE(ar.due_date, '%Y/%m/%d') < STR_TO_DATE(:today, '%Y-%m-%d')"
        ]
        params = {'today': today}
        
        if customer_name and customer_name.strip():
            ar_where_conditions.append("ar.customer_name LIKE :customer_name")
            params['customer_name'] = f"%{customer_name.strip()}%"
        
        ar_where_clause = " AND ".join(ar_where_conditions)
        
        # 构建partner_list的WHERE条件
        p_where_conditions = []
        
        if level_name and level_name.strip():
            p_where_conditions.append("p.level_name = :level_name")
            params['level_name'] = level_name.strip()
        
        if payment_description and payment_description.strip():
            p_where_conditions.append("p.payment_description = :payment_description")
            params['payment_description'] = payment_description.strip()
        
        p_where_clause = " AND ".join(p_where_conditions)
        if p_where_clause:
            p_where_clause = " AND " + p_where_clause
        
        # 查询总数
        count_sql = text(f"""
            SELECT COUNT(*) FROM (
                SELECT 1
                FROM (
                    SELECT 
                        ar.customer_code,
                        ar.customer_name,
                        ar.partner_id
                    FROM account_receivable_list ar
                    WHERE {ar_where_clause}
                    GROUP BY ar.customer_code, ar.customer_name, ar.partner_id
                    HAVING ABS(SUM(ar.tax_total_amount) - SUM(ar.received_amount)) > 0
                ) AS sub
                INNER JOIN partner_list p ON sub.partner_id = p.partner_id
                WHERE 1=1 {p_where_clause}
            ) AS t
        """)
        
        count_result = session.execute(count_sql, params)
        total = count_result.scalar() or 0
        
        # 计算分页偏移
        offset = (page - 1) * limit
        
        # 查询数据（按客户分组）
        data_sql = text(f"""
            SELECT 
                sub.customer_code,
                sub.customer_name,
                sub.total_tax_amount,
                sub.total_received_amount,
                sub.unpaid_amount,
                p.level_name,
                p.payment_description
            FROM (
                SELECT 
                    ar.customer_code,
                    ar.customer_name,
                    ar.partner_id,
                    SUM(ar.tax_total_amount) AS total_tax_amount,
                    SUM(ar.received_amount) AS total_received_amount,
                    (SUM(ar.tax_total_amount) - SUM(ar.received_amount)) AS unpaid_amount
                FROM account_receivable_list ar
                WHERE {ar_where_clause}
                GROUP BY ar.customer_code, ar.customer_name, ar.partner_id
                HAVING ABS(SUM(ar.tax_total_amount) - SUM(ar.received_amount)) > 0
            ) AS sub
            INNER JOIN partner_list p ON sub.partner_id = p.partner_id
            WHERE 1=1 {p_where_clause}
            ORDER BY ABS(sub.unpaid_amount) DESC
            LIMIT :limit OFFSET :offset
        """)
        
        params['limit'] = limit
        params['offset'] = offset
        
        result = session.execute(data_sql, params)
        rows = result.fetchall()
        
        # 转换为字典列表
        customer_list = []
        for row in rows:
            customer_list.append({
                'customer_code': row[0],
                'customer_name': row[1],
                'total_tax_amount': float(row[2]) if row[2] else 0,
                'total_received_amount': float(row[3]) if row[3] else 0,
                'unpaid_amount': float(row[4]) if row[4] else 0,
                'level_name': row[5],
                'payment_description': row[6]
            })
        
        return {
            'total': total,
            'result': customer_list
        }

    @classmethod
    def get_overdue_unpaid_customers_with_quota(cls, session, page=1, limit=20, customer_name=None, level_name=None, payment_description=None, quota_status=None, today=None):
        """
        查询：以今天为准，查看到期日过了，且没有给够钱的顾客数据，并关联客户授信总额度
        条件：due_date < 今天 AND (tax_total_amount - received_amount) > 0
        
        :param session: SQLAlchemy Session 对象
        :param page: 页码
        :param limit: 每页条数
        :param customer_name: 客户名称模糊查询
        :param level_name: 客户等级筛选
        :param payment_description: 付款说明筛选
        :param quota_status: 授信额度状态筛选：exhausted-已用尽，available-未用尽
        :param today: 今天的日期（字符串格式）
        :return: {total: 总数, result: 客户列表}
        """
        # 构建account_receivable_list的WHERE条件
        ar_where_conditions = [
            "ar.customer_code IS NOT NULL",
            "ar.due_date IS NOT NULL",
            "STR_TO_DATE(ar.due_date, '%Y/%m/%d') < STR_TO_DATE(:today, '%Y-%m-%d')"
        ]
        params = {'today': today}
        
        if customer_name and customer_name.strip():
            ar_where_conditions.append("ar.customer_name LIKE :customer_name")
            params['customer_name'] = f"%{customer_name.strip()}%"
        
        ar_where_clause = " AND ".join(ar_where_conditions)
        
        # 构建partner_list的WHERE条件
        p_where_conditions = []
        
        if level_name and level_name.strip():
            p_where_conditions.append("p.level_name = :level_name")
            params['level_name'] = level_name.strip()
        
        if payment_description and payment_description.strip():
            p_where_conditions.append("p.payment_description = :payment_description")
            params['payment_description'] = payment_description.strip()
        
        p_where_clause = " AND ".join(p_where_conditions)
        if p_where_clause:
            p_where_clause = " AND " + p_where_clause
        
        # 构建授信额度状态的HAVING条件
        having_conditions = ["ABS(SUM(ar.tax_total_amount) - SUM(ar.received_amount)) > 0"]
        
        # 查询总数
        count_sql = text(f"""
            SELECT COUNT(*) FROM (
                SELECT 1
                FROM (
                    SELECT 
                        ar.customer_code,
                        ar.customer_name,
                        ar.partner_id,
                        SUM(ar.tax_total_amount) AS total_tax_amount,
                        SUM(ar.received_amount) AS total_received_amount,
                        (SUM(ar.tax_total_amount) - SUM(ar.received_amount)) AS unpaid_amount
                    FROM account_receivable_list ar
                    WHERE {ar_where_clause}
                    GROUP BY ar.customer_code, ar.customer_name, ar.partner_id
                    HAVING { " AND ".join(having_conditions) }
                ) AS sub
                INNER JOIN partner_list p ON sub.partner_id = p.partner_id
                LEFT JOIN customer_quota cq ON sub.partner_id = cq.partner_id AND cq.is_deleted = 0
                WHERE 1=1 {p_where_clause}
                { " AND (cq.credit_quota - sub.unpaid_amount) <= 0" if quota_status == 'exhausted' else "" }
                { " AND (cq.credit_quota - sub.unpaid_amount) > 0" if quota_status == 'available' else "" }
            ) AS t
        """)
        
        count_result = session.execute(count_sql, params)
        total = count_result.scalar() or 0
        
        # 计算分页偏移
        offset = (page - 1) * limit
        
        # 查询数据（按客户分组，并关联customer_quota表获取授信额度）
        data_sql = text(f"""
            SELECT 
                sub.customer_code,
                sub.customer_name,
                sub.total_tax_amount,
                sub.total_received_amount,
                sub.unpaid_amount,
                p.level_name,
                p.payment_description,
                COALESCE(cq.credit_quota, 0) AS credit_quota
            FROM (
                SELECT 
                    ar.customer_code,
                    ar.customer_name,
                    ar.partner_id,
                    SUM(ar.tax_total_amount) AS total_tax_amount,
                    SUM(ar.received_amount) AS total_received_amount,
                    (SUM(ar.tax_total_amount) - SUM(ar.received_amount)) AS unpaid_amount
                FROM account_receivable_list ar
                WHERE {ar_where_clause}
                GROUP BY ar.customer_code, ar.customer_name, ar.partner_id
                HAVING { " AND ".join(having_conditions) }
            ) AS sub
            INNER JOIN partner_list p ON sub.partner_id = p.partner_id
            LEFT JOIN customer_quota cq ON sub.partner_id = cq.partner_id AND cq.is_deleted = 0
            WHERE 1=1 {p_where_clause}
            { " AND (cq.credit_quota - sub.unpaid_amount) <= 0" if quota_status == 'exhausted' else "" }
            { " AND (cq.credit_quota - sub.unpaid_amount) > 0" if quota_status == 'available' else "" }
            ORDER BY ABS(sub.unpaid_amount) DESC
            LIMIT :limit OFFSET :offset
        """)
        
        params['limit'] = limit
        params['offset'] = offset
        
        result = session.execute(data_sql, params)
        rows = result.fetchall()
        
        # 转换为字典列表
        customer_list = []
        for row in rows:
            customer_list.append({
                'customer_code': row[0],
                'customer_name': row[1],
                'total_tax_amount': float(row[2]) if row[2] else 0,
                'total_received_amount': float(row[3]) if row[3] else 0,
                'unpaid_amount': float(row[4]) if row[4] else 0,
                'level_name': row[5],
                'payment_description': row[6],
                'credit_quota': float(row[7]) if row[7] else 0.00
            })
        
        return {
            'total': total,
            'result': customer_list
        }

    @classmethod
    def list_to_dict_list(cls, obj_list):
        """
        将对象列表转换为字典列表
        
        支持两种输入类型：
        1. AccountReceivableList 模型对象列表
        2. SQLAlchemy Row 对象列表（原生SQL查询结果）
        
        :param obj_list: AccountReceivableList 对象列表 或 Row 对象列表
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

    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<AccountReceivableList id={self.id} receipt_no={self.receipt_no}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "id": self.id,
            "receipt_no": self.receipt_no,
            "receipt_status": self.receipt_status,
            "customer_name": self.customer_name,
            "tax_total_amount": float(self.tax_total_amount) if self.tax_total_amount else None,
            "total_amount": float(self.total_amount) if self.total_amount else None,
            "received_amount": float(self.received_amount) if self.received_amount else None,
            "customer_code": self.customer_code,
            "partner_id": self.partner_id,
            "business_date": self.business_date,
            "due_date": self.due_date,
            "payment_terms": self.payment_terms,
            "payment_org": self.payment_org,
            "salesperson": self.salesperson,
            "remark": self.remark,
            "customer_group": self.customer_group,
            "creator": self.creator,
            "create_date": self.create_date,
            "payment_type": self.payment_type,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
