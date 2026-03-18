# backend/log_viewer_api.py
"""
日志查看器 API 模块
用于读取和展示服务器日志文件及系统配置
"""

from flask import Blueprint, request, jsonify, session, render_template
from functools import wraps
import os
import re
import sys
import platform
import subprocess
from datetime import datetime

# 创建蓝图
log_viewer_bp = Blueprint('log_viewer', __name__)

# 日志文件路径配置
LOG_FILE_PATH = '/www/wwwlogs/python/beihuo_system/uwsgi.log'


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


@log_viewer_bp.route('/log_viewer')
@login_required
def log_viewer_page():
    """渲染日志查看页面"""
    return render_template('log_viewer.html')


@log_viewer_bp.route('/api/logs')
@login_required
def get_logs():
    """
    获取日志内容 API
    
    查询参数:
    - page: 页码 (默认 1)
    - limit: 每页行数 (默认 50, 最大 500)
    - keyword: 搜索关键词 (可选)
    - level: 日志级别过滤 (可选: ERROR, WARNING, INFO, DEBUG)
    - start_date: 开始日期过滤 (格式: YYYY-MM-DD)
    - end_date: 结束日期过滤 (格式: YYYY-MM-DD)
    """
    try:
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        keyword = request.args.get('keyword', '').strip()
        level = request.args.get('level', '').upper()
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        # 参数校验
        if page < 1:
            page = 1
        if limit < 1:
            limit = 50
        if limit > 500:
            limit = 500  # 限制最大行数，防止内存溢出
        
        # 检查日志文件是否存在
        if not os.path.exists(LOG_FILE_PATH):
            return jsonify({
                'code': 1,
                'msg': f'日志文件不存在: {LOG_FILE_PATH}'
            })
        
        # 读取日志文件
        logs_data = read_log_file(
            page=page,
            limit=limit,
            keyword=keyword,
            level=level,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': logs_data['lines'],
            'count': logs_data['total'],
            'page': page,
            'limit': limit,
            'total_pages': logs_data['total_pages'],
            'file_size': logs_data['file_size'],
            'file_size_readable': logs_data['file_size_readable']
        })
        
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'读取日志失败: {str(e)}'
        })


@log_viewer_bp.route('/api/logs/download')
@login_required
def download_logs():
    """下载完整日志文件"""
    try:
        if not os.path.exists(LOG_FILE_PATH):
            return jsonify({
                'code': 1,
                'msg': f'日志文件不存在: {LOG_FILE_PATH}'
            })
        
        from flask import send_file
        
        return send_file(
            LOG_FILE_PATH,
            mimetype='text/plain',
            as_attachment=True,
            download_name=f'uwsgi_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
        
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'下载日志失败: {str(e)}'
        })


@log_viewer_bp.route('/api/logs/stats')
@login_required
def get_log_stats():
    """获取日志统计信息"""
    try:
        if not os.path.exists(LOG_FILE_PATH):
            return jsonify({
                'code': 1,
                'msg': f'日志文件不存在: {LOG_FILE_PATH}'
            })

        stats = analyze_log_stats()

        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': stats
        })

    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'获取统计信息失败: {str(e)}'
        })


@log_viewer_bp.route('/api/logs/context')
@login_required
def get_log_context():
    """
    获取指定行号的上下文日志

    查询参数:
    - line_num: 目标行号 (必填)
    - context_lines: 上下文行数 (默认 10, 即前后各10行)
    """
    try:
        line_num = request.args.get('line_num', type=int)
        context_lines = request.args.get('context_lines', 10, type=int)

        if line_num is None or line_num < 1:
            return jsonify({
                'code': 1,
                'msg': '请提供有效的行号'
            })

        # 限制上下文行数，防止内存溢出
        if context_lines < 1:
            context_lines = 10
        if context_lines > 100:
            context_lines = 100

        if not os.path.exists(LOG_FILE_PATH):
            return jsonify({
                'code': 1,
                'msg': f'日志文件不存在: {LOG_FILE_PATH}'
            })

        context_data = read_log_context(line_num, context_lines)

        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': context_data
        })

    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'获取上下文失败: {str(e)}'
        })


