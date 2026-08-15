# -*- coding:utf-8 -*-
# @Time    : 2026/07/25
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_refund_ref_dao.py
# @Software: trae-cn

# 导入SQLAlchemy的text和bindparam，用于构建动态SQL
from sqlalchemy import text, bindparam
# 导入ORM会话工具，用于数据库连接和事务管理
from app.utils.orm.session import orm_session


def insert_unmatched_refund_orders(batch_size: int = 1000) -> int:
    """
    Step 1: 批量插入未匹配的退货订单到关联表
    
    将sales_order_history表中未被处理过的退货订单（order_type_id=2）
    批量插入到stock_safe_refund_ref关联表中，标记为type=50（未进行匹配）。
    
    Args:
        batch_size: 每批插入的数量，默认1000
        
    Returns:
        插入的记录数
    """
    # 构建INSERT...SELECT SQL语句，从sales_order_history查询退货订单并插入关联表
    sql = text("""
        INSERT INTO stock_safe_refund_ref (
            refund_order_items_id,
            number,
            brand_name,
            pdname,
            frey_no,
            customer_id,
            refund_quantity,
            refund_create_date,
            type
        )
        SELECT
            orders_items_id,
            number,
            brand_name,
            pdname,
            frey_no,
            customer_id,
            quantity AS refund_quantity,
            create_date AS refund_create_date,
            50 AS type
        FROM sales_order_history
        WHERE order_type_id = 2
          AND NOT EXISTS (
              SELECT 1 FROM stock_safe_refund_ref 
              WHERE stock_safe_refund_ref.refund_order_items_id = sales_order_history.orders_items_id
          )
        ORDER BY create_date ASC
        LIMIT :batch_size
    """)

    # 使用ORM会话执行SQL
    with orm_session() as session:
        result = session.execute(sql, {"batch_size": batch_size})
        # 返回插入的记录数
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


def get_pending_refund_orders(batch_size: int = 100) -> list:
    """
    获取待匹配的退货订单列表（type=50）
    
    从关联表中查询所有尚未匹配的退货订单，按创建时间升序排列，优先处理更早的订单。
    
    Args:
        batch_size: 每批获取的数量，默认100
        
    Returns:
        退货订单记录列表，每个元素是包含订单信息的字典
    """
    # 构建查询SQL，获取type=50的退货订单
    # LEFT JOIN sales_order_history 取fullname(客户全称)作为customer_name，
    # 供 find_matching_normal_orders 做客户id/客户名称二选一匹配
    sql = text("""
        SELECT
            r.refund_order_items_id,
            r.customer_id,
            r.number,
            r.brand_name,
            r.pdname,
            r.frey_no,
            r.refund_quantity,
            r.refund_create_date,
            s.fullname AS customer_name
        FROM stock_safe_refund_ref r
        LEFT JOIN sales_order_history s ON s.orders_items_id = r.refund_order_items_id
        WHERE r.type = 50
        ORDER BY r.refund_create_date ASC
        LIMIT :batch_size
    """)

    # 使用ORM会话执行查询，返回映射后的字典列表
    with orm_session() as session:
        result = session.execute(sql, {"batch_size": batch_size}).mappings().all()
        return [dict(row) for row in result]


