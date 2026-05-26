# -*- coding:utf-8 -*-
# @Time    : 2026/5/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : mercedes_dalfsc_service.py
# @Software: PyCharm
from app.scripts.spiders.spider_entities.mercedes_dalfsc import MercedesDalfscSpider
from app.scripts.spiders.pipeline_clean.mercedes_dalfsc_clean import clean_parts_information, clean_stock_information, extract_all_part_numbers_from_part_data
from app.dao.car_parts_library_benz_dao import CarPartsLibraryBenzDao
from app.utils.orm.session import orm_session
from config.config_list_manager.config_cache import get_config_value


def fetch_mercedes_parts_information(spider, part_number, customer_id, sales_organization_id):
    """
    爬取单个奔驰零件信息（暂不入库）
    
    :param spider: MercedesDalfscSpider实例（已验证过Cookie）
    :param part_number: 零件编号
    :param customer_id: 客户ID
    :param sales_organization_id: 销售组织ID
    :return: 包含成功/失败状态和提示信息的字典，格式: {'status': bool, 'msg': str, 'part_numbers': list}
    """
    try:
        # 调用接口
        response = spider.get_parts_informations(part_number, customer_id, sales_organization_id)
        
        if not response:
            msg = f"请求失败：{part_number}"
            print(msg)
            return {'status': False, 'msg': msg, 'part_numbers': []}
        
        # 获取JSON数据
        data = response.json()
        
        # 清洗数据
        clean_data = clean_parts_information(data)
        
        msg = f"零件 {part_number} 数据清洗完成"
        print(msg, clean_data)
        
        # 入库
        if clean_data:
            with orm_session() as session:
                count = CarPartsLibraryBenzDao.upsert(session, clean_data)
                msg = f"零件 {part_number} 入库成功，影响 {count} 条"
                print(msg)
        
        # 提取所有相关的零件编号
        part_numbers = extract_all_part_numbers_from_part_data(data)
        
        return {'status': True, 'msg': msg, 'part_numbers': part_numbers}
        
    except Exception as e:
        msg = f"处理零件 {part_number} 时出错：{str(e)}"
        print(msg)
        return {'status': False, 'msg': msg, 'part_numbers': []}


def fetch_mercedes_stock_information(spider, part_numbers):
    """
    爬取奔驰库存信息（暂不入库）
    
    :param spider: MercedesDalfscSpider实例（已验证过Cookie）
    :param part_numbers: 零件编号列表
    :return: 包含成功/失败状态和提示信息的字典，格式: {'status': bool, 'msg': str, 'stock_data': list}
    """
    try:
        # 调用接口
        response = spider.get_stock_information(part_numbers)
        
        if not response:
            msg = "库存信息请求失败"
            print(msg)
            return {'status': False, 'msg': msg, 'stock_data': []}
        
        # 获取JSON数据
        data_list = response.json()
        
        # 清洗数据
        clean_data_list = clean_stock_information(data_list)
        
        msg = f"库存信息清洗完成，共 {len(clean_data_list)} 条"
        print(msg)
        
        # 入库（暂不执行）
        # if clean_data_list:
        #     with orm_session() as session:
        #         count = CarPartsLibraryBenzStock.bulk_upsert(session, clean_data_list)
        #         print(f"库存信息入库成功，影响 {count} 条")
        
        return {'status': True, 'msg': msg, 'stock_data': clean_data_list}
        
    except Exception as e:
        msg = f"处理库存信息时出错：{str(e)}"
        print(msg)
        return {'status': False, 'msg': msg, 'stock_data': []}


