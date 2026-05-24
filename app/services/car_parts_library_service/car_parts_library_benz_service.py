# -*- coding:utf-8 -*-
# @Time    : 2026/5/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_service.py
# @Software: PyCharm

"""
汽车配件库服务层
负责处理配件库的业务逻辑
"""

from app.models.orm_models.car_parts_library_benz import CarPartsLibraryBenz
from app.services.car_parts_library_service.mercedes_dalfsc_service import fetch_mercedes_data
from app.utils.orm.session import orm_session
from app.dao.car_parts_library_benz_dao import CarPartsLibraryBenzDao
from app.services.system_setting_service.beihuo_system_config_service import set_config_by_key
from config.config_list_manager.config_cache import get_config_value
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func
import json

def get_part_by_number(part_number: str) -> Optional[Dict]:
    """
    根据配件编号获取配件详情

    :param part_number: 配件编号
    :return: 配件字典，如果不存在则返回None
    """
    try:
        with orm_session() as session:
            # 直接使用 session.query 查询
            part = session.query(CarPartsLibraryBenz).filter(
                CarPartsLibraryBenz.part_number == part_number
            ).first()
            
            if part:
                return part.to_dict()
            return None
    except Exception as e:
        print(f"从数据库查询配件详情失败: {str(e)}")
        return None

def get_parts_list_page(
    page: int = 1,
    page_size: int = 20,
    part_number: Optional[str] = None
) -> Optional[Dict]:
    """
    获取配件列表（分页）

    :param page: 页码，默认1
    :param page_size: 每页条数，默认20
    :param part_number: 配件编号筛选（可选）
    :return: 包含状态、消息、总数和数据列表的字典
    """
    try:
        with orm_session() as session:
            # 检查是否有查询条件，没有则直接返回空
            has_condition = False
            if part_number and part_number.strip():
                has_condition = True
            
            if not has_condition:
                msg = "没有查询条件，不返回数据"
                print(msg)
                return {'status': False, 'msg': msg, 'count': 0, 'data': []}
            
            # 构建查询
            query = session.query(CarPartsLibraryBenz)
            
            # 添加筛选条件
            if part_number:
                part_number = part_number.strip()
                query = query.filter(CarPartsLibraryBenz.part_number.like(f'%{part_number}%'))
            
            # 获取总条数
            total = query.count()
            
            # 分页查询
            offset = (page - 1) * page_size
            items = query.order_by(CarPartsLibraryBenz.updated_at.desc()).offset(offset).limit(page_size).all()
            
            # 转换为字典列表
            data = []
            for item in items:
                data.append(item.to_dict())

            print(f"从数据库查询到 {len(data)} 条配件数据，共 {total} 条")
            return {'status': True, 'msg': '查询成功', 'count': total, 'data': data}

    except Exception as e:
        print(f"从数据库查询配件列表失败: {str(e)}")
        return {'status': False, 'msg': f"查询配件列表失败: {str(e)}", 'count': 0, 'data': []}






## 进行数据刷新
def data_list_page_refresh(
    page: int = 1,
    page_size: int = 20,
    part_number: Optional[str] = None
) -> Dict:  
    """
    获取配件列表（分页）

    :param page: 页码，默认1
    :param page_size: 每页条数，默认20
    :param part_number: 配件编号筛选（可选）
    :return: 包含成功/失败状态和提示信息的字典，格式: {'status': bool, 'msg': str, 'count': int}
    """

    try:
        with orm_session() as session:
            # 检查是否有查询条件，没有则直接返回
            has_condition = False
            if part_number and part_number.strip():
                has_condition = True
            
            if not has_condition:
                msg = "没有查询条件，不返回数据"
                print(msg)
                return {'status': False, 'msg': msg, 'parts_count': 0, 'stock_count': 0}
            



            # 构建查询
            query = session.query(CarPartsLibraryBenz)
            
            # 添加筛选条件
            if part_number:
                part_number = part_number.strip()
                query = query.filter(CarPartsLibraryBenz.part_number.like(f'%{part_number}%'))
         
            # 分页查询
            offset = (page - 1) * page_size
            items = query.order_by(CarPartsLibraryBenz.updated_at.desc()).offset(offset).limit(page_size).all()
            
           
            if len(items) == 0:
                return fetch_mercedes_data([part_number])

            # 只提取part_number转化为列表
            part_numbers = []
            for item in items:
                part_numbers.append(item.part_number)
            return fetch_mercedes_data(part_numbers)

    except Exception as e:
        msg = f"从数据库查询配件数据刷新失败: {str(e)}"
        print(msg)
        return {'status': False, 'msg': msg, 'parts_count': 0, 'stock_count': 0}


def set_mercedes_config(cookie: str, customer_id: str, sales_organization_id: str) -> Dict:
    """
    设置奔驰大库配置

    :param cookie: Cookie 字符串
    :param customer_id: 客户ID
    :param sales_organization_id: 销售组织ID
    :return: 设置结果
    """
    try:
        # 将配置保存为 JSON 格式
        config_value = json.dumps({
            'cookie': cookie,
            'customer_id': customer_id,
            'sales_organization_id': sales_organization_id
        }, ensure_ascii=False)
        
        set_config_by_key(
            'mercedes_benz',
            config_value,
            config_type='json',
            config_group='car_parts',
            label='奔驰大库配置',
            remark='用于访问奔驰大库的配置信息'
        )
        return {
            'code': 200,
            'message': '奔驰配置设置成功'
        }
    except Exception as e:
        return {
            'code': 500,
            'message': f'奔驰配置设置失败: {str(e)}'
        }


def get_mercedes_config() -> Optional[Dict]:
    """
    获取奔驰大库配置

    :return: 配置字典，如果不存在则返回None
    """
    try:
        config = get_config_value('mercedes_benz')
        return config  # pyright: ignore[reportReturnType]
    except Exception as e:
        print(f"获取奔驰配置失败: {str(e)}")
        return None





