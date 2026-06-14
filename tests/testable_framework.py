# -*- coding: utf-8 -*-
# """
# =============================================================================
# Testable Framework - 简化版（显式引用模式）
# =============================================================================

# 🎯 设计理念：显式注册，即导即用，无装饰器

# 使用方式（3 步启动测试服务）：
#     from tests.testable_framework import register, start

#     # 1. 导入你要测试的蓝图
#     from app.api.system_management_api.permission_api import permission_bp
#     from app.routes.permission_manager_web import permission_manager_web_bp

#     # 2. 显式注册（import 了就可以注册）
#     register(permission_bp, url_prefix='/api')
#     register(permission_manager_web_bp)

#     # 3. 启动服务
#     start(port=5001)

#     # 或者用于单元测试（不启动真实服务）
#     from tests.testable_framework import create_app
#     client = create_app().test_client()
#     response = client.get('/api/permissions')
# """

import sys
import os
from datetime import datetime
from typing import Optional, List, Dict, Callable, Union, Tuple

from flask import Flask, Blueprint, jsonify


# ======================================================================
# 路径配置
# ======================================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ======================================================================
# 全局注册表（简化版：用两个列表存储）
# ======================================================================

# 存储已注册的 Blueprint: [(blueprint, url_prefix, name), ...]
_registered_blueprints: List[Tuple[Blueprint, Optional[str], str]] = []

# 存储已注册的独立路由: [(path, methods, func), ...]
_registered_routes: List[Tuple[str, List[str], Callable]] = []


# ======================================================================
# 核心 API：register - 显式注册蓝图或路由
# ======================================================================

def register(item: Union[Blueprint, Callable],
             url_prefix: Optional[str] = None,
             name: Optional[str] = None,
             route_path: Optional[str] = None,
             methods: Optional[List[str]] = None) -> None:
    """
    🔧 显式注册要测试的内容。

    这是最核心的函数，支持两种用法：

    用法 1：注册 Blueprint（最常用）
    ────────────────────────────────────────────────
        from app.api.permission_api import permission_bp
        register(permission_bp, url_prefix='/api')
        # ↑ 这样 permission_bp 下的所有路由都会被包含

    用法 2：注册独立函数为路由（用于快速测试）
    ────────────────────────────────────────────────
        def my_test():
            return jsonify({'status': 'ok'})
        register(my_test, route_path='/api/test', methods=['GET'])

    Args:
        item: Blueprint 实例 或 普通函数
        url_prefix: Blueprint 的 URL 前缀（仅 Blueprint 用）
        name: 显示名称（可选，默认用 blueprint.name）
        route_path: 路由路径（仅普通函数用，如 '/api/test'）
        methods: HTTP 方法列表（仅普通函数用，如 ['GET', 'POST']）

    示例：
        # 注册 API 蓝图
        from app.api.system_management_api.permission_api import permission_bp
        register(permission_bp, url_prefix='/api')

        # 注册页面蓝图
        from app.routes.permission_manager_web import permission_manager_web_bp
        register(permission_manager_web_bp)

        # 注册自定义函数为路由
        def hello():
            return jsonify({'message': 'Hello!'})
        register(hello, route_path='/api/hello', methods=['GET'])
    """
    global _registered_blueprints, _registered_routes

    if isinstance(item, Blueprint):
        # 注册 Blueprint
        bp_name = name or item.name
        _registered_blueprints.append((item, url_prefix, bp_name))
        _print(f'✓ 注册蓝图: {bp_name} → {url_prefix or "/"}')

    elif callable(item) and route_path:
        # 注册独立路由函数
        http_methods = methods or ['GET']
        _registered_routes.append((route_path, http_methods, item))
        _print(f'✓ 注册路由: [{",".join(http_methods)}] {route_path}')

    else:
        _print(f'✗ 跳过: 不支持的类型 {type(item)}，或缺少 route_path')


# ======================================================================
# 辅助：一次注册多个蓝图
# ======================================================================

def register_all(items: List[Union[Blueprint, Dict]]) -> None:
    """
    📦 批量注册多个蓝图/路由。

    用法 1：简单列表（所有蓝图用相同配置）
        register_all([bp1, bp2, bp3])

    用法 2：字典列表（每个蓝图独立配置）
        register_all([
            {'item': permission_bp, 'url_prefix': '/api'},
            {'item': role_bp, 'url_prefix': '/api'},
            {'item': user_bp, 'url_prefix': '/api/v1'},
        ])

    用法 3：混合模式
        register_all([
            permission_bp,                     # Blueprint
            {'item': role_bp, 'url_prefix': '/api'},  # 带配置
            {'item': my_func, 'route_path': '/test'}, # 函数
        ])

    Args:
        items: Blueprint 列表或字典列表
    """
    for item in items:
        if isinstance(item, dict):
            # 字典配置：解包后调用 register
            register(**item)
        else:
            # 直接是 Blueprint：简单注册
            register(item)


