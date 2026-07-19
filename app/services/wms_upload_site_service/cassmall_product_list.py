# -*- coding:utf-8 -*-
# @Time    : 2026/5/6 16:18
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : cassmall_product_list.py
# @Software: PyCharm

from app.scripts.spiders.spider_entities.cassmall import CassmallSpider
from config.config_list_manager.config_cache import get_config_value


def cassmall_product_list_search(internal_name,spider, parts_no="", brand_ids=None,
                                 status_id="", start_date="", end_date="", 
                                 product_name="", product_scope="N", 
                                 product_tag="ALL", page_num=1, page_size=100):
    """
    搜索开思mall产品列表（单次请求）
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
       
        return {
            'message':'请求失败',
            'data':[]
        }

    json_data = response.json()

    # 无数据直接返回
    if not json_data:
        print("无数据")
       
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

       
    return {
        'message': '搜索成功',
        'data': product_list
    }

# if __name__ == "__main__":
#     data=cassmall_product_list_search("P64119242607 ML")
#     print(data)





def cassmall_get_inventorys(product_ids,spider):
    """
    获取开思mall产品库存信息
    :param product_ids: 产品ID列表
    :return: 库存信息
    """
  

    
    
   

    # 请求接口
    response = spider.get_inventorys(product_ids)

    # if not response:
    #     print("请求失败")
    #     spider.close()
    #     return {
    #         'message': '请求失败',
    #         'data': []
    #     }

    json_data = response.json()  # pyright: ignore[reportOptionalMemberAccess]

    # 无数据直接返回
    if not json_data:
        print("无数据")
       
        return {
            'message': '无数据',
            'data': []
        }

    # 获取库存数据
    inventory_list = json_data

       
    return {
        'message': '获取库存成功',
        'data': inventory_list
    }


def cassmall_update_inventory_batch(inventory_list,spider):
    """
    更新开思mall产品库存（支持单个产品多仓库或多个产品多仓库更新）
    :param inventory_list: 库存列表，每个元素包含 facilityId, availableToPromiseTotal, safeToPromiseTotal, productId
    :return: 更新结果
    """
   

    
  

    # 请求接口
    response = spider.update_inventory_batch(inventory_list)

    if not response:
        print("请求失败")
       
        return {
            'message': '请求失败',
            'data': None
        }

    json_data = response.json()

    # 检查返回结果
    if json_data.get('code') != 200:
        error_msg = json_data.get('errorMessage', '未知错误')
        print(f"更新库存失败: {error_msg}")
       
        return {
            'message': f'更新库存失败: {error_msg}',
            'data': None
        }

    result_data = json_data.get('data')

       
    return {
        'message': '更新库存成功',
        'data': result_data
    }


def on_shelf(product_ids,spider):
    """
    开思商品上架
    :param product_id: 产品ID
    :return: 更新结果
    """   
    

    response = spider.update_product_status(product_ids)
    data = response.json()  # pyright: ignore[reportOptionalMemberAccess]
   
    if not data.get('success'):
        print(f"更新商品状态失败: {data.get('errorMessage', '未知错误')}")
        return False
   
    return True


def cassmall_add_or_update_price(product_id, price_value, spider, price_type="DEFAULT_PRICE"):
    """
    新增或更新开思mall产品价格
    :param product_id: 产品ID
    :param price_value: 价格值
    :param spider: 爬虫实例
    :param price_type: 价格类型，默认 DEFAULT_PRICE
    :return: 更新结果
    """
    response = spider.add_or_update_price(product_id, price_value, price_type)

    if not response:
        print("价格更新请求失败")
        return {
            'message': '价格更新请求失败',
            'data': None
        }

    if response.status_code != 200:
        print(f"更新价格失败: HTTP状态码 {response.status_code}")
        return {
            'message': f'更新价格失败: HTTP状态码 {response.status_code}',
            'data': None
        }

    try:
        json_data = response.json()
        result_data = json_data.get('data')
    except:
        result_data = response.text

    return {
        'message': '更新价格成功',
        'data': result_data
    }


# if __name__ == "__main__":
#     data=on_shelf(["21600375463843921950","21600375463843921940"])
#     print(data)