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

from app.models.orm_models.car_parts_library import CarPartsLibrary
from app.utils.orm.session import orm_session
from typing import Dict, List, Optional, Tuple


class CarPartsLibraryService:
    """
    汽车配件库服务类
    """

    @staticmethod
    def get_part_by_number(part_number: str) -> Optional[Dict]:
        """
        根据配件编号获取配件详情

        :param part_number: 配件编号
        :return: 配件字典，如果不存在则返回None
        """
        try:
            with orm_session() as session:
                # 直接使用 session.query 查询
                part = session.query(CarPartsLibrary).filter(
                    CarPartsLibrary.part_number == part_number
                ).first()
                
                if part:
                    return part.to_dict()
                return None
        except Exception as e:
            print(f"从数据库查询配件详情失败: {str(e)}")
            return None

    @staticmethod
    def get_parts_list(
        page: int = 1,
        page_size: int = 20,
        part_number: Optional[str] = None,
        description_cn: Optional[str] = None
    ) -> Tuple[int, List[Dict]]:
        """
        获取配件列表（分页）

        :param page: 页码，默认1
        :param page_size: 每页条数，默认20
        :param part_number: 配件编号筛选（可选）
        :param description_cn: 中文描述筛选（可选）
        :return: (总条数, 配件列表)
        """
        try:
            with orm_session() as session:
                # 构建查询
                query = session.query(CarPartsLibrary)
                
                # 添加筛选条件
                if part_number:
                    query = query.filter(CarPartsLibrary.part_number.like(f'%{part_number}%'))
                if description_cn:
                    query = query.filter(CarPartsLibrary.description_cn.like(f'%{description_cn}%'))
                
                # 获取总条数
                total = query.count()
                
                # 分页查询
                offset = (page - 1) * page_size
                items = query.order_by(CarPartsLibrary.updated_at.desc()).offset(offset).limit(page_size).all()
                
                # 转换为字典列表
                result = []
                for item in items:
                    result.append(item.to_dict())
                
                print(f"从数据库查询到 {len(result)} 条配件数据，共 {total} 条")
                return total, result
        except Exception as e:
            print(f"从数据库查询配件列表失败: {str(e)}")
            return 0, []

if __name__ == '__main__':

    pass
