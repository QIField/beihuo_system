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


# result_source 英文值到中文展示名的映射
_RESULT_SOURCE_CN_MAP = {
    'existing_quote': '已有报价',
    'crm': 'CRM现货',
    'mercedes': '奔驰接口',
    'bmw': '宝马接口',
    'adapt_list_empty': '适配列表为空',
    'original_product_no_oe': '原厂产品无 OE',
    'crm_part_no_mismatch': 'CRM-partNo未匹配',
    'crm_no_price': 'CRM无有效价格',
    'crm_price_check_failed': 'CRM价格校验失败',
    'oe_data_missing': '零件信息请求失败',
    'no_stock': '无库存',
    'invalid_price': '价格无效',
    'price_check_failed': '价格检测失败',
    'unknown': '未知',
}

_RESULT_SOURCE_EN_MAP = {v: k for k, v in _RESULT_SOURCE_CN_MAP.items()}


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


def _build_conditions(current_store, supplier_enquiry_no='', item_oe='', item_name='', brand_name='',
                      company='', begin_date='', end_date='', filter_column=None, filter_values=None,
                      allowed_filter_columns=None):
    """构建公共 WHERE 条件和参数列表"""
    conditions = ['company = %s']
    params = [current_store]

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
    if filter_column and allowed_filter_columns and filter_column in allowed_filter_columns and filter_values:
        # result_source 前端传中文，查库前转英文
        if filter_column == 'result_source':
            filter_values = [_RESULT_SOURCE_EN_MAP.get(v, v) for v in filter_values]
        placeholders = ', '.join(['%s'] * len(filter_values))
        conditions.append(f'{filter_column} IN ({placeholders})')
        params.extend(filter_values)

    return conditions, params


def _prefix_conditions(conditions, prefix):
    """为条件中的列名添加表别名前缀，避免 JOIN 后 where clause 歧义"""
    prefixed = []
    for cond in conditions:
        parts = cond.split(' ', 2)
        if len(parts) >= 2:
            col = parts[0]
            rest = cond[len(col):]
            prefixed.append(f'{prefix}.{col}{rest}')
        else:
            prefixed.append(cond)
    return prefixed


@qpl_quote_bp.route('/records', methods=['GET'])
@login_required
def get_records():
    """获取汽配龙报价记录列表"""
    try:
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
        sort_column = request.args.get('sort_column', '').strip()
        sort_dir = request.args.get('sort_dir', '').strip().lower()
        filter_column = request.args.get('filter_column', '').strip()
        filter_values = request.args.getlist('filter_values')

        # 计算偏移量
        offset = (page - 1) * limit

        # 允许的字段白名单（排序和筛选共用）
        allowed_columns = {
            'supplier_enquiry_no', 'submit_time', 'item_oe', 'item_name',
            'brand_name', 'item_sell_price', 'delivery_aging', 'item_quality',
            'parts_no', 'quote_status', 'result_source', 'submit_result'
        }
        
        # 获取用户当前门店
        current_store = get_user_store()

        # 构建查询条件
        conditions, params = _build_conditions(
            current_store,
            supplier_enquiry_no=supplier_enquiry_no,
            item_oe=item_oe,
            item_name=item_name,
            brand_name=brand_name,
            company=company,
            begin_date=begin_date,
            end_date=end_date,
            filter_column=filter_column,
            filter_values=filter_values,
            allowed_filter_columns=allowed_columns
        )

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
                
                # 获取列表数据：默认按订单最新提交时间降序，再按订单号、OE号、提交时间排，保持合并；支持自定义排序
                if sort_column and sort_column in allowed_columns and sort_dir in ('asc', 'desc'):
                    sql += f' ORDER BY {sort_column} {sort_dir.upper()} LIMIT %s OFFSET %s'
                    list_params = params + [limit, offset]
                    cursor.execute(sql, list_params)
                else:
                    inner_where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
                    outer_conditions = _prefix_conditions(conditions, 'q1')
                    outer_where = ' WHERE ' + ' AND '.join(outer_conditions) if outer_conditions else ''
                    sql = f'''SELECT q1.* FROM qpl_quote_record q1
                        INNER JOIN (
                            SELECT supplier_enquiry_no, MAX(submit_time) as max_submit_time
                            FROM qpl_quote_record
                            {inner_where}
                            GROUP BY supplier_enquiry_no
                        ) q2 ON q1.supplier_enquiry_no = q2.supplier_enquiry_no
                        {outer_where}
                        ORDER BY q2.max_submit_time DESC, q1.supplier_enquiry_no ASC, q1.item_oe ASC, q1.submit_time DESC
                        LIMIT %s OFFSET %s'''
                    list_params = params + params + [limit, offset]
                    cursor.execute(sql, list_params)
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
                    # result_source 英文值转中文展示
                    record['result_source'] = _RESULT_SOURCE_CN_MAP.get(
                        record.get('result_source'), record.get('result_source', '未知')
                    )
                    result.append(record)
            
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
        return jsonify({'code': 500, 'msg': str(e)})


