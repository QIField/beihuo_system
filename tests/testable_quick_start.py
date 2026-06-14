# -*- coding: utf-8 -*-
# """
# =============================================================================
# Testable Framework - 快速上手
# =============================================================================

# 最简单的测试服务启动示例

# 运行方式：
#     python -m tests.testable_quick_start
# """

import sys
import os


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# 1. 从简化版框架导入核心函数
from tests.testable_framework import register, start, reset, list_registered


def demo():
    """演示：注册权限模块的蓝图并启动服务"""

    print('\n' + '═' * 60)
    print('Testable Framework - 快速演示')
    print('═' * 60)

    # 2. 导入你项目中的蓝图
    print('\n� 正在导入项目蓝图...')

   
    # from app.api.system_management_api.permission_api import permission_bp
    # register(permission_bp)
    from app.api.system_management_api import system_management_bp
    register(system_management_bp, url_prefix='/new/api/system_management')

   
    from app.routes.permission_manager_web import permission_manager_web_bp
    register(permission_manager_web_bp, url_prefix='/web/permission_manager')

    # 4. 可选：注册一个自定义测试路由（用于快速验证服务是否正常）
    from flask import jsonify

    def hello():
        return jsonify({
            'message': 'Hello! Testable Framework 运行正常 👋',
            'timestamp': '你看到这个说明服务启动成功了！',
        })

    register(hello, route_path='/api/test-hello', methods=['GET'])

    # 5. 启动服务（start() 会自动打印路由详情）
    print('\n🚀 正在启动服务...')
    print('''
  服务启动后，你可以：

  🌐 浏览器访问:
     http://127.0.0.1:5001/testable/          ← 控制台首页
     http://127.0.0.1:5001/testable/endpoints ← 所有端点列表
     http://127.0.0.1:5001/api/test-hello     ← 测试路由（验证用）
     http://127.0.0.1:5001/api/permissions    ← 你的权限 API（如果注册了）

  📮 Postman 或 curl 测试:
     GET http://127.0.0.1:5001/api/permissions

  ⏹️  按 Ctrl+C 停止服务
''')

    start(port=5001)


if __name__ == '__main__':
    try:
        demo()
    except KeyboardInterrupt:
        print('\n\n👋 再见！')
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        import traceback
        traceback.print_exc()
