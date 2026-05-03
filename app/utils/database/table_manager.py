from datetime import datetime
import pymysql
from app.utils.database_connection import get_db_connection

# 导入各模块表初始化函数
from .tables import (
    init_sales_history_detail_table,
    init_quote_count_ks_table,
    init_procurement_history_table,
    init_procurement_history_detail_table,
    init_zhuozhixing_table,
    init_inventory_detail_table,
    init_ks_inquiry_detail_table,
    init_weixin_inquiry_detail_table,
    init_virtual_inventory_stats_log_table,
    init_ks_inquiry_monitor_table,
    init_shop_event_summary_table,
    init_shop_event_detail_table,
    init_shop_business_indicator_table,
    init_price_inquiry_direct_table,
    init_safety_stock_calculation_table,
    init_all_virtual_inventory_tables,
)


def check_and_add_fields(table_name, fields_to_check):
    """检查并添加表字段"""
    conn = get_db_connection()
    added = []
    try:
        with conn.cursor() as cursor:
            for field in fields_to_check:
                cursor.execute("""
                    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
                """, (table_name, field['name']))
                if not cursor.fetchone():
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN `{field['name']}` {field['definition']}")
                    added.append(field['name'])
    except:
        pass
    finally:
        conn.close()


def modify_field_type(table_name, field_name, new_definition):
    """修改表字段类型（如果字段存在且类型不匹配）"""
    import pymysql.cursors
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 检查字段是否存在
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """, (table_name, field_name))
            result = cursor.fetchone()
            
            if result:
                current_type = result['DATA_TYPE'].upper() if result else None
                # 检查当前类型是否已经是 TEXT
                if current_type != 'TEXT':
                    alter_sql = f"ALTER TABLE `{table_name}` MODIFY COLUMN `{field_name}` {new_definition}"
                    cursor.execute(alter_sql)
                    conn.commit()
                    print(f"  ✓ 修改 {table_name}.{field_name} 字段类型为 TEXT")
                else:
                    print(f"  ✓ {table_name}.{field_name} 字段已是 TEXT 类型")
            else:
                # 字段不存在，添加字段
                alter_sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{field_name}` {new_definition}"
                cursor.execute(alter_sql)
                conn.commit()
                print(f"  ✓ 添加 {table_name}.{field_name} 字段")
    except Exception as e:
        print(f"  ✗ 修改 {table_name}.{field_name} 字段失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def check_and_create_indexes(table_name, indexes_to_check):
    """检查并创建表索引"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for idx in indexes_to_check:
                cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = '{idx['name']}'")
                if not cursor.fetchone():
                    cursor.execute(f"ALTER TABLE {table_name} {idx['definition']}")
    except:
        pass
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
                car_model TEXT COMMENT '车型',
                replace_number TEXT COMMENT '替换号',
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
    except Exception as e:
        print(f"  ✗ 购物车表: {e}")
    finally:
        conn.close()
    
    # 修改购物车表字段类型
    modify_field_type('crmapp_cart', 'car_model', "TEXT COMMENT '车型'")
    modify_field_type('crmapp_cart', 'replace_number', "TEXT COMMENT '替换号'")


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
    except Exception as e:
        print(f"  ✗ 用户表: {e}")
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
        },
        {
            'name': 'can_inquiry_module',
            'definition': "TINYINT(1) DEFAULT 0 COMMENT '是否有权限访问询价模块 0-否 1-是'"
        },
        {
            'name': 'can_compare_module',
            'definition': "TINYINT(1) DEFAULT 0 COMMENT '是否有权限访问比价模块 0-否 1-是'"
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
                近12个月销量 INT DEFAULT 0 COMMENT '近12个月销量',
                近1个月询价量 INT DEFAULT 0 COMMENT '近1个月询价量',
                近3个月月均询价量 INT DEFAULT 0 COMMENT '近3个月月均询价量',
                近6个月月均销量 INT DEFAULT 0 COMMENT '近6个月月均销量',
                近6个月销量 INT DEFAULT 0 COMMENT '近6个月销量',
                近7天销量 INT DEFAULT 0 COMMENT '近7天销量',
                预警状态 VARCHAR(255) COMMENT '预警状态',
                company VARCHAR(100) COMMENT '公司',
                更新时间 TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                今日销售 VARCHAR(255) COMMENT '今日销售',
                在途数量 INT DEFAULT 0 COMMENT '在途数量',
                车型 TEXT COMMENT '车型',
                替换号 TEXT COMMENT '替换号',
                INDEX idx_oe (oe),
                INDEX idx_barcode (物料条码),
                INDEX idx_company (company),
                INDEX idx_oe_barcode (oe, 物料条码),
                INDEX idx_updated_time (更新时间)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='备货数据表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  ✗ 备货数据表: {e}")
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
        },
        {
            'name': '近12个月销量',
            'definition': "INT DEFAULT 0 COMMENT '近12个月销量'"
        },
        {
            'name': '近6个月销量',
            'definition': "INT DEFAULT 0 COMMENT '近6个月销量'"
        }
    ]
    check_and_add_fields('crmapp_beihuo', beihuo_fields_to_check)
    
    # 修改替换号字段类型为 TEXT（如果存在且不是 TEXT）
    modify_field_type('crmapp_beihuo', '替换号', "TEXT COMMENT '替换号'")


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
                替换号 TEXT COMMENT '替换号',
                今日销量 INT DEFAULT 0 COMMENT '今日销量',
                昨日销量 INT DEFAULT 0 COMMENT '昨日销量',
                本月销量 INT DEFAULT 0 COMMENT '本月销量',
                近7天销量 INT DEFAULT 0 COMMENT '近7天销量',
                近1个月询价量 INT DEFAULT 0 COMMENT '近1个月询价量',
                近3个月月均询价量 DECIMAL(10,2) DEFAULT 0.00 COMMENT '近3个月月均询价量',
                近6个月月均销量 DECIMAL(10,2) DEFAULT 0.00 COMMENT '近6个月月均销量',
                近12个月月均销量 DECIMAL(10,2) DEFAULT 0.00 COMMENT '近12个月月均销量',
                近6个月销量 INT DEFAULT 0 COMMENT '近6个月销量',
                近12个月销量 INT DEFAULT 0 COMMENT '近12个月销量',
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
    except Exception as e:
        print(f"  ✗ 日期搜索表: {e}")
    finally:
        conn.close()

    # 检查并添加缺失的字段
    date_search_fields_to_check = [
        {
            'name': '近6个月销量',
            'definition': "INT DEFAULT 0 COMMENT '近6个月销量'"
        },
        {
            'name': '近12个月销量',
            'definition': "INT DEFAULT 0 COMMENT '近12个月销量'"
        }
    ]
    check_and_add_fields('crmapp_date_search', date_search_fields_to_check)
    
    # 修改日期查询表字段类型
    modify_field_type('crmapp_date_search', '车型', "TEXT COMMENT '车型'")
    modify_field_type('crmapp_date_search', '替换号', "TEXT COMMENT '替换号'")