@log_viewer_bp.route('/api/logs/line-position')
@login_required
def get_line_position():
    """
    获取指定行号在完整日志中的位置信息（用于跳转）

    查询参数:
    - line_num: 目标行号 (必填)
    - limit: 每页行数 (默认 50)

    返回:
    - 该行所在的页码、在页内的索引等信息
    """
    try:
        target_line_num = request.args.get('line_num', type=int)
        limit = request.args.get('limit', 50, type=int)

        if target_line_num is None or target_line_num < 1:
            return jsonify({
                'code': 1,
                'msg': '请提供有效的行号'
            })

        if limit < 1:
            limit = 50
        if limit > 500:
            limit = 500

        if not os.path.exists(LOG_FILE_PATH):
            return jsonify({
                'code': 1,
                'msg': f'日志文件不存在: {LOG_FILE_PATH}'
            })

        # 计算目标行在完整日志中的位置
        position_data = calculate_line_position(target_line_num, limit)

        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': position_data
        })

    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'获取行位置失败: {str(e)}'
        })


def read_log_file(page=1, limit=50, keyword='', level='', start_date='', end_date=''):
    """
    读取日志文件内容
    
    参数:
    - page: 页码
    - limit: 每页行数
    - keyword: 搜索关键词
    - level: 日志级别过滤
    - start_date: 开始日期
    - end_date: 结束日期
    
    返回:
    - 包含日志行、总行数、总页数等信息的字典
    """
    
    # 获取文件信息
    file_stat = os.stat(LOG_FILE_PATH)
    file_size = file_stat.st_size
    file_size_readable = format_file_size(file_size)
    
    # 使用更高效的方式读取大文件 - 从末尾开始读取
    lines = []
    total_matched = 0
    
    # 正则表达式用于检测日志级别
    level_pattern = re.compile(r'\b(ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL)\b', re.IGNORECASE)
    
    # 日期格式正则
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')
    
    with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        # 读取所有行（对于大文件，这里可能需要优化）
        all_lines = f.readlines()
    
    # 过滤和搜索
    filtered_lines = []
    for line_num, line in enumerate(all_lines, 1):
        line = line.rstrip('\n\r')
        
        if not line:  # 跳过空行
            continue
        
        # 关键词过滤
        if keyword and keyword.lower() not in line.lower():
            continue
        
        # 日志级别过滤
        if level:
            line_level = detect_log_level(line, level_pattern)
            if line_level != level:
                continue
        
        # 日期过滤
        if start_date or end_date:
            line_date = extract_date(line, date_pattern)
            if line_date:
                if start_date and line_date < start_date:
                    continue
                if end_date and line_date > end_date:
                    continue
        
        # 检测日志级别（用于前端着色）
        line_level = detect_log_level(line, level_pattern)
        
        filtered_lines.append({
            'line_num': line_num,
            'content': line,
            'level': line_level,
            'timestamp': extract_timestamp(line)
        })
    
    total_matched = len(filtered_lines)
    total_pages = (total_matched + limit - 1) // limit if total_matched > 0 else 1

    # 分页 - 正序显示（最早的日志在前面，方便按时间顺序查看）
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_lines = filtered_lines[start_idx:end_idx]
    
    return {
        'lines': paginated_lines,
        'total': total_matched,
        'total_pages': total_pages,
        'file_size': file_size,
        'file_size_readable': file_size_readable
    }


def detect_log_level(line, pattern=None):
    """
    检测日志行的级别
    
    参数:
    - line: 日志行内容
    - pattern: 正则表达式模式
    
    返回: 日志级别字符串 (ERROR, WARNING, INFO, DEBUG, UNKNOWN)
    """
    if pattern is None:
        pattern = re.compile(r'\b(ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL)\b', re.IGNORECASE)
    
    match = pattern.search(line)
    if match:
        level = match.group(1).upper()
        # 统一 WARN -> WARNING
        if level == 'WARN':
            level = 'WARNING'
        return level
    
    # 根据内容特征判断
    if 'error' in line.lower() or 'exception' in line.lower() or 'traceback' in line.lower():
        return 'ERROR'
    elif 'warning' in line.lower() or 'warn' in line.lower():
        return 'WARNING'
    elif 'debug' in line.lower():
        return 'DEBUG'
    elif 'info' in line.lower():
        return 'INFO'
    
    return 'UNKNOWN'


