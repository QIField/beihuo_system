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
from app.models.orm_models.crmapp_compare_summary import CrmappCompareSummary
from app.services.car_parts_library_service.mercedes_dalfsc_service import fetch_mercedes_data
from app.services.car_parts_library_service.excel_import_service import process_file_stream, generate_template
from app.utils.orm.session import orm_session
from app.dao.car_parts_library_benz_dao import CarPartsLibraryBenzDao
from app.services.system_setting_service.beihuo_system_config_service import set_config_by_key
from config.config_list_manager.config_cache import get_config_value
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func
import json
import re

def get_part_by_number(part_number: str) -> Optional[Dict]:
    """
    根据配件编号获取配件详情

    :param part_number: 配件编号
    :return: 配件字典，如果不存在则返回None
    """
    try:
        # 先获取配置
        tax_rate = 1.13
        discount_rate = 0.83
        try:
            config = get_config_value('mercedes_benz')
            if config and isinstance(config, dict):
                tax_rate = config.get('tax_rate', 1.13)
                discount_rate = config.get('discount_rate', 0.83)
        except Exception:
            pass

        with orm_session() as session:
            # 直接使用 session.query 查询
            part = session.query(CarPartsLibraryBenz).filter(
                CarPartsLibraryBenz.part_number == part_number
            ).first()
            
            if part:
                return part.to_web_dict(tax_rate, discount_rate)
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
        # 先获取配置
        tax_rate = 1.13
        discount_rate = 0.87
        try:
            config = get_config_value('mercedes_benz')
            if config and isinstance(config, dict):
                tax_rate = config.get('tax_rate', 1.13)
                discount_rate = config.get('discount_rate', 0.87)
        except Exception:
            pass

        with orm_session() as session:
            # 检查是否有查询条件，没有则直接返回
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
            items = query.order_by(CarPartsLibraryBenz.part_number.asc(), CarPartsLibraryBenz.updated_at.desc()).offset(offset).limit(page_size).all()
            
            # 转换为字典列表
            data = []
            for item in items:
                data.append(item.to_web_dict(tax_rate, discount_rate))

            print(f"从数据库查询到 {len(data)} 条配件数据，共 {total} 条")
            return {'status': True, 'msg': '查询成功', 'count': total, 'data': data}

    except Exception as e:
        print(f"从数据库查询配件列表失败: {str(e)}")
        return {'status': False, 'msg': f"查询配件列表失败: {str(e)}", 'count': 0, 'data': []}