def fetch_mercedes_data(part_numbers):
    """
    完整的奔驰数据爬取流程：先爬零件信息，从零件数据中提取载荷信息，再爬库存信息（暂不入库）
    
    :param part_numbers: 初始零件编号列表
    :return: 包含成功/失败状态和提示信息的字典，格式: {'status': bool, 'msg': str, 'parts_count': int, 'stock_count': int}
    """
    print("=" * 100)
    print("奔驰大库数据爬取开始")
    
    # 获取配置
    config = get_config_value("mercedes_benz")

    # config = {
    #     "cookie": "_abck=9CF00446D3E0B33C259A7C11C21E2056~0~YAAQpG2bGxeVfj6eAQAAyTqqUw/D4a3jbPqHHudCBBFbYgxEUw+MlqxLYnT8QGbvEtvemVFpUZ3w/0pwqCKNHZVEz5f/xQ0wAjiEqkiJcX9khS/wca9hi3X1Jv+/PggXtPOAJCIrHSIIozoxwQMIslG8LXlDCXZ+gRA2/yCx5Vzz+7CFyX0msrNfx+qMBPf7h4vsTNQUpJ0WUEMgFdWQlwsKVojU8nbAnCZOMGtJR78usoxEVZp4+DxCFaMM1es5olUBjE1eHI0gcUTx3yPnIcnmPv9xWW4EHYvP7cAJY7gSA36RniGecz9Bn8Wz5CF/ak9r2mcXqUFBfXaK+aDzgfeU746PrPTAZUJ7ofKJHH6zxB47s1c/JVHnJSl8N3kpYPKxcZdU3jT9+CFtQ7Zpxz34pMx2xKnuaQdsT5IeeVOUBs7z+3I0qDkD0B8Lg+aLW4OL8O411L185ZdN8MFsb7gtq1gFDDKse7yQ9UszpKOA/Fv68+6DxXKOkewNbc8zX4cLl1kKnVLHvOtsZqMG6SZhyjvQuZRYKIevStaAQZI2JTtGpS8esTqeay/sHOJmMKbzZrbmuAY/0smF6brmrOdLK3qm1agJMW0k0S4C2EKNpISW6+WAZfEPf/KUBAANyRt+yfoXiMsrTTMU7BgUk7igkLSQfUpaso4QU2YJQwwML9RfrB6k0vaE0AFL5vg4VoLIFct5OybB8tFo2rnD80GwkwLHdM33sxGZqctpxJN8WwSjyLO5DvSYcfKVE/hAtRnB4V6yGBlYiTShpmGY3QB1krHRXnqSI3a7+Ee0Mo4fm2Ifgbw9NvGD7lyqS9h1c1vVHjMAxKdPnEHpxbozJA8nuI7bHkUDdFOyJaUimoTEJEhLReJ8HN8K8w5oHNyjLPTOUPrAfYT2Ay5399IpIkkBKYvy7TydG0mwRCJAp7kgopo4yAwac0T5H5QfxZss+s86tynpEg==~-1~-1~1779523718~AAQAAAAF%2f%2f%2f%2f%2f2HJArYy1hULRL80x+OEbkTCjGJ%2fuy4G8rp3Hv4WsFuBa%2fxVNSuNH40CsHUA2tRkBONOKUNCNNnOc+LzKvQlk8KcuntqJ8YiPqMQ~-1; bm_sz=4903077DCB23E8E0F34857B752B15326~YAAQpG2bGyqXfj6eAQAAKX+qUx+wvGYVM46ODbHXpqvkikKi03L48Yf1UbQ0ySWC1N9SIFbcCwN28yB81nqV7QSJr6z8qeRxY97y74s2sPx+moQbyR362YSBROKCmIAYv/13UPWXsIEUljVZWEvsc2SrB9DS9ObkglD/Q+c6JNy9ajKNIUHFTQuMoolsXhZElH1UTqveCdaquqlBqWtmG7j8y38OeK2CSrStTt6A99DkFzLYxQMj2i+Gz4CIjhpgylj5BASoyNaD6i99aXZ9rv7bPQvwW9TwrOXt+1ahzmFZcAaeY/rPLjW3Dzp4AvY21y1w4krcc+M6qo7osC7WtEzaj7OeaiYxxiNabG8qYheDRpuU5jWFhyiv0KBIxxSMdJDLe2veVMXWDqECOd907j2n6MQbz0/v6ZQCB1jxXhWr6V/4xL5XvzGBj3qyMvWpOc8ds2JbeaqPWiS7fmRq1+9YVgJCDehtshwOmSTyI5fQRn3y8SusTj/lIXwRh1FoWMS9N22W~3683638~3162937; SESSION=63d399fa-b7e9-471a-bc40-621c8b185ba5",

    #     "customer_id": "193211390",
    #     "sales_organization_id": "O 50000741"
    # }


    
    if not config:
        msg = "未找到奔驰大库配置"
        print(msg)
        return {'status': False, 'msg': msg, 'parts_count': 0, 'stock_count': 0}
    
    cookie = config.get("cookie", "")  # pyright: ignore[reportAttributeAccessIssue]
    customer_id = config.get("customer_id", "193211390")  # pyright: ignore[reportAttributeAccessIssue]
    sales_organization_id = config.get("sales_organization_id", "O 50000741")  # pyright: ignore[reportAttributeAccessIssue]
    
    if not cookie:
        msg = "Cookie 未配置"
        print(msg)
        return {'status': False, 'msg': msg, 'parts_count': 0, 'stock_count': 0}
    
    # 创建spider实例
    spider = MercedesDalfscSpider(cookie)
    
    try:
        # 验证Cookie是否有效
        is_valid, error_msg = spider.validate_cookie(
            test_part_number="A0005420590",
            test_customer_id=customer_id,
            test_sales_organization_id=sales_organization_id
        )
        if not is_valid:
            msg = f"Cookie验证失败：==={error_msg}"
            print(msg)
            return {'status': False, 'msg': msg, 'parts_count': 0, 'stock_count': 0}
        print("Cookie验证通过，继续执行...")
        
        # 逐个爬取零件信息
        print("\n开始爬取零件信息...")
        all_part_numbers = set()
        success_count = 0
        for part_number in part_numbers:
            result = fetch_mercedes_parts_information(spider, part_number, customer_id, sales_organization_id)
            if result['status']:
                success_count += 1
                if result['part_numbers']:
                    all_part_numbers.update(result['part_numbers'])
    
        print(f"\n零件信息爬取完成，成功 {success_count}/{len(part_numbers)} 个")
        
        all_part_numbers = list(all_part_numbers)
        print(f"\n共提取到 {len(all_part_numbers)} 个零件编号用于库存查询")
        
        # 第三步：批量爬取库存信息
        print("\n开始爬取库存信息...")
        stock_result = fetch_mercedes_stock_information(spider, all_part_numbers)
        
        stock_count = len(stock_result['stock_data']) if stock_result['status'] and stock_result['stock_data'] else 0
        if stock_result['status']:
            print("库存信息爬取完成")
        else:
            print("库存信息爬取失败")
        
        msg = f"奔驰大库数据爬取完成，零件信息 {success_count} 条，库存信息 {stock_count} 条"
        print("\n" + msg)
        print("=" * 100)
        
        return {'status': True, 'msg': msg, 'parts_count': success_count, 'stock_count': stock_count}
    finally:
        spider.close()

# if __name__ == "__main__":
#    fetch_mercedes_data(["A0005420711"])  