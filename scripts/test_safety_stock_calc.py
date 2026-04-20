"""
安全库存计算测试脚本
用于手动执行计算并测试数据
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.safety_stock_service import execute_daily_calculation


def main():
    """执行安全库存计算测试"""
    print("=" * 80)
    print("安全库存计算测试")
    print("=" * 80)
    
    try:
        count = execute_daily_calculation()
        print(f"\n✅ 计算完成！共处理 {count} 条产品记录")
    except Exception as e:
        print(f"\n❌ 计算失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("=" * 80)
    return 0


if __name__ == '__main__':
    exit(main())
