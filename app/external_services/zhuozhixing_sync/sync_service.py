# -*- coding: utf-8 -*-
"""
同步服务主模块

整合API获取、数据处理、数据库存储的完整流程
"""

import time
from datetime import datetime
from typing import List, Dict, Any

from .config import SUPPLIERS
from .api_client import fetch_supplier_data
from .data_processor import process_data
from .db_service import save_supplier_data, clear_all_and_reset_auto_increment


def sync_supplier(supplier_name: str, gsign: str, skip_clear: bool = False) -> Dict[str, Any]:
    """
    同步单个供应商的数据

    完整流程：
    1. 从API获取数据
    2. 数据清洗处理
    3. 保存到数据库

    Args:
        supplier_name: 供应商名称
        gsign: 供应商签名
        skip_clear: 是否跳过清空旧数据（全量同步时已清空整张表，可跳过）

    Returns:
        同步结果
    """
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始同步 {supplier_name}")
    print(f"{'='*60}")

    try:
        # 第一步：获取数据
        raw_data = fetch_supplier_data(supplier_name, gsign)
        if not raw_data:
            print(f"[!] {supplier_name} 没有获取到数据")
            return {
                'supplier': supplier_name,
                'success': False,
                'message': '没有获取到数据',
                'count': 0,
                'time_cost': 0
            }

        # 第二步：数据处理
        records = process_data(raw_data, supplier_name)

        # 第三步：保存到数据库
        result = save_supplier_data(supplier_name, records, skip_clear=skip_clear)

        time_cost = round(time.time() - start_time, 2)
        print(f"\n[{supplier_name}] 同步完成，耗时: {time_cost}秒")

        return {
            'supplier': supplier_name,
            'success': True,
            'message': '同步成功',
            'count': result['inserted'],
            'time_cost': time_cost
        }

    except Exception as e:
        time_cost = round(time.time() - start_time, 2)
        print(f"\n[✗] {supplier_name} 同步失败: {e}")

        return {
            'supplier': supplier_name,
            'success': False,
            'message': str(e),
            'count': 0,
            'time_cost': time_cost
        }


def sync_all_suppliers() -> List[Dict[str, Any]]:
    """
    同步所有供应商的数据

    遍历 SUPPLIERS 配置，依次同步每个供应商

    Returns:
        所有供应商的同步结果列表
    """
    print(f"\n{'#'*60}")
    print(f"# 开始全量同步 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # 先清空整张表并重置自增ID
    clear_all_and_reset_auto_increment()

    results = []

    for supplier_name, config in SUPPLIERS.items():
        result = sync_supplier(supplier_name, config['gsign'], skip_clear=True)
        results.append(result)

    # 打印汇总
    print(f"\n{'#'*60}")
    print(f"# 同步汇总")
    print(f"{'#'*60}")
    success_count = sum(1 for r in results if r['success'])
    total_count = sum(r['count'] for r in results)
    print(f"  成功: {success_count}/{len(results)} 个供应商")
    print(f"  总数据: {total_count} 条")
    for r in results:
        status = "✓" if r['success'] else "✗"
        print(f"  {status} {r['supplier']}: {r['count']} 条 ({r['time_cost']}秒)")
    print(f"{'#'*60}\n")

    return results


# 定时任务调用的入口函数
def zhuozhixing_daily_sync():
    """
    每日同步任务入口

    由定时任务管理器调用，每晚23:00执行
    """
    print(f"\n[定时任务] 卓之星每日同步开始...")
    sync_all_suppliers()
    print(f"[定时任务] 卓之星每日同步结束\n")
