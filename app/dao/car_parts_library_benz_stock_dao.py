# -*- coding:utf-8 -*-
# @Time    : 2026/06/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_benz_stock_dao.py
# @Software: trae-cn

"""
奔驰库存信息数据访问层
负责处理数据库原生 SQL 操作
"""

from typing import List, Dict
from sqlalchemy import text
from app.utils.orm.session import orm_session


class CarPartsLibraryBenzStockDao:
    """
    奔驰库存信息数据访问类
    """

    @staticmethod
    def batch_upsert(session, data_list: List[Dict]) -> int:
        """
        批量插入或更新数据（以 part_number 和 warehouse 为组合主键）

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
                data_copy = data.copy()
                if 'part_number' in data_copy and data_copy['part_number']:
                    data_copy['part_number'] = data_copy['part_number'].replace(' ', '')
                # 打印调试信息 - 查看 quantity_available 的值
                if len(processed_data_list) < 5:  # 只打印前5条
                    print(f"准备入库数据 - part_number: {data_copy.get('part_number')}, warehouse: {data_copy.get('warehouse')}, quantity_available: {data_copy.get('quantity_available')}, type: {type(data_copy.get('quantity_available'))}")
                processed_data_list.append(data_copy)

            # 定义表字段
            all_columns = [
                'part_number', 'warehouse', 'description',
                'quantity_available', 'unit'
            ]

            # 获取第一条数据的字段作为参考
            first_data = processed_data_list[0]
            insert_columns = []
            for col in all_columns:
                if col in first_data:
                    insert_columns.append(col)

            if not insert_columns:
                return 0

            # 构建更新字段列表（排除主键）
            update_columns = [col for col in insert_columns if col not in ['part_number', 'warehouse']]
            update_clause = ', '.join([f'{col} = VALUES({col})' for col in update_columns])

            # 只构建一次 SQL
            placeholders = [f':{col}' for col in insert_columns]
            sql = text(f"""
                INSERT INTO car_parts_library_benz_stock ({', '.join(insert_columns)})
                VALUES ({', '.join(placeholders)})
                ON DUPLICATE KEY UPDATE {update_clause}
            """)

            # 真正的批量执行 - 一次性提交所有数据
            session.execute(sql, processed_data_list)

            return len(processed_data_list)

        except Exception as e:
            print(f"批量插入或更新库存信息失败: {str(e)}")
            raise