def find_matching_normal_orders(
    customer_id: int,
    customer_name: str,
    number: str,
    brand_name: str,
    pdname: str,
    frey_no: str,
    refund_create_date: int,
    excluded_normal_ids: list = None  # pyright: ignore[reportArgumentType]
) -> list:
    """
    Step 2: 为退货订单查找匹配的常规订单（支持一对多匹配）

    匹配条件：
    - order_type_id = 1（常规订单）
    - 客户匹配（二选一，先匹配customer_id，相等即视为同一客户；不相等再匹配客户名称fullname）：
      customer_id = :customer_id OR fullname = :customer_name
    - number、brand_name、pdname、frey_no 完全匹配（与sales_order_history同名字段直接对应）
    - create_date < refund_create_date（常规订单在退货订单之前创建）
    - 排除已被匹配过的常规订单（NOT EXISTS type IN (11, 12, 13, 21, 22, 23, 31, 32, 33)），
      避免同一常规订单被重复匹配（跨批次去重，21/22/23 也要排除因其已有退货关联）

    注意：去掉了price匹配条件和数量判断条件，避免优惠折扣影响匹配。

    Args:
        customer_id: 客户ID
        customer_name: 客户全称（即sales_order_history.fullname字段，customer_id未命中时作为同一客户的兜底匹配）
        number: OE号（即sales_order_history.number字段）
        brand_name: 品牌名
        pdname: 产品名称（即sales_order_history.pdname字段）
        frey_no: 条码（即sales_order_history.frey_no字段）
        refund_create_date: 退货订单创建时间戳
        excluded_normal_ids: 已被排除的常规订单ID列表（同批次内已匹配的订单），默认空列表

    Returns:
        匹配的常规订单列表，每个元素包含orders_items_id, total_price, quantity；未匹配返回空列表
    """
    # 如果未传入排除列表，初始化为空列表
    if excluded_normal_ids is None:
        excluded_normal_ids = []

    # 构建SQL查询片段列表，便于动态拼接
    sql_parts = [
        """
        SELECT 
            orders_items_id,
            total_price,
            quantity
        FROM sales_order_history
        WHERE order_type_id = 1
          AND (customer_id = :customer_id OR fullname = :customer_name)
          AND number = :number
          AND brand_name = :brand_name
          AND pdname = :pdname
          AND frey_no = :frey_no
          AND create_date < :refund_create_date
          AND NOT EXISTS (
              SELECT 1 FROM stock_safe_refund_ref 
              WHERE stock_safe_refund_ref.normal_order_items_id = sales_order_history.orders_items_id
                AND stock_safe_refund_ref.type IN (11, 12, 13,21,22, 23, 31, 32, 33)
          )
        """
    ]

    # 如果有排除的常规订单ID，添加NOT IN条件
    if excluded_normal_ids:
        sql_parts.append("AND orders_items_id NOT IN :excluded_normal_ids ")

    # 添加排序和限制，按创建时间倒序（最新的常规订单优先），最多返回10条
    sql_parts.append("ORDER BY create_date DESC LIMIT 10")

    # 拼接SQL片段
    sql = text("".join(sql_parts))

    # 如果有排除列表，需要使用expanding参数支持IN条件
    if excluded_normal_ids:
        sql = sql.bindparams(
            bindparam("excluded_normal_ids", expanding=True)
        )

    # 构建查询参数字典
    params = {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "number": number,
        "brand_name": brand_name,
        "pdname": pdname,
        "frey_no": frey_no,
        "refund_create_date": refund_create_date,
    }

    # 如果有排除列表，添加到参数中
    if excluded_normal_ids:
        params["excluded_normal_ids"] = excluded_normal_ids

    # 执行查询并返回结果
    with orm_session() as session:
        result = session.execute(sql, params).mappings().all()
        return [dict(row) for row in result]





def insert_matched_refund(
    matched_list: list
) -> int:
    """
    批量插入匹配成功的退货关联记录（一次性插入）

    在单个事务中一次性插入本批次所有匹配记录。每条记录的字段字典由service层预构造，
    直接用于executemany批量插入，本函数不再内部构造参数。

    Args:
        matched_list: 匹配成功的记录字典列表，每个元素需包含：
            refund_order_items_id: 退货订单明细ID
            normal_order_items_id: 常规订单明细ID
            number: OE号
            brand_name: 品牌名
            pdname: 产品名称
            frey_no: 条码
            customer_id: 客户ID
            normal_quantity: 常规订单数量
            refund_quantity: 退货订单数量
            processed_quantity: 处理数量（常规剩余数量 + 退货数量）
            match_count: 匹配次数
            type: 类型值

    Returns:
        插入的记录总数
    """
    # 如果列表为空，直接返回0
    if not matched_list:
        return 0

    # 构建批量INSERT SQL（参数由调用方预构造，直接executemany）
    sql = text("""
        INSERT INTO stock_safe_refund_ref (
            refund_order_items_id,
            normal_order_items_id,
            number,
            brand_name,
            pdname,
            frey_no,
            customer_id,
            normal_quantity,
            refund_quantity,
            processed_quantity,
            match_count,
            type
        )
        VALUES (
            :refund_order_items_id,
            :normal_order_items_id,
            :number,
            :brand_name,
            :pdname,
            :frey_no,
            :customer_id,
            :normal_quantity,
            :refund_quantity,
            :processed_quantity,
            :match_count,
            :type
        )
    """)

    # 使用ORM会话批量执行插入，底层调用DBAPI的executemany()
    with orm_session() as session:
        result = session.execute(sql, matched_list)
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]








