# beihuo_system/virtual_inventory_api.py
from flask import Blueprint, request, jsonify, session, render_template
import pymysql
from functools import wraps
import os
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection  # 使用统一的连接池实现
import time

# 计时工具函数
def log_time_cost(operation_name, start_time):
    """记录操作耗时"""
    cost = (time.time() - start_time) * 1000  # 转换为毫秒
    print(f"[⏱️ 后端计时] {operation_name} 耗时: {cost:.2f}ms")
    return cost

# 创建蓝图
virtual_inventory_bp = Blueprint('virtual_inventory', __name__)

VIRTUAL_INVENTORY_TABLE_MAP = {
    'fsbbr': 'virtual_inventory',
    'zhbbr': 'virtual_inventory_zhbbr',
    'zsbbr': 'virtual_inventory_zsbbr',
    'dgby': 'virtual_inventory_dgby',
    'dghf': 'virtual_inventory_dghf'
}


def get_current_virtual_inventory_context():
    company = session.get('current_org') or session.get('store') or 'fsbbr'
    table_name = VIRTUAL_INVENTORY_TABLE_MAP.get(company, 'virtual_inventory')
    supplier_column = 'supplier_name' if company == 'fsbbr' else 'upload_supplier_name'
    return company, table_name, supplier_column

