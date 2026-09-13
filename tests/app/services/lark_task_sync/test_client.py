# -*- coding:utf-8 -*-
"""
飞书 API 客户端单元测试

目标：验证 batch_get_lark_user_ids 的分批、重试、结果解析逻辑，不触网。
"""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.services.lark_task_sync import client as lark_client


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

    def json(self):
        return self._data


def _mock_token():
    lark_client.get_tenant_access_token = lambda: 'fake_token'


def _mobile_response(mobiles):
    return FakeResponse({
        'code': 0,
        'data': {
            'user_list': [
                {'mobile': m, 'user_id': f'ou_{m}', 'union_id': f'on_{m}'}
                for m in mobiles
            ]
        }
    })


def test_batch_get_lark_user_ids_success():
    _mock_token()

    with mock.patch.object(lark_client.requests, 'post') as mock_post:
        # 飞书实际返回的是 user_id 字段
        mock_post.return_value = FakeResponse({
            'code': 0,
            'data': {
                'user_list': [
                    {'mobile': '13800138000', 'user_id': 'ou_100', 'union_id': 'on_100'},
                ]
            }
        })

        result = lark_client.batch_get_lark_user_ids(mobiles=['13800138000'])
        assert result['mobiles']['13800138000']['open_id'] == 'ou_100'
        assert result['mobiles']['13800138000']['union_id'] == 'on_100'
        print('PASS: test_batch_get_lark_user_ids_success')


def test_batch_get_lark_user_ids_mobile_and_email():
    _mock_token()

    def fake_post(url, json=None, headers=None, timeout=None):
        if 'mobiles' in json:
            return FakeResponse({
                'code': 0,
                'data': {
                    'user_list': [
                        {'mobile': '13800138000', 'user_id': 'ou_100', 'union_id': 'on_100'},
                    ]
                }
            })
        return FakeResponse({
            'code': 0,
            'data': {
                'user_list': [
                    {'email': 'a@b.com', 'user_id': 'ou_200', 'union_id': 'on_200'},
                ]
            }
        })

    with mock.patch.object(lark_client.requests, 'post', side_effect=fake_post):
        result = lark_client.batch_get_lark_user_ids(
            mobiles=['13800138000'],
            emails=['a@b.com'],
        )
        assert result['mobiles']['13800138000']['open_id'] == 'ou_100'
        assert result['emails']['a@b.com']['open_id'] == 'ou_200'
        print('PASS: test_batch_get_lark_user_ids_mobile_and_email')


def test_batch_get_lark_user_ids_batching():
    _mock_token()

    with mock.patch.object(lark_client.requests, 'post') as mock_post:
        mock_post.side_effect = lambda url, json=None, headers=None, timeout=None: _mobile_response(json['mobiles'])

        mobiles = [f'138000000{i:02d}' for i in range(60)]
        lark_client.batch_get_lark_user_ids(mobiles=mobiles, batch_size=50)

        assert mock_post.call_count == 2
        first_body = mock_post.call_args_list[0][1]['json']
        second_body = mock_post.call_args_list[1][1]['json']
        assert len(first_body['mobiles']) == 50
        assert len(second_body['mobiles']) == 10
        print('PASS: test_batch_get_lark_user_ids_batching')


def test_batch_get_lark_user_ids_retry_then_success():
    _mock_token()

    with mock.patch.object(lark_client.requests, 'post') as mock_post:
        mock_post.side_effect = [
            RuntimeError('network error'),
            RuntimeError('network error'),
            FakeResponse({
                'code': 0,
                'data': {'user_list': [{'mobile': '13800138000', 'user_id': 'ou_100'}]}
            }),
        ]

        result = lark_client.batch_get_lark_user_ids(mobiles=['13800138000'])
        assert result['mobiles']['13800138000']['open_id'] == 'ou_100'
        assert mock_post.call_count == 3
        print('PASS: test_batch_get_lark_user_ids_retry_then_success')


def test_batch_get_lark_user_ids_retry_exhausted():
    _mock_token()

    with mock.patch.object(lark_client.requests, 'post') as mock_post:
        mock_post.side_effect = RuntimeError('network error')

        try:
            lark_client.batch_get_lark_user_ids(mobiles=['13800138000'])
            assert False, '应抛出异常'
        except RuntimeError as e:
            assert 'network error' in str(e)
        assert mock_post.call_count == 3
        print('PASS: test_batch_get_lark_user_ids_retry_exhausted')


if __name__ == '__main__':
    test_batch_get_lark_user_ids_success()
    test_batch_get_lark_user_ids_mobile_and_email()
    test_batch_get_lark_user_ids_batching()
    test_batch_get_lark_user_ids_retry_then_success()
    test_batch_get_lark_user_ids_retry_exhausted()
    print('ALL LARK CLIENT TESTS PASSED')