def batch_insert_matched_refund(matched_list: list) -> int:
    """
    批量插入匹配成功的退货关联记录

    在单个事务中批量执行插入，使用SQLAlchemy的executemany()一次性提交所有记录，
    比循环逐条插入效率更高。每条记录包含匹配的常规订单信息和计算后的处理结果。
    match_count从matched_list的每个元素中获取，表示第几次匹配产生的记录。

    Args:
        matched_list: 匹配成功的记录列表，每个元素包含：
            refund_order_items_id: 退货订单明细ID
            normal_order_items_id: 匹配到的常规订单明细ID
            number: OE号
            brand_name: 品牌名
            pdname: 产品名称
            frey_no: 条码
            customer_id: 客户ID
            normal_quantity: 常规订单数量
            refund_quantity: 退货订单数量
            processed_quantity: 处理数量
            match_count: 匹配次数（标识本条记录是第几次匹配产生的）
            type: 类型值

    Returns:
        插入/更新的记录总数
    """
    # 如果列表为空，直接返回0
    if not matched_list:
        return 0

    # 构建INSERT...ON DUPLICATE KEY UPDATE SQL，包含match_count字段
    # 注意：SQL中不要使用 -- 行内注释。MySQL要求 -- 后必须跟空白字符才视为注释，
    # 否则会被当成表达式导致1064语法错误；同时行内注释会破坏pymysql executemany
    # 的批量VALUES合并正则，导致退化为逐条执行。字段含义见上方docstring。
    sql = text("""
        INSERT INTO stock_safe_refund_ref (
            refund_order_items_id,
            normal_order_items_id,
            number,
            brand_name,
            pdname,
            frey_no,
            customer_id,
            normal_quantity,
            refund_quantity,
            processed_quantity,
            match_count,
            type
        )
        VALUES (
            :refund_order_items_id,
            :normal_order_items_id,
            :number,
            :brand_name,
            :pdname,
            :frey_no,
            :customer_id,
            :normal_quantity,
            :refund_quantity,
            :processed_quantity,
            :match_count,
            :type
        )
        ON DUPLICATE KEY UPDATE
            number = VALUES(number),
            brand_name = VALUES(brand_name),
            pdname = VALUES(pdname),
            frey_no = VALUES(frey_no),
            customer_id = VALUES(customer_id),
            normal_quantity = VALUES(normal_quantity),
            refund_quantity = VALUES(refund_quantity),
            processed_quantity = VALUES(processed_quantity),
            type = VALUES(type)
    """)

  

    # 使用ORM会话批量执行插入，底层调用DBAPI的executemany()，比循环单条执行效率更高
    with orm_session() as session:
        result = session.execute(sql, matched_list)
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]




def batch_update_unmatched_to_type40(refund_ids: list) -> int:
    """
    批量更新未匹配的退货订单为type=40
    
    使用IN条件在单条SQL中更新多个记录，减少数据库交互次数。
    
    Args:
        refund_ids: 未匹配的退货订单明细ID列表
        
    Returns:
        更新的记录数
    """
    # 如果列表为空，直接返回0
    if not refund_ids:
        return 0

    # 构建批量UPDATE SQL
    sql = text("""
        UPDATE stock_safe_refund_ref
        SET type = 40
        WHERE refund_order_items_id IN :refund_ids
          AND type = 50
    """).bindparams(
        bindparam("refund_ids", expanding=True)
    )

    # 执行批量更新并返回影响行数
    with orm_session() as session:
        result = session.execute(sql, {"refund_ids": refund_ids})
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


def delete_pending_by_refund_ids(refund_ids: list) -> int:
    """
    删除已匹配退货单的 type=50 占位行

    Step 1 会为每个退货单插入一行 type=50 占位行（normal_order_items_id=NULL）作为待匹配队列。
    Step 2 匹配成功时，batch_insert_matched_refund 会新增匹配行（normal_order_items_id=具体值，
    type=11/13/21 等）。由于唯一键 uk_normal_refund 为 (normal_order_items_id, refund_order_items_id)，
    匹配行与占位行是不同的行，占位行不会被自动清理。若不删除，get_pending_refund_orders 会在下一批
    再次捞回该占位行，导致同一退货单被重复匹配（每次消耗一个新的常规单）并最终被误标为 type=40。

    因此在批量插入匹配记录后，需调用本方法删除这些已匹配退货单的 type=50 占位行。

    Args:
        refund_ids: 已匹配成功的退货订单明细ID列表

    Returns:
        删除的占位行数
    """
    # 如果列表为空，直接返回0
    if not refund_ids:
        return 0

    # 仅删除 type=50 的占位行，不影响已插入的匹配行（type=11/13/21 等）
    sql = text(
        "DELETE FROM stock_safe_refund_ref WHERE type = 50 AND refund_order_items_id IN :refund_ids"
    ).bindparams(
        bindparam("refund_ids", expanding=True)
    )

    # 执行删除并返回影响行数
    with orm_session() as session:
        result = session.execute(sql, {"refund_ids": refund_ids})
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


