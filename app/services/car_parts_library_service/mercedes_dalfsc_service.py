# -*- coding:utf-8 -*-
# @Time    : 2026/5/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : mercedes_dalfsc_service.py
# @Software: PyCharm
from app.scripts.spiders.spider_entities.mercedes_dalfsc import MercedesDalfscSpider
from app.scripts.spiders.pipeline_clean.mercedes_dalfsc_clean import clean_parts_information, clean_stock_information, extract_all_part_numbers_from_part_data
from app.dao.car_parts_library_benz_dao import CarPartsLibraryBenzDao
from app.dao.car_parts_library_benz_stock_dao import CarPartsLibraryBenzStockDao
from app.scripts.spiders.spider_entities.mercedes_login import MercedesLoginService
from app.utils.orm.session import orm_session
from config.config_list_manager.config_cache import get_config_value
import json

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
    爬取奔驰库存信息并入库

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
        
        # 打印调试信息
        print(f"API 返回原始数据条数：{len(data_list)}")
        if data_list:
            print(f"前几条原始数据预览：{data_list[:3]}")

        # 清洗数据
        clean_data_list = clean_stock_information(data_list)

        msg = f"库存信息清洗完成，共 {len(clean_data_list)} 条"
        print(msg)

        # 入库
        count = 0
        if clean_data_list:
            with orm_session() as session:
                count = CarPartsLibraryBenzStockDao.batch_upsert(session, clean_data_list)
                session.commit()
                msg = f"库存信息入库成功，影响 {count} 条"
                print(msg)

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
    
    # 读取配置获取其他需要的参数
    from config.config_list_manager.config_cache import get_config_value
    config = get_config_value('mercedes_benz')
    
    
    
    customer_id = config.get("customer_id", "193211390")   # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
    sales_organization_id = config.get("sales_organization_id", "O 50000741")   # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
    
    # 创建spider实例（会自动获取并验证 cookie）
    spider = MercedesDalfscSpider()
    
    try:
        print("✓ Spider 初始化完成，cookie 已验证")
        
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



def by_part_number_get_data(part_number):
    """
    根据零件编号获取零件信息和库存信息（不入库，返回JSON）
    
    :param part_number: 零件编号
    :return: 包含零件信息和库存信息的JSON字典
    :raises Exception: 当请求失败或处理出错时抛出异常
    """
    result = {
        'part_number': part_number,
        'part_info': None,
        'stock_info': []
    }
    
    config = get_config_value('mercedes_benz')
    customer_id = config.get("customer_id", "193211390")  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
    sales_organization_id = config.get("sales_organization_id", "O 50000741")  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
    
    spider = MercedesDalfscSpider()
    
    try:
        parts_response = spider.get_parts_informations(part_number, customer_id, sales_organization_id)
        if not parts_response:
            raise Exception('零件信息请求失败')
        
        parts_data = parts_response.json()
        clean_part_data = clean_parts_information(parts_data)
        
        # 将 JSON 字符串转换为字典（使用 json.loads 而不是 .json()）
       
        clean_part_data['part_nr_info_super_session'] = json.loads(clean_part_data['part_nr_info_super_session'])
        
        result['part_info'] = clean_part_data
        
        all_part_numbers = extract_all_part_numbers_from_part_data(parts_data)
        
        stock_response = spider.get_stock_information(all_part_numbers)
        if not stock_response:
            raise Exception('库存信息请求失败')
        
        stock_data = stock_response.json()
        clean_stock_data = clean_stock_information(stock_data)
        result['stock_info'] = clean_stock_data
        
        return result
        
    finally:
        spider.close()



# if __name__ == "__main__":
# #    fetch_mercedes_data(["A2642000301"])  
#     result = by_part_number_get_data("A2642000301")
#     print(result)
