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


def get_user_favorite_categories(user_id: int) -> Dict:
    """
    获取用户的所有收藏分类

    :param user_id: 用户ID
    :return: 包含分类列表的字典
    """
    try:
        with orm_session() as session:
            # 查询该用户的所有不重复的分类
            categories = session.query(CarPartsFavorite.category).filter(
                CarPartsFavorite.user_id == user_id
            ).distinct().all()
            
            # 转换为列表
            category_list = [cat[0] for cat in categories]
            
            # 如果没有分类，添加默认的"主收藏"
            if not category_list:
                category_list = ['主收藏']
            
            return {'status': True, 'msg': '获取成功', 'categories': category_list}
    except Exception as e:
        msg = f'获取收藏分类失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'categories': ['主收藏']}


def batch_add_to_favorites(user_id: int, part_numbers: List[str], category: str = '主收藏') -> Dict:
    """
    批量添加配件到收藏夹（优化版本，适用于大量数据）

    :param user_id: 用户ID
    :param part_numbers: 配件编号列表
    :param category: 分类，默认为'主收藏'
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'added_count': 0, 'exists_count': 0}
        
        # 去重
        part_numbers = list(set(part_numbers))
        
        BATCH_SIZE = 5000
        added_count = 0
        
        with orm_session() as session:
            from datetime import datetime
            # 分批插入
            for i in range(0, len(part_numbers), BATCH_SIZE):
                batch = part_numbers[i:i + BATCH_SIZE]
                # 批量构建收藏对象
                favorites_to_add = [
                    CarPartsFavorite(
                        user_id=user_id,
                        part_number=part_number,
                        category=category,
                        created_at=datetime.now()
                    )
                    for part_number in batch
                ]
                # 批量添加
                session.bulk_save_objects(favorites_to_add)
                session.commit()
                added_count += len(batch)
        
        return {
            'status': True,
            'msg': f'收藏成功！新增 {added_count} 个',
            'added_count': added_count,
            'exists_count': 0
        }
    except Exception as e:
        msg = f'收藏失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'added_count': 0, 'exists_count': 0}


def move_to_main_category(user_id: int, part_numbers: List[str], source_category: Optional[str] = None) -> Dict:
    """
    批量将收藏从指定分类移动到主收藏

    :param user_id: 用户ID
    :param part_numbers: 配件编号列表
    :param source_category: 来源分类，如果为None则从所有非主收藏分类移动
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'moved_count': 0, 'deleted_count': 0}

        moved_count = 0
        deleted_count = 0

        with orm_session() as session:
            try:
                # 先对用户加锁，确保同一用户的请求串行执行
                # 尝试获取该用户的任意一条收藏记录加锁，如果没有则不影响
                # lock_query = session.query(CarPartsFavorite.id).filter(
                #     CarPartsFavorite.user_id == user_id
                # ).order_by(CarPartsFavorite.id.asc()).limit(1).with_for_update().first()

                # 第一步：找出在主收藏中已存在的配件
                existing_in_main = session.query(CarPartsFavorite.part_number).filter(
                    CarPartsFavorite.user_id == user_id,
                    CarPartsFavorite.part_number.in_(part_numbers),
                    CarPartsFavorite.category == '主收藏'
                ).all()
                existing_part_numbers = [item[0] for item in existing_in_main]

                # 第二步：对于主收藏已存在的配件，直接删除来源分类的记录
                if existing_part_numbers:
                    query = session.query(CarPartsFavorite).filter(
                        CarPartsFavorite.user_id == user_id,
                        CarPartsFavorite.part_number.in_(existing_part_numbers)
                    )
                    if source_category:
                        query = query.filter(CarPartsFavorite.category == source_category)
                    else:
                        query = query.filter(CarPartsFavorite.category != '主收藏')
                    deleted_result = query.delete(synchronize_session=False)
                    deleted_count = deleted_result

                # 第三步：对于主收藏不存在的配件，执行移动操作
                parts_to_move = [pn for pn in part_numbers if pn not in existing_part_numbers]
                if parts_to_move:
                    query = session.query(CarPartsFavorite).filter(
                        CarPartsFavorite.user_id == user_id,
                        CarPartsFavorite.part_number.in_(parts_to_move)
                    )
                    if source_category:
                        query = query.filter(CarPartsFavorite.category == source_category)
                    else:
                        query = query.filter(CarPartsFavorite.category != '主收藏')
                    move_result = query.update(
                        {'category': '主收藏'},
                        synchronize_session=False
                    )
                    moved_count = move_result

                session.commit()
            except Exception:
                # 发生异常时回滚事务，确保锁被释放
                session.rollback()
                raise

        msg_parts = []
        if moved_count > 0:
            msg_parts.append(f'移动 {moved_count} 个')
        if deleted_count > 0:
            msg_parts.append(f'删除重复 {deleted_count} 个')

        return {
            'status': True,
            'msg': f'移动成功！{", ".join(msg_parts)}收藏到主收藏',
            'moved_count': moved_count,
            'deleted_count': deleted_count
        }
    except Exception as e:
        msg = f'移动失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'moved_count': 0, 'deleted_count': 0}


def copy_to_main_category(user_id: int, part_numbers: List[str]) -> Dict:
    """
    批量复制收藏到主收藏（保持原分类不变）

    :param user_id: 用户ID
    :param part_numbers: 配件编号列表
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'copied_count': 0, 'exists_count': 0}
        
        copied_count = 0
        exists_count = 0
        
        with orm_session() as session:
            for part_number in part_numbers:
                # 检查主收藏中是否已存在
                existing = session.query(CarPartsFavorite).filter(
                    CarPartsFavorite.user_id == user_id,
                    CarPartsFavorite.part_number == part_number,
                    CarPartsFavorite.category == '主收藏'
                ).first()
                
                if existing:
                    exists_count += 1
                else:
                    # 添加新的主收藏记录
                    new_favorite = CarPartsFavorite(
                        user_id=user_id,
                        part_number=part_number,
                        category='主收藏',
                    )
                    session.add(new_favorite)
                    copied_count += 1
            
            session.commit()
        
        return {
            'status': True,
            'msg': f'复制成功！新增 {copied_count} 个，已存在 {exists_count} 个',
            'copied_count': copied_count,
            'exists_count': exists_count
        }
    except Exception as e:
        msg = f'复制失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'copied_count': 0, 'exists_count': 0}


def clear_category_favorites(user_id: int, category: str) -> Dict:
    """
    清空指定分类下的所有收藏

    :param user_id: 用户ID
    :param category: 分类名称
    :return: 包含操作结果的字典
    """
    try:
        if not category:
            return {'status': False, 'msg': '分类名称不能为空', 'cleared_count': 0}
        
        cleared_count = 0
        
        with orm_session() as session:
            # 删除指定分类下的所有收藏
            result = session.query(CarPartsFavorite).filter(
                CarPartsFavorite.user_id == user_id,
                CarPartsFavorite.category == category
            ).delete(synchronize_session=False)
            
            cleared_count = result
            session.commit()
        
        return {
            'status': True,
            'msg': f'清空成功！共删除 {cleared_count} 个收藏',
            'cleared_count': cleared_count
        }
    except Exception as e:
        msg = f'清空失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'cleared_count': 0}
