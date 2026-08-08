"""
购物车数据更新服务

负责从备货表同步数据到购物车表
"""

import pymysql
from typing import Optional
from app.utils.database_connection import get_db_connection


def update_cart_data(store: Optional[str] = None) -> None:
    """
    批量更新购物车中的数据 - 使用物料条码加组织匹配
    
    从 crmapp_beihuo 表获取最新数据，更新到 crmapp_cart 表
    
    Args:
        store: 门店代码，如果指定则只更新该门店的购物车数据
               如果不指定，则更新所有门店的购物车数据
    """
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取购物车数据（如果指定了门店，则只获取该门店的数据）
        if store:
            cursor.execute("SELECT id, barcode, store FROM crmapp_cart WHERE store = %s", (store,))
        else:
            cursor.execute("SELECT id, barcode, store FROM crmapp_cart")
        cart_items = cursor.fetchall()
        
        if not cart_items:
            print("[信息] 购物车为空，无需更新")
            return
        
        # 按门店分组购物车项目
        items_by_store = {}
        for item in cart_items:
            store_key = item['store']
            if store_key not in items_by_store:
                items_by_store[store_key] = []
            items_by_store[store_key].append(item)
        
        # 对每个门店的购物车数据进行批量更新
        for store_key, store_items in items_by_store.items():
            # 提取该门店所有购物车项目的条码
            barcodes = [item['barcode'] for item in store_items if item['barcode']]
            
            if not barcodes:
                continue
            
            # 构建查询语句，使用物料条码和公司（store）匹配
            placeholders = ','.join(['%s'] * len(barcodes))
            select_sql = f"""
                SELECT `供应商`, `品牌`, `物料名称`, `物料条码`, `车型品牌`, `标签`, 
                       `近1个月询价量`, `近3个月月均询价量`, `库存数量`, `昨日销量`, `本月销量`, `今日销量`,
                       `全国近1个月询价量`, `全国近3个月月均询价量`, `内部备注`, `品牌号`, `库存金额`,
                       `成品可卖天数`, `成本价`, `近12个月月均销量`, `近6个月月均销量`, `近7天销量`, `预警状态`, `在途数量`, `车型`, `替换号`, `purchase_records`
                FROM crmapp_beihuo 
                WHERE `物料条码` IN ({placeholders}) AND `company` = %s
            """
            cursor.execute(select_sql, barcodes + [store_key])
            latest_data_list = cursor.fetchall()
            
            # 构建条码到最新数据的映射
            latest_data_map = {item['物料条码']: item for item in latest_data_list}
            
            # 准备批量更新数据
            update_data_for_batch = []
            for item in store_items:
                if item['barcode'] in latest_data_map:
                    latest_data = latest_data_map[item['barcode']]
                    update_data_for_batch.append((
                        latest_data['供应商'],
                        latest_data['品牌'],
                        latest_data['物料名称'],
                        latest_data['车型品牌'],
                        latest_data['标签'],
                        latest_data['近1个月询价量'],
                        latest_data['近3个月月均询价量'],
                        latest_data['库存数量'],
                        latest_data['昨日销量'],
                        latest_data['本月销量'],
                        latest_data['今日销量'],
                        latest_data['全国近1个月询价量'],
                        latest_data['全国近3个月月均询价量'],
                        latest_data['内部备注'],
                        latest_data['品牌号'],
                        latest_data['库存金额'],
                        latest_data['成品可卖天数'],
                        latest_data['成本价'],
                        latest_data['近12个月月均销量'],
                        latest_data['近6个月月均销量'],
                        latest_data['近7天销量'],
                        latest_data['预警状态'],
                        latest_data['在途数量'],
                        latest_data['车型'],
                        latest_data['替换号'],
                        latest_data['purchase_records'],
                        item['id']
                    ))
            
            # 批量更新购物车表中的数据
            if update_data_for_batch:
                update_sql = """
                    UPDATE crmapp_cart 
                    SET supplier = %s, brand = %s, material_name = %s, car_brand = %s, tag = %s,
                        inquiry_1m = %s, inquiry_3m = %s, stock = %s, sales_yesterday = %s, 
                        sales_month = %s, today_sales = %s, national_inquiry_1m = %s, 
                        national_inquiry_3m = %s, internal_remarks = %s, brand_code = %s, 
                        stock_amount = %s, sellable_days = %s, cost_price = %s, 
                        avg_sales_12m = %s, avg_sales_6m = %s, sales_7d = %s, warning_status = %s, 
                        on_way = %s, car_model = %s, replace_number = %s, purchase_records = %s
                    WHERE id = %s
                """
                cursor.executemany(update_sql, update_data_for_batch)
                conn.commit()
        
        print(f"[成功] 购物车数据批量更新完成，共处理 {len(cart_items)} 条记录")
        
    except Exception as e:
        conn.rollback()
        print(f"[失败] 更新购物车数据失败: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()