@qpl_quote_bp.route('/filter_values', methods=['GET'])
@login_required
def get_filter_values():
    """获取指定列在当前查询条件下的去重值列表（供表头筛选面板使用）"""
    try:
        column = request.args.get('column', '').strip()

        allowed_columns = {
            'supplier_enquiry_no', 'submit_time', 'item_oe', 'item_name',
            'brand_name', 'item_sell_price', 'delivery_aging', 'item_quality',
            'parts_no', 'quote_status', 'result_source', 'submit_result'
        }
        if not column or column not in allowed_columns:
            return jsonify({'code': 1, 'msg': '无效的列名'})

        # 复用 /records 相同的查询条件
        supplier_enquiry_no = request.args.get('supplier_enquiry_no', '')
        item_oe = request.args.get('item_oe', '')
        item_name = request.args.get('item_name', '')
        brand_name = request.args.get('brand_name', '')
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')

        current_store = get_user_store()

        conditions, params = _build_conditions(
            current_store,
            supplier_enquiry_no=supplier_enquiry_no,
            item_oe=item_oe,
            item_name=item_name,
            brand_name=brand_name,
            company=company,
            begin_date=begin_date,
            end_date=end_date
        )

        where_clause = 'WHERE ' + ' AND '.join(conditions)

        # 明细列表筛选面板计数需要按订单维度去重的字段
        order_dedup_columns = {
            'supplier_enquiry_no': 'supplier_enquiry_no',
            'submit_time': 'supplier_enquiry_no, submit_time',
            'item_oe': 'supplier_enquiry_no, item_oe',
            'item_name': 'supplier_enquiry_no, item_name',
        }

        if column in order_dedup_columns:
            distinct_fields = order_dedup_columns[column]
            sql = f'''
                SELECT {column} AS value, COUNT(*) AS count
                FROM (
                    SELECT DISTINCT {distinct_fields}
                    FROM qpl_quote_record
                    {where_clause}
                ) t
                GROUP BY {column}
                ORDER BY {column} ASC
                LIMIT 1000
            '''
        else:
            sql = f'''
                SELECT {column} AS value, COUNT(*) AS count
                FROM qpl_quote_record
                {where_clause}
                GROUP BY {column}
                ORDER BY {column} ASC
                LIMIT 1000
            '''

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                values = []
                for row in rows:
                    if isinstance(row, dict):
                        val = row.get('value')
                        cnt = int(row.get('count', 0))
                    else:
                        val = row[0]
                        cnt = int(row[1]) if len(row) > 1 else 0
                    if val is None:
                        val = '(空)'
                    # result_source 英文值转中文展示
                    if column == 'result_source':
                        val = _RESULT_SOURCE_CN_MAP.get(val, val)
                    values.append({'value': str(val), 'count': cnt})
                return jsonify({'code': 0, 'msg': 'success', 'data': values})
        finally:
            conn.close()
    except Exception as e:
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


