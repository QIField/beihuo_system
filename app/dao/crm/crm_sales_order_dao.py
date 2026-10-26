# -*- coding:utf-8 -*-
# @Time    : 2026/06/26 13:35
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crm_sales_order_dao.py
# @Software: trae-cn

from sqlalchemy import text

from app.utils.orm.session import orm_session


def dashboard_crm_wms_data(start_date, end_date, keyword='', status=''):
    """
    获取CRM与WMS订单数据
    status=3 表示查询所有未完成（未开始+正在拣货），且不受日期限制
    """
    base_sql = """
        SELECT
            c.d_sap_no AS pono_new,
            c.create_date AS create_date_crm,
            c.fullname AS fullname_crm,
            c.`handler` AS handler_crm,
            
            w.`status` AS status_wms,
            w.toqty AS toqty_wms,
            w.wait_pick_num AS wait_pick_num_wms,
            w.already_pick_num AS already_pick_num_wms,
            w.data_flag AS is_data_exists_wms_keywd,
            w.qty AS qty_wms,
            w.`name` AS name_wms,
            CAST(UNIX_TIMESTAMP(w.jhdate) AS UNSIGNED) AS jhdate_timestamp,
            
            wo.ship_date AS ship_date,
            wo.total_quantity AS total_quantity,
            wo.shipper AS shipper,
            wo.photos AS photos,
            wo.order_id AS order_id
        FROM
        crm_sales_order AS c
        LEFT JOIN wms_picking_list AS w ON c.d_sap_no = w.pono
        LEFT JOIN wms_orders AS wo ON wo.out_no=c.d_sap_no
        
        WHERE
            c.order_type_name = 1
    """

    params = {}

    if status != '3':
        base_sql += """
            AND
                c.create_date >= :start_date  
            AND 
                c.create_date <= :end_date
        """
        params["start_date"] = start_date
        params["end_date"] = end_date

    if keyword:
        base_sql += """
            AND (
                c.fullname LIKE :keyword
                OR c.d_sap_no LIKE :keyword
                OR c.`handler` LIKE :keyword
                OR w.`name` LIKE :keyword
                OR wo.shipper LIKE :keyword
            )
        """
        params["keyword"] = f"%{keyword}%"

    if status:
        if status == '3':
            base_sql += " AND w.`status` IN (0, 1)"
        else:
            base_sql += " AND w.`status` = :status"
            params["status"] = status

    sql = text(base_sql)

    with orm_session() as session:
        result = session.execute(sql, params).mappings().all()

        result = [dict(row) for row in result]
        return result


def get_customer_total_price_sum(session,
                                 page=1, limit=20,
                                 start_time=None, end_time=None,
                                 customer_name=None,
                                 level_id=None,
                                 payment_description=None,
                                 total_price_min=None, total_price_max=None):
    """
    客户额度管理-交易金额统计（按客户分组：订单数/订单金额/实发金额/未结算金额）

    口径自旧 merge_order_list 统计查询原样平移（2026-10-22 额度管理切换数据源）：
    - 关联键：crm_sales_order.customer_id = partner_list.partner_id
      （实测该表 customer_id 与 partner_id 两字段值完全相同，保持旧口径减少变动）；
    - 不含 status 过滤，与旧口径一致；
    - 数据源说明：crm_sales_order 由每日 02:00 全量 + 看板心跳增量维护
      （旧表 merge_order_list 每周二全量已停更，仅保留表数据与 ORM）。

    :param session: SQLAlchemy Session 对象
    :return: (总记录数, 当前页字典列表)
    """
    page = max(1, int(page))
    limit = max(1, min(int(limit), 100))
    offset = (page - 1) * limit

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
                     FROM crm_sales_order m
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

    count_sql = text("""
                     SELECT COUNT(*)
                     FROM (SELECT customer_id
                           FROM crm_sales_order m
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

    params = {
        "start_time": start_time,
        "end_time": end_time,
        "customer_name": f"%{customer_name}%" if customer_name else None,
        "level_id": level_id,
        "payment_description": payment_description,
        "total_price_min": total_price_min,
        "total_price_max": total_price_max,
        "limit": limit,
        "offset": offset,
    }

    total = session.execute(count_sql, params).scalar() or 0
    rows = session.execute(sql, params).mappings().all()
    # Decimal/Numeric 统一转 float，保证接口可 JSON 序列化
    result = [
        {k: (float(v) if hasattr(v, "real") and hasattr(v, "imag") else v) for k, v in dict(row).items()}
        for row in rows
    ]
    return total, result


def get_pono_list(start_date, end_date, keyword=''):
    """
    获取CRM有，没有WMS的订单号列表
    """
    base_sql = """
        SELECT 
            c.d_sap_no AS pono
        FROM 
            crm_sales_order AS c 
        WHERE 
            c.create_date >= :start_date  
        AND 
            c.create_date <= :end_date
        AND
            c.order_type_name = 1  
            
        AND NOT EXISTS (
                SELECT 1 
                FROM wms_picking_list w 
                WHERE w.pono = c.d_sap_no
        )
    """

    params = {"start_date": start_date, "end_date": end_date}

    if keyword and keyword.strip():
        base_sql += """
            AND (
                c.fullname LIKE :keyword
                OR c.d_sap_no LIKE :keyword
                OR c.`handler` LIKE :keyword
            )
        """
        params["keyword"] = f"%{keyword.strip()}%"

    sql = text(base_sql)

    with orm_session() as session:
        result = session.execute(sql, params).mappings().all()
        result = [dict(row) for row in result]
        return result


# if __name__ == "__main__":
#     start_date = 1772434342
#     end_date = 1792444342
    
#     data=get_pono_list(start_date, end_date)
#     print(data)
#     print(f"共 {len(data)} 条数据")


# if __name__ == "__main__":
#     data=dashboard_crm_wms_data(1782434124, 1782454124)
#     for item in data:
#         print(item)
