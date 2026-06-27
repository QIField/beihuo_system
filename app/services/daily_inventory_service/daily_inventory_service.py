# -*- coding:utf-8 -*-
# @Time    : 2026/06/07 10:04
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : daily_inventory_service.py
# @Software: trae-cn

"""
每日库存服务层
负责处理采购订单相关的业务逻辑
"""

from app.models.orm_models.crm_purchase_order_list import CrmPurchaseOrderList
from app.models.orm_models.crm_purchase_order_details import CrmPurchaseOrderDetails
from app.models.orm_models.system_models.crmapp_users import CrmappUsers
from app.utils.orm.session import orm_session
from sqlalchemy import func
from typing import Dict, Optional, List


def mark_order_detail_viewed(purchase_order_line_id: int, user_id: int) -> Optional[Dict]:
    """
    标记订单明细为已查看，更新操作人字段

    :param purchase_order_line_id: 订单明细ID
    :param user_id: 当前登录用户ID，用于查询用户名写入操作人字段
    :return: 包含状态和消息的字典，失败时返回None
    """
    try:
        with orm_session() as session:
            # 1. 通过用户ID查询用户名
            user = session.query(CrmappUsers).filter(
                CrmappUsers.id == user_id
            ).first()

            if not user:
                return {
                    'status': False,
                    'msg': '用户不存在，请重新登录',
                    'data': None
                }

            operator = user.username

            # 2. 查询订单明细记录
            detail = session.query(CrmPurchaseOrderDetails).filter(
                CrmPurchaseOrderDetails.purchase_order_line_id == purchase_order_line_id
            ).first()

            if not detail:
                return {
                    'status': False,
                    'msg': '订单明细不存在',
                    'data': None
                }

            # 3. 更新操作人字段
            detail.operator = operator  # pyright: ignore[reportAttributeAccessIssue]
            session.commit()

            return {
                'status': True,
                'msg': '确认查看成功',
                'data': {
                    'purchase_order_line_id': purchase_order_line_id,
                    'operator': operator
                }
            }
    except Exception as e:
        error_msg = f'标记查看失败: {str(e)}'
        print(error_msg)
        return {'status': False, 'msg': error_msg, 'data': None}


def batch_mark_order_detail_viewed(purchase_order_line_ids: List[int], user_id: int) -> Optional[Dict]:
    """
    批量标记订单明细为已查看，更新操作人字段

    :param purchase_order_line_ids: 订单明细ID列表
    :param user_id: 当前登录用户ID，用于查询用户名写入操作人字段
    :return: 包含状态和消息的字典，失败时返回None
    """
    try:
        with orm_session() as session:
            # 1. 通过用户ID查询用户名
            user = session.query(CrmappUsers).filter(
                CrmappUsers.id == user_id
            ).first()

            if not user:
                return {
                    'status': False,
                    'msg': '用户不存在，请重新登录',
                    'data': None
                }

            operator = user.username

            # 2. 参数验证
            if not purchase_order_line_ids or not isinstance(purchase_order_line_ids, list):
                return {
                    'status': False,
                    'msg': '订单明细ID列表不能为空',
                    'data': None
                }

            # 3. 批量查询并更新订单明细记录
            details = session.query(CrmPurchaseOrderDetails).filter(
                CrmPurchaseOrderDetails.purchase_order_line_id.in_(purchase_order_line_ids)
            ).all()

            if not details:
                return {
                    'status': False,
                    'msg': '未找到可更新的订单明细',
                    'data': None
                }

            # 4. 更新所有找到的记录的操作人字段
            updated_ids = []
            for detail in details:
                detail.operator = operator  # pyright: ignore[reportAttributeAccessIssue]
                updated_ids.append(detail.purchase_order_line_id)

            session.commit()

            return {
                'status': True,
                'msg': f'批量确认查看成功，共更新 {len(updated_ids)} 条记录',
                'data': {
                    'purchase_order_line_ids': updated_ids,
                    'operator': operator,
                    'count': len(updated_ids)
                }
            }
    except Exception as e:
        error_msg = f'批量标记查看失败: {str(e)}'
        print(error_msg)
        return {'status': False, 'msg': error_msg, 'data': None}


