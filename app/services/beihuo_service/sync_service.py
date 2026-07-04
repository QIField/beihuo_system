"""
备货数据同步服务

整合 API 调用、数据处理和数据库操作的完整流程。
"""

import threading
from datetime import datetime
from typing import Dict, Any, List

from . import api_client
from . import data_processor
from . import db_service
from .config import COMPANIES

# 并发控制锁
_fetch_task_lock = threading.Lock()
_updating_lock = threading.Lock()
_is_updating_flag = False


def update_company(company: str) -> Dict[str, Any]:
    """
    更新单个门店数据
    
    调用更新 API 触发后台数据更新
    
    Args:
        company: 门店代码
        
    Returns:
        更新结果
    """
    print(f"[更新] 开始更新门店 {company}...")
    result = api_client.update_company(company)
    
    if result['success']:
        print(f"[成功] 门店 {company} 更新请求发送成功: {result['message']}")
    else:
        print(f"[失败] 门店 {company} 更新请求失败: {result['message']}")
    
    return result


def update_all_companies() -> Dict[str, Any]:
    """
    更新所有门店数据
    
    依次调用所有门店的更新 API
    
    Returns:
        更新汇总结果
    """
    print(f"\n{'='*60}")
    print(f"开始更新所有门店数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    success_count = 0
    results = []
    
    for company in COMPANIES:
        result = update_company(company)
        results.append({
            'company': company,
            'success': result['success'],
            'message': result['message']
        })
        if result['success']:
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"更新完成！成功: {success_count}/{len(COMPANIES)}")
    print(f"{'='*60}\n")
    
    # 执行更新后的清理操作
    _post_update_cleanup()
    
    return {
        'success_count': success_count,
        'total': len(COMPANIES),
        'results': results
    }


def _post_update_cleanup():
    """更新后的清理操作"""
    try:
        from app.services.data_sync_service.update_completion_handler import UpdateCompletionHandler
        handler = UpdateCompletionHandler()
        cleanup_results = handler.handle_post_update_operations()
        
        if cleanup_results['cart_cleanup']['status'] == 'completed':
            total_deleted = cleanup_results['cart_cleanup']['total_deleted']
            print(f"[定时] 定时更新后清理完成：共删除 {total_deleted} 个高库存商品")
    except Exception as e:
        print(f"[失败] 定时更新后清理失败: {e}")


def _merge_vehicle_mapping(company: str, records: list) -> list:
    """
    从 crmapp_compare_summary 获取车型映射，合并到 records 中
    
    优化策略：使用INNER JOIN只查询beihuo表中实际存在的条码的映射数据
    性能提升：从扫描12万条减少到几千条
    
    Args:
        company: 门店代码
        records: 数据记录列表
        
    Returns:
        合并后的记录列表
    """
    import pymysql.cursors
    from app.utils.database_connection import get_db_connection
    
    if not records:
        return records
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取所有物料条码
        barcodes = [r.get('物料条码') for r in records if r.get('物料条码')]
        
        if not barcodes:
            return records
        
        # 查询车型映射（使用BINARY避免字符集冲突）
        placeholders = ','.join(['%s'] * len(barcodes))
        cursor.execute(f"""
            SELECT frey_no, l_model_zh, replace_number
            FROM crmapp_compare_summary
            WHERE company = %s 
              AND frey_no IN ({placeholders})
              AND frey_no IS NOT NULL 
              AND frey_no != ''
        """, (company,) + tuple(barcodes))
        
        mappings = {row['frey_no']: row for row in cursor.fetchall()}
        
        # 合并映射数据到 records
        merged_count = 0
        for record in records:
            barcode = record.get('物料条码')
            if barcode and barcode in mappings:
                mapping = mappings[barcode]
                # 优先使用映射表的车型，如果不存在则保留原有车型
                if mapping.get('l_model_zh'):
                    record['车型'] = mapping['l_model_zh']
                # 设置替换号
                record['替换号'] = mapping.get('replace_number', '')
                merged_count += 1
        
        print(f"[车型] 门店 {company} 车型映射合并完成，共 {merged_count}/{len(records)} 条记录")
        return records
        
    except Exception as e:
        print(f"[警告] 门店 {company} 车型映射合并失败: {e}，继续保存原始数据")
        return records
    finally:
        cursor.close()
        conn.close()