def data_refresh(part_numbers: List[str]) -> Dict:
    """
    根据配件编号列表刷新数据
    
    :param part_numbers: 配件编号列表
    :return: 包含状态、消息和统计信息的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'parts_count': 0, 'stock_count': 0}
        
        fetch_mercedes_data_result = fetch_mercedes_data(part_numbers)
        get_crmapp_compare_summary_result = get_crmapp_compare_summary(part_numbers)

        parts_count = fetch_mercedes_data_result.get("parts_count", 0)
        stock_count = fetch_mercedes_data_result.get("stock_count", 0)

        if fetch_mercedes_data_result.get('status') and get_crmapp_compare_summary_result:
            return {
                'status': True, 
                'msg': f'🎉 数据刷新成功！成功更新了 {len(part_numbers)} 个配件，包含 {parts_count} 条零件信息和 {stock_count} 条库存信息', 
                'parts_count': parts_count, 
                'stock_count': stock_count
            }
        else:
            return {
                'status': False, 
                'msg': f'❌ 数据刷新失败！涉及 {len(part_numbers)} 个配件，零件信息 {parts_count} 条，库存信息 {stock_count} 条，请检查配置或网络连接', 
                'parts_count': parts_count, 
                'stock_count': stock_count
            }
    except Exception as e:
        msg = f"💥 批量刷新数据异常: {str(e)}"
        print(msg)
        return {'status': False, 'msg': msg, 'parts_count': 0, 'stock_count': 0}


def get_crmapp_compare_summary(oe_list: List[str], vehicle_brand: str = '奔驰', company: str = 'fsbbr') -> bool:
    """
    根据OE号列表、品牌和公司/门店代码查询比价数据，并更新CarPartsLibraryBenz表的字段

    :param oe_list: OE号列表
    :param vehicle_brand: 品牌（可选）
    :param company: 公司/门店代码（可选）
    :return: 布尔值，True表示操作成功
    """
    try:
        with orm_session() as session:
            # 处理OE号，去掉前面的大写字母A
            processed_oe_list = [re.sub(r'^A', '', oe) for oe in oe_list]
            
            # 构建查询 - 使用GROUP BY和MAX()去重
            query = session.query(
                CrmappCompareSummary.oe,
                func.max(CrmappCompareSummary.product_name).label('product_name'),
                func.max(CrmappCompareSummary.l_model_zh).label('l_model_zh'),
                func.max(CrmappCompareSummary.vehicle_brand).label('vehicle_brand')
            )
            
            # 添加OE号筛选（使用处理后的OE号）
            if processed_oe_list:
                query = query.filter(CrmappCompareSummary.oe.in_(processed_oe_list))
            
            # 添加品牌筛选
            if vehicle_brand:
                query = query.filter(CrmappCompareSummary.vehicle_brand == vehicle_brand)
            
            # 添加公司筛选
            if company:
                query = query.filter(CrmappCompareSummary.company == company)
            
            # 添加brand条件筛选：只查询原厂或原厂国内4s件
            query = query.filter(CrmappCompareSummary.brand.in_(['原厂', '原厂国内4s件']))
            
            # 添加GROUP BY
            query = query.group_by(CrmappCompareSummary.oe)
            
            # 执行查询
            results = query.all()
            
            # 转换为字典，key为处理后的OE号，value为包含所需字段的字典
            result_dict: Dict[str, Dict[str, Optional[str]]] = {}
            for row in results:
                result_dict[row.oe] = {
                    'product_name': row.product_name,
                    'l_model_zh': row.l_model_zh,
                    'vehicle_brand': row.vehicle_brand
                }
            
            # 更新CarPartsLibraryBenz表的字段
            for original_oe in oe_list:
                # 处理当前OE号
                processed_oe = re.sub(r'^A', '', original_oe)
                
                # 检查是否有对应的比价数据
                if processed_oe not in result_dict:
                    continue
                
                compare_result = result_dict[processed_oe]
                
                # 根据原始OE号查找CarPartsLibraryBenz记录
                benz_part = session.query(CarPartsLibraryBenz).filter(
                    CarPartsLibraryBenz.part_number == original_oe
                ).first()
                
                if benz_part:
                    # 更新description_cn字段（从product_name）
                    if compare_result['product_name']:
                        benz_part.description_cn = compare_result['product_name']  # pyright: ignore[reportAttributeAccessIssue]
                    
                    # 更新l_model_zh字段
                    if compare_result['l_model_zh']:
                        benz_part.l_model_zh = compare_result['l_model_zh']  # pyright: ignore[reportAttributeAccessIssue]

            return True
    except Exception as e:
        print(f"查询比价数据更新配件库失败: {str(e)}")
        return False



def set_mercedes_config(
    cookie: str, customer_id: str, sales_organization_id: str, 
    tax_rate: float = 1.13, discount_rate: float = 0.87, 
    column_config: Optional[Dict] = None, 
    favorite_column_config: Optional[Dict] = None,
    column_order: Optional[List[str]] = None,
    favorite_column_order: Optional[List[str]] = None
) -> Dict:
    """
    设置奔驰大库配置

    :param cookie: Cookie 字符串
    :param customer_id: 客户ID
    :param sales_organization_id: 销售组织ID
    :param tax_rate: 税率，默认 1.13
    :param discount_rate: 折扣率，默认 0.83
    :param column_config: 配件列表列配置（可选）
    :param favorite_column_config: 收藏列表列配置（可选）
    :param column_order: 配件列表列顺序（可选）
    :param favorite_column_order: 收藏列表列顺序（可选）
    :return: 设置结果
    """
    try:
        # 获取现有配置
        existing_config = get_mercedes_config() or {}
        
        # 构建新配置
        config_dict = {
            'cookie': cookie,
            'customer_id': customer_id,
            'sales_organization_id': sales_organization_id,
            'tax_rate': tax_rate,
            'discount_rate': discount_rate
        }
        
        # 如果有列配置，添加到配置中；否则保留现有的列配置
        if column_config is not None:
            config_dict['column_config'] = column_config
        else:
            config_dict['column_config'] = existing_config.get('column_config')
        
        # 如果有收藏列表列配置，添加到配置中；否则保留现有的收藏列配置
        if favorite_column_config is not None:
            config_dict['favorite_column_config'] = favorite_column_config
        else:
            config_dict['favorite_column_config'] = existing_config.get('favorite_column_config')
        
        # 如果有列顺序配置，添加到配置中；否则保留现有的列顺序
        if column_order is not None:
            config_dict['column_order'] = column_order
        else:
            config_dict['column_order'] = existing_config.get('column_order')
        
        # 如果有收藏列表列顺序配置，添加到配置中；否则保留现有的
        if favorite_column_order is not None:
            config_dict['favorite_column_order'] = favorite_column_order
        else:
            config_dict['favorite_column_order'] = existing_config.get('favorite_column_order')
        
        # 将配置保存为 JSON 格式
        config_value = json.dumps(config_dict, ensure_ascii=False)
        
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




def add_part(part_data: dict) -> dict:
    """
    添加配件
    :param part_data: 配件数据字典
    :return: 操作结果
    """
    try:
        with orm_session() as session:
            # 检查配件编号是否已存在
            existing_part = session.query(CarPartsLibraryBenz).filter(
                CarPartsLibraryBenz.part_number == part_data.get('part_number')
            ).first()

            if existing_part:
                return {
                    'status': False,
                    'msg': '配件编号已存在'
                }

            # 创建新配件对象
            new_part = CarPartsLibraryBenz()

            # 填充数据
            for key, value in part_data.items():
                if hasattr(new_part, key):
                    setattr(new_part, key, value)

            # 设置数据来源
            new_part.data_source = 'manual'  # pyright: ignore[reportAttributeAccessIssue]

            session.add(new_part)
            session.commit()

            return {
                'status': True,
                'msg': '添加成功'
            }
    except Exception as e:
        print(f"添加配件失败: {str(e)}")
        return {
            'status': False,
            'msg': f'添加失败: {str(e)}'
        }


def update_part(part_number: str, part_data: dict) -> dict:
    """
    更新配件
    :param part_number: 配件编号
    :param part_data: 更新的数据字典
    :return: 操作结果
    """
    try:
        with orm_session() as session:
            # 查找配件
            part = session.query(CarPartsLibraryBenz).filter(
                CarPartsLibraryBenz.part_number == part_number
            ).first()

            if not part:
                return {
                    'status': False,
                    'msg': '配件不存在'
                }

            # 更新数据
            for key, value in part_data.items():
                if hasattr(part, key) and key != 'part_number':  # 不允许修改配件编号
                    setattr(part, key, value)

            session.commit()

            return {
                'status': True,
                'msg': '更新成功'
            }
    except Exception as e:
        print(f"更新配件失败: {str(e)}")
        return {
            'status': False,
            'msg': f'更新失败: {str(e)}'
        }


def delete_part(part_number: str) -> dict:
    """
    删除配件
    :param part_number: 配件编号
    :return: 操作结果
    """
    try:
        with orm_session() as session:
            # 查找配件
            part = session.query(CarPartsLibraryBenz).filter(
                CarPartsLibraryBenz.part_number == part_number
            ).first()

            if not part:
                return {
                    'status': False,
                    'msg': '配件不存在'
                }

            session.delete(part)
            session.commit()

            return {
                'status': True,
                'msg': '删除成功'
            }
    except Exception as e:
        print(f"删除配件失败: {str(e)}")
        return {
            'status': False,
            'msg': f'删除失败: {str(e)}'
        }


def import_parts(file_obj, filename) -> Dict:
    """
    批量导入配件数据（插入更新模式）

    :param file_obj: 文件对象
    :param filename: 文件名
    :return: 包含统计信息的字典
    """
    try:
        dao = CarPartsLibraryBenzDao()
        stats = process_file_stream(file_obj, filename, dao)

        msg = f'导入完成！共处理 {stats["total"]} 条数据，成功 {stats["success"]} 条，失败 {stats["failed"]} 条'

        return {
            'status': True,
            'msg': msg,
            'data': stats
        }
    except Exception as e:
        msg = f'导入失败: {str(e)}'
        print(msg)
        return {
            'status': False,
            'msg': msg,
            'data': {
                'total': 0,
                'success': 0,
                'failed': 0,
                'errors': [{'error': str(e)}],
                'success_part_numbers': []
            }
        }


def download_template():
    """
    下载Excel导入模板

    :return: BytesIO对象，包含Excel模板
    """
    try:
        return generate_template()
    except Exception as e:
        print(f'生成模板失败: {str(e)}')
        raise


# if __name__ == '__main__':
#     a=data_list_page_refresh(part_number='8201245')
#     print(a)
