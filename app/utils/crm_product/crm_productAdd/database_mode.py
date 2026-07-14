"""
CRM 产品新建 - 数据库模式

职责：
- 从 virtual_inventory 表读取待新建数据
- 过滤已创建产品，避免重复
- 调用 crm_processor 处理单个 OE
- 记录结果到 crmapp_created_products 表
- 更新 virtual_inventory 的 update_status
"""

from config import create_crm_session
from .crm_processor import process_single_oe, ProcessStatus, _format_result_message
from .db_manager import get_db_connection, load_data_from_mysql
from .excel_data_loader import load_alias_data, load_product_data


def init_crmapp_created_products_table(db_manager):
    """
    初始化 crmapp_created_products 表
    用于记录已创建的产品，防止重复创建
    """
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS crmapp_created_products (
            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
            oe_code VARCHAR(100) NOT NULL COMMENT 'OE号',
            brand VARCHAR(100) NOT NULL COMMENT '品牌',
            supplier_name VARCHAR(100) DEFAULT NULL COMMENT '供应商名称',
            create_result VARCHAR(50) DEFAULT NULL COMMENT '创建结果状态',
            update_msg TEXT COMMENT '完整的创建结果消息',
            first_create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '首次创建时间',
            last_update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
            create_count INT DEFAULT 1 COMMENT '创建次数统计',
            UNIQUE KEY uk_oe_brand (oe_code, brand) COMMENT 'OE号和品牌组合唯一'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='CRM已创建产品记录表'
    """
    try:
        db_manager.execute_update(create_table_sql)
        print("[成功] crmapp_created_products 表初始化完成")
    except Exception as e:
        print(f"[失败] 初始化 crmapp_created_products 表失败: {e}")
        raise


def get_existing_products(db_manager):
    """
    获取已存在的产品列表（oe_code + brand 组合）
    返回: set((oe_code, brand), ...)
    """
    try:
        sql = "SELECT oe_code, brand FROM crmapp_created_products"
        result = db_manager.execute_query(sql)
        existing_set = set()
        for row in result:
            key = (row['oe_code'], row['brand'])
            existing_set.add(key)
        print(f"[列表] 已存在 {len(existing_set)} 个产品记录")
        return existing_set
    except Exception as e:
        print(f"[失败] 获取已存在产品列表失败: {e}")
        return set()


def _resolve_create_result(result):
    """
    根据 ProcessResult 解析创建结果状态
    """
    if result.status == ProcessStatus.SUCCESS:
        return '新建成功-新创建'
    if result.status == ProcessStatus.EXISTED:
        return '新建成功-已存在'

    if result.status == ProcessStatus.FAILED:
        if result.message == '未返回产品名称':
            return '新建失败-未返回产品名称'
        if result.message == '未返回车型':
            return '新建失败-未返回车型'
        if result.message == '未返回原厂品牌':
            return '新建失败-未返回原厂品牌'
        return '新建失败-其他'

    return '其他'


def record_create_result(db_manager, oe_code, brand, supplier_name, result):
    """
    记录产品创建失败结果到 crmapp_created_products 表
    新建成功和已存在的记录不写入该表

    Args:
        db_manager: 数据库管理器
        oe_code: OE 号
        brand: 品牌
        supplier_name: 供应商名称
        result: ProcessResult 对象
    """
    if result.status in (ProcessStatus.SUCCESS, ProcessStatus.EXISTED):
        return

    create_result = _resolve_create_result(result)
    result_msg = _format_result_message(result)

    update_sql = """
        UPDATE crmapp_created_products
        SET create_result = %s,
            update_msg = %s,
            create_count = create_count + 1,
            last_update_time = NOW()
        WHERE oe_code = %s AND brand = %s
    """

    insert_sql = """
        INSERT INTO crmapp_created_products
        (oe_code, brand, supplier_name, create_result, update_msg, first_create_time)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """

    try:
        affected = db_manager.execute_update(update_sql, (create_result, result_msg, oe_code, brand))
        if affected == 0:
            db_manager.execute_update(insert_sql, (oe_code, brand, supplier_name, create_result, result_msg))
    except Exception as e:
        print(f"[失败] 记录创建结果失败 [{oe_code}/{brand}]: {e}")


def batch_update_status(db_manager):
    """
    批量更新所有记录的 update_status 字段
    根据 update_msg 内容分类更新状态
    """
    print("\n开始批量更新 update_status...")

    update_sql = """
        UPDATE virtual_inventory
        SET update_status = CASE
            WHEN LOWER(update_msg) LIKE '%update%' OR LOWER(update_msg) = 'add' THEN '上传成功'
            WHEN update_msg LIKE 'OE号【%】处理结果：已存在 - 该物料已关联当前组织!' THEN '新建成功-已存在'
            WHEN update_msg LIKE 'OE号【%】处理结果：成功 - product_id:%' THEN '新建成功-新创建'
            WHEN update_msg LIKE 'OE号【%】处理结果：失败 - 未返回产品名称' THEN '新建失败-未返回产品名称'
            WHEN update_msg LIKE 'OE号【%】处理结果：失败 - 未返回车型%' THEN '新建失败-未返回车型'
            WHEN update_msg LIKE 'OE号【%】处理结果：失败 - 未返回原厂品牌' THEN '新建失败-未返回原厂品牌'
            WHEN update_msg LIKE '过期时间【%】不能小于当前时间' THEN '上传失败-过期时间错误'
            WHEN update_msg LIKE '品牌名称【%】总部不存在,请核查数据' THEN '上传失败-品牌不存在'
            WHEN update_msg LIKE '物料所属品牌【%】OE号【%】产品数据不存在,请核查数据' THEN '上传失败-产品不存在'
            ELSE '其他'
        END
        WHERE update_status IS NULL OR update_status = ''
    """

    try:
        affected_rows = db_manager.execute_update(update_sql)
        print(f"[成功] 已更新 {affected_rows} 条记录的 update_status")
    except Exception as e:
        print(f"[失败] 更新 update_status 失败: {e}")
        import traceback
        traceback.print_exc()


def process_database_mode_api(supplier_name=None):
    """
    数据库模式 API 接口
    供虚拟库存上传后调用

    Args:
        supplier_name: 可选，指定供应商名称筛选数据，如 '佛山万拓'

    Returns:
        bool
    """
    if supplier_name:
        print(f"\n=== CRM Product Add - 数据库模式 (供应商: {supplier_name}) ===")
    else:
        print("\n=== CRM Product Add - 数据库模式 ===")

    session = create_crm_session()
    print("Session 创建成功")

    product_df = load_product_data()
    alias_df = load_alias_data()

    db_manager = get_db_connection()
    if not db_manager:
        print("[失败] 数据库连接失败")
        return False

    try:
        init_crmapp_created_products_table(db_manager)

        data = load_data_from_mysql(supplier_name)
        if not data:
            print("没有数据需要处理")
            return True

        print(f"从数据库加载了 {len(data)} 条数据...")

        existing_products = get_existing_products(db_manager)

        items = []
        skipped_count = 0
        for row in data:
            oe_number = str(row['oe_code']).strip()
            brand = row['brand']

            key = (oe_number, brand)
            if key in existing_products:
                skipped_count += 1
                continue

            items.append({
                'oe_number': oe_number,
                'brand': brand,
                'supplier_name': row.get('supplier_name', ''),
                'mode': 'database'
            })

        print(f"跳过已存在的 {skipped_count} 个产品，实际待处理 {len(items)} 个产品")

        if not items:
            print("没有新产品需要处理")
            return True

        total = len(items)
        for idx, item in enumerate(items, 1):
            oe_number = item['oe_number']
            brand = item['brand']
            supplier_name = item.get('supplier_name', '')

            try:
                result = process_single_oe(item, product_df, alias_df, db_manager=db_manager, session=session)
                record_create_result(db_manager, oe_number, brand, supplier_name, result)
            except Exception as e:
                print(f"[失败] {oe_number}: 处理异常: {e}")

            if idx % 10 == 0 or idx == total:
                print(f"进度: {idx}/{total}")

        print(f"\n处理完成: {total} 条")

        batch_update_status(db_manager)

    finally:
        db_manager.close()
        print("数据库连接已关闭")

    return True