def fetch_company(company: str) -> int:
    """
    拉取单个门店数据
    
    调用拉取 API 获取数据，合并车型映射后保存到数据库
    
    Args:
        company: 门店代码
        
    Returns:
        成功插入的记录数，失败返回 -1
    """
    print(f"[导入] 开始拉取门店 {company} 数据...")
    
    # 1. 调用 API 获取数据
    api_result = api_client.fetch_company(company)
    
    if not api_result['success']:
        print(f"[失败] 门店 {company} 拉取失败: {api_result['message']}")
        return -1
    
    raw_data = api_result['data']
    gx_date = api_result['gx_date']
    
    if not raw_data:
        print(f"[警告] 门店 {company} 没有数据")
        return 0
    
    print(f"[统计] 门店 {company} 获取到 {len(raw_data)} 条原始数据")
    
    # 2. 数据处理
    records = data_processor.transform_fetch_data(raw_data, company, gx_date)
    
    # 3. 获取车型映射数据并合并到 records
    print(f"[车型] 门店 {company} 开始获取车型映射...")
    records = _merge_vehicle_mapping(company, records)
    
    # 4. 保存到数据库（已包含车型和替换号）
    saved_count = db_service.save_company_data(company, records)
    
    if saved_count >= 0:
        print(f"[成功] 门店 {company} 数据保存完成，共 {saved_count} 条")
        
        # 5. 异步执行购物车更新（车型映射已完成，不需要再执行）
        threading.Thread(target=_update_cart_only, args=(company,), daemon=True).start()
    else:
        print(f"[失败] 门店 {company} 数据保存失败")
    
    return saved_count


def _update_cart_only(company: str):
    """仅更新购物车数据（车型映射已在保存前完成）"""
    print(f"[购物车] [{company}] 开始更新购物车...")
    from app.services.cart_service.cart_update_service import update_cart_data
    update_cart_data(company)  # 只更新当前门店的购物车
    print(f"[成功] [{company}] 购物车更新完成")


def fetch_all_companies() -> Dict[str, Any]:
    """
    拉取所有门店数据
    
    依次拉取所有门店的数据并保存
    
    Returns:
        拉取汇总结果
    """
    with _fetch_task_lock:
        print(f"\n{'='*60}")
        print(f"开始拉取所有门店数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        success_count = 0
        total_records = 0
        results = []
        
        for company in COMPANIES:
            count = fetch_company(company)
            results.append({
                'company': company,
                'count': count,
                'success': count >= 0
            })
            if count >= 0:
                success_count += 1
                total_records += count
        
        # 更新购物车数据
        _update_cart_data()
        
        print(f"\n{'='*60}")
        print(f"拉取完成！成功: {success_count}/{len(COMPANIES)}，共 {total_records} 条记录")
        print(f"{'='*60}\n")
        
        return {
            'success_count': success_count,
            'total': len(COMPANIES),
            'total_records': total_records,
            'results': results
        }


def _update_cart_data():
    """更新购物车数据"""
    try:
        from app.services.cart_service.cart_update_service import update_cart_data
        update_cart_data()
        print("[购物车] 购物车数据更新完成")
    except Exception as e:
        print(f"[购物车] 购物车数据更新失败: {e}")


def update_then_fetch_all():
    """
    先更新所有门店，然后延迟15分钟后拉取
    
    这是定时任务的入口函数
    """
    global _is_updating_flag
    
    with _updating_lock:
        if _is_updating_flag:
            print("[跳过] 已有更新任务在执行，跳过本次执行")
            return
        _is_updating_flag = True
    
    try:
        print(f"\n{'#'*60}")
        print(f"# 开始自动更新+拉取任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}")
        
        # 1. 执行更新
        update_result = update_all_companies()
        
        # 2. 设置15分钟后拉取
        print(f"⏰ 将在15分钟后执行数据拉取...")
        from threading import Timer
        Timer(15 * 60, fetch_all_companies).start()
        
    finally:
        _is_updating_flag = False
