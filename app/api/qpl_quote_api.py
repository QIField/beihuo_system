# -*- coding:utf-8 -*-
# @Time    : 2026/6/5
# @Author  : system
# @Project : beihuo_system
# @File    : qpl_quote_api.py
# @Software: PyCharm

from functools import wraps
from flask import Blueprint, request, jsonify, session
from app.utils.database_connection import get_db_connection
from datetime import datetime

qpl_quote_bp = Blueprint('qpl_quote', __name__, url_prefix='/qpl_quote')


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_user_store():
    """获取用户当前的门店"""
    user_store = session.get('store', 'fsbbr')
    current_org = session.get('current_org', user_store)
    
    # 如果current_org是无效值，返回用户默认门店
    if not current_org or current_org in ('all', 'none', 'undefined', ''):
        return user_store
    
    return current_org


@qpl_quote_bp.route('/records', methods=['GET'])
@login_required
def get_records():
    """获取汽配龙报价记录列表"""
    try:
        print('[QPL Quote API] 收到请求')
        # 获取查询参数
        supplier_enquiry_no = request.args.get('supplier_enquiry_no', '')
        item_oe = request.args.get('item_oe', '')
        item_name = request.args.get('item_name', '')
        brand_name = request.args.get('brand_name', '')
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        # 计算偏移量
        offset = (page - 1) * limit
        
        # 获取用户当前门店
        current_store = get_user_store()
        print(f'[QPL Quote API] 用户门店: {current_store}')
        
        # 构建查询条件
        conditions = []
        params = []
        
        # 默认加上用户所在门店过滤
        conditions.append('company = %s')
        params.append(current_store)
        
        if supplier_enquiry_no:
            conditions.append('supplier_enquiry_no LIKE %s')
            params.append(f'%{supplier_enquiry_no}%')
        
        if item_oe:
            conditions.append('item_oe LIKE %s')
            params.append(f'%{item_oe}%')
        
        if item_name:
            conditions.append('item_name LIKE %s')
            params.append(f'%{item_name}%')
        
        if brand_name:
            conditions.append('brand_name LIKE %s')
            params.append(f'%{brand_name}%')
        
        if company:
            conditions.append('company = %s')
            params.append(company)
        
        if begin_date:
            conditions.append('submit_time >= %s')
            params.append(f'{begin_date} 00:00:00')
        
        if end_date:
            conditions.append('submit_time <= %s')
            params.append(f'{end_date} 23:59:59')
        
        # 构建SQL查询
        sql = 'SELECT * FROM qpl_quote_record'
        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)
        
        # 先获取总数
        count_sql = 'SELECT COUNT(*) FROM qpl_quote_record'
        if conditions:
            count_sql += ' WHERE ' + ' AND '.join(conditions)
        
        # 获取数据
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 获取总数
                cursor.execute(count_sql, params)
                result = cursor.fetchone()
                total = result['COUNT(*)'] if isinstance(result, dict) else (result[0] if result else 0)
                
                # 获取列表数据
                sql += ' ORDER BY submit_time DESC LIMIT %s OFFSET %s'
                params.extend([limit, offset])
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                result = []
                for row in rows:
                    # 直接使用字典结果（因为连接使用了DictCursor）
                    record = row.copy()
                    # 格式化时间（只对datetime对象处理）
                    if record.get('submit_time') and hasattr(record['submit_time'], 'strftime'):
                        record['submit_time'] = record['submit_time'].strftime('%Y-%m-%d %H:%M:%S')
                    if record.get('created_at') and hasattr(record['created_at'], 'strftime'):
                        record['created_at'] = record['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    result.append(record)
            
            print(f'[QPL Quote API] 返回数据: code=0, total={total}, list_length={len(result)}')
            return jsonify({
                'code': 0,
                'msg': 'success',
                'data': {
                    'list': result,
                    'total': total,
                    'page': page,
                    'limit': limit
                }
            })
        finally:
            conn.close()
    except Exception as e:
        print(f'[QPL Quote API] records接口错误: {type(e).__name__}: {str(e)}')
        import traceback
        print(f'[QPL Quote API] 堆栈: {traceback.format_exc()}')
        return jsonify({'code': 500, 'msg': str(e)})


@qpl_quote_bp.route('/stats', methods=['GET'])
def get_stats():
    """获取报价统计信息"""
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 今日数量
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute('SELECT COUNT(*) FROM qpl_quote_record WHERE DATE(submit_time) = %s', (today,))
                today_count = cursor.fetchone()[0]
                
                # 本周数量
                cursor.execute('SELECT COUNT(*) FROM qpl_quote_record WHERE YEARWEEK(submit_time, 1) = YEARWEEK(NOW(), 1)')
                week_count = cursor.fetchone()[0]
                
                # 总数量
                cursor.execute('SELECT COUNT(*) FROM qpl_quote_record')
                total_count = cursor.fetchone()[0]
            
            return jsonify({
            'code': 0,
            'msg': 'success',
            'data': {
                'today_count': today_count,
                'week_count': week_count,
                'total_count': total_count
            }
        })
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})
