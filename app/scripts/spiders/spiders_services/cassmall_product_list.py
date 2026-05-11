# -*- coding:utf-8 -*-
# @Time    : 2026/5/6 16:18
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : cassmall_product_list.py
# @Software: PyCharm

from app.scripts.spiders.spider_entities.cassmall import CassmallSpider
from config.config_list_manager.config_cache import get_config_value


def cassmall_product_list_search(internal_name, parts_no="", brand_ids=None,
                                 status_id="", start_date="", end_date="", 
                                 product_name="", product_scope="N", 
                                 product_tag="ALL", page_num=1, page_size=100):
    """
    搜索卡思mall产品列表（单次请求）
    :param cookie: 认证cookie
    :param internal_name: 内部名称（默认搜索关键词）
    :param parts_no: 零件号
    :param brand_ids: 品牌ID列表
    :param status_id: 状态ID
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param product_name: 产品名称
    :param product_scope: 产品范围
    :param product_tag: 产品标签
    :param page_num: 页码
    :param page_size: 每页数量
    :return: 搜索到的产品
    """

    cookie = get_config_value("main_ks_cookie")

    if not cookie:
        print("未配置cassmall的COOKIE，请检查配置")
        return {
            'message': '未配置cassmall的COOKIE，请检查配置',
            'data': []
        }

    spider = CassmallSpider(cookie)
    
    # 测试 Cookie 是否有效
    print("正在测试 Cookie 有效性...")
    is_valid, test_message = spider.test_cookie()
    if not is_valid:
        print(f"Cookie 测试失败: {test_message}")
        spider.close()
        return {
            'message': f'Cookie 无效或已过期，请配置正确的COOKIE: {test_message}',
            'data': []
        }
    print("Cookie 测试通过")



    # 请求接口
    response = spider.get_product_list(
        internal_name=internal_name,
        parts_no=parts_no,
        brand_ids=brand_ids,
        status_id=status_id,
        start_date=start_date,
        end_date=end_date,
        product_name=product_name,
        product_scope=product_scope,
        product_tag=product_tag,
        page_num=page_num,
        page_size=page_size
    )

    if not response:
        print("请求失败")
        spider.close()
        return {
            'message':'请求失败',
            'data':[]
        }

    json_data = response.json()

    # 无数据直接返回
    if not json_data:
        print("无数据")
        spider.close()
        return {
            'message': '无数据',
            'data': []
        }

    # 获取产品数据（需要根据实际返回结构调整）
    # 注意：这里假设返回结构，实际使用时需要根据API响应调整字段路径
    product_list = json_data.get("data", [])



    if not product_list:
        print("没有数据")
        return {
            'message': '没有数据',
            'data': []
        }

    spider.close()
    return {
        'message': '搜索成功',
        'data': product_list
    }


def cassmall_get_inventorys(product_ids):
    """
    获取卡思mall产品库存信息
    :param product_ids: 产品ID列表
    :return: 库存信息
    """
    cookie = get_config_value("main_ks_cookie")


    if not cookie:
        print("未配置cassmall的COOKIE，请检查配置")
        return {
            'message': '未配置cassmall的COOKIE，请检查配置',
            'data': []
        }

    spider = CassmallSpider(cookie)
    
    # 测试 Cookie 是否有效
    print("正在测试 Cookie 有效性...")
    is_valid, test_message = spider.test_cookie()
    if not is_valid:
        print(f"Cookie 测试失败: {test_message}")
        spider.close()
        return {
            'message': f'Cookie 无效或已过期，请配置正确的COOKIE: {test_message}',
            'data': []
        }
    print("Cookie 测试通过")

    # 请求接口
    response = spider.get_inventorys(product_ids)

    # if not response:
    #     print("请求失败")
    #     spider.close()
    #     return {
    #         'message': '请求失败',
    #         'data': []
    #     }

    json_data = response.json()

    # 无数据直接返回
    if not json_data:
        print("无数据")
        spider.close()
        return {
            'message': '无数据',
            'data': []
        }

    # 获取库存数据
    inventory_list = json_data

    spider.close()
    return {
        'message': '获取库存成功',
        'data': inventory_list
    }


def cassmall_update_inventory_batch(inventory_list):
    """
    更新卡思mall产品库存（支持单个产品多仓库或多个产品多仓库更新）
    :param inventory_list: 库存列表，每个元素包含 facilityId, availableToPromiseTotal, safeToPromiseTotal, productId
    :return: 更新结果
    """
    cookie = get_config_value("main_ks_cookie")


    if not cookie:
        print("未配置cassmall的COOKIE，请检查配置")
        return {
            'message': '未配置cassmall的COOKIE，请检查配置',
            'data': None
        }

    spider = CassmallSpider(cookie)
    
    # 测试 Cookie 是否有效
    print("正在测试 Cookie 有效性...")
    is_valid, test_message = spider.test_cookie()
    if not is_valid:
        print(f"Cookie 测试失败: {test_message}")
        spider.close()
        return {
            'message': f'Cookie 无效或已过期，请配置正确的COOKIE: {test_message}',
            'data': None
        }
    print("Cookie 测试通过")

    # 请求接口
    response = spider.update_inventory_batch(inventory_list)

    if not response:
        print("请求失败")
        spider.close()
        return {
            'message': '请求失败',
            'data': None
        }

    json_data = response.json()

    # 检查返回结果
    if json_data.get('code') != 200:
        error_msg = json_data.get('errorMessage', '未知错误')
        print(f"更新库存失败: {error_msg}")
        spider.close()
        return {
            'message': f'更新库存失败: {error_msg}',
            'data': None
        }

    result_data = json_data.get('data')

    spider.close()
    return {
        'message': '更新库存成功',
        'data': result_data
    }








# if __name__ == "__main__":
# #     # 测试代码
# #     ks_json_data=cassmall_product_list_search("PGN10571-18B1")
# #     if ks_json_data.get('data'):
# #         print(ks_json_data)
# #     else:
# #         print(ks_json_data)

#     # # 查询库存
#     # print("=== 查询库存...")
#     # inventory_result = cassmall_get_inventorys(["21211694423523821150"])
#     # print("查询结果:", inventory_result)
#     #
#     # # 直接从查询结果中提取数据并组合
#     # print("\n=== 组合更新数据...")
#     # inventory_data = inventory_result.get('data', {})
#     # product_id = "21211694423523821150"
#     # product_info = inventory_data.get(product_id, {})
#     # inv_list = product_info.get('inventory', [])
#     #
#     # # 手动组合两个仓库的数据
#     # inventory_list = [
#     #     {
#     #         "facilityId": inv_list[0].get('facilityId'),
#     #         "availableToPromiseTotal": 2,
#     #         "safeToPromiseTotal": inv_list[0].get('safeToPromiseTotal', 0),
#     #         "productId": product_id
#     #     },
#     #     {
#     #         "facilityId": inv_list[1].get('facilityId'),
#     #         "availableToPromiseTotal": 0,
#     #         "safeToPromiseTotal": inv_list[1].get('safeToPromiseTotal', 0),
#     #         "productId": product_id
#     #     }
#     # ]
#     #
#     # print("组合后的格式:", inventory_list)
#     #
#     # print("\n=== 更新库存...")
#     # update_result = cassmall_update_inventory_batch(inventory_list)
#     # print("更新结果:", update_result)

#     dd=cassmall_get_inventorys(["23385805342078814450","22160020164890296840"])
#     print(dd)