@qpl_quote_bp.route('/oe_stats', methods=['GET'])
@login_required
def get_oe_stats():
    """按 OE+产品名称 分组统计出现次数"""
    try:
        item_oe = request.args.get('item_oe', '')
        item_name = request.args.get('item_name', '')
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        sort_column = request.args.get('sort_column', '').strip()
        sort_dir = request.args.get('sort_dir', '').strip().lower()
        filter_column = request.args.get('filter_column', '').strip()
        filter_values = request.args.getlist('filter_values')

        offset = (page - 1) * limit

        allowed_columns = {'item_oe', 'item_name', 'occurrence_count'}
        allowed_filter_columns = {'item_oe', 'item_name', 'occurrence_count'}
        current_store = get_user_store()

        # occurrence_count 是聚合字段，需用 HAVING 过滤，不能放在 WHERE
        having_filter_condition = ''
        having_filter_params = []
        query_filter_column = filter_column
        query_filter_values = filter_values
        if filter_column == 'occurrence_count' and filter_values:
            placeholders = ', '.join(['%s'] * len(filter_values))
            having_filter_condition = f' AND occurrence_count IN ({placeholders})'
            having_filter_params = list(filter_values)
            query_filter_column = ''
            query_filter_values = []

        conditions, params = _build_conditions(
            current_store,
            item_oe=item_oe,
            item_name=item_name,
            company=company,
            begin_date=begin_date,
            end_date=end_date,
            filter_column=query_filter_column,
            filter_values=query_filter_values,
            allowed_filter_columns=allowed_filter_columns
        )

        where_clause = 'WHERE ' + ' AND '.join(conditions)

        # 统计总数
        count_sql = f'''
            SELECT COUNT(*) FROM (
                SELECT item_oe, COALESCE(item_name, '') as item_name, COUNT(DISTINCT supplier_enquiry_no) as occurrence_count
                FROM qpl_quote_record
                {where_clause}
                GROUP BY item_oe, COALESCE(item_name, '')
                HAVING 1=1 {having_filter_condition}
            ) t
        '''

        # 数据查询
        order_by = 'occurrence_count DESC, item_oe ASC'
        if sort_column and sort_column in allowed_columns and sort_dir in ('asc', 'desc'):
            if sort_column == 'occurrence_count':
                order_by = f'occurrence_count {sort_dir.upper()}, item_oe ASC'
            else:
                order_by = f'{sort_column} {sort_dir.upper()}'

        data_sql = f'''
            SELECT item_oe, COALESCE(item_name, '') as item_name, COUNT(DISTINCT supplier_enquiry_no) as occurrence_count
            FROM qpl_quote_record
            {where_clause}
            GROUP BY item_oe, COALESCE(item_name, '')
            HAVING 1=1 {having_filter_condition}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        '''

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(count_sql, params + having_filter_params)
                result = cursor.fetchone()
                total = result['COUNT(*)'] if isinstance(result, dict) else (result[0] if result else 0)

                cursor.execute(data_sql, params + having_filter_params + [limit, offset])
                rows = cursor.fetchall()

                result_list = []
                for idx, row in enumerate(rows, start=offset + 1):
                    record = row.copy() if isinstance(row, dict) else dict(row)
                    record['rowNumber'] = idx
                    result_list.append(record)

            return jsonify({
                'code': 0,
                'msg': 'success',
                'data': {
                    'list': result_list,
                    'total': total,
                    'page': page,
                    'limit': limit
                }
            })
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})


