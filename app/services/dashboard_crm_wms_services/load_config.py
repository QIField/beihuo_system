# -*- coding:utf-8 -*-
# @Time    : 2026/4/2 15:11
# @Author  : xingkongtub
# @Project : overall_project
# @File    : load_config.py
# @Software: PyCharm


import json
import os

# 配置文件路径
# CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# 1. 获取当前 load_config.py 所在的文件夹路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2. 拼接成完整的配置文件路径（和你实际文件名完全一致！）
CONFIG_PATH = os.path.join(BASE_DIR, "dashboard_crm_wms_config.json")

def get_config():
    """✅ 每次都读取文件，实时生效"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


