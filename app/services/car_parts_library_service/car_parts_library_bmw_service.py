# -*- coding:utf-8 -*-


"""
华晨宝马（BMW Brilliance）零件库服务层
负责处理宝马配件库的查询、分页、刷新等业务逻辑
"""

from typing import Dict, List, Optional

from app.utils.orm.session import orm_session
from app.models.orm_models.car_parts_library_bmw import CarPartsLibraryBmw
from app.models.orm_models.car_parts_library_bmw_stock import CarPartsLibraryBmwStock
from app.services.car_parts_library_service.bmw_crawler import data_upsert
# ====================================================
# 接口一：根据零件号获取配件详情（含库存信息）
# ====================================================

def get_part_by_number(part_number: str) -> Optional[Dict]:
    """
    根据零件号获取配件详情（包含库存信息）

    流程：
      1. 从 car_parts_library_bmw 表查询零件基础信息
      2. 从 car_parts_library_bmw_stock 表查询多仓库库存信息
      3. 合并基础信息 + 库存信息后返回

    :param part_number: 零件号（OE号）
    :return: 包含基础信息与库存信息的字典；不存在或查询失败返回 None
    """
    try:
        if not part_number or not str(part_number).strip():
            return None

        oe_clean = str(part_number).strip()

        with orm_session() as session:
            # 查询零件基础信息
            part = session.query(CarPartsLibraryBmw).filter(
                CarPartsLibraryBmw.part_number == oe_clean
            ).first()

            if not part:
                return None

            # 查询库存信息（BMW 库存表以 part_number 为主键，一行记录包含所有仓库）
            stock = session.query(CarPartsLibraryBmwStock).filter(
                CarPartsLibraryBmwStock.part_number == oe_clean
            ).first()

            result = part.to_dict()
            result['stock_info'] = stock.to_dict() if stock else None

            return result

    except Exception as e:
        print(f"从数据库查询宝马配件详情失败: {str(e)}")
        return None


# ====================================================
# 接口二：分页查询零件列表（按零件号筛选）
# ====================================================

def get_parts_list_page(
    page: int = 1,
    page_size: int = 20,
    part_number: Optional[str] = None,
) -> Dict:
    """
    获取宝马配件列表（分页）

    流程：
      1. 校验查询条件（part_number 为空时不返回数据）
      2. 从 car_parts_library_bmw 表按 part_number 模糊查询
      3. 从 car_parts_library_bmw_stock 表批量查询库存信息
      4. 将基础信息、库存信息合并后返回

    :param page: 页码，默认 1
    :param page_size: 每页条数，默认 20
    :param part_number: 零件号筛选（可选，模糊匹配）
    :return: {'status': bool, 'msg': str, 'count': int, 'data': list}
    """
    try:
        # 1. 参数合法性检查
        if not part_number or not str(part_number).strip():
            return {'status': False, 'msg': '没有查询条件，不返回数据', 'count': 0, 'data': []}

        part_number = str(part_number).strip()

        with orm_session() as session:
            # 2. 构建基础查询（按 part_number 模糊匹配）
            query = session.query(CarPartsLibraryBmw).filter(
                CarPartsLibraryBmw.part_number.like(f'%{part_number}%')
            )

            # 3. 总数
            total = query.count()

            # 4. 分页查询当前页
            offset = (page - 1) * page_size
            items = query.order_by(
                CarPartsLibraryBmw.part_number.asc(),
                CarPartsLibraryBmw.updated_at.desc()
            ).offset(offset).limit(page_size).all()

            # 5. 收集当前页所有 part_number，批量查询库存信息
            part_numbers = [item.part_number for item in items if item.part_number]  # pyright: ignore[reportGeneralTypeIssues]

            # 5.1 批量查询库存信息（以 part_number 为 key）
            stock_dict: Dict[str, Dict] = {}
            if part_numbers:
                stock_items = session.query(CarPartsLibraryBmwStock).filter(
                    CarPartsLibraryBmwStock.part_number.in_(part_numbers)
                ).all()
                for stock in stock_items:
                    stock_dict[stock.part_number] = stock.to_dict()  # pyright: ignore[reportArgumentType]

            # 6. 组装数据
            data = []
            for item in items:
                item_dict = item.to_dict()
                item_dict['stock_info'] = stock_dict.get(item.part_number, None)  # pyright: ignore[reportCallIssue, reportArgumentType]
                data.append(item_dict)

            print(f"从数据库查询到 {len(data)} 条宝马配件数据，共 {total} 条")
            return {'status': True, 'msg': '查询成功', 'count': total, 'data': data}

    except Exception as e:
        print(f"从数据库查询宝马配件列表失败: {str(e)}")
        return {'status': False, 'msg': f'查询宝马配件列表失败: {str(e)}', 'count': 0, 'data': []}


# ====================================================
# 接口四：批量刷新零件数据（爬虫 + 入库）
# ====================================================

