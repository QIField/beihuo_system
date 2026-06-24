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


def move_bmw_to_main_category(part_numbers: List[str], source_category: Optional[str] = None, operator_user_id: Optional[int] = None) -> Dict:
    """
    批量将收藏从指定分类移动到宝马主收藏

    :param part_numbers: 配件编号列表
    :param source_category: 来源分类，如果为None则从所有非宝马主收藏分类移动
    :param operator_user_id: 操作人用户ID（可为None，仅作记录）
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'moved_count': 0, 'deleted_count': 0}

        # 记录移动成功数与重复删除数
        moved_count = 0
        deleted_count = 0

        with orm_session() as session:
            try:
                # 第一步：查出当前已存在于"宝马主收藏"中的配件编号
                # 目的：如果这些配件同时还出现在其他分类里，其他分类的条目需要删除
                # （否则同一 part_number 会在"宝马主收藏"和其他分类下同时出现）
                existing_in_main = session.query(CarPartsFavorite.part_number).filter(
                    CarPartsFavorite.part_number.in_(part_numbers),
                    CarPartsFavorite.category == '宝马主收藏'
                ).all()
                existing_part_numbers = [item[0] for item in existing_in_main]

                # 第二步：对于已存在于"宝马主收藏"的 part_number，
                # 把它们在来源分类（或所有非宝马主收藏分类）中的条目删掉，
                # 避免同一个配件既在主收藏里又在其他分类里出现
                if existing_part_numbers:
                    query = session.query(CarPartsFavorite).filter(
                        CarPartsFavorite.part_number.in_(existing_part_numbers)
                    )
                    if source_category:
                        # 若指定了来源分类，则只删该来源分类下的重复
                        query = query.filter(CarPartsFavorite.category == source_category)
                    else:
                        # 否则删除所有非"宝马主收藏"分类下的相同 part_number 记录
                        query = query.filter(CarPartsFavorite.category != '宝马主收藏')
                    deleted_result = query.delete(synchronize_session=False)
                    deleted_count = deleted_result

                # 第三步：剩下的 part_number（当前还不存在于宝马主收藏）
                # 直接把它们的 category 更新为"宝马主收藏"
                parts_to_move = [pn for pn in part_numbers if pn not in existing_part_numbers]
                if parts_to_move:
                    query = session.query(CarPartsFavorite).filter(
                        CarPartsFavorite.part_number.in_(parts_to_move)
                    )
                    if source_category:
                        # 若指定了来源分类，只移动该分类下的条目
                        query = query.filter(CarPartsFavorite.category == source_category)
                    else:
                        # 否则把所有非"宝马主收藏"分类下的对应条目都改为宝马主收藏
                        query = query.filter(CarPartsFavorite.category != '宝马主收藏')
                    # 更新 category 字段（同时刷新操作者 user_id）
                    move_result = query.update(
                        {'category': '宝马主收藏', 'user_id': operator_user_id},
                        synchronize_session=False
                    )
                    moved_count = move_result

                session.commit()
            except Exception:
                session.rollback()
                raise

        msg_parts = []
        if moved_count > 0:
            msg_parts.append(f'移动 {moved_count} 个')
        if deleted_count > 0:
            msg_parts.append(f'删除重复 {deleted_count} 个')

        return {
            'status': True,
            'msg': f'移动成功！{", ".join(msg_parts)}收藏到宝马主收藏',
            'moved_count': moved_count,
            'deleted_count': deleted_count
        }
    except Exception as e:
        msg = f'移动失败: {str(e)}'
        print(msg)
        return {'status': False, 'msg': msg, 'moved_count': 0, 'deleted_count': 0}


def copy_bmw_to_main_category(part_numbers: List[str], operator_user_id: Optional[int] = None) -> Dict:
    """
    批量复制收藏到宝马主收藏（保持原分类不变）

    :param part_numbers: 配件编号列表
    :param operator_user_id: 操作人用户ID（可为None，仅作记录）
    :return: 包含操作结果的字典
    """
    try:
        if not part_numbers or len(part_numbers) == 0:
            return {'status': False, 'msg': '配件编号列表不能为空', 'copied_count': 0, 'exists_count': 0}

        copied_count = 0
        exists_count = 0

        with orm_session() as session:
            for part_number in part_numbers:
                existing = session.query(CarPartsFavorite).filter(
                    CarPartsFavorite.part_number == part_number,
                    CarPartsFavorite.category == '宝马主收藏'
                ).first()

                if existing:
                    exists_count += 1
                else:
                    new_favorite = CarPartsFavorite(
                        user_id=operator_user_id,
                        part_number=part_number,
                        category='宝马主收藏',
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