@qpl_quote_bp.route('/oe_filter_values', methods=['GET'])
@login_required
def get_oe_filter_values():
    """获取 OE 统计维度指定列的去重值"""
    try:
        column = request.args.get('column', '').strip()
        allowed_columns = {'item_oe', 'item_name', 'occurrence_count'}
        if not column or column not in allowed_columns:
            return jsonify({'code': 1, 'msg': '无效的列名'})

        item_oe = request.args.get('item_oe', '')
        item_name = request.args.get('item_name', '')
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')

        current_store = get_user_store()
        conditions, params = _build_conditions(
            current_store,
            item_oe=item_oe,
            item_name=item_name,
            company=company,
            begin_date=begin_date,
            end_date=end_date
        )

        where_clause = 'WHERE ' + ' AND '.join(conditions)

        if column == 'occurrence_count':
            sql = f'''
                SELECT occurrence_count AS value, COUNT(*) AS count
                FROM (
                    SELECT COUNT(DISTINCT supplier_enquiry_no) AS occurrence_count
                    FROM qpl_quote_record
                    {where_clause}
                    GROUP BY item_oe, COALESCE(item_name, '')
                ) t
                GROUP BY occurrence_count
                ORDER BY occurrence_count ASC
                LIMIT 1000
            '''
        else:
            sql = f'''
                SELECT {column} AS value, COUNT(DISTINCT supplier_enquiry_no) AS count
                FROM qpl_quote_record
                {where_clause}
                GROUP BY {column}
                ORDER BY {column} ASC
                LIMIT 1000
            '''

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                values = []
                for row in rows:
                    if isinstance(row, dict):
                        val = row.get('value')
                        cnt = int(row.get('count', 0))
                    else:
                        val = row[0]
                        cnt = int(row[1]) if len(row) > 1 else 0
                    if val is None:
                        val = '(空)'
                    values.append({'value': str(val), 'count': cnt})
                return jsonify({'code': 0, 'msg': 'success', 'data': values})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})


def _build_vin_base_conditions(current_store, company='', begin_date='', end_date=''):
    """构建 VIN 维度统计的公共 WHERE 条件（使用 q 作为 qpl_quote_record 别名）"""
    conditions = ['q.company = %s']
    params = [current_store]

    if company:
        conditions.append('q.company = %s')
        params.append(company)
    if begin_date:
        conditions.append('q.submit_time >= %s')
        params.append(f'{begin_date} 00:00:00')
    if end_date:
        conditions.append('q.submit_time <= %s')
        params.append(f'{end_date} 23:59:59')

    return conditions, params


def _get_vin_dimension_config(dimension):
    """获取 VIN 维度统计的 SQL 配置"""
    configs = {
        'oenum': {
            'select_expr': 'q.item_oe',
            'group_expr': 'q.item_oe',
            'label_column': 'item_oe',
            'allowed_sort_columns': {'item_oe', 'occurrence_count'},
            'allowed_filter_columns': {'item_oe', 'occurrence_count'},
            'join_clause': '',
            'value_select': 'q.item_oe'
        },
        'engine': {
            'select_expr': "COALESCE(v.engine, '')",
            'group_expr': "COALESCE(v.engine, '')",
            'label_column': 'engine',
            'allowed_sort_columns': {'engine', 'occurrence_count'},
            'allowed_filter_columns': {'engine', 'occurrence_count'},
            'join_clause': 'LEFT JOIN vin_vehicle_info v ON q.vin_code = v.vin_code',
            'value_select': "COALESCE(v.engine, '')"
        },
        'chassis': {
            'select_expr': "COALESCE(v.chassis, '')",
            'group_expr': "COALESCE(v.chassis, '')",
            'label_column': 'chassis',
            'allowed_sort_columns': {'chassis', 'occurrence_count'},
            'allowed_filter_columns': {'chassis', 'occurrence_count'},
            'join_clause': 'LEFT JOIN vin_vehicle_info v ON q.vin_code = v.vin_code',
            'value_select': "COALESCE(v.chassis, '')"
        }
    }
    return configs.get(dimension)


