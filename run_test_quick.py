# -*- coding:utf-8 -*-
"""
快速测试脚本 - 用于验证新创建的测试文件是否能正确运行

使用方法:
    python run_test_quick.py
"""

import sys
import os
import unittest

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print(f"项目根目录: {PROJECT_ROOT}")
print(f"Python 路径: {sys.path[:3]}...")
print("=" * 70)

# 检查必要模块是否可以导入
try:
    import flask
    print(f"✓ Flask 版本: {flask.__version__}")
except ImportError as e:
    print(f"✗ Flask 未安装: {e}")
    sys.exit(1)

try:
    from app.api.system_management_api.permission_api import permission_bp
    print("✓ permission_api 模块导入成功")
except Exception as e:
    print(f"✗ permission_api 模块导入失败: {e}")

try:
    from app.routes.permission_manager_web import permission_manager_web_bp
    print("✓ permission_manager_web 模块导入成功")
except Exception as e:
    print(f"✗ permission_manager_web 模块导入失败: {e}")

print("=" * 70)
print("\n开始运行测试...\n")

# 运行测试
loader = unittest.TestLoader()
suite = unittest.TestSuite()

try:
    tests1 = loader.loadTestsFromName('tests.permission.test_07_permission_api')
    suite.addTests(tests1)
    print(f"✓ 已加载 test_07_permission_api: {tests1.countTestCases()} 个测试用例")
except Exception as e:
    print(f"✗ test_07_permission_api 加载失败: {e}")

try:
    tests2 = loader.loadTestsFromName('tests.permission.test_08_permission_web')
    suite.addTests(tests2)
    print(f"✓ 已加载 test_08_permission_web: {tests2.countTestCases()} 个测试用例")
except Exception as e:
    print(f"✗ test_08_permission_web 加载失败: {e}")

print("=" * 70)
print(f"总测试用例数: {suite.countTestCases()}")
print("=" * 70)
print()

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

print("\n" + "=" * 70)
if result.wasSuccessful():
    print("✓ 所有测试通过！")
else:
    print("✗ 有测试失败或错误")
    print(f"  失败: {len(result.failures)}, 错误: {len(result.errors)}")
print("=" * 70)
