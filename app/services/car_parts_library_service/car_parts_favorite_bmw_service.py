# -*- coding:utf-8 -*-
# @Time    : 2026/06/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_favorite_bmw_service.py
# @Software: trae-cn

"""
华晨宝马配件收藏服务层
负责处理宝马配件收藏的业务逻辑
数据同样存储在 car_parts_favorite 表中，通过 category='宝马主收藏' 区分
"""

from app.models.orm_models.car_parts_library_bmw import CarPartsLibraryBmw
from app.models.orm_models.car_parts_favorite import CarPartsFavorite
from app.utils.orm.session import orm_session
from typing import Dict, List, Optional


def add_bmw_to_favorites(user_id: Optional[int], part_numbers: List[str], category: str = '宝马主收藏') -> Dict:
    """
    批量添加宝马配件到收藏夹

    :param user_id: 收藏人/操作人用户ID（可为None）
    :param part_numbers: 配件编号列表
    :param category: 分类，默认为'宝马主收藏'
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'added_count': 0, 'exists_count': 0}

        added_count = 0
        exists_count = 0

        with orm_session() as session:
            for part_number in part_numbers:
                # 检查是否已收藏（按配件编号+分类）
                existing = session.query(CarPartsFavorite).filter(
                    CarPartsFavorite.part_number == part_number,
                    CarPartsFavorite.category == category
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


def get_bmw_favorites(category: Optional[str] = '宝马主收藏', page: int = 1, page_size: int = 10) -> Optional[Dict]:
    """
    获取宝马收藏列表（分页），JOIN 宝马配件表

    :param category: 分类筛选（可选），默认'宝马主收藏'
    :param page: 页码，默认1
    :param page_size: 每页条数，默认10
    :return: 包含状态、消息、总数和数据列表的字典
    """
    try:
        with orm_session() as session:
            # JOIN 宝马配件表
            query = session.query(
                CarPartsFavorite,
                CarPartsLibraryBmw
            ).join(
                CarPartsLibraryBmw,
                CarPartsFavorite.part_number == CarPartsLibraryBmw.part_number
            )

            # 如果指定了分类，添加分类筛选
            if category:
                query = query.filter(CarPartsFavorite.category == category)

            # 获取总条数
            total = query.count()

            # 分页查询
            offset = (page - 1) * page_size
            favorites = query.order_by(
                CarPartsFavorite.created_at.desc(),
                CarPartsFavorite.id.desc()
            ).offset(offset).limit(page_size).all()

            result = []
            for favorite, part in favorites:
                part_dict = part.to_dict()
                part_dict['favorite_id'] = favorite.id
                part_dict['favorite_category'] = favorite.category
                part_dict['favorite_created_at'] = favorite.created_at
                part_dict['favorite_user_id'] = favorite.user_id
                result.append(part_dict)

            print(f'从数据库查询到 {len(result)} 条宝马收藏数据，共 {total} 条')
            return {'status': True, 'msg': '获取成功', 'count': total, 'data': result}
    except Exception as e:
        print(f'获取宝马收藏列表失败: {str(e)}')
        return {'status': False, 'msg': f'获取宝马收藏列表失败: {str(e)}', 'count': 0, 'data': []}


def remove_bmw_from_favorites(part_numbers: List[str], category: Optional[str] = '宝马主收藏') -> Dict:
    """
    批量从收藏夹删除宝马配件

    :param part_numbers: 配件编号列表
    :param category: 分类筛选（可选），不传则按配件编号删除所有分类下的该配件
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'removed_count': 0}

        removed_count = 0

        with orm_session() as session:
            query = session.query(CarPartsFavorite).filter(
                CarPartsFavorite.part_number.in_(part_numbers)
            )
            if category:
                query = query.filter(CarPartsFavorite.category == category)
            result = query.delete(synchronize_session=False)

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


def get_bmw_favorite_categories() -> Dict:
    """
    获取所有宝马相关的收藏分类（分类名中包含'宝马'）

    :return: 包含分类列表的字典
    """
    try:
        with orm_session() as session:
            categories = session.query(CarPartsFavorite.category).distinct().all()

            # 只保留宝马相关的分类（excel_bmw_ 前缀文件上传 + 宝马主收藏）
            category_list = [
                cat[0] for cat in categories
                if cat[0] and (str(cat[0]).startswith('excel_bmw_') or '宝马' in str(cat[0]))
            ]

            # 如果没有分类，添加默认的"宝马主收藏"
            if not category_list:
                category_list = ['宝马主收藏']

            return {'status': True, 'msg': '获取成功', 'categories': category_list}
    except Exception as e:
        msg = f'获取收藏分类失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'categories': ['宝马主收藏']}


def clear_bmw_category_favorites(category: str) -> Dict:
    """
    清空指定宝马分类下的所有收藏

    :param category: 分类名称
    :return: 包含操作结果的字典
    """
    try:
        if not category:
            return {'status': False, 'msg': '分类名称不能为空', 'cleared_count': 0}

        cleared_count = 0

        with orm_session() as session:
            result = session.query(CarPartsFavorite).filter(
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
