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
    
    # 获取配置
    config = get_config_value("mercedes_benz")

    # config = {
    #     "cookie": "_abck=9CF00446D3E0B33C259A7C11C21E2056~0~YAAQ7G+bG9FZBXaeAQAABwKvjBD33UEqKVchKGzHISA5Pcz/YkPaGBVkFxj7FNlHHnOwjAR1UEkCCkuIsPPtOuCdkVu6SEFRf0QF0Qwf9p3uo7rtBJBZ4vy7kGy8g/OzcKxJ1TAEw2hah4K1TPCyOdawgTAP+2y9FYB/Snz17aGKHgZggPpq+4PM8mwLuB7f8PbT11EtHEEmbasYFsoU+P6JyfAQwYMwT6wLgxn2bHza81urHugkK6kGJJXhKBCu0n1aWF2dadSGnnQX5iqGPZDtGKjI0Bf/hM8hCe42FeanNaUm8UoB9TD4QXBB+TTNL4BePDjfp9wFdCVi8R5crKwsG5u+42n2d6rCosyX3ThlCwrpC5PMEoApZ9+yD3V2FYIjsUe3rx3/AmFaQUUTXMkXDn5gjcanskwGzPP8JH7A+EsQE6CuSxUqJjAVe/I92OZXEir+6eOAaFG8kOFoumOt/XVWsBVmHMBbjeQObGR/k5HkM/qT1ivLPl6+zhkS0tAhQOYTKX524hbnvQGzAHeJl+T0YKDZASuzhXwJy7/h4Q+NaLgv9IWco/o0dcEnPuO2QwtSvO7lgp2hF3+eJOVQ5OIrTXzYbk/60vumbJts12vBFybS2FiWtdtBzhuEs2Yqii4XzioOGTQVqEeAgECvKFzTTlBa8Q1ykKKuOIlitb7ikPo8bcq7hLSNMnRk401PqzN0MqHB1+xiygpO0VT3wGkDBpneV2FI6FgSdNXGNwXp7WuHRPcQCnHOU+/ZIAnYkNM3u9SWD1NVOatpIbDG7J407OU3zch/IXgpYd3WwG+ElPtLM8kTMr4Hus2dn0Juzbl2OyZCzQU999P4ll02Iw6o6kGaElx6JlkeLJNU82mkCqwEnfLf+WVblBOZ/v/oRjFvzzPchoW/jAluhiJFPg==~-1~-1~1779949745~AAQAAAAF%2f%2f%2f%2f%2f38xH6h1TTBZPHrrsQGltUM8OiNQTOgPSYBJuJd458uUZ8s7FuQpDSkDqF6+f8kON1PUjLIHiAjFfSYlOfPT8VPG7wTbfSoi+9ZQ~-1; bm_sz=BD0A0F88CA54E3C159B888EAF9F10B49~YAAQ7G+bG9JZBXaeAQAABwKvjADY3vO/G3ZqhSa1c9/vjwoUN5zU5G9O4Kx7N+j80kwFeGYt/Df5op32Tj0D3j/eyxA2KcXzVRsFNCNt7B30R28U8I79kiz5nFuNw6N5uOINmjnuvWbGz6xtahr0ASyMB8q6H1OnAYtJbDNnD0K+1/Ch8v72vEFa/D+twyYi4XKF6EMmGvQn3sv89r6MTKJ/jEW68AC5pJ80uMiB9qxtTvXlWj3iFQxlqsHsMaNVPjDFbQPlpBQdXSzC1q/hIXelAYz2bB4S1jioYin+6qgrgbEZI5EMAu/OhSN+2FWJ4ku8H+yXqFx+eFuZ3lcMzbm6T39ziVaU6orXeR+Rm3tnerWU2alajgz4XggMJCIgmpD6zzSgaj8G3xkGt91kudn2Jk0=~3552820~4272690; SESSION=6667d620-aad0-45bf-8d9b-dddea069a3f6",

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

if __name__ == "__main__":
   fetch_mercedes_data(["A2642000301"])  