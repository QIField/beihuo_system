from flask import Flask, render_template, jsonify, request, session, Response, send_file
import pymysql ,atexit ,schedule ,threading,re,time,os,json, io, csv, math, sys
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from backend.virtual_inventory_api import register_virtual_inventory_routes
from backend.search_in_crm import search_in_crm_bp
from backend.ks_auto_bill_api import ks_auto_bill_bp
from backend.excel_process_api import register_excel_process_routes
from urllib.parse import unquote
import pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Alignment, NamedStyle, Font
from openpyxl.utils import get_column_letter
import chardet
import warnings
from decimal import Decimal, getcontext
from werkzeug.utils import secure_filename
import zipfile
from io import BytesIO
import tempfile
import shutil
import uuid
from backend.get_order import get_order_bp
from backend.log_viewer_api import register_log_viewer_routes
from flask_socketio import SocketIO
from app.sockets import register_socket_events, notification_manager
from app.utils.database_connection import get_db_connection
from app.utils.search import parse_space, parse_comma
from app.utils.export_tools import handle_export_request

# 导入轻量级任务管理器（延迟初始化）
from app.core.task_manager import task_manager


app = Flask(__name__, 
            template_folder='./templates',
            static_folder='./static')
app.secret_key = 'your-very-secret-key' 
register_virtual_inventory_routes(app)
register_excel_process_routes(app)  # 注册Excel处理API
app.register_blueprint(search_in_crm_bp)
app.register_blueprint(get_order_bp)
app.register_blueprint(ks_auto_bill_bp)
register_log_viewer_routes(app)  # 注册日志查看器路由
# 根据环境选择 async_mode
import platform

# 检测是否在 uWSGI 环境中运行
try:
    import uwsgi
    IS_UWSGI = True
except ImportError:
    IS_UWSGI = False

# 检测 eventlet 是否可用
try:
    import eventlet
    EVENTLET_AVAILABLE = True
except ImportError:
    EVENTLET_AVAILABLE = False

# 选择 async_mode 的优先级：
# 1. 如果在 uWSGI 中运行，必须使用 threading（eventlet/gevent 与 uWSGI 不兼容）
# 2. 如果不在 uWSGI 中且 eventlet 可用，使用 eventlet（性能更好）
# 3. 否则使用 threading（保底方案）
if IS_UWSGI:
    # uWSGI 环境：必须使用 threading
    ASYNC_MODE = 'threading'
    print("[SocketIO] 检测到 uWSGI 环境，使用 threading 模式")
elif EVENTLET_AVAILABLE and platform.system() == 'Linux':
    # Linux 独立运行：使用 eventlet（高并发）
    ASYNC_MODE = 'eventlet'
    print("[SocketIO] 使用 eventlet 模式")
else:
    # Windows 或 eventlet 不可用：使用 threading
    ASYNC_MODE = 'threading'
    print(f"[SocketIO] 使用 threading 模式 (平台: {platform.system()})")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode=ASYNC_MODE,
    logger=False,  # 关闭详细日志，减少输出
    engineio_logger=False
)
# 将socketio实例存储到应用中，供notification_manager使用
app.socketio = socketio

app.config['JSON_AS_ASCII'] = False

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    XLSX_SUPPORT = True
except ImportError:
    XLSX_SUPPORT = False
    print("警告：未安装openpyxl，无法导出XLSX格式，请运行 'pip install openpyxl'")

# 门店映射
STORES = {
    'fsbbr': '佛山门店',
    'zsbbr': '中山门店',
    'zhbbr': '珠海门店',
    'dgby': '百业门店',
    'dghf': '合峰门店'
}

#前置函数====================================================================================================================
def get_valid_db_connection():
    """获取有效的数据库连接，如果连接失效则重新连接"""
    try:
        connection = get_db_connection()
        # 测试连接是否有效
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return connection
    except Exception as e:
        print(f"数据库连接测试失败: {e}")
        # 如果连接失败，尝试重新连接
        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return connection
        except Exception as e2:
            print(f"重新连接数据库也失败: {e2}")
            raise e2

    # 在应用启动时检查并创建购物车表
def init_cart_table():
    """初始化购物车表 - 包含账户名和门店字段"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建购物车表
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS crmapp_cart (
        id INT AUTO_INCREMENT PRIMARY KEY,
        oe VARCHAR(255) NOT NULL COMMENT 'OE号',
        supplier VARCHAR(255) COMMENT '供应商',
        brand VARCHAR(255) COMMENT '品牌',
        material_name VARCHAR(500) COMMENT '物料名称',
        barcode VARCHAR(255) COMMENT '物料条码',
        car_brand VARCHAR(255) COMMENT '车型品牌',
        tag VARCHAR(255) COMMENT '标签',
        inquiry_1m INT DEFAULT 0 COMMENT '近1个月询价量',
        inquiry_3m INT DEFAULT 0 COMMENT '近3个月月均询价量',
        stock INT DEFAULT 0 COMMENT '库存数量',
        sales_yesterday INT DEFAULT 0 COMMENT '昨日销量',
        sales_month INT DEFAULT 0 COMMENT '本月销量',
        today_sales INT DEFAULT 0 COMMENT '今日销量',
        national_inquiry_1m INT DEFAULT 0 COMMENT '全国近1个月询价量',
        national_inquiry_3m INT DEFAULT 0 COMMENT '全国近3个月月均询价量',
        internal_remarks TEXT COMMENT '内部备注',
        brand_code VARCHAR(255) COMMENT '品牌号',
        stock_amount DECIMAL(10,2) DEFAULT 0.00 COMMENT '库存金额',
        sellable_days INT DEFAULT 0 COMMENT '成品可卖天数',
        cost_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '成本价',
        avg_sales_12m INT DEFAULT 0 COMMENT '近12个月月均销量',
        avg_sales_6m INT DEFAULT 0 COMMENT '近6个月月均销量',
        sales_7d INT DEFAULT 0 COMMENT '近7天销量',
        warning_status VARCHAR(255) COMMENT '预警状态',
        on_way INT DEFAULT 0 COMMENT '在途数量',
        car_model VARCHAR(255) COMMENT '车型',
        quantity INT DEFAULT 1 COMMENT '数量',
        added_time DATETIME COMMENT '加入时间',
        added_by VARCHAR(255) COMMENT '加入账户名',
        store VARCHAR(100) COMMENT '门店代码',
        INDEX idx_oe (oe),
        INDEX idx_barcode (barcode),
        INDEX idx_store (store),
        INDEX idx_added_by (added_by),
        INDEX idx_added_time (added_time),
        INDEX idx_barcode_store (barcode, store),  -- 优化添加到购物车的查询
        INDEX idx_oe_store (oe, store),            -- 优化更新数量的查询
        INDEX idx_oe_barcode_store (oe, barcode, store), -- 优化精确查找的查询
        INDEX idx_oe_barcode (oe, barcode)         -- 新增：优化OE和条码的组合查询
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='购物车表';
    """
    
    try:
        cursor.execute(create_table_sql)
        print("购物车表初始化完成")
    except Exception as e:
        print(f"初始化购物车表时出错: {e}")
    finally:
        cursor.close()
        conn.close()



