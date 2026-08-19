# -*- coding:utf-8 -*-
# @Time    : 2026/6/9
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : mercedes_config_service.py
# @Software: PyCharm

"""
奔驰大库配置服务层
负责处理奔驰大库的配置管理业务逻辑
"""

from typing import Dict, List, Optional

from app.services.system_setting_service.beihuo_system_config_service import update_json_config
from config.config_list_manager.config_cache import get_config_value


def set_mercedes_config(
    username: Optional[str] = None,
    password: Optional[str] = None,
    customer_id: Optional[str] = None,
    sales_organization_id: Optional[str] = None,
    cookie: Optional[str] = None,
    tax_rate: Optional[float] = None,
    discount_rate: Optional[float] = None
) -> Dict:
    """
    设置奔驰大库配置（不含列配置）
    所有参数都是可选的，如果参数为 None，则保留原有配置不变

    :param username: 登录用户名（可选），默认保留原值
    :param password: 登录密码（可选），默认保留原值
    :param customer_id: 客户ID（可选）
    :param sales_organization_id: 销售组织ID（可选）
    :param cookie: Cookie（可选），默认保留原值
    :param tax_rate: 税率（可选），默认保留原值
    :param discount_rate: 折扣率（可选），默认保留原值
    :return: 设置结果
    """
    update_dict = {}

    if username is not None:
        update_dict['username'] = username
    if password is not None:
        update_dict['password'] = password
    if customer_id is not None:
        update_dict['customer_id'] = customer_id
    if sales_organization_id is not None:
        update_dict['sales_organization_id'] = sales_organization_id
    if cookie is not None:
        update_dict['cookie'] = cookie
    if tax_rate is not None:
        update_dict['tax_rate'] = tax_rate
    if discount_rate is not None:
        update_dict['discount_rate'] = discount_rate

    return update_json_config(
        'mercedes_benz',
        update_dict,
        config_group='car_parts',
        label='奔驰大库配置',
        remark='用于访问奔驰大库的配置信息'
    )


def set_benz_column_config(
    column_config: Optional[Dict] = None,
    favorite_column_config: Optional[Dict] = None,
    column_order: Optional[List[str]] = None,
    favorite_column_order: Optional[List[str]] = None
) -> Dict:
    """
    设置奔驰配件列表列配置（独立配置项）

    :param column_config: 配件列表列配置（可选），默认保留原值
    :param favorite_column_config: 收藏列表列配置（可选），默认保留原值
    :param column_order: 配件列表列顺序（可选），默认保留原值
    :param favorite_column_order: 收藏列表列顺序（可选），默认保留原值
    :return: 设置结果
    """
    update_dict = {}

    if column_config is not None:
        update_dict['column_config'] = column_config
    if favorite_column_config is not None:
        update_dict['favorite_column_config'] = favorite_column_config
    if column_order is not None:
        update_dict['column_order'] = column_order
    if favorite_column_order is not None:
        update_dict['favorite_column_order'] = favorite_column_order

    return update_json_config(
        'benz_column_config',
        update_dict,
        config_group='car_parts',
        label='奔驰配件列配置',
        remark='用于奔驰配件库页面的列显示与顺序配置'
    )


def get_benz_column_config() -> Optional[Dict]:
    """
    获取奔驰配件列表列配置

    :return: 列配置字典，如果不存在则返回 None
    """
    try:
        config = get_config_value('benz_column_config')
        return config  # pyright: ignore[reportReturnType]
    except Exception as e:
        print(f"获取奔驰列配置失败: {str(e)}")
        return None


def get_mercedes_config() -> Optional[Dict]:
    """
    获取奔驰大库配置

    :return: 配置字典，如果不存在则返回None
    """
    try:
        config = get_config_value('mercedes_benz')
        return config  # pyright: ignore[reportReturnType]
    except Exception as e:
        print(f"获取奔驰配置失败: {str(e)}")
        return None
