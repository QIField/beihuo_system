# -*- coding:utf-8 -*-
# @Time    : 2026/4/10
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_status_orders_raw.py
# @Software: PyCharm

from typing import List, Dict, Any
import pandas as pd
from app.utils.database_connection import db_query_one, db_query_all, db_execute, db_cursor


class WmsStatusOrders:
    """
    WMS状态订单表模型
    对应数据库表：wms_status_orders
    """
    __tablename__ = 'wms_status_orders'

    def __init__(self, id=None, type=None, is_checkupdate=None, orders_id=None,
                 orders_no=None, pono=None, rid=None, frey_no=None, status=None,
                 partner_sapno=None, fullname=None, orderdate=None, name=None,
                 dhdate=None, jhdate=None, qty=None, toqty=None, l_name_zh=None,
                 wait_pick_num=None, already_pick_num=None, is_data_exists=None,
                 created_at=None, updated_at=None):
        self.id = id
        self.type = type
        self.is_checkupdate = is_checkupdate
        self.orders_id = orders_id
        self.orders_no = orders_no
        self.pono = pono
        self.rid = rid
        self.frey_no = frey_no
        self.status = status
        self.partner_sapno = partner_sapno
        self.fullname = fullname
        self.orderdate = orderdate
        self.name = name
        self.dhdate = dhdate
        self.jhdate = jhdate
        self.qty = qty
        self.toqty = toqty
        self.l_name_zh = l_name_zh
        self.wait_pick_num = wait_pick_num
        self.already_pick_num = already_pick_num
        self.is_data_exists = is_data_exists
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def get_by_id(cls, order_id):
        """根据ID获取订单"""
        sql = """
              SELECT id, type, is_checkupdate, orders_id, orders_no, pono, rid,
                     frey_no, status, partner_sapno, fullname, orderdate, name,
                     dhdate, jhdate, qty, toqty, l_name_zh, wait_pick_num,
                     already_pick_num, is_data_exists, created_at, updated_at
              FROM wms_status_orders
              WHERE id = %s
              """
        result = db_query_one(sql, (order_id,))
        if result:
            return cls(**result)
        return None

    @classmethod
    def get_by_pono(cls, pono):
        """根据拣货单号获取订单"""
        sql = """
              SELECT id, type, is_checkupdate, orders_id, orders_no, pono, rid,
                     frey_no, status, partner_sapno, fullname, orderdate, name,
                     dhdate, jhdate, qty, toqty, l_name_zh, wait_pick_num,
                     already_pick_num, is_data_exists, created_at, updated_at
              FROM wms_status_orders
              WHERE pono = %s
              """
        result = db_query_one(sql, (pono,))
        if result:
            return cls(**result)
        return None

    @classmethod
    def get_by_ponos(cls, pono_list):
        """根据 pono 数组获取多条数据"""
        if not pono_list:
            return []

        placeholders = ', '.join(['%s'] * len(pono_list))
        sql = f"""
        SELECT id, type, is_checkupdate, orders_id, orders_no, pono, rid,
               frey_no, status, partner_sapno, fullname, orderdate, name,
               dhdate, jhdate, qty, toqty, l_name_zh, wait_pick_num,
               already_pick_num, is_data_exists, created_at, updated_at
        FROM wms_status_orders
        WHERE pono IN ({placeholders})
        """

        results = db_query_all(sql, pono_list)
        orders = []
        for result in results:
            orders.append(cls(**result))
        return orders

    @classmethod
    def batch_insert(cls, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入数据
        """
        if not data_list:
            return 0

        fields = ['type', 'is_checkupdate', 'orders_id', 'orders_no', 'pono',
                  'rid', 'frey_no', 'status', 'partner_sapno', 'fullname',
                  'orderdate', 'name', 'dhdate', 'jhdate', 'qty', 'toqty',
                  'l_name_zh', 'wait_pick_num', 'already_pick_num', 'is_data_exists']
        fields_str = ', '.join(fields)
        placeholders = ', '.join(['%s'] * len(fields))
        sql = f"INSERT INTO {cls.__tablename__} ({fields_str}) VALUES ({placeholders})"

        records = []
        for data in data_list:
            record = (
                data.get('type'),
                data.get('is_checkupdate'),
                data.get('orders_id'),
                data.get('orders_no'),
                data.get('pono'),
                data.get('rid'),
                data.get('frey_no'),
                data.get('status'),
                data.get('partner_sapno'),
                data.get('fullname'),
                data.get('orderdate'),
                data.get('name'),
                data.get('dhdate'),
                data.get('jhdate'),
                data.get('qty'),
                data.get('toqty'),
                data.get('l_name_zh'),
                data.get('wait_pick_num'),
                data.get('already_pick_num'),
                data.get('is_data_exists')
            )
            records.append(record)

        total_inserted = 0
        batch_size = 100

        try:
            with db_cursor(dict_cursor=False) as cursor:
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    cursor.executemany(sql, batch)
                    total_inserted += len(batch)
            return total_inserted
        except Exception as e:
            print(f"批量插入失败: {e}")
            raise

    @classmethod
    def batch_upsert(cls, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入或更新数据（根据 pono 判断）
        先查询 pono 是否存在，存在则更新，不存在则插入
        """
        if not data_list:
            return 0

        total_affected = 0

        try:
            with db_cursor(dict_cursor=True) as cursor:
                for data in data_list:
                    pono = data.get('pono')
                    
                    if not pono:
                        continue
                    
                    check_sql = "SELECT id FROM wms_status_orders WHERE pono = %s"
                    cursor.execute(check_sql, (pono,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        update_sql = """
                            UPDATE wms_status_orders
                            SET type=%s, is_checkupdate=%s, orders_id=%s, orders_no=%s,
                                rid=%s, frey_no=%s, status=%s, partner_sapno=%s,
                                fullname=%s, orderdate=%s, name=%s, dhdate=%s,
                                jhdate=%s, qty=%s, toqty=%s, l_name_zh=%s,
                                wait_pick_num=%s, already_pick_num=%s, is_data_exists=%s,
                                updated_at=CURRENT_TIMESTAMP
                            WHERE id=%s
                        """
                        params = (
                            data.get('type'),
                            data.get('is_checkupdate'),
                            data.get('orders_id'),
                            data.get('orders_no'),
                            data.get('rid'),
                            data.get('frey_no'),
                            data.get('status'),
                            data.get('partner_sapno'),
                            data.get('fullname'),
                            data.get('orderdate'),
                            data.get('name'),
                            data.get('dhdate'),
                            data.get('jhdate'),
                            data.get('qty'),
                            data.get('toqty'),
                            data.get('l_name_zh'),
                            data.get('wait_pick_num'),
                            data.get('already_pick_num'),
                            data.get('is_data_exists'),
                            existing['id']
                        )
                        cursor.execute(update_sql, params)
                        total_affected += cursor.rowcount
                    else:
                        insert_sql = """
                            INSERT INTO wms_status_orders
                            (type, is_checkupdate, orders_id, orders_no, pono, rid, frey_no,
                             status, partner_sapno, fullname, orderdate, name, dhdate, jhdate,
                             qty, toqty, l_name_zh, wait_pick_num, already_pick_num, is_data_exists)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        params = (
                            data.get('type'),
                            data.get('is_checkupdate'),
                            data.get('orders_id'),
                            data.get('orders_no'),
                            data.get('pono'),
                            data.get('rid'),
                            data.get('frey_no'),
                            data.get('status'),
                            data.get('partner_sapno'),
                            data.get('fullname'),
                            data.get('orderdate'),
                            data.get('name'),
                            data.get('dhdate'),
                            data.get('jhdate'),
                            data.get('qty'),
                            data.get('toqty'),
                            data.get('l_name_zh'),
                            data.get('wait_pick_num'),
                            data.get('already_pick_num'),
                            data.get('is_data_exists')
                        )
                        cursor.execute(insert_sql, params)
                        total_affected += cursor.rowcount
            
            return total_affected
        except Exception as e:
            print(f"批量插入或更新失败: {e}")
            raise

    def save(self):
        """保存当前对象到数据库"""
        if self.id:
            return self.update()
        else:
            return self.insert()

    def insert(self):
        """插入新记录"""
        sql = """
              INSERT INTO wms_status_orders
              (type, is_checkupdate, orders_id, orders_no, pono, rid, frey_no,
               status, partner_sapno, fullname, orderdate, name, dhdate, jhdate,
               qty, toqty, l_name_zh, wait_pick_num, already_pick_num, is_data_exists)
              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
              """
        params = (
            self.type, self.is_checkupdate, self.orders_id, self.orders_no,
            self.pono, self.rid, self.frey_no, self.status, self.partner_sapno,
            self.fullname, self.orderdate, self.name, self.dhdate, self.jhdate,
            self.qty, self.toqty, self.l_name_zh, self.wait_pick_num,
            self.already_pick_num, self.is_data_exists
        )
        affected = db_execute(sql, params)
        if affected > 0:
            self.id = db_query_one("SELECT LAST_INSERT_ID() as id")['id']
        return affected

    def update(self):
        """更新记录"""
        sql = """
              UPDATE wms_status_orders
              SET type=%s, is_checkupdate=%s, orders_id=%s, orders_no=%s,
                  pono=%s, rid=%s, frey_no=%s, status=%s, partner_sapno=%s,
                  fullname=%s, orderdate=%s, name=%s, dhdate=%s, jhdate=%s,
                  qty=%s, toqty=%s, l_name_zh=%s, wait_pick_num=%s,
                  already_pick_num=%s, is_data_exists=%s, updated_at=CURRENT_TIMESTAMP
              WHERE id=%s
              """
        params = (
            self.type, self.is_checkupdate, self.orders_id, self.orders_no,
            self.pono, self.rid, self.frey_no, self.status, self.partner_sapno,
            self.fullname, self.orderdate, self.name, self.dhdate, self.jhdate,
            self.qty, self.toqty, self.l_name_zh, self.wait_pick_num,
            self.already_pick_num, self.is_data_exists, self.id
        )
        return db_execute(sql, params)

    @classmethod
    def delete_by_pono(cls, pono):
        """根据 pono 删除记录"""
        sql = "DELETE FROM wms_status_orders WHERE pono = %s"
        return db_execute(sql, (pono,))

    @classmethod
    def clear_all(cls):
        """清空表"""
        sql = "DELETE FROM wms_status_orders"
        return db_execute(sql)

    @classmethod
    def get_by_orderdate_to_df(cls, orderdate):
        """
        根据订单日期查询数据并返回 DataFrame
        
        Args:
            orderdate: 订单日期，格式如 '2026-04-09'
            
        Returns:
            pandas DataFrame
        """
        sql = """
              SELECT id, type, is_checkupdate, orders_id, orders_no, pono, rid,
                     frey_no, status, partner_sapno, fullname, orderdate, name,
                     dhdate, jhdate, qty, toqty, l_name_zh, wait_pick_num,
                     already_pick_num, is_data_exists, created_at, updated_at
              FROM wms_status_orders
              WHERE orderdate = %s
              """
        results = db_query_all(sql, (orderdate,))
        return pd.DataFrame(results) if results else pd.DataFrame()

    @classmethod
    def get_by_orderdate_range_to_df(cls, start_date, end_date):
        """
        根据订单日期范围查询数据并返回 DataFrame
        
        Args:
            start_date: 开始日期，格式如 '2026-04-09'
            end_date: 结束日期，格式如 '2026-04-09'
            
        Returns:
            pandas DataFrame
        """
        sql = """
              SELECT id, type, is_checkupdate, orders_id, orders_no, pono, rid,
                     frey_no, status, partner_sapno, fullname, orderdate, name,
                     dhdate, jhdate, qty, toqty, l_name_zh, wait_pick_num,
                     already_pick_num, is_data_exists, created_at, updated_at
              FROM wms_status_orders
              WHERE orderdate BETWEEN %s AND %s
              """
        results = db_query_all(sql, (start_date, end_date))
        return pd.DataFrame(results) if results else pd.DataFrame()

    def to_dict(self):
        """
        模型转字典
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
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None
        }

    def __repr__(self):
        return f"<WmsStatusOrders {self.pono}>"