def _query_vin_stats(dimension, current_store, company, begin_date, end_date,
                     sort_column, sort_dir, filter_column, filter_values, page, limit):
    """通用 VIN 维度统计查询"""
    config = _get_vin_dimension_config(dimension)
    if not config:
        return None, '无效的统计维度'

    conditions, params = _build_vin_base_conditions(
        current_store, company=company, begin_date=begin_date, end_date=end_date
    )
    where_clause = 'WHERE ' + ' AND '.join(conditions)

    # 维度字段过滤条件
    filter_condition = ''
    filter_params = []
    # occurrence_count 聚合字段过滤条件
    having_count_condition = ''
    having_count_params = []
    if filter_column and filter_column in config['allowed_filter_columns'] and filter_values:
        placeholders = ', '.join(['%s'] * len(filter_values))
        if filter_column == 'occurrence_count':
            having_count_condition = f' AND occurrence_count IN ({placeholders})'
            having_count_params = list(filter_values)
        else:
            filter_condition = f' AND {config["label_column"]} IN ({placeholders})'
            filter_params = list(filter_values)

    # 不统计空字符串维度值
    empty_condition = f" AND {config['label_column']} != ''"

    count_sql = f'''
        SELECT COUNT(*) FROM (
            SELECT {config['select_expr']} AS {config['label_column']}, COUNT(DISTINCT q.supplier_enquiry_no) AS occurrence_count
            FROM qpl_quote_record q
            {config['join_clause']}
            {where_clause}
            GROUP BY {config['group_expr']}
            HAVING 1=1 {filter_condition} {empty_condition} {having_count_condition}
        ) t
    '''

    order_by = f'occurrence_count DESC, {config["label_column"]} ASC'
    if sort_column and sort_column in config['allowed_sort_columns'] and sort_dir in ('asc', 'desc'):
        if sort_column == 'occurrence_count':
            order_by = f'occurrence_count {sort_dir.upper()}, {config["label_column"]} ASC'
        else:
            order_by = f'{config["label_column"]} {sort_dir.upper()}'

    data_sql = f'''
        SELECT {config['select_expr']} AS {config['label_column']}, COUNT(DISTINCT q.supplier_enquiry_no) AS occurrence_count
        FROM qpl_quote_record q
        {config['join_clause']}
        {where_clause}
        GROUP BY {config['group_expr']}
        HAVING 1=1 {filter_condition} {empty_condition} {having_count_condition}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
    '''

    offset = (page - 1) * limit
    query_params = params + filter_params + having_count_params
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(count_sql, query_params)
            result = cursor.fetchone()
            total = result['COUNT(*)'] if isinstance(result, dict) else (result[0] if result else 0)

            cursor.execute(data_sql, query_params + [limit, offset])
            rows = cursor.fetchall()

            result_list = []
            for idx, row in enumerate(rows, start=offset + 1):
                record = row.copy() if isinstance(row, dict) else dict(row)
                record['rowNumber'] = idx
                result_list.append(record)

        return {
            'code': 0,
            'msg': 'success',
            'data': {
                'list': result_list,
                'total': total,
                'page': page,
                'limit': limit
            }
        }, None
    finally:
        conn.close()


def _query_vin_filter_values(dimension, column, current_store, company, begin_date, end_date):
    """通用 VIN 维度列头筛选值查询"""
    config = _get_vin_dimension_config(dimension)
    if not config or column not in config['allowed_filter_columns']:
        return None, '无效的列名'

    conditions, params = _build_vin_base_conditions(
        current_store, company=company, begin_date=begin_date, end_date=end_date
    )
    where_clause = 'WHERE ' + ' AND '.join(conditions)

    if column == 'occurrence_count':
        sql = f'''
            SELECT occurrence_count AS value, COUNT(*) AS count
            FROM (
                SELECT COUNT(DISTINCT q.supplier_enquiry_no) AS occurrence_count
                FROM qpl_quote_record q
                {config['join_clause']}
                {where_clause}
                GROUP BY {config['group_expr']}
                HAVING {config['label_column']} != ''
            ) t
            GROUP BY occurrence_count
            ORDER BY occurrence_count ASC
            LIMIT 1000
        '''
    else:
        sql = f'''
            SELECT {config['value_select']} AS value, COUNT(DISTINCT q.supplier_enquiry_no) AS count
            FROM qpl_quote_record q
            {config['join_clause']}
            {where_clause}
            GROUP BY {config['group_expr']}
            HAVING value != ''
            ORDER BY {config['label_column']} ASC
            LIMIT 1000
        '''

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            values = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    val = row.get('value')
                    cnt = int(row.get('count', 0))
                else:
                    val = row[0]
                    cnt = int(row[1]) if len(row) > 1 else 0
                if val is None:
                    val = '(空)'
                values.append({'value': str(val), 'count': cnt})
            return {'code': 0, 'msg': 'success', 'data': values}, None
    finally:
        conn.close()