def delete_type40_by_refund_ids(refund_ids: list) -> int:
    """
    删除已匹配退货单的 type=40 记录（第一次匹配失败的占位行）

    type=40 记录是 step2 第一次匹配未命中的退货单。step3 的 find_matching_refund_order_type3
    会把 type=40 也纳入第二次匹配尝试；匹配成功后 insert_matched_refund 会新增匹配行
    （type=12/22/32 等，match_count 更大）。此时 type=40 记录已失去意义，若不删除，
    step3 结束时的 batch_update_unmatched_to_type41 会把它误标为 type=41（第二次匹配失败）。

    因此在 step3 批量插入匹配记录后，需调用本方法删除这些已匹配退货单的 type=40 记录。
    对于 type=31/32 的退货单（无 type=40 记录），本方法为空操作，不影响其数据。

    Args:
        refund_ids: 已匹配成功的退货订单明细ID列表

    Returns:
        删除的 type=40 记录数
    """
    # 如果列表为空，直接返回0
    if not refund_ids:
        return 0

    # 仅删除 type=40 的记录，不影响 type=31/32 等其他记录
    sql = text(
        "DELETE FROM stock_safe_refund_ref WHERE type = 40 AND refund_order_items_id IN :refund_ids"
    ).bindparams(
        bindparam("refund_ids", expanding=True)
    )

    # 执行删除并返回影响行数
    with orm_session() as session:
        result = session.execute(sql, {"refund_ids": refund_ids})
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


def batch_update_unmatched_to_type41() -> int:
    """
    Step3结束后，将仍未匹配的 type=40 记录更新为 type=41

    type 值含义：
    - type=40：第一次匹配(step2)未匹配上
    - type=41：第二次匹配(step3)仍未匹配上

    在 step3 全部分页处理完成、且已匹配退货单的 type=40 记录被 delete_type40_by_refund_ids
    清理之后调用本方法。此时表中剩余的 type=40 记录均为两次匹配都未命中的退货单，
    统一更新为 type=41 以区分匹配轮次。

    Returns:
        更新为 type=41 的记录数
    """
    # 将所有剩余 type=40 记录更新为 type=41
    sql = text("UPDATE stock_safe_refund_ref SET type = 41 WHERE type = 40")

    # 执行更新并返回影响行数
    with orm_session() as session:
        result = session.execute(sql)
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


def get_type_summary() -> list:
    """
    获取各类型分布统计
    
    统计关联表中各type值的记录数量，用于生成处理结果摘要。
    
    Returns:
        类型分布列表，每个元素包含type和count两个字段
    """
    # 构建统计SQL
    sql = text("""
        SELECT type, COUNT(*) as count
        FROM stock_safe_refund_ref
        GROUP BY type
        ORDER BY type
    """)

    # 执行查询并返回结果
    with orm_session() as session:
        result = session.execute(sql).mappings().all()
        return [dict(row) for row in result]


def get_pending_count() -> int:
    """
    获取待处理（type=50）的退货订单数量
    
    返回关联表中尚未匹配的退货订单总数。
    
    Returns:
        待处理订单数量
    """
    # 构建计数SQL
    sql = text("""
        SELECT COUNT(*) as pending_count
        FROM stock_safe_refund_ref
        WHERE type = 50
    """)

    # 执行查询并返回计数值
    with orm_session() as session:
        result = session.execute(sql).mappings().first()
        return result["pending_count"] if result else 0


