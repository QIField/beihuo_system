# -*- coding:utf-8 -*-
# @Time    : 2026/4/26 10:10
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_get_status_orders_type.py
# @Software: PyCharm


from app.models.orm_models.wms_status_orders_type import WmsStatusOrdersType
from app.models.orm_models.wms_return_items import WmsReturnItems
from app.scripts.spiders.pipeline_clean.wms_get_status_orders_clean import remove_duplicate
from app.scripts.spiders.pipeline_clean.wms_return_items_clean import clean_return_items
from app.scripts.spiders.spider_entities.wms_gzbbr import WmsGzbbrSpider
from app.utils.orm import orm_session
from config.config_list_manager.config_cache import get_config_value


def wms_get_status_orders_type(token, type_param=None, status_param=None, page_num=None, is_data_returned=False):
    """
    获取 WMS 状态订单数据
    
    :param token: 认证 token
    :param type_param: 类型参数
    :param status_param: 状态参数
    :param page_num: 指定页数，None 表示爬取全部
    :param is_data_returned: 是否返回爬取的数据
    :return: 当 is_data_returned=True 时返回清洗后的订单数据列表，否则返回 None
    """
    spider = WmsGzbbrSpider(token)
    data_total_count = 0  # 存储所有订单数据总计
    current_page = 1
    data_returned = [] if is_data_returned else None
    
    while True:
        # 请求接口
        json_data = spider.get_status_orders(
            type=type_param, 
            status=status_param,
            page=current_page
        ).json()

        # 获取订单数据
        data_node = json_data.get('data', {}).get('data', {})
        order_list = data_node.get('data', [])
        
        # 无数据直接退出
        print("数据为", json_data)
        if not order_list:
            print(f"第{current_page}页无数据，爬取结束")
            break

        # 进行数据清洗和字段过滤
        print(f"第{current_page}页原始订单数量: {len(order_list)}")
        filtered_data_list = remove_duplicate(order_list)
        print(f"第{current_page}页清洗后订单数量: {len(filtered_data_list)}")

        # 如果需要返回数据，收集到列表中
        if is_data_returned:
            data_returned.extend(filtered_data_list)

        # 进行入库操作（插入或更新）
        if filtered_data_list:
            print(f"开始入库第{current_page}页数据...")
            with orm_session() as session:
                count = WmsStatusOrdersType.bulk_upsert(session, filtered_data_list)
                print(f"第{current_page}页成功入库 {count} 条数据（插入或更新）")

        # 累加数据
        data_total_count += len(filtered_data_list)
        print(f"第{current_page}页订单数量: {len(order_list)}, 累计: {data_total_count}")

        # ===================== 核心退出逻辑 =====================
        # 1. 指定了页数：爬够页数就退出
        if page_num is not None and current_page >= page_num:
            print(f"已爬取指定的{page_num}页，爬取结束")
            break

        # 2. 继续下一页
        current_page += 1
    
    # 如果需要返回数据，返回收集到的数据
    return data_returned if is_data_returned else None

def wms_get_return_items(token, orders_no_list=None,type_param=None,status_param=None):
    """
    获取采购入库单列表
    
    :param token: 认证 token
    :param orders_no_list: 订单号列表
    :param type_param: 类型参数
    :param status_param: 状态参数
    :return: 采购入库单列表（所有订单的合并结果）
    """
    spider = WmsGzbbrSpider(token)
    all_return_items = []
    data_total_count = 0
    
    if not orders_no_list:
        return all_return_items
    else:
        with orm_session() as session:
            # 将表中所有记录的 status 字段更新为 3
            WmsReturnItems.update_all_status(session, 3)

    for orders_no in orders_no_list:
        try:
            print(f"正在查询订单 {orders_no} 的采购入库单...")
            json_data = spider.get_return_items(orders_no).json()
            
            # 获取退货商品数据
            return_items = json_data.get('data', {}).get('data', {}).get(orders_no, [])
            # 获取订单相关信息（pono, orders_id）
            po_info = json_data.get('data', {}).get('po', {})
            pono = po_info.get('pono')
            orders_id = po_info.get('orders_id')
            
            # 为每个商品添加订单信息
            for item in return_items:
                item['pono'] = pono
                item['orders_no'] = orders_no
                item['orders_id'] = orders_id
                item['type_param'] = type_param
                item['status']=status_param
            
            all_return_items.extend(return_items)
            print(f"订单 {orders_no} 查询完成，获取到 {len(return_items)} 条采购入库单")
            
            # 对当前订单的退货商品进行清洗和入库
            if return_items:
                # 进行数据清洗
                filtered_data_list = clean_return_items(return_items)
                print(f"订单 {orders_no} 清洗后采购入库单数量: {len(filtered_data_list)}")
                
                # 进行入库操作（插入或更新）
                if filtered_data_list:
                    print(f"开始入库订单 {orders_no} 的采购入库单数据...")
                    with orm_session() as session:
                        count = WmsReturnItems.bulk_upsert(session, filtered_data_list)
                        print(f"订单 {orders_no} 成功入库 {count} 条采购入库单数据（插入或更新）")
                        data_total_count += count
                
        except Exception as e:
            print(f"查询订单 {orders_no} 采购入库单时出错: {e}")
    
    spider.close()
    print(f"\n采购入库单数据入库完成，总共处理 {data_total_count} 条数据")
    return all_return_items




def wms_get_return_items_service(type_param=None, status_param=None, page_num=None):
    """
    WMS 状态订单爬虫服务

    :param type_param: 类型参数
    :param status_param: 状态参数
    :param page_num: 指定页数，None 表示爬取全部
    """
    print("=" * 100)
    print("wms_get_status_orders_type_service 执行开始")
    token = get_config_value("main_wms_token")
    
    # 获取订单列表数据
    json_data = wms_get_status_orders_type(token, type_param=type_param, status_param=status_param, page_num=page_num, is_data_returned=True)
    
    # 提取订单号列表
    orders_no_list = [item.get('orders_no') for item in json_data if item.get('orders_no')]
    print(f"提取到 {len(orders_no_list)} 个订单号")

    # 获取采购入库单数据
    if orders_no_list:
        print("\n" + "=" * 50)
        print("开始查询采购入库单...")
        return_items = wms_get_return_items(token, orders_no_list=orders_no_list, type_param=type_param, status_param=status_param)
        print(f"总共获取到 {len(return_items)} 条采购入库单数据")
        print("=" * 50)
        print("wms_get_status_orders_type_service 执行结束")
        print("=" * 100)
        return return_items

    else:
        print("wms_get_status_orders_type_service 执行结束")
        print("=" * 100)
        return None
    



if __name__ == '__main__':
    wms_get_return_items_service(type_param=5,status_param=0)