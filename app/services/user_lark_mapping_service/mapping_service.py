# -*- coding:utf-8 -*-
"""
用户飞书绑定 - 业务编排层

职责：参数校验、唯一性检查、调用 repository 持久化。
"""

from app.utils.orm.session import orm_session
from app.services.lark_task_sync.client import batch_get_lark_user_ids

from .repository import UserLarkMappingRepository


class UserLarkMappingServiceError(Exception):
    pass


class UserLarkMappingService:

    @staticmethod
    def bind_user(user_id, lark_open_id, lark_union_id=None):
        UserLarkMappingService._validate_bind(user_id, lark_open_id)

        with orm_session() as session:
            existing = UserLarkMappingRepository.get_active_by_user_id(session, user_id)
            if existing:
                raise UserLarkMappingServiceError('该用户已绑定飞书')

            open_id_used = UserLarkMappingRepository.get_active_by_open_id(session, lark_open_id)
            if open_id_used:
                raise UserLarkMappingServiceError('该飞书 open_id 已被绑定')

            mapping = UserLarkMappingRepository.create(
                session=session,
                user_id=user_id,
                lark_open_id=lark_open_id,
                lark_union_id=lark_union_id,
            )
            return mapping.to_dict()

    @staticmethod
    def update_mapping(mapping_id, lark_open_id, lark_union_id=None):
        if not mapping_id:
            raise UserLarkMappingServiceError('绑定ID不能为空')
        if not lark_open_id:
            raise UserLarkMappingServiceError('飞书 open_id 不能为空')

        with orm_session() as session:
            mapping = UserLarkMappingRepository.get_by_id(session, mapping_id)
            if not mapping:
                raise UserLarkMappingServiceError('绑定记录不存在')

            if lark_open_id != mapping.lark_open_id:
                open_id_used = UserLarkMappingRepository.get_active_by_open_id(session, lark_open_id)
                if open_id_used and open_id_used.id != mapping_id:
                    raise UserLarkMappingServiceError('该飞书 open_id 已被绑定')

            mapping.lark_open_id = lark_open_id
            if lark_union_id is not None:
                mapping.lark_union_id = lark_union_id
            session.flush()
            return mapping.to_dict()

    @staticmethod
    def toggle_status(mapping_id, status):
        if status not in {0, 1}:
            raise UserLarkMappingServiceError('状态值不合法')

        with orm_session() as session:
            mapping = UserLarkMappingRepository.get_by_id(session, mapping_id)
            if not mapping:
                raise UserLarkMappingServiceError('绑定记录不存在')
            mapping.status = status
            session.flush()
            return mapping.to_dict()

    @staticmethod
    def list_mappings(keyword=None, page=1, page_size=10):
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        offset = (page - 1) * page_size

        with orm_session() as session:
            rows = UserLarkMappingRepository.list_mappings(session, keyword, offset, page_size)
            total = UserLarkMappingRepository.count_mappings(session, keyword)
            data_list = [UserLarkMappingService._format_mapping(row) for row in rows]

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'list': data_list,
        }

    @staticmethod
    def list_candidates(keyword=None, limit=50):
        with orm_session() as session:
            users = UserLarkMappingRepository.list_candidates(session, keyword, limit)
            return [u.to_dict() for u in users]

    @staticmethod
    def list_all_users(keyword=None, limit=200):
        with orm_session() as session:
            users = UserLarkMappingRepository.list_all_users(session, keyword, limit)
            return [u.to_dict() for u in users]

    @staticmethod
    def update_user_contact(user_id, mobile=None, email=None):
        """
        更新业务用户手机号/邮箱，并校验唯一性。

        :return: 更新后的用户 dict
        """
        if not user_id:
            raise UserLarkMappingServiceError('用户ID不能为空')
        mobile = (mobile or '').strip() or None
        email = (email or '').strip() or None

        with orm_session() as session:
            existing = UserLarkMappingRepository.get_user_by_mobile_or_email(
                session, user_id, mobile, email
            )
            if existing:
                raise UserLarkMappingServiceError('手机号或邮箱已被其他用户使用')

            user = UserLarkMappingRepository.update_user_contact(session, user_id, mobile, email)
            if not user:
                raise UserLarkMappingServiceError('用户不存在')
            return user.to_dict()

    @staticmethod
    def _collect_contact_inputs(users):
        """从用户字典列表中收集手机号/邮箱与 user_id 的映射。"""
        mobiles = []
        emails = []
        user_by_mobile = {}
        user_by_email = {}

        for user in users:
            user_id = user['id']
            mobile = user.get('mobile')
            email = user.get('email')
            if mobile:
                mobiles.append(mobile)
                user_by_mobile[mobile] = user_id
            if email:
                emails.append(email)
                user_by_email[email] = user_id

        return mobiles, emails, user_by_mobile, user_by_email

    @staticmethod
    def _build_lark_id_mapping(lark_result, user_by_mobile, user_by_email):
        """
        根据飞书反查结果，构建 user_id -> lark_info 映射。

        :return: (user_id_to_lark_info, open_ids)
        """
        user_id_to_lark_info = {}
        open_ids = []

        for mobile, lark_info in lark_result.get('mobiles', {}).items():
            user_id = user_by_mobile.get(mobile)
            if user_id and lark_info.get('open_id'):
                open_ids.append(lark_info['open_id'])
                user_id_to_lark_info[user_id] = lark_info

        for email, lark_info in lark_result.get('emails', {}).items():
            user_id = user_by_email.get(email)
            if user_id and lark_info.get('open_id'):
                open_ids.append(lark_info['open_id'])
                # 手机号已命中的优先级更高，不覆盖
                if user_id not in user_id_to_lark_info:
                    user_id_to_lark_info[user_id] = lark_info

        return user_id_to_lark_info, open_ids

    @staticmethod
    def batch_bind_by_contact(user_ids):
        """
        根据用户补充的手机号/邮箱，批量反查飞书用户 ID 并自动绑定。

        :param user_ids: 业务用户 ID 列表
        :return: {'success': int, 'failed': [{'user_id': int, 'reason': str}, ...]}
        """
        if not user_ids:
            raise UserLarkMappingServiceError('用户ID列表不能为空')

        with orm_session() as session:
            users = UserLarkMappingRepository.get_users_by_ids(session, user_ids)
            # 在 session 内把 ORM 对象转成普通 dict，避免 detached instance 问题
            user_dict = {
                u.id: {'id': u.id, 'mobile': u.mobile, 'email': u.email}
                for u in users
            }

        mobiles, emails, user_by_mobile, user_by_email = \
            UserLarkMappingService._collect_contact_inputs(list(user_dict.values()))

        # 飞书接口调用放在 session 外，避免长时间占用数据库连接
        lark_result = batch_get_lark_user_ids(mobiles=mobiles, emails=emails)

        user_id_to_lark_info, open_ids = UserLarkMappingService._build_lark_id_mapping(
            lark_result, user_by_mobile, user_by_email
        )

        success = 0
        failed = []

        with orm_session() as session:
            bound_user_ids = UserLarkMappingRepository.get_active_mapping_by_user_ids(
                session, list(user_dict.keys())
            )
            bound_open_ids = UserLarkMappingRepository.get_active_mapping_by_open_ids(
                session, open_ids
            )

            for user_id in user_ids:
                user = user_dict.get(user_id)
                if not user:
                    failed.append({'user_id': user_id, 'reason': '用户不存在'})
                    continue

                if user_id in bound_user_ids:
                    failed.append({'user_id': user_id, 'reason': '已绑定飞书'})
                    continue

                lark_info = user_id_to_lark_info.get(user_id)
                if not lark_info:
                    failed.append({'user_id': user_id, 'reason': '未找到飞书用户'})
                    continue

                open_id = lark_info['open_id']
                if open_id in bound_open_ids:
                    failed.append({'user_id': user_id, 'reason': '该飞书账号已被绑定'})
                    continue

                UserLarkMappingRepository.create(
                    session,
                    user_id=user_id,
                    lark_open_id=open_id,
                    lark_union_id=lark_info.get('union_id'),
                )
                success += 1

        return {'success': success, 'failed': failed}

    @staticmethod
    def _format_mapping(row):
        mapping, user = row
        data = mapping.to_dict()
        data['username'] = user.username if user else ''
        data['department'] = user.department if user else ''
        data['store'] = user.store if user else ''
        return data

    @staticmethod
    def _validate_bind(user_id, lark_open_id):
        if not user_id:
            raise UserLarkMappingServiceError('用户ID不能为空')
        if not lark_open_id:
            raise UserLarkMappingServiceError('飞书 open_id 不能为空')
