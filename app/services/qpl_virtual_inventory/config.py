#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存导入配置常量
"""

import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Excel 导出文件统一存放目录（与 excel_download.py 约定一致）
EXPORT_DIR = os.path.join(PROJECT_ROOT, 'static', 'exports')

# 生成后的导入文件输出路径
OUTPUT_EXCEL_PATH = os.path.join(EXPORT_DIR, 'qpl_virtual_inventory_import_fsbbr_{date_str}.xlsx')

# 导出文件下载路由 category
DOWNLOAD_CATEGORY = 'qpl_virtual_inventory_import'

# 默认组织
DEFAULT_COMPANY = 'fsbbr'

# 定时任务默认执行时间（cron）
CRON_HOUR = 6
CRON_MINUTE = 0

# 历史文件保留天数
FILE_RETENTION_DAYS = 15
