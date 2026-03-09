# backend/log_viewer_api.py
"""
日志查看器 API 模块
用于读取和展示服务器日志文件
"""

from flask import Blueprint, request, jsonify, session, render_template
from functools import wraps
import os
import re
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


def register_log_viewer_routes(app):
    """注册日志查看器路由到 Flask 应用"""
    app.register_blueprint(log_viewer_bp)
