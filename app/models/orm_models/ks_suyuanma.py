# -*- coding:utf-8 -*-
# @Time    : 2026/5/9
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : ks_suyuanma.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, String, DateTime, text, Integer

from .base_models import BaseModels


class KsSuyuanma(BaseModels):
    """
    开思溯源码表 ORM 模型
    
    对应数据库表：ks_suyuanma
    """
    
    __tablename__ = "ks_suyuanma"

    # 专门解决【无主键、无唯一字段】的官方方案
    # 正确、安全、稳定的【伪主键】写法（不会影响数据库）
    id_num = Column(Integer, primary_key=True)
    
    md = Column(String(255), nullable=True, comment="组织")
    suyuanma = Column(String(255), nullable=True, comment="溯源码")
    start_m = Column(String(255), nullable=True, comment="开始")
    end_m = Column(String(255), nullable=False, comment="结束")

    @classmethod
    def get_suyuan_statistics(cls, session, md=None):
        """
        根据组织统计溯源码数量
        
        按 start_m 和 end_m 分组，统计每个分组下的不同溯源码数量
        
        :param session: SQLAlchemy Session 对象
        :param md: 组织参数，如果不传则查询所有组织
        :return: 查询结果列表，每个元素包含 start_m, end_m, count
        """
        # 构建 SQL 查询语句
        sql = text("""
                   SELECT start_m, end_m, COUNT(DISTINCT suyuanma) as count
                   FROM ks_suyuanma
                   WHERE (:md IS NULL OR md = :md)
                   GROUP BY start_m, end_m
                   """)
        
        # 绑定参数
        params = {
            "md": md
        }
        
        # 执行查询
        results = session.execute(sql, params).all()
        
        return results
    
    @classmethod
    def list_to_dict_list(cls, obj_list):
        """
        将对象列表转换为字典列表
        
        支持两种输入类型：
        1. KsSuyuanma 模型对象列表
        2. SQLAlchemy Row 对象列表（原生SQL查询结果）
        
        :param obj_list: KsSuyuanma 对象列表 或 Row 对象列表
        :return: 字典列表
        """
        if not obj_list:
            return []
        
        result = []
        for obj in obj_list:
            if hasattr(obj, 'to_dict'):
                # 是模型对象，调用 to_dict 方法
                result.append(obj.to_dict())
            else:
                # 是 Row 对象，转换为字典并处理特殊类型
                try:
                    # 尝试使用 _asdict() 方法（适用于 SQLAlchemy 1.4+）
                    row_dict = obj._asdict()
                except AttributeError:
                    # 备用方法：手动构建字典
                    row_dict = {}
                    for key in obj.keys():
                        row_dict[key] = obj[key]
                result.append(row_dict)
        return result
    
    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<KsSuyuanma md={self.md} suyuanma={self.suyuanma}>"
    
    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "md": self.md,
            "suyuanma": self.suyuanma,
            "start_m": self.start_m,
            "end_m": self.end_m,
        }
