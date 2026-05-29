# -*- coding:utf-8 -*-
# @Time    : 2026/05/26 14:26
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_favorite_service.py
# @Software: trae-cn

"""
汽车配件收藏服务层
负责处理配件收藏的业务逻辑
"""

from app.models.orm_models.car_parts_library_benz import CarPartsLibraryBenz
from app.models.orm_models.car_parts_favorite import CarPartsFavorite
from app.utils.orm.session import orm_session
from config.config_list_manager.config_cache import get_config_value
from typing import Dict, List, Optional


def add_to_favorites(user_id: int, part_numbers: List[str], category: str = '主收藏') -> Dict:
    """
    批量添加配件到收藏夹

    :param user_id: 用户ID
    :param part_numbers: 配件编号列表
    :param category: 分类，默认为'主收藏'
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'added_count': 0, 'exists_count': 0}
        
        added_count = 0
        exists_count = 0
        
        with orm_session() as session:
            for part_number in part_numbers:
                # 检查是否已收藏
                existing = session.query(CarPartsFavorite).filter(
                    CarPartsFavorite.user_id == user_id,
                    CarPartsFavorite.part_number == part_number
                ).first()
                
                if existing:
                    exists_count += 1
                else:
                    # 添加新收藏
                    new_favorite = CarPartsFavorite(
                        user_id=user_id,
                        part_number=part_number,
                        category=category
                    )
                    session.add(new_favorite)
                    added_count += 1
            
            session.commit()
        
        return {
            'status': True,
            'msg': f'收藏成功！新增 {added_count} 个，已存在 {exists_count} 个',
            'added_count': added_count,
            'exists_count': exists_count
        }
    except Exception as e:
        msg = f'收藏失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'added_count': 0, 'exists_count': 0}


def get_user_favorites(user_id: int, category: Optional[str] = '主收藏', page: int = 1, page_size: int = 10) -> Optional[Dict]:
    """
    获取用户收藏列表（分页）

    :param user_id: 用户ID
    :param category: 分类筛选（可选），如果不传则返回所有分类
    :param page: 页码，默认1
    :param page_size: 每页条数，默认10
    :return: 包含状态、消息、总数和数据列表的字典，如果失败则返回None
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
            # 构建查询
            query = session.query(
                CarPartsFavorite,
                CarPartsLibraryBenz
            ).join(
                CarPartsLibraryBenz,
                CarPartsFavorite.part_number == CarPartsLibraryBenz.part_number
            ).filter(
                CarPartsFavorite.user_id == user_id
            )
            
            # 如果指定了分类，添加分类筛选
            if category:
                query = query.filter(CarPartsFavorite.category == category)
            
            # 获取总条数
            total = query.count()
            
            # 分页查询
            offset = (page - 1) * page_size
            favorites = query.order_by(
                CarPartsLibraryBenz.part_number.desc()
            ).offset(offset).limit(page_size).all()
            
            result = []
            for favorite, part in favorites:
                part_dict = part.to_web_dict(tax_rate, discount_rate)
                part_dict['favorite_id'] = favorite.id
                part_dict['favorite_category'] = favorite.category
                part_dict['favorite_created_at'] = favorite.created_at
                result.append(part_dict)
            
            print(f'从数据库查询到 {len(result)} 条收藏数据，共 {total} 条')
            return {'status': True, 'msg': '获取成功', 'count': total, 'data': result}
    except Exception as e:
        print(f'获取收藏列表失败: {str(e)}')
        return {'status': False, 'msg': f'获取收藏列表失败: {str(e)}', 'count': 0, 'data': []}


def remove_from_favorites(user_id: int, part_numbers: List[str]) -> Dict:
    """
    批量从收藏夹删除配件

    :param user_id: 用户ID
    :param part_numbers: 配件编号列表
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'removed_count': 0}
        
        removed_count = 0
        
        with orm_session() as session:
            result = session.query(CarPartsFavorite).filter(
                CarPartsFavorite.user_id == user_id,
                CarPartsFavorite.part_number.in_(part_numbers)
            ).delete(synchronize_session=False)
            
            removed_count = result
            session.commit()
        
        return {
            'status': True,
            'msg': f'删除成功！共删除 {removed_count} 个收藏',
            'removed_count': removed_count
        }
    except Exception as e:
        msg = f'删除收藏失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'removed_count': 0}
