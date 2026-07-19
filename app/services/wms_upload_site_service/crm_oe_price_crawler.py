

import pandas as pd

from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider


def oe_price_clean(product_list, number: str, brand_name: str):
    """
    OE 价格清理服务

    根据输入的 OE 号和品牌名称精确匹配清洗产品数据，由于 API 返回的是模糊匹配结果，
    会包含多个不同 OE 号和品牌的产品，此函数只保留 OE 号和品牌与输入完全匹配的产品记录。

    :param product_list: 爬虫返回的原始 JSON 数据（已解析为字典）
    :param number: 输入的 OE 号，用于精确匹配
    :param brand_name: 输入的品牌名称，用于精确匹配
    :return: 清洗后的产品列表，每个元素包含 name、stock、number、price、product_id、brand_name
    """
    # 参数校验：检查输入数据是否有效
    if not product_list or not isinstance(product_list, dict):
        return []

    # 提取 data 层级数据
    data_obj = product_list.get('data', {})
    if not data_obj or not isinstance(data_obj, dict):
        return []

    # 提取 data.data 层级数据
    data_list = data_obj.get('data', [])
    if not data_list or not isinstance(data_list, list):
        return []

    # 定义需要保留的字段列表
    model_fields = ['name', 'stock', 'number', 'price', 'product_id', 'brand_name']

    # 使用列表推导式展平所有 child 列表，提取所有产品数据
    child_lists = [item.get('child', []) for item in data_list if isinstance(item.get('child'), list)]
    all_products = [product for child_list in child_lists for product in child_list]

    # 转换为 DataFrame 进行向量化清洗
    df = pd.DataFrame(all_products)

    # 空数据检查
    if df.empty:
        return []

    # 精确匹配 OE 号：将 number 字段转为字符串并去除空格后与输入 OE 号严格比较
    df['number'] = df['number'].astype(str).str.strip()
    df = df[df['number'] == number.strip()].copy()

    # 匹配后为空检查
    if df.empty:
        return []

    # 精确匹配品牌名称：将 brand_name 字段转为字符串并去除空格后与输入品牌名称严格比较
    # 如果 brand_name 为空或 None，则跳过品牌过滤
    if brand_name and brand_name.strip():
        df['brand_name'] = df['brand_name'].astype(str).str.strip()  # pyright: ignore[reportAttributeAccessIssue]
        df = df[df['brand_name'] == brand_name.strip()].copy()

        # 匹配后为空检查
        if df.empty:  # pyright: ignore[reportAttributeAccessIssue]
            return []

    # 只保留模型定义的字段
    available_fields = [field for field in model_fields if field in df.columns]  # pyright: ignore[reportAttributeAccessIssue]
    df = df[available_fields].copy()

    # 类型转换：product_id 转为数值类型
    df['product_id'] = pd.to_numeric(df['product_id'], errors='coerce')

    # 类型转换：price 转为浮点类型，空值填充为 0，保留两位小数
    df['price'] = pd.to_numeric(df['price'].replace('', 0), errors='coerce').fillna(0).round(2).astype(float)  # pyright: ignore[reportAttributeAccessIssue]

    # 转换为字典列表返回
    clean_data_list = df.to_dict('records')  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]

    return clean_data_list


def crm_get_oe_price_data(spider: CrmGzbbrSpider,number: str,brand_name: str):
    """
    CRM OE 价格爬虫服务
    """
    #number清理格式化 
    number = number.strip().split()[0].replace(' ', '')


    # 调用爬虫方法获取产品列表
    product_list = spider.get_product_product_list(number=number).json()  # pyright: ignore[reportOptionalMemberAccess]
    # print(product_list)
    # 清理产品列表
    product_list = oe_price_clean(product_list,number=number,brand_name=brand_name)
    wms_price = product_list[0].get('price')
    # print(product_list)
    return wms_price
  


# def crm_get_oe_price_list(list: list):
#     """
#     CRM OE 价格列表爬虫服务
#     :param list: OE 号列表
#     :return: 清洗后的 OE列表
#     """
#     # 初始化爬虫
#     spider = CrmGzbbrSpider()
#     product_list = []
#     for number in list:
#         product_list.extend(oe_price_clean(spider,number=number,brand_name=""))
#     return product_list

