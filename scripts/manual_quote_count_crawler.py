"""
手动运行版本 - 开思询价次数统计爬取
用于初始化近36个月的询价数据

运行方式:
    python scripts/manual_quote_count_crawler.py

处理逻辑：
    - 循环爬取近36个月的数据（每个月为一批次）
    - 每月独立爬取、统计、保存（覆盖模式）
    - 从远到近处理（先处理最早的月份）
    - 失败自动重试（最多3次）
    - 直接连接线上数据库
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta
from app.services.quote_count_service import QuoteCountSyncService

# 重试配置
MAX_RETRY = 3
RETRY_DELAY = 5  # 重试间隔（秒）


def get_recent_36_months():
    """
    获取近36个月的年月列表
    从远到近排序（如：2022-04, 2022-05, ..., 2025-03）

    Returns:
        List[Tuple[int, int]]: [(year, month), ...]
    """
    months = []
    now = datetime.now()
    
    # 从当前月往前推算36个月
    current_year = now.year
    current_month = now.month
    
    for i in range(35, -1, -1):  # 从35个月前到当前月
        # 计算偏移后的月份
        year_offset = (current_month - i - 1) // 12
        month_offset = (current_month - i - 1) % 12
        
        year = current_year + year_offset
        month = month_offset + 1
        
        months.append((year, month))

    return months


def main():
    """
    主函数：循环爬取近36个月的询价数据
    """
    print("=" * 70)
    print("开思询价次数统计手动爬取工具")
    print("=" * 70)
    print("本脚本将爬取近36个月的询价数据")
    print("每个月为一批次，独立处理保存")
    print("直接连接线上数据库")
    print("=" * 70)

    # 创建服务实例（内部会自动处理双方案登录）
    print("\n[初始化] 正在初始化服务（自动选择登录方案）...")
    service = QuoteCountSyncService()
    print("[初始化] 服务初始化完成")

    # 获取近36个月的年月列表
    months_to_sync = get_recent_36_months()

    print(f"\n[计划] 将处理以下 {len(months_to_sync)} 个月份:")
    for year, month in months_to_sync:
        print(f"  - {year}-{month:02d}")

    all_results = {
        'months': [],
        'total_orders': 0,
        'total_items': 0,
        'total_saved': 0,
        'total_failed': 0
    }

    # 循环处理每个月份
    for idx, (year, month) in enumerate(months_to_sync, 1):
        year_month = f"{year}-{month:02d}"

        print(f"\n{'='*70}")
        print(f"[批次 {idx}/{len(months_to_sync)}] 处理 {year_month} 的数据")
        print(f"{'='*70}")

        # 重试机制
        retry_count = 0
        success = False

        while retry_count < MAX_RETRY and not success:
            if retry_count > 0:
                print(f"[重试] 第 {retry_count}/{MAX_RETRY} 次重试处理 {year_month}...")
                time.sleep(RETRY_DELAY)

            try:
                # 执行同步
                result = service.sync_month(year, month)

                all_results['months'].append(year_month)
                all_results['total_orders'] += result['orders']
                all_results['total_items'] += result['items']
                all_results['total_saved'] += result['saved']
                all_results['total_failed'] += result['failed']

                print(f"[批次完成] 订单:{result['orders']}, "
                      f"明细:{result['items']}, "
                      f"保存:{result['saved']}, "
                      f"失败:{result['failed']}")

                success = True

            except Exception as e:
                retry_count += 1
                print(f"[批次错误] 处理 {year_month} 时出错 (尝试 {retry_count}/{MAX_RETRY}): {e}")

                if retry_count >= MAX_RETRY:
                    print(f"[批次失败] {year_month} 重试次数已耗尽，跳过该月份")
                    import traceback
                    traceback.print_exc()
                else:
                    print(f"[重试] 等待 {RETRY_DELAY} 秒后重试...")

        if not success:
            continue

        # 月份之间暂停一下，避免请求过快
        if idx < len(months_to_sync):
            print("[暂停] 等待2秒后继续处理下一个月...")
            time.sleep(2)

    # 输出最终统计
    print("\n" + "=" * 70)
    print("爬取完成!")
    print("=" * 70)
    print(f"处理月份: {', '.join(all_results['months'])}")
    print(f"总订单数: {all_results['total_orders']}")
    print(f"总明细数: {all_results['total_items']}")
    print(f"保存记录: {all_results['total_saved']}")
    print(f"失败订单: {all_results['total_failed']}")
    print("=" * 70)


if __name__ == '__main__':
    main()
