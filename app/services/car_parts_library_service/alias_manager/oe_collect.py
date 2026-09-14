# -*- coding:utf-8 -*-
import functools

import threading

from app.dao.car_parts_library.benz_error_oe_dao import batch_query_existing, batch_insert, query_page
from app.utils.orm.session import orm_session


oe_error_list = set()
_lock = threading.Lock()


def record_oe_error(func):
    """
    装饰器：捕获被装饰函数执行时的异常，记录出错的 OE 号（part_number），并重新抛出异常。

    适用于形如 func(part_number, ...) 的函数，例如 mercedes_dalfsc_service.by_part_number_get_data。
    出错的 OE 号会通过 collect_oe_error 收集，满足阈值后批量写入 benz_error_oe 表。
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        part_number = kwargs.get('part_number') if 'part_number' in kwargs else (args[0] if args else None)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            collect_oe_error(part_number)
            raise
    return wrapper


def collect_oe_error(part_number):
    """
    收集 OE 号信息，超过阈值时批量写入 benz_error_oe 表

    :param part_number: 出错的 OE 编号
    """
   
    oe_error_list.add(part_number)
   

   
    if len(oe_error_list) >= 10:
        flush_oe_errors()


def flush_oe_errors():
    """
    将收集的 OE 号批量写入 benz_error_oe 表（已存在的跳过），写完后清空集合

    使用非阻塞锁：拿到锁才执行批量写入，拿不到锁则跳过本次（OE 号仍留在
    集合中，等下次触发阈值时再写入），保证不会丢失错误记录。
    """
    if not _lock.acquire(blocking=False):
        return

    try:
       
        oes = list(oe_error_list)
       

        try:
            with orm_session() as session:
                existing = set(batch_query_existing(oes, session))
                new_oes = [oe for oe in oes if oe not in existing]
                if new_oes:
                    batch_insert(new_oes, session)
        except Exception as e:
            # logger.error(f"写入错误 OE 记录失败: {e}", exc_info=True)
            pass
    finally:
        oe_error_list.clear()
        _lock.release()


def page_oe_errors(page=1, page_size=10, keyword=None):
    """
    分页返回错误 OE 记录（仅状态为 0-未入别名库），供前端查看

    :param page: 页码，默认1
    :param page_size: 每页条数，默认10
    :param keyword: 关键字筛选（可选），模糊匹配 OE 编号
    :return: {'status': bool, 'msg': str, 'count': int, 'data': list}
    """
    try:
        with orm_session() as session:
            total, rows = query_page(
                session,
                page=page,
                page_size=page_size,
                keyword=keyword,
            )
        return {'status': True, 'msg': '获取成功', 'count': total, 'data': rows}
    except Exception as e:
        # logger.error(f"分页查询错误 OE 记录失败: {e}", exc_info=True)
        return {'status': False, 'msg': f'获取错误OE记录失败: {str(e)}', 'count': 0, 'data': []}