def get_purchase_order_list_with_details(page: int = 1, page_size: int = 10, date: str = '', keyword: str = '', order_type: str = '', business_type: str = '') -> Optional[Dict]:
    """
    获取采购订单列表及其明细（一对多分页查询，按订单分页）
    
    使用 SQLAlchemy join 在数据库层面进行表连接查询
    通过 purchase_order_id 关联 crm_purchase_order_list 和 crm_purchase_order_details
    按订单进行分页，每页返回 page_size 个订单及其所有明细
    
    :param page: 页码，默认1
    :param page_size: 每页条数（订单数），默认10
    :param date: 日期筛选，格式 yyyy-MM-dd，可选
    :param keyword: 搜索关键词，用于搜索采购单号
    :param order_type: 订单类型筛选（1:采购入库单，2:采购退货单）
    :param business_type: 业务类型筛选（1:外购，2:普通，3:调货）
    :return: 包含状态、消息、总数和数据列表的字典，如果失败则返回None
    """
    try:
        with orm_session() as session:
            # 优化方案：使用子查询，将查询次数从3次减少到2次
            # 1. 使用子查询获取当前页的订单ID，同时获取总数
            offset = (page - 1) * page_size
            
            # 构建订单查询，应用筛选条件
            order_query = session.query(CrmPurchaseOrderList.purchase_order_id)
            
            # 添加日期筛选条件（只针对订单表）
            if date:
                order_query = order_query.filter(
                    CrmPurchaseOrderList.create_date.like(f'{date}%')
                )
            
            # 添加搜索条件（只针对订单表：采购单号和供应商名称）
            if keyword:
                order_query = order_query.filter(
                    (CrmPurchaseOrderList.pono.like(f'%{keyword}%'))
                    # (CrmPurchaseOrderList.fullname.like(f'%{keyword}%'))
                )
            
            # 添加订单类型筛选条件
            if order_type:
                order_query = order_query.filter(
                    CrmPurchaseOrderList.order_type_id == int(order_type)
                )
            
            # 添加业务类型筛选条件
            if business_type:
                order_query = order_query.filter(
                    CrmPurchaseOrderList.order_source_type == int(business_type)
                )
            
            # 子查询：获取当前页的订单ID（按 purchase_order_id 降序）
            order_ids_subquery = order_query.order_by(
                CrmPurchaseOrderList.purchase_order_id.desc()
            ).offset(offset).limit(page_size).subquery()
            
            # 获取总数
            total_query = session.query(func.count(CrmPurchaseOrderList.purchase_order_id))
            if date:
                total_query = total_query.filter(
                    CrmPurchaseOrderList.create_date.like(f'{date}%')
                )
            if keyword:
                total_query = total_query.filter(
                    (CrmPurchaseOrderList.pono.like(f'%{keyword}%'))
                    # (CrmPurchaseOrderList.fullname.like(f'%{keyword}%'))
                )
            if order_type:
                total_query = total_query.filter(
                    CrmPurchaseOrderList.order_type_id == int(order_type)
                )
            if business_type:
                total_query = total_query.filter(
                    CrmPurchaseOrderList.order_source_type == int(business_type)
                )
            total = total_query.scalar()
            
            # 2. 使用 join 查询所有订单及其明细
            query = session.query(
                CrmPurchaseOrderDetails,
                CrmPurchaseOrderList
            ).join(
                CrmPurchaseOrderList,
                CrmPurchaseOrderDetails.purchase_order_id == CrmPurchaseOrderList.purchase_order_id
            ).filter(
                CrmPurchaseOrderDetails.purchase_order_id.in_(order_ids_subquery)  # pyright: ignore[reportArgumentType]
            )
            
            results = query.order_by(
                CrmPurchaseOrderList.purchase_order_id.desc(),
                CrmPurchaseOrderDetails.no.asc(),
                CrmPurchaseOrderDetails.purchase_order_line_id.asc()
            ).all()
            
            # 3. 将查询结果合并
            list_data = []
            for detail, order in results:
                order_dict = order.to_dict()
                detail_dict = detail.to_dict()
                data_dict = {**order_dict, **detail_dict}
                list_data.append(data_dict)
            
            print(f'从数据库查询到 {len(list_data)} 条采购订单数据，共 {total} 条')
            return {
                'status': True, 
                'msg': '获取成功', 
                'count': total, 
                'data': list_data
            }
    except Exception as e:
        error_msg = f'获取采购订单列表失败: {str(e)}'
        print(error_msg)
        return {'status': False, 'msg': error_msg, 'count': 0, 'data': []}



# if __name__ == '__main__':
#     data = get_purchase_order_list_with_details(page_size=3)
#     print(data)