def get_type21_22_records(batch_size: int = 100, page: int = 1) -> list:
    """
    获取常规订单有剩余的记录（type=21/22）

    这些记录表示常规订单数量大于退货数量，还有剩余数量可以继续匹配其他退货订单。
    对同一常规订单，取最新记录（match_count最大的记录，跨所有type）；
    仅当该最新记录仍为type=21/22（有剩余）时才返回，避免已完全退货(type=12)或退货超出(type=32)的订单被重复匹配。

    使用分页查询（LIMIT + OFFSET），页码从1开始。配合service层的页码自增逻辑，
    确保即使某页记录全部未匹配也能继续向后翻页，避免死循环。

    Args:
        batch_size: 每批获取的数量，默认100
        page: 页码，从1开始，默认1

    Returns:
        记录列表，包含完整的订单信息和处理结果
    """
    # 计算偏移量
    offset = (page - 1) * batch_size
    # 构建查询SQL：子查询取同一常规订单的全局最大match_count（不限制type），
    # 外层再限定type IN (21,22)，确保只返回最新记录仍为有剩余状态的常规订单
    # LEFT JOIN sales_order_history 获取常规订单的创建时间，用于 step3 的时间约束
    sql = text("""
        SELECT
            r.id,
            r.refund_order_items_id,
            r.normal_order_items_id,
            r.customer_id,
            r.number,
            r.brand_name,
            r.pdname,
            r.frey_no,
            r.normal_quantity,
            r.refund_quantity,
            r.processed_quantity,
            r.match_count,
            r.type,
            s.create_date AS normal_order_create_date
        FROM stock_safe_refund_ref r
        LEFT JOIN sales_order_history s ON s.orders_items_id = r.normal_order_items_id
        WHERE r.type IN (21, 22)
          AND r.match_count = (
              SELECT MAX(match_count)
              FROM stock_safe_refund_ref r2
              WHERE r2.normal_order_items_id = r.normal_order_items_id
          )
        ORDER BY r.created_at ASC
        LIMIT :batch_size OFFSET :offset
    """)

    # 执行查询并返回结果
    with orm_session() as session:
        result = session.execute(sql, {"batch_size": batch_size, "offset": offset}).mappings().all()
        return [dict(row) for row in result]


def find_matching_refund_order_type3(
    customer_id: int,
    number: str,
    brand_name: str,
    pdname: str,
    frey_no: str,
    normal_order_create_date: int,
    excluded_refund_ids: list = None  # pyright: ignore[reportArgumentType]
) -> list:
    """
    Step 3: 为常规订单查找多条匹配的退货订单（仅 type=40）

    仅查找 type=40 的退货订单（第一次匹配 step2 未命中），
    对同一退货订单，取最新记录（match_count 最大的记录，跨所有 type）；
    仅当该最新记录仍为 type=40 时才返回，避免已被匹配的退货被重复匹配。

    时间约束：退货订单的 refund_create_date 必须大于常规订单的创建时间
    （r.refund_create_date > :normal_order_create_date），
    确保退货发生在常规订单之后。

    匹配条件：customer_id、number、brand_name、pdname、frey_no 完全匹配（与sales_order_history同名字段直接对应）

    Args:
        customer_id: 客户ID
        number: OE号
        brand_name: 品牌名
        pdname: 产品名称
        frey_no: 条码
        normal_order_create_date: 常规订单的创建时间（sales_order_history.create_date），用于时间约束
        excluded_refund_ids: 已被排除的退货订单ID列表（同批次内已匹配的），默认空列表

    Returns:
        匹配的退货订单列表，每个元素包含 refund_order_items_id, refund_quantity, processed_quantity；未匹配返回空列表
    """
    # 如果未传入排除列表，初始化为空列表
    if excluded_refund_ids is None:
        excluded_refund_ids = []

    # 构建SQL查询片段列表，获取match_count最大的记录（最后一次匹配产生的）
    # 仅查询 type=40（step2 未匹配的退货订单）
    # 时间约束：退货订单的 refund_create_date > 常规订单的创建时间
    sql_parts = [
        """
        SELECT
            refund_order_items_id,
            refund_quantity,
            processed_quantity
        FROM stock_safe_refund_ref r
        WHERE r.type = 40
          AND r.customer_id = :customer_id
          AND r.number = :number
          AND r.brand_name = :brand_name
          AND r.pdname = :pdname
          AND r.frey_no = :frey_no
          AND r.refund_create_date > :normal_order_create_date
          AND r.match_count = (
              SELECT MAX(match_count)
              FROM stock_safe_refund_ref r2
              WHERE r2.refund_order_items_id = r.refund_order_items_id
          )
        """
    ]

    # 如果有排除的退货订单ID，添加NOT IN条件
    if excluded_refund_ids:
        sql_parts.append("AND r.refund_order_items_id NOT IN :excluded_refund_ids ")

    # 添加排序和限制，按退货订单创建时间升序（先处理更早的退货订单），最多返回10条
    sql_parts.append("ORDER BY r.refund_create_date ASC LIMIT 10")

    # 拼接SQL片段
    sql = text("".join(sql_parts))

    # 如果有排除列表，需要使用expanding参数支持IN条件
    if excluded_refund_ids:
        sql = sql.bindparams(
            bindparam("excluded_refund_ids", expanding=True)
        )

    # 构建查询参数字典
    params = {
        "customer_id": customer_id,
        "number": number,
        "brand_name": brand_name,
        "pdname": pdname,
        "frey_no": frey_no,
        "normal_order_create_date": normal_order_create_date,
    }

    # 如果有排除列表，添加到参数中
    if excluded_refund_ids:
        params["excluded_refund_ids"] = excluded_refund_ids

    # 执行查询并返回结果
    with orm_session() as session:
        result = session.execute(sql, params).mappings().all()
        if result:
            return [dict(row) for row in result]
        return []




