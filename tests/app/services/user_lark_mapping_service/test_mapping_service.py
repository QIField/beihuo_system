# -*- coding:utf-8 -*-
"""
UserLarkMappingService 单元测试

目标：验证绑定唯一性、更新、启用/禁用、批量通过联系方式绑定等核心逻辑，不依赖数据库。
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.services.user_lark_mapping_service import mapping_service


class FakeSession:
    def flush(self):
        pass


class FakeOrmSession:
    def __enter__(self):
        return FakeSession()

    def __exit__(self, *args):
        return False


class FakeUser:
    def __init__(self, username='', department='', store='', mobile='', email=''):
        self.username = username
        self.department = department
        self.store = store
        self.mobile = mobile
        self.email = email


class FakeCrmappUsers:
    def __init__(self, user_id, username, mobile=None, email=None):
        self.id = user_id
        self.username = username
        self.mobile = mobile
        self.email = email

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'mobile': self.mobile,
            'email': self.email,
        }


class FakeMapping:
    def __init__(self, mapping_id, user_id, lark_open_id, status=1):
        self.id = mapping_id
        self.user_id = user_id
        self.lark_open_id = lark_open_id
        self.lark_union_id = None
        self.status = status

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'lark_open_id': self.lark_open_id,
            'lark_union_id': self.lark_union_id,
            'status': self.status,
        }


class FakeRepository:
    mappings = {}
    users = {}

    @classmethod
    def reset(cls):
        cls.mappings = {
            1: FakeMapping(1, 100, 'open_100'),
        }
        cls.users = {
            100: FakeCrmappUsers(100, 'user_100'),
            200: FakeCrmappUsers(200, 'user_200', mobile='13800138000'),
            300: FakeCrmappUsers(300, 'user_300', email='a@b.com'),
            400: FakeCrmappUsers(400, 'user_400', mobile='13800138001', email='b@b.com'),
        }

    @classmethod
    def create(cls, session, user_id, lark_open_id, lark_union_id):
        mapping_id = max(cls.mappings.keys(), default=0) + 1
        mapping = FakeMapping(mapping_id, user_id, lark_open_id)
        cls.mappings[mapping_id] = mapping
        return mapping

    @classmethod
    def get_by_id(cls, session, mapping_id):
        return cls.mappings.get(mapping_id)

    @classmethod
    def get_active_by_user_id(cls, session, user_id):
        for m in cls.mappings.values():
            if m.user_id == user_id and m.status == 1:
                return m
        return None

    @classmethod
    def get_active_by_open_id(cls, session, lark_open_id):
        for m in cls.mappings.values():
            if m.lark_open_id == lark_open_id and m.status == 1:
                return m
        return None

    @classmethod
    def list_mappings(cls, session, keyword, offset, limit):
        user = FakeUser(username='测试用户', department='测试部', store='测试店')
        return [(m, user) for m in cls.mappings.values()]

    @classmethod
    def count_mappings(cls, session, keyword):
        return len(cls.mappings)

    @classmethod
    def list_candidates(cls, session, keyword, limit):
        return []

    @classmethod
    def list_all_users(cls, session, keyword, limit):
        return list(cls.users.values())

    @classmethod
    def get_users_by_ids(cls, session, user_ids):
        return [cls.users.get(uid) for uid in user_ids if uid in cls.users]

    @classmethod
    def update_user_contact(cls, session, user_id, mobile, email):
        user = cls.users.get(user_id)
        if not user:
            return None
        user.mobile = mobile
        user.email = email
        return user

    @classmethod
    def get_user_by_mobile_or_email(cls, session, exclude_user_id, mobile, email):
        for user in cls.users.values():
            if user.id == exclude_user_id:
                continue
            if mobile and user.mobile == mobile:
                return user
            if email and user.email == email:
                return user
        return None

    @classmethod
    def get_active_mapping_by_user_ids(cls, session, user_ids):
        result = set()
        for m in cls.mappings.values():
            if m.user_id in user_ids and m.status == 1:
                result.add(m.user_id)
        return result

    @classmethod
    def get_active_mapping_by_open_ids(cls, session, open_ids):
        result = set()
        for m in cls.mappings.values():
            if m.lark_open_id in open_ids and m.status == 1:
                result.add(m.lark_open_id)
        return result

    @classmethod
    def get_mappings_by_ids(cls, session, mapping_ids):
        return [m for m in cls.mappings.values() if m.id in mapping_ids]

    @classmethod
    def update_mapping(cls, session, mapping_id, lark_open_id, lark_union_id=None):
        mapping = cls.mappings.get(mapping_id)
        if not mapping:
            return None
        mapping.lark_open_id = lark_open_id
        if lark_union_id is not None:
            mapping.lark_union_id = lark_union_id
        return mapping

    @classmethod
    def get_active_mapping_by_open_ids_except_user_ids(cls, session, open_ids, user_ids):
        result = set()
        for m in cls.mappings.values():
            if m.lark_open_id in open_ids and m.status == 1 and m.user_id not in user_ids:
                result.add(m.lark_open_id)
        return result


def _mock_session():
    mapping_service.orm_session = FakeOrmSession


def _mock_repository():
    FakeRepository.reset()
    mapping_service.UserLarkMappingRepository = FakeRepository()


def _mock_batch_get(result):
    mapping_service.batch_get_lark_user_ids = lambda mobiles=None, emails=None, batch_size=50: result


def test_update_mapping_success():
    _mock_session()
    _mock_repository()

    result = mapping_service.UserLarkMappingService.update_mapping(1, 'open_updated')
    assert result['lark_open_id'] == 'open_updated'
    print('PASS: test_update_mapping_success')


def test_toggle_status_success():
    _mock_session()
    _mock_repository()

    result = mapping_service.UserLarkMappingService.toggle_status(1, 0)
    assert result['status'] == 0
    print('PASS: test_toggle_status_success')


def test_toggle_status_invalid():
    _mock_session()
    _mock_repository()

    try:
        mapping_service.UserLarkMappingService.toggle_status(1, 2)
        assert False, '应抛出异常'
    except mapping_service.UserLarkMappingServiceError as e:
        assert '状态' in str(e)
    print('PASS: test_toggle_status_invalid')


def test_list_mappings():
    _mock_session()
    _mock_repository()

    result = mapping_service.UserLarkMappingService.list_mappings(page=1, page_size=10)
    assert result['total'] == 1
    assert len(result['list']) == 1
    print('PASS: test_list_mappings')


def test_update_user_contact_success():
    _mock_session()
    _mock_repository()

    result = mapping_service.UserLarkMappingService.update_user_contact(
        200, mobile='13900139000', email='new@b.com'
    )
    assert result['mobile'] == '13900139000'
    assert result['email'] == 'new@b.com'
    print('PASS: test_update_user_contact_success')


def test_update_user_contact_duplicate_mobile():
    _mock_session()
    _mock_repository()

    try:
        mapping_service.UserLarkMappingService.update_user_contact(
            200, mobile='13800138001'
        )
        assert False, '应抛出异常'
    except mapping_service.UserLarkMappingServiceError as e:
        assert '已被其他用户使用' in str(e)
    print('PASS: test_update_user_contact_duplicate_mobile')


def test_batch_bind_by_contact_success():
    _mock_session()
    _mock_repository()
    _mock_batch_get({
        'mobiles': {'13800138000': {'open_id': 'open_200', 'union_id': 'union_200'}},
        'emails': {},
    })

    result = mapping_service.UserLarkMappingService.batch_bind_by_contact([200])
    assert result['success'] == 1
    assert len(result['failed']) == 0
    print('PASS: test_batch_bind_by_contact_success')


def test_batch_bind_by_contact_not_found():
    _mock_session()
    _mock_repository()
    _mock_batch_get({'mobiles': {}, 'emails': {}})

    result = mapping_service.UserLarkMappingService.batch_bind_by_contact([200])
    assert result['success'] == 0
    assert result['failed'][0]['reason'] == '未找到飞书用户'
    print('PASS: test_batch_bind_by_contact_not_found')


def test_batch_bind_by_contact_already_bound():
    _mock_session()
    _mock_repository()
    _mock_batch_get({
        'mobiles': {'13800138000': {'open_id': 'open_200', 'union_id': 'union_200'}},
        'emails': {},
    })

    result = mapping_service.UserLarkMappingService.batch_bind_by_contact([100])
    assert result['success'] == 0
    assert result['failed'][0]['reason'] == '已绑定飞书'
    print('PASS: test_batch_bind_by_contact_already_bound')


def test_batch_bind_by_contact_open_id_used():
    _mock_session()
    _mock_repository()
    _mock_batch_get({
        'mobiles': {'13800138000': {'open_id': 'open_100', 'union_id': 'union_100'}},
        'emails': {},
    })

    result = mapping_service.UserLarkMappingService.batch_bind_by_contact([200])
    assert result['success'] == 0
    assert result['failed'][0]['reason'] == '该飞书账号已被绑定'
    print('PASS: test_batch_bind_by_contact_open_id_used')


def test_batch_bind_by_contact_string_user_id():
    """前端 checkbox x-model 会把 ID 收集为字符串，需兼容。"""
    _mock_session()
    _mock_repository()
    _mock_batch_get({
        'mobiles': {'13800138000': {'open_id': 'open_200', 'union_id': 'union_200'}},
        'emails': {},
    })

    result = mapping_service.UserLarkMappingService.batch_bind_by_contact(['200'])
    assert result['success'] == 1
    assert len(result['failed']) == 0
    print('PASS: test_batch_bind_by_contact_string_user_id')


def test_batch_refresh_by_contact_success():
    """已绑定用户刷新为新的 open_id。"""
    _mock_session()
    _mock_repository()
    FakeRepository.users[100].mobile = '13800138000'
    _mock_batch_get({
        'mobiles': {'13800138000': {'open_id': 'open_200_new', 'union_id': 'union_200_new'}},
        'emails': {},
    })

    result = mapping_service.UserLarkMappingService.batch_refresh_by_contact([1])
    assert result['success'] == 1
    assert len(result['failed']) == 0
    assert FakeRepository.mappings[1].lark_open_id == 'open_200_new'
    print('PASS: test_batch_refresh_by_contact_success')


def test_batch_refresh_by_contact_open_id_used_by_other():
    """新的 open_id 已被其他用户绑定，应刷新失败。"""
    _mock_session()
    _mock_repository()
    FakeRepository.users[100].mobile = '13800138000'
    # 另一个用户已占用 open_300
    FakeRepository.mappings[2] = FakeMapping(2, 300, 'open_300')
    _mock_batch_get({
        'mobiles': {'13800138000': {'open_id': 'open_300', 'union_id': 'union_300'}},
        'emails': {},
    })

    result = mapping_service.UserLarkMappingService.batch_refresh_by_contact([1])
    assert result['success'] == 0
    assert result['failed'][0]['reason'] == '该飞书账号已被其他用户绑定'
    print('PASS: test_batch_refresh_by_contact_open_id_used_by_other')


def test_batch_refresh_by_contact_string_mapping_id():
    """前端 checkbox x-model 会把绑定 ID 收集为字符串，需兼容。"""
    _mock_session()
    _mock_repository()
    FakeRepository.users[100].mobile = '13800138000'
    _mock_batch_get({
        'mobiles': {'13800138000': {'open_id': 'open_200_new', 'union_id': 'union_200_new'}},
        'emails': {},
    })

    result = mapping_service.UserLarkMappingService.batch_refresh_by_contact(['1'])
    assert result['success'] == 1
    assert len(result['failed']) == 0
    assert FakeRepository.mappings[1].lark_open_id == 'open_200_new'
    print('PASS: test_batch_refresh_by_contact_string_mapping_id')


if __name__ == '__main__':
    test_update_mapping_success()
    test_toggle_status_success()
    test_toggle_status_invalid()
    test_list_mappings()
    test_update_user_contact_success()
    test_update_user_contact_duplicate_mobile()
    test_batch_bind_by_contact_success()
    test_batch_bind_by_contact_not_found()
    test_batch_bind_by_contact_already_bound()
    test_batch_bind_by_contact_open_id_used()
    test_batch_bind_by_contact_string_user_id()
    test_batch_refresh_by_contact_success()
    test_batch_refresh_by_contact_open_id_used_by_other()
    test_batch_refresh_by_contact_string_mapping_id()
    print('ALL MAPPING SERVICE TESTS PASSED')