def data_refresh(part_numbers: List[str]) -> Dict:
    """
    根据零件号列表刷新宝马零件数据

    流程：
      1. 从系统配置获取 BMW Brilliance 的 cookie
      2. 对每个零件号调用 bmw_crawler.data_upsert：
         - 爬取库存信息（query_part_stock）并 upsert 到 car_parts_library_bmw_stock 表
         - 爬取详情信息（query_part_detail）并 upsert 到 car_parts_library_bmw 表
      3. 统计成功 / 失败数量，返回汇总结果

    :param part_numbers: 零件号列表
    :return: {'status': bool, 'msg': str, 'parts_count': int, 'stock_count': int, 'failed': list}
    """
    try:
        if not part_numbers:
            return {
                'status': False,
                'msg': '零件号列表不能为空',
                'parts_count': 0,
                'stock_count': 0,
                'failed': [],
            }

        # 从系统配置获取 cookie
        from config.config_list_manager.config_cache import get_config_value
        from app.exceptions.base import BusinessError
        bmw_config = get_config_value('bmw_car_parts_libray')
        cookie = None
        if bmw_config and isinstance(bmw_config, dict):
            cookie = bmw_config.get('cookie')
        if not cookie:
            raise BusinessError('未在系统配置中找到 BMW Brilliance 的 cookie，请先配置 bmw_car_parts_libray')

        parts_count = 0
        stock_count = 0
        failed = []

        for idx, oe in enumerate(part_numbers):
            try:
                if not oe or not str(oe).strip():
                    continue

                result = data_upsert(oe, cookie)

                if result.get('status'):
                    if result.get('detail_updated'):
                        parts_count += 1
                    if result.get('stock_updated'):
                        stock_count += 1
                    print(f"[{idx + 1}/{len(part_numbers)}] 零件 {oe} 刷新成功: {result.get('msg')}")
                else:
                    failed.append({'part_number': oe, 'reason': result.get('msg', '未知错误')})
                    print(f"[{idx + 1}/{len(part_numbers)}] 零件 {oe} 刷新失败: {result.get('msg')}")

            except Exception as inner_e:
                failed.append({'part_number': oe, 'reason': str(inner_e)})
                print(f"[{idx + 1}/{len(part_numbers)}] 零件 {oe} 刷新异常: {str(inner_e)}")

        total_success = parts_count + stock_count
        msg = (
            f'数据刷新完成！共处理 {len(part_numbers)} 个零件，'
            f'更新详情 {parts_count} 条，更新库存 {stock_count} 条，'
            f'失败 {len(failed)} 个'
        )

        return {
            'status': True,
            'msg': msg,
            'parts_count': parts_count,
            'stock_count': stock_count,
            'total_success': total_success,
            'failed': failed,
        }

    except Exception as e:
        msg = f'批量刷新宝马零件数据异常: {str(e)}'
        print(msg)
        return {
            'status': False,
            'msg': msg,
            'parts_count': 0,
            'stock_count': 0,
            'total_success': 0,
            'failed': [],
        }


# ====================================================
# 接口五：添加 / 更新 / 删除零件（基础 CRUD）
# ====================================================

def add_part(part_data: dict) -> dict:
    """
    添加宝马零件

    :param part_data: 零件数据字典（需包含 part_number）
    :return: {'status': bool, 'msg': str}
    """
    try:
        if not part_data or not part_data.get('part_number'):
            return {'status': False, 'msg': '零件号不能为空'}

        with orm_session() as session:
            existing = session.query(CarPartsLibraryBmw).filter(
                CarPartsLibraryBmw.part_number == part_data.get('part_number')
            ).first()

            if existing:
                return {'status': False, 'msg': '零件号已存在'}

            new_part = CarPartsLibraryBmw()
            for key, value in part_data.items():
                if hasattr(new_part, key):
                    setattr(new_part, key, value)

            session.add(new_part)
            session.commit()
            return {'status': True, 'msg': '添加成功'}

    except Exception as e:
        print(f"添加宝马零件失败: {str(e)}")
        return {'status': False, 'msg': f'添加失败: {str(e)}'}


def update_part(part_number: str, part_data: dict) -> dict:
    """
    更新宝马零件

    :param part_number: 零件号（主键，不可修改）
    :param part_data: 要更新的字段字典
    :return: {'status': bool, 'msg': str}
    """
    try:
        if not part_number:
            return {'status': False, 'msg': '零件号不能为空'}

        with orm_session() as session:
            part = session.query(CarPartsLibraryBmw).filter(
                CarPartsLibraryBmw.part_number == part_number
            ).first()

            if not part:
                return {'status': False, 'msg': '零件不存在'}

            for key, value in part_data.items():
                if hasattr(part, key) and key != 'part_number':
                    setattr(part, key, value)

            session.commit()
            return {'status': True, 'msg': '更新成功'}

    except Exception as e:
        print(f"更新宝马零件失败: {str(e)}")
        return {'status': False, 'msg': f'更新失败: {str(e)}'}


def delete_part(part_number: str) -> dict:
    """
    删除宝马零件（同时删除库存记录）

    :param part_number: 零件号
    :return: {'status': bool, 'msg': str}
    """
    try:
        if not part_number:
            return {'status': False, 'msg': '零件号不能为空'}

        with orm_session() as session:
            part = session.query(CarPartsLibraryBmw).filter(
                CarPartsLibraryBmw.part_number == part_number
            ).first()

            if not part:
                return {'status': False, 'msg': '零件不存在'}

            session.delete(part)

            # 同步删除库存表中关联记录（如存在）
            stock = session.query(CarPartsLibraryBmwStock).filter(
                CarPartsLibraryBmwStock.part_number == part_number
            ).first()
            if stock:
                session.delete(stock)

            session.commit()
            return {'status': True, 'msg': '删除成功'}

    except Exception as e:
        print(f"删除宝马零件失败: {str(e)}")
        return {'status': False, 'msg': f'删除失败: {str(e)}'}