@qpl_quote_bp.route('/vin_stats_oenum', methods=['GET'])
@login_required
def get_vin_stats_oenum():
    """VIN 维度：按 OE 分组统计出现次数"""
    try:
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        sort_column = request.args.get('sort_column', '').strip()
        sort_dir = request.args.get('sort_dir', '').strip().lower()
        filter_column = request.args.get('filter_column', '').strip()
        filter_values = request.args.getlist('filter_values')

        current_store = get_user_store()
        result, error = _query_vin_stats(
            'oenum', current_store, company, begin_date, end_date,
            sort_column, sort_dir, filter_column, filter_values, page, limit
        )
        if error:
            return jsonify({'code': 1, 'msg': error})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})


@qpl_quote_bp.route('/vin_stats_engine', methods=['GET'])
@login_required
def get_vin_stats_engine():
    """VIN 维度：按发动机分组统计出现次数"""
    try:
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        sort_column = request.args.get('sort_column', '').strip()
        sort_dir = request.args.get('sort_dir', '').strip().lower()
        filter_column = request.args.get('filter_column', '').strip()
        filter_values = request.args.getlist('filter_values')

        current_store = get_user_store()
        result, error = _query_vin_stats(
            'engine', current_store, company, begin_date, end_date,
            sort_column, sort_dir, filter_column, filter_values, page, limit
        )
        if error:
            return jsonify({'code': 1, 'msg': error})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})


@qpl_quote_bp.route('/vin_stats_chassis', methods=['GET'])
@login_required
def get_vin_stats_chassis():
    """VIN 维度：按底盘分组统计出现次数"""
    try:
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        sort_column = request.args.get('sort_column', '').strip()
        sort_dir = request.args.get('sort_dir', '').strip().lower()
        filter_column = request.args.get('filter_column', '').strip()
        filter_values = request.args.getlist('filter_values')

        current_store = get_user_store()
        result, error = _query_vin_stats(
            'chassis', current_store, company, begin_date, end_date,
            sort_column, sort_dir, filter_column, filter_values, page, limit
        )
        if error:
            return jsonify({'code': 1, 'msg': error})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})


@qpl_quote_bp.route('/vin_oenum_filter_values', methods=['GET'])
@login_required
def get_vin_oenum_filter_values():
    """VIN 维度：OE 统计列头筛选值"""
    try:
        column = request.args.get('column', '').strip()
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')

        current_store = get_user_store()
        result, error = _query_vin_filter_values(
            'oenum', column, current_store, company, begin_date, end_date
        )
        if error:
            return jsonify({'code': 1, 'msg': error})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})


@qpl_quote_bp.route('/vin_engine_filter_values', methods=['GET'])
@login_required
def get_vin_engine_filter_values():
    """VIN 维度：发动机统计列头筛选值"""
    try:
        column = request.args.get('column', '').strip()
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')

        current_store = get_user_store()
        result, error = _query_vin_filter_values(
            'engine', column, current_store, company, begin_date, end_date
        )
        if error:
            return jsonify({'code': 1, 'msg': error})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})


@qpl_quote_bp.route('/vin_chassis_filter_values', methods=['GET'])
@login_required
def get_vin_chassis_filter_values():
    """VIN 维度：底盘统计列头筛选值"""
    try:
        column = request.args.get('column', '').strip()
        company = request.args.get('company', '')
        begin_date = request.args.get('begin_date', '')
        end_date = request.args.get('end_date', '')

        current_store = get_user_store()
        result, error = _query_vin_filter_values(
            'chassis', column, current_store, company, begin_date, end_date
        )
        if error:
            return jsonify({'code': 1, 'msg': error})
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)})
