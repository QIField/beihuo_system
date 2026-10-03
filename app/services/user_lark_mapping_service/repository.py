# -*- coding:utf-8 -*-
"""
用户飞书绑定 - 数据访问层

职责：只负责 user_lark_mapping / crmapp_users 的查询与写入。
"""

from sqlalchemy import func, or_, exists

from sqlalchemy.orm import load_only

from app.models.orm_models import UserLarkMapping
from app.models.orm_models.system_models import CrmappUsers
from app.utils.orm.session import orm_session


class UserLarkMappingRepository:

    @staticmethod
    def create(session, user_id, lark_open_id, lark_union_id):
        mapping = UserLarkMapping(
            user_id=user_id,
            lark_open_id=lark_open_id,
            lark_union_id=lark_union_id,
            status=1,
        )
        session.add(mapping)
        session.flush()
        return mapping

    @staticmethod
    def get_by_id(session, mapping_id):
        return session.query(UserLarkMapping).filter(UserLarkMapping.id == mapping_id).first()

    @staticmethod
    def get_active_by_user_id(session, user_id):
        return session.query(UserLarkMapping).filter(
            UserLarkMapping.user_id == user_id,
            UserLarkMapping.status == 1,
        ).first()

    @staticmethod
    def get_active_by_open_id(session, lark_open_id):
        return session.query(UserLarkMapping).filter(
            UserLarkMapping.lark_open_id == lark_open_id,
            UserLarkMapping.status == 1,
        ).first()

    @staticmethod
    def list_mappings(session, keyword=None, offset=0, limit=10, store=None):
        query = session.query(UserLarkMapping, CrmappUsers).join(
            CrmappUsers, UserLarkMapping.user_id == CrmappUsers.id
        )
        if store:
            query = query.filter(CrmappUsers.store == store)
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(CrmappUsers.username.ilike(like))
        return query.order_by(UserLarkMapping.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def count_mappings(session, keyword=None, store=None):
        query = session.query(func.count(UserLarkMapping.id)).join(
            CrmappUsers, UserLarkMapping.user_id == CrmappUsers.id
        )
        if store:
            query = query.filter(CrmappUsers.store == store)
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(CrmappUsers.username.ilike(like))
        return query.scalar() or 0

    @staticmethod
    def list_candidates(session, keyword=None, limit=50, store=None):
        """查询未绑定飞书的业务用户列表。"""
        active_mapping_exists = exists().where(
            UserLarkMapping.user_id == CrmappUsers.id,
            UserLarkMapping.status == 1,
        )
        query = session.query(CrmappUsers).filter(~active_mapping_exists)
        if store:
            query = query.filter(CrmappUsers.store == store)
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(CrmappUsers.username.ilike(like))
        return query.order_by(CrmappUsers.id.desc()).limit(limit).all()

    @staticmethod
    def list_all_users(session, keyword=None, limit=200, store=None):
        """查询全部业务用户，用于任务分配下拉。"""
        query = session.query(CrmappUsers)
        if store:
            query = query.filter(CrmappUsers.store == store)
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(CrmappUsers.username.ilike(like))
        return query.order_by(CrmappUsers.id.desc()).limit(limit).all()

    @staticmethod
    def get_users_by_ids(session, user_ids):
        """根据 ID 列表查询业务用户，只加载必要字段。"""
        if not user_ids:
            return []
        return session.query(CrmappUsers).options(
            load_only(
                CrmappUsers.id,
                CrmappUsers.username,
                CrmappUsers.mobile,
                CrmappUsers.email,
            )
        ).filter(CrmappUsers.id.in_(user_ids)).all()

    @staticmethod
    def get_user_by_mobile_or_email(session, exclude_user_id, mobile, email):
        """查询 mobile 或 email 是否已被其他用户使用。"""
        if not mobile and not email:
            return None
        filters = [CrmappUsers.id != exclude_user_id]
        conditions = []
        if mobile:
            conditions.append(CrmappUsers.mobile == mobile)
        if email:
            conditions.append(CrmappUsers.email == email)
        filters.append(or_(*conditions))
        return session.query(CrmappUsers).filter(*filters).first()

    @staticmethod
    def update_user_contact(session, user_id, mobile, email):
        """更新业务用户手机号/邮箱。"""
        user = session.query(CrmappUsers).filter(CrmappUsers.id == user_id).first()
        if not user:
            return None
        user.mobile = mobile
        user.email = email
        session.flush()
        return user

    @staticmethod
    def get_active_mapping_by_user_ids(session, user_ids):
        """查询指定用户ID列表中已有有效绑定的 user_id 集合。"""
        if not user_ids:
            return set()
        rows = session.query(UserLarkMapping.user_id).filter(
            UserLarkMapping.user_id.in_(user_ids),
            UserLarkMapping.status == 1,
        ).all()
        return {row[0] for row in rows}

    @staticmethod
    def get_active_mapping_by_open_ids(session, open_ids):
        """查询指定 open_id 列表中已有有效绑定的 open_id 集合。"""
        if not open_ids:
            return set()
        rows = session.query(UserLarkMapping.lark_open_id).filter(
            UserLarkMapping.lark_open_id.in_(open_ids),
            UserLarkMapping.status == 1,
        ).all()
        return {row[0] for row in rows}

    @staticmethod
    def get_mappings_by_ids(session, mapping_ids):
        """根据绑定 ID 列表查询绑定记录。"""
        if not mapping_ids:
            return []
        return session.query(UserLarkMapping).filter(
            UserLarkMapping.id.in_(mapping_ids),
        ).all()

    @staticmethod
    def update_mapping(session, mapping_id, lark_open_id, lark_union_id=None):
        """更新指定绑定记录的飞书 open_id 与 union_id。"""
        mapping = session.query(UserLarkMapping).filter(
            UserLarkMapping.id == mapping_id,
        ).first()
        if not mapping:
            return None
        mapping.lark_open_id = lark_open_id
        if lark_union_id is not None:
            mapping.lark_union_id = lark_union_id
        session.flush()
        return mapping

    @staticmethod
    def get_active_mapping_by_open_ids_except_user_ids(session, open_ids, user_ids):
        """查询指定 open_id 列表中，已被非指定 user_id 绑定的 open_id 集合。"""
        if not open_ids:
            return set()
        rows = session.query(UserLarkMapping.lark_open_id).filter(
            UserLarkMapping.lark_open_id.in_(open_ids),
            UserLarkMapping.status == 1,
            UserLarkMapping.user_id.notin_(user_ids),
        ).all()
        return {row[0] for row in rows}


def mapping_session():
    return orm_session()
