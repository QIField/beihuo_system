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
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.scripts.spiders.spider_entities.wms_gzbbr import WmsGzbbrSpider
from app.services.wms_upload_site_service.crm_oe_price_crawler import crm_get_oe_price_data
from app.utils.orm import orm_session
from config.config_list_manager.config_cache import get_config_value


def wms_get_status_orders_type(session,type_param=None, status_param=None, page_num=None, is_data_returned=False):
    """
    获取 WMS 状态订单数据
    :param type_param: 类型参数
    :param status_param: 状态参数
    :param page_num: 指定页数，None 表示爬取全部
    :param is_data_returned: 是否返回爬取的数据
    :param session: 数据库会话，传入则使用外部会话，否则创建新会话
    :return: 当 is_data_returned=True 时返回清洗后的订单数据列表，否则返回 None
    """
    spider = WmsGzbbrSpider()
    data_total_count = 0  # 存储所有订单数据总计
    current_page = 1
    data_returned = [] if is_data_returned else None
    
    while True:
        # 请求接口
        json_data = spider.get_status_orders(
            type=type_param, 
            status=status_param,
            page=current_page
        ).json()  # pyright: ignore[reportOptionalMemberAccess]

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
            data_returned.extend(filtered_data_list)  # pyright: ignore[reportOptionalMemberAccess]

        # 进行入库操作（插入或更新）
        if filtered_data_list:
            print(f"开始入库第{current_page}页数据...")
           
            with orm_session() as new_session:
                count = WmsStatusOrdersType.bulk_upsert(new_session, filtered_data_list)
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

def wms_get_return_items(session,orders_no_list=None, type_param=None, status_param=None):
    """
    获取采购入库单列表
    :param orders_no_list: 订单号列表
    :param type_param: 类型参数
    :param status_param: 状态参数
    :param session: 数据库会话，传入则使用外部会话
    :return: 采购入库单列表（所有订单的合并结果）
    """
    # 创建 WMS 爬虫实例，用于调用 WMS 系统接口
    spider = WmsGzbbrSpider()
    # 初始化结果列表，用于存储所有采购入库单数据
    all_return_items = 0
    # 初始化计数器，记录成功入库的总条数
    data_total_count = 0

    crm_spider = CrmGzbbrSpider()

    # 判断订单号列表是否为空，如果为空直接返回空列表
    if not orders_no_list:
        # 关闭爬虫连接，释放资源
        spider.close()
        # 返回空列表
        return all_return_items

    # 遍历每个订单号，逐个查询采购入库单
    for orders_no in orders_no_list:
        # 使用 try-except 捕获单个订单的异常，避免一个订单失败导致整个流程中断
        try:
            # 打印当前正在查询的订单号
            print(f"正在查询订单 {orders_no} 的采购入库单...")
            # 调用爬虫的 get_return_items 方法获取指定订单的采购入库单数据，并解析为 JSON
            json_data = spider.get_return_items(orders_no).json()  # pyright: ignore[reportOptionalMemberAccess]

            # 从返回的 JSON 数据中提取退货商品列表，路径为 data -> data -> orders_no
            return_items = json_data.get('data', {}).get('data', {}).get(orders_no, [])
            # 从返回的 JSON 数据中提取订单基本信息（pono、orders_id 等）
            po_info = json_data.get('data', {}).get('po', {})
            # 提取拣货单号
            pono = po_info.get('pono')
            # 提取订单ID
            orders_id = po_info.get('orders_id')
            # 提取供应商全称
            fullname = po_info.get('fullname')

            # 遍历每个商品条目，为其补充订单相关的公共字段
            for item in return_items:
                # 设置拣货单号
                item['pono'] = pono
                # 设置订单编号
                item['orders_no'] = orders_no
                # 设置订单ID
                item['orders_id'] = orders_id
                # 设置类型参数
                item['type_param'] = type_param
                # 设置状态参数（0=未开始，1=正在拣货）
                item['status'] = status_param
                # 设置供应商全称
                item['fullname'] = fullname

            # 将当前订单的商品列表添加到总结果列表中
            all_return_items+=len(return_items)
            # 打印当前订单查询完成的信息和获取到的商品数量
            print(f"订单 {orders_no} 查询完成，获取到 {len(return_items)} 条采购入库单")

            # 判断当前订单是否有采购入库单数据
            if return_items:
                # 调用数据清洗函数对数据进行清洗和字段过滤
                filtered_data_list = clean_return_items(return_items)
                # 打印清洗后的数据条数
                print(f"订单 {orders_no} 清洗后采购入库单数量: {len(filtered_data_list)}")

                # 判断清洗后的数据是否非空
                if filtered_data_list:
                    # 打印开始入库的提示
                    print(f"开始入库订单 {orders_no} 的采购入库单数据...")
                    # 判断是否有外部传入的 session
                
                        # 没有外部 session，则创建新的数据库会话
                    with orm_session() as new_session:
                        # 使用新会话进行批量插入或更新操作
                        count = WmsReturnItems.bulk_upsert(new_session, filtered_data_list)
                        # 累加入库数量到总计数器
                        data_total_count += count
                    # 打印当前订单成功入库的条数
                    print(f"订单 {orders_no} 成功入库 {count} 条采购入库单数据（插入或更新）")

        # 捕获查询过程中可能出现的任何异常
        except Exception as e:
            # 打印错误信息，记录哪个订单查询失败以及失败原因
            print(f"查询订单 {orders_no} 采购入库单时出错: {e}")

    # 所有订单处理完毕后，关闭爬虫连接
    spider.close()
    # 打印总入库数量的汇总信息
    print(f"\n采购入库单数据入库完成，总共处理 {data_total_count} 条数据")
    # 返回所有采购入库单的合并列表
    return all_return_items