#连接数据库以及表格功能实现========================================================================================
def login_required(f):
    """登录验证装饰器 - 与主应用一致"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_update_status(update_msg):
    """
    根据 update_msg 内容判断更新状态
    返回: 'success', 'failed', 'new_success', 'new_failed', 'empty'
    """
    if not update_msg:
        return 'empty'

    msg_lower = update_msg.lower()

    # 上传成功：包含 update
    if 'update' in msg_lower:
        return 'success'

    # 新建成功
    if 'oe号【' in update_msg and '】处理结果：成功' in update_msg:
        return 'new_success'

    # 新建失败
    if 'oe号【' in update_msg and '】处理结果：失败' in update_msg:
        return 'new_failed'

    # 其他都归类为失败
    return 'failed'

def refresh_update_status():
    """
    刷新所有记录的 update_status 字段
    用于初始化或数据迁移后更新状态
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("开始刷新 update_status 字段...")

        # 分批更新，避免一次性更新太多数据
        batch_size = 5000
        offset = 0
        total_updated = 0

        while True:
            # 获取一批需要更新的记录
            cursor.execute("""
                SELECT id, update_msg FROM virtual_inventory
                WHERE update_status IS NULL
                LIMIT %s OFFSET %s
            """, (batch_size, offset))

            rows = cursor.fetchall()
            if not rows:
                break

            # 更新这批记录
            for row in rows:
                status = get_update_status(row[1])
                cursor.execute("""
                    UPDATE virtual_inventory
                    SET update_status = %s
                    WHERE id = %s
                """, (status, row[0]))

            conn.commit()
            total_updated += len(rows)
            print(f"已更新 {total_updated} 条记录的 update_status")

            if len(rows) < batch_size:
                break

            offset += batch_size

        print(f"update_status 刷新完成，共更新 {total_updated} 条记录")

    except Exception as e:
        print(f"刷新 update_status 失败: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@virtual_inventory_bp.route('/virtual_inventory')
@login_required
def virtual_inventory_page():
    """虚拟库存管理页面"""
    return render_template('virtual_inventory.html')

@virtual_inventory_bp.route('/api/virtual_inventory')
@login_required
def get_virtual_inventory():
    """获取虚拟库存数据"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit

        # 获取排序参数
        field = request.args.get('field', '').strip() or None
        order = request.args.get('order', '').strip() or None

        # 获取搜索条件
        supplier_name = request.args.get('supplier_name', '').strip()
        oe_code = request.args.get('oe_code', '').strip()
        brand = request.args.get('brand', '').strip()
        warehouse = request.args.get('warehouse', '').strip()
        remark = request.args.get('remark', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 构建查询条件
        where_conditions = ["1=1"]
        params = []

        if supplier_name:
            where_conditions.append("`supplier_name` LIKE %s")
            params.append(f"%{supplier_name}%")
        
        if oe_code:
            where_conditions.append("`oe_code` LIKE %s")
            params.append(f"%{oe_code}%")
            
        if brand:
            where_conditions.append("`brand` LIKE %s")
            params.append(f"%{brand}%")
        
        if warehouse:
            where_conditions.append("`warehouse` LIKE %s")
            params.append(f"%{warehouse}%")
        
        if remark:
            where_conditions.append("`remark` LIKE %s")
            params.append(f"%{remark}%")

        where_clause = " AND ".join(where_conditions)

        # 获取总记录数
        count_sql = f"SELECT COUNT(*) AS total FROM virtual_inventory WHERE {where_clause}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        # 构建排序子句
        order_clause = ""
        if field and order:
            # 字段映射，确保安全
            field_mapping = {
                'supplier_name': '`supplier_name`',
                'oe_code': '`oe_code`',
                'brand': '`brand`',
                'price': '`price`',
                'expiry_date': '`expiry_date`',
                'warehouse': '`warehouse`',
                'stock': '`stock`',
                'remark': '`remark`',
                'fetch_time': '`fetch_time`',
                'update_msg': '`update_msg`'
            }
            
            if field in field_mapping:
                order_direction = "ASC" if order.lower() == "asc" else "DESC"
                # 对于价格和库存，使用数值型排序
                if field in ['price', 'stock']:
                    order_clause = f"ORDER BY {field_mapping[field]}+0 {order_direction}"
                else:
                    order_clause = f"ORDER BY {field_mapping[field]} {order_direction}"
            else:
                order_clause = "ORDER BY `id` DESC"
        else:
            order_clause = "ORDER BY `id` DESC"

        # 查询数据
        sql = f"""
            SELECT `supplier_name`, `oe_code`, `brand`, `price`, `expiry_date`, `warehouse`, `stock`, `remark`, 
                   `fetch_time`, `update_msg`
            FROM virtual_inventory 
            WHERE {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # 格式化时间字段
        for row in rows:
            if row['fetch_time']:
                # 将fetch_time转换为字符串格式
                if hasattr(row['fetch_time'], 'strftime'):
                    row['fetch_time'] = row['fetch_time'].strftime('%Y-%m-%d %H:%M:%S')
            if row['expiry_date']:
                # 将expiry_date转换为字符串格式
                if hasattr(row['expiry_date'], 'strftime'):
                    row['expiry_date'] = row['expiry_date'].strftime('%Y-%m-%d %H:%M:%S')

        conn.close()

        return jsonify({
            'code': 0,
            'msg': '',
            'count': total,
            'data': rows
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取数据失败: {str(e)}'}), 500
    
@virtual_inventory_bp.route('/api/virtual_inventory_search', methods=['GET'])
@login_required
def get_virtual_inventory_search():
    """获取虚拟库存数据 - 包含搜索和排序功能的统一接口"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit

        # 获取排序参数
        field = request.args.get('field', '').strip() or None
        order = request.args.get('order', '').strip() or None

        # 获取搜索条件
        supplier_name = request.args.get('supplier_name', '').strip()
        oe_code = request.args.get('oe_code', '').strip()
        brand = request.args.get('brand', '').strip()
        warehouse = request.args.get('warehouse', '').strip()
        remark = request.args.get('remark', '').strip()
        pattern = request.args.get('pattern', '').strip()  # 更新信息模式筛选

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 构建查询条件
        where_conditions = ["1=1"]
        params = []

        # 根据模式筛选数据
        if pattern:
            if pattern == "品牌名称[任意文本]总部不存在,请核查数据":
                # 匹配 "品牌名称[任意内容]总部不存在,请核查数据" 格式
                where_conditions.append("`update_msg` LIKE %s")
                params.append("%品牌名称%总部不存在%请核查数据%")
            elif pattern == "过期时间[任意文本]不能小于当前时间":
                # 匹配 "过期时间[任意内容]不能小于当前时间" 格式
                where_conditions.append("`update_msg` LIKE %s")
                params.append("%过期时间%不能小于当前时间%")
            elif pattern == "物料所属品牌[任意文本]OE号[任意文本]产品数据不存在,请核查数据":
                # 匹配 "物料所属品牌[任意内容]OE号[任意内容]产品数据不存在,请核查数据" 格式
                where_conditions.append("`update_msg` LIKE %s")
                params.append("%物料所属品牌%OE号%产品数据不存在%请核查数据%")
            elif pattern == "更新成功":
                # 匹配包含"update"的更新成功信息
                where_conditions.append("LOWER(`update_msg`) LIKE %s")
                params.append("%update%")
            elif pattern == "空值":
                # 筛选更新信息为空的数据
                where_conditions.append("(`update_msg` IS NULL OR `update_msg` = '')")
            elif pattern == "其它":
                # 筛选不属于以上任何分类的数据（且不是空值）
                where_conditions.append("(`update_msg` IS NOT NULL AND `update_msg` != '' AND `update_msg` NOT LIKE %s AND `update_msg` NOT LIKE %s AND `update_msg` NOT LIKE %s AND LOWER(`update_msg`) NOT LIKE %s)")
                params.extend(["%品牌名称%总部不存在%请核查数据%", "%过期时间%不能小于当前时间%", "%物料所属品牌%OE号%产品数据不存在%请核查数据%", "%update%"])
            else:
                # 如果是其他具体值，直接匹配
                where_conditions.append("`update_msg` = %s")
                params.append(pattern)

        # 添加其他搜索条件
        if supplier_name:
            where_conditions.append("`supplier_name` LIKE %s")
            params.append(f"%{supplier_name}%")
        
        if oe_code:
            where_conditions.append("`oe_code` LIKE %s")
            params.append(f"%{oe_code}%")
            
        if brand:
            where_conditions.append("`brand` LIKE %s")
            params.append(f"%{brand}%")
        
        if warehouse:
            where_conditions.append("`warehouse` LIKE %s")
            params.append(f"%{warehouse}%")
        
        if remark:
            where_conditions.append("`remark` LIKE %s")
            params.append(f"%{remark}%")

        where_clause = " AND ".join(where_conditions)

        # 获取总记录数
        count_start = time.time()
        count_sql = f"SELECT COUNT(*) AS total FROM virtual_inventory WHERE {where_clause}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']
        log_time_cost("查询总记录数", count_start)

        # 构建排序子句
        order_clause = ""
        if field and order:
            # 字段映射，确保安全
            field_mapping = {
                'supplier_name': '`supplier_name`',
                'oe_code': '`oe_code`',
                'brand': '`brand`',
                'price': '`price`',
                'expiry_date': '`expiry_date`',
                'warehouse': '`warehouse`',
                'stock': '`stock`',
                'remark': '`remark`',
                'fetch_time': '`fetch_time`',
                'update_msg': '`update_msg`'
            }

            if field in field_mapping:
                order_direction = "ASC" if order.lower() == "asc" else "DESC"
                # 对于价格和库存，使用数值型排序
                if field in ['price', 'stock']:
                    order_clause = f"ORDER BY {field_mapping[field]}+0 {order_direction}"
                else:
                    order_clause = f"ORDER BY {field_mapping[field]} {order_direction}"
            else:
                order_clause = "ORDER BY `fetch_time` DESC"  # 使用fetch_time作为默认排序
        else:
            order_clause = "ORDER BY `fetch_time` DESC"  # 使用fetch_time作为默认排序

        # 查询数据
        query_start = time.time()
        sql = f"""
            SELECT `supplier_name`, `oe_code`, `brand`, `price`, `expiry_date`, `warehouse`, `stock`, `remark`,
                   `fetch_time`, `update_msg`
            FROM virtual_inventory
            WHERE {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        log_time_cost("查询分页数据", query_start)

        # 格式化时间字段
        format_start = time.time()
        for row in rows:
            if row['fetch_time']:
                # 将fetch_time转换为字符串格式
                if hasattr(row['fetch_time'], 'strftime'):
                    row['fetch_time'] = row['fetch_time'].strftime('%Y-%m-%d %H:%M:%S')
            if row['expiry_date']:
                # 将expiry_date转换为字符串格式
                if hasattr(row['expiry_date'], 'strftime'):
                    row['expiry_date'] = row['expiry_date'].strftime('%Y-%m-%d %H:%M:%S')
        log_time_cost("格式化时间字段", format_start)

        conn.close()

        return jsonify({
            'code': 0,
            'msg': '',
            'count': total,
            'data': rows
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取数据失败: {str(e)}'}), 500
    
#表格搜索框功能========================================================================================

# 更新信息下拉选项
@virtual_inventory_bp.route('/api/update_msg_options')
@login_required
def get_update_msg_options():
    """获取更新信息的选项列表（按格式分类）"""
    api_start_time = time.time()
    print(f"\n[⏱️ 后端计时] ========== API /api/update_msg_options 开始 ==========")
    try:
        db_connect_start = time.time()
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        log_time_cost("数据库连接", db_connect_start)

        # 查询所有唯一的更新信息，排除空值
        query_start = time.time()
        sql = """
            SELECT update_msg
            FROM virtual_inventory
            WHERE update_msg IS NOT NULL AND update_msg != ''
            ORDER BY update_msg
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        log_time_cost("查询更新信息", query_start)

        conn.close()

        # 提取更新信息文本并过滤空值
        update_msgs = [row['update_msg'] for row in rows if row['update_msg']]

        # 统计各分类
        brand_not_exist_count = 0
        expiry_time_invalid_count = 0
        product_not_exist_count = 0
        update_success_count = 0
        new_success_count = 0
        new_fail_count = 0
        
        # 定义预定义的分类
        categories = set()

        for msg in update_msgs:
            if ("品牌名称" in msg and "总部不存在" in msg and "请核查数据" in msg) or \
            ("过期时间" in msg and "不能小于当前时间" in msg) or \
            ("物料所属品牌" in msg and "OE号" in msg and "产品数据不存在,请核查数据" in msg) or \
            ("OE号【" in msg and "】处理结果：成功" in msg) or \
            ("OE号【" in msg and "】处理结果：失败" in msg):
                categories.add("上传失败")  # 合并为上传失败分类
            elif "update" in msg.lower():
                categories.add("上传成功")  # 改名为上传成功
            elif "OE号【" in msg and "】处理结果：成功" in msg:
                categories.add("新建成功")
            elif "OE号【" in msg and "】处理结果：失败" in msg:
                categories.add("新建失败")

        categories.add("上传失败")
        categories.add("上传成功")
        categories.add("新建成功")  # 保留单独的搜索选项
        categories.add("新建失败")  # 保留单独的搜索选项
        
        print(f"分类统计:")
        print(f"品牌名称[任意文本]总部不存在,请核查数据: {brand_not_exist_count} 条")
        print(f"过期时间[任意文本]不能小于当前时间: {expiry_time_invalid_count} 条")
        print(f"物料所属品牌[任意文本]OE号[任意文本]产品数据不存在,请核查数据: {product_not_exist_count} 条")
        print(f"更新成功: {update_success_count} 条")
        print(f"新建成功: {new_success_count} 条")
        print(f"新建失败: {new_fail_count} 条")
        print(f"总计非空更新信息: {len(update_msgs)} 条")

        total_cost = log_time_cost("API 总耗时", api_start_time)
        print(f"[⏱️ 后端计时] ========== API /api/update_msg_options 完成，总耗时: {total_cost:.2f}ms ==========\n")

        return jsonify({
            'code': 0,
            'msg': '',
            'data': list(categories)
        })

    except Exception as e:
        total_cost = log_time_cost("API 总耗时(异常)", api_start_time)
        print(f"[⏱️ 后端计时] ========== API /api/update_msg_options 异常结束，总耗时: {total_cost:.2f}ms ==========\n")
        return jsonify({'code': 1, 'msg': f'获取更新信息选项失败: {str(e)}'}), 500


@virtual_inventory_bp.route('/api/virtual_inventory_statistics')
@login_required
def get_virtual_inventory_statistics():
    """获取虚拟库存统计信息 - 始终基于当前业务日期范围"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 获取当前业务日期范围
        start_time, end_time = get_business_date_range()

        # 总记录数 - 限制为当前业务日期范围
        total_sql = "SELECT COUNT(*) as count FROM virtual_inventory WHERE fetch_time >= %s AND fetch_time < %s"
        cursor.execute(total_sql, (start_time, end_time))
        total_count = cursor.fetchone()['count']
        print(f"当前业务日期范围总记录数: {total_count}")

        # 成功上传：包含"update"的数据 - 限制为当前业务日期范围
        success_sql = "SELECT COUNT(*) as count FROM virtual_inventory WHERE LOWER(update_msg) LIKE %s AND fetch_time >= %s AND fetch_time < %s"
        cursor.execute(success_sql, ("%update%", start_time, end_time))
        success_count = cursor.fetchone()['count']
        print(f"当前业务日期范围成功上传数 (update): {success_count}")
        
        # 新建成功：包含"OE号【"和"】处理结果：成功" - 限制为当前业务日期范围
        new_success_sql = """
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE update_msg LIKE %s AND update_msg LIKE %s AND fetch_time >= %s AND fetch_time < %s
        """
        cursor.execute(new_success_sql, ["%OE号【%", "%】处理结果：成功%", start_time, end_time])
        new_success_count = cursor.fetchone()['count']
        print(f"当前业务日期范围新建成功数: {new_success_count}")
        
        # 新建失败：包含"OE号【"和"】处理结果：失败" - 限制为当前业务日期范围
        new_fail_sql = """
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE update_msg LIKE %s AND update_msg LIKE %s AND fetch_time >= %s AND fetch_time < %s
        """
        cursor.execute(new_fail_sql, ["%OE号【%", "%】处理结果：失败%", start_time, end_time])
        new_fail_count = cursor.fetchone()['count']
        print(f"当前业务日期范围新建失败数: {new_fail_count}")
        
        # 品牌名称总部不存在 - 限制为当前业务日期范围
        brand_not_exist_sql = """
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE update_msg LIKE %s AND fetch_time >= %s AND fetch_time < %s
        """
        cursor.execute(brand_not_exist_sql, ["%品牌名称%总部不存在%请核查数据%", start_time, end_time])
        brand_not_exist_count = cursor.fetchone()['count']
        print(f"当前业务日期范围品牌名称总部不存在数: {brand_not_exist_count}")
        
        # 物料所属品牌OE号不存在 - 限制为当前业务日期范围
        product_not_exist_sql = """
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE update_msg LIKE %s AND fetch_time >= %s AND fetch_time < %s
        """
        cursor.execute(product_not_exist_sql, ["%物料所属品牌%OE号%产品数据不存在%请核查数据%", start_time, end_time])
        product_not_exist_count = cursor.fetchone()['count']
        print(f"当前业务日期范围物料所属品牌OE号不存在数: {product_not_exist_count}")
        
        # 失败：总记录数 - 成功上传
        failed_count = total_count - success_count
        print(f"当前业务日期范围失败数: {failed_count}")
        
        # 没有档案：新建失败 + 新建成功 + 品牌名称总部不存在 + 物料所属品牌OE号不存在
        no_record_count = new_success_count + new_fail_count + brand_not_exist_count + product_not_exist_count
        print(f"当前业务日期范围没有档案数: {no_record_count}")
        
        # 新建档案：新建成功
        new_archive_count = new_success_count
        print(f"当前业务日期范围新建档案数: {new_archive_count}")

        conn.close()

        result = {
            'code': 0,
            'msg': '',
            'data': {
                'success_count': success_count,
                'failed_count': failed_count,
                'no_record_count': no_record_count,
                'new_archive_count': new_archive_count
            }
        }
        print(f"当前业务日期范围统计返回结果: {result}")
        
        return jsonify(result)

    except Exception as e:
        print(f"获取当前业务日期范围统计数据失败: {str(e)}")
        return jsonify({'code': 1, 'msg': f'获取统计数据失败: {str(e)}'}), 500

@virtual_inventory_bp.route('/api/virtual_inventory_by_msg_pattern')
@login_required
def get_virtual_inventory_by_msg_pattern():
    """根据更新信息模式获取虚拟库存数据 - 遵循用户选择的日期范围"""
    api_start_time = time.time()
    print(f"\n[⏱️ 后端计时] ========== API /api/virtual_inventory_by_msg_pattern 开始 ==========")
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit
        pattern = request.args.get('pattern', '').strip()

        # 获取排序参数
        field = request.args.get('field', '').strip() or None
        order = request.args.get('order', '').strip() or None

        # 获取搜索条件
        supplier_name = request.args.get('supplier_name', '').strip()
        oe_code = request.args.get('oe_code', '').strip()
        brand = request.args.get('brand', '').strip()
        warehouse = request.args.get('warehouse', '').strip()
        remark = request.args.get('remark', '').strip()

        # 获取日期范围参数
        start_date_str = request.args.get('start_date', '').strip()
        end_date_str = request.args.get('end_date', '').strip()

        company, table_name, supplier_column = get_current_virtual_inventory_context()

        db_connect_start = time.time()
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        log_time_cost("数据库连接", db_connect_start)

        # 构建查询条件
        where_conditions = ["1=1"]
        params = []

        # 根据日期范围参数添加时间条件
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                start_time = datetime.combine(start_date, datetime.min.time())
                end_time = datetime.combine(end_date, datetime.max.time().replace(microsecond=0))
                where_conditions.append("fetch_time >= %s AND fetch_time <= %s")
                params.extend([start_time, end_time])
            except ValueError:
                return jsonify({'code': 1, 'msg': '日期格式错误，请使用 YYYY-MM-DD 格式'}), 400

        # 根据模式筛选数据 - 使用 update_status 字段（支持8种中文状态）
        if pattern:
            # 8种精确匹配的状态
            exact_statuses = [
                '上传成功', '新建成功-已存在', '新建成功-新创建',
                '新建失败-未找到产品名称', '新建失败-车型不能为空',
                '上传失败-过期时间错误', '上传失败-品牌不存在', '上传失败-产品不存在',
                '其他'
            ]
            
            if pattern in exact_statuses:
                # 精确匹配单种状态
                where_conditions.append("update_status = %s")
                params.append(pattern)
            elif pattern == "上传失败":
                # 上传失败：除上传成功以外的所有
                where_conditions.append("(update_status != '上传成功' OR update_status IS NULL)")
            elif pattern == "新建成功":
                # 新建成功：包含两种成功状态
                where_conditions.append("update_status IN ('新建成功-已存在', '新建成功-新创建')")
            elif pattern == "新建失败":
                # 新建失败：包含三种失败状态
                where_conditions.append("update_status IN ('新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')")
            elif pattern == "没有档案":
                # 没有档案：包含五种状态
                where_conditions.append("update_status IN ('新建成功-已存在', '新建成功-新创建', '新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')")

        # 无论是否有pattern，都要添加其他搜索条件
        if supplier_name:
            where_conditions.append(f"`{supplier_column}` LIKE %s")
            params.append(f"%{supplier_name}%")
        
        if oe_code:
            where_conditions.append("`oe_code` LIKE %s")
            params.append(f"%{oe_code}%")
            
        if brand:
            where_conditions.append("`brand` LIKE %s")
            params.append(f"%{brand}%")
        
        if warehouse:
            where_conditions.append("`warehouse` LIKE %s")
            params.append(f"%{warehouse}%")
        
        if remark:
            where_conditions.append("`remark` LIKE %s")
            params.append(f"%{remark}%")

        where_clause = " AND ".join(where_conditions)

        # 获取总记录数
        count_sql = f"SELECT COUNT(*) AS total FROM {table_name} WHERE {where_clause}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        # 构建排序子句
        order_clause = ""
        if field and order:
            # 字段映射，确保安全
            field_mapping = {
                'supplier_name': f'`{supplier_column}`',
                'oe_code': '`oe_code`',
                'brand': '`brand`',
                'price': '`price`',
                'expiry_date': '`expiry_date`',
                'warehouse': '`warehouse`',
                'stock': '`stock`',
                'remark': '`remark`',
                'fetch_time': '`fetch_time`',
                'update_msg': '`update_msg`'
            }
            
            if field in field_mapping:
                order_direction = "ASC" if order.lower() == "asc" else "DESC"
                # 对于价格和库存，使用数值型排序
                if field in ['price', 'stock']:
                    order_clause = f"ORDER BY {field_mapping[field]}+0 {order_direction}"
                else:
                    order_clause = f"ORDER BY {field_mapping[field]} {order_direction}"
            else:
                order_clause = "ORDER BY `fetch_time` DESC"  # 使用fetch_time作为默认排序
        else:
            order_clause = "ORDER BY `fetch_time` DESC"  # 使用fetch_time作为默认排序

        # 查询数据
        sql = f"""
            SELECT `{supplier_column}` AS supplier_name, `oe_code`, `brand`, `price`, `expiry_date`, `warehouse`, `stock`, `remark`, 
                   `fetch_time`, `update_msg`
            FROM {table_name}
            WHERE {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """      
        params.extend([limit, offset])
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # 格式化时间字段
        for row in rows:
            if row['fetch_time']:
                # 将fetch_time转换为字符串格式
                if hasattr(row['fetch_time'], 'strftime'):
                    row['fetch_time'] = row['fetch_time'].strftime('%Y-%m-%d %H:%M:%S')
            if row['expiry_date']:
                # 将expiry_date转换为字符串格式
                if hasattr(row['expiry_date'], 'strftime'):
                    row['expiry_date'] = row['expiry_date'].strftime('%Y-%m-%d %H:%M:%S')

        # 使用 update_status 字段进行统计，避免 LIKE 查询
        stats_start = time.time()

        # 使用索引字段统计成功数量
        simple_success_sql = f"""
            SELECT COUNT(*) as count FROM {table_name}
            WHERE update_status = 'success' AND {where_clause}
        """
        cursor.execute(simple_success_sql, params[:-2])
        success_count = cursor.fetchone()['count']

        # 失败数量 = 总数 - 成功数
        failed_count = total - success_count
        no_record_count = failed_count
        new_archive_count = 0

        log_time_cost("统计查询(使用update_status索引)", stats_start)

        conn.close()

        total_cost = log_time_cost("API 总耗时", api_start_time)
        print(f"[⏱️ 后端计时] ========== API /api/virtual_inventory_by_msg_pattern 完成，总耗时: {total_cost:.2f}ms ==========\n")

        return jsonify({
            'code': 0,
            'msg': '',
            'count': total,
            'data': rows,
            'statistics': {
                'success_count': success_count,
                'failed_count': failed_count,
            }
        })

    except Exception as e:
        total_cost = log_time_cost("API 总耗时(异常)", api_start_time)
        print(f"[⏱️ 后端计时] ========== API /api/virtual_inventory_by_msg_pattern 异常结束，总耗时: {total_cost:.2f}ms ==========\n")
        return jsonify({'code': 1, 'msg': f'获取数据失败: {str(e)}'}), 500

@virtual_inventory_bp.route('/api/virtual_inventory_statistics_by_pattern', methods=['GET'])
@login_required
def get_virtual_inventory_statistics_by_pattern():
    """根据筛选条件获取统计信息 - 异步加载专用接口"""
    api_start_time = time.time()
    print(f"\n[⏱️ 后端计时] ========== API /api/virtual_inventory_statistics_by_pattern 开始 ==========")
    try:
        pattern = request.args.get('pattern', '').strip()
        business_date_type = request.args.get('business_date_type', '').strip()

        db_connect_start = time.time()
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        log_time_cost("数据库连接", db_connect_start)

        # 构建查询条件
        where_conditions = ["1=1"]
        params = []

        # 根据业务日期范围参数添加时间条件
        if business_date_type == 'today':
            start_time, end_time = get_business_date_range()
            where_conditions.append("fetch_time >= %s AND fetch_time < %s")
            params.extend([start_time, end_time])

        # 根据模式筛选数据 - 使用 update_status 字段优化查询（支持8种中文状态）
        if pattern:
            # 8种精确匹配的状态
            exact_statuses = [
                '上传成功', '新建成功-已存在', '新建成功-新创建',
                '新建失败-未找到产品名称', '新建失败-车型不能为空',
                '上传失败-过期时间错误', '上传失败-品牌不存在', '上传失败-产品不存在',
                '其他'
            ]
            
            if pattern in exact_statuses:
                # 精确匹配单种状态
                where_conditions.append("update_status = %s")
                params.append(pattern)
            elif pattern == "上传失败":
                # 上传失败：除上传成功以外的所有
                where_conditions.append("(update_status != '上传成功' OR update_status IS NULL)")
            elif pattern == "新建成功":
                # 新建成功：包含两种成功状态
                where_conditions.append("update_status IN ('新建成功-已存在', '新建成功-新创建')")
            elif pattern == "新建失败":
                # 新建失败：包含三种失败状态
                where_conditions.append("update_status IN ('新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')")
            elif pattern == "没有档案":
                # 没有档案：包含五种状态
                where_conditions.append("update_status IN ('新建成功-已存在', '新建成功-新创建', '新建失败-未找到产品名称', '新建失败-车型不能为空', '上传失败-产品不存在')")

        where_clause = " AND ".join(where_conditions)

        # 获取总记录数 - 使用索引优化
        query_start = time.time()
        count_sql = f"SELECT COUNT(*) AS total FROM virtual_inventory WHERE {where_clause}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        # 统计成功数量 - 使用 update_status 字段，避免 LIKE
        success_sql = f"SELECT COUNT(*) as count FROM virtual_inventory WHERE update_status = 'success' AND {where_clause}"
        cursor.execute(success_sql, params)
        success_count = cursor.fetchone()['count']
        log_time_cost("统计查询(使用update_status索引)", query_start)

        failed_count = total - success_count

        conn.close()

        total_cost = log_time_cost("API 总耗时", api_start_time)
        print(f"[⏱️ 后端计时] ========== API /api/virtual_inventory_statistics_by_pattern 完成，总耗时: {total_cost:.2f}ms ==========\n")

        return jsonify({
            'code': 0,
            'msg': '',
            'data': {
                'total_count': total,
                'success_count': success_count,
                'failed_count': failed_count,
                'no_record_count': failed_count,
                'new_archive_count': 0
            }
        })

    except Exception as e:
        total_cost = log_time_cost("API 总耗时(异常)", api_start_time)
        print(f"[⏱️ 后端计时] ========== API /api/virtual_inventory_statistics_by_pattern 异常结束，总耗时: {total_cost:.2f}ms ==========\n")
        return jsonify({'code': 1, 'msg': f'获取统计数据失败: {str(e)}'}), 500

@virtual_inventory_bp.route('/api/supplier_summary')
@login_required
def get_supplier_summary():
    """获取各供应商上传成功和失败统计 - 基于用户选择的日期范围"""
    api_start_time = time.time()
    print(f"\n[⏱️ 后端计时] ========== API /api/supplier_summary 开始 ==========")
    try:
        # 获取日期范围参数
        start_date_str = request.args.get('start_date', '').strip()
        end_date_str = request.args.get('end_date', '').strip()

        company, table_name, supplier_column = get_current_virtual_inventory_context()

        db_connect_start = time.time()
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        log_time_cost("数据库连接", db_connect_start)

        # 构建查询条件和参数
        where_conditions = [f"`{supplier_column}` IS NOT NULL AND `{supplier_column}` != ''"]
        params = []

        # 根据日期范围参数添加时间条件
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                start_time = datetime.combine(start_date, datetime.min.time())
                end_time = datetime.combine(end_date, datetime.max.time().replace(microsecond=0))
                where_conditions.append("fetch_time >= %s AND fetch_time <= %s")
                params.extend([start_time, end_time])
            except ValueError:
                return jsonify({'code': 1, 'msg': '日期格式错误，请使用 YYYY-MM-DD 格式'}), 400

        where_clause = " AND ".join(where_conditions)

        # 查询每个供应商的上传成功和失败统计
        query_start = time.time()
        sql = f"""
            SELECT
                `{supplier_column}` AS supplier_name,
                COUNT(*) as total_count,
                SUM(CASE WHEN LOWER(update_msg) LIKE %s THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN LOWER(update_msg) NOT LIKE %s OR update_msg IS NULL OR update_msg = '' THEN 1 ELSE 0 END) as failed_count
            FROM {table_name}
            WHERE {where_clause}
            GROUP BY `{supplier_column}`
            ORDER BY `{supplier_column}`
        """
        cursor.execute(sql, ["%update%", "%update%"] + params)
        rows = cursor.fetchall()
        log_time_cost("供应商汇总查询", query_start)

        conn.close()

        total_cost = log_time_cost("API 总耗时", api_start_time)
        print(f"[⏱️ 后端计时] ========== API /api/supplier_summary 完成，总耗时: {total_cost:.2f}ms ==========\n")

        return jsonify({
            'code': 0,
            'msg': '',
            'company': company,
            'data': rows
        })

    except Exception as e:
        total_cost = log_time_cost("API 总耗时(异常)", api_start_time)
        print(f"[⏱️ 后端计时] ========== API /api/supplier_summary 异常结束，总耗时: {total_cost:.2f}ms ==========\n")
        return jsonify({'code': 1, 'msg': f'获取供应商汇总失败: {str(e)}'}), 500

@virtual_inventory_bp.route('/api/admin/refresh_update_status', methods=['POST'])
@login_required
def admin_refresh_update_status():
    """管理接口：刷新所有记录的 update_status 字段"""
    try:
        # 检查是否是管理员（这里简单判断，你可以根据实际需求修改）
        if session.get('username') != 'admin':
            return jsonify({'code': 1, 'msg': '只有管理员才能执行此操作'}), 403

        result = refresh_update_status_sync()
        return jsonify(result)

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'刷新失败: {str(e)}'}), 500

def refresh_update_status_sync():
    """
    同步刷新所有记录的 update_status 字段
    返回刷新结果统计
    """
    start_time = time.time()
    result = {
        'code': 0,
        'msg': '',
        'total_updated': 0,
        'details': {
            'success': 0,
            'failed': 0,
            'new_success': 0,
            'new_failed': 0,
            'empty': 0
        }
    }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("[管理后台] 开始刷新 update_status 字段...")

        # 分批更新，避免一次性更新太多数据
        batch_size = 5000
        offset = 0

        while True:
            # 获取一批需要更新的记录
            cursor.execute("""
                SELECT id, update_msg FROM virtual_inventory
                WHERE update_status IS NULL
                LIMIT %s OFFSET %s
            """, (batch_size, offset))

            rows = cursor.fetchall()
            if not rows:
                break

            # 更新这批记录
            for row in rows:
                status = get_update_status(row[1])
                cursor.execute("""
                    UPDATE virtual_inventory
                    SET update_status = %s
                    WHERE id = %s
                """, (status, row[0]))

                result['details'][status] += 1

            conn.commit()
            result['total_updated'] += len(rows)
            print(f"[管理后台] 已更新 {result['total_updated']} 条记录")

            if len(rows) < batch_size:
                break

            offset += batch_size

        cost_time = (time.time() - start_time) * 1000
        result['msg'] = f"刷新完成，共更新 {result['total_updated']} 条记录，耗时 {cost_time:.2f}ms"
        print(f"[管理后台] {result['msg']}")

    except Exception as e:
        result['code'] = 1
        result['msg'] = f"刷新失败: {str(e)}"
        print(f"[管理后台] 刷新 update_status 失败: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

    return result

@virtual_inventory_bp.route('/api/admin/check_update_status', methods=['GET'])
@login_required
def admin_check_update_status():
    """管理接口：检查 update_status 字段的统计情况"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 统计各种状态的数量
        cursor.execute("""
            SELECT
                update_status,
                COUNT(*) as count
            FROM virtual_inventory
            GROUP BY update_status
        """)
        rows = cursor.fetchall()

        # 统计为空的记录数
        cursor.execute("""
            SELECT COUNT(*) as count FROM virtual_inventory
            WHERE update_status IS NULL
        """)
        null_count = cursor.fetchone()['count']

        conn.close()

        # 整理结果
        status_stats = {row['update_status'] or 'NULL': row['count'] for row in rows}
        status_stats['未分类(NULL)'] = null_count

        return jsonify({
            'code': 0,
            'msg': '查询成功',
            'data': status_stats
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询失败: {str(e)}'}), 500

# ==================== 黑名单管理 API ====================

@virtual_inventory_bp.route('/api/blacklist', methods=['GET'])
@login_required
def get_blacklist_api():
    """获取黑名单列表"""
    try:
        from app.utils.inventory_tasks import get_blacklist
        blacklist = get_blacklist()
        return jsonify({
            'code': 0,
            'msg': '',
            'count': len(blacklist),
            'data': blacklist
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取黑名单失败: {str(e)}'}), 500


@virtual_inventory_bp.route('/api/blacklist', methods=['POST'])
@login_required
def add_blacklist_api():
    """添加黑名单记录"""
    try:
        data = request.get_json()
        supplier_name = data.get('supplier_name', '').strip()
        oe_code = data.get('oe_code', '').strip()
        brand = data.get('brand', '').strip()
        
        if not all([supplier_name, oe_code, brand]):
            return jsonify({'code': 1, 'msg': '供应商名称、OE码和品牌不能为空'}), 400
        
        from app.utils.inventory_tasks import add_to_blacklist, refresh_blacklist_cache
        result = add_to_blacklist(supplier_name, oe_code, brand)
        
        # 添加成功后刷新缓存
        if result['success']:
            refresh_blacklist_cache()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'添加黑名单失败: {str(e)}'}), 500


@virtual_inventory_bp.route('/api/blacklist', methods=['DELETE'])
@login_required
def delete_blacklist_api():
    """删除黑名单记录"""
    try:
        data = request.get_json()
        supplier_name = data.get('supplier_name', '').strip()
        oe_code = data.get('oe_code', '').strip()
        brand = data.get('brand', '').strip()
        
        if not all([supplier_name, oe_code, brand]):
            return jsonify({'code': 1, 'msg': '供应商名称、OE码和品牌不能为空'}), 400
        
        from app.utils.inventory_tasks import remove_from_blacklist, refresh_blacklist_cache
        result = remove_from_blacklist(supplier_name, oe_code, brand)
        
        # 删除成功后刷新缓存
        if result['success']:
            refresh_blacklist_cache()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'删除黑名单失败: {str(e)}'}), 500


@virtual_inventory_bp.route('/api/blacklist/batch', methods=['POST'])
@login_required
def batch_add_blacklist_api():
    """批量添加黑名单记录"""
    try:
        data = request.get_json()
        records = data.get('records', [])
        
        if not records:
            return jsonify({'code': 1, 'msg': '没有需要添加的记录'}), 400
        
        # 转换为元组列表
        tuple_records = [(r['supplier_name'], r['oe_code'], r['brand']) for r in records]
        
        from app.utils.inventory_tasks import batch_add_to_blacklist, refresh_blacklist_cache
        result = batch_add_to_blacklist(tuple_records)
        
        # 添加成功后刷新缓存
        if result['success']:
            refresh_blacklist_cache()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'批量添加黑名单失败: {str(e)}'}), 500


@virtual_inventory_bp.route('/api/blacklist/clear', methods=['POST'])
@login_required
def clear_blacklist_api():
    """清空所有黑名单记录"""
    try:
        from app.utils.inventory_tasks import clear_blacklist, refresh_blacklist_cache
        result = clear_blacklist()
        
        # 清空成功后刷新缓存
        if result['success']:
            refresh_blacklist_cache()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'清空黑名单失败: {str(e)}'}), 500


@virtual_inventory_bp.route('/api/blacklist/stats', methods=['GET'])
@login_required
def get_blacklist_stats_api():
    """获取黑名单统计信息"""
    try:
        from app.utils.inventory_tasks import get_filter_stats
        stats = get_filter_stats()
        return jsonify({
            'code': 0,
            'msg': '',
            'data': stats
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取统计信息失败: {str(e)}'}), 500


@virtual_inventory_bp.route('/api/virtual_inventory/trigger_task', methods=['POST'])
@login_required
def trigger_virtual_inventory_task():
    """手动触发虚拟库存任务"""
    try:
        import threading
        from app.utils.virtual_inventory import main_process

        def run_task():
            """在后台线程中运行任务"""
            try:
                print("=" * 60)
                print("手动触发虚拟库存任务开始")
                print("=" * 60)
                main_process()
                print("=" * 60)
                print("手动触发虚拟库存任务完成")
                print("=" * 60)
            except Exception as e:
                print(f"虚拟库存任务执行失败: {e}")
                import traceback
                traceback.print_exc()

        # 在后台线程中运行任务，避免阻塞请求
        thread = threading.Thread(target=run_task)
        thread.daemon = True
        thread.start()

        return jsonify({
            'code': 0,
            'msg': '虚拟库存任务已启动，请在后台查看执行结果'
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'启动失败: {str(e)}'
        }), 500


# ==================== 统计日志API ====================

@virtual_inventory_bp.route('/api/virtual_inventory_stats_log', methods=['GET'])
@login_required
def get_stats_log_list():
    """获取统计日志列表（最近30天）"""
    try:
        from app.services.virtual_inventory_stats_service import get_stats_log_list as get_stats_list

        days = request.args.get('days', 30, type=int)
        rows = get_stats_list(days)

        return jsonify({
            'code': 0,
            'msg': '',
            'count': len(rows),
            'data': rows
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取统计日志失败: {str(e)}'}), 500


@virtual_inventory_bp.route('/api/virtual_inventory_stats_log/save', methods=['POST'])
@login_required
def manual_save_stats():
    """手动保存近三天统计数据"""
    try:
        from app.services.virtual_inventory_stats_service import save_recent_statistics

        results = save_recent_statistics(days=1)
        failed_results = [result for result in results if result['code'] != 0]
        if failed_results:
            return jsonify({'code': 1, 'msg': '部分统计数据保存失败', 'data': results})

        return jsonify({'code': 0, 'msg': '近三天统计数据保存成功', 'data': results})

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'保存失败: {str(e)}'}), 500


# 导入到主应用的函数============================================================================================
def register_virtual_inventory_routes(app):
    # 注册蓝图
    app.register_blueprint(virtual_inventory_bp)

    # 初始化黑名单表
    try:
        from app.utils.inventory_tasks import init_blacklist_table
        init_blacklist_table()
    except:
        pass