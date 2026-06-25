# -*- coding:utf-8 -*-
# @Time    : 2026/5/5 16:34
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_inbound_push.py
# @Software: PyCharm
from app.scripts.spiders.spiders_services.cassmall_product_list import cassmall_product_list_search, \
    cassmall_update_inventory_batch, cassmall_get_inventorys
from app.scripts.spiders.spiders_services.wms_get_status_orders_type import wms_get_return_items_service
from app.utils.orm.session import orm_session
from app.models.orm_models.wms_return_items import WmsReturnItems
from app.services.system_setting_service.beihuo_system_config_service import set_config_by_key


def wms_get_return_items_data():
    """
    WMS 状态订单爬虫服务 - 重新爬取数据
    """
    return_items = wms_get_return_items_service(type_param=5, status_param=0, page_num=None)
    return return_items


def wms_get_return_items_from_db(page=1, limit=20, has_pushed_ks=''):
    """
    从数据库获取采购入库单数据（分页，只返回status=0的数据）
    
    :param page: 页码，从1开始
    :param limit: 每页数量
    :param has_pushed_ks: 推送状态筛选（''表示全部，'0'表示未推送，'1'表示已推送）
    :return: (数据列表, 总条数)
    """
    try:
        with orm_session() as session:
            # 查询条件：只返回status=0的数据
            query = session.query(WmsReturnItems).filter(WmsReturnItems.status == 0)
            
            # 添加has_pushed_ks筛选条件
            if has_pushed_ks in ['0', '1']:
                query = query.filter(WmsReturnItems.has_pushed_ks == int(has_pushed_ks))
            
            # 获取总条数
            total = query.count()
            
            # 分页查询
            offset = (page - 1) * limit
            items = query.order_by(WmsReturnItems.updated_at.desc()).offset(offset).limit(limit).all()
            
            # 转换为字典列表
            result = []
            for item in items:
                result.append(item.to_dict())
            
            print(f"从数据库查询到 {len(result)} 条采购入库单数据，共 {total} 条")
            return result, total
    except Exception as e:
        print(f"从数据库查询采购入库单数据失败: {str(e)}")
        return [], 0



def get_cassmall_product_list_search(internal_name):
    
    ks_json_data=cassmall_product_list_search(internal_name)
    if ks_json_data.get('data'):
        # 获取数据列表
        data_list = ks_json_data.get('data', [])
        # 进行绝对匹配筛选
        matched_list = []
        for item in data_list:
            if item.get('internalName') == internal_name:
                matched_list.append(item)
        # 更新数据
        ks_json_data['data'] = matched_list
        print(f"原始数据 {len(data_list)} 条，匹配后 {len(matched_list)} 条")
        if len(matched_list) > 0:
            ks_json_data['message'] = f"搜索成功，匹配到 {len(matched_list)} 条数据"
        else:
            ks_json_data['message'] = f"{internal_name}没有搜索到对应的商家编码，请创建商家编码"
        return ks_json_data
    else:
        print(ks_json_data)
        return ks_json_data


def inventory_sync(product_id, availableToPromiseTotal, record_id=None):
    # 查询库存
    print("=== 查询库存...")

    inventory_result = cassmall_get_inventorys([product_id])
    print("查询结果:", inventory_result)

    # 直接从查询结果中提取数据并组合
    print("\n=== 组合更新数据...")
    inventory_data = inventory_result.get('data', {})

    product_info = inventory_data.get(product_id, {})
    inv_list = product_info.get('inventory', [])

    # 手动组合两个仓库的数据
    inventory_list = [
        {
            "facilityId": inv_list[0].get('facilityId'),
            "availableToPromiseTotal": availableToPromiseTotal,
            "safeToPromiseTotal": inv_list[0].get('safeToPromiseTotal', 0),
            "productId": product_id
        },
        {
            "facilityId": inv_list[1].get('facilityId'),
            "availableToPromiseTotal": inv_list[1].get('availableToPromiseTotal', 0),
            "safeToPromiseTotal": inv_list[1].get('safeToPromiseTotal', 0),
            "productId": product_id
        }
    ]

    print("组合后的格式:", inventory_list)

    print("\n=== 更新库存...")
    update_result = cassmall_update_inventory_batch(inventory_list)
    
    # 如果推送成功，更新数据库中的 has_pushed_ks 字段
    message = update_result.get('message', '')
    if '更新库存成功' in message and record_id:
        try:
            with orm_session() as session:
                # 根据 id 更新记录
                session.query(WmsReturnItems).filter(
                    WmsReturnItems.id == record_id
                ).update({
                    WmsReturnItems.has_pushed_ks: 1
                })
                session.commit()
                print(f"已更新 id={record_id} 的 has_pushed_ks 为 1")
        except Exception as e:
            print(f"更新 has_pushed_ks 失败: {str(e)}")
    
    return update_result


def inventory_sync_batch(items):
    """
    批量同步库存到开思
    
    :param items: 列表，每个元素包含 {'product_id': xxx, 'availableToPromiseTotal': xxx, 'record_id': xxx}
    :return: 批量处理结果
    """
    if not items:
        return {'code': 400, 'message': '没有数据需要同步'}
    
    print(f"=== 开始批量同步库存，共 {len(items)} 条数据 ===")
    
    success_count = 0
    failed_count = 0
    results = []
    
    for idx, item in enumerate(items, 1):
        product_id = item['product_id']
        availableToPromiseTotal = item['availableToPromiseTotal']
        record_id = item.get('record_id')
        
        print(f"\n=== 处理第 {idx}/{len(items)} 条数据 ===")
        print(f"product_id: {product_id}, availableToPromiseTotal: {availableToPromiseTotal}")
        
        try:
            # 调用单个更新函数
            result = inventory_sync(product_id, availableToPromiseTotal, record_id)
            results.append({
                'product_id': product_id,
                'result': result
            })
            
            message = result.get('message', '')
            if '更新库存成功' in message:
                success_count += 1
                print(f"✅ 第 {idx} 条数据更新成功")
            else:
                failed_count += 1
                print(f"❌ 第 {idx} 条数据更新失败: {message}")
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            results.append({
                'product_id': product_id,
                'error': error_msg
            })
            print(f"❌ 第 {idx} 条数据处理异常: {error_msg}")
    
    print(f"\n=== 批量同步完成 ===")
    print(f"成功: {success_count}, 失败: {failed_count}")
    
    return {
        'code': 200,
        'message': f'批量同步完成，成功 {success_count} 条，失败 {failed_count} 条',
        'data': {
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }
    }


def set_cookie(cookie):
    """
    设置 Cookie 配置
    :param cookie: Cookie 字符串
    :return: 设置结果
    """
    try:
        set_config_by_key(
            'main_ks_cookie',
            cookie,
            config_group='wms',
            label='开思mall Cookie',
            remark='用于访问开思mall的Cookie'
        )
        return {
            'code': 200,
            'message': 'Cookie设置成功'
        }
    except Exception as e:
        return {
            'code': 500,
            'message': f'Cookie设置失败: {str(e)}'
        }


# if __name__ == '__main__':
#     # a=get_cassmall_product_list_search("PGN10571-18B1")
#     # print(a)
#     # b=inventory_sync(product_id = "21211694423523821150",availableToPromiseTotal=2)
#     # print(b)