def extract_date(line, pattern=None):
    """
    从日志行中提取日期
    
    参数:
    - line: 日志行内容
    - pattern: 正则表达式模式
    
    返回: YYYY-MM-DD 格式的日期字符串，或 None
    """
    if pattern is None:
        pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')
    
    match = pattern.search(line)
    if match:
        return match.group(1)
    return None


def extract_timestamp(line):
    """
    从日志行中提取完整时间戳
    
    参数:
    - line: 日志行内容
    
    返回: 时间戳字符串，或 None
    """
    # 匹配常见的时间格式
    patterns = [
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',  # 2024-01-15 10:30:00
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',   # 2024-01-15T10:30:00
        r'(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})',    # 15/Jan/2024:10:30:00
    ]
    
    for pattern in patterns:
        match = re.search(pattern, line)
        if match:
            return match.group(1)
    
    return None


def format_file_size(size_bytes):
    """
    将字节大小转换为可读格式
    
    参数:
    - size_bytes: 字节数
    
    返回: 可读的大小字符串 (如: 1.5 MB)
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def analyze_log_stats():
    """
    分析日志统计信息
    
    返回: 包含统计信息的字典
    """
    stats = {
        'total_lines': 0,
        'error_count': 0,
        'warning_count': 0,
        'info_count': 0,
        'debug_count': 0,
        'file_size': 0,
        'file_size_readable': '',
        'last_modified': '',
        'recent_errors': []
    }
    
    file_stat = os.stat(LOG_FILE_PATH)
    stats['file_size'] = file_stat.st_size
    stats['file_size_readable'] = format_file_size(file_stat.st_size)
    stats['last_modified'] = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    
    level_pattern = re.compile(r'\b(ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL)\b', re.IGNORECASE)
    
    with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            stats['total_lines'] += 1
            
            level = detect_log_level(line, level_pattern)
            if level == 'ERROR':
                stats['error_count'] += 1
                # 保存最近的错误
                if len(stats['recent_errors']) < 5:
                    stats['recent_errors'].append(line.strip()[:200])
            elif level == 'WARNING':
                stats['warning_count'] += 1
            elif level == 'INFO':
                stats['info_count'] += 1
            elif level == 'DEBUG':
                stats['debug_count'] += 1
    
    return stats


def read_log_context(target_line_num, context_lines=10):
    """
    读取指定行号的上下文日志

    参数:
    - target_line_num: 目标行号 (1-based)
    - context_lines: 上下文行数 (前后各多少行)

    返回:
    - 包含上下文日志信息的字典
    """
    level_pattern = re.compile(r'\b(ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL)\b', re.IGNORECASE)

    # 计算读取范围
    start_line = max(1, target_line_num - context_lines)
    end_line = target_line_num + context_lines

    context_logs = []
    total_file_lines = 0

    with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        all_lines = f.readlines()
        total_file_lines = len(all_lines)

        # 调整结束行号，不超过文件总行数
        end_line = min(end_line, total_file_lines)

        # 提取上下文行
        for line_idx in range(start_line - 1, end_line):  # 转换为 0-based 索引
            line_num = line_idx + 1  # 转回 1-based 行号
            line = all_lines[line_idx].rstrip('\n\r')

            # 检测日志级别
            line_level = detect_log_level(line, level_pattern)

            context_logs.append({
                'line_num': line_num,
                'content': line,
                'level': line_level,
                'is_target': line_num == target_line_num  # 标记是否为目标行
            })

    return {
        'target_line': target_line_num,
        'context_lines': context_logs,
        'start_line': start_line,
        'end_line': end_line,
        'total_file_lines': total_file_lines
    }


def calculate_line_position(target_line_num, limit=50):
    """
    计算指定行号在完整日志（无过滤）中的位置信息

    参数:
    - target_line_num: 目标行号 (1-based)
    - limit: 每页行数

    返回:
    - 包含页码、索引等位置信息的字典
    """
    total_lines = 0

    with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        all_lines = f.readlines()
        total_lines = len(all_lines)

    # 确保目标行号在有效范围内
    if target_line_num > total_lines:
        target_line_num = total_lines

    # 计算目标行所在的页码 (1-based)
    target_page = (target_line_num - 1) // limit + 1

    # 计算目标行在页内的索引 (0-based)
    index_in_page = (target_line_num - 1) % limit

    # 计算总页数
    total_pages = (total_lines + limit - 1) // limit if total_lines > 0 else 1

    return {
        'target_line': target_line_num,
        'target_page': target_page,
        'index_in_page': index_in_page,
        'total_lines': total_lines,
        'total_pages': total_pages,
        'limit': limit
    }


@log_viewer_bp.route('/api/server/config')
@login_required
def get_server_config():
    """
    获取服务器配置信息
    包括uWSGI配置、Python环境、系统资源、数据库状态等
    """
    try:
        config_data = {
            'uwsgi': get_uwsgi_config(),
            'python': get_python_info(),
            'system': get_system_info(),
            'database': get_database_status(),
            'application': get_application_info()
        }
        
        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': config_data
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'获取服务器配置失败: {str(e)}'
        })


def get_uwsgi_config():
    """获取uWSGI配置信息"""
    config = {
        'config_file': 'uwsgi.ini',
        'config_exists': os.path.exists('uwsgi.ini'),
        'settings': {}
    }
    
    # 尝试读取uwsgi.ini文件
    if config['config_exists']:
        try:
            with open('uwsgi.ini', 'r', encoding='utf-8') as f:
                content = f.read()
                config['raw_content'] = content
                
            # 解析关键配置项
            config['settings'] = {
                'module': extract_ini_value(content, 'module'),
                'processes': extract_ini_value(content, 'processes'),
                'threads': extract_ini_value(content, 'threads'),
                'enable_threads': extract_ini_value(content, 'enable-threads'),
                'single_interpreter': extract_ini_value(content, 'single-interpreter'),
                'lazy_apps': extract_ini_value(content, 'lazy-apps'),
                'http': extract_ini_value(content, 'http'),
                'master': extract_ini_value(content, 'master'),
                'max_requests': extract_ini_value(content, 'max-requests'),
                'harakiri': extract_ini_value(content, 'harakiri'),
                'buffer_size': extract_ini_value(content, 'buffer-size')
            }
        except Exception as e:
            config['error'] = str(e)
    
    # 检测是否在uWSGI环境中运行
    config['running_in_uwsgi'] = 'uwsgi' in sys.modules
    
    return config


def extract_ini_value(content, key):
    """从ini文件内容中提取配置值"""
    pattern = rf'^{key}\s*=\s*(.+)$'
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else None


def get_python_info():
    """获取Python环境信息"""
    info = {
        'version': sys.version,
        'version_info': {
            'major': sys.version_info.major,
            'minor': sys.version_info.minor,
            'micro': sys.version_info.micro,
            'releaselevel': sys.version_info.releaselevel
        },
        'executable': sys.executable,
        'platform': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'prefix': sys.prefix,
        'path': sys.path[:5]  # 只显示前5个路径
    }
    
    # 获取关键库版本
    try:
        import pandas
        info['pandas_version'] = pandas.__version__
    except ImportError:
        info['pandas_version'] = '未安装'
    
    try:
        import numpy
        info['numpy_version'] = numpy.__version__
    except ImportError:
        info['numpy_version'] = '未安装'
    
    try:
        import flask
        info['flask_version'] = flask.__version__
    except ImportError:
        info['flask_version'] = '未安装'
    
    try:
        import sqlalchemy
        info['sqlalchemy_version'] = sqlalchemy.__version__
    except ImportError:
        info['sqlalchemy_version'] = '未安装'
    
    return info


def get_system_info():
    """获取系统资源信息"""
    info = {
        'os': platform.system(),
        'os_release': platform.release(),
        'hostname': platform.node(),
        'cpu_count': os.cpu_count(),
    }
    
    # 尝试获取内存信息（Linux）
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
            
        # 解析内存信息
        total_match = re.search(r'MemTotal:\s+(\d+)\s+kB', meminfo)
        available_match = re.search(r'MemAvailable:\s+(\d+)\s+kB', meminfo)
        
        if total_match:
            total_kb = int(total_match.group(1))
            info['memory_total'] = format_memory_size(total_kb * 1024)
        
        if available_match:
            available_kb = int(available_match.group(1))
            info['memory_available'] = format_memory_size(available_kb * 1024)
            
        if total_match and available_match:
            used_kb = int(total_match.group(1)) - int(available_match.group(1))
            info['memory_used'] = format_memory_size(used_kb * 1024)
            info['memory_usage_percent'] = round(used_kb / int(total_match.group(1)) * 100, 1)
            
    except Exception:
        info['memory_info'] = '无法获取（非Linux系统或权限不足）'
    
    # 尝试获取磁盘信息
    try:
        stat = os.statvfs('.')
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bfree * stat.f_frsize
        used = total - free
        
        info['disk_total'] = format_memory_size(total)
        info['disk_free'] = format_memory_size(free)
        info['disk_used'] = format_memory_size(used)
        info['disk_usage_percent'] = round(used / total * 100, 1)
    except Exception as e:
        info['disk_info'] = f'无法获取: {str(e)}'
    
    return info


def format_memory_size(size_bytes):
    """将字节大小转换为可读格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_database_status():
    """获取数据库连接状态"""
    status = {
        'status': '未知',
        'config_loaded': False,
        'connection_test': '未测试'
    }
    
    try:
        # 尝试导入数据库配置
        from app.utils.db_pool import pool
        status['config_loaded'] = True
        
        # 尝试获取连接池信息
        if hasattr(pool, '_pool'):
            pool_obj = pool._pool
            status['pool_size'] = pool_obj._pool_size if hasattr(pool_obj, '_pool_size') else '未知'
            status['connections'] = len(pool_obj._connections) if hasattr(pool_obj, '_connections') else '未知'
        
        # 测试连接
        try:
            conn = pool.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
            cursor.close()
            pool.release_connection(conn)
            status['status'] = '正常'
            status['connection_test'] = '成功'
        except Exception as e:
            status['status'] = '连接失败'
            status['connection_test'] = f'失败: {str(e)}'
            
    except ImportError:
        status['status'] = '配置未加载'
        status['connection_test'] = '无法导入数据库模块'
    except Exception as e:
        status['status'] = '异常'
        status['connection_test'] = f'错误: {str(e)}'
    
    return status


def get_application_info():
    """获取应用运行信息"""
    info = {
        'current_working_directory': os.getcwd(),
        'process_id': os.getpid(),
        'parent_process_id': os.getppid(),
        'environment_variables': {
            'PYTHONPATH': os.environ.get('PYTHONPATH', '未设置'),
            'FLASK_ENV': os.environ.get('FLASK_ENV', '未设置'),
            'FLASK_DEBUG': os.environ.get('FLASK_DEBUG', '未设置')
        }
    }
    
    # 获取已加载的模块数量
    info['loaded_modules_count'] = len(sys.modules)
    
    # 检测是否在uWSGI中
    info['uwsgi_mode'] = 'uwsgi' in sys.modules
    
    # 获取线程信息
    try:
        import threading
        info['active_threads'] = threading.active_count()
    except Exception:
        pass
    
    return info


def register_log_viewer_routes(app):
    """注册日志查看器路由到 Flask 应用"""
    app.register_blueprint(log_viewer_bp)
