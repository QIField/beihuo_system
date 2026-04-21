# -*- coding:utf-8 -*-
# @Time    : 2026/4/17 15:29
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : beihuo_system_config.py
# @Software: PyCharm


from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import insert
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class BeihuoSystemConfig(BaseModels):
    __tablename__ = 'beihuo_system_config'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    config_key = Column(String(100), nullable=False)
    config_value = Column(Text, nullable=True)
    config_type = Column(String(20), nullable=False, default='string')
    config_group = Column(String(50), nullable=False, default='default')
    label = Column(String(100), nullable=False)
    remark = Column(String(255), nullable=True)
    sort = Column(Integer, nullable=False, default=1)
    status = Column(Integer, nullable=False, default=1)
    env = Column(String(20), nullable=False, default='prod')
    created_by = Column(String(50), nullable=True)
    updated_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 联合唯一约束 + 索引（完全对应你数据库的 uk_key_env）
    __table_args__ = (
        UniqueConstraint('config_key', 'env', name='uk_key_env'),
        Index('idx_group', 'config_group'),
        Index('idx_env', 'env'),
    )

    @classmethod
    def get_by_key(cls, session, config_key, env='prod'):
        """简写：只传 key，默认 prod 环境"""
        return session.query(cls).filter(
            cls.config_key == config_key,
            cls.env == env
        ).first()

    @classmethod
    def get_paged_configs(cls, session, page=1, page_size=10):
        """
        分页查询所有配置（带分页）
        :param session: 数据库会话
        :param page: 页码，默认第1页
        :param page_size: 每页条数，默认10条
        :return: (total: 总条数, items: 当前页配置列表)
        """
        query = session.query(cls)

        # 统计总条数
        total = query.count()

        # 分页查询
        items = query.order_by( cls.sort.asc(), cls.id.asc()).limit(page_size).offset((page - 1) * page_size) .all()

        return total, items


    def to_dict(self):
        """
        单个对象转字典
        :return: 字典形式的对象数据
        """
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'config_type': self.config_type,
            'config_group': self.config_group,
            'label': self.label,
            'remark': self.remark,
            'sort': self.sort,
            'status': self.status,
            'env': self.env,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }



    @classmethod
    def list_to_dict_list(cls, items):
        """
        对象列表转字典列表
        :param items: BeihuoSystemConfig 对象列表
        :return: 字典列表
        """
        return [item.to_dict() for item in items]

    @classmethod
    def create(cls, session, data):
        """
        创建新配置
        :param session: 数据库会话
        :param data: 配置数据字典
        :return: 创建的配置对象
        """
        config = cls(**data)
        session.add(config)
        session.flush()
        return config

    @classmethod
    def update(cls, session, config_id, data):
        """
        更新配置
        :param session: 数据库会话
        :param config_id: 配置ID
        :param data: 更新数据字典
        :return: 更新后的配置对象或 None
        """
        config = session.query(cls).filter_by(id=config_id).first()
        if config:
            for key, value in data.items():
                if hasattr(config, key) and key not in ['id', 'created_at','config_key']:
                    setattr(config, key, value)
            session.flush()
        return config



    
    