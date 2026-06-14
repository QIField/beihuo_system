# -*- coding:utf-8 -*-
"""
权限模块的示例/测试代码目录

本目录包含以下示例文件，按推荐顺序阅读：

    test_01_registry_basic.py
        └─ PermissionCheckerRegistry 的最基础用法
           注册函数 → 调用函数 → 看结果

    test_02_decorator_with_registry.py
        └─ 装饰器（@require_permission 等）是如何通过 Registry 工作的
           完整的 Flask 应用演示流程

    test_03_testing_with_mock.py
        └─ Registry 在测试中的真正价值：随时替换检查逻辑
           不需要数据库，用 lambda 就能模拟任意权限场景

运行方式（在项目根目录执行）：
    python -m tests.permission.test_01_registry_basic
    python -m tests.permission.test_02_decorator_with_registry
    python -m tests.permission.test_03_testing_with_mock
"""
