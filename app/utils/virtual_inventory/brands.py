# -*- coding: utf-8 -*-
"""
虚拟库存品牌相关工具模块

提供品牌缓存加载、价格规则处理、CRM 别名映射、brands.json 加载等功能。
"""

import json
import os

import pymysql
import pandas as pd

from ..database_connection import get_db_connection as get_pooled_db_connection
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


# 全局品牌缓存
_brand_cache = None


def load_crm_brand_list():
    """
    从 crm_brand_list 表加载品牌列表
    返回: {品牌名: type_cn, ...}
    """
    global _brand_cache

    if _brand_cache is not None:
        return _brand_cache

    conn = get_pooled_db_connection()
    brand_dict = {}

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = "SELECT l_name_zh, type_cn FROM crm_brand_list"
            cursor.execute(sql)
            rows = cursor.fetchall()
            logger.info(f"查询 crm_brand_list 返回 {len(rows)} 行数据")
            for row in rows:
                brand_name = row['l_name_zh'].strip() if row['l_name_zh'] else ''
                type_cn = row['type_cn'].strip() if row['type_cn'] else ''
                if brand_name:
                    brand_dict[brand_name] = type_cn

        _brand_cache = brand_dict
        logger.info(f"已从 crm_brand_list 表加载 {len(brand_dict)} 个品牌")
        return brand_dict
    except Exception:
        logger.exception(f"加载 crm_brand_list 表失败")
        _brand_cache = {}
        return {}
    finally:
        conn.close()


def clear_brand_cache():
    """清除品牌缓存"""
    global _brand_cache
    _brand_cache = None
    logger.info("品牌缓存已清除")


def process_price_by_brand(price, brand, is_wantuo=False, is_changsheng_special=False, company='fsbbr'):
    """
    根据品牌精准匹配处理价格：
    - 所有公司统一规则：原厂+5%，品牌+6%，其他+8%
    - 万拓额外+15%，昌盛特殊产品额外+6%

    :param price: 原始价格
    :param brand: 品牌名称
    :param is_wantuo: 是否为万拓数据，如果是则额外加15%
    :param is_changsheng_special: 是否为昌盛特殊产品（尾号80结尾+原厂再制造），如果是则额外加10%
    :param company: 公司标识（保留参数，不再区分规则）
    """
    if not price or price == '':
        return 0.0

    try:
        price_float = float(price)

        # 获取品牌缓存
        brand_dict = load_crm_brand_list()

        # 基础加点率（百分比）- 所有公司统一规则
        base_rate = 0.0

        # 检查品牌是否在 crm_brand_list 中
        if brand in brand_dict:
            type_cn = brand_dict[brand]
            # 原厂品牌
            if type_cn == '原厂':
                base_rate = 0.05
            # type_cn='品牌'
            elif type_cn == '品牌':
                base_rate = 0.06
            # type_cn='其他品牌'
            else:
                base_rate = 0.08
        else:
            # 品牌不在 crm_brand_list 中
            base_rate = 0.08

        # 额外加点率（万拓+15%，昌盛特殊+6%）
        extra_rate = 0.0
        if is_wantuo:
            extra_rate += 0.15
        elif is_changsheng_special:
            extra_rate += 0.06

        # 总加点率 = 基础加点 + 额外加点
        total_rate = base_rate + extra_rate
        final_price = price_float * (1 + total_rate)
        return round(final_price, 2)

    except (ValueError, TypeError):
        return 0.0


def load_crm_aliases_mapping():
    """
    加载CRM可用别名映射关系
    从static/excel/crm可用别名.xlsx读取数据
    """
    try:
        # 获取当前脚本所在目录，向上两级到达项目根目录，然后进入static/excel目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        excel_path = os.path.join(project_root, "static", "excel", "crm可用别名.xlsx")

        # 检查文件是否存在
        if not os.path.exists(excel_path):
            logger.warning(f"警告: 未找到 {excel_path} 文件，将不进行品牌名称映射")
            return {}

        df = pd.read_excel(excel_path)
        brand_mapping = {}

        # 遍历每一行，解析pp_names字段
        for _, row in df.iterrows():
            pp_name = row['pp_name']
            pp_names_str = str(row['pp_names']) if pd.notna(row['pp_names']) else ""

            # 解析pp_names字段，通常是逗号分隔的多个可能的品牌名
            possible_names = [name.strip() for name in pp_names_str.split(',')]
            for name in possible_names:
                if name and name != "-":  # 忽略占位符"-"
                    brand_mapping[name] = pp_name

        logger.info(f"加载了 {len(brand_mapping)} 个品牌别名映射")
        return brand_mapping
    except Exception as e:
        logger.exception(f"读取CRM可用别名文件时出错")
        return {}


def load_brands_from_json():
    """
    从brands.json文件中加载品牌信息
    """
    try:
        with open('brands.json', 'r', encoding='utf-8') as f:
            brands_data = json.load(f)

        # 提取所有有效的中文品牌名称
        valid_brands = set()
        for brand in brands_data:
            brand_name = brand.get('l_name_zh', '').strip()
            if brand_name:
                valid_brands.add(brand_name)

        logger.info(f"从brands.json加载了 {len(valid_brands)} 个有效品牌")
        return valid_brands

    except FileNotFoundError:
        logger.warning("警告: 未找到brands.json文件，将不过滤品牌数据")
        return None
    except Exception as e:
        logger.exception(f"读取brands.json文件时出错")
        return None