# 初始化用户表
def init_user_table():
    """初始化用户表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建用户表
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS crmapp_users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名',
        password VARCHAR(255) NOT NULL COMMENT '密码',
        is_admin TINYINT(1) DEFAULT 0 COMMENT '是否为管理员 0-否 1-是',
        store VARCHAR(50) DEFAULT 'fsbbr' COMMENT '所属门店代码',
        can_delete_cart TINYINT(1) DEFAULT 0 COMMENT '是否有权限删除购物车 0-否 1-是',
        can_process_orders TINYINT(1) DEFAULT 0 COMMENT '是否有权限处理单据 0-否 1-是',
        department VARCHAR(20) DEFAULT NULL COMMENT '板块:业务/市场/后勤',
        job_level VARCHAR(20) DEFAULT NULL COMMENT '职级:经理/主管/业务员',
        ip_records JSON COMMENT '登录IP记录，最多保留5个最近的IP地址',
        allowed_orgs JSON COMMENT '允许切换的组织列表，JSON格式，如["fsbbr", "zsbbr"]，null表示所有组织都可切换',
        created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        INDEX idx_username (username),
        INDEX idx_store (store)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';
    """
    
    try:
        cursor.execute(create_table_sql)
        print("用户表初始化完成")
    except Exception as e:
        print(f"初始化用户表时出错: {e}")
    finally:
        cursor.close()
        conn.close()
        
    # 检查并添加缺失的字段（使用循环统一处理）
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 定义需要检查和添加的字段列表
        fields_to_check = [
            {
                'name': 'can_delete_cart',
                'definition': "TINYINT(1) DEFAULT 0 COMMENT '是否有权限删除购物车 0-否 1-是'"
            },
            {
                'name': 'can_process_orders',
                'definition': "TINYINT(1) DEFAULT 0 COMMENT '是否有权限处理单据 0-否 1-是'"
            },
            {
                'name': 'ip_records',
                'definition': "JSON COMMENT '登录IP记录，最多保留5个最近的IP地址'"
            },
            {
                'name': 'allowed_orgs',
                'definition': "JSON COMMENT '允许切换的组织列表，JSON格式，如[\"fsbbr\", \"zsbbr\"]，null表示所有组织都可切换'"
            },
            {
                'name': 'department',
                'definition': "VARCHAR(20) DEFAULT NULL COMMENT '板块:业务/市场/后勤'"
            },
            {
                'name': 'job_level',
                'definition': "VARCHAR(20) DEFAULT NULL COMMENT '职级:经理/主管/业务员'"
            }
        ]
        
        # 循环检查并添加字段
        for field in fields_to_check:
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'crmapp_users' 
                AND COLUMN_NAME = %s
            """, (field['name'],))
            
            result = cursor.fetchone()
            if not result:
                cursor.execute(f"ALTER TABLE crmapp_users ADD COLUMN {field['name']} {field['definition']}")
                print(f"已添加 {field['name']} 字段")
            else:
                pass
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"检查并添加字段时出错: {e}")
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

    # 检查是否已有用户，如果没有则创建默认管理员账户
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT COUNT(*) as count FROM crmapp_users")
    result = cursor.fetchone()
    conn.close()
    
    if result['count'] == 0:
        # 创建默认用户
        create_default_users()


def create_default_users():
    """创建默认用户账户"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    default_users = [
        ('admin', '123456', 1, 'fsbbr', 1),      # 管理员默认门店为佛山，可以通过切换功能查看所有门店数据
        ('fsbbr', 'fsbbr123', 0, 'fsbbr', 1),  # 佛山门店
        ('zsbbr', 'zsbbr123', 0, 'zsbbr', 1),  # 中山门店
        ('zhbbr', 'zhbbr123', 0, 'zhbbr', 1),  # 珠海门店
        ('dgby', 'dgby123', 0, 'dgby', 1),     # 百业门店
        ('dghf', 'dghf123', 0, 'dghf', 1)      # 合峰门店
    ]
    
    try:
        for user in default_users:
            cursor.execute("""
                INSERT INTO crmapp_users (username, password, is_admin, store, can_delete_cart) 
                VALUES (%s, %s, %s, %s, %s)
            """, user)
        conn.commit()
        print("默认用户创建完成")
    except Exception as e:
        print(f"创建默认用户时出错: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# 添加一个函数来初始化备货数据表
def init_beihuo_table():
    """初始化备货数据表 - 包含更新时间字段"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建备货数据表
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS crmapp_beihuo (
        id INT AUTO_INCREMENT PRIMARY KEY,
        oe VARCHAR(255) NOT NULL COMMENT 'OE号',
        今日销量 INT DEFAULT 0 COMMENT '今日销量',
        供应商 TEXT COMMENT '供应商',
        全国近1个月询价量 INT DEFAULT 0 COMMENT '全国近1个月询价量',
        全国近3个月月均询价量 INT DEFAULT 0 COMMENT '全国近3个月月均询价量',
        内部备注 TEXT COMMENT '内部备注',
        品牌 VARCHAR(255) COMMENT '品牌',
        品牌号 VARCHAR(255) COMMENT '品牌号',
        库存数量 INT DEFAULT 0 COMMENT '库存数量',
        库存金额 DECIMAL(10,2) DEFAULT 0.00 COMMENT '库存金额',
        成品可卖天数 INT DEFAULT 0 COMMENT '成品可卖天数',
        成本价 DECIMAL(10,2) DEFAULT 0.00 COMMENT '成本价',
        昨日销量 INT DEFAULT 0 COMMENT '昨日销量',
        本月销量 INT DEFAULT 0 COMMENT '本月销量',
        标签 VARCHAR(255) COMMENT '标签',
        物料名称 VARCHAR(500) COMMENT '物料名称',
        物料条码 VARCHAR(255) COMMENT '物料条码',
        车型品牌 VARCHAR(255) COMMENT '车型品牌',
        近12个月月均销量 INT DEFAULT 0 COMMENT '近12个月月均销量',
        近1个月询价量 INT DEFAULT 0 COMMENT '近1个月询价量',
        近3个月月均询价量 INT DEFAULT 0 COMMENT '近3个月月均询价量',
        近6个月月均销量 INT DEFAULT 0 COMMENT '近6个月月均销量',
        近7天销量 INT DEFAULT 0 COMMENT '近7天销量',
        预警状态 VARCHAR(255) COMMENT '预警状态',
        company VARCHAR(100) COMMENT '公司',
        更新时间 TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        今日销售 VARCHAR(255) COMMENT '今日销售',
        在途数量 INT DEFAULT 0 COMMENT '在途数量',
        车型 TEXT COMMENT '车型',
        替换号 VARCHAR(255) COMMENT '替换号',
        INDEX idx_oe (oe),
        INDEX idx_barcode (物料条码),
        INDEX idx_company (company),
        INDEX idx_oe_barcode (oe, 物料条码),
        INDEX idx_updated_time (更新时间)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='备货数据表';
    """
    
    try:
        cursor.execute(create_table_sql)
        print("备货数据表初始化完成")
        
        # 检查并添加缺失的字段（使用循环统一处理）
        beihuo_fields = [
            {
                'name': '在途数量',
                'definition': "INT DEFAULT 0 COMMENT '在途数量'"
            },
            {
                'name': '车型',
                'definition': "VARCHAR(255) COMMENT '车型'"
            }
        ]
        
        for field in beihuo_fields:
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'crmapp_beihuo' 
                AND COLUMN_NAME = %s
            """, (field['name'],))
            result = cursor.fetchone()
            if not result:
                cursor.execute(f"ALTER TABLE crmapp_beihuo ADD COLUMN `{field['name']}` {field['definition']}")
                print(f"{field['name']} 字段已添加到备货数据表")
            else:
                pass
            
    except Exception as e:
        print(f"初始化备货数据表时出错: {e}")
    finally:
        cursor.close()
        conn.close()


# 添加一个函数来确保购物车表有适当的索引
def ensure_cart_indexes():
    """确保购物车表有适当的索引以提高查询性能"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 定义需要检查和创建的索引列表
        cart_indexes = [
            {
                'name': 'idx_barcode_store',
                'definition': 'ADD INDEX idx_barcode_store (barcode, store)',
                'desc': '物料条码和门店组合索引'
            },
            {
                'name': 'idx_oe_store',
                'definition': 'ADD INDEX idx_oe_store (oe, store)',
                'desc': 'oe和门店组合索引'
            },
            {
                'name': 'idx_oe_barcode',
                'definition': 'ADD INDEX idx_oe_barcode (oe, barcode)',
                'desc': 'oe和物料条码组合索引'
            },
            {
                'name': 'idx_added_time',
                'definition': 'ADD INDEX idx_added_time (added_time)',
                'desc': '添加时间索引'
            },
            {
                'name': 'idx_oe_barcode_store',
                'definition': 'ADD INDEX idx_oe_barcode_store (oe, barcode, store)',
                'desc': 'oe、物料条码和门店组合索引'
            }
        ]
        
        # 循环检查并创建索引
        for idx in cart_indexes:
            cursor.execute(f"SHOW INDEX FROM crmapp_cart WHERE Key_name = '{idx['name']}'")
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE crmapp_cart {idx['definition']}")
                print(f"✅ 购物车表{idx['desc']}已创建")
            else:
                pass
    except Exception as e:
        print(f"❌ 创建购物车表索引失败: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def init_date_search_table():
    """初始化日期搜索数据表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建日期搜索数据表
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS crmapp_date_search (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) COMMENT '用户名',
        start_date DATE COMMENT '开始日期',
        end_date DATE COMMENT '结束日期',
        company VARCHAR(50) COMMENT '公司代码',
        物料条码 VARCHAR(255) COMMENT '物料条码',
        物料名称 VARCHAR(500) COMMENT '物料名称',
        品牌 VARCHAR(255) COMMENT '品牌',
        品牌号 VARCHAR(255) COMMENT '品牌号',
        车型品牌 VARCHAR(255) COMMENT '车型品牌',
        oe TEXT COMMENT 'OE码',
        标签 VARCHAR(255) COMMENT '标签',
        车型 TEXT COMMENT '车型',
        替换号 VARCHAR(255) COMMENT '替换号',
        今日销量 INT DEFAULT 0 COMMENT '今日销量',
        昨日销量 INT DEFAULT 0 COMMENT '昨日销量',
        本月销量 INT DEFAULT 0 COMMENT '本月销量',
        近7天销量 INT DEFAULT 0 COMMENT '近7天销量',
        近1个月询价量 INT DEFAULT 0 COMMENT '近1个月询价量',
        近3个月月均询价量 DECIMAL(10,2) DEFAULT 0.00 COMMENT '近3个月月均询价量',
        近6个月月均销量 DECIMAL(10,2) DEFAULT 0.00 COMMENT '近6个月月均销量',
        近12个月月均销量 DECIMAL(10,2) DEFAULT 0.00 COMMENT '近12个月月均销量',
        成品可卖天数 INT DEFAULT 0 COMMENT '成品可卖天数',
        库存数量 INT DEFAULT 0 COMMENT '库存数量',
        在途数量 INT DEFAULT 0 COMMENT '在途数量',
        成本价 DECIMAL(10,2) DEFAULT 0.00 COMMENT '成本价',
        库存金额 DECIMAL(15,2) DEFAULT 0.00 COMMENT '库存金额',
        供应商 TEXT COMMENT '供应商',
        全国近1个月询价量 INT DEFAULT 0 COMMENT '全国近1个月询价量',
        全国近3个月月均询价量 INT DEFAULT 0 COMMENT '全国近3个月月均询价量',
        内部备注 TEXT COMMENT '内部备注',
        预警状态 VARCHAR(255) COMMENT '预警状态',
        销量 INT DEFAULT 0 COMMENT '销量',
        查询时间 TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '查询时间',
        INDEX idx_username (username),
        INDEX idx_dates (start_date, end_date),
        INDEX idx_company (company),
        INDEX idx_barcode (物料条码),
        INDEX idx_username_dates (username, start_date, end_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='日期搜索数据表';
    """
    
    try:
        cursor.execute(create_table_sql)
        print("日期搜索数据表初始化完成")
    except Exception as e:
        print(f"初始化日期搜索数据表时出错: {e}")
    finally:
        cursor.close()
        conn.close()

def ensure_table_structure():
    """确保数据库表结构正确，包括字段长度等"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 定义需要修改的字段列表（表名、字段名、新定义）
    fields_to_modify = [
        {'table': 'crmapp_beihuo', 'field': '车型', 'definition': 'TEXT', 'desc': '车型字段'},
        {'table': 'crmapp_cart', 'field': 'car_model', 'definition': 'TEXT', 'desc': '购物车车型字段'},
        {'table': 'crmapp_beihuo', 'field': '供应商', 'definition': 'TEXT', 'desc': '供应商字段'},
        {'table': 'crmapp_beihuo', 'field': '内部备注', 'definition': 'TEXT', 'desc': '内部备注字段'}
    ]
    
    for field in fields_to_modify:
        try:
            cursor.execute(f"""
                ALTER TABLE {field['table']} MODIFY COLUMN `{field['field']}` {field['definition']}
            """)
            print(f"✅ {field['desc']}已更新为{field['definition']}类型")
        except Exception as e:
            print(f"ℹ️ 修改{field['desc']}类型时可能遇到预期情况: {e}")
    
    cursor.close()
    conn.close()

# 在应用启动时调用初始化函数
init_beihuo_table()
init_cart_table()
init_user_table()
init_date_search_table()  

# 确保表结构正确
ensure_table_structure()

# 检查并修复可能存在的错误数据
def fix_user_store_data():
    """修复可能存在的错误用户数据，将store为'all'的用户更新为有效门店代码"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查并更新store为'all'的用户
        cursor.execute("UPDATE crmapp_users SET store = 'fsbbr' WHERE store = 'all'")
        affected_rows = cursor.rowcount
        if affected_rows > 0:
            print(f"✅ 已修复 {affected_rows} 个用户的错误门店数据")
        else:
            print("ℹ️ 未发现需要修复的错误门店数据")
        conn.commit()
    except Exception as e:
        print(f"❌ 修复用户门店数据失败: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# 在应用启动时修复数据
fix_user_store_data()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

def is_alpha_only(s):
    """检查字符串是否只包含字母"""
    return s.isalpha()

# 使用新的搜索工具包，保留原函数名作为别名
def process_barcode_search(barcode_str):
    """处理条码搜索，特别处理空格分隔的条码"""
    return parse_space(barcode_str)


def process_oe_search(oe_str):
    """处理OE搜索，空格分隔的每个部分作为一个独立的搜索项"""
    return parse_space(oe_str)


def process_material_name_search(material_name_str):
    """处理物料名称搜索，使用逗号分隔（中文逗号或英文逗号）"""
    return parse_comma(material_name_str)

#调用虚拟库存文件并新建档案=========================================================================================================
import os
import threading
from datetime import datetime, date

# 添加进程ID标识，确保只有主进程运行定时任务
MAIN_PROCESS_ID = os.getpid()
print(f"当前进程ID: {MAIN_PROCESS_ID}")

# 定时任务执行追踪
task_execution_tracker = {
    'virtual_inventory_last_run': None,
    'task_running': False,
    'execution_log': [],
    'process_id': MAIN_PROCESS_ID  # 添加进程ID标识
}

# 单一锁，确保任务串行执行
combined_task_lock = threading.Lock()

# 添加每日执行状态追踪
daily_execution_status = {
    'combined_task_executed_today': False,
    'last_execution_date': None
}

def reset_daily_status():
    """重置每日执行状态"""
    today = date.today()
    if daily_execution_status['last_execution_date'] != today:
        daily_execution_status['last_execution_date'] = today
        daily_execution_status['combined_task_executed_today'] = False
        print(f"[{datetime.now()}] DEBUG: 重置每日执行状态，今天是 {today}")

def run_crm_create_products_task():
    """运行CRM新建产品任务的函数 - 优化版本"""
    print(f"[{datetime.now()}] 开始执行CRM新建产品任务...")
    
    try:
        # 使用新的 API 调用数据库模式
        from app.utils.crm_product import process_database_mode_api
        
        # 调用数据库模式处理
        process_database_mode_api()
            
        print(f"[{datetime.now()}] CRM新建产品任务执行完成！")
        
    except Exception as e:
        print(f"[{datetime.now()}] 执行CRM新建产品任务时出错: {e}")

def run_virtual_inventory_task():
    """运行虚拟库存任务的函数 - 优化版本，保持串行执行逻辑"""
    current_time = datetime.now()
    print(f"[{current_time}] DEBUG: run_virtual_inventory_task 被调用, 进程ID: {os.getpid()}")
    
    # 检查是否有任务正在运行
    if task_execution_tracker['task_running']:
        print(f"[{current_time}] DEBUG: 任务已在运行中，跳过本次执行")
        task_execution_tracker['execution_log'].append({
            'time': current_time,
            'status': 'skipped_already_running',
            'reason': 'previous_task_still_running',
            'process_id': os.getpid()
        })
        return
    
    # 记录任务开始
    task_execution_tracker['task_running'] = True
    task_execution_tracker['virtual_inventory_last_run'] = current_time
    task_execution_tracker['execution_log'].append({
        'time': current_time,
        'status': 'started',
        'function': 'run_virtual_inventory_task',
        'process_id': os.getpid()
    })
    
    reset_daily_status()
    
    with combined_task_lock:
        # 检查今天是否已经执行过组合任务
        if daily_execution_status['combined_task_executed_today']:
            print(f"[{datetime.now()}] 组合任务（虚拟库存+CRM）今日已执行，跳过本次执行")
            task_execution_tracker['task_running'] = False
            task_execution_tracker['execution_log'].append({
                'time': current_time,
                'status': 'skipped_already_executed_today',
                'reason': 'combined_task_executed_today',
                'process_id': os.getpid()
            })
            return
        
        print(f"[{datetime.now()}] 进程{os.getpid()} 开始执行虚拟库存数据同步任务...")
        
        try:
            # 动态导入virtual_inventory模块
            # 确保项目根目录在sys.path中
            project_root = os.path.dirname(os.path.abspath(__file__))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            # 使用绝对导入方式加载模块
            from app.utils import virtual_inventory
            
            # 调用主处理函数，跳过表创建（已在应用启动时创建）
            virtual_inventory.main_process(skip_table_creation=True)
            print(f"[{datetime.now()}] 虚拟库存数据同步任务执行完成！")
            
            # 在虚拟库存任务完成后，立即执行CRM新建产品任务（保持原有串行逻辑）
            run_crm_create_products_task()
            
            # 标记今日已执行组合任务
            daily_execution_status['combined_task_executed_today'] = True
            
            # 记录成功完成
            task_execution_tracker['execution_log'].append({
                'time': datetime.now(),
                'status': 'completed_successfully',
                'function': 'run_virtual_inventory_task'
            })
            
        except Exception as e:
            print(f"[{datetime.now()}] 执行虚拟库存数据同步任务时出错: {e}")
        finally:
            # 确保任务标记被重置
            task_execution_tracker['task_running'] = False
            print(f"[{datetime.now()}] DEBUG: 任务执行结束，重置task_running标志")

# 注册每小时购物车高库存清理任务
def run_cart_cleanup_task():
    """每小时自动清理购物车高库存商品"""
    print(f"[{datetime.now()}] 🕒 开始执行每小时购物车高库存清理任务...")

    try:
        from app.services.cart_service.cart_auto_cleanup import CartAutoCleanupService

        cleanup_service = CartAutoCleanupService()
        results = cleanup_service.cleanup_after_data_update()

        # 统计清理结果
        total_deleted = sum(
            r.get('deleted_count', 0)
            for r in results
            if r.get('status') == 'success'
        )

        if total_deleted > 0:
            print(f"✅ 每小时购物车清理完成：共删除 {total_deleted} 个高库存商品")
        else:
            print("ℹ️ 每小时购物车清理完成：无高库存商品需要清理")

    except Exception as e:
        print(f"❌ 每小时购物车清理任务失败: {str(e)}")

def print_task_debug_info():
    """打印任务执行调试信息"""
    print("="*50)
    print("DEBUG INFO - 任务执行状态:")
    print(f"- task_running: {task_execution_tracker['task_running']}")
    print(f"- combined_task_executed_today: {daily_execution_status['combined_task_executed_today']}")
    print(f"- last_execution_date: {daily_execution_status['last_execution_date']}")
    print(f"- virtual_inventory_last_run: {task_execution_tracker['virtual_inventory_last_run']}")
    print(f"- execution_log_count: {len(task_execution_tracker['execution_log'])}")
    
    # 显示task_manager统计
    stats = task_manager.get_stats()
    print(f"\nTask Manager 统计:")
    print(f"- 提交任务: {stats['submitted']}")
    print(f"- 运行中: {stats['running']}")
    print(f"- 已完成: {stats['completed']}")
    print(f"- 失败: {stats['failed']}")
    print(f"- 活跃线程: {stats['active_threads']}")
    
    # 显示最近5次执行记录
    recent_logs = task_execution_tracker['execution_log'][-5:] if task_execution_tracker['execution_log'] else []
    print("\n最近的执行记录:")
    for log in recent_logs:
        print(f"  - {log}")
    print("="*50)

print("定时任务已启动：每天13:00执行虚拟库存数据同步，完成后执行CRM新建产品")
print("调试信息将在任务执行时输出，可通过 print_task_debug_info() 查看当前状态")
print("任务统计信息可通过 /api/tasks/stats 查看")


#定时更新========================================================================================================================================
import time
from threading import Timer
from datetime import datetime, timedelta
import atexit
import re

# 添加定时更新相关全局变量
last_auto_update_time = None
auto_update_lock = threading.Lock()
scheduled_fetch_timer = None
fetch_task_lock = threading.Lock()

# 添加一个标志来防止重复执行
updating_lock = threading.Lock()
is_updating_flag = False

def auto_update_and_fetch():
    """自动更新数据，然后10分钟后自动拉取"""
    global last_auto_update_time, is_updating_flag
    
    # 使用锁防止并发执行
    with updating_lock:
        if is_updating_flag:
            print("🔄 自动更新已在执行中，跳过本次执行")
            return
        
        is_updating_flag = True
    
    try:
        current_time = datetime.now()
        last_auto_update_time = current_time
        print(f"⏰ 开始执行自动更新: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 执行更新操作（调用更新API）
        update_all_stores()
        
        # 设置10分钟后自动拉取数据的定时器
        schedule_fetch_after_delay()
        
    finally:
        # 重置执行标志
        is_updating_flag = False

def clean_data_date(value):
    """清理数据，处理特殊格式"""
    if value is None:
        return ""
    if isinstance(value, str):
        # 处理包含<数字次的格式
        match = re.search(r'<(\d+)次', value)
        if match:
            num = int(match.group(1))
            # 返回比匹配数字大1的值
            return str(num + 1)
        return value
    return str(value)



def update_all_stores():
    """更新所有门店的数据 - 参考手动更新的逻辑"""
    import requests
    import json
    
    # API配置 - 使用与手动更新相同的API端点
    API_URL = "http://bi.gzbbr.com/crmapp_api.update_beihuo"
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Authorization': 'Basic YWRtaW46ODA4OA==',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'http://bi.gzbbr.com',
        'Pragma': 'no-cache',
        'Referer': 'http://bi.gzbbr.com/crmapp_api.bh_index',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    # 更新所有门店的数据
    companies = ['fsbbr', 'zsbbr', 'zhbbr', 'dgby', 'dghf']
    
    success_count = 0
    for company in companies:
        try:
            # 准备请求数据
            data = {"company": company}
            
            # 发送更新请求 (与手动更新完全一致)
            response = requests.post(
                API_URL,
                headers=headers,
                data=data,
                timeout=120  # 增加超时时间，更新操作可能需要较长时间
            )
            
            # 检查HTTP状态码
            if response.status_code == 200:
                try:
                    # 尝试解析JSON响应
                    result = response.json()
                    
                    if isinstance(result, dict):
                        if result.get('code') == 0:
                            success_count += 1
                            print(f"✅ 门店 {company} 数据更新请求发送成功")
                        else:
                            # 输出完整的错误信息
                            error_msg = result.get('msg', 'Unknown error')
                            print(f"❌ 门店 {company} 数据更新请求失败: {error_msg}")
                            
                            # 检查响应中是否包含特定的成功提示（即使code不为0）
                            response_text = str(result)
                            if '正在更新' in response_text or '处理' in response_text:
                                success_count += 1
                                print(f"✅ 门店 {company} 数据更新请求已发送（正在后台处理）")
                    else:
                        print(f"❌ 门店 {company} 数据更新响应格式异常: {result}")
                        
                        # 如果响应不是预期的字典格式，检查文本内容
                        response_text = response.text
                        print(f"💡 门店 {company} 响应内容预览: {response_text[:500]}")
                        
                        # 检查是否包含成功或正在处理的关键词
                        if '正在更新' in response_text or '正在处理' in response_text or 'start' in response_text or 'running' in response_text:
                            success_count += 1
                            print(f"✅ 门店 {company} 数据更新请求已发送（正在后台处理）")
                        else:
                            print(f"❌ 门店 {company} 数据更新请求失败: 响应格式异常")
                            
                except json.JSONDecodeError:
                    # 如果响应不是JSON格式，检查文本内容中是否包含成功标识
                    response_text = response.text
                    print(f"💡 门店 {company} 响应内容预览: {response_text[:500]}")
                    
                    # 检查是否包含成功或正在处理的关键词
                    if '正在更新' in response_text or '正在处理' in response_text or 'start' in response_text or 'running' in response_text:
                        success_count += 1
                        print(f"✅ 门店 {company} 数据更新请求已发送（正在后台处理）")
                    else:
                        print(f"❌ 门店 {company} 数据更新请求失败: 无法解析响应")
            else:
                print(f"❌ 门店 {company} 数据更新请求HTTP错误 {response.status_code}: {response.text[:200]}...")
                
        except requests.exceptions.Timeout:
            # 超时可能意味着请求已发送，但响应较慢
            print(f"⏰ 门店 {company} 数据更新请求超时（可能仍在后台处理）")
            success_count += 1  # 假设请求已发送
        except requests.exceptions.RequestException as e:
            print(f"❌ 门店 {company} 更新网络请求时出错: {str(e)}")
        except Exception as e:
            print(f"❌ 门店 {company} 更新时出错: {str(e)}")
    
    print(f"✅ 自动更新完成！成功发送更新请求到 {success_count}/{len(companies)} 个门店")

    try:
        from app.services.data_sync_service.update_completion_handler import UpdateCompletionHandler
        handler = UpdateCompletionHandler()
        cleanup_results = handler.handle_post_update_operations()
        
        if cleanup_results['cart_cleanup']['status'] == 'completed':
            total_deleted = cleanup_results['cart_cleanup']['total_deleted']
            print(f"🕒 定时更新后清理完成：共删除 {total_deleted} 个高库存商品")
    except Exception as e:
        print(f"❌ 定时更新后清理失败: {str(e)}")

def auto_fetch_data():
    """自动拉取数据 - 添加锁防止并发"""
    with fetch_task_lock:  # 防止多个拉取任务同时执行
        print(f"⏰ 开始执行自动拉取数据: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 获取所有门店
        companies = ['fsbbr', 'zsbbr', 'zhbbr', 'dgby', 'dghf']
        
        success_count = 0
        for company in companies:
            try:
                # 调用拉取数据函数
                processed_count = fetch_data_for_company(company)
                if processed_count >= 0:  # 成功时返回非负数
                    success_count += 1
                    print(f"✅ 门店 {company} 数据自动拉取完成，处理了 {processed_count} 条记录")
                else:
                    print(f"❌ 门店 {company} 数据自动拉取失败")
            except Exception as e:
                print(f"❌ 门店 {company} 自动拉取时出错: {str(e)}")
        
        # 拉取数据完成后，更新购物车数据
        try:
            update_cart_data()
            print("🛒 购物车数据自动更新完成")
        except Exception as e:
            print(f"🛒 购物车数据自动更新失败: {str(e)}")
        
        print(f"✅ 自动拉取数据完成！成功更新 {success_count}/{len(companies)} 个门店的数据")



def schedule_fetch_after_delay():
    """在当前更新后10分钟安排拉取 - 优化版本"""
    global scheduled_fetch_timer
    
    with fetch_task_lock:  # 确保定时器操作的原子性
        # 如果之前有定时器，取消它
        if scheduled_fetch_timer:
            scheduled_fetch_timer.cancel()
            print("⏰ 已取消之前的延时拉取任务")
        
        # 10分钟后执行拉取
        def delayed_fetch():
            auto_fetch_data()
        
        # 创建定时器，10分钟后执行
        scheduled_fetch_timer = Timer(10 * 60, delayed_fetch)  # 10分钟 = 600秒
        scheduled_fetch_timer.start()
        print(f"⏰ 已设定10分钟后自动拉取数据")


def fetch_data_for_company(company):
    """为单个公司/门店拉取数据"""
    try:
        import requests
        import json
        import re
        from datetime import datetime
        
        API_URL = "http://bi.gzbbr.com/crmapp_api.get_beihuo"
        
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Authorization': 'Basic YWRtaW46ODA4OA==',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'http://bi.gzbbr.com',
            'Pragma': 'no-cache',
            'Referer': 'http://bi.gzbbr.com/crmapp_api.bh_index',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }

        response = requests.post(
            API_URL,
            data={"company": company},
            headers=headers,
            timeout=120
        )
        
        print(f"📊 {company} 拉取数据API响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"📊 {company} 拉取数据API响应内容类型: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
                
                # 检查响应格式 - 实际API返回的是直接包含'data'的数据，而非标准格式
                if isinstance(result, dict):
                    # 检查是否包含'data'字段，这是实际的响应格式
                    if 'data' in result:
                        # 处理返回的数据
                        data_list = result.get("data", [])
                        if not isinstance(data_list, list):
                            print(f"⚠️ company={company} 返回数据格式异常")
                            return 0

                        # 获取接口返回的更新时间（如果有的话）
                        gx_date = result.get("gx_date", None)
                        print(f"📅 接口数据更新时间 (company={company}): {gx_date}")

                        # 使用与手动拉取相同的字段定义和SQL构造方式
                        FIELDS = [
                            "oe", "今日销量", "供应商", "全国近1个月询价量", "全国近3个月月均询价量",
                            "内部备注", "品牌", "品牌号", "库存数量", "库存金额", "成品可卖天数",
                            "成本价", "昨日销量", "本月销量", "标签", "物料名称", "物料条码",
                            "车型品牌", "近12个月月均销量", "近1个月询价量", "近3个月月均询价量",
                            "近6个月月均销量", "近7天销量", "预警状态", "在途数量", "车型", "company"
                        ]
                        JSON_KEYS = [
                            "OE", "今日销量", "供应商", "全国近1个月询价量", "全国近3个月月均询价量",
                            "内部备注", "品牌", "品牌号", "库存数量", "库存金额", "成品可卖天数",
                            "成本价", "昨日销量", "本月销量", "标签", "物料名称", "物料条码",
                            "车型品牌", "近12个月月均销量", "近1个月询价量", "近3个月月均询价量",
                            "近6个月月均销量", "近7天销量", "预警状态", "在途数量", "车型"
                        ]

                        COLUMNS_STR = ", ".join([f"`{f}`" for f in FIELDS])
                        PLACEHOLDERS_STR = ", ".join(["%s"] * (len(FIELDS) + 1))  # FIELDS数量+1个更新时间
                        UPDATE_SET = ", ".join([f"`{f}` = VALUES(`{f}`)" for f in FIELDS if f != 'id'])
                        UPSERT_SQL = f"""
                        INSERT INTO `crmapp_beihuo` ({COLUMNS_STR}, `更新时间`)
                        VALUES ({PLACEHOLDERS_STR})
                        ON DUPLICATE KEY UPDATE {UPDATE_SET}, `更新时间` = VALUES(`更新时间`)
                        """

                        def clean_data(value):
                            if isinstance(value, str):
                                match = re.search(r'<(\d+)次', value)
                                if match:
                                    return str(int(match.group(1)) - 3)
                            return value

                        # 建立数据库连接并执行插入
                        conn = get_db_connection()
                        cursor = conn.cursor()

                        batch_size = 5000
                        total = len(data_list)
                        processed = 0

                        try:
                            for i in range(0, total, batch_size):
                                batch = data_list[i:i + batch_size]
                                values_batch = []
                                
                                for item in batch:
                                    row = [clean_data(item.get(key)) for key in JSON_KEYS]
                                    row.append(company)
                                    
                                    # 获取当前记录的品牌值和物料条码
                                    current_brand = item.get("品牌", "")
                                    current_barcode = item.get("物料条码", "")
                                    
                                    # 如果品牌是"原厂 SJZX"且物料条码以"P"或"Y"开头，则根据条码前缀修改品牌
                                    if current_brand == "原厂 SJZX":
                                        if current_barcode and current_barcode.startswith("P"):
                                            brand_index = JSON_KEYS.index("品牌")
                                            row[brand_index] = "原厂国内4s件"
                                        elif current_barcode and current_barcode.startswith("Y"):
                                            brand_index = JSON_KEYS.index("品牌")
                                            row[brand_index] = "原厂"
                                    
                                    # 如果品牌是"菲尔"或者"菲尔 FREY"，将物料条码复制到品牌号
                                    if current_brand in ["菲尔", "菲尔 FREY"]:
                                        barcode_index = JSON_KEYS.index("物料条码")
                                        brand_code_index = JSON_KEYS.index("品牌号")
                                        row[brand_code_index] = row[barcode_index]
                                    
                                    # 添加更新时间到每行数据（最后一个元素）
                                    if gx_date:
                                        try:
                                            # 尝试解析日期字符串
                                            if ' ' in gx_date:
                                                parsed_date = datetime.strptime(gx_date, '%Y-%m-%d %H:%M:%S')
                                            else:
                                                parsed_date = datetime.strptime(gx_date, '%Y-%m-%d')
                                            row.append(parsed_date)
                                        except ValueError:
                                            # 如果解析失败，使用当前时间
                                            row.append(datetime.now())
                                    else:
                                        # 如果没有更新时间，使用当前时间
                                        row.append(datetime.now())

                                    values_batch.append(row)

                                cursor.executemany(UPSERT_SQL, values_batch)
                                conn.commit()
                                processed += len(values_batch)

                        except Exception as e:
                            conn.rollback()
                            print(f"❌ 插入/更新失败 (company={company}): {str(e)}")
                            return -1
                        finally:
                            cursor.close()
                            conn.close()

                        print(f"✅ 门店 {company} 数据自动拉取完成，处理了 {processed} 条记录")
                        return processed
                    else:
                        # 如果没有'data'字段，可能返回的是错误信息
                        print(f"❌ API请求失败 (company={company}): 响应中没有'data'字段，响应内容: {result}")
                        return -1
                else:
                    print(f"❌ company={company} 返回的数据格式不是字典: {type(result)}")
                    return -1
            except json.JSONDecodeError:
                # 响应不是JSON格式，检查文本内容
                response_text = response.text
                print(f"📊 {company} 非JSON响应内容: {response_text[:500]}...")
                
                # 检查是否包含成功或正在处理的关键词
                if '正在' in response_text or '处理' in response_text or 'start' in response_text or 'running' in response_text:
                    print(f"✅ 门店 {company} 数据拉取请求已发送（正在后台处理）")
                    return 0  # 表示请求已发送
                else:
                    print(f"❌ {company} 响应无法解析为JSON且不包含处理信息")
                    return -1
        else:
            print(f"❌ API请求失败 (company={company}), 状态码: {response.status_code}")
            print(f"❌ 响应内容: {response.text[:500]}...")
            return -1
        
    except requests.exceptions.Timeout:
        print(f"⏰ 门店 {company} 数据拉取请求超时（可能仍在后台处理）")
        return 0  # 超时情况下假设请求已发送
    except requests.exceptions.RequestException as e:
        print(f"❌ 门店 {company} 拉取网络请求时出错: {str(e)}")
        return -1
    except Exception as e:
        print(f"❌ 门店 {company} 拉取时出错: {str(e)}")
        return -1

def insert_or_update_data(data_list, company, gx_date):
    """插入或更新数据的核心逻辑"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # JSON数据键顺序定义
        JSON_KEYS = [
            '供应商', '品牌', '物料名称', 'OE', '物料条码', '车型品牌', '标签',
            '近1个月询价量', '近3个月月均询价量', '库存数量', '昨日销量', '本月销量', '今日销量',
            '全国近1个月询价量', '全国近3个月月均询价量', '内部备注', '品牌号', '库存金额',
            '成品可卖天数', '成本价', '近12个月月均销量', '近6个月月均销量', '近7天销量',
            '预警状态', '在途数量', '车型'
        ]
        
        # UPSERT SQL语句
        UPSERT_SQL = """
            INSERT INTO crmapp_beihuo (
                `供应商`, `品牌`, `物料名称`, `OE`, `物料条码`, `车型品牌`, `标签`,
                `近1个月询价量`, `近3个月月均询价量`, `库存数量`, `昨日销量`, `本月销量`, `今日销量`,
                `全国近1个月询价量`, `全国近3个月月均询价量`, `内部备注`, `品牌号`, `库存金额`,
                `成品可卖天数`, `成本价`, `近12个月月均销量`, `近6个月月均销量`, `近7天销量`,
                `预警状态`, `在途数量`, `车型`, `company`, `update_time`
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                `供应商`=VALUES(`供应商`), `品牌`=VALUES(`品牌`), `物料名称`=VALUES(`物料名称`),
                `OE`=VALUES(`OE`), `物料条码`=VALUES(`物料条码`), `车型品牌`=VALUES(`车型品牌`),
                `标签`=VALUES(`标签`), `近1个月询价量`=VALUES(`近1个月询价量`),
                `近3个月月均询价量`=VALUES(`近3个月月均询价量`), `库存数量`=VALUES(`库存数量`),
                `昨日销量`=VALUES(`昨日销量`), `本月销量`=VALUES(`本月销量`), `今日销量`=VALUES(`今日销量`),
                `全国近1个月询价量`=VALUES(`全国近1个月询价量`), `全国近3个月月均询价量`=VALUES(`全国近3个月月均询价量`),
                `内部备注`=VALUES(`内部备注`), `品牌号`=VALUES(`品牌号`), `库存金额`=VALUES(`库存金额`),
                `成品可卖天数`=VALUES(`成品可卖天数`), `成本价`=VALUES(`成本价`),
                `近12个月月均销量`=VALUES(`近12个月月均销量`), `近6个月月均销量`=VALUES(`近6个月月均销量`),
                `近7天销量`=VALUES(`近7天销量`), `预警状态`=VALUES(`预警状态`), `在途数量`=VALUES(`在途数量`),
                `车型`=VALUES(`车型`), `company`=VALUES(`company`), `update_time`=VALUES(`update_time`)
        """
        
        batch_size = 5000
        total = len(data_list)
        processed = 0

        for i in range(0, total, batch_size):
            batch = data_list[i:i + batch_size]
            values_batch = []
            
            for item in batch:
                row = [clean_data_date(item.get(key)) for key in JSON_KEYS]
                
                # 添加公司标识和更新时间
                row.append(company)
                
                # 获取当前记录的品牌值和物料条码
                current_brand = item.get("品牌", "")
                current_barcode = item.get("物料条码", "")
                
                # 如果品牌是"原厂 SJZX"且物料条码以"P"或"Y"开头，则根据条码前缀修改品牌
                if current_brand == "原厂 SJZX":
                    if current_barcode and current_barcode.startswith("P"):
                        brand_index = JSON_KEYS.index("品牌")
                        row[brand_index] = "原厂国内4s件"
                    elif current_barcode and current_barcode.startswith("Y"):
                        brand_index = JSON_KEYS.index("品牌")
                        row[brand_index] = "原厂"
                
                # 如果品牌是"菲尔"或者"菲尔 FREY"，将物料条码复制到品牌号
                if current_brand in ["菲尔", "菲尔 FREY"]:
                    barcode_index = JSON_KEYS.index("物料条码")
                    brand_code_index = JSON_KEYS.index("品牌号")
                    row[brand_code_index] = row[barcode_index]
                
                # 添加更新时间到每行数据
                if gx_date:
                    # 尝试解析日期字符串
                    try:
                        # 尝试解析日期字符串
                        if ' ' in gx_date:
                            parsed_date = datetime.strptime(gx_date, '%Y-%m-%d %H:%M:%S')
                        else:
                            parsed_date = datetime.strptime(gx_date, '%Y-%m-%d')
                        row.append(parsed_date)
                    except ValueError:
                        # 如果解析失败，使用当前时间
                        row.append(datetime.now())
                else:
                    # 如果没有更新时间，使用当前时间
                    row.append(datetime.now())

                values_batch.append(row)

            cursor.executemany(UPSERT_SQL, values_batch)
            conn.commit()
            processed += len(values_batch)

        return processed
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ 插入/更新失败 (company={company}): {str(e)}")
        return -1
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# 配置定时任务 - 使用 task_manager
def setup_scheduled_tasks():
    """设置定时任务"""
    # 注册间隔任务（每15分钟）
    task_manager.schedule(
        auto_update_and_fetch,
        'interval',
        'auto_update_interval',
        minutes=15,
        replace_existing=True
    )
    
    print("[任务初始化] 自动更新任务已注册（每15分钟）")


# 清理函数
def cleanup_timers():
    """清理定时器"""
    global scheduled_fetch_timer
    if scheduled_fetch_timer:
        scheduled_fetch_timer.cancel()
        print("⏰ 已取消待执行的延时拉取任务")


# 注册清理函数
atexit.register(cleanup_timers)

#路由====================================================================================================================
@app.route('/')
def index():
    # 检查用户是否已登录
    if 'logged_in' not in session:
        return render_template('login.html')
    return render_template('index.html')

@app.route('/instructions')
def instructions():
    # 检查用户是否已登录
    if 'logged_in' not in session:
        return render_template('login.html')
    return render_template('instructions.html')


# ==================== 任务管理 API ====================

@app.route('/api/tasks/stats')
def get_task_stats():
    """获取任务统计信息"""
    return jsonify(task_manager.get_stats())


@app.route('/api/tasks/jobs')
def get_scheduled_jobs():
    """获取所有定时任务列表"""
    return jsonify(task_manager.get_jobs())


@app.route('/api/tasks/history')
def get_task_history():
    """获取任务执行历史"""
    limit = request.args.get('limit', 20, type=int)
    return jsonify(task_manager.get_history(limit))


@app.route('/api/tasks/jobs/<job_id>/pause', methods=['POST'])
def pause_scheduled_job(job_id):
    """暂停定时任务"""
    success = task_manager.pause_job(job_id)
    if success:
        return jsonify({'code': 0, 'msg': f'任务 {job_id} 已暂停'})
    return jsonify({'code': 1, 'msg': f'暂停任务失败: {job_id}'})


@app.route('/api/tasks/jobs/<job_id>/resume', methods=['POST'])
def resume_scheduled_job(job_id):
    """恢复定时任务"""
    success = task_manager.resume_job(job_id)
    if success:
        return jsonify({'code': 0, 'msg': f'任务 {job_id} 已恢复'})
    return jsonify({'code': 1, 'msg': f'恢复任务失败: {job_id}'})


@app.route('/api/tasks/jobs/<job_id>', methods=['DELETE'])
def delete_scheduled_job(job_id):
    """删除定时任务"""
    success = task_manager.unschedule(job_id)
    if success:
        return jsonify({'code': 0, 'msg': f'任务 {job_id} 已删除'})
    return jsonify({'code': 1, 'msg': f'删除任务失败: {job_id}'})


# ==================== 用户认证 API ====================

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录 - 设置独立的权限字段"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # 获取用户IP地址
    user_ip = request.remote_addr
    
    # 从数据库验证用户
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM crmapp_users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and user['password'] == password:
        session['logged_in'] = True
        session['username'] = username
        session['is_admin'] = user['is_admin']
        session['can_delete_cart'] = user['can_delete_cart']  # 添加删除购物车权限到session
        
        # 对于用户名为"admin"的用户，默认处理单据权限为开启状态
        if username == 'admin':
            session['can_process_orders'] = 1
        else:
            session['can_process_orders'] = user['can_process_orders']  # 添加处理单据权限到session
            
        session['user_id'] = user['id']  # 添加用户ID到session，用于后续权限检查
        # 检查用户store是否有效，如果无效则设置为默认值
        user_store = user['store']
        if not user_store or user_store == 'all' or user_store == 'none' or user_store == 'undefined' or user_store == '':
            user_store = 'fsbbr'  # 设置为默认门店
        session['store'] = user_store
        # 初始化当前组织为用户的默认门店，确保不会设置为'none'或'undefined'等无效值
        session['current_org'] = user_store
        
        # 设置新的独立权限字段（如果数据库中不存在这些字段，则使用默认值）
        session['admin_access'] = user.get('admin_access', user['is_admin'])  # 管理员访问权限（独立于is_admin）
        session['org_switch_access'] = user.get('org_switch_access', user['is_admin'])  # 组织切换权限（独立于is_admin）
        session['can_view_all_data'] = user.get('can_view_all_data', False)
        session['can_export_data'] = user.get('can_export_data', False)
        session['can_modify_prices'] = user.get('can_modify_prices', False)
        
        # 设置板块和职级信息（新增字段）
        session['department'] = user.get('department', None)  # 板块:业务/市场/后勤
        session['job_level'] = user.get('job_level', None)    # 职级:经理/主管/业务员
        
        # 处理允许切换的组织列表
        if user.get('allowed_orgs'):
            try:
                import json
                allowed_orgs = json.loads(user['allowed_orgs'])
                session['allowed_orgs'] = allowed_orgs
            except:
                session['allowed_orgs'] = []
        else:
            session['allowed_orgs'] = []
        
        # 更新IP记录
        update_user_ip_record(user['id'], user_ip)
        
        return jsonify({
            'code': 0, 
            'msg': '登录成功',
            'data': {
                'username': username,
                'is_admin': user['is_admin'],
                'can_delete_cart': user['can_delete_cart'],  # 添加删除购物车权限信息
                'can_process_orders': user['can_process_orders'],
                'store': user_store,  # 返回修复后的store值
                'admin_access': session['admin_access'],  # 新增独立的管理员权限
                'org_switch_access': session['org_switch_access']  # 新增独立的组织切换权限
            }
        })
    else:
        return jsonify({'code': 1, 'msg': '用户名或密码错误'})


def update_user_ip_record(user_id, ip_address):
    """更新用户的IP记录，保留最近的5个IP"""
    import json  # 在函数开始时导入json模块
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 获取当前IP记录
        cursor.execute("SELECT ip_records FROM crmapp_users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            ip_records = json.loads(result[0])
        else:
            ip_records = []
        
        # 检查IP是否已存在，如果存在则移除（避免重复）
        if ip_address in ip_records:
            ip_records.remove(ip_address)
        
        # 将新IP添加到列表开头
        ip_records.insert(0, ip_address)
        
        # 只保留最近的5个IP
        ip_records = ip_records[:5]
        
        # 更新数据库
        cursor.execute(
            "UPDATE crmapp_users SET ip_records = %s WHERE id = %s",
            (json.dumps(ip_records), user_id)
        )
        conn.commit()
    except Exception as e:
        print(f"更新用户IP记录失败: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


# 修改用户API，限制非admin和fsbbr账号对admin和fsbbr账号的操作
@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """修改用户信息"""
    # 检查当前用户权限 - 只有admin和fsbbr账号可以修改用户信息
    current_username = session.get('username')
    if current_username not in ['admin', 'fsbbr']:
        return jsonify({'code': 1, 'msg': '权限不足，只有admin和fsbbr账号可以修改用户信息'}), 403
    
    # 获取目标用户信息
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT username FROM crmapp_users WHERE id = %s", (user_id,))
    target_user = cursor.fetchone()
    
    if not target_user:
        conn.close()
        return jsonify({'code': 1, 'msg': '用户不存在'}), 404
    
    target_username = target_user['username']
    
    # 检查是否尝试修改admin账号，只有admin账号可以修改admin账号
    if target_username == 'admin':
        if current_username != 'admin':
            conn.close()
            return jsonify({'code': 1, 'msg': '权限不足，只有admin账号可以修改管理员账号'}), 403
    
    # 原有的更新用户逻辑
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin')
    can_delete_cart = data.get('can_delete_cart')
    can_process_orders = data.get('can_process_orders') 
    store = data.get('store')
    allowed_orgs = data.get('allowed_orgs')  # 新增：允许切换的组织列表
    department = data.get('department')  # 板块:业务/市场/后勤
    job_level = data.get('job_level')    # 职级:经理/主管/业务员

    # 验证板块和职级的有效值（如果提供了的话）
    if department is not None:
        valid_departments = ['业务', '市场', '后勤']
        if department and department not in valid_departments:
            conn.close()
            return jsonify({'code': 1, 'msg': f'板块必须是以下之一: {", ".join(valid_departments)}'}), 400
    if job_level is not None:
        valid_job_levels = ['经理', '主管', '业务员']
        if job_level and job_level not in valid_job_levels:
            conn.close()
            return jsonify({'code': 1, 'msg': f'职级必须是以下之一: {", ".join(valid_job_levels)}'}), 400

    # 更新用户信息
    try:
        update_fields = []
        params = []
        
        if username is not None:
            update_fields.append("username = %s")
            params.append(username)
        if password is not None:
            update_fields.append("password = %s")
            params.append(password)
        if is_admin is not None:
            update_fields.append("is_admin = %s")
            params.append(is_admin)
        if can_delete_cart is not None:
            update_fields.append("can_delete_cart = %s")
            params.append(can_delete_cart)
        if can_process_orders is not None: 
            update_fields.append("can_process_orders = %s")
            params.append(can_process_orders)
        if store is not None:
            update_fields.append("store = %s")
            params.append(store)
        if allowed_orgs is not None:
            import json
            allowed_orgs_json = json.dumps(allowed_orgs) if allowed_orgs else None
            update_fields.append("allowed_orgs = %s")
            params.append(allowed_orgs_json)
        if department is not None:
            update_fields.append("department = %s")
            params.append(department)
        if job_level is not None:
            update_fields.append("job_level = %s")
            params.append(job_level)
        
        if update_fields:
            sql = f"UPDATE crmapp_users SET {', '.join(update_fields)} WHERE id = %s"
            params.append(user_id)
            cursor.execute(sql, params)
            conn.commit()
            print(f"✅ 用户 {target_username} 信息更新成功")
        else:
            print("ℹ️ 没有提供需要更新的字段")
    except Exception as e:
        import traceback
        print(f"❌ 更新用户信息失败: {str(e)}")
        print(traceback.format_exc())
        conn.rollback()
        return jsonify({'code': 1, 'msg': f'更新失败: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
    
    return jsonify({'code': 0, 'msg': '更新成功'})



# 修改删除用户API，限制非admin和fsbbr账号对admin和fsbbr账号的操作
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """删除用户"""
    current_username = session.get('username')
    
    # 检查当前用户是否有权限执行此操作
    if current_username not in ['admin', 'fsbbr']:
        return jsonify({'code': 1, 'msg': '权限不足，只有admin和fsbbr账号可以删除用户'}), 403
    
    # 获取目标用户信息
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT username FROM crmapp_users WHERE id = %s", (user_id,))
    target_user = cursor.fetchone()
    
    if not target_user:
        conn.close()
        return jsonify({'code': 1, 'msg': '用户不存在'}), 404
    
    target_username = target_user['username']
    
    # 检查是否尝试删除admin或fsbbr账号
    if target_username in ['admin', 'fsbbr']:
        # 只有admin账号可以删除admin和fsbbr账号
        if current_username != 'admin':
            conn.close()
            return jsonify({'code': 1, 'msg': '权限不足，只有admin账号可以删除管理员账号'}), 403
    
    # 不能删除自己
    if target_username == current_username:
        conn.close()
        return jsonify({'code': 1, 'msg': '不能删除自己的账号'}), 400
    
    try:
        cursor.execute("DELETE FROM crmapp_users WHERE id = %s", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'msg': '用户删除成功'})
    except Exception as e:
        conn.close()
        return jsonify({'code': 1, 'msg': f'删除用户失败: {str(e)}'}), 500


# 添加登出API接口
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'code': 0, 'msg': '退出成功'})

@app.route('/api/beihuo')
@login_required
def api_beihuo():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    offset = (page - 1) * limit

    # 获取排序参数
    field = request.args.get('field', '').strip() or None
    order = request.args.get('order', '').strip() or None

    print(f"Debug - 接收到排序参数: field={field}, order={order}")  # 调试信息

    # 获取搜索条件并处理多行输入
    oe = request.args.get('oe', '').strip()
    supplier = request.args.get('supplier', '').strip()
    brand = request.args.get('brand', '').strip()
    material_name = request.args.get('material_name', '').strip()
    tag = request.args.get('tag', '').strip()
    barcode = request.args.get('barcode', '').strip()
    car_brand = request.args.get('car_brand', '').strip()
    brand_code = request.args.get('brand_code', '').strip()  # 添加品牌号搜索条件
    
    # 处理多行搜索：只有oe，物料名称，物料条码，品牌号需要多行搜索
    oe_list = process_oe_search(oe)  # 使用新的OE处理函数
    material_name_list = process_material_name_search(material_name)  # 使用新的物料名称处理函数
    barcode_list = process_barcode_search(barcode)  # 使用新的条码处理函数
    brand_code_list = [item.strip() for item in brand_code.split('\n') if item.strip()] if '\n' in brand_code else ([brand_code] if brand_code else [])
    
    # 对于其他字段，不再使用多行搜索，仅保留原始值
    supplier_list = [supplier] if supplier else []
    brand_list = [brand] if brand else []
    tag_list = [tag] if tag else []
    car_brand_list = [car_brand] if car_brand else []

    # 数值比较条件
    inquiry_1m_op = request.args.get('inquiry_1m_op', '')
    inquiry_1m_val = request.args.get('inquiry_1m_val', '').strip() or None
    inquiry_3m_op = request.args.get('inquiry_3m_op', '')
    inquiry_3m_val = request.args.get('inquiry_3m_val', '').strip() or None
    stock_op = request.args.get('stock_op', '')
    stock_val = request.args.get('stock_val', '').strip() or None
    sales_yesterday_op = request.args.get('sales_yesterday_op', '')
    sales_yesterday_val = request.args.get('sales_yesterday_val', '').strip() or None
    sales_month_op = request.args.get('sales_month_op', '')
    sales_month_val = request.args.get('sales_month_val', '').strip() or None
    today_sales_op = request.args.get('today_sales_op', '')
    today_sales_val = request.args.get('today_sales_val', '').strip() or None
    sales_today_op = request.args.get('sales_today_op', '')
    sales_today_val = request.args.get('sales_today_val', '').strip() or None
    national_inquiry_1m_op = request.args.get('national_inquiry_1m_op', '')
    national_inquiry_1m_val = request.args.get('national_inquiry_1m_val', '').strip() or None
    national_inquiry_3m_op = request.args.get('national_inquiry_3m_op', '')
    national_inquiry_3m_val = request.args.get('national_inquiry_3m_val', '').strip() or None
    avg_sales_12m_op = request.args.get('avg_sales_12m_op', '')
    avg_sales_12m_val = request.args.get('avg_sales_12m_val', '').strip() or None
    avg_sales_6m_op = request.args.get('avg_sales_6m_op', '')
    avg_sales_6m_val = request.args.get('avg_sales_6m_val', '').strip() or None
    sales_7d_op = request.args.get('sales_7d_op', '')
    sales_7d_val = request.args.get('sales_7d_val', '').strip() or None

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 构建查询条件
    where_parts = []
    params = []

    # 根据用户权限过滤数据 - 统一使用get_user_store()获取当前门店
    current_store = get_user_store()  # 使用统一的函数获取当前用户门店
    where_parts.append("`company` = %s")
    params.append(current_store)

    print(f"Debug - Field: {field}, Order: {order}")  # 调试信息
    print(f"Debug - Where clause: {where_parts}")  # 调试信息
    print(f"Debug - Params: {params}")  # 调试信息

    # 处理搜索参数
    if oe_list:
        # 为OE列表中的每个值创建 OR 条件
        or_conditions = []
        for item in oe_list:
            or_conditions.append("`oe` LIKE %s")
            params.append(f"%{item}%")
        if or_conditions:
            where_parts.append("(" + " OR ".join(or_conditions) + ")")
    
    if supplier_list:
        # 为供应商列表中的每个值创建 OR 条件
        or_conditions = []
        for item in supplier_list:
            or_conditions.append("`供应商` LIKE %s")
            params.append(f"%{item}%")
        if or_conditions:
            where_parts.append("(" + " OR ".join(or_conditions) + ")")
    
    if brand_list:
        # 为品牌列表中的每个值创建 OR 条件
        or_conditions = []
        for item in brand_list:
            or_conditions.append("`品牌` = %s")
            params.append(item)
        if or_conditions:
            where_parts.append("(" + " OR ".join(or_conditions) + ")")
    
    if material_name_list or brand_code_list:
        # 为物料名称或品牌号列表中的每个值创建 OR 条件
        or_conditions = []
        for item in material_name_list:
            or_conditions.append("`物料名称` LIKE %s")
            params.append(f"%{item}%")
        for item in brand_code_list:
            or_conditions.append("`品牌号` LIKE %s")
            params.append(f"%{item}%")
        if or_conditions:
            where_parts.append("(" + " OR ".join(or_conditions) + ")")
    
    if tag_list:
        # 为标签列表中的每个值创建 OR 条件
        or_conditions = []
        for item in tag_list:
            or_conditions.append("`标签` = %s")
            params.append(item)
        if or_conditions:
            where_parts.append("(" + " OR ".join(or_conditions) + ")")
    
    if barcode_list:
        # 为物料条码列表中的每个值创建 OR 条件
        or_conditions = []
        for item in barcode_list:
            or_conditions.append("(`物料条码` LIKE %s OR `品牌号` LIKE %s)")
            params.extend([f"%{item}%", f"%{item}%"])
        if or_conditions:
            where_parts.append("(" + " OR ".join(or_conditions) + ")")
    
    if car_brand_list:
        # 为车型品牌列表中的每个值创建 OR 条件
        or_conditions = []
        for item in car_brand_list:
            or_conditions.append("`车型品牌` = %s")
            params.append(item)
        if or_conditions:
            where_parts.append("(" + " OR ".join(or_conditions) + ")")

    # 处理数值比较条件
    if inquiry_1m_val is not None and inquiry_1m_op:
        where_parts.append(f"`近1个月询价量` {inquiry_1m_op} %s")
        params.append(inquiry_1m_val)
    if inquiry_3m_val is not None and inquiry_3m_op:
        where_parts.append(f"`近3个月月均询价量` {inquiry_3m_op} %s")
        params.append(inquiry_3m_val)
    if stock_val is not None and stock_op:
        where_parts.append(f"`库存数量` {stock_op} %s")
        params.append(stock_val)
    if sales_yesterday_val is not None and sales_yesterday_op:
        where_parts.append(f"`昨日销量` {sales_yesterday_op} %s")
        params.append(sales_yesterday_val)
    if sales_month_val is not None and sales_month_op:
        where_parts.append(f"`本月销量` {sales_month_op} %s")
        params.append(sales_month_val)
    if today_sales_val is not None and today_sales_op:
        where_parts.append(f"`今日销量` {today_sales_op} %s")
        params.append(today_sales_val)
    if sales_today_val is not None and sales_today_op:
        where_parts.append(f"`今日销量` {sales_today_op} %s")
        params.append(sales_today_val)
    if national_inquiry_1m_val is not None and national_inquiry_1m_op:
        where_parts.append(f"`全国近1个月询价量` {national_inquiry_1m_op} %s")
        params.append(national_inquiry_1m_val)
    if national_inquiry_3m_val is not None and national_inquiry_3m_op:
        where_parts.append(f"`全国近3个月月均询价量` {national_inquiry_3m_op} %s")
        params.append(national_inquiry_3m_val)
    if avg_sales_12m_val is not None and avg_sales_12m_op:
        where_parts.append(f"`近12个月月均销量` {avg_sales_12m_op} %s")
        params.append(avg_sales_12m_val)
    if avg_sales_6m_val is not None and avg_sales_6m_op:
        where_parts.append(f"`近6个月月均销量` {avg_sales_6m_op} %s")
        params.append(avg_sales_6m_val)
    if sales_7d_val is not None and sales_7d_op:
        where_parts.append(f"`近7天销量` {sales_7d_op} %s")
        params.append(sales_7d_val)

    where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

    print(f"Debug - Field: {field}, Order: {order}")  # 调试信息
    print(f"Debug - Where clause: {where_clause}")  # 调试信息
    print(f"Debug - Params: {params}")  # 调试信息

    # 处理排序
    order_clause = ""
    if field and order:
        # 字段映射，确保安全
        field_mapping = {
            '物料名称': '`物料名称`',
            '品牌': '`品牌`',
            '物料条码': '`物料条码`',
            'oe': '`oe`',
            '车型品牌': '`车型品牌`',
            '标签': '`标签`',
            '库存金额': '`库存金额`',
            '成本价': '`成本价`',
            '库存数量': '`库存数量`',
            '近12个月月均销量': '`近12个月月均销量`',
            '近6个月月均销量': '`近6个月月均销量`',
            '本月销量': '`本月销量`',
            '近7天销量': '`近7天销量`',
            '昨日销量': '`昨日销量`',
            '今日销量': '`今日销量`',
            '成品可卖天数': '`成品可卖天数`',
            '预警状态': '`预警状态`',
            '供应商': '`供应商`',
            '近1个月询价量': '`近1个月询价量`',
            '近3个月月均询价量': '`近3个月月均询价量`',
            '全国近1个月询价量': '`全国近1个月询价量`',
            '全国近3个月月均询价量': '`全国近3个月月均询价量`',
            '品牌号': '`品牌号`',
            '内部备注': '`内部备注`'
        }
        
        # 检查是否需要对特殊格式数据进行排序处理
        special_numeric_fields = ['近1个月询价量', '近3个月月均询价量', '近12个月月均销量', '近6个月月均销量', '近7天销量', '库存数量', '在途数量', '昨日销量', '本月销量', '今日销量', '全国近1个月询价量', '全国近3个月月均询价量', '成品可卖天数', '成本价', '库存金额']
        if field in field_mapping:
            order_direction = "ASC" if order.lower() == "asc" else "DESC"
            
            # 如果是需要特殊处理的字段，使用CASE语句进行数值转换排序
            if field in special_numeric_fields:
                order_clause = f"""ORDER BY CASE 
                    WHEN {field_mapping[field]} REGEXP '^<[0-9]+次$' 
                        THEN CAST(SUBSTRING({field_mapping[field]}, 2, CHAR_LENGTH({field_mapping[field]}) - 3) AS DECIMAL) - 1 
                    WHEN {field_mapping[field]} REGEXP '^>[0-9]+次$' 
                        THEN CAST(SUBSTRING({field_mapping[field]}, 2, CHAR_LENGTH({field_mapping[field]}) - 2) AS DECIMAL) + 1 
                    WHEN {field_mapping[field]} REGEXP '^[0-9]+次$'
                        THEN CAST(SUBSTRING({field_mapping[field]}, 1, CHAR_LENGTH({field_mapping[field]}) - 1) AS DECIMAL)
                    ELSE CAST({field_mapping[field]} AS DECIMAL)  -- 将非特殊格式的值转换为DECIMAL类型进行排序
                END {order_direction}"""
            else:
                order_clause = f"ORDER BY {field_mapping[field]} {order_direction}"
        else:
            # 如果字段不在映射中，使用默认排序
            order_clause = "ORDER BY CASE WHEN `oe` IS NULL OR `oe` = '' THEN 1 ELSE 0 END, `oe`"
    else:
        # 如果没有指定排序，则使用默认排序
        order_clause = "ORDER BY CASE WHEN `oe` IS NULL OR `oe` = '' THEN 1 ELSE 0 END, `oe`"

    # 获取总记录数
    count_sql = f"SELECT COUNT(*) AS total FROM crmapp_beihuo {where_clause}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()['total']

    # 计算总页数（用于后端排序）
    total_pages = math.ceil(total / limit) if limit > 0 else 1

    # 如果需要后端排序（排序字段在特殊字段中），则获取所有数据进行排序
    if field and field in ['近1个月询价量', '近3个月月均询价量', '近12个月月均销量', '近6个月月均销量', '近7天销量', '库存数量', '在途数量', '昨日销量', '本月销量', '今日销量', '全国近1个月询价量', '全国近3个月月均询价量', '成品可卖天数', '成本价']:
        print(f"Debug - Starting backend sorting for field: {field}")  # 调试信息
        
        # 获取所有符合条件的数据
        all_data_sql = f"""
            SELECT `物料名称`, `品牌`, `物料条码`, `oe`, `车型品牌`, `标签`, `库存金额`, `成本价`, 
                `库存数量`, `近12个月月均销量`, `近6个月月均销量`, `本月销量`, `近7天销量`, 
                `昨日销量`, `今日销量`, `成品可卖天数`, `预警状态`, `供应商`, `近1个月询价量`, 
                `近3个月月均询价量`, `全国近1个月询价量`, `全国近3个月月均询价量`, 
                `品牌号`, `内部备注`, `company`, `在途数量`, `车型`
            FROM crmapp_beihuo
            {where_clause}
            ORDER BY `oe`  -- 使用一个稳定排序避免结果顺序变化
        """
        print(f"Debug - All data SQL: {all_data_sql}")  # 调试信息
        cursor.execute(all_data_sql, params)
        all_rows = cursor.fetchall()
        
        print(f"Debug - Total rows to sort: {len(all_rows)}")  # 调试信息
        
        # 应用后端排序
        if field in all_rows[0] if all_rows else []:
            reverse = order.lower() == "desc"
            all_rows.sort(key=lambda x: extract_numeric_value(x[field]) if x[field] else 0, reverse=reverse)
        
        # 应用分页
        start_index = offset
        end_index = start_index + limit
        paginated_rows = all_rows[start_index:end_index]
        
        result = paginated_rows
    else:
        # 使用数据库排序和分页
        sql = f"""
            SELECT `物料名称`, `品牌`, `物料条码`, `oe`, `车型品牌`, `标签`, `库存金额`, `成本价`, 
                `库存数量`, `近12个月月均销量`, `近6个月月均销量`, `本月销量`, `近7天销量`, 
                `昨日销量`, `今日销量`, `成品可卖天数`, `预警状态`, `供应商`, `近1个月询价量`, 
                `近3个月月均询价量`, `全国近1个月询价量`, `全国近3个月月均询价量`, 
                `品牌号`, `内部备注`, `company`, `在途数量`, `车型`
            FROM crmapp_beihuo
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        cursor.execute(sql, params)
        result = cursor.fetchall()

    # 添加调试信息
    print(f"Debug - SQL查询: {sql if 'sql' in locals() else 'Backend sorted'}")
    print(f"Debug - 参数: {params[:-2] if len(params) >= 2 else params}")
    print(f"Debug - 查询结果数量: {len(result)}")

    # 添加数据处理逻辑以合并销量字段
    for row in result:
        # 合并销量字段为一个格式化字符串
        today_sales = row.get('今日销量', 0) or 0
        yesterday_sales = row.get('昨日销量', 0) or 0
        sales_7d = row.get('近7天销量', 0) or 0
        sales_month = row.get('本月销量', 0) or 0
        avg_sales_6m = row.get('近6个月月均销量', 0) or 0
        avg_sales_12m = row.get('近12个月月均销量', 0) or 0
        
        # 创建合并的销量数据
        sales_text = f"今/昨/近7天:{today_sales}/{yesterday_sales}/{sales_7d};\n近1/6/12:{sales_month}/{avg_sales_6m}/{avg_sales_12m};"
        row['sales_data'] = sales_text

    conn.close()
    return jsonify({
        'code': 0,
        'msg': '',
        'count': total,
        'data': result
    })

# 获取品牌列表
@app.route('/api/brands')
@login_required
def api_brands():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    # 根据用户权限决定查询条件
    if session.get('is_admin'):
        # 管理员获取所有门店的品牌
        cursor.execute("SELECT DISTINCT `品牌` FROM crmapp_beihuo WHERE `品牌` IS NOT NULL AND `品牌` != '' ORDER BY `品牌`")
    else:
        # 普通用户只获取自己门店的品牌
        cursor.execute("SELECT DISTINCT `品牌` FROM crmapp_beihuo WHERE `品牌` IS NOT NULL AND `品牌` != '' AND `company` = %s ORDER BY `品牌`", (get_user_store(),))
    
    result = cursor.fetchall()
    brands = [row['品牌'] for row in result if row['品牌']]
    
    conn.close()
    return jsonify({'code': 0, 'data': brands})

# 获取标签列表
@app.route('/api/tags')
@login_required
def api_tags():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    if session.get('is_admin'):
        # 管理员获取所有门店的标签
        cursor.execute("SELECT DISTINCT `标签` FROM crmapp_beihuo WHERE `标签` IS NOT NULL AND `标签` != '' ORDER BY `标签`")
    else:
        # 普通用户只获取自己门店的标签
        cursor.execute("SELECT DISTINCT `标签` FROM crmapp_beihuo WHERE `标签` IS NOT NULL AND `标签` != '' AND `company` = %s ORDER BY `标签`", (get_user_store(),))
    
    result = cursor.fetchall()
    tags = [row['标签'] for row in result if row['标签']]
    
    conn.close()
    return jsonify({'code': 0, 'data': tags})

# 获取车型品牌列表
@app.route('/api/car_brands')
@login_required
def api_car_brands():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    # 根据用户权限决定查询条件
    if session.get('is_admin'):
        # 管理员获取所有门店的车型品牌
        cursor.execute("SELECT DISTINCT `车型品牌` FROM crmapp_beihuo WHERE `车型品牌` IS NOT NULL AND `车型品牌` != '' ORDER BY `车型品牌`")
    else:
        # 普通用户只获取自己门店的车型品牌
        cursor.execute("SELECT DISTINCT `车型品牌` FROM crmapp_beihuo WHERE `车型品牌` IS NOT NULL AND `车型品牌` != '' AND `company` = %s ORDER BY `车型品牌`", (get_user_store(),))
    
    result = cursor.fetchall()
    car_brands = [row['车型品牌'] for row in result if row['车型品牌']]
    
    conn.close()
    return jsonify({'code': 0, 'data': car_brands})


@app.route('/api/cart', methods=['GET'])
@login_required
def get_cart():
    """获取购物车数据 - 集成自动清理功能"""
    try:
        # 获取当前用户门店 - 统一使用 get_user_store() 函数
        current_store = get_user_store()
        is_admin = session.get('is_admin', False)
        
        # ========== 新增：调用新的请求处理器（包含自动清理）==========
        from app.services.cart_service.cart_request_handler import CartRequestHandler
        handler = CartRequestHandler()
        result = handler.handle_get_cart_request(current_store, is_admin, request.args)
        
        # 直接返回处理结果（已包含所有原有功能）
        return jsonify({
            'code': result['code'],
            'msg': result['msg'],
            'count': result['count'],
            'data': result['data']
        })
        # =======================================================
        
    except Exception as e:
        print(f"Debug - Cart Error: {str(e)}")  # 添加错误调试信息
        import traceback
        print(f"Debug - Full traceback: {traceback.format_exc()}")  # 添加完整堆栈跟踪
        return jsonify({'code': 1, 'msg': f'获取购物车数据失败：{str(e)}'})

    

def parse_supplier_string(supplier_str):
    if not supplier_str or not isinstance(supplier_str, str):
        return [(supplier_str, "N/A")]
    
    # 按换行符分割供应商信息，而不是按空格
    supplier_parts = supplier_str.split('\n')
    
    suppliers = []
    for part in supplier_parts:
        part = part.strip()  # 去除首尾空白字符
        if not part:
            continue  # 跳过空字符串
        
        # 查找冒号分隔的供应商名称和价格
        colon_index = part.rfind('：')  # 使用中文冒号
        if colon_index != -1:
            name = part[:colon_index]
            price = part[colon_index+1:]
            suppliers.append((name, price))
        else:
            # 如果没有找到冒号，整个部分作为供应商名称
            suppliers.append((part, "N/A"))
    
    return suppliers if suppliers else [(supplier_str, "N/A")]

def extract_numeric_value(value):
    """从字符串中提取数值，用于排序"""
    if value is None:
        return 0
    
    # 如果已经是数字，直接返回
    if isinstance(value, (int, float)):
        return value
    
    # 如果是字符串，尝试提取数字
    str_value = str(value)
    
    # 处理特殊格式的数值（如"<10次", ">50次", "25次"等）
    import re
    match = re.search(r'([<>]?)(\d+\.?\d*)', str_value)
    if match:
        operator, number = match.groups()
        number = float(number)
        
        if operator == '<':
            return number - 1  # 小于号的值视为比该数小1
        elif operator == '>':
            return number + 1  # 大于号的值视为比该数大1
        else:
            return number  # 直接是数字的情况
    else:
        # 如果没有找到数字，尝试直接转换为数字
        try:
            return float(str_value)
        except ValueError:
            # 如果转换失败，返回0
            return 0



def get_cart_items_with_dimension(store, is_admin, dimension='product'):
    """获取购物车数据的辅助函数，支持维度参数 - 优化性能"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 统一使用传入的store参数，确保门店数据隔离
    sql = "SELECT * FROM crmapp_cart WHERE store = %s ORDER BY added_time DESC"
    cursor.execute(sql, (store,))

    result = cursor.fetchall()
    
    # 如果购物车数据为空，直接返回
    if not result:
        conn.close()
        return result

    # 提取所有购物车项目的物料条码
    barcodes = [item['barcode'] for item in result if item['barcode']]
    
    # 批量更新购物车数据
    if barcodes:
        # 构建查询语句
        placeholders = ','.join(['%s'] * len(barcodes))
        update_sql = f"""
            SELECT `供应商`, `品牌`, `物料名称`, `物料条码`, `车型品牌`, `标签`, 
                   `近1个月询价量`, `近3个月月均询价量`, `库存数量`, `昨日销量`, `本月销量`, `今日销量`,
                   `全国近1个月询价量`, `全国近3个月月均询价量`, `内部备注`, `品牌号`, `库存金额`,
                   `成品可卖天数`, `成本价`, `近12个月月均销量`, `近6个月月均销量`, `近7天销量`, 
                   `预警状态`, `在途数量`, `车型`
            FROM crmapp_beihuo 
            WHERE `物料条码` IN ({placeholders}) AND `company` = %s
        """
        cursor.execute(update_sql, barcodes + [store])
        latest_data_list = cursor.fetchall()
        
        # 构建条码到最新数据的映射
        latest_data_map = {item['物料条码']: item for item in latest_data_list}
        
        # 准备批量更新数据
        update_data_for_batch = []
        for item in result:
            barcode = item['barcode']
            if barcode in latest_data_map:
                latest_data = latest_data_map[barcode]
                update_data_for_batch.append((
                    latest_data['供应商'], latest_data['品牌'], latest_data['物料名称'],
                    latest_data['车型品牌'], latest_data['标签'], latest_data['近1个月询价量'],
                    latest_data['近3个月月均询价量'], latest_data['库存数量'], latest_data['昨日销量'],
                    latest_data['本月销量'], latest_data['今日销量'], latest_data['全国近1个月询价量'],
                    latest_data['全国近3个月月均询价量'], latest_data['内部备注'], latest_data['品牌号'],
                    latest_data['库存金额'], latest_data['成品可卖天数'], latest_data['成本价'],
                    latest_data['近12个月月均销量'], latest_data['近6个月月均销量'], 
                    latest_data['近7天销量'], latest_data['预警状态'], latest_data['在途数量'],
                    latest_data['车型'], barcode, store
                ))
        
        # 批量更新购物车表中的数据
        if update_data_for_batch:
            update_cart_sql = """
                UPDATE crmapp_cart 
                SET supplier = %s, brand = %s, material_name = %s, car_brand = %s, tag = %s,
                    inquiry_1m = %s, inquiry_3m = %s, stock = %s, sales_yesterday = %s, 
                    sales_month = %s, today_sales = %s, national_inquiry_1m = %s, 
                    national_inquiry_3m = %s, internal_remarks = %s, brand_code = %s, 
                    stock_amount = %s, sellable_days = %s, cost_price = %s, 
                    avg_sales_12m = %s, avg_sales_6m = %s, sales_7d = %s, 
                    warning_status = %s, on_way = %s, car_model = %s
                WHERE barcode = %s AND store = %s
            """
            cursor.executemany(update_cart_sql, update_data_for_batch)
            conn.commit()
        
        # 更新结果列表中的数据
        for item in result:
            barcode = item['barcode']
            if barcode in latest_data_map:
                latest_data = latest_data_map[barcode]
                item['supplier'] = latest_data['供应商']
                item['brand'] = latest_data['品牌']
                item['material_name'] = latest_data['物料名称']
                item['car_brand'] = latest_data['车型品牌']
                item['tag'] = latest_data['标签']
                item['inquiry_1m'] = latest_data['近1个月询价量']
                item['inquiry_3m'] = latest_data['近3个月月均询价量']
                item['stock'] = latest_data['库存数量']
                item['sales_yesterday'] = latest_data['昨日销量']
                item['sales_month'] = latest_data['本月销量']
                item['today_sales'] = latest_data['今日销量']
                item['national_inquiry_1m'] = latest_data['全国近1个月询价量']
                item['national_inquiry_3m'] = latest_data['全国近3个月月均询价量']
                item['internal_remarks'] = latest_data['内部备注']
                item['brand_code'] = latest_data['品牌号']
                item['stock_amount'] = latest_data['库存金额']
                item['sellable_days'] = latest_data['成品可卖天数']
                item['cost_price'] = latest_data['成本价']
                item['avg_sales_12m'] = latest_data['近12个月月均销量']
                item['avg_sales_6m'] = latest_data['近6个月月均销量']
                item['sales_7d'] = latest_data['近7天销量']
                item['warning_status'] = latest_data['预警状态']
                item['on_way'] = latest_data['在途数量']
                item['car_model'] = latest_data['车型']

    # 添加数据处理逻辑以合并销量字段
    for item in result:
        today_sales = item.get('today_sales', 0) or 0
        yesterday_sales = item.get('sales_yesterday', 0) or 0
        sales_7d = item.get('sales_7d', 0) or 0
        sales_month = item.get('sales_month', 0) or 0
        avg_sales_6m = item.get('avg_sales_6m', 0) or 0
        avg_sales_12m = item.get('avg_sales_12m', 0) or 0
        
        sales_text = f"今/昨/近7天:{today_sales}/{yesterday_sales}/{sales_7d};\n近1/6/12:{sales_month}/{avg_sales_6m}/{avg_sales_12m};"
        item['sales_data'] = sales_text

    # 确保时间格式正确
    for item in result:
        if isinstance(item['added_time'], datetime):
            item['added_time'] = item['added_time'].strftime('%Y-%m-%d %H:%M:%S')

    # 如果是供应商维度，拆分供应商数据
    if dimension == 'supplier':
        expanded_result = []
        for item in result:
            suppliers = parse_supplier_string(item['supplier'])
            for supplier_info in suppliers:
                supplier_name, price = supplier_info
                supplier_item = item.copy()
                supplier_item['supplier'] = f"{supplier_name}: {price}"
                
                today_sales = supplier_item.get('today_sales', 0) or 0
                yesterday_sales = supplier_item.get('sales_yesterday', 0) or 0
                sales_7d = supplier_item.get('sales_7d', 0) or 0
                sales_month = supplier_item.get('sales_month', 0) or 0
                avg_sales_6m = supplier_item.get('avg_sales_6m', 0) or 0
                avg_sales_12m = supplier_item.get('avg_sales_12m', 0) or 0
                
                sales_text = f"今/昨/近7天:{today_sales}/{yesterday_sales}/{sales_7d};\n近1/6/12:{sales_month}/{avg_sales_6m}/{avg_sales_12m};"
                supplier_item['sales_data'] = sales_text
                expanded_result.append(supplier_item)
        result = expanded_result

    conn.close()
    return result

@app.route('/api/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    """添加商品到购物车 - 根据 OE 和条码从备货表获取完整数据"""
    try:
        data = request.get_json()
        item_details = data.get('item_details', [])

        if not item_details:
            return jsonify({'code': 1, 'msg': '没有要添加的商品'}), 400

        # 获取当前用户门店
        store = get_user_store()
        
        # ========== 从 beihuo 表批量查询完整商品数据 ==========
        # 构建批量查询条件
        oe_barcode_pairs = []
        for item in item_details:
            if isinstance(item, dict) and item.get('oe'):
                oe = item.get('oe', '')
                barcode = item.get('barcode', '')
                oe_barcode_pairs.append((oe, barcode))
        
        complete_items = []
        if oe_barcode_pairs:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 构建批量查询的 WHERE 子句
            conditions = []
            params = [store]
            for oe, barcode in oe_barcode_pairs:
                conditions.append("(oe = %s AND 物料条码 = %s)")
                params.extend([oe, barcode])
            
            where_clause = " OR ".join(conditions)
            query_sql = f"""
                SELECT * FROM crmapp_beihuo 
                WHERE company = %s AND ({where_clause})
            """
            
            cursor.execute(query_sql, params)
            beihuo_data_list = cursor.fetchall()
            conn.close()
            
            # 构建字典便于查找
            beihuo_dict = {}
            for beihuo_data in beihuo_data_list:
                oe_val = beihuo_data['oe'] if 'oe' in beihuo_data else ''
                barcode_val = beihuo_data['物料条码'] if '物料条码' in beihuo_data else ''
                key = (oe_val, barcode_val)
                beihuo_dict[key] = beihuo_data
            
            # 字段映射配置：备货表键名 -> (购物车字段名，默认值)
            field_config = [
                ('oe', 'oe', ''),
                ('供应商', 'supplier', ''),
                ('品牌', 'brand', ''),
                ('物料名称', 'material_name', ''),
                ('物料条码', 'barcode', ''),
                ('车型品牌', 'car_brand', ''),
                ('标签', 'tag', ''),
                ('近1个月询价量', 'inquiry_1m', 0),
                ('近3个月月均询价量', 'inquiry_3m', 0),
                ('库存数量', 'stock', 0),
                ('昨日销量', 'sales_yesterday', 0),
                ('本月销量', 'sales_month', 0),
                ('今日销量', 'today_sales', 0),
                ('全国近1个月询价量', 'national_inquiry_1m', 0),
                ('全国近3个月月均询价量', 'national_inquiry_3m', 0),
                ('内部备注', 'internal_remarks', ''),
                ('品牌号', 'brand_code', ''),
                ('库存金额', 'stock_amount', 0.0),
                ('成品可卖天数', 'sellable_days', 0),
                ('成本价', 'cost_price', 0.0),
                ('近12个月月均销量', 'avg_sales_12m', 0),
                ('近6个月月均销量', 'avg_sales_6m', 0),
                ('近7天销量', 'sales_7d', 0),
                ('预警状态', 'warning_status', ''),
                ('在途数量', 'on_way', 0),
                ('车型', 'car_model', '')
            ]
            
            # 匹配并转换数据
            for oe, barcode in oe_barcode_pairs:
                key = (oe, barcode)
                if key not in beihuo_dict:
                    continue
                
                beihuo_data = beihuo_dict[key]
                
                # ========== 关键修复：双重字典映射 ==========
                # 创建两个字典：一个保留原始键名，一个去除所有空白字符
                original_data = dict(beihuo_data)  # 保留原始键名
                normalized_data = {}
                for raw_k, raw_v in beihuo_data.items():
                    # 去除所有空白字符（空格、制表符等）
                    clean_k = ''.join(str(raw_k).split())
                    normalized_data[clean_k] = raw_v
                
                # 辅助函数：从两个字典中查找值
                def find_value(key):
                    # 先在原始字典找
                    if key in original_data:
                        return original_data[key]
                    # 再在标准化字典找
                    if key in normalized_data:
                        return normalized_data[key]
                    return None
                
                # 构建购物车数据
                complete_item = {}
                
                # 特殊处理：今日销售如果存在且非 NULL，覆盖今日销量
                today_sales_val = find_value('今日销售')
                if today_sales_val is not None:
                    complete_item['today_sales'] = int(today_sales_val) if isinstance(today_sales_val, (int, float)) else 0
                
                # 遍历配置，从双重字典取值
                for beihuo_key, cart_key, default_val in field_config:
                    if cart_key in complete_item:
                        continue
                    
                    raw = find_value(beihuo_key)
                    
                    if raw is None:
                        complete_item[cart_key] = default_val
                    elif isinstance(raw, Decimal):
                        complete_item[cart_key] = float(raw)
                    elif isinstance(raw, bool):
                        complete_item[cart_key] = int(raw)
                    else:
                        # 尝试将字符串转换为数值类型
                        if cart_key in ['stock_amount', 'cost_price']:
                            try:
                                complete_item[cart_key] = float(raw)
                            except (ValueError, TypeError):
                                complete_item[cart_key] = 0.0
                        else:
                            complete_item[cart_key] = raw
                
                # 添加购物车特有字段
                complete_item['quantity'] = 1
                complete_item['added_time'] = datetime.now()
                complete_item['added_by'] = session.get('username', 'unknown')
                complete_item['store'] = store
                
                complete_items.append(complete_item)
        
        # 查询已有记录，避免重复添加
        conn = get_db_connection()
        cursor = conn.cursor()
        
        barcodes = [item['barcode'] for item in complete_items if item.get('barcode')]
        if barcodes:
            placeholders = ','.join(['%s'] * len(barcodes))
            check_sql = f"SELECT barcode FROM crmapp_cart WHERE store = %s AND barcode IN ({placeholders})"
            cursor.execute(check_sql, [store] + barcodes)
            existing_barcodes = {row[0] for row in cursor.fetchall()}
        else:
            existing_barcodes = set()
        
        # 过滤掉已存在的商品
        new_items = [item for item in complete_items if item.get('barcode') not in existing_barcodes]
        
        # 批量插入数据
        if new_items:
            items_to_add = []
            for item in new_items:
                items_to_add.append((
                    item['oe'], item['supplier'], item['brand'], item['material_name'],
                    item['barcode'], item['car_brand'], item['tag'], 
                    item['inquiry_1m'], item['inquiry_3m'], item['stock'],
                    item['sales_yesterday'], item['sales_month'], item['today_sales'],
                    item['national_inquiry_1m'], item['national_inquiry_3m'],
                    item['internal_remarks'], item['brand_code'], item['stock_amount'],
                    item['sellable_days'], item['cost_price'], item['avg_sales_12m'],
                    item['avg_sales_6m'], item['sales_7d'], item['warning_status'],
                    item['on_way'], item['car_model'], item['store'], 
                    item['quantity'], item['added_time'], item['added_by']
                ))
            
            insert_sql = """
                INSERT INTO crmapp_cart (
                    oe, supplier, brand, material_name, barcode, car_brand, tag,
                    inquiry_1m, inquiry_3m, stock, sales_yesterday, sales_month, today_sales,
                    national_inquiry_1m, national_inquiry_3m, internal_remarks, brand_code,
                    stock_amount, sellable_days, cost_price, avg_sales_12m, avg_sales_6m,
                    sales_7d, warning_status, on_way, car_model, store, quantity, added_time, added_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(insert_sql, items_to_add)
        
        conn.commit()
        conn.close()

        return jsonify({
            'code': 0,
            'msg': f'成功添加 {len(new_items)} 个商品到购物车',
            'added_count': len(new_items),
            'skipped_count': len(complete_items) - len(new_items)
        })
        
    except Exception as e:
        print(f"添加购物车失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'添加失败：{str(e)}'}), 500

@app.route('/api/current_user', methods=['GET'])
@login_required
def get_current_user():
    """获取当前登录用户信息"""
    # 从session获取当前用户信息
    logged_in = session.get('logged_in', False)
    username = session.get('username', '')
    is_admin = session.get('is_admin', False)
    can_delete_cart = session.get('can_delete_cart', False)
    can_process_orders = session.get('can_process_orders', False)
    store = session.get('store', '')
    user_id = session.get('user_id', None)
    
    # 新的权限字段 - 完全独立的权限控制
    admin_access = session.get('admin_access', False)  # 管理员访问权限（独立于is_admin）
    org_switch_access = session.get('org_switch_access', False)  # 组织切换权限（独立于is_admin）
    can_view_all_data = session.get('can_view_all_data', False)
    can_export_data = session.get('can_export_data', False)
    can_modify_prices = session.get('can_modify_prices', False)
    allowed_orgs = session.get('allowed_orgs', [])
    
    # 板块和职级信息（新增字段）
    department = session.get('department', None)  # 板块:业务/市场/后勤
    job_level = session.get('job_level', None)    # 职级:经理/主管/业务员
    
    # 检查store是否为无效值
    if not store or store == 'all' or store == 'none' or store == 'undefined' or store == '':
        store = 'fsbbr'
    
    # 获取当前用户切换后的组织
    current_org = session.get('current_org', store)

    # 从数据库获取用户IP记录
    ip_records_formatted = ''
    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT ip_records FROM crmapp_users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user and user['ip_records']:
            try:
                import json
                ip_list = json.loads(user['ip_records'])
                ip_records_formatted = ', '.join(ip_list)
            except:
                ip_records_formatted = ''
    
    return jsonify({
        'logged_in': logged_in,
        'username': username,
        'is_admin': is_admin,
        'admin_access': admin_access,  # 新增独立的管理员访问权限
        'org_switch_access': org_switch_access,  # 新增独立的组织切换权限
        'can_delete_cart': can_delete_cart,
        'can_process_orders': can_process_orders,
        'can_view_all_data': can_view_all_data,
        'can_export_data': can_export_data,
        'can_modify_prices': can_modify_prices,
        'allowed_orgs': allowed_orgs,  # 允许切换的组织列表
        'department': department,  # 板块:业务/市场/后勤
        'job_level': job_level,    # 职级:经理/主管/业务员
        'store': store,
        'current_org': current_org,
        'store_name': STORES.get(store, '未知门店'),
        'current_org_name': STORES.get(current_org, '未知门店'),
        'ip_records_formatted': ip_records_formatted
    })

def get_cart_items(store, is_admin):
    """获取购物车数据的辅助函数 - 不再实时更新购物车数据，只查询现有数据"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 统一使用传入的store参数，确保门店数据隔离
    sql = "SELECT * FROM crmapp_cart WHERE store = %s ORDER BY added_time DESC"
    cursor.execute(sql, (store,))

    result = cursor.fetchall()

    # 确保时间格式正确
    for item in result:
        if isinstance(item['added_time'], datetime):
            item['added_time'] = item['added_time'].strftime('%Y-%m-%d %H:%M:%S')
        elif item['added_time'] and isinstance(item['added_time'], str):
            # 如果已经是字符串格式，保持不变
            pass

    conn.close()
    return result

@app.route('/api/cart/clear', methods=['POST'])
@login_required
def clear_cart():
    """清空购物车"""
    # 检查用户是否有删除购物车权限
    can_delete_cart = session.get('can_delete_cart', False)
    is_admin = session.get('is_admin', False)
    
    # 普通用户需要有删除购物车权限或为管理员
    if not (can_delete_cart or is_admin):
        return jsonify({'code': 1, 'msg': '权限不足，无法清空购物车'}), 403
    
    # 统一获取当前用户门店，确保门店数据隔离
    store = get_user_store()  # 使用新的函数获取用户门店
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 统一使用传入的store参数，确保门店数据隔离，即使是管理员也只能操作当前门店
    sql = "DELETE FROM crmapp_cart WHERE store = %s"
    cursor.execute(sql, (store,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'code': 0, 'msg': '购物车已清空'})

@app.route('/api/switch_org', methods=['POST'])
@login_required
def switch_org():
    """用户切换组织（门店）- 基于allowed_orgs权限控制"""
    data = request.get_json()
    new_org = data.get('org')
    print(f"Debug - 接收到的组织切换请求: {new_org}")  # 调试信息
    
    if not new_org:
        return jsonify({'code': 1, 'msg': '请选择要切换的组织'}), 400
    
    # 检查组织是否在允许的门店列表中
    if new_org not in STORES:
        print(f"Debug - 无效的组织代码: {new_org}")  # 调试信息
        return jsonify({'code': 1, 'msg': '无效的组织代码'}), 400
    
    # 获取当前用户的允许组织列表
    current_user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT allowed_orgs FROM crmapp_users WHERE id = %s", (current_user_id,))
    user = cursor.fetchone()
    conn.close()
    
    # 检查用户是否被限制只能切换到特定组织
    if user and user['allowed_orgs']:
        try:
            import json
            allowed_orgs = json.loads(user['allowed_orgs'])
            # 如果有设置允许的组织列表，则只允许切换到这些组织
            if allowed_orgs and new_org not in allowed_orgs:
                return jsonify({'code': 1, 'msg': f'权限不足，您只能切换到以下组织：{", ".join(allowed_orgs)}'}), 403
        except:
            pass  # 如果解析失败，允许切换（保持向后兼容）
    
    # 管理员可以切换到任何组织，普通用户受allowed_orgs限制
    is_admin = session.get('is_admin', False)
    if not is_admin:
        # 普通用户额外检查：即使allowed_orgs为空，也只能在自己门店内操作
        user_store = session.get('store', '')
        if not user.get('allowed_orgs') and new_org != user_store:
            return jsonify({'code': 1, 'msg': '权限不足，普通用户只能在自己所属门店操作'}), 403

    session['current_org'] = new_org
    print(f"Debug - 用户组织切换成功，新的current_org: {new_org}")  # 调试信息
    return jsonify({
        'code': 0, 
        'msg': '组织切换成功',
        'data': {
            'current_org': new_org,
            'current_org_name': STORES.get(new_org, '未知门店')
        }
    })


def get_user_store():
    """获取用户当前的门店（用于数据查询）"""
    # 对于管理员，返回当前切换的组织；对于普通用户，返回其所属门店
    is_admin = session.get('is_admin', False)
    user_store = session.get('store', 'fsbbr')  # 用户的默认门店，使用默认值'fsbbr'
    
    print(f"Debug - get_user_store: is_admin={is_admin}, user_store={user_store}")  # 调试信息
    print(f"Debug - get_user_store: session keys: {list(session.keys())}")  # 调试信息
    print(f"Debug - get_user_store: session.get('current_org')={session.get('current_org')}")  # 调试信息
    
    # 无论是否为管理员，都应返回当前切换的组织（如果存在）
    current_org = session.get('current_org', user_store)
    print(f"Debug - get_user_store: current_org={current_org}")  # 调试信息
    
    # 如果current_org是'none'、'undefined'、'all'等无效值，返回用户默认门店
    if not current_org or current_org == 'all' or current_org == 'none' or current_org == 'undefined' or current_org == '':
        print(f"Debug - get_user_store: using user_store instead of invalid current_org")  # 调试信息
        return user_store
    return current_org

@app.route('/api/cart/remove_multiple', methods=['POST'])
@login_required
def remove_multiple_from_cart():
    """批量从购物车移除商品"""
    # 检查用户是否有删除购物车权限
    can_delete_cart = session.get('can_delete_cart', False)
    is_admin = session.get('is_admin', False)

    # 普通用户需要有删除购物车权限或为管理员
    if not (can_delete_cart or is_admin):
        return jsonify({'code': 1, 'msg': '权限不足，无法删除购物车商品'}), 403

    try:
        data = request.get_json()
        item_details = data.get('item_details', [])

        if not item_details:
            return jsonify({'code': 1, 'msg': '没有要删除的商品'}), 400

        # 获取当前用户门店
        store = get_user_store()

        conn = get_db_connection()
        cursor = conn.cursor()

        deleted_count = 0
        for item in item_details:
            item_oe = item.get('item_oe')
            item_barcode = item.get('item_barcode')

            # 修改删除逻辑：如果提供了物料条码，则按OE和物料条码组合删除；否则按OE删除（兼容旧逻辑）
            if item_barcode:
                sql = "DELETE FROM crmapp_cart WHERE oe = %s AND barcode = %s AND store = %s"
                cursor.execute(sql, (item_oe, item_barcode, store))
            else:
                # 兼容旧逻辑，仅按OE删除
                sql = "DELETE FROM crmapp_cart WHERE oe = %s AND store = %s"
                cursor.execute(sql, (item_oe, store))

            deleted_count += cursor.rowcount

        conn.commit()
        conn.close()

        # 删除成功后不返回购物车数据，前端自行调用获取购物车接口
        return jsonify({
            'code': 0,
            'msg': f'成功删除 {deleted_count} 个商品',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'删除失败: {str(e)}'})

@app.route('/api/cart/remove', methods=['POST'])
@login_required
def remove_from_cart():
    """从购物车移除指定商品"""
    # 检查用户是否有删除购物车权限
    can_delete_cart = session.get('can_delete_cart', False)
    is_admin = session.get('is_admin', False)

    # 普通用户需要有删除购物车权限或为管理员
    if not (can_delete_cart or is_admin):
        return jsonify({'code': 1, 'msg': '权限不足，无法删除购物车商品'}), 403

    try:
        data = request.get_json()
        item_oe = data.get('item_oe')
        item_barcode = data.get('item_barcode')  # 新增：获取物料条码

        # 获取当前用户门店
        store = get_user_store()

        conn = get_db_connection()
        cursor = conn.cursor()

        # 修改删除逻辑：如果提供了物料条码，则按OE和物料条码组合删除；否则按OE删除（兼容旧逻辑）
        if item_barcode:
            sql = "DELETE FROM crmapp_cart WHERE oe = %s AND barcode = %s AND store = %s"
            cursor.execute(sql, (item_oe, item_barcode, store))
        else:
            # 兼容旧逻辑，仅按OE删除
            sql = "DELETE FROM crmapp_cart WHERE oe = %s AND store = %s"
            cursor.execute(sql, (item_oe, store))

        conn.commit()
        conn.close()

        # 删除成功后不返回购物车数据，前端自行调用获取购物车接口
        return jsonify({
            'code': 0,
            'msg': '删除成功'
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'删除失败: {str(e)}'})


@app.route('/api/cart/update_quantity', methods=['POST'])
@login_required
def update_cart_quantity():
    """更新购物车商品数量"""
    try:
        data = request.get_json()
        item_oe = data.get('item_oe')
        quantity = data.get('quantity', 1)
        
        # 确保数量为正整数
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return jsonify({'code': 1, 'msg': '数量必须大于0'})
        except ValueError:
            return jsonify({'code': 1, 'msg': '数量必须是整数'})
        
        # 获取当前用户门店
        store = get_user_store()  # 使用新的函数获取用户门店
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 先检查商品是否存在
        check_sql = "SELECT id FROM crmapp_cart WHERE oe = %s AND store = %s"
        cursor.execute(check_sql, (item_oe, store))
        existing_item = cursor.fetchone()
        
        if not existing_item:
            # 检查商品是否存在于其他门店，用于调试
            debug_sql = "SELECT id, store FROM crmapp_cart WHERE oe = %s"
            cursor.execute(debug_sql, (item_oe,))
            debug_result = cursor.fetchall()
            print("调试：在所有门店中查找OE为 '{}' 的商品，找到 {} 条记录".format(item_oe, len(debug_result)))  # 修复格式化错误
            if debug_result:
                for item in debug_result:
                    print("  - ID: {}, 门店: {}".format(item[0], item[1]))  # 修复格式化错误
            else:
                print("  - 未找到 OE 为 '{}' 的商品".format(item_oe))  # 修复格式化错误
            
            conn.close()
            return jsonify({'code': 1, 'msg': '购物车中未找到该商品'})
        
        # 更新数量
        sql = "UPDATE crmapp_cart SET quantity = %s WHERE oe = %s AND store = %s"
        cursor.execute(sql, (quantity, item_oe, store))
        
        conn.commit()
        conn.close()
        
        # 获取维度参数以返回正确的数据格式
        dimension = request.args.get('dimension', 'product')
        return jsonify({
            'code': 0,
            'msg': '数量更新成功',
            'data': get_cart_items_with_dimension(store, session.get('is_admin', False), dimension)
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'更新失败: {str(e)}'})
    

# 添加获取所有用户信息的接口（仅管理员可用）
@app.route('/api/users', methods=['GET'])
@login_required
def get_users():
    import json  # 在函数开始时导入json模块
    
    if not session.get('is_admin'):
        return jsonify({'code': 1, 'msg': '权限不足'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    # 获取所有用户信息（不包括密码）
    cursor.execute("SELECT id, username, is_admin, store, can_delete_cart, can_process_orders, department, job_level, ip_records, allowed_orgs FROM crmapp_users ORDER BY id")
    users = cursor.fetchall()
    
    # 添加门店名称和处理权限字段
    for user in users:
        user['store_name'] = STORES.get(user['store'], '未知门店')
        # 格式化IP记录
        if user['ip_records']:
            try:
                ip_list = json.loads(user['ip_records'])
                user['ip_records_formatted'] = ', '.join(ip_list)
            except:
                user['ip_records_formatted'] = ''
        else:
            user['ip_records_formatted'] = ''
        # 格式化允许的组织列表
        if user['allowed_orgs']:
            try:
                allowed_orgs = json.loads(user['allowed_orgs'])
                if allowed_orgs:
                    org_names = [STORES.get(org, org) for org in allowed_orgs]
                    user['allowed_orgs_formatted'] = ', '.join(org_names)
                else:
                    user['allowed_orgs_formatted'] = '所有组织'
            except:
                user['allowed_orgs_formatted'] = '所有组织'
        else:
            user['allowed_orgs_formatted'] = '所有组织'
        
        # 添加默认的权限字段（用于兼容性）
        user['admin_access'] = user['is_admin']
        user['org_switch_access'] = user['is_admin']
    
    conn.close()
    
    return jsonify({
        'code': 0,
        'data': users,
        'count': len(users),
        'msg': ''
    })

# 添加创建新用户的接口（仅管理员可用）
@app.route('/api/users', methods=['POST'])
@login_required
def create_user():
    """创建新用户"""
    # 检查当前用户权限 - 只有admin和fsbbr账号可以创建用户
    current_username = session.get('username', '')
    if current_username not in ['admin', 'fsbbr']:
        return jsonify({'code': 1, 'msg': '权限不足，只有admin和fsbbr账号可以创建用户'}), 403
    
    data = request.get_json()
    
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin', 0)
    can_delete_cart = data.get('can_delete_cart', 0)
    can_process_orders = data.get('can_process_orders', 0)  # 新增：处理单据权限
    store = data.get('store', 'fsbbr')
    department = data.get('department')  # 板块:业务/市场/后勤
    job_level = data.get('job_level')    # 职级:经理/主管/业务员
    
    # 验证必填字段
    if not username or not password:
        return jsonify({'code': 1, 'msg': '用户名和密码不能为空'}), 400
    
    # 验证板块和职级必填（新增用户时必须填写）
    if not department:
        return jsonify({'code': 1, 'msg': '板块不能为空'}), 400
    if not job_level:
        return jsonify({'code': 1, 'msg': '职级不能为空'}), 400
    
    # 验证板块和职级的有效值
    valid_departments = ['业务', '市场', '后勤']
    valid_job_levels = ['经理', '主管', '业务员']
    if department not in valid_departments:
        return jsonify({'code': 1, 'msg': f'板块必须是以下之一: {", ".join(valid_departments)}'}), 400
    if job_level not in valid_job_levels:
        return jsonify({'code': 1, 'msg': f'职级必须是以下之一: {", ".join(valid_job_levels)}'}), 400
    
    # 验证字段类型
    if not isinstance(is_admin, bool) and is_admin not in [0, 1]:
        return jsonify({'code': 1, 'msg': '管理员权限值必须为0或1'}), 400
    
    if not isinstance(can_delete_cart, bool) and can_delete_cart not in [0, 1]:
        return jsonify({'code': 1, 'msg': '删除购物车权限值必须为0或1'}), 400
    
    if not isinstance(can_process_orders, bool) and can_process_orders not in [0, 1]:  # 新增验证
        return jsonify({'code': 1, 'msg': '处理单据权限值必须为0或1'}), 400
    
    if not isinstance(store, str):
        return jsonify({'code': 1, 'msg': '门店代码必须为字符串'}), 400
    
    # 检查用户名是否已存在
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM crmapp_users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'code': 1, 'msg': '用户名已存在'}), 400
        
        # 插入新用户
        cursor.execute(
            "INSERT INTO crmapp_users (username, password, is_admin, store, can_delete_cart, can_process_orders, department, job_level) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (username, password, is_admin, store, can_delete_cart, can_process_orders, department, job_level)  # 添加新字段
        )
        
        conn.commit()
        
        return jsonify({'code': 0, 'msg': '用户创建成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'code': 1, 'msg': f'创建用户失败: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

# 修改用户密码的接口（仅管理员可用）
@app.route('/api/users/<int:user_id>/password', methods=['PUT'])
@login_required
def change_user_password(user_id):
    if not session.get('is_admin'):
        return jsonify({'code': 1, 'msg': '权限不足'}), 403
    
    # 不能修改自己的密码通过这个接口（需要通过其他接口）
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT username FROM crmapp_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'code': 1, 'msg': '用户不存在'})
    
    # 检查是否是当前用户试图修改自己的密码
    if user['username'] == session.get('username'):
        conn.close()
        return jsonify({'code': 1, 'msg': '不能通过此接口修改自己的密码，请使用密码修改功能'})
    
    data = request.get_json()
    new_password = data.get('password')
    
    if not new_password:
        conn.close()
        return jsonify({'code': 1, 'msg': '密码不能为空'})
    
    if len(new_password) < 6:
        conn.close()
        return jsonify({'code': 1, 'msg': '密码长度不能少于6个字符'})
    
    # 更新密码
    try:
        cursor.execute("UPDATE crmapp_users SET password = %s WHERE id = %s", (new_password, user_id))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'msg': '密码修改成功'})
    except Exception as e:
        conn.close()
        return jsonify({'code': 1, 'msg': f'修改密码失败: {str(e)}'})


# 用户自己修改密码的接口（无需验证旧密码）
@app.route('/api/user/password', methods=['PUT'])
@login_required
def change_own_password():
    data = request.get_json()
    new_password = data.get('new_password')
    username = session.get('username')
    
    if not new_password:
        return jsonify({'code': 1, 'msg': '新密码不能为空'})
    
    if len(new_password) < 6:
        return jsonify({'code': 1, 'msg': '密码长度不能少于6个字符'})
    
    # 更新密码
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute("UPDATE crmapp_users SET password = %s WHERE username = %s", (new_password, username))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'msg': '密码修改成功'})
    except Exception as e:
        conn.close()
        return jsonify({'code': 1, 'msg': f'修改密码失败: {str(e)}'})

@app.route('/api/cart/import', methods=['POST'])
@login_required
def import_cart():
    """导入购物车数据"""
    try:
        if 'file' not in request.files:
            return jsonify({'code': 1, 'msg': '没有上传文件'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'code': 1, 'msg': '没有选择文件'})

        # 获取当前用户信息
        current_store = get_user_store()
        current_username = session.get('username', '未知用户')
        is_admin = session.get('is_admin', False)

        # 保存上传的文件
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            file.save(tmp_file.name)
            temp_file_path = tmp_file.name

        try:
            # 读取Excel文件
            import pandas as pd
            df = pd.read_excel(temp_file_path) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(temp_file_path)

            # 限制导入数据量，最多1000条
            if len(df) > 10000:
                return jsonify({'code': 1, 'msg': f'导入数据量过大，最多支持10000条，当前数据量为{len(df)}条'})

            # 动态查找包含"物料条码"和"品牌号"关键词的列
            barcode_column = None
            brand_code_column = None
            
            # 遍历列名，查找包含关键词的列
            for col in df.columns:
                col_str = str(col).strip()
                # 清理列名中的特殊字符和空白
                cleaned_col = re.sub(r'[^\w\u4e00-\u9fff]', '', col_str)
                
                # 检查是否包含"物料条码"或"barcode"相关关键词
                if '物料条码' in cleaned_col or 'barcode' in cleaned_col.lower():
                    barcode_column = col
                # 检查是否包含"品牌号"或"brand"相关关键词
                if '品牌号' in cleaned_col or 'brand' in cleaned_col.lower():
                    brand_code_column = col

            # 检查是否包含必要的列
            has_barcode = barcode_column is not None
            has_brand_code = brand_code_column is not None

            if not (has_barcode or has_brand_code):
                return jsonify({'code': 1, 'msg': 'Excel文件必须包含"物料条码"或"品牌号"列'})

            # 连接数据库
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            all_matched_items = []
            unmatched_values = set()  # 存储未匹配的值

            # 处理数值类型转换
            def convert_value(value):
                if pd.notna(value) and value != '':
                    if isinstance(value, float):
                        # 如果是浮点数，转换为整数再转字符串
                        if value.is_integer():
                            return str(int(value))
                        else:
                            return str(value).rstrip('0').rstrip('.')
                    else:
                        return str(value).strip()
                return None

            # 批量处理数据 - 提取所有需要查询的值
            barcode_values = set() if has_barcode else set()
            brand_code_values = set() if has_brand_code else set()
            
            for index, row in df.iterrows():
                if has_barcode:
                    barcode_val = convert_value(row[barcode_column])
                    if barcode_val:
                        barcode_values.add(barcode_val)
                
                if has_brand_code:
                    brand_code_val = convert_value(row[brand_code_column])
                    if brand_code_val:
                        brand_code_values.add(brand_code_val)

            # 批量查询数据库 - 物料条码
            all_items_map = {}
            if barcode_values:
                placeholders = ','.join(['%s'] * len(barcode_values))
                query_sql = f"""
                    SELECT `oe`, `供应商` as supplier, `品牌` as brand, `物料名称` as material_name, 
                           `物料条码` as barcode, `车型品牌` as car_brand, `标签` as tag, 
                           `近1个月询价量` as inquiry_1m, `近3个月月均询价量` as inquiry_3m, 
                           `库存数量` as stock, `昨日销量` as sales_yesterday, `本月销量` as sales_month, 
                           `今日销量` as today_sales, `全国近1个月询价量` as national_inquiry_1m, 
                           `全国近3个月月均询价量` as national_inquiry_3m, `内部备注` as internal_remarks, 
                           `品牌号` as brand_code, `库存金额` as stock_amount, `成品可卖天数` as sellable_days, 
                           `成本价` as cost_price, `近12个月月均销量` as avg_sales_12m, 
                           `近6个月月均销量` as avg_sales_6m, `近7天销量` as sales_7d, 
                           `预警状态` as warning_status
                    FROM crmapp_beihuo 
                    WHERE `物料条码` IN ({placeholders}) AND `company` = %s
                """
                cursor.execute(query_sql, list(barcode_values) + [current_store])
                barcode_results = cursor.fetchall()
                
                for item in barcode_results:
                    all_items_map[item['barcode']] = item

            # 批量查询数据库 - 品牌号
            if brand_code_values:
                placeholders = ','.join(['%s'] * len(brand_code_values))
                query_sql = f"""
                    SELECT `oe`, `供应商` as supplier, `品牌` as brand, `物料名称` as material_name, 
                           `物料条码` as barcode, `车型品牌` as car_brand, `标签` as tag, 
                           `近1个月询价量` as inquiry_1m, `近3个月月均询价量` as inquiry_3m, 
                           `库存数量` as stock, `昨日销量` as sales_yesterday, `本月销量` as sales_month, 
                           `今日销量` as today_sales, `全国近1个月询价量` as national_inquiry_1m, 
                           `全国近3个月月均询价量` as national_inquiry_3m, `内部备注` as internal_remarks, 
                           `品牌号` as brand_code, `库存金额` as stock_amount, `成品可卖天数` as sellable_days, 
                           `成本价` as cost_price, `近12个月月均销量` as avg_sales_12m, 
                           `近6个月月均销量` as avg_sales_6m, `近7天销量` as sales_7d, 
                           `预警状态` as warning_status
                    FROM crmapp_beihuo 
                    WHERE `品牌号` IN ({placeholders}) AND `company` = %s
                """
                cursor.execute(query_sql, list(brand_code_values) + [current_store])
                brand_code_results = cursor.fetchall()
                
                for item in brand_code_results:
                    all_items_map[item['brand_code']] = item

            # 处理每一行数据
            for index, row in df.iterrows():
                matched = False
                
                # 优先使用物料条码进行匹配
                if has_barcode:
                    barcode_val = convert_value(row[barcode_column])
                    if barcode_val and barcode_val in all_items_map:
                        item = all_items_map[barcode_val]
                        all_matched_items.append(item)
                        matched = True
                
                # 如果物料条码未匹配到，再使用品牌号进行匹配
                if not matched and has_brand_code:
                    brand_code_val = convert_value(row[brand_code_column])
                    if brand_code_val and brand_code_val in all_items_map:
                        item = all_items_map[brand_code_val]
                        all_matched_items.append(item)
                        matched = True
                
                # 如果两个都匹配不到，记录未匹配的值
                if not matched:
                    if has_barcode and pd.notna(row[barcode_column]) and row[barcode_column] != '':
                        barcode_raw = row[barcode_column]
                        if isinstance(barcode_raw, float) and barcode_raw.is_integer():
                            unmatched_values.add(str(int(barcode_raw)))
                        else:
                            unmatched_values.add(str(barcode_raw))
                    if has_brand_code and pd.notna(row[brand_code_column]) and row[brand_code_column] != '':
                        brand_code_raw = row[brand_code_column]
                        if isinstance(brand_code_raw, float) and brand_code_raw.is_integer():
                            unmatched_values.add(str(int(brand_code_raw)))
                        else:
                            unmatched_values.add(str(brand_code_raw))

            # 去重：防止同一商品通过不同字段匹配到多次
            unique_matched_items = {}
            for item in all_matched_items:
                key = (item['barcode'], item['oe'])  # 使用条码和OE作为唯一标识
                if key not in unique_matched_items:
                    unique_matched_items[key] = item
            
            all_matched_items = list(unique_matched_items.values())

            # 批量检查购物车中已存在的条码
            if all_matched_items:
                cart_barcodes = [item['barcode'] for item in all_matched_items if item['barcode']]
                if cart_barcodes:
                    placeholders_cart = ','.join(['%s'] * len(cart_barcodes))
                    cursor.execute(f"SELECT barcode FROM crmapp_cart WHERE barcode IN ({placeholders_cart}) AND store = %s", cart_barcodes + [current_store])
                    existing_barcodes = {row['barcode'] for row in cursor.fetchall()}
                else:
                    existing_barcodes = set()
            else:
                existing_barcodes = set()

            # 批量插入新商品到购物车
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            items_to_insert = []
            for item in all_matched_items:
                # 检查是否已在购物车中，按物料条码和门店的组合判断
                if item['barcode'] not in existing_barcodes:
                    items_to_insert.append((
                        item['oe'] if item['oe'] is not None else '',
                        item['supplier'] if item['supplier'] is not None else '',
                        item['brand'] if item['brand'] is not None else '',
                        item['material_name'] if item['material_name'] is not None else '',
                        item['barcode'] if item['barcode'] is not None else '',
                        item['car_brand'] if item['car_brand'] is not None else '',
                        item['tag'] if item['tag'] is not None else '',
                        item['inquiry_1m'] if item['inquiry_1m'] is not None else 0,
                        item['inquiry_3m'] if item['inquiry_3m'] is not None else 0,
                        item['stock'] if item['stock'] is not None else 0,
                        item['sales_yesterday'] if item['sales_yesterday'] is not None else 0,
                        item['sales_month'] if item['sales_month'] is not None else 0,
                        item['today_sales'] if item['today_sales'] is not None else 0,
                        item['national_inquiry_1m'] if item['national_inquiry_1m'] is not None else 0,
                        item['national_inquiry_3m'] if item['national_inquiry_3m'] is not None else 0,
                        item['internal_remarks'] if item['internal_remarks'] is not None else '',
                        item['brand_code'] if item['brand_code'] is not None else '',
                        item['stock_amount'] if item['stock_amount'] is not None else 0.0,
                        item['sellable_days'] if item['sellable_days'] is not None else 0,
                        item['cost_price'] if item['cost_price'] is not None else 0.0,
                        item['avg_sales_12m'] if item['avg_sales_12m'] is not None else 0,
                        item['avg_sales_6m'] if item['avg_sales_6m'] is not None else 0,
                        item['sales_7d'] if item['sales_7d'] is not None else 0,
                        item['warning_status'] if item['warning_status'] is not None else '',
                        1,  # 默认数量为1
                        current_time,  # 加入时间
                        current_username,  # 加入购物车的账户名
                        current_store  # 门店代码
                    ))

            # 批量插入
            added_count = 0
            if items_to_insert:
                insert_sql = """
                    INSERT INTO crmapp_cart 
                    (oe, supplier, brand, material_name, barcode, car_brand, tag, inquiry_1m, inquiry_3m, 
                        stock, sales_yesterday, sales_month, today_sales, national_inquiry_1m, national_inquiry_3m, 
                        internal_remarks, brand_code, stock_amount, sellable_days, cost_price, avg_sales_12m, 
                        avg_sales_6m, sales_7d, warning_status, quantity, added_time, added_by, store) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.executemany(insert_sql, items_to_insert)
                added_count = len(items_to_insert)
                conn.commit()

            # 如果有未匹配的数据，生成Excel文件供下载
            result_msg = f'成功匹配 {len(all_matched_items)} 条数据，添加到购物车 {added_count} 条记录'
            if unmatched_values:
                result_msg += f'，有 {len(unmatched_values)} 条数据在系统中不存在'
                # 创建一个包含未匹配数据的Excel文件
                import pandas as pd
                from io import BytesIO
                import uuid
                
                # 创建包含未匹配数据的DataFrame
                unmatched_df = pd.DataFrame(list(unmatched_values), columns=['未匹配的数据'])
                
                # 生成临时文件
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    unmatched_df.to_excel(writer, sheet_name='系统不存在产品', index=False)
                
                output.seek(0)
                
                # 保存文件到临时位置
                import tempfile
                temp_file_name = f"系统不存在产品_{uuid.uuid4().hex[:8]}.xlsx"
                temp_path = os.path.join(tempfile.gettempdir(), temp_file_name)
                with open(temp_path, 'wb') as f:
                    f.write(output.getvalue())
                
                # 将临时文件路径存储到session中，以便后续下载
                session['unmatched_file_path'] = temp_path
                session['unmatched_file_name'] = f'系统不存在产品_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            else:
                session.pop('unmatched_file_path', None)  # 清除session中的临时文件路径
                
        finally:
            # 删除临时上传的文件
            os.unlink(temp_file_path)

        conn.close()

        return jsonify({
            'code': 0,
            'msg': result_msg,
            'unmatched_count': len(unmatched_values) if 'unmatched_values' in locals() else 0
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'导入失败: {str(e)}'})

@app.route('/api/cart/download_unmatched', methods=['GET'])
@login_required
def download_unmatched():
    """下载未匹配的数据Excel文件"""
    try:
        # 检查session中是否有未匹配数据文件
        if 'unmatched_file_path' in session and 'unmatched_file_name' in session:
            file_path = session['unmatched_file_path']
            file_name = session['unmatched_file_name']
            
            if os.path.exists(file_path):
                from flask import send_file
                return send_file(file_path, as_attachment=True, download_name=file_name)
            else:
                return jsonify({'code': 1, 'msg': '未匹配数据文件不存在'})
        else:
            return jsonify({'code': 1, 'msg': '没有未匹配的数据文件'})
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'下载失败: {str(e)}'})

# ==================== 通用导出API接口 ====================

@app.route('/api/export/<export_type>', methods=['GET'])
@login_required
def unified_export(export_type):
    """
    通用数据导出接口 - 根据搜索条件导出数据
    
    Args:
        export_type: 导出类型（beihuo/cart）
        
    Query参数（备货表）:
        oe: OE号搜索
        supplier: 供应商搜索
        brand: 品牌搜索
        material_name: 物料名称搜索
        tag: 标签搜索
        barcode: 物料条码搜索
        car_brand: 车型品牌搜索
        
    Query参数（购物车表）:
        oe: OE号搜索
        barcode: 物料条码/品牌号搜索
        material_name: 物料名称搜索
        brand: 品牌搜索
        tag: 标签搜索
        car_model: 车型搜索
        dimension: 维度（product/supplier），默认product
    """
    try:
        # 获取当前门店
        current_store = get_user_store()
        
        # 获取搜索条件
        search_params = {}
        
        if export_type == 'beihuo':
            # 备货表搜索参数
            search_params = {
                'oe': request.args.get('oe', '').strip(),
                'supplier': request.args.get('supplier', '').strip(),
                'brand': request.args.get('brand', '').strip(),
                'material_name': request.args.get('material_name', '').strip(),
                'tag': request.args.get('tag', '').strip(),
                'barcode': request.args.get('barcode', '').strip(),
                'car_brand': request.args.get('car_brand', '').strip(),
            }
        elif export_type == 'cart':
            # 购物车表搜索参数
            search_params = {
                'oe': request.args.get('oe', '').strip(),
                'barcode': request.args.get('barcode', '').strip(),
                'material_name': request.args.get('material_name', '').strip(),
                'brand': request.args.get('brand', '').strip(),
                'tag': request.args.get('tag', '').strip(),
                'car_model': request.args.get('car_model', '').strip(),
                'dimension': request.args.get('dimension', 'product'),
            }
        
        # 调用通用导出函数
        return handle_export_request(
            export_type=export_type,
            store=current_store,
            search_params=search_params
        )
        
    except Exception as e:
        print(f"导出失败: {str(e)}")
        return jsonify({'code': 1, 'msg': f'导出失败: {str(e)}'}), 500


# 添加更新备货数据的API接口
@app.route('/api/beihuo/update', methods=['POST'])
@login_required
def update_beihuo():
    try:
        data = request.get_json()
        oe = data.get('oe')
        field = data.get('field')
        value = data.get('value')
        
        if not oe or not field or value is None:
            return jsonify({'code': 1, 'msg': '缺少必要参数'}), 400
        
        # 验证字段名是否合法（防止SQL注入）
        allowed_fields = {
            'material_name': '`物料名称`',
            'brand': '`品牌`',
            'barcode': '`物料条码`',
            'oe': '`oe`',
            'car_brand': '`车型品牌`',
            'tag': '`标签`',
            'stock_amount': '`库存金额`',
            'cost_price': '`成本价`',
            'stock': '`库存数量`',
            'avg_sales_12m': '`近12个月月均销量`',
            'avg_sales_6m': '`近6个月月均销量`',
            'sales_month': '`本月销量`',
            'sales_7d': '`近7天销量`',
            'sales_yesterday': '`昨日销量`',
            'today_sales': '`今日销量`',
            'sellable_days': '`成品可卖天数`',
            'warning_status': '`预警状态`',
            'supplier': '`供应商`',
            'inquiry_1m': '`近1个月询价量`',
            'inquiry_3m': '`近3个月月均询价量`',
            'national_inquiry_1m': '`全国近1个月询价量`',
            'national_inquiry_3m': '`全国近3个月月均询价量`',
            'brand_code': '`品牌号`',
            'internal_remarks': '`内部备注`'
        }
        
        if field not in allowed_fields:
            return jsonify({'code': 1, 'msg': '不允许修改的字段'}), 400
        
        # 根据用户权限决定是否可以更新该记录
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if not session.get('is_admin'):
            # 普通用户只能更新自己门店的数据
            sql = f"UPDATE crmapp_beihuo SET {allowed_fields[field]} = %s WHERE `oe` = %s AND `company` = %s"
            params = (value, oe, get_user_store())
        else:
            # 管理员可以更新所有数据
            sql = f"UPDATE crmapp_beihuo SET {allowed_fields[field]} = %s WHERE `oe` = %s"
            params = (value, oe)
        
        cursor.execute(sql, params)
        affected_rows = cursor.rowcount
        
        if affected_rows == 0:
            conn.close()
            return jsonify({'code': 1, 'msg': '未找到要更新的记录或无权限更新'}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({'code': 0, 'msg': '更新成功'})
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'更新失败: {str(e)}'}), 500

# 添加一个临时的调试接口来检查数据库字段
@app.route('/api/debug_fields', methods=['GET'])
@login_required
def debug_fields():
    """调试接口：获取数据库字段信息"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取表结构
        cursor.execute("DESCRIBE crmapp_beihuo")
        columns = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'code': 0,
            'columns': [col[0] for col in columns]  # 只返回字段名
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)})
    

# 添加函数：更新购物车中的数据
def update_cart_data():
    """在拉取数据后批量更新购物车中的数据 - 使用物料条码加组织匹配"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取所有购物车数据
        cursor.execute("SELECT id, barcode, store FROM crmapp_cart")
        cart_items = cursor.fetchall()
        
        if cart_items:
            # 按门店分组购物车项目
            items_by_store = {}
            for item in cart_items:
                store = item['store']
                if store not in items_by_store:
                    items_by_store[store] = []
                items_by_store[store].append(item)
            
            # 对每个门店的购物车数据进行批量更新
            for store, store_items in items_by_store.items():
                # 提取该门店所有购物车项目的条码
                barcodes = [item['barcode'] for item in store_items if item['barcode']]
                
                if barcodes:
                    # 构建查询语句，使用物料条码和公司（store）匹配
                    placeholders = ','.join(['%s'] * len(barcodes))
                    select_sql = f"""
                        SELECT `供应商`, `品牌`, `物料名称`, `物料条码`, `车型品牌`, `标签`, 
                               `近1个月询价量`, `近3个月月均询价量`, `库存数量`, `昨日销量`, `本月销量`, `今日销量`,
                               `全国近1个月询价量`, `全国近3个月月均询价量`, `内部备注`, `品牌号`, `库存金额`,
                               `成品可卖天数`, `成本价`, `近12个月月均销量`, `近6个月月均销量`, `近7天销量`, `预警状态`, `在途数量`, `车型`
                        FROM crmapp_beihuo 
                        WHERE `物料条码` IN ({placeholders}) AND `company` = %s
                    """
                    cursor.execute(select_sql, barcodes + [store])
                    latest_data_list = cursor.fetchall()
                    
                    # 构建条码到最新数据的映射
                    latest_data_map = {item['物料条码']: item for item in latest_data_list}
                    
                    # 准备批量更新数据
                    update_data_for_batch = []
                    for item in store_items:
                        if item['barcode'] in latest_data_map:
                            latest_data = latest_data_map[item['barcode']]
                            # 不需要限制car_model字段长度，因为我们已将其改为TEXT类型
                            update_data_for_batch.append((
                                latest_data['供应商'],
                                latest_data['品牌'],
                                latest_data['物料名称'],
                                latest_data['车型品牌'],
                                latest_data['标签'],
                                latest_data['近1个月询价量'],
                                latest_data['近3个月月均询价量'],
                                latest_data['库存数量'],
                                latest_data['昨日销量'],
                                latest_data['本月销量'],
                                latest_data['今日销量'],
                                latest_data['全国近1个月询价量'],
                                latest_data['全国近3个月月均询价量'],
                                latest_data['内部备注'],
                                latest_data['品牌号'],
                                latest_data['库存金额'],
                                latest_data['成品可卖天数'],
                                latest_data['成本价'],
                                latest_data['近12个月月均销量'],
                                latest_data['近6个月月均销量'],
                                latest_data['近7天销量'],
                                latest_data['预警状态'],
                                latest_data['在途数量'],
                                latest_data['车型'],  # 不限制长度，完整保存数据
                                item['id']  # 使用购物车记录的ID进行更新
                            ))
                    
                    # 批量更新购物车表中的数据
                    if update_data_for_batch:
                        update_sql = """
                            UPDATE crmapp_cart 
                            SET supplier = %s, brand = %s, material_name = %s, car_brand = %s, tag = %s,
                                inquiry_1m = %s, inquiry_3m = %s, stock = %s, sales_yesterday = %s, 
                                sales_month = %s, today_sales = %s, national_inquiry_1m = %s, 
                                national_inquiry_3m = %s, internal_remarks = %s, brand_code = %s, 
                                stock_amount = %s, sellable_days = %s, cost_price = %s, 
                                avg_sales_12m = %s, avg_sales_6m = %s, sales_7d = %s, warning_status = %s, on_way = %s, car_model = %s
                            WHERE id = %s
                        """
                        cursor.executemany(update_sql, update_data_for_batch)
                        conn.commit()
            
            print(f"✅ 购物车数据批量更新完成，共处理 {len(cart_items)} 条记录")
        else:
            print("ℹ️ 购物车为空，无需更新")
    except Exception as e:
        print(f"❌ 更新购物车数据失败: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

# 修改拉取数据API，在拉取数据后更新购物车数据
@app.route('/api/fetch_data', methods=['POST'])
@login_required
def fetch_data_api():
    """拉取数据API - 根据当前用户门店拉取数据"""
    try:
        import requests
        import re
        from functools import wraps

        # API配置
        API_URL = "http://bi.gzbbr.com/crmapp_api.get_beihuo"
        
        # 从session获取当前用户门店
        current_store = get_user_store()
        
        # 所有用户都只拉取当前门店的数据
        companies = [current_store]
        
        # 定义字段
        FIELDS = [
            "oe", "今日销量", "供应商", "全国近1个月询价量", "全国近3个月月均询价量",
            "内部备注", "品牌", "品牌号", "库存数量", "库存金额", "成品可卖天数",
            "成本价", "昨日销量", "本月销量", "标签", "物料名称", "物料条码",
            "车型品牌", "近12个月月均销量", "近1个月询价量", "近3个月月均询价量",
            "近6个月月均销量", "近7天销量", "预警状态", "在途数量", "车型", "company"
        ]
        JSON_KEYS = [
            "OE", "今日销量", "供应商", "全国近1个月询价量", "全国近3个月月均询价量",
            "内部备注", "品牌", "品牌号", "库存数量", "库存金额", "成品可卖天数",
            "成本价", "昨日销量", "本月销量", "标签", "物料名称", "物料条码",
            "车型品牌", "近12个月月均销量", "近1个月询价量", "近3个月月均询价量",
            "近6个月月均销量", "近7天销量", "预警状态", "在途数量", "车型"
        ]

        
        
        COLUMNS_STR = ", ".join([f"`{f}`" for f in FIELDS])
        PLACEHOLDERS_STR = ", ".join(["%s"] * (len(FIELDS) + 1))  # FIELDS数量+1个更新时间
        UPDATE_SET = ", ".join([f"`{f}` = VALUES(`{f}`)" for f in FIELDS if f != 'id'])
        UPSERT_SQL = f"""
        INSERT INTO `crmapp_beihuo` ({COLUMNS_STR}, `更新时间`)
        VALUES ({PLACEHOLDERS_STR})
        ON DUPLICATE KEY UPDATE {UPDATE_SET}, `更新时间` = VALUES(`更新时间`)
        """

        def clean_data(value):
            if isinstance(value, str):
                match = re.search(r'<(\d+)次', value)
                if match:
                    return str(int(match.group(1)) - 3)
            return value

        def ensure_unique_index(cursor):
            try:
                cursor.execute(f"SHOW INDEX FROM `crmapp_beihuo` WHERE Key_name = 'uk_barcode_company'")
                if cursor.fetchone():
                    return True

                cursor.execute(f"""
                    ALTER TABLE `crmapp_beihuo`
                    ADD UNIQUE KEY `uk_barcode_company` (`物料条码`(50), `company`(20))
                """)
                return True
            except Exception as e:
                print(f"⚠️ 创建唯一索引失败: {e}")
                return False

        def fetch_and_save_company(company, cursor, conn):
            try:
                response = requests.post(
                    API_URL,
                    data={"company": company},
                    headers={
                        'Accept': 'application/json, text/javascript, */*; q=0.01',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Authorization': 'Basic YWRtaW46ODA4OA==',
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'Origin': 'http://bi.gzbbr.com',
                        'Pragma': 'no-cache',
                        'Referer': 'http://bi.gzbbr.com/crmapp_api.bh_index',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                print(f"❌ 请求失败 (company={company}): {e}")
                return 0  # 只返回处理数量

            # 获取接口返回的更新时间
            gx_date = result.get("gx_date", None)
            print(f"📅 接口数据更新时间 (company={company}): {gx_date}")

            data_list = result.get("data", [])
            if not isinstance(data_list, list):
                print(f"⚠️ company={company} 返回数据格式异常")
                return 0

            batch_size = 5000
            total = len(data_list)
            processed = 0

            try:
                for i in range(0, total, batch_size):
                    batch = data_list[i:i + batch_size]
                    values_batch = []
                    for item in batch:
                        row = [clean_data(item.get(key)) for key in JSON_KEYS]
                        row.append(company)
                        
                        # 获取当前记录的品牌值和物料条码
                        current_brand = item.get("品牌", "")
                        current_barcode = item.get("物料条码", "")
                        
                        # 如果品牌是"原厂 SJZX"且物料条码以"P"或"Y"开头，则根据条码前缀修改品牌
                        if current_brand == "原厂 SJZX":
                            if current_barcode and current_barcode.startswith("P"):
                                brand_index = JSON_KEYS.index("品牌")
                                row[brand_index] = "原厂国内4s件"
                            elif current_barcode and current_barcode.startswith("Y"):
                                brand_index = JSON_KEYS.index("品牌")
                                row[brand_index] = "原厂"
                        
                        # 如果品牌是"菲尔"或者"菲尔 FREY"，将物料条码复制到品牌号
                        if current_brand in ["菲尔", "菲尔 FREY"]:
                            barcode_index = JSON_KEYS.index("物料条码")
                            brand_code_index = JSON_KEYS.index("品牌号")
                            row[brand_code_index] = row[barcode_index]
                        
                        # 不需要限制车型字段长度，因为我们已将其改为TEXT类型
                        # 添加更新时间到每行数据（第28个）
                        if gx_date:
                            # 将字符串格式的日期转换为datetime对象
                            from datetime import datetime
                            try:
                                # 尝试解析日期字符串
                                if ' ' in gx_date:
                                    parsed_date = datetime.strptime(gx_date, '%Y-%m-%d %H:%M:%S')
                                else:
                                    parsed_date = datetime.strptime(gx_date, '%Y-%m-%d')
                                row.append(parsed_date)
                            except ValueError:
                                # 如果解析失败，使用当前时间
                                from datetime import datetime
                                row.append(datetime.now())
                        else:
                            # 如果没有更新时间，使用当前时间
                            from datetime import datetime
                            row.append(datetime.now())

                        values_batch.append(row)

                    cursor.executemany(UPSERT_SQL, values_batch)
                    conn.commit()
                    processed += len(values_batch)

            except Exception as e:
                conn.rollback()
                print(f"❌ 插入/更新失败 (company={company}): {e}")
                return 0

            return processed
        
        # 开始执行拉取数据
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 确保唯一索引存在
        if not ensure_unique_index(cursor):
            cursor.close()
            conn.close()
            return jsonify({'code': 1, 'msg': '创建唯一索引失败'})

        total = 0
        for company in companies:
            count = fetch_and_save_company(company, cursor, conn)
            total += count

        cursor.close()
        conn.close()

        # 拉取数据完成后，更新购物车数据
        update_cart_data()

        return jsonify({
            'code': 0, 
            'msg': f'数据拉取完成！总计处理 {total} 条记录',
            'data': {'processed_count': total}
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'拉取数据失败: {str(e)}'}), 500
    
@app.route('/api/latest_update_time', methods=['GET'])
@login_required
def get_latest_update_time():
    """获取最新更新时间"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 如果是管理员，获取所有门店的最新更新时间
        if session.get('is_admin'):
            cursor.execute("SELECT MAX(更新时间) FROM crmapp_beihuo")
        else:
            # 普通用户只获取自己门店的最新更新时间
            cursor.execute("SELECT MAX(更新时间) FROM crmapp_beihuo WHERE company = %s", (get_user_store(),))
        
        result = cursor.fetchone()
        latest_time = result[0] if result[0] is not None else None
        
        conn.close()
        
        if latest_time:
            # 格式化时间为字符串
            latest_time_str = latest_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            latest_time_str = '-'
        
        return jsonify({
            'code': 0,
            'latest_update_time': latest_time_str
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)})
    
@app.route('/api/load_data', methods=['POST'])
@login_required
def load_data_api():
    """加载数据API - 所有用户都更新全部门店数据"""
    try:
        import requests
        import threading
        import time
        from datetime import datetime, timedelta
        
        # 检查是否正在更新（这里可以使用Redis或内存存储，这里使用简单的全局变量）
        if not hasattr(load_data_api, 'last_update_time'):
            load_data_api.last_update_time = None
        if not hasattr(load_data_api, 'is_updating'):
            load_data_api.is_updating = False
        
        # 检查是否正在更新
        if load_data_api.is_updating:
            return jsonify({'code': 1, 'msg': '正在更新，请不要重复点击'})
        
        # 检查距离上次更新是否超过10分钟
        current_time = datetime.now()
        if (load_data_api.last_update_time and 
            current_time - load_data_api.last_update_time < timedelta(minutes=10)):
            remaining_time = timedelta(minutes=10) - (current_time - load_data_api.last_update_time)
            minutes_left = int(remaining_time.total_seconds() // 60)
            seconds_left = int(remaining_time.total_seconds() % 60)
            return jsonify({'code': 1, 'msg': f'请等待更新完成，还有{minutes_left}分{seconds_left}秒可再次更新'})
        
        # 设置正在更新标志
        load_data_api.is_updating = True
        load_data_api.last_update_time = current_time
        
        # API配置
        API_URL = "http://bi.gzbbr.com/crmapp_api.update_beihuo"
        
        # 所有用户都更新全部门店的数据
        companies = ['fsbbr', 'zsbbr', 'zhbbr', 'dgby', 'dghf']
        
        def update_company_async(company):
            """异步更新单个公司的数据"""
            try:
                response = requests.post(
                    API_URL,
                    data={"company": company},
                    headers={
                        'Accept': 'application/json, text/javascript, */*; q=0.01',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Authorization': 'Basic YWRtaW46ODA4OA==',
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',  # 修正Content-Type
                        'Origin': 'http://bi.gzbbr.com',
                        'Pragma': 'no-cache',
                        'Referer': 'http://bi.gzbbr.com/crmapp_api.bh_index',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    timeout=120  # 增加超时时间
                )
                response.raise_for_status()
                result = response.json()
                
                print(f"✅ {company} 数据更新完成")
                return result
            except Exception as e:
                print(f"❌ {company} 数据更新失败: {e}")
                return None
        
        # 异步更新所有公司的数据
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(companies)) as executor:
            futures = [executor.submit(update_company_async, company) for company in companies]
            results = [future.result() for future in futures]
        
        # 更新完成，重置标志
        load_data_api.is_updating = False
        
        # 统计成功更新的公司数量
        success_count = sum(1 for result in results if result is not None)
        
        # 拉取数据完成后，更新购物车数据
        update_cart_data()
        
        return jsonify({
            'code': 0, 
            'msg': f'数据加载完成！成功更新 {success_count}/{len(companies)} 个门店的数据'
        })
        
    except Exception as e:
        # 出现异常也要重置标志
        if hasattr(load_data_api, 'is_updating'):
            load_data_api.is_updating = False
        return jsonify({'code': 1, 'msg': f'加载数据失败: {str(e)}'}), 500

date_ordercount_cache = {}  # 用户缓存字典
cache_lock = threading.Lock()  # 缓存访问锁

@app.route('/api/date_ordercount', methods=['POST'])
@login_required
def date_ordercount():
    """根据日期范围查询订单统计"""
    try:
        data = request.get_json()
        start_date = data.get('start')
        end_date = data.get('end')
        
        if not start_date or not end_date:
            return jsonify({'code': 1, 'msg': '缺少日期参数'}), 400
        
        # 获取当前用户公司
        company = session.get('store', 'fsbbr')
        username = session.get('username', 'default_user')
        
        # 保存查询参数到session，以便其他函数可以使用
        session['last_date_ordercount_start_date'] = start_date
        session['last_date_ordercount_end_date'] = end_date
        session['last_date_ordercount_company'] = company
        
        print(f"存储到session - 用户: {username}, 开始日期: {start_date}, 结束日期: {end_date}")
        
        # 检查数据库中是否已有该用户和日期范围的数据
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        check_sql = """
        SELECT id FROM crmapp_date_search 
        WHERE username = %s AND start_date = %s AND end_date = %s
        LIMIT 1
        """
        cursor.execute(check_sql, (username, start_date, end_date))
        existing_data = cursor.fetchone()
        
        if existing_data:
            # 如果已有数据，直接从数据库获取
            get_sql = """
            SELECT * FROM crmapp_date_search 
            WHERE username = %s AND start_date = %s AND end_date = %s
            ORDER BY id
            """
            cursor.execute(get_sql, (username, start_date, end_date))
            beihuo_data = cursor.fetchall()
            print(f"从数据库获取已有数据，条数: {len(beihuo_data)}")
            conn.close()
            
            return jsonify({
                'code': 0,
                'msg': '查询成功',
                'data': beihuo_data
            })
        else:
            # 没有缓存数据，调用外部API获取数据
            url = "http://bi.gzbbr.com/crmapp_api.by_date_xl"
            
            api_data = {
                "company": company,
                "start": start_date,
                "end": end_date
            }
            
            headers = {
                'Authorization': 'Basic YWRtaW46ODA4OA==',
                'Content-Type': 'application/x-www-form-urlencoded' 
            }
            
            import requests
            response = requests.post(url, data=api_data, headers=headers)
            
            if response.status_code != 200:
                conn.close()
                return jsonify({'code': 1, 'msg': f'外部API调用失败: {response.text}'}), 400
            
            try:
                result = response.json()
            except Exception as e:
                conn.close()
                return jsonify({'code': 1, 'msg': f'API响应解析失败: {str(e)}'}), 400
            
            if not isinstance(result, list):
                # 如果返回的是包含数据的字典，需要获取数据列表
                if isinstance(result, dict) and 'data' in result:
                    data_list = result.get('data', [])
                else:
                    data_list = []
            else:
                data_list = result
            
            # 根据物料条码和公司代码查询crmapp_beihuo表中的完整数据
            # 获取所有查询到的物料条码
            barcodes = [item.get('物料条码') for item in data_list if item.get('物料条码')]
            
            if barcodes:
                placeholders = ','.join(['%s'] * len(barcodes))
                sql = f"""
                SELECT `oe`, `今日销量`, `供应商`, `全国近1个月询价量`, `全国近3个月月均询价量`,
                       `内部备注`, `品牌`, `品牌号`, `库存数量`, `库存金额`, `成品可卖天数`,
                       `成本价`, `昨日销量`, `本月销量`, `标签`, `物料名称`, `物料条码`,
                       `车型品牌`, `近12个月月均销量`, `近1个月询价量`, `近3个月月均询价量`,
                       `近6个月月均销量`, `近7天销量`, `预警状态`, `在途数量`, `车型`,`company`
                FROM crmapp_beihuo 
                WHERE `物料条码` IN ({placeholders}) AND `company` = %s
                """
                cursor.execute(sql, barcodes + [company])
                beihuo_data = cursor.fetchall()
                
                # 将销量信息添加到返回数据中
                for item in beihuo_data:
                    barcode = item['物料条码']
                    # 查找对应的销量信息
                    for order_item in data_list:
                        if order_item.get('物料条码') == barcode:
                            item['销量'] = order_item.get('自定义销量', 0)
                            break
                    else:
                        item['销量'] = 0  # 如果没有对应的销量数据，则设为0
            else:
                beihuo_data = []
            
            # 将查询结果批量存储到数据库中
            if beihuo_data:
                # 先删除该用户和日期范围的旧数据（如果有）
                delete_sql = """
                DELETE FROM crmapp_date_search 
                WHERE username = %s AND start_date = %s AND end_date = %s
                """
                cursor.execute(delete_sql, (username, start_date, end_date))
                
                # 准备批量插入的数据
                batch_data = []
                for item in beihuo_data:
                    batch_data.append((
                        username, start_date, end_date, company, 
                        item.get('物料条码', ''),
                        item.get('物料名称', ''),
                        item.get('品牌', ''),
                        item.get('品牌号', ''),
                        item.get('车型品牌', '') or '',  # 添加车型品牌字段
                        item.get('oe', ''),
                        item.get('标签', ''),
                        item.get('车型', '') or '',  # 添加车型字段
                        item.get('替换号', '') or '',  # 添加替换号字段
                        item.get('今日销量', 0),
                        item.get('昨日销量', 0),
                        item.get('本月销量', 0),
                        item.get('近7天销量', 0),
                        item.get('近1个月询价量', 0),
                        item.get('近3个月月均询价量', 0.00),
                        item.get('近6个月月均销量', 0.00),
                        item.get('近12个月月均销量', 0.00),
                        item.get('成品可卖天数', 0),
                        item.get('库存数量', 0),
                        item.get('在途数量', 0),
                        item.get('成本价', 0.00),
                        item.get('库存金额', 0.00),
                        item.get('供应商', '') or '',  # 添加供应商字段
                        item.get('全国近1个月询价量', 0),  # 添加全国近1个月询价量字段
                        item.get('全国近3个月月均询价量', 0),  # 添加全国近3个月月均询价量字段
                        item.get('内部备注', '') or '',  # 添加内部备注字段
                        item.get('预警状态', '') or '',  # 添加预警状态字段
                        item.get('销量', 0)
                    ))
                
                # 批量插入数据
                insert_sql = """
                INSERT INTO crmapp_date_search (
                    username, start_date, end_date, company, 物料条码, 物料名称, 品牌, 品牌号, 
                    车型品牌, oe, 标签, 车型, 替换号, 今日销量, 昨日销量, 本月销量, 近7天销量, 近1个月询价量, 近3个月月均询价量, 
                    近6个月月均销量, 近12个月月均销量, 成品可卖天数, 库存数量, 在途数量, 成本价, 库存金额, 供应商, 
                    全国近1个月询价量, 全国近3个月月均询价量, 内部备注, 预警状态, 销量
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.executemany(insert_sql, batch_data)
                print(f"批量插入了 {len(batch_data)} 条数据到数据库")
            else:
                print("没有数据需要插入到数据库")
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'code': 0,
                'msg': '查询成功',
                'data': beihuo_data
            })
        
    except Exception as e:
        print(f"Debug - date_ordercount函数发生错误: {str(e)}")  # 添加详细错误信息
        import traceback
        print(f"Debug - 错误堆栈: {traceback.format_exc()}")  # 添加堆栈跟踪
        return jsonify({'code': 1, 'msg': f'查询失败: {str(e)}'}), 500

# 新增API：日期查询结果面板的搜索功能
@app.route('/api/date_ordercount_search', methods=['POST'])
@login_required
def date_ordercount_search():
    """日期查询结果面板的搜索功能，支持物料条码和门店搜索"""
    try:
        data = request.get_json()
        # 获取搜索参数
        oe = data.get('oe', '').strip()
        barcode = data.get('barcode', '').strip()
        material_name = data.get('material_name', '').strip()
        brand = data.get('brand', '').strip()
        tag = data.get('tag', '').strip()
        # 获取排序参数
        field = data.get('field', '').strip()  # 排序字段
        order = data.get('order', '').strip()  # 排序方向：asc/desc
        
        # 获取日期范围参数（用于定位特定查询的数据）
        start_date = session.get('last_date_ordercount_start_date')
        end_date = session.get('last_date_ordercount_end_date')
        username = session.get('username', 'default_user')
        
        # 如果没有日期范围信息，返回提示
        if not start_date or not end_date:
            return jsonify({
                'code': 0,
                'msg': '请先执行日期范围查询以获取数据',
                'data': []
            })
        
        # 从数据库获取该用户和日期范围的缓存数据
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        get_sql = """
        SELECT * FROM crmapp_date_search 
        WHERE username = %s AND start_date = %s AND end_date = %s
        ORDER BY id
        """
        cursor.execute(get_sql, (username, start_date, end_date))
        cached_data = cursor.fetchall()
        conn.close()

        # 如果没有缓存数据，返回空结果
        if not cached_data:
            return jsonify({
                'code': 0,
                'msg': '请先执行日期范围查询以获取数据',
                'data': []
            })
        
        # 处理多行搜索
        oe_list = process_oe_search(oe) if oe else []
        barcode_list = process_barcode_search(barcode) if barcode else []
        material_name_list = process_material_name_search(material_name) if material_name else []
        brand_list = [item.strip() for item in brand.split('\n') if item.strip()] if '\n' in brand else ([brand] if brand else [])
        tag_list = [item.strip() for item in tag.split('\n') if item.strip()] if '\n' in tag else ([tag] if tag else [])
        
        # 在缓存数据中进行搜索
        filtered_data = []
        for item in cached_data:
            match = True  # 假设匹配成功
            
            # 检查OE搜索条件
            if oe_list and item.get('oe', '') not in oe_list:
                match = False
                
            # 检查物料条码搜索条件
            if barcode_list:
                barcode_match = False
                for barcode_item in barcode_list:
                    if barcode_item in item.get('物料条码', '') or barcode_item in item.get('品牌号', ''):
                        barcode_match = True
                        break
                if not barcode_match:
                    match = False
            
            # 检查物料名称搜索条件
            if material_name_list:
                name_match = False
                for name in material_name_list:
                    if name in item.get('物料名称', '') or name in item.get('品牌号', ''):
                        name_match = True
                        break
                if not name_match:
                    match = False
                    
            # 检查品牌搜索条件
            if brand_list:
                brand_match = False
                for brand_item in brand_list:
                    if brand_item in item.get('品牌', ''):
                        brand_match = True
                        break
                if not brand_match:
                    match = False
                    
            # 检查标签搜索条件
            if tag_list:
                tag_match = False
                for tag_item in tag_list:
                    if tag_item in item.get('标签', ''):
                        tag_match = True
                        break
                if not tag_match:
                    match = False
            
            if match:
                filtered_data.append(item)
        
        # 处理排序
        if field and order:
            reverse_order = order.lower() == "desc"
            try:
                if field in ['今日销量', '昨日销量', '本月销量', '近1个月询价量', '近3个月月均询价量', '近7天销量', '近6个月月均销量', '近12个月月均销量', '库存数量', '成本价', '库存金额', '成品可卖天数', '在途数量']:
                    # 数值字段排序
                    filtered_data.sort(key=lambda x: float(x.get(field, 0) or 0), reverse=reverse_order)
                else:
                    # 字符串字段排序
                    filtered_data.sort(key=lambda x: str(x.get(field, '') or '').lower(), reverse=reverse_order)
            except Exception as e:
                print(f"排序过程中出现错误: {str(e)}")
                # 如果排序失败，保持原有顺序
        
        return jsonify({
            'code': 0,
            'msg': '查询成功',
            'data': filtered_data
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'请点击排序图标'}), 500


# 新增API：清空日期查询缓存
@app.route('/api/date_ordercount_clear_cache', methods=['POST'])
@login_required
def date_ordercount_clear_cache():
    """清空当前用户的日期查询缓存（删除特定日期范围的数据）"""
    try:
        username = session.get('username', 'default_user')
        # 从请求中获取要删除的日期范围
        data = request.get_json()
        start_date = data.get('start')  # 如果提供了特定日期范围，则删除该范围数据
        end_date = data.get('end')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if start_date and end_date:
            # 删除特定日期范围的数据
            delete_sql = """
            DELETE FROM crmapp_date_search 
            WHERE username = %s AND start_date = %s AND end_date = %s
            """
            cursor.execute(delete_sql, (username, start_date, end_date))
        else:
            # 删除用户的所有缓存数据
            delete_sql = """
            DELETE FROM crmapp_date_search 
            WHERE username = %s
            """
            cursor.execute(delete_sql, (username,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'code': 0,
            'msg': '缓存已清空'
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'清空缓存失败: {str(e)}'}), 500


# 新增API：获取日期查询缓存数据（用于重置功能）
@app.route('/api/date_ordercount_get_cache', methods=['POST'])
@login_required
def date_ordercount_get_cache():
    """获取当前用户的日期查询缓存数据"""
    try:
        username = session.get('username', 'default_user')
        # 从请求中获取日期范围，如果请求中没有，则从session获取
        data = request.get_json()
        start_date = data.get('start') or session.get('last_date_ordercount_start_date')
        end_date = data.get('end') or session.get('last_date_ordercount_end_date')
        
        print(f"获取缓存 - 用户: {username}, 开始日期: {start_date}, 结束日期: {end_date}")
        print(f"Session中的日期: {session.get('last_date_ordercount_start_date')}, {session.get('last_date_ordercount_end_date')}")
        print(f"请求中的日期: {data.get('start') if data else None}, {data.get('end') if data else None}")
        
        if not start_date or not end_date:
            return jsonify({
                'code': 0,
                'msg': '没有可获取的缓存数据',
                'data': []
            })
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取特定用户和日期范围的缓存数据
        get_sql = """
        SELECT * FROM crmapp_date_search 
        WHERE username = %s AND start_date = %s AND end_date = %s
        ORDER BY id
        """
        print(f"执行查询: {get_sql % (username, start_date, end_date)}")
        cursor.execute(get_sql, (username, start_date, end_date))
        cached_data = cursor.fetchall()
        print(f"查询到的数据条数: {len(cached_data)}")
        conn.close()
        
        return jsonify({
            'code': 0,
            'msg': '获取缓存成功',
            'data': cached_data
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取缓存失败: {str(e)}'}), 500

@app.route('/api/stock_info', methods=['GET'])
@login_required
def get_stock_info():
    """获取库存信息API - 显示所有门店的库存数量"""
    try:
        barcode = request.args.get('barcode', '').strip()
        
        if not barcode:
            return jsonify({'code': 1, 'msg': '缺少物料条码参数'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 查询所有门店的库存信息
        sql = """
            SELECT `库存数量` as stock, `company` as store
            FROM crmapp_beihuo 
            WHERE `物料条码` = %s
            ORDER BY `company`
        """
        cursor.execute(sql, (barcode,))
        results = cursor.fetchall()
        
        # 将结果转换为按门店分组的格式
        stock_info = []
        for row in results:
            store_name = STORES.get(row['store'], row['store'])
            stock_info.append({
                'store': store_name,
                'store_code': row['store'],
                'stock': row['stock'] or 0
            })
        
        conn.close()
        
        return jsonify({
            'code': 0,
            'data': stock_info
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取库存信息失败: {str(e)}'}), 500

    
@app.route('/api/process_bill', methods=['POST'])
@login_required
def process_bill():
    """处理对账单文件 - 修正版"""
    try:
        # 检查是否有文件上传
        if 'files' not in request.files:
            return jsonify({'code': 1, 'msg': '没有上传文件'}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'code': 1, 'msg': '没有选择文件'}), 400

        # 获取处理类型参数
        process_type = request.form.get('process_type', 'bill')
        order_type = request.form.get('order_type', '')
        
        # 检查权限
        if process_type == 'order':
            user_can_process_orders = session.get('can_process_orders', False)
            if not user_can_process_orders:
                return jsonify({'code': 1, 'msg': '权限不足，无法处理单据'}), 403

        # 初始化上传文件路径列表
        uploaded_file_paths = []
        
        # 保存上传的文件
        for file in files:
            if file and file.filename != '':
                import os
                allowed_extensions = {'.xlsx', '.xls', '.csv'}
                if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
                    return jsonify({'code': 1, 'msg': f'不支持的文件格式: {file.filename}'}), 400

                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
                    file.save(tmp_file.name)
                    uploaded_file_paths.append(tmp_file.name)

        if not uploaded_file_paths:
            return jsonify({'code': 1, 'msg': '没有成功保存任何文件'}), 400

        # 调用处理函数 - 现在返回文件列表和临时目录
        processed_files, temp_dir = process_bill_files(uploaded_file_paths, process_type, order_type)

        if not processed_files:
            # 如果有临时目录，需要清理
            if temp_dir:
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    print(f"清理临时目录时出错: {str(e)}")
            return jsonify({'code': 1, 'msg': '没有成功处理任何文件'}), 500

        # 清理临时上传的文件
        for file_path in uploaded_file_paths:
            try:
                import os
                os.remove(file_path)
            except:
                pass

        # 处理返回结果
        # 处理返回结果
        import zipfile
        import tempfile
        from flask import send_file, Response
        from datetime import datetime
        import io

        if process_type == 'order':
            # 对于订单处理，不管是一个还是多个文件，都打包成ZIP，且文件放在子文件夹中
            print(f"DEBUG: 开始处理订单文件，共 {len(processed_files)} 个文件")
            
            # 根据订单类型确定要添加的图片文件夹
            img_folder_path = None
            if order_type == '广州龙星景丰':
                img_folder_path = os.path.join(
                    os.path.dirname(__file__), 
                    'static', 
                    '广州龙星景丰汽车配件销售有限公司报价清单', 
                    'img'
                )
            elif order_type == '厦门华禹':
                img_folder_path = os.path.join(
                    os.path.dirname(__file__), 
                    'static', 
                    '厦门华禹贸易有限公司报价清单', 
                    'img'
                )
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 添加处理后的文件
                for file_path in processed_files:
                    print(f"DEBUG: 正在处理文件: {file_path}")
                    if os.path.exists(file_path):  # 检查文件是否存在
                        # 将文件放入"处理结果/"子文件夹中再添加到ZIP
                        folder_name = "处理结果"
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # 创建ZipInfo对象以更好地控制文件信息
                            archive_path = f"{folder_name}/{os.path.basename(file_path)}"
                            print(f"DEBUG: 将文件存入归档路径: {archive_path}")
                            info = zipfile.ZipInfo(archive_path)
                            info.compress_type = zipfile.ZIP_DEFLATED
                            # 设置外部文件属性（文件权限）为标准的文件权限
                            import stat
                            info.external_attr = 0o644 << 16  # 设置为标准文件权限
                            # 写入内容，指定UTF-8编码
                            zf.writestr(info, content.encode('utf-8'))
                            print(f"DEBUG: 已写入文件到ZIP: {archive_path}")
                    else:
                        # 清理临时目录
                        if temp_dir:
                            try:
                                import shutil
                                shutil.rmtree(temp_dir, ignore_errors=True)
                            except Exception as e:
                                print(f"清理临时目录时出错: {str(e)}")
                        return jsonify({'code': 1, 'msg': f'生成的文件不存在: {file_path}'}), 500
                
                # 如果是广州龙星景丰或厦门华禹订单，添加对应的图片文件夹到处理结果目录
                if img_folder_path and os.path.exists(img_folder_path):
                    print(f"DEBUG: 添加图片文件夹到处理结果目录: {img_folder_path}")
                    for img_file in os.listdir(img_folder_path):
                        img_file_path = os.path.join(img_folder_path, img_file)
                        if os.path.isfile(img_file_path):
                            # 将图片文件添加到ZIP的"处理结果/img/"子文件夹中
                            archive_img_path = f"处理结果/img/{img_file}"  # 放在处理结果目录下的img子目录
                            print(f"DEBUG: 将图片存入归档路径: {archive_img_path}")
                            with open(img_file_path, 'rb') as img:
                                zf.writestr(archive_img_path, img.read())
                                print(f"DEBUG: 已写入图片到ZIP: {archive_img_path}")

            print(f"DEBUG: ZIP构建完成，准备发送")
            # 现在可以安全地删除原始临时目录了
            if temp_dir:
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    print(f"清理临时目录时出错: {str(e)}")
            
            # 将ZIP缓冲区的内容作为响应发送，使用英文文件名避免编码问题
            zip_buffer.seek(0)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"Processed_Orders_{timestamp}.zip"
            print(f"DEBUG: 发送ZIP文件，文件名: {safe_filename}")
            return Response(
                zip_buffer.getvalue(),
                mimetype='application/zip',
                headers={
                    'Content-Disposition': f'attachment; filename="{safe_filename}"'
                }
            )
        else:
            # 对于非订单处理，清理临时目录
            if temp_dir:
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    print(f"清理临时目录时出错: {str(e)}")
                    
            if len(processed_files) == 1:
                # 使用安全的文件名，避免HTTP头部编码问题
                original_filename = os.path.basename(processed_files[0])
                file_ext = os.path.splitext(original_filename)[1]
                safe_filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
                
                # 根据文件扩展名设置正确的MIME类型
                if file_ext.lower() == '.xlsx':
                    mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif file_ext.lower() == '.xls':
                    mimetype = 'application/vnd.ms-excel'
                elif file_ext.lower() == '.csv':
                    mimetype = 'text/csv'
                elif file_ext.lower() == '.html' or file_ext.lower() == '.htm':
                    mimetype = 'text/html; charset=utf-8'
                else:
                    mimetype = 'application/octet-stream'
                
                return send_file(
                    processed_files[0], 
                    as_attachment=True, 
                    download_name=safe_filename,
                    mimetype=mimetype
                )
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as zip_file:
                    with zipfile.ZipFile(zip_file.name, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for file_path in processed_files:
                            if os.path.exists(file_path):  # 检查文件是否存在
                                zf.write(file_path, os.path.basename(file_path))
                            else:
                                return jsonify({'code': 1, 'msg': f'生成的文件不存在: {file_path}'}), 500
                    # 使用安全的ZIP文件名
                    safe_zip_filename = f"Processed_Bills_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                    return send_file(
                        zip_file.name, 
                        as_attachment=True, 
                        download_name=safe_zip_filename
                    )

    except Exception as e:
        print(f"处理对账单时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'处理失败: {str(e)}'}), 500
    

def process_bill_files(file_paths, process_type='bill', order_type=''):
    """处理文件，根据类型调用不同的脚本"""
    import os
    import tempfile
    import shutil
    import zipfile
    import glob

    if process_type == 'bill':
        # 调用原来的对账单处理逻辑
        app_path = os.path.join(os.path.dirname(__file__), 'app')
        if app_path not in sys.path:
            sys.path.insert(0, app_path)

        # 动态导入模块，处理文件名中的空格
        import importlib.util
        # 修正路径：Bill Processing.py位于app/utils目录下
        bill_processing_file_path = os.path.join(app_path, 'utils', 'Bill Processing.py')
        spec = importlib.util.spec_from_file_location(
            "bill_processing", 
            bill_processing_file_path
        )
        bill_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bill_module)

        # 执行处理
        processed_files = bill_module.main(file_paths)
        return processed_files, None  # 返回文件列表和无临时目录
    elif process_type == 'order':
        # 创建临时目录，但不使用with语句，而是返回目录供调用方管理
        temp_dir = tempfile.mkdtemp()
        try:
            # 根据订单类型调用不同的脚本
            app_path = os.path.join(os.path.dirname(__file__), 'app')
            
            if order_type == '广州龙星景丰':
                # 调用广州龙星景丰脚本
                import importlib.util
                order_script_path = os.path.join(app_path, '广州龙星景丰.py')
                spec = importlib.util.spec_from_file_location(
                    "gz_longxkjf", 
                    order_script_path
                )
                order_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(order_module)
                
                # 初始化数据库表
                order_module.init_database()
                
                # 预分配订单号
                allocated_order_numbers = order_module.preallocate_order_numbers(len(file_paths))
                
                # 处理每个上传的文件
                html_files = []
                for i, file_path in enumerate(file_paths):
                    # 使用预分配的订单号处理单个文件
                    allocated_order_number = allocated_order_numbers[i] if i < len(allocated_order_numbers) else None
                    output_file = order_module.start(single_file_path=file_path, output_dir=temp_dir, allocated_order_number=allocated_order_number)
                    html_files.append(output_file)
                        
                return html_files, temp_dir  # 返回文件列表和临时目录
                
            elif order_type == '厦门华禹':
                # 调用厦门华禹脚本
                import importlib.util
                order_script_path = os.path.join(app_path, '厦门华禹.py')
                spec = importlib.util.spec_from_file_location(
                    "xm_huayu", 
                    order_script_path
                )
                order_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(order_module)
                
                # 初始化数据库表
                order_module.init_database()
                
                # 预分配订单号
                allocated_order_numbers = order_module.preallocate_order_numbers(len(file_paths))
                
                # 处理每个上传的文件
                html_files = []
                for i, file_path in enumerate(file_paths):
                    # 使用预分配的订单号处理单个文件
                    allocated_order_number = allocated_order_numbers[i] if i < len(allocated_order_numbers) else None
                    output_file = order_module.start(single_file_path=file_path, output_dir=temp_dir, allocated_order_number=allocated_order_number)
                    html_files.append(output_file)
                        
                return html_files, temp_dir  # 返回文件列表和临时目录
            else:
                return [], temp_dir
        except Exception:
            # 如果出现异常，清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    else:
        return [], None
    
@app.route('/download_template/<template_type>')
def download_template(template_type):
    """下载模板文件"""
    import os
    from flask import send_file
    
    # 根据模板类型确定文件路径
    # 使用项目根目录下的static目录路径
    project_root = os.path.dirname(os.path.abspath(__file__))
    if template_type == 'guangzhou_lxjf':
        file_path = os.path.join(
            project_root, 
            'static', 
            '广州龙星景丰汽车配件销售有限公司报价清单', 
            '广州龙星景丰单据模板.xlsx'
        )
        filename = '广州龙星景丰单据模板.xlsx'
    elif template_type == 'xiamen_huayu':
        file_path = os.path.join(
            project_root, 
            'static', 
            '厦门华禹贸易有限公司报价清单', 
            '厦门华禹单据模板.xlsx'
        )
        filename = '厦门华禹单据模板.xlsx'
    else:
        return jsonify({'code': 1, 'msg': '模板类型不存在'}), 404
    
    if not os.path.exists(file_path):
        return jsonify({'code': 1, 'msg': '模板文件不存在'}), 404
    
    return send_file(file_path, as_attachment=True, download_name=filename)



# 注册SocketIO事件处理器（在这里插入）
register_socket_events(socketio)
# 初始化通知管理器
notification_manager.init_app(app, socketio)
# 初始化全局SocketIO引用
from app.sockets.notification_manager import init_global_socketio
init_global_socketio(app, socketio)

# 全局标志：虚拟库存表是否已初始化
_virtual_inventory_tables_initialized = False

def init_virtual_inventory_tables():
    """
    初始化虚拟库存相关数据库表（全局只执行一次）
    在应用启动时调用，确保所有表已创建
    """
    global _virtual_inventory_tables_initialized
    
    if _virtual_inventory_tables_initialized:
        return
    
    try:
        print(f"[{datetime.now()}] 正在初始化虚拟库存数据库表...")
        from app.utils import virtual_inventory
        virtual_inventory.create_tables()
        _virtual_inventory_tables_initialized = True
        print(f"[{datetime.now()}] 虚拟库存数据库表初始化完成")
    except Exception as e:
        print(f"[{datetime.now()}] 初始化虚拟库存数据库表失败: {e}")
        import traceback
        traceback.print_exc()

# 初始化后台任务（单 worker 极简版）
def init_background_tasks():
    """
    初始化后台任务 - 单 worker 环境下直接启动
    """
    try:
        from app.core.task_manager import task_manager, init_ks_bill_monitor
        
        print("[任务初始化] 正在初始化...")
        task_manager.initialize()
        
        # 注册虚拟库存任务
        task_manager.schedule(
            run_virtual_inventory_task,
            'cron',
            'virtual_inventory_daily',
            hour=13,
            minute=0,
            replace_existing=True
        )
        print("[任务] 虚拟库存: 每天13:00")
        
        # 注册购物车清理任务
        task_manager.schedule(
            run_cart_cleanup_task,
            'cron',
            'cart_cleanup_hourly',
            minute=0,
            replace_existing=True
        )
        print("[任务] 购物车清理: 每小时")
        
        # 注册自动更新任务
        setup_scheduled_tasks()
        
        # 初始化开思自动对单
        init_ks_bill_monitor()
        
        print("[任务初始化] 完成")
        
    except Exception as e:
        print(f"[任务初始化] 失败: {e}")
        import traceback
        traceback.print_exc()

# 应用启动配置
if __name__ == '__main__':
    # 先在主进程中初始化数据库表
    init_virtual_inventory_tables()
    
    # 初始化后台任务
    init_background_tasks()
    
    # 使用纯 Flask 运行
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)

# uWSGI/gunicorn 环境下的初始化
if IS_UWSGI or not __name__ == '__main__':
    print(f"[服务器] 检测到生产环境，正在初始化... (PID: {os.getpid()})")
    
    # 初始化数据库表
    try:
        init_virtual_inventory_tables()
        print("[服务器] 数据库表初始化完成")
    except Exception as e:
        print(f"[服务器] 数据库表初始化失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 延迟初始化后台任务 - 给服务器一些时间完全启动
    def delayed_init():
        try:
            print(f"[服务器] 等待环境就绪... (PID: {os.getpid()})")
            time.sleep(5)
            
            # 初始化后台任务（内部会自动检测是否为主 worker）
            init_background_tasks()
            print(f"[服务器] 后台任务初始化完成 (PID: {os.getpid()})")
            
        except Exception as e:
            print(f"[服务器] 初始化失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 启动延迟初始化线程
    init_thread = threading.Thread(target=delayed_init, daemon=True, name='server_init')
    init_thread.start()
    print("[服务器] 初始化线程已启动（5秒后执行）")
