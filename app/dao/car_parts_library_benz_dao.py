# -*- coding:utf-8 -*-
# @Time    : 2026/05/22 18:32
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_benz_dao.py
# @Software: trae-cn

"""
奔驰配件库数据访问层
负责处理数据库原生 SQL 操作
"""

from typing import List, Dict, Tuple, Optional
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.mysql import insert
from app.utils.orm.session import orm_session
from app.models.orm_models.car_parts_library_benz import CarPartsLibraryBenz


class CarPartsLibraryBenzDao:
    """
    奔驰配件库数据访问类
    """

    @staticmethod
    def get_mapping_data(page: int = 1, page_size: int = 1000, vehicle_brand: str = None, company: str = None) -> List[Dict]:  # pyright: ignore[reportArgumentType]
        """
        使用原生 SQL 查询获取映射数据
        从 crmapp_compare_summary 表关联查询 product_name 和 l_model_zh

        :param page: 页码，从1开始
        :param page_size: 每页记录数
        :param vehicle_brand: 车辆品牌筛选条件，可选
        :param company: 公司/门店代码筛选条件，可选
        :return: 查询结果列表，每个元素是 {'part_number': xxx, 'description_cn': xxx, 'l_model_zh': xxx}
        """
        try:
            with orm_session() as session:
                # 计算 offset
                offset = (page - 1) * page_size

                # 原生 SQL 查询，两个表都先做子查询过滤再连接
                sql = text("""
                SELECT
                    benz_sub.part_number AS part_number,
                    MAX(compare_sub.product_name) AS description_cn,
                    MAX(compare_sub.l_model_zh) AS l_model_zh
                FROM (
                    SELECT part_number
                    FROM car_parts_library_benz
                    LIMIT :page_size
                    OFFSET :offset
                ) AS benz_sub
                INNER JOIN (
                    SELECT oe, product_name, l_model_zh
                    FROM crmapp_compare_summary
                    WHERE
                        oe IS NOT NULL
                        AND oe COLLATE utf8mb4_unicode_ci != ''
                        AND (:vehicle_brand IS NULL OR vehicle_brand = :vehicle_brand)
                        AND (:company IS NULL OR company = :company)
                ) AS compare_sub
                ON
                    benz_sub.part_number COLLATE utf8mb4_unicode_ci = compare_sub.oe COLLATE utf8mb4_unicode_ci
                GROUP BY
                    benz_sub.part_number
                """)

                # 执行查询并转换为字典列表
                result = session.execute(
                    sql,
                    {
                        'page_size': page_size,
                        'offset': offset,
                        'vehicle_brand': vehicle_brand,
                        'company': company
                    }
                ).mappings().all()

                # 将 RowMapping 转换为普通字典
                return [dict(row) for row in result]

        except Exception as e:
            print(f"查询映射数据失败: {str(e)}")
            raise

    @staticmethod
    def batch_update(update_data: List[Dict]) -> int:
        """
        使用原生 SQL 批量更新 car_parts_library_benz 表

        :param update_data: 更新数据列表，每个元素是 {'part_number': xxx, 'description_cn': xxx, 'l_model_zh': xxx}
        :return: 更新的记录数
        """
        if not update_data:
            return 0

        try:
            with orm_session() as session:  # pyright: ignore[reportGeneralTypeIssues]
                # 原生 SQL 批量更新语句
                sql = text("""
                UPDATE car_parts_library_benz
                SET
                    description_cn = :description_cn,
                    l_model_zh = :l_model_zh
                WHERE
                    part_number COLLATE utf8mb4_unicode_ci = :part_number
                """)

                # 批量执行更新
                result = session.execute(sql, update_data)
                session.commit()

                return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]

        except Exception as e:
            print(f"批量更新失败: {str(e)}")
            raise

    @staticmethod
    def upsert(session, data: Dict) -> int:
        """
        单条插入或更新数据（以 part_number 为唯一索引）
        
        使用原生 SQL 的 INSERT ... ON DUPLICATE KEY UPDATE

        :param session: 数据库会话
        :param data: 数据字典
        :return: 处理的记录数（1 表示成功）
        """
        if not data:
            return 0

        try:
            # 确保 part_number 去除所有空格（安全措施）
            if 'part_number' in data and data['part_number']:
                data = data.copy()  # 复制一份，避免修改原始数据
                data['part_number'] = data['part_number'].replace(' ', '')

            # 获取所有字段名（除了 created_at 和 updated_at，因为它们会自动处理）
            all_columns = [
                'part_number', 'descriptions', 'description_cn', 'marketing_code',
                'dealer_discount_group', 'msrp', 'dealer_fixed_nominal_margin',
                'wholesale_price', 'marketing_code_description', 'quantity_unit',
                'sales_pack_size', 'weight', 'length', 'width', 'height',
                'effective_date', 'data_source', 'l_model_zh', 'brand', 'category',
                'ccc_mark', 'volume', 'hazmat_code', 'origin_country', 'shelf_life',
                'is_hazmat', 'purchase_price', 'part_nr_info_super_session'
            ]

            # 构建插入字段列表和占位符
            insert_columns = []
            insert_placeholders = []
            for col in all_columns:
                # 检查数据中是否包含该字段，只有包含的字段才参与插入
                if col in data:
                    insert_columns.append(col)
                    insert_placeholders.append(f':{col}')

            if not insert_columns:
                return 0

            # 构建更新字段列表（排除 part_number 和 created_at）
            update_columns = [col for col in insert_columns if col not in ['part_number', 'created_at']]
            update_clause = ', '.join([f'{col} = VALUES({col})' for col in update_columns])

            # 构建原生 SQL
            sql = text(f"""
                INSERT INTO car_parts_library_benz ({', '.join(insert_columns)})
                VALUES ({', '.join(insert_placeholders)})
                ON DUPLICATE KEY UPDATE {update_clause}
            """)

            # 执行单条插入
            session.execute(sql, data)
            session.commit()

            return 1

        except Exception as e:
            print(f"单条插入或更新失败: {str(e)}")
            raise

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
                    data = data.copy()  # 复制一份，避免修改原始数据
                    data['part_number'] = data['part_number'].replace(' ', '')
                processed_data_list.append(data)

            # 获取所有字段名（除了 created_at 和 updated_at，因为它们会自动处理）
            all_columns = [
                'part_number', 'descriptions', 'description_cn', 'marketing_code',
                'dealer_discount_group', 'msrp', 'dealer_fixed_nominal_margin',
                'wholesale_price', 'marketing_code_description', 'quantity_unit',
                'sales_pack_size', 'weight', 'length', 'width', 'height',
                'effective_date', 'data_source', 'l_model_zh', 'brand', 'category',
                'ccc_mark', 'volume', 'hazmat_code', 'origin_country', 'shelf_life',
                'is_hazmat', 'purchase_price', 'part_nr_info_super_session'
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
                INSERT INTO car_parts_library_benz ({', '.join(insert_columns)})
                VALUES ({', '.join(placeholders)})
                ON DUPLICATE KEY UPDATE {update_clause}
            """)

            # 真正的批量执行 - 一次性提交所有数据
            session.execute(sql, processed_data_list)

            return len(processed_data_list)

        except Exception as e:
            print(f"批量插入或更新失败: {str(e)}")
            raise



