import json  # 导入 json 模块，用于调试时打印 JSON 数据
from collections import defaultdict

from pandas.core.frame import to_arrays  # 导入 defaultdict，用于按 oe_code 分组时简化代码

from app.exceptions.crawler_exceptions import CrawlerError
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider  # 导入 CRM 爬虫类
from app.scripts.spiders.pipeline_clean.wms_gzbbr_clear import crawl_products_by_oe_brand_clean, product_list_clean


##通过oe号搜索产品并清理数据
def crawl_related_products(oe_code):
    # 实例化 CRM 爬虫对象
    spider = CrmGzbbrSpider()
    # 调用产品列表接口，根据 OE 号查询相关产品，获取响应并解析为 JSON
    product_list = spider.get_product_product_list(numberlist=oe_code).json()  # pyright: ignore[reportOptionalMemberAccess]
    # 对返回的原始数据进行清洗，只保留需要的字段且过滤掉无库存产品
    clean_data = product_list_clean(product_list,oe_code)
    # 返回清洗后的产品列表
    return clean_data

def generate_tree(data_list):
    root = []
    for row in data_list:
        oe = row['number']
        brand = row['brand_name']
        product_title = f"{row['name']} - {row['price']}元"
        product_id = f"{row['product_id']}"
        
        oe_node = None
        for node in root:
            if node['id'] == oe:
                oe_node = node
                break
        if not oe_node:
            oe_node = {'id': oe, 'title': oe, 'child': []}
            root.append(oe_node)
        
        brand_node = None
        for node in oe_node['child']:
            if node['id'] == brand:
                brand_node = node
                break
        if not brand_node:
            brand_node = {'id': brand, 'title': brand, 'type': 'group', 'child': []}
            oe_node['child'].append(brand_node)
        
        brand_node['child'].append({
            'id': product_id,
            'title': product_title,
            'productData': row
        })
    
    return root


def crawl_products_by_oe_brand(oe_code):
    spider = CrmGzbbrSpider()
    # 调用产品列表接口，根据 OE 号查询相关产品，获取响应并解析为 JSON
    product_list = spider.get_product_product_list(numberlist=oe_code).json()  # pyright: ignore[reportOptionalMemberAccess]
    # 对返回的原始数据进行清洗，只保留需要的字段且过滤掉无库存产品
    clean_data = crawl_products_by_oe_brand_clean(oe_code,product_list)
    
    tree = generate_tree(clean_data)
    
    return tree


if __name__ == '__main__':
    data=crawl_products_by_oe_brand('0259971845')
    print(json.dumps(data, ensure_ascii=False, indent=2))
   

##生成tree结构



#通过oe进行分组合并
def merge_items_by_oe_code(items):
    # 按 oe_code 分组，返回一个字典，键为 oe_code，值为包含该 oe_code 的所有 items
    items_groups = defaultdict(list)
    for item in items:
        item['brand'] = item['brand'].replace("猫头鹰", "伦福德(猫)")
        items_groups[item.get('oe_code')].append(item)
        
    return items_groups


# 取出两边匹配值相等的交集数据
def list_matching(items,product_list):
    # 1. 取出两边匹配值相等的交集数据
    result = []
    for item in items:
        for product in product_list:
            # if product['brand_name'].replace(" ", "") in item['brand'].replace(" ", "") and product['price'] == item['price'] :
            
            if product['brand_name'].replace(" ", "") in item['brand'].replace(" ", "") and int(product['contrast_price_flag']) == int(item['price']) :

                # 合并两个字典
                merge_item = {
                    "quote_oe_code": item['oe_code'],
                    "quote_brand": item['brand'],
                    "quote_price": item['price'],
                    "quote_quantity": item['quantity'],              
                     **product

                }
                
                result.append(merge_item)
    return result



def add_cart_to_orders(inquiry_customer_id,list_data):
    spider = CrmGzbbrSpider()
    product_id_list = []
    for item in list_data:
        product_id_list.append(item['product_id'])
        spider.get_add_cart(search_no=item['search_no'],pid=item['product_id'],num=item['quote_quantity'],sales_price=item['price'])


    data = spider.get_cart_add_to_orders(partner_id=inquiry_customer_id,product_id=product_id_list).json()  # pyright: ignore[reportOptionalMemberAccess]



    if data.get('status',0) == 200:
        return data.get('data',0)
    else:
        raise CrawlerError(data.get('msg','生成草稿失败'))
    
# if __name__ == '__main__':
#     list_data = []
#     add_cart_to_orders(list_data)






##生成草稿链接
def generate_link(inquiry_customer_id, items, extra_items):
    list_data = []

    if items:
        oe_groups = merge_items_by_oe_code(items)
        for oe, group_items in oe_groups.items():
            product_list = crawl_related_products(oe)
            data = list_matching(group_items, product_list)
            list_data.extend(data)

    if extra_items:
        for item in extra_items:
            extra_item = {
                'product_id': item.get('product_id'),
                'search_no': item.get('oe_code'),
                'quote_quantity': item.get('quantity'),
                'price': item.get('price'),
            }
            list_data.append(extra_item)

  

    link_code = add_cart_to_orders(inquiry_customer_id, list_data)
    return link_code
    



