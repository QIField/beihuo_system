# -*- coding:utf-8 -*-
# @Time    : 2026/6/9
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : crmapp_users.py
# @Software: trae-cn
# @Description: 用户表 ORM 模型

import json
from sqlalchemy import Column, Integer, String, DateTime, SmallInteger, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CrmappUsers(BaseModels):
    """
    用户表模型
    对应数据库表：crmapp_users
    """
    __tablename__ = 'crmapp_users'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 账号基础信息
    username = Column(String(50), nullable=False, comment='用户名')
    password = Column(String(255), nullable=False, comment='密码')

    # 权限与身份标识
    is_admin = Column(SmallInteger, default=0, comment='是否为管理员 0-否 1-是')
    can_delete_cart = Column(SmallInteger, default=0, comment='是否有权限删除购物车 0-否 1-是')
    can_process_orders = Column(SmallInteger, default=0, comment='是否有权限处理单据 0-否 1-是')
    can_inquiry_module = Column(SmallInteger, default=0, comment='是否有权限访问询价模块 0-否 1-是')
    can_compare_module = Column(SmallInteger, default=0, comment='是否有权限访问比价模块 0-否 1-是')
    can_update_crm = Column(SmallInteger, default=0, comment='是否有权限更新CRM产品信息 0-否 1-是')
    can_multi_channel_quote_adjust = Column(SmallInteger, default=0, comment='是否有权限访问多渠道报价调价 0-否 1-是')

    # 组织与人员信息
    store = Column(String(50), default='fsbbr', comment='所属门店代码')
    department = Column(String(20), nullable=True, comment='板块:业务/市场/后勤')
    job_level = Column(String(20), nullable=True, comment='职级:经理/主管/业务员')

    # JSON 字段：登录IP记录（最多保留5个最近的IP地址）
    ip_records = Column(JSON, nullable=True, comment='登录IP记录，最多保留5个最近的IP地址')

    # JSON 字段：允许切换的组织列表，如 ["fsbbr", "zsbbr"]，null表示所有组织都可切换
    allowed_orgs = Column(JSON, nullable=True, comment='允许切换的组织列表，JSON格式，如["fsbbr", "zsbbr"]，null表示所有组织都可切换')

    # 时间字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 定义唯一约束与索引（与数据库保持一致）
    __table_args__ = (
        UniqueConstraint('username', name='username'),
        Index('idx_username', 'username'),
        Index('idx_store', 'store'),
        {
            'comment': '用户表'
        }
    )


    def get_ip_records(self):
        """
        安全解析 ip_records JSON 字段为 Python 列表。

        ip_records 在数据库中可能为：
          - None（未设置过）→ 返回 []
          - list（SQLAlchemy JSON 自动反序列化）→ 直接返回
          - 字符串（某些特殊情况下仍为 JSON 字符串）→ 解析后返回
        """
        value = self.ip_records
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                return []
        # 其他异常类型：保险处理
        return []

    def get_allowed_orgs(self):
        """
        安全解析 allowed_orgs JSON 字段为 Python 列表 / None。

        allowed_orgs 语义：
          - None → 表示允许切换所有组织（不限制）
          - list → 表示只允许切换列表中列出的组织代码
        """
        value = self.allowed_orgs
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
                # 如果是其他类型（如 dict/str），视为配置异常，按"不限制"处理
                return None
            except (ValueError, TypeError):
                return None
        return None

    def to_dict(self, include_sensitive=False):
        """
        将对象转换为字典
        :param include_sensitive: 是否包含敏感字段（如 password），默认不包含
        :return: 字典形式的对象数据
        """
        result = {
            'id': self.id,
            'username': self.username,
            'is_admin': self.is_admin,
            'store': self.store,
            'department': self.department,
            'job_level': self.job_level,
            'can_delete_cart': self.can_delete_cart,
            'can_process_orders': self.can_process_orders,
            'can_inquiry_module': self.can_inquiry_module,
            'can_compare_module': self.can_compare_module,
            'can_update_crm': self.can_update_crm,
            'can_multi_channel_quote_adjust': self.can_multi_channel_quote_adjust,
            'ip_records': self.get_ip_records(),
            'allowed_orgs': self.get_allowed_orgs(),
            'created_time': self.created_time.strftime('%Y-%m-%d %H:%M:%S') if self.created_time else None,  # pyright: ignore[reportGeneralTypeIssues]
            'updated_time': self.updated_time.strftime('%Y-%m-%d %H:%M:%S') if self.updated_time else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
        if include_sensitive:
            result['password'] = self.password
        return result

