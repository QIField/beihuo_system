# -*- coding:utf-8 -*-
# @Time    : 2026/4/17 15:41
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : beihuo_system_config.py.py
# @Software: PyCharm
from app.models.orm_models.beihuo_system_config import BeihuoSystemConfig
from app.utils.orm import orm_session

if __name__ == '__main__':
    with orm_session() as session:
        total,data_list=BeihuoSystemConfig.get_paged_configs(session)
        for data in data_list:
            print("="*20,data)
            print(f"{data.config_key}   {data.config_value}")
