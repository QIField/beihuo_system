# -*- coding: utf-8 -*-
"""
权限模块 - Testable Framework 使用示例

运行：python -m tests.permission.testable_demo
"""

import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 从简化版框架导入
from tests.testable_framework import register, start, reset, list_registered, create_app
import json


def main():
    print('\n' + '═' * 60)
    print('权限模块测试服务')
    print('═' * 60)

    # 1. 导入项目蓝图
    print('\n[导入] 导入蓝图...')
    try:
        from app.api.system_management_api.permission_api import permission_bp
        print('  [成功] permission_api.permission_bp')
    except Exception as e:
        print(f'  [失败] permission_api: {e}')
        permission_bp = None

    try:
        from app.routes.permission_manager_web import permission_manager_web_bp
        print('  [成功] permission_manager_web.permission_manager_web_bp')
    except Exception as e:
        print(f'  [失败] permission_manager_web: {e}')
        permission_manager_web_bp = None

    # 2. 显式注册
    print('\n[工具] 注册到测试服务...')
    if permission_bp:
        register(permission_bp, url_prefix='/api')
    if permission_manager_web_bp:
        register(permission_manager_web_bp)

    # 3. 启动服务（start() 会自动打印路由详情）
    print('\n[开始] 启动服务...')
    start(port=5001)


def unit_test_demo():
    """单元测试模式演示：不启动服务，直接用 test_client"""
    print('\n' + '═' * 60)
    print('单元测试模式演示（不启动真实服务）')
    print('═' * 60)

    reset()

    try:
        from app.api.system_management_api.permission_api import permission_bp
        register(permission_bp, url_prefix='/api')
    except Exception as e:
        print(f'  [失败] 导入失败: {e}')
        return

    # 创建测试客户端（内存中执行，不需要网络）
    client = create_app().test_client()

    print('\n[编辑] 发送测试请求...')

    # 测试框架内置端点
    resp = client.get('/testable/health')
    print(f'  GET /testable/health → {resp.status_code}')

    # 测试权限 API
    print('\n  测试权限 API 端点:')
    test_paths = [
        '/api/permissions',
        '/api/permissions?page=1&page_size=5',
        '/api/permissions/all',
    ]

    for path in test_paths:
        try:
            resp = client.get(path)
            data = resp.get_json() if resp.is_json else None
            code = data.get('code') if data else 'N/A'
            print(f'  GET {path[:50]:50s} → {resp.status_code} (api_code: {code})')
        except Exception as e:
            print(f'  GET {path[:50]:50s} → 错误: {e}')

    print('\n[灯泡] 提示：这种模式适合写自动化测试，速度快，不需要启动服务')


if __name__ == '__main__':
    # 简单的模式选择
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        unit_test_demo()
    else:
        main()
