# -*- coding:utf-8 -*-
# @Time    : 2026/06/17
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_bmw_dao.py
# @Software : trae-cn

"""
华晨宝马配件库数据访问层
负责处理 car_parts_library_bmw 表的数据库原生 SQL 操作
"""

from typing import List, Dict
from sqlalchemy import text
from app.models.orm_models.car_parts_library_bmw import CarPartsLibraryBmw


class CarPartsLibraryBmwDao:
    """
    华晨宝马配件库数据访问类
    """

    @staticmethod
    def batch_upsert(session, data_list: List[Dict]) -> int:
        """
        批量插入或更新数据（以 part_number 为唯一索引）

        使用原生 SQL 的 INSERT ... ON DUPLICATE KEY UPDATE，真正批量执行

        :param session: 数据库会话
        :param data_list: 数据列表
        :return: 处理的记录数
        """
        if not data_list:
            return 0

        try:
            # 确保所有数据的 part_number 都去除空格（安全措施）
            processed_data_list = []
            for data in data_list:
                if 'part_number' in data and data['part_number']:
                    data = data.copy()
                    data['part_number'] = str(data['part_number']).replace(' ', '')
                processed_data_list.append(data)

            # car_parts_library_bmw 表的所有字段（除 created_at/updated_at，这两个由数据库自动处理）
            all_columns = [
                'part_number', 'part_name', 'sales_unit', 'material_group',
                'gross_weight', 'net_weight', 'volume', 'retail_price',
                'discount_stock', 'discount_rush', 'dealer_net_stock',
                'dealer_net_rush', 'available_stock', 'data_collect_time',
            ]

            # 获取第一条数据的字段作为参考
            first_data = processed_data_list[0]
            insert_columns = []
            for col in all_columns:
                if col in first_data:
                    insert_columns.append(col)

            if not insert_columns:
                return 0

            # 构建更新字段列表（排除 part_number）
            update_columns = [col for col in insert_columns if col not in ['part_number']]
            update_clause = ', '.join([f'{col} = VALUES({col})' for col in update_columns])

            # 只构建一次 SQL
            placeholders = [f':{col}' for col in insert_columns]
            sql = text(f"""
                INSERT INTO car_parts_library_bmw ({', '.join(insert_columns)})
                VALUES ({', '.join(placeholders)})
                ON DUPLICATE KEY UPDATE {update_clause}
            """)

            # 真正的批量执行 - 一次性提交所有数据
            session.execute(sql, processed_data_list)

            return len(processed_data_list)

        except Exception as e:
            print(f"宝马配件库批量插入或更新失败: {str(e)}")
            raise
