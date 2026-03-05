# beihuo_system/virtual_inventory_api.py
from flask import Blueprint, request, jsonify, session, render_template
import pymysql
from functools import wraps
import os
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection  # 使用统一的连接池实现

# 创建蓝图
virtual_inventory_bp = Blueprint('virtual_inventory', __name__)

#连接数据库以及表格功能实现========================================================================================
def login_required(f):
    """登录验证装饰器 - 与主应用一致"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

def init_virtual_inventory_table():
    """初始化虚拟库存表"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 创建虚拟库存表
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS virtual_inventory (
            id INT AUTO_INCREMENT PRIMARY KEY,
            supplier_name VARCHAR(100) COMMENT '供应商名称',
            oe_code VARCHAR(100) COMMENT 'OE码',
            brand VARCHAR(255) NOT NULL COMMENT '品牌',
            price DECIMAL(10,2) COMMENT '价格',
            expiry_date DATETIME COMMENT '过期时间',
            warehouse VARCHAR(255) COMMENT '仓库',
            stock INT DEFAULT 0 COMMENT '库存',
            remark TEXT COMMENT '备注',
            fetch_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '获取时间',
            update_msg TEXT COMMENT '更新信息',
            INDEX idx_brand (brand),
            INDEX idx_warehouse (warehouse),
            INDEX idx_expiry_date (expiry_date),
            INDEX idx_fetch_time (fetch_time),
            UNIQUE KEY uk_brand_warehouse (brand, warehouse)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='虚拟库存表';
        """
        cursor.execute(create_table_sql)
        conn.commit()
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_business_date(target_time):
    """
    获取业务日期
    业务日期定义：从当天下午13:00到第二天下午13:00为一个完整的业务日
    """
    if isinstance(target_time, str):
        target_time = datetime.strptime(target_time, '%Y-%m-%d %H:%M:%S')
    
    # 如果目标时间的小时数小于13，则属于前一天的业务日
    if target_time.hour < 13:
        business_date = target_time.date() - timedelta(days=1)
    else:
        # 如果目标时间的小时数大于等于13，则属于当天的业务日
        business_date = target_time.date()
        
    return business_date

def get_business_date_range(target_time=None):
    """
    获取业务日期的时间范围
    返回该业务日的开始时间和结束时间
    如果target_time为None，则使用当前时间
    """
    if target_time is None:
        target_time = datetime.now()
    
    if isinstance(target_time, str):
        target_time = datetime.strptime(target_time, '%Y-%m-%d %H:%M:%S')
    
    # 获取业务日期
    business_date = get_business_date(target_time)
    
    # 业务日开始时间：当天13:00:00
    start_time = datetime.combine(business_date, datetime.min.time().replace(hour=13))
    # 业务日结束时间：第二天13:00:00
    end_time = start_time + timedelta(days=1)
    
    return start_time, end_time

@virtual_inventory_bp.route('/virtual_inventory')
@login_required
def virtual_inventory_page():
    """虚拟库存管理页面"""
    # 确保表存在
    init_virtual_inventory_table()
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
                order_clause = "ORDER BY `fetch_time` DESC"  # 使用fetch_time作为默认排序
        else:
            order_clause = "ORDER BY `fetch_time` DESC"  # 使用fetch_time作为默认排序

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
    
#表格搜索框功能========================================================================================

# 更新信息下拉选项
@virtual_inventory_bp.route('/api/update_msg_options')
@login_required
def get_update_msg_options():
    """获取更新信息的选项列表（按格式分类）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 查询所有唯一的更新信息，排除空值
        sql = """
            SELECT update_msg 
            FROM virtual_inventory 
            WHERE update_msg IS NOT NULL AND update_msg != ''
            ORDER BY update_msg
        """
        cursor.execute(sql)
        rows = cursor.fetchall()

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

        return jsonify({
            'code': 0,
            'msg': '',
            'data': list(categories)
        })

    except Exception as e:
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
    """根据更新信息模式获取虚拟库存数据 - 遵循用户选择的业务日期范围"""
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

        # 获取业务日期范围参数
        business_date_type = request.args.get('business_date_type', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 构建查询条件
        where_conditions = ["1=1"]
        params = []

        # 根据业务日期范围参数添加时间条件
        if business_date_type == 'today':
            # 使用当前业务日期范围
            start_time, end_time = get_business_date_range()
            where_conditions.append("fetch_time >= %s AND fetch_time < %s")
            params.extend([start_time, end_time])

        # 根据模式筛选数据
        if pattern:
            if pattern == "上传失败":
                # 匹配所有上传失败的情况
                where_conditions.append("""
                    (`update_msg` LIKE %s OR `update_msg` LIKE %s OR `update_msg` LIKE %s OR 
                    `update_msg` LIKE %s OR `update_msg` LIKE %s OR
                    `update_msg` IS NULL OR `update_msg` = '' OR
                    (`update_msg` IS NOT NULL AND `update_msg` != '' AND 
                    `update_msg` NOT LIKE %s AND `update_msg` NOT LIKE %s AND 
                    `update_msg` NOT LIKE %s AND `update_msg` NOT LIKE %s AND 
                    `update_msg` NOT LIKE %s AND LOWER(`update_msg`) NOT LIKE %s))
                """)
                # 参数：品牌名称不存在 OR 过期时间无效 OR 产品不存在 OR 新建成功 OR 新建失败 OR 其它情况
                params.extend([
                    "%品牌名称%总部不存在%请核查数据%",  # 品牌名称总部不存在
                    "%过期时间%不能小于当前时间%",      # 过期时间不能小于当前时间
                    "%物料所属品牌%OE号%产品数据不存在%请核查数据%",  # 物料所属品牌OE号不存在
                    "%OE号【%】处理结果：成功%",         # 新建成功
                    "%OE号【%】处理结果：失败%",         # 新建失败
                    "%品牌名称%总部不存在%请核查数据%",  # 用于NOT LIKE
                    "%过期时间%不能小于当前时间%",      # 用于NOT LIKE
                    "%物料所属品牌%OE号%产品数据不存在%请核查数据%",  # 用于NOT LIKE
                    "%OE号【%】处理结果：成功%",         # 用于NOT LIKE
                    "%OE号【%】处理结果：失败%",         # 用于NOT LIKE
                    "%update%"  # 用于NOT LIKE
                ])
            elif pattern == "上传成功":
                # 匹配包含"update"的更新成功信息
                where_conditions.append("LOWER(`update_msg`) LIKE %s")
                params.append("%update%")
            elif pattern == "新建成功":
                # 匹配包含"OE号【"和"】处理结果：成功"的新建成功信息
                where_conditions.append("`update_msg` LIKE %s AND `update_msg` LIKE %s")
                params.extend(["%OE号【%", "%】处理结果：成功%"])
            elif pattern == "新建失败":
                # 匹配包含"OE号【"和"】处理结果：失败"的新建失败信息
                where_conditions.append("`update_msg` LIKE %s AND `update_msg` LIKE %s")
                params.extend(["%OE号【%", "%】处理结果：失败%"])

        # 无论是否有pattern，都要添加其他搜索条件
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
                order_clause = "ORDER BY `fetch_time` DESC"  # 使用fetch_time作为默认排序
        else:
            order_clause = "ORDER BY `fetch_time` DESC"  # 使用fetch_time作为默认排序

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

        # 分别统计各个类别 - 上传失败统计
        upload_failed_sql = f"""
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE (update_msg LIKE %s OR update_msg LIKE %s OR update_msg LIKE %s OR 
                update_msg LIKE %s OR update_msg LIKE %s OR
                update_msg IS NULL OR update_msg = '' OR
                (update_msg IS NOT NULL AND update_msg != '' AND 
                    update_msg NOT LIKE %s AND update_msg NOT LIKE %s AND 
                    update_msg NOT LIKE %s AND update_msg NOT LIKE %s AND 
                    update_msg NOT LIKE %s AND LOWER(update_msg) NOT LIKE %s)) AND {where_clause}
        """
        cursor.execute(upload_failed_sql, [
            "%品牌名称%总部不存在%请核查数据%",
            "%过期时间%不能小于当前时间%",
            "%物料所属品牌%OE号%产品数据不存在%请核查数据%",
            "%OE号【%】处理结果：成功%",         # 新建成功
            "%OE号【%】处理结果：失败%",         # 新建失败
            "%品牌名称%总部不存在%请核查数据%",  # 用于NOT LIKE
            "%过期时间%不能小于当前时间%",      # 用于NOT LIKE
            "%物料所属品牌%OE号%产品数据不存在%请核查数据%",  # 用于NOT LIKE
            "%OE号【%】处理结果：成功%",         # 用于NOT LIKE
            "%OE号【%】处理结果：失败%",         # 用于NOT LIKE
            "%update%"  # 用于NOT LIKE
        ] + params[:-2])
        upload_failed_count = cursor.fetchone()['count']

        # 计算统计结果
        success_count = total - upload_failed_count  # 成功数量 = 总数 - 上传失败数
        failed_count = upload_failed_count  # 失败数等于上传失败数
        no_record_count = upload_failed_count  # 没有档案数等于上传失败数
        new_archive_count = 0  # 新建档案数为0（因为都归类到上传失败了）

        conn.close()

        return jsonify({
            'code': 0,
            'msg': '',
            'count': total,
            'data': rows,
            'statistics': {
                'success_count': success_count,
                'failed_count': failed_count,
                'no_record_count': no_record_count,
                'new_archive_count': new_archive_count
            }
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取数据失败: {str(e)}'}), 500

@virtual_inventory_bp.route('/api/supplier_summary')
@login_required
def get_supplier_summary():
    """获取各供应商上传成功和失败统计 - 始终基于当前业务日期范围"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 获取当前业务日期范围
        start_time, end_time = get_business_date_range()

        # 查询每个供应商的上传成功和失败统计 - 限制为当前业务日期范围
        sql = """
            SELECT 
                supplier_name,
                COUNT(*) as total_count,
                SUM(CASE WHEN LOWER(update_msg) LIKE %s THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN LOWER(update_msg) NOT LIKE %s OR update_msg IS NULL OR update_msg = '' THEN 1 ELSE 0 END) as failed_count
            FROM virtual_inventory 
            WHERE supplier_name IS NOT NULL AND supplier_name != ''
            AND fetch_time >= %s AND fetch_time < %s
            GROUP BY supplier_name
            ORDER BY supplier_name
        """
        cursor.execute(sql, ("%update%", "%update%", start_time, end_time))
        rows = cursor.fetchall()

        conn.close()

        return jsonify({
            'code': 0,
            'msg': '',
            'data': rows
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取供应商汇总失败: {str(e)}'}), 500

# 新增API路由：根据当前业务日期获取虚拟库存数据
@virtual_inventory_bp.route('/api/virtual_inventory_today', methods=['GET'])
@login_required
def get_virtual_inventory_today():
    """获取当前业务日的虚拟库存数据"""
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

        # 获取业务日期范围
        start_time, end_time = get_business_date_range()

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 构建查询条件
        where_conditions = ["fetch_time >= %s AND fetch_time < %s"]
        params = [start_time, end_time]

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
                order_clause = "ORDER BY `fetch_time` DESC"
        else:
            order_clause = "ORDER BY `fetch_time` DESC"

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
            'data': rows,
            'business_date': start_time.strftime('%Y-%m-%d'),  # 返回业务日期
            'business_time_range': f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}"  # 返回业务时间范围
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取今日数据失败: {str(e)}'}), 500

# 新增API路由：获取指定业务日期的虚拟库存数据
@virtual_inventory_bp.route('/api/virtual_inventory_by_date', methods=['GET'])
@login_required
def get_virtual_inventory_by_date():
    """获取指定业务日期的虚拟库存数据"""
    try:
        # 获取请求参数
        business_date_str = request.args.get('business_date', '').strip()  # 业务日期，格式：YYYY-MM-DD
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

        # 如果没有提供业务日期，使用当前业务日期
        if not business_date_str:
            start_time, end_time = get_business_date_range()
        else:
            try:
                business_date = datetime.strptime(business_date_str, '%Y-%m-%d').date()
                start_time = datetime.combine(business_date, datetime.min.time().replace(hour=13))
                end_time = start_time + timedelta(days=1)
            except ValueError:
                return jsonify({'code': 1, 'msg': '日期格式错误，请使用 YYYY-MM-DD 格式'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 构建查询条件
        where_conditions = ["fetch_time >= %s AND fetch_time < %s"]
        params = [start_time, end_time]

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
                order_clause = "ORDER BY `fetch_time` DESC"
        else:
            order_clause = "ORDER BY `fetch_time` DESC"

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
            'data': rows,
            'business_date': business_date_str if business_date_str else start_time.strftime('%Y-%m-%d'),
            'business_time_range': f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取指定日期数据失败: {str(e)}'}), 500

# 新增API路由：获取当前业务日期的统计数据
@virtual_inventory_bp.route('/api/virtual_inventory_statistics_today', methods=['GET'])
@login_required
def get_virtual_inventory_statistics_today():
    """获取当前业务日的虚拟库存统计信息"""
    try:
        # 获取业务日期范围
        start_time, end_time = get_business_date_range()

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 总记录数
        total_sql = "SELECT COUNT(*) as count FROM virtual_inventory WHERE fetch_time >= %s AND fetch_time < %s"
        cursor.execute(total_sql, (start_time, end_time))
        total_count = cursor.fetchone()['count']
        print(f"当前业务日总记录数: {total_count}")

        # 成功上传：包含"update"的数据
        success_sql = "SELECT COUNT(*) as count FROM virtual_inventory WHERE LOWER(update_msg) LIKE %s AND fetch_time >= %s AND fetch_time < %s"
        cursor.execute(success_sql, ("%update%", start_time, end_time))
        success_count = cursor.fetchone()['count']
        print(f"当前业务日成功上传数 (update): {success_count}")
        
        # 新建成功：包含"OE号【"和"】处理结果：成功"
        new_success_sql = """
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE update_msg LIKE %s AND update_msg LIKE %s AND fetch_time >= %s AND fetch_time < %s
        """
        cursor.execute(new_success_sql, ["%OE号【%", "%】处理结果：成功%", start_time, end_time])
        new_success_count = cursor.fetchone()['count']
        print(f"当前业务日新建成功数: {new_success_count}")
        
        # 新建失败：包含"OE号【"和"】处理结果：失败"
        new_fail_sql = """
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE update_msg LIKE %s AND update_msg LIKE %s AND fetch_time >= %s AND fetch_time < %s
        """
        cursor.execute(new_fail_sql, ["%OE号【%", "%】处理结果：失败%", start_time, end_time])
        new_fail_count = cursor.fetchone()['count']
        print(f"当前业务日新建失败数: {new_fail_count}")
        
        # 品牌名称总部不存在
        brand_not_exist_sql = """
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE update_msg LIKE %s AND fetch_time >= %s AND fetch_time < %s
        """
        cursor.execute(brand_not_exist_sql, ["%品牌名称%总部不存在%请核查数据%", start_time, end_time])
        brand_not_exist_count = cursor.fetchone()['count']
        print(f"当前业务日品牌名称总部不存在数: {brand_not_exist_count}")
        
        # 物料所属品牌OE号不存在
        product_not_exist_sql = """
            SELECT COUNT(*) as count FROM virtual_inventory 
            WHERE update_msg LIKE %s AND fetch_time >= %s AND fetch_time < %s
        """
        cursor.execute(product_not_exist_sql, ["%物料所属品牌%OE号%产品数据不存在%请核查数据%", start_time, end_time])
        product_not_exist_count = cursor.fetchone()['count']
        print(f"当前业务日物料所属品牌OE号不存在数: {product_not_exist_count}")
        
        # 失败：总记录数 - 成功上传
        failed_count = total_count - success_count
        print(f"当前业务日失败数: {failed_count}")
        
        # 没有档案：新建失败 + 新建成功 + 品牌名称总部不存在 + 物料所属品牌OE号不存在
        no_record_count = new_success_count + new_fail_count + brand_not_exist_count + product_not_exist_count
        print(f"当前业务日没有档案数: {no_record_count}")
        
        # 新建档案：新建成功
        new_archive_count = new_success_count
        print(f"当前业务日新建档案数: {new_archive_count}")

        conn.close()

        result = {
            'code': 0,
            'msg': '',
            'data': {
                'business_date': start_time.strftime('%Y-%m-%d'),
                'business_time_range': f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
                'total_count': total_count,
                'success_count': success_count,
                'failed_count': failed_count,
                'no_record_count': no_record_count,
                'new_archive_count': new_archive_count
            }
        }
        print(f"当前业务日统计返回结果: {result}")
        
        return jsonify(result)

    except Exception as e:
        print(f"获取当前业务日统计数据失败: {str(e)}")
        return jsonify({'code': 1, 'msg': f'获取当前业务日统计数据失败: {str(e)}'}), 500

# 导入到主应用的函数============================================================================================
def register_virtual_inventory_routes(app):
    app.register_blueprint(virtual_inventory_bp)