def wms_get_return_items_service(session,type_param=None, status_param=None, page_num=None):
    """
    WMS 状态订单爬虫服务

    :param type_param: 类型参数
    :param status_param: 状态参数
    :param page_num: 指定页数，None 表示爬取全部
    :param session: 数据库会话，传入则使用外部会话，否则创建新会话
    """
    # 打印分隔线，标记服务开始
    print("=" * 100)
    # 打印服务开始提示
    print("wms_get_status_orders_type_service 执行开始")
    #token = get_config_value("main_wms_token")
    
    # 调用 wms_get_status_orders_type 获取订单列表数据，is_data_returned=True 表示返回数据
    json_data = wms_get_status_orders_type(type_param=type_param, status_param=status_param, page_num=page_num, is_data_returned=True, session=session)
    
    # 从订单列表中提取所有订单号，过滤掉为空的订单号
    orders_no_list = [item.get('orders_no') for item in json_data if item.get('orders_no')]  # pyright: ignore[reportOptionalIterable]
    # 打印提取到的订单号数量
    print(f"提取到 {len(orders_no_list)} 个订单号")

    # 判断订单号列表是否非空
    if orders_no_list:
        # 打印分隔线
        print("\n" + "=" * 50)
        # 打印开始查询采购入库单的提示
        print("开始查询采购入库单...")
        # 调用 wms_get_return_items 获取采购入库单数据，传入订单号列表、类型、状态和会话
        all_return_items = wms_get_return_items(orders_no_list=orders_no_list, type_param=type_param, status_param=status_param, session=session)
        # 打印总共获取到的采购入库单数量
        print(f"总共获取到 {all_return_items} 条采购入库单数据")
        # 打印分隔线
        print("=" * 50)
        # 打印服务结束提示
        print("wms_get_status_orders_type_service 执行结束")
        # 打印分隔线
        print("=" * 100)
        


if __name__ == '__main__':
    with orm_session() as session:
        wms_get_return_items_service(type_param=5, status_param=0, page_num=None, session=session)
    
  
      
    



# if __name__ == '__main__':
#     wms_get_return_items_service(type_param=5,status_param=0)