def init_ks_auto_bill_table():
    """初始化开思自动账单表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 创建开思自动账单表（如果不存在）
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_ks_auto_bill (
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
    except Exception as e:
        print(f"  ✗ 开思自动账单表: {e}")
    finally:
        conn.close()

    # 检查并添加缺失的字段
    ks_auto_bill_fields_to_check = [
        {
            'name': 'crm订单号',
            'definition': "VARCHAR(50) COMMENT 'CRM订单号'"
        },
        {
            'name': 'crm订单链接',
            'definition': "VARCHAR(255) COMMENT 'CRM订单链接'"
        },
        {
            'name': 'crm订单状态',
            'definition': "VARCHAR(50) COMMENT 'CRM订单状态'"
        },
        {
            'name': '开单时间',
            'definition': "DATETIME COMMENT '开单时间'"
        }
    ]
    check_and_add_fields('crmapp_ks_auto_bill', ks_auto_bill_fields_to_check)


def ensure_table_structure():
    """确保数据库表结构正确，包括字段长度等"""
    conn = get_db_connection()
    modified = []
    try:
        with conn.cursor() as cursor:
            fields_to_modify = [
                {'table': 'crmapp_beihuo', 'field': '车型', 'definition': 'TEXT'},
                {'table': 'crmapp_cart', 'field': 'car_model', 'definition': 'TEXT'},
                {'table': 'crmapp_beihuo', 'field': '供应商', 'definition': 'TEXT'},
                {'table': 'crmapp_beihuo', 'field': '内部备注', 'definition': 'TEXT'},
                {'table': 'zhuozhixing_inventory', 'field': '互换码', 'definition': 'TEXT COMMENT \'互换码\''},
            ]

            for field in fields_to_modify:
                try:
                    # 先检查字段当前类型
                    cursor.execute("""
                        SELECT DATA_TYPE 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = %s 
                        AND COLUMN_NAME = %s
                    """, (field['table'], field['field']))
                    result = cursor.fetchone()
                    
                    # 如果字段不存在或者类型不对，才修改
                    target_type = 'TEXT'
                    if not result or result[0].upper() != target_type:
                        cursor.execute(f"""
                            ALTER TABLE {field['table']} MODIFY COLUMN `{field['field']}` {field['definition']}
                        """)
                        modified.append(f"{field['table']}.{field['field']}")
                except:
                    pass
    except:
        pass
    finally:
        conn.close()
    if modified:
        print(f"[数据库] 已修复字段: {', '.join(modified)}")


def ensure_cart_indexes():
    """确保购物车表有适当的索引"""
    cart_indexes = [
        {'name': 'idx_barcode_store', 'definition': 'ADD INDEX idx_barcode_store (barcode, store)'},
        {'name': 'idx_oe_store', 'definition': 'ADD INDEX idx_oe_store (oe, store)'},
        {'name': 'idx_oe_barcode', 'definition': 'ADD INDEX idx_oe_barcode (oe, barcode)'},
        {'name': 'idx_added_time', 'definition': 'ADD INDEX idx_added_time (added_time)'},
        {'name': 'idx_oe_barcode_store', 'definition': 'ADD INDEX idx_oe_barcode_store (oe, barcode, store)'},
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


def init_price_inquiry_table():
    """初始化询价比价表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_price_inquiry (
                id INT AUTO_INCREMENT PRIMARY KEY,
                oe VARCHAR(100) NOT NULL COMMENT 'OE号',
                brand VARCHAR(50) COMMENT '品牌',
                price DECIMAL(10,2) DEFAULT 0.00 COMMENT '单价（加价后）',
                original_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '原始单价（加价前）',
                supplier VARCHAR(50) COMMENT '供应商',
                warehouse VARCHAR(255) COMMENT '仓库',
                expire_time DATETIME COMMENT '失效时间',
                remark TEXT COMMENT '备注',
                stock_quantity INT DEFAULT 0 COMMENT '库存数量',
                common_number VARCHAR(255) COMMENT '通用号',
                ks_sync TINYINT(1) DEFAULT 0 COMMENT '开思是否同步，0=未同步，1=已同步',
                company VARCHAR(100) DEFAULT 'fsbbr' COMMENT '公司/门店代码',
                import_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '导入时间',
                INDEX idx_oe (oe),
                INDEX idx_brand (brand),
                INDEX idx_supplier (supplier),
                INDEX idx_company (company),
                INDEX idx_oe_brand (oe, brand),
                INDEX idx_oe_brand_company (oe, brand, company),
                INDEX idx_import_time (import_time),
                -- 唯一索引：同一产品同一品牌同一供应商同一价格只能有一条记录
                UNIQUE INDEX uk_oe_brand_supplier_price_company (oe, brand, supplier, price, company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='询价比价表';
            """
            cursor.execute(create_table_sql)
            
            # 检查并添加缺失的字段（兼容旧表）
            alter_columns = [
                ("warehouse", "VARCHAR(255) COMMENT '仓库'"),
                ("expire_time", "DATETIME COMMENT '失效时间'"),
                ("remark", "TEXT COMMENT '备注'"),
                ("stock_quantity", "INT DEFAULT 0 COMMENT '库存数量'"),
                ("common_number", "VARCHAR(255) COMMENT '通用号'"),
                ("ks_sync", "TINYINT(1) DEFAULT 0 COMMENT '开思是否同步，0=未同步，1=已同步'"),
                ("company", "VARCHAR(100) DEFAULT 'fsbbr' COMMENT '公司/门店代码'"),
                ("import_time", "DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '导入时间'"),
                ("original_price", "DECIMAL(10,2) DEFAULT 0.00 COMMENT '原始单价（加价前）'")
            ]
            
            for col_name, col_def in alter_columns:
                try:
                    cursor.execute(f"ALTER TABLE crmapp_price_inquiry ADD COLUMN {col_name} {col_def}")
                except Exception as e:
                    if "Duplicate column name" not in str(e):
                        print(f"添加字段 {col_name} 时出错: {str(e)}")
            
            # 删除旧的import_history字段（如果存在）
            try:
                cursor.execute("ALTER TABLE crmapp_price_inquiry DROP COLUMN import_history")
                print("已删除旧字段 import_history")
            except Exception as e:
                if "Can't DROP" not in str(e) and "doesn't exist" not in str(e):
                    print(f"删除字段 import_history 时出错: {str(e)}")
            
            # 检查并修改字段长度（兼容旧表）
            try:
                cursor.execute("ALTER TABLE crmapp_price_inquiry MODIFY oe VARCHAR(100) NOT NULL COMMENT 'OE号'")
                cursor.execute("ALTER TABLE crmapp_price_inquiry MODIFY brand VARCHAR(50) COMMENT '品牌'")
                cursor.execute("ALTER TABLE crmapp_price_inquiry MODIFY supplier VARCHAR(50) COMMENT '供应商'")
                print("已更新字段长度")
            except Exception as e:
                print(f"更新字段长度时出错: {str(e)}")
            
            # 检查并添加索引（兼容旧表）
            index_list = [
                ("idx_company", "company"),
                ("idx_oe_brand_company", "oe, brand, company"),
                ("idx_import_time", "import_time"),
            ]
            
            for idx_name, idx_cols in index_list:
                try:
                    cursor.execute(f"ALTER TABLE crmapp_price_inquiry ADD INDEX {idx_name} ({idx_cols})")
                    print(f"已添加索引 {idx_name}")
                except Exception as e:
                    if "Duplicate key name" not in str(e):
                        print(f"添加索引 {idx_name} 时出错: {str(e)}")
            
            # ==================== 修改唯一索引为包含价格 ====================
            # 先删除旧索引（如果存在）
            old_indexes = [
                "uk_oe_brand_supplier_company",
                "uk_oe_brand_supplier_price_company"
            ]
            
            for old_idx in old_indexes:
                try:
                    cursor.execute(f"ALTER TABLE crmapp_price_inquiry DROP INDEX {old_idx}")
                    print(f"已删除旧唯一索引 {old_idx}")
                except Exception as e:
                    if "Can't DROP" not in str(e) and "doesn't exist" not in str(e):
                        print(f"删除旧索引 {old_idx} 时出错: {str(e)}")
            
            # 添加新唯一索引（包含价格）
            try:
                cursor.execute("""
                    ALTER TABLE crmapp_price_inquiry 
                    ADD UNIQUE INDEX uk_oe_brand_supplier_price_company (oe, brand, supplier, price, company)
                """)
                print("已添加唯一索引 uk_oe_brand_supplier_price_company (oe, brand, supplier, price, company)")
            except Exception as e:
                if "Duplicate key name" not in str(e):
                    print(f"添加唯一索引时出错: {str(e)}")
            
    except Exception as e:
        print(f"  ✗ 询价比价表: {e}")
    finally:
        conn.close()


def init_compare_summary_table():
    """
    初始化比价数据汇总表
    用于存储比价模块的汇总数据，包含销量统计、价格区间等信息
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_compare_summary (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                product_id VARCHAR(100) COMMENT '产品ID',
                oe VARCHAR(255) NOT NULL COMMENT 'OE号',
                brand VARCHAR(255) COMMENT '品牌',
                company VARCHAR(100) DEFAULT 'fsbbr' COMMENT '公司/门店代码',
                product_name VARCHAR(500) COMMENT '产品名称',
                vehicle_brand VARCHAR(255) COMMENT '车辆品牌',
                replace_number VARCHAR(255) COMMENT '替换号',
                replace_number_with_keys VARCHAR(500) COMMENT '替换号(含key信息，格式key1:num1;key2:num2)',
                brand_code VARCHAR(255) COMMENT '品牌编码',
                inquiry_count INT DEFAULT 0 COMMENT '询价次数',
                product_level VARCHAR(50) COMMENT '产品等级',
                best_sales_month VARCHAR(20) COMMENT '销量最好的月份',
                best_sales_season VARCHAR(20) COMMENT '销量最好的季节',
                max_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '最高价',
                min_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '最低价',
                supplier_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '供应商价格',
                dealer_purchase_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '4S含税进价',
                dealer_sale_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '4S含税售价',
                price_update_time DATETIME COMMENT '更新价格时间',
                today_sales INT DEFAULT 0 COMMENT '今日销量',
                yesterday_sales INT DEFAULT 0 COMMENT '昨日销量',
                month_sales INT DEFAULT 0 COMMENT '本月销量',
                avg_sales_12m DECIMAL(10,2) DEFAULT 0.00 COMMENT '近12个月月均销量',
                avg_sales_6m DECIMAL(10,2) DEFAULT 0.00 COMMENT '近6个月月均销量',
                sales_7d INT DEFAULT 0 COMMENT '近7天销量',
                sales_6m INT DEFAULT 0 COMMENT '近6个月总销量',
                sales_12m INT DEFAULT 0 COMMENT '近12个月总销量',
                product_remark TEXT COMMENT '系统产品备注',
                is_cass VARCHAR(10) COMMENT '是否同步开思',
                l_model_zh TEXT COMMENT '车型中文名',
                created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                INDEX idx_oe (oe),
                INDEX idx_brand (brand),
                INDEX idx_company (company),
                INDEX idx_product_name (product_name),
                INDEX idx_vehicle_brand (vehicle_brand),
                INDEX idx_brand_code (brand_code),
                INDEX idx_oe_brand (oe, brand),
                INDEX idx_oe_brand_company (oe, brand, company),
                INDEX idx_updated_time (updated_time),
                UNIQUE INDEX uk_oe_brand_company (oe, brand, company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='比价数据汇总表';
            """
            cursor.execute(create_table_sql)
            
            # 检查并添加唯一索引（兼容旧表）
            try:
                cursor.execute("""
                    ALTER TABLE crmapp_compare_summary 
                    ADD UNIQUE INDEX uk_oe_brand_company (oe, brand, company)
                """)
                print("已添加唯一索引 uk_oe_brand_company 到 crmapp_compare_summary 表")
            except Exception as e:
                if "Duplicate key name" not in str(e) and "Duplicate entry" not in str(e):
                    print(f"添加唯一索引时出错: {str(e)}")
            
            # 检查并添加缺失的字段（兼容旧表）
            alter_columns = [
                ("product_id", "VARCHAR(100) COMMENT '产品ID'"),
                ("is_cass", "VARCHAR(10) COMMENT '是否同步开思'"),
                ("stock_zaitu_list", "JSON COMMENT '在途库存列表'"),
                ("frey_no", "VARCHAR(255) COMMENT 'Frey编号'"),
                ("sales_6m", "INT DEFAULT 0 COMMENT '近6个月总销量'"),
                ("sales_12m", "INT DEFAULT 0 COMMENT '近12个月总销量'"),
                ("replace_number_with_keys", "VARCHAR(500) COMMENT '替换号(含key信息，格式key1:num1;key2:num2)'"),
            ]
            
            for col_name, col_def in alter_columns:
                try:
                    cursor.execute(f"ALTER TABLE crmapp_compare_summary ADD COLUMN {col_name} {col_def}")
                    print(f"已添加字段 {col_name} 到 crmapp_compare_summary 表")
                except Exception as e:
                    if "Duplicate column name" not in str(e):
                        pass  # 静默处理字段添加错误
            
            # 检查并确保 l_model_zh 字段存在且类型为 TEXT
            try:
                cursor.execute("""
                    SELECT DATA_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'crmapp_compare_summary' 
                    AND COLUMN_NAME = 'l_model_zh'
                """)
                result = cursor.fetchone()
                
                # 兼容元组和字典两种返回格式
                if isinstance(result, dict):
                    data_type = result.get('DATA_TYPE', '')
                else:
                    data_type = result[0] if result else ''
                
                if result is None:
                    # 字段不存在，添加字段
                    cursor.execute("""
                        ALTER TABLE crmapp_compare_summary 
                        ADD COLUMN l_model_zh TEXT COMMENT '车型中文名'
                    """)
                    print("已添加 l_model_zh 字段到 crmapp_compare_summary 表")
                elif data_type.upper() != 'TEXT':
                    # 字段存在但类型不是 TEXT，修改类型
                    cursor.execute("""
                        ALTER TABLE crmapp_compare_summary 
                        MODIFY COLUMN l_model_zh TEXT COMMENT '车型中文名'
                    """)
                    print(f"已修改 l_model_zh 字段类型为 TEXT (原类型: {data_type})")
                else:
                    print("  ✓ l_model_zh 字段类型已是 TEXT，无需修改")
            except Exception as e:
                print(f"处理 l_model_zh 字段时出错: {e}")
            
            # 检查并删除冗余字段 procurement_records
            try:
                cursor.execute("""
                    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'crmapp_compare_summary' AND COLUMN_NAME = 'procurement_records'
                """)
                if cursor.fetchone():
                    cursor.execute("ALTER TABLE crmapp_compare_summary DROP COLUMN procurement_records")
                    print("已删除冗余字段 procurement_records 从 crmapp_compare_summary 表")
            except Exception as e:
                print(f"删除字段 procurement_records 时出错: {str(e)}")
    except Exception as e:
        print(f"  ✗ 比价汇总表: {e}")
    finally:
        conn.close()


def auto_fix_all_tables_collation():
    """
    自动修复所有表的字符集排序规则为 utf8mb4_unicode_ci
    解决字符集冲突问题，静默执行
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT TABLE_NAME, TABLE_COLLATION 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_TYPE = 'BASE TABLE'
            """)
            tables = cursor.fetchall()
            
            for table_name, current_collation in tables:
                if current_collation != 'utf8mb4_unicode_ci':
                    try:
                        cursor.execute(f"""
                            ALTER TABLE `{table_name}` 
                            CONVERT TO CHARACTER SET utf8mb4 
                            COLLATE utf8mb4_unicode_ci
                        """)
                    except Exception:
                        pass
            
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def init_all_tables():
    """初始化所有数据库表"""
    tables = [
        ('备货数据', init_beihuo_table),
        ('购物车', init_cart_table),
        ('用户', init_user_table),
        ('日期搜索', init_date_search_table),
        ('开思自动账单', init_ks_auto_bill_table),
        ('询价比价', init_price_inquiry_table),
        ('比价汇总', init_compare_summary_table),
        ('销量明细', init_sales_history_detail_table),
        ('询价次数', init_quote_count_ks_table),
        ('开思询价明细', init_ks_inquiry_detail_table),
        ('微信询价明细', init_weixin_inquiry_detail_table),
        ('采购历史', init_procurement_history_table),
        ('采购历史明细', init_procurement_history_detail_table),
        ('卓之星库存', init_zhuozhixing_table),
        ('库存明细', init_inventory_detail_table),
        ('虚拟库存统计日志', init_virtual_inventory_stats_log_table),
        ('开思询价单监控', init_ks_inquiry_monitor_table),
        ('店铺事件汇总', init_shop_event_summary_table),
        ('店铺事件明细', init_shop_event_detail_table),
        ('店铺经营指标', init_shop_business_indicator_table),
        ('询价直接入库', init_price_inquiry_direct_table),
        ('安全库存计算', init_safety_stock_calculation_table),
        ('虚拟库存', init_all_virtual_inventory_tables),
    ]

    completed = []
    for name, init_func in tables:
        try:
            init_func()
            completed.append('✓')
        except Exception as e:
            completed.append('✗')
            print(f"  ✗ {name}表: {e}")

    # 结构优化和索引
    ensure_table_structure()
    ensure_cart_indexes()
    check_and_create_default_users()
    
    # 自动修复所有表的字符集
    auto_fix_all_tables_collation()

    # 简洁输出
    print(f"[数据库] {sum(1 for c in completed if c == '✓')}/{len(tables)} 表初始化完成")
