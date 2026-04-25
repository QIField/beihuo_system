"""
初始化安全库存计算结果表
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.database.tables.safety_stock_tables import init_safety_stock_calculation_table

if __name__ == '__main__':
    print("正在初始化安全库存计算结果表...")
    init_safety_stock_calculation_table()
    print("完成！")