# ======================================================================
# 核心 API：create_app - 创建 Flask 应用
# ======================================================================

def create_app(template_folder: Optional[str] = None,
               static_folder: Optional[str] = None,
               config: Optional[Dict] = None) -> Flask:
    """
    🏗️ 创建包含所有已注册内容的 Flask 应用。

    主要用于：
    - 单元测试：client = create_app().test_client()
    - 自定义启动：app = create_app()，然后 app.run()

    Args:
        template_folder: 模板文件夹（默认用项目根目录的 templates）
        static_folder: 静态资源文件夹（默认用项目根目录的 static）
        config: 额外的 Flask 配置

    Returns:
        Flask 应用实例

    用法（单元测试）：
        app = create_app()
        client = app.test_client()
        response = client.get('/api/permissions')
        data = response.get_json()

    用法（自定义启动）：
        app = create_app()
        app.run(port=5001, debug=True)
    """
    # 1. 创建 Flask 应用
    app = Flask(
        __name__,
        template_folder=template_folder or os.path.join(PROJECT_ROOT, 'templates'),
        static_folder=static_folder or os.path.join(PROJECT_ROOT, 'static'),
    )
    app.config['SECRET_KEY'] = 'testable-framework-secret'
    app.config['JSON_AS_ASCII'] = False
    app.config['TESTING'] = True

    if config:
        app.config.update(config)

    # 2. 注册所有 Blueprint
    registered_count = 0
    for bp, prefix, name in _registered_blueprints:
        try:
            if prefix:
                app.register_blueprint(bp, url_prefix=prefix)
            else:
                app.register_blueprint(bp)
            registered_count += 1
        except Exception as e:
            _print(f'✗ 注册蓝图 {name} 失败: {e}')

    # 3. 注册所有独立路由
    for path, methods, func in _registered_routes:
        try:
            app.route(path, methods=methods)(func)
        except Exception as e:
            _print(f'✗ 注册路由 {path} 失败: {e}')

    # 4. 添加内置辅助端点
    _add_builtin_endpoints(app, registered_count)

    return app


# ======================================================================
# 核心 API：start - 启动测试服务
# ======================================================================

def start(port: int = 5001,
          host: str = '127.0.0.1',
          debug: bool = False,
          blocking: bool = True,
          template_folder: Optional[str] = None,
          static_folder: Optional[str] = None) -> Optional[Flask]:
    """
    🚀 启动测试服务。

    这是最常用的函数，启动后可以用浏览器或 Postman 访问。

    Args:
        port: 端口号（默认 5001）
        host: 监听地址（默认 127.0.0.1，如需外部访问用 '0.0.0.0'）
        debug: 是否开启调试模式（自动重载）
        blocking: 是否阻塞运行（True: 一直运行直到 Ctrl+C；False: 后台线程）
        template_folder: 模板文件夹路径
        static_folder: 静态资源文件夹路径

    Returns:
        如果 blocking=False，返回 Flask 应用实例
        如果 blocking=True，不会返回（一直运行）

    用法：
        from tests.testable_framework import register, start

        from app.api.permission_api import permission_bp
        register(permission_bp, url_prefix='/api')

        # 启动服务，按 Ctrl+C 停止
        start(port=5001)

        # 浏览器访问:
        #   http://127.0.0.1:5001/testable/     ← 控制台首页
        #   http://127.0.0.1:5001/testable/endpoints  ← 所有端点列表
        #   http://127.0.0.1:5001/api/permissions  ← 你的 API
    """
    # 创建应用
    app = create_app(template_folder=template_folder, static_folder=static_folder)

    # 打印启动信息
    print('\n' + '═' * 70)
    print('🚀 Testable Framework - 测试服务已启动')
    print('═' * 70)
    print(f'  服务地址: http://{host}:{port}')
    print(f'  控制台首页: http://{host}:{port}/testable/')
    print(f'  端点列表: http://{host}:{port}/testable/endpoints')
    print(f'  健康检查: http://{host}:{port}/testable/health')
    print('─' * 70)
    print('  💡 按 Ctrl+C 停止服务')
    print('═' * 70)

    # 打印详细的路由信息（使用增强版 list_registered）
    list_registered(show_routes=True)

    # 启动服务
    if blocking:
        try:
            app.run(host=host, port=port, debug=debug, threaded=True)
        except KeyboardInterrupt:
            print('\n服务已停止')
    else:
        import threading
        thread = threading.Thread(
            target=app.run,
            kwargs={'host': host, 'port': port, 'debug': debug, 'threaded': True},
            daemon=True
        )
        thread.start()
        return app


