# -*- coding:utf-8 -*-
# @Time    : 2026/8/18
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : zhaopeiyun_benz.py
# @Software: PyCharm

"""
兆配云奔驰配件爬取服务
当奔驰原厂大库爬取失败时，使用兆配云作为备选数据源
只获取当前OE的基本信息和库存，不进行递归爬取关联零件
"""

from app.utils.orm.session import orm_session
from app.models.orm_models.external_system_models.zpy_token import ZpyToken
from app.models.orm_models.car_parts_library_benz import CarPartsLibraryBenz
from app.models.orm_models.car_parts_library_benz_stock import CarPartsLibraryBenzStock
from app.scripts.spiders.spider_entities.zhaopeiyun import ZhaoPeiYunSpider
from typing import Dict, List, Any
from sqlalchemy.dialects.mysql import insert


def get_zpy_token() -> str:
    """从数据库获取兆配云访问令牌"""
    with orm_session() as session:
        token_record = session.query(ZpyToken).order_by(ZpyToken.update_date.desc()).first()
        if token_record and token_record.access_token:  # pyright: ignore[reportGeneralTypeIssues]
            return token_record.access_token  # pyright: ignore[reportReturnType]
    return ""


def fetch_and_save_benz_part_zpy(part_number: str) -> Dict[str, Any]:
    """
    从兆配云获取单个奔驰配件信息+库存，保存到数据库（一次API调用完成）

    API返回格式: { "statusCode":200, "data": { "partInfo":{...}, "stockInfos":[...] } }
    """
    result = {'part_success': False, 'stock_count': 0}

    # 获取token
    token = get_zpy_token()
    if not token:
        print("[兆配云奔驰] 访问令牌为空")
        return result

    # 调用API（一次调用获取配件+库存）
    spider = ZhaoPeiYunSpider(token=token)
    try:
        response = spider.get_oe_detail(brand_code='benz', part_code=part_number)
        if response is None:
            print("[兆配云奔驰] API返回空响应")
            return result

        raw_json = response.json()
        data = raw_json.get('data')
        if not data:
            print(f"[兆配云奔驰] 配件 {part_number} 未找到数据")
            return result

        # ====== 1. 清洗配件信息 ======
        part_info = data.get('partInfo') or {}
        part_data = {
            'part_number': part_number,
            'descriptions': None,
            'description_cn': part_info.get('partName'),
            'marketing_code': part_info.get('designCode'),
            'dealer_discount_group': None,
            'msrp': float(part_info['price']) if part_info.get('price') else None,
            'dealer_fixed_nominal_margin': None,
            'wholesale_price': float(part_info['cost']) if part_info.get('cost') else None,
            'marketing_code_description': None,
            'quantity_unit': None,
            'sales_pack_size': part_info.get('ppq'),
            'weight': None,
            'length': None,
            'width': None,
            'height': None,
            'effective_date': None,
            'data_source': 'zhaopeiyun',
            'l_model_zh': None,
            'brand': '奔驰',
            'category': part_info.get('familyCode'),
            'ccc_mark': None,
            'volume': None,
            'hazmat_code': None,
            'origin_country': None,
            'shelf_life': None,
            'is_hazmat': None,
            'purchase_price': None,
            'part_nr_info_super_session': None
        }

        # upsert配件数据
        with orm_session() as session:
            stmt = insert(CarPartsLibraryBenz).values(**part_data)
            stmt = stmt.on_duplicate_key_update(**part_data)  # pyright: ignore[reportAttributeAccessIssue]
            session.execute(stmt)
            session.commit()

        result['part_success'] = True
        print(f"[兆配云奔驰] 配件 {part_number} 入库完成")

        # ====== 2. 清洗库存信息 ======
        stock_infos = data.get('stockInfos') or []
        if stock_infos:
            cleaned_stock_list = []
            for item in stock_infos:
                cleaned_stock_list.append({
                    'part_number': part_number,
                    'warehouse': str(item.get('warehouse', 'default')),
                    'description': item.get('companyName'),
                    'quantity_available': int(item.get('stock', 0)),
                    'unit': '件'
                })

            with orm_session() as session:
                for stock in cleaned_stock_list:
                    stmt = insert(CarPartsLibraryBenzStock).values(**stock)
                    stmt = stmt.on_duplicate_key_update(  # pyright: ignore[reportAttributeAccessIssue]
                        quantity_available=stock['quantity_available'],
                        description=stock['description'],
                        unit=stock['unit']
                    )
                    session.execute(stmt)
                session.commit()

            result['stock_count'] = len(cleaned_stock_list)
            print(f"[兆配云奔驰] 库存 {len(cleaned_stock_list)} 条入库完成")

        return result

    except Exception as e:
        print(f"[兆配云奔驰] 处理配件 {part_number} 失败: {str(e)}")
        return result
    finally:
        spider.close()


def zhaopeiyun_benz_fallback(func):
    """
    装饰器：当原厂奔驰爬取失败时，使用兆配云作为备选爬取
    """
    def wrapper(part_numbers: List[str]) -> Dict:
        original_result = func(part_numbers)

        # 只要有一个配件成功，就不使用兆配云
        if original_result.get('parts_count', 0) > 0:
            return original_result

        print("\n[兆配云备选] 所有原厂爬取失败，启用兆配云备选爬取...")

        zpy_success_parts = 0
        zpy_stock_count = 0

        for part_number in part_numbers:
            zpy_result = fetch_and_save_benz_part_zpy(part_number)
            if zpy_result['part_success']:
                zpy_success_parts += 1
            zpy_stock_count += zpy_result['stock_count']

        if zpy_success_parts > 0:
            return {
                'status': True,
                'msg': (f'兆配云补充成功，共 {zpy_success_parts} 个零件，{zpy_stock_count} 条库存'),
                'parts_count': zpy_success_parts,
                'stock_count': zpy_stock_count
            }
        else:
            return {
                'status': False,
                'msg': '原厂和兆配云均爬取失败',
                'parts_count': 0,
                'stock_count': 0
            }

    return wrapper