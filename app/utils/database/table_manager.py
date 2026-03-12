from datetime import datetime
import pymysql
from app.utils.database_connection import get_db_connection


def check_and_add_fields(table_name, fields_to_check):
    """
    检查并添加表字段
    
    参数:
        table_name: 表名
        fields_to_check: 字段列表，每个字段包含name和definition
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for field in fields_to_check:
                cursor.execute("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = %s 
                    AND COLUMN_NAME = %s
                """, (table_name, field['name']))
                
                result = cursor.fetchone()
                if not result:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN `{field['name']}` {field['definition']}")
                    print(f"已添加 {table_name}.{field['name']} 字段")
    except Exception as e:
        print(f"检查并添加字段时出错: {str(e)}")
    finally:
        conn.close()


def check_and_create_indexes(table_name, indexes_to_check):
    """
    检查并创建表索引
    
    参数:
        table_name: 表名
        indexes_to_check: 索引列表，每个索引包含name和definition
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for idx in indexes_to_check:
                cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = '{idx['name']}'")
                if not cursor.fetchone():
                    cursor.execute(f"ALTER TABLE {table_name} {idx['definition']}")
                    print(f"已创建 {table_name}.{idx['name']} 索引")
    except Exception as e:
        print(f"检查并创建索引时出错: {str(e)}")
    finally:
        conn.close()


def init_cart_table():
    """初始化购物车表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
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
            cursor.execute(create_table_sql)
            print("购物车表初始化完成")
    except Exception as e:
        print(f"初始化购物车表时出错: {str(e)}")
    finally:
        conn.close()


def init_user_table():
    """初始化用户表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
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
            cursor.execute(create_table_sql)
            print("用户表初始化完成")
    except Exception as e:
        print(f"初始化用户表时出错: {str(e)}")
    finally:
        conn.close()
    
    # 检查并添加缺失的字段
    user_fields_to_check = [
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
            'definition': 'JSON COMMENT \'允许切换的组织列表，JSON格式，如["fsbbr", "zsbbr"]，null表示所有组织都可切换\''
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
    check_and_add_fields('crmapp_users', user_fields_to_check)


def init_beihuo_table():
    """初始化备货数据表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
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
            cursor.execute(create_table_sql)
            print("备货数据表初始化完成")
    except Exception as e:
        print(f"初始化备货数据表时出错: {str(e)}")
    finally:
        conn.close()
    
    # 检查并添加缺失的字段
    beihuo_fields_to_check = [
        {
            'name': '在途数量',
            'definition': "INT DEFAULT 0 COMMENT '在途数量'"
        },
        {
            'name': '车型',
            'definition': "TEXT COMMENT '车型'"
        }
    ]
    check_and_add_fields('crmapp_beihuo', beihuo_fields_to_check)


def init_date_search_table():
    """初始化日期搜索数据表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
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
            cursor.execute(create_table_sql)
            print("日期搜索数据表初始化完成")
    except Exception as e:
        print(f"初始化日期搜索数据表时出错: {str(e)}")
    finally:
        conn.close()


def init_ks_auto_bill_table():
    """初始化开思自动账单表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 创建开思自动账单表
            create_table_sql = """
            CREATE TABLE crmapp_ks_auto_bill (
                id INT AUTO_INCREMENT PRIMARY KEY,
                日期 DATETIME NOT NULL,
                开思订单号 VARCHAR(50) NOT NULL UNIQUE,
                执行日志 TEXT,
                客户 VARCHAR(100),
                数量 INT DEFAULT 0,
                金额 DECIMAL(10,2) DEFAULT 0.00,
                INDEX idx_order_id (开思订单号),
                INDEX idx_date (日期),
                INDEX idx_customer (客户)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='开思自动账单表';
            """
            cursor.execute(create_table_sql)
            print("开思自动账单表初始化完成")
    except Exception as e:
        print(f"初始化开思自动账单表时出错: {str(e)}")
    finally:
        conn.close()


def ensure_table_structure():
    """确保数据库表结构正确，包括字段长度等"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
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
                    print(f"ℹ️ 修改{field['desc']}类型时可能遇到预期情况: {str(e)}")
    except Exception as e:
        print(f"确保表结构正确时出错: {str(e)}")
    finally:
        conn.close()


def ensure_cart_indexes():
    """确保购物车表有适当的索引"""
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
    check_and_create_indexes('crmapp_cart', cart_indexes)


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


def check_and_create_default_users():
    """检查是否已有用户，如果没有则创建默认管理员账户"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT COUNT(*) as count FROM crmapp_users")
    result = cursor.fetchone()
    conn.close()
    
    if result['count'] == 0:
        # 创建默认用户
        create_default_users()


def init_all_tables():
    """初始化所有数据库表"""
    init_beihuo_table()
    init_cart_table()
    init_user_table()
    init_date_search_table()
    init_ks_auto_bill_table()
    ensure_table_structure()
    ensure_cart_indexes()
    check_and_create_default_users()