# ======================================================================
# 辅助：重置注册表（用于测试之间清理）
# ======================================================================

def reset() -> None:
    """
    🔄 清空所有已注册的蓝图和路由。

    主要用于单元测试中，确保每个测试用例独立运行。

    用法：
        from tests.testable_framework import reset, register, create_app

        def test_1():
            reset()  # 清空前一个测试注册的内容
            register(bp1, url_prefix='/api')
            client = create_app().test_client()
            ...

        def test_2():
            reset()  # 清空前一个测试注册的内容
            register(bp2, url_prefix='/api')
            ...
    """
    global _registered_blueprints, _registered_routes
    _registered_blueprints = []
    _registered_routes = []
    _print('🔄 注册表已清空')


# ======================================================================
# 辅助：显示注册内容
# ======================================================================

def list_registered(show_routes: bool = True) -> None:
    """
    📋 打印当前已注册的所有内容（包含每个蓝图下的路由详情）。

    Args:
        show_routes: 是否打印每个蓝图的路由详情（默认 True）

    用于调试，确认注册是否成功。

    用法：
        register(permission_bp, url_prefix='/api')
        list_registered()           # 打印完整详情
        list_registered(show_routes=False)  # 只打印摘要
    """
    print('\n' + '═' * 70)
    print('📋 已注册内容详情')
    print('═' * 70)

    # ─── 1. Blueprint 详情 ──────────────────────────────────
    if _registered_blueprints:
        print(f'\n  📦 Blueprint ({len(_registered_blueprints)} 个):')
        print('  ' + '─' * 68)

        for bp_idx, (bp, prefix, name) in enumerate(_registered_blueprints, 1):
            url_prefix = prefix or bp.url_prefix or ''

            # 蓝图基本信息
            print(f'\n  [{bp_idx}] {name}')
            print(f'        URL 前缀: {url_prefix or "/"}')
            print(f'        Blueprint 名称: {bp.name}')

            # 打印该蓝图下的所有路由
            if show_routes:
                try:
                    # 创建临时应用，注册蓝图，提取路由信息
                    temp_app = Flask(f'temp_inspect_{bp.name}')
                    if prefix:
                        temp_app.register_blueprint(bp, url_prefix=prefix)
                    else:
                        temp_app.register_blueprint(bp)

                    # 收集该蓝图的所有路由（临时应用中除 static 外的所有路由都属于该蓝图）
                    bp_routes = []
                    for rule in temp_app.url_map.iter_rules():
                        if rule.endpoint == 'static':
                            continue
                        methods = sorted(m for m in rule.methods if m not in ('HEAD', 'OPTIONS'))  # pyright: ignore[reportOptionalIterable]
                        bp_routes.append({
                            'path': rule.rule,
                            'methods': methods,
                            'endpoint': rule.endpoint,
                        })

                    if bp_routes:
                        print(f'        路由数量: {len(bp_routes)}')
                        print(f'        路由列表:')
                        # 按路径排序并打印
                        for route in sorted(bp_routes, key=lambda r: r['path']):
                            method_str = ','.join(route['methods'])
                            print(f'           [{method_str:6s}] {route["path"]}')
                    else:
                        print(f'        路由数量: 0（可能有嵌套子蓝图）')

                except Exception as e:
                    print(f'        ⚠️  路由解析失败: {e}')

    # ─── 2. 独立路由详情 ────────────────────────────────────
    if _registered_routes:
        print(f'\n\n  🚀 独立路由 ({len(_registered_routes)} 个):')
        print('  ' + '─' * 68)

        for idx, (path, methods, func) in enumerate(_registered_routes, 1):
            method_str = ','.join(methods)
            func_name = func.__name__ if hasattr(func, '__name__') else str(func)
            func_module = func.__module__ if hasattr(func, '__module__') else 'unknown'

            print(f'\n  [{idx}] [{method_str:6s}] {path}')
            print(f'        处理函数: {func_module}.{func_name}()')

    # ─── 3. 空状态 ─────────────────────────────────────────
    if not _registered_blueprints and not _registered_routes:
        print('\n    (空 - 尚未注册任何内容)')
        print('\n    💡 使用 register(your_blueprint, url_prefix="/api") 注册蓝图')

    print('\n' + '═' * 70 + '\n')


# ======================================================================
# 内部函数：添加内置辅助端点
# ======================================================================

