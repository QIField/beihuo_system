# -*- coding:utf-8 -*-
# @Time    : 2026/6/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_config_service.py
# @Software: PyCharm

"""
华晨宝马（BMW Brilliance）零件库配置服务层
负责处理宝马配件库的配置管理业务逻辑
"""

from typing import Dict, Optional

from app.services.system_setting_service.beihuo_system_config_service import update_json_config
from config.config_list_manager.config_cache import get_config_value


def set_bmw_config(cookie: Optional[str] = None,
                   tax_rate: Optional[float] = None,
                   ) -> Dict:
    """
    设置宝马大库配置

    所有参数都是可选的，如果参数为 None，则保留原有配置不变。

    :param cookie: BMW Brilliance 的登录态 Cookie（可选）
    :param tax_rate: 税率（可选），默认 1.13
    :return: 设置结果字典，包含 code 和 message
    """
    # 构建要更新的字典
    update_dict = {}

    if cookie is not None:
        update_dict['cookie'] = cookie
    if tax_rate is not None:
        update_dict['tax_rate'] = float(tax_rate)
    

    # 使用通用函数更新配置
    return update_json_config(
        'bmw_car_parts_libray',
        update_dict,
        config_group='car_parts',
        label='宝马大库配置',
        remark='用于访问 BMW Brilliance 大库的配置信息及配件价格计算参数'
    )


def get_bmw_config() -> Optional[Dict]:
    """
    获取宝马大库配置

    :return: 配置字典，如果不存在则返回 None
    """
    try:
        config = get_config_value('bmw_car_parts_libray')
        return config  # pyright: ignore[reportReturnType]
    except Exception as e:
        print(f"获取宝马配置失败: {str(e)}")
        return None
