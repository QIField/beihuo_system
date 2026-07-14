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
    - 所有公司统一规则：原厂+6%，品牌+8%，其他+10%
    - 万拓额外+16%，昌盛特殊产品额外+7%

    :param price: 原始价格
    :param brand: 品牌名称
    :param is_wantuo: 是否为万拓数据，如果是则额外加16%
    :param is_changsheng_special: 是否为昌盛特殊产品（尾号80结尾+备注含"是惠选件"），如果是则额外加7%
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
                base_rate = 0.06
            # type_cn='品牌'
            elif type_cn == '品牌':
                base_rate = 0.08
            # type_cn='其他品牌'
            else:
                base_rate = 0.10
        else:
            # 品牌不在 crm_brand_list 中
            base_rate = 0.10

        # 额外加点率（万拓+16%，昌盛特殊+7%）
        extra_rate = 0.0
        if is_wantuo:
            extra_rate += 0.16
        elif is_changsheng_special:
            extra_rate += 0.07

        # 总加点率 = 基础加点 + 额外加点
        total_rate = base_rate + extra_rate
        final_price = price_float * (1 + total_rate)
        return round(final_price, 2)

    except (ValueError, TypeError):
        return 0.0


def _get_project_root():
    """
    查找项目根目录。

    从当前文件所在目录开始向上逐级查找，直到找到包含 beihuo_system.py 的目录。
    这种实现不依赖固定的目录层级，本地和线上部署都能自适应。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.exists(os.path.join(current_dir, "beihuo_system.py")):
            return current_dir
        parent = os.path.dirname(current_dir)
        if parent == current_dir:
            # 已到文件系统根目录仍未找到，fallback 到原来的固定层级
            break
        current_dir = parent

    # fallback：按原来的相对层级计算
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(current_dir))


def load_crm_aliases_mapping():
    """
    加载CRM可用别名映射关系
    从static/excel/crm可用别名.xlsx读取数据
    """
    try:
        project_root = _get_project_root()
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


# 全局品牌标准化映射表：集中管理所有供应商的硬编码品牌映射
BRAND_NORMALIZATION_MAPPING = {
    'FC': '巴博瑞',
    'TRW': '天合',
    'VDO': '威迪欧',
    '博格华纳BORG': '博格华纳',
    '博世(BOSCH)BS': '博世',
    '岱高进口': '岱高',
    '进口威巴克': '威巴克',
    '原厂(SJZX)': '原厂',
    'WANTUO': '巴博瑞',
    '菲儿': '菲尔',
    '品牌': '巴博瑞',
    '原厂国外': '原厂',
    '原厂大库': '原厂国内4s件',
    '赛多夫': '巴博瑞',
    '猫头鹰': '伦福德(猫)',
    '下线': 'XX',
    '原厂件': '原厂',
    '其它': '其他',
    '尼兰': '其他',
    '陆地卫士': '其他',
    '曼克马利': '巴博瑞',
    '伦福德': '伦福德(猫)',
    '科尔本施密特': '科尔本',
    '路爵士': '巴博瑞',
    '优宾': '巴博瑞',
    '卡玛伦': '巴博瑞',
    '汉科再生': '巴博瑞',
    '长虹': '巴博瑞',
    '都得利': '巴博瑞',
    '台湾提维西': '巴博瑞',
    '台湾维仑': '巴博瑞',
    '维轮AP': '巴博瑞',
    '亿升钣金': '巴博瑞',
    'ANHUO': '巴博瑞',
    '隆丰': '巴博瑞',
    '鹰眼': '巴博瑞',
}


def normalize_brand(brand, supplier=None):
    """
    标准化品牌名称。

    :param brand: 原始品牌名称
    :param supplier: 已废弃，保留参数仅用于兼容旧调用
    :return: 标准化后的品牌名称；若未匹配则返回原值
    """
    if not brand:
        return brand

    normalized = BRAND_NORMALIZATION_MAPPING.get(str(brand).strip(), brand)
    return normalized
