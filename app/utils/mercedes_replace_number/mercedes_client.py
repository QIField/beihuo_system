# -*- coding: utf-8 -*-
"""
奔驰零件信息接口（不入库）
"""

import json
from typing import Dict, List

from app.scripts.spiders.spider_entities.mercedes_dalfsc import MercedesDalfscSpider
from app.scripts.spiders.pipeline_clean.mercedes_dalfsc_clean import clean_parts_information
from config.config_list_manager.config_cache import get_config_value

from app.utils.logger_config import get_task_logger
from .config import TASK_NAME


logger = get_task_logger(TASK_NAME)


def fetch_part_info(part_number: str, excluded_number: str = None) -> Dict:
    """
    调奔驰零件信息接口，解析替换号树并返回产品信息。

    Returns:
        {
            'replace_numbers': [...],
            'product_name': '产品中文描述',
            'oe_brand_name': '奔驰',
        }
    """
    config = get_config_value('mercedes_benz')
    customer_id = config.get('customer_id', '193211390')
    sales_organization_id = config.get('sales_organization_id', 'O 50000741')

    spider = MercedesDalfscSpider()
    try:
        response = spider.get_parts_informations(part_number, customer_id, sales_organization_id)
        if not response:
            logger.warning(f"奔驰接口无响应: {part_number}")
            return {'replace_numbers': [], 'product_name': '', 'oe_brand_name': ''}

        data = response.json()
        clean_data = clean_parts_information(data)
        super_session = json.loads(clean_data.get('part_nr_info_super_session') or '{}')

        numbers = []
        _traverse_super_session(super_session, numbers)

        seen = set()
        result = []
        for num in numbers:
            num = num.replace(' ', '').strip()
            if not num or num in seen:
                continue
            if excluded_number and num.upper() == excluded_number.upper():
                continue
            seen.add(num)
            result.append(num)

        logger.info(f"奔驰接口 {part_number} 获取到 {len(result)} 个替换号")
        return {
            'replace_numbers': result,
            'product_name': clean_data.get('description_cn', ''),
            'oe_brand_name': clean_data.get('brand', ''),
        }

    except Exception:
        logger.exception(f"奔驰接口调用失败: {part_number}")
        return {'replace_numbers': [], 'product_name': '', 'oe_brand_name': ''}
    finally:
        spider.close()


def fetch_replace_numbers(part_number: str, excluded_number: str = None) -> List[str]:
    """
    调奔驰零件信息接口，解析替换号树。

    Args:
        part_number: 带 A 的完整 OE
        excluded_number: 需要过滤掉的不带 A 版本号

    Returns:
        去空格、去重、过滤 excluded_number 后的替换号列表
    """
    return fetch_part_info(part_number, excluded_number).get('replace_numbers', [])


def _traverse_super_session(node, result: List[str]):
    """递归遍历替换号树，收集所有 partNo.number。"""
    if not isinstance(node, dict):
        return
    part_no = node.get('partNo', {})
    number = part_no.get('number', '')
    if number:
        result.append(str(number).strip())
    for child in node.get('children', []):
        _traverse_super_session(child, result)
