# -*- coding:utf-8 -*-
# @Time    : 2026/07/27
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test3.py
# @Software: trae-cn

import sys
import os
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    print("=" * 80)
    print("测试 run_full_process 运行时间")
    print("=" * 80)
    
    try:
        from app.services.stock_safe_service.stock_safe_refund_ref_service import run_full_process
        
        print("\n开始执行 run_full_process...")
        print("-" * 80)
        
        start_total = time.time()
        
        result = run_full_process()
        
        end_total = time.time()
        actual_total_time = round(end_total - start_total, 2)
        
        print("\n" + "=" * 80)
        print("运行时间统计结果")
        print("=" * 80)
        
        print(f"\n【总耗时】: {actual_total_time} 秒")
        print(f"  返回值中总耗时: {result['total_elapsed_time']} 秒")
        
        print("\n【Step 1】批量插入未匹配退货订单")
        print(f"  耗时: {result['step1']['elapsed_time']} 秒")
        print(f"  插入记录数: {result['step1']['inserted_count']}")
        print(f"  批次大小: {result['step1']['batch_size']}")
        
        print("\n【Step 2】批量匹配常规订单")
        print(f"  耗时: {result['step2']['elapsed_time']} 秒")
        print(f"  总处理数: {result['step2']['total_processed']}")
        print(f"  匹配成功: {result['step2']['matched_count']}")
        print(f"  未匹配: {result['step2']['unmatched_count']}")
        print(f"  批次大小: {result['step2']['batch_size']}")
        
        print("\n【Step 3】处理常规订单剩余数量匹配退货订单")
        print(f"  耗时: {result['step3']['elapsed_time']} 秒")
        print(f"  总处理数: {result['step3']['total_processed']}")
        print(f"  匹配成功: {result['step3']['matched_count']}")
        print(f"  未匹配: {result['step3']['unmatched_count']}")
        print(f"  总匹配对数: {result['step3']['total_matched_pairs']}")
        print(f"  批次大小: {result['step3']['batch_size']}")

        print("\n【统计摘要】")
        print(f"  待处理订单数: {result['summary']['pending_count']}")
        print(f"  未完全抵消退货数(type31/32/33): {result['summary']['type3_count']}")
        print(f"  类型分布: {result['summary']['type_distribution']}")
        
        print("\n" + "=" * 80)
        print("测试完成！")
        print("=" * 80)
        
    except ImportError as e:
        print(f"\n[错误] 导入模块失败: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n[错误] 执行异常: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
