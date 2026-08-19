
# -*- coding:utf-8 -*-
"""
奔驰配件库 data_refresh 测试脚本

直接执行方式（推荐）：

"""

import os
import sys

# ============ 关键：将项目根目录加入 sys.path ============
# 获取当前脚本所在目录 tests/
current_dir = os.path.dirname(os.path.abspath(__file__))
# 项目根目录是 tests/ 的上一级
project_root = os.path.dirname(current_dir)
# 避免重复添加
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ==========================================================

from app.services.car_parts_library_service.car_parts_library_benz_service import data_refresh


# if __name__ == "__main__":
#     print("=" * 80)
#     print(f"项目根目录: {project_root}")
#     print(f"sys.path 前3项: {sys.path[:3]}")
#     print("=" * 80)

#     # 测试奔驰 data_refresh
#     part_numbers = ["A0009063701"]
#     print(f"\n开始刷新以下配件数据: {part_numbers}")
#     result = data_refresh(part_numbers)
#     print("\n返回结果:")
#     print(result)
