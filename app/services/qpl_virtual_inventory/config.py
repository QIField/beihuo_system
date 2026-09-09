#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存导入配置常量
"""

import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 生成后的导入文件输出路径
OUTPUT_EXCEL_PATH = os.path.join(PROJECT_ROOT, 'static', 'excel', 'qpl_product_import.xlsx')

# 上传失败后文件归档目录
FAILED_DIR = os.path.join(PROJECT_ROOT, 'static', 'excel', 'qpl_product_import_failed')

# 默认组织
DEFAULT_COMPANY = 'fsbbr'

# 定时任务默认执行时间（cron）
CRON_HOUR = 6
CRON_MINUTE = 0
