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
from app.models.orm_models.car_parts_library_benz_stock import CarPartsLibraryBenzStock
from app.models.orm_models.crmapp_compare_summary import CrmappCompareSummary
from app.services.car_parts_library_service.mercedes_dalfsc_service import fetch_mercedes_data
from app.services.car_parts_library_service.excel_import_service import process_file_stream, generate_template
from app.utils.orm.session import orm_session
from app.dao.car_parts_library_benz_dao import CarPartsLibraryBenzDao
from app.services.system_setting_service.beihuo_system_config_service import set_config_by_key, update_json_config
from config.config_list_manager.config_cache import get_config_value
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func
import json
import re

def get_part_by_number(part_number: str) -> Optional[Dict]:
    """
    根据配件编号获取配件详情（包含库存信息）

    :param part_number: 配件编号
    :return: 配件字典，如果不存在则返回None，包含stock_info字段
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

        with orm_session() as session:  # pyright: ignore[reportGeneralTypeIssues]
            # 直接使用 session.query 查询
            part = session.query(CarPartsLibraryBenz).filter(
                CarPartsLibraryBenz.part_number == part_number
            ).first()
            
            if part:
                # 查询库存信息
                stock_items = session.query(CarPartsLibraryBenzStock).filter(
                    CarPartsLibraryBenzStock.part_number == part_number
                ).all()
                
                # 将库存信息转换为字典列表
                stock_info_list = [item.to_dict() for item in stock_items]
                
                # 获取配件基本信息
                part_dict = part.to_web_dict(tax_rate, discount_rate)
                
                # 合并数据
                result = {
                    **part_dict,
                    'stock_info': stock_info_list
                }
                
                return result
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
            oe_list=[]
            for item in items:
                oe=re.sub(r'^A', '', item.part_number)  # pyright: ignore[reportCallIssue, reportArgumentType]
                oe_list.append(oe)

                # 转换为字典，并附带oe字段用于后续匹配
                item_dict = item.to_web_dict(tax_rate, discount_rate)
                item_dict['oe'] = oe  # 添加oe字段，用于匹配备货数据
                data.append(item_dict)

            ## 使用oe_list在crmapp_beihuo搜索数据，并合并到data中
            beihuo_data_dict = get_crmapp_beihuo_data(oe_list)
            for item in data:
                oe_key = item.get('oe', '')
                item['beihuo_data'] = beihuo_data_dict.get(oe_key, [])  # pyright: ignore[reportOptionalMemberAccess]
            




            print(f"从数据库查询到 {len(data)} 条配件数据，共 {total} 条")
            return {'status': True, 'msg': '查询成功', 'count': total, 'data': data}

    except Exception as e:
        print(f"从数据库查询配件列表失败: {str(e)}")
        return {'status': False, 'msg': f"查询配件列表失败: {str(e)}", 'count': 0, 'data': []}





def get_crmapp_beihuo_data(oe_list):
    """
    根据OE号列表查询备货数据（crmapp_beihuo表）
    返回按OE分组的字典结构，一个OE对应多个地区(company)的数据列表

    :param oe_list: OE号列表
    :return: 字典，key为OE号，value为该OE下所有地区的备货数据列表；查询失败返回空字典

    返回格式示例:
    {
        "1665000075": [
            {"brand": "原厂", "model_brand": "奔驰", "company": "fsbbr", "stock_quantity": 3, ...},
            {"brand": "原厂", "model_brand": "奔驰", "company": "dghf", "stock_quantity": 1, ...}
        ],
        "2642004201": [...]
    }
    """
    from collections import defaultdict

    try:
        # 参数校验：OE列表为空时直接返回空字典
        if not oe_list:
            return None

        with orm_session() as session:  # pyright: ignore[reportGeneralTypeIssues]
            # 导入CrmappBeihuo模型（局部导入避免循环依赖）
            from app.models.orm_models.crmapp_beihuo import CrmappBeihuo

            # 根据OE号列表批量查询备货数据（奔驰 + 原厂品牌筛选）
            results = session.query(CrmappBeihuo).filter(
                CrmappBeihuo.oe.in_(oe_list),
                CrmappBeihuo.car_model_brand == '奔驰',  # 筛选奔驰车型品牌
                CrmappBeihuo.brand.in_(['原厂国内4s件', '原厂']),  # 筛选原厂品牌
            ).all()

            # 按OE号分组，使用defaultdict自动创建列表
            oe_grouped: Dict[str, List[Dict]] = defaultdict(list)
            for item in results:
                item_dict = {
                    'company': item.company,
                    'stock_quantity': item.stock_quantity,
                    'brand': item.brand,
                    'model_brand': item.car_model_brand,
                }  # pyright: ignore[reportArgumentType]



                oe_grouped[item.oe].append(item_dict)  # pyright: ignore[reportArgumentType]

            print(f"根据OE列表查询到 {len(oe_grouped)} 个OE，共 {len(results)} 条数据")
            return dict(oe_grouped)

    except Exception as e:
        print(f"查询备货数据失败: {str(e)}")
        return None

# if __name__ == '__main__':
#     oe_list=['2642004201','1665000875','1665000075','2742003100']
#     result=get_crmapp_beihuo_data(oe_list)
#     print(result)
    
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
