# -*- coding:utf-8 -*-
# @Time    : 2026/4/13 15:27
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : type_decorators.py
# @Software: PyCharm

from sqlalchemy.types import TypeDecorator, INTEGER


class StringToIntType(TypeDecorator):
    """
    自定义类型装饰器：实现字符串和整数之间的自动转换
    
    - 从数据库读取时：int -> str（根据映射关系转换）
    - 写入数据库时：str -> int（根据映射关系转换）
    
    类似 MyBatis 的类型处理器机制
    """
    impl = INTEGER

    def __init__(self, mapping_dict, *args, **kwargs):
        """
        初始化类型装饰器
        
        :param mapping_dict: 映射字典，格式为 {'字符串值': 整数值}
        """
        self.mapping_dict = mapping_dict
        self.reverse_mapping_dict = {v: k for k, v in mapping_dict.items()}
        super(StringToIntType, self).__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        """
        写入数据库前的处理：str -> int
        
        :param value: 输入值（字符串类型或整数类型）
        :param dialect: SQLAlchemy 方言
        :return: 数据库中的值（整数类型）
        """
        if value is None:
            return None
        
        # 如果已经是整数，直接返回
        if isinstance(value, int):
            # 验证整数是否在映射值中
            if value in self.reverse_mapping_dict:
                return value
            # 如果不在映射中，但可能是有效的整数值，也返回
            return value
        
        # 如果是字符串，尝试精确匹配映射
        if isinstance(value, str):
            # 先尝试精确匹配
            if value in self.mapping_dict:
                return self.mapping_dict[value]
            
            # 尝试将字符串转换为整数
            try:
                int_val = int(value)
                if int_val in self.reverse_mapping_dict:
                    return int_val
                return int_val
            except ValueError:
                pass
        
        # 如果没有匹配到，返回 None
        return None

    def process_result_value(self, value, dialect):
        """
        从数据库读取后的处理：int -> str
        
        :param value: 数据库中的值（整数类型）
        :param dialect: SQLAlchemy 方言
        :return: 输出值（字符串类型）
        """
        if value is None:
            return None
        
        return self.reverse_mapping_dict.get(value, str(value))

