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