def get_type3_count() -> int:
    """
    获取数量未完全抵消的退货订单数量（type=31/32/33）
    
    返回关联表中退货数量超出常规订单数量的记录总数。
    
    Returns:
        type=31/32/33的记录数量
    """
    # 构建计数SQL
    sql = text("""
        SELECT COUNT(*) as count
        FROM stock_safe_refund_ref
        WHERE type IN (31, 32, 33)
    """)

    # 执行查询并返回计数值
    with orm_session() as session:
        result = session.execute(sql).mappings().first()
        return result["count"] if result else 0


def update_type_to_by_refund_order() -> int:
    """
    按退货订单视角统一type：取同一refund_order_items_id下MAX(match_count)记录的type，
    将该退款单下所有匹配记录统一为该type（覆盖一对多-退货订单视角 13/23/33）。

    未匹配/占位记录（normal_order_items_id IS NULL）被排除；单条匹配天然no-op。
    子查询包派生表规避MySQL 1093（UPDATE目标表不能出现在子查询FROM中）。

    Returns:
        更新的记录数
    """
    sql = text("""
        UPDATE stock_safe_refund_ref r
        JOIN (
            SELECT refund_order_items_id, type AS target_type
            FROM (
                SELECT r1.refund_order_items_id, r1.type
                FROM stock_safe_refund_ref r1
                LEFT JOIN stock_safe_refund_ref r2
                    ON r1.refund_order_items_id = r2.refund_order_items_id
                    AND (r1.match_count < r2.match_count
                         OR (r1.match_count = r2.match_count AND r1.id < r2.id))
                    AND r2.normal_order_items_id IS NOT NULL
                    AND r2.type IN (13, 23, 33)
                WHERE r2.id IS NULL
                  AND r1.normal_order_items_id IS NOT NULL
                  AND r1.type IN (13, 23, 33)
            ) ranked
        ) t ON r.refund_order_items_id = t.refund_order_items_id
        SET r.type = t.target_type
        WHERE r.type != t.target_type
    """)

    with orm_session() as session:
        result = session.execute(sql)
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


def update_type_to_by_normal_order() -> int:
    """
    按常规订单视角统一type：取同一normal_order_items_id下MAX(match_count)记录的type，
    将该常规单下所有匹配记录统一为该type（覆盖一对多-常规订单视角 12/22/32）。

    未匹配/占位记录（normal_order_items_id IS NULL）被排除；单条匹配天然no-op。
    子查询包派生表规避MySQL 1093（UPDATE目标表不能出现在子查询FROM中）。

    Returns:
        更新的记录数
    """
    sql = text("""
        UPDATE stock_safe_refund_ref r
        JOIN (
            SELECT normal_order_items_id, type AS target_type
            FROM (
                SELECT r1.normal_order_items_id, r1.type
                FROM stock_safe_refund_ref r1
                LEFT JOIN stock_safe_refund_ref r2
                    ON r1.normal_order_items_id = r2.normal_order_items_id
                    AND (r1.match_count < r2.match_count
                         OR (r1.match_count = r2.match_count AND r1.id < r2.id))
                    AND r2.normal_order_items_id IS NOT NULL
                    AND r2.type IN (12, 22, 32)
                WHERE r2.id IS NULL
                  AND r1.normal_order_items_id IS NOT NULL
                  AND r1.type IN (12, 22, 32)
            ) ranked
        ) t ON r.normal_order_items_id = t.normal_order_items_id
        SET r.type = t.target_type
        WHERE r.type != t.target_type
    """)

    with orm_session() as session:
        result = session.execute(sql)
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