def _add_builtin_endpoints(app: Flask, blueprint_count: int) -> None:
    """
    添加框架内置的辅助端点，方便调试。

    端点列表：
        GET /testable/              - HTML 控制台首页
        GET /testable/health        - 健康检查（JSON）
        GET /testable/endpoints     - 所有端点列表（JSON）
        GET /testable/registered    - 已注册内容（JSON）
    """

    @app.route('/testable/health')
    def health():
        return jsonify({
            'status': 'ok',
            'service': 'Testable Framework',
            'timestamp': datetime.now().isoformat(),
            'blueprints': blueprint_count,
            'routes': len(_registered_routes),
        })

    @app.route('/testable/endpoints')
    def endpoints():
        endpoint_list = []
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            if rule.endpoint == 'static':
                continue
            methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))  # pyright: ignore[reportOptionalOperand]
            endpoint_list.append({
                'path': rule.rule,
                'methods': methods,
                'endpoint': rule.endpoint,
            })
        return jsonify({
            'count': len(endpoint_list),
            'endpoints': endpoint_list,
        })

    @app.route('/testable/registered')
    def registered_info():
        return jsonify({
            'blueprints': [
                {'name': name, 'url_prefix': prefix}
                for _, prefix, name in _registered_blueprints
            ],
            'routes': [
                {'path': path, 'methods': methods}
                for path, methods, _ in _registered_routes
            ],
        })

    @app.route('/testable/')
    def home():
        # 生成端点列表 HTML
        rows = []
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            if rule.endpoint == 'static':
                continue
            methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))  # pyright: ignore[reportOptionalOperand]
            rows.append(
                f'<tr>'
                f'<td><code>{rule.rule}</code></td>'
                f'<td><span class="method">{methods}</span></td>'
                f'<td><a href="{rule.rule}" target="_blank">打开</a></td>'
                f'</tr>'
            )

        return f'''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Testable Framework - 测试控制台</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                       margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1000px; margin: 0 auto; }}
                h1 {{ color: #333; }}
                .info {{ background: #fff; padding: 15px 20px; border-radius: 8px;
                         margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; background: #fff;
                         box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-radius: 8px;
                         overflow: hidden; }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }}
                th {{ background: #4CAF50; color: white; }}
                tr:hover {{ background: #f9f9f9; }}
                .method {{ display: inline-block; padding: 3px 8px; background: #e3f2fd;
                           color: #1976d2; border-radius: 4px; font-family: monospace;
                           font-size: 12px; }}
                code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px;
                        font-size: 13px; }}
                a {{ color: #4CAF50; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Testable Framework - 测试控制台</h1>

                <div class="info">
                    <strong>快捷入口：</strong>
                    <ul>
                        <li><a href="/testable/health">/testable/health</a> - 健康检查</li>
                        <li><a href="/testable/endpoints">/testable/endpoints</a> - 所有端点 (JSON)</li>
                        <li><a href="/testable/registered">/testable/registered</a> - 已注册内容 (JSON)</li>
                    </ul>
                </div>

                <h2>📋 所有端点 ({len(app.url_map._rules) - 1})</h2>
                <table>
                    <thead>
                        <tr><th>路径</th><th>方法</th><th>操作</th></tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        '''


# ======================================================================
# 内部函数：打印日志
# ======================================================================

def _print(message: str) -> None:
    """内部日志输出，带时间戳。"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f'  [{timestamp}] {message}')


# ======================================================================
# 模块导出
# ======================================================================

__all__ = [
    # 核心 API
    'register',      # 显式注册蓝图/路由
    'register_all',  # 批量注册
    'start',         # 启动服务
    'create_app',    # 创建 Flask 应用（单元测试用）
    # 辅助
    'reset',         # 清空注册表
    'list_registered',  # 显示已注册内容
]


# ======================================================================
# 直接运行时的交互式演示
# ======================================================================

if __name__ == '__main__':
    print('\n' + '═' * 60)
    print('Testable Framework - 简化版（显式引用模式）')
    print('═' * 60)
    print('''
  使用方式：

    1. 在你的测试文件中：
       from tests.testable_framework import register, start

    2. 导入并注册你要测试的内容：
       from app.api.permission_api import permission_bp
       register(permission_bp, url_prefix='/api')

    3. 启动服务：
       start(port=5001)

    4. 浏览器访问 http://127.0.0.1:5001/testable/

  或者创建自己的测试启动文件，例如 tests/my_test_server.py：

    from tests.testable_framework import register, start
    from app.api.permission_api import permission_bp
    from app.routes.permission_manager_web import permission_manager_web_bp

    register(permission_bp, url_prefix='/api')
    register(permission_manager_web_bp)

    start(port=5001)

  然后运行: python -m tests.my_test_server
''')
    print('═' * 60)
