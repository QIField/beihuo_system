"""
CRM 产品添加主程序
支持三种模式：数据库模式、两列模式、三列模式
"""

import os
import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

# 导入统一的 SessionManager
from app.utils.session_manager import SessionManager, get_session

# 导入 CRM Session 创建函数
from config import create_crm_session

# 保持向后兼容的别名
get_thread_session = get_session

# 导入 CRM 相关模块 (使用相对导入)
from .crm_brand_id import get_brand_dict
from .crm_get_oe_link import get_oe_link
from .crm_Product_Add import add_product
from .crm_product_id import get_product_id
from .crm_updateView import update_product_name_by_oe, update_brand_code_by_oe

# 导入 Excel 数据模块 (使用相对导入)
from .excel_data_loader import (
    load_alias_data,
    load_product_data,
    find_brand_by_alias,
    find_product_name_by_oe,
    find_best_match_product
)

# 导入数据库模块 (使用相对导入)
from .db_manager import (
    get_db_connection,
    load_data_from_mysql,
    update_msg_with_processed_result
)


# ============================================================================
# 初始化函数
# ============================================================================

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
        print("✅ crmapp_created_products 表初始化完成")
    except Exception as e:
        print(f"❌ 初始化 crmapp_created_products 表失败: {e}")
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
        print(f"📋 已存在 {len(existing_set)} 个产品记录")
        return existing_set
    except Exception as e:
        print(f"❌ 获取已存在产品列表失败: {e}")
        return set()


def record_create_result(db_manager, oe_code, brand, supplier_name, result_msg):
    """
    记录产品创建结果到 crmapp_created_products 表
    """
    # 解析创建结果状态
    create_result = '其他'
    if '处理结果：成功 - product_id:' in result_msg:
        create_result = '新建成功-新创建'
    elif '处理结果：已存在 - 该物料已关联当前组织!' in result_msg:
        create_result = '新建成功-已存在'
    elif '处理结果：失败 - 未找到产品名称' in result_msg:
        create_result = '新建失败-未找到产品名称'
    elif '处理结果：失败 - 车型不能为空' in result_msg:
        create_result = '新建失败-车型不能为空'
    elif '处理结果：失败' in result_msg:
        create_result = '新建失败-其他'
    
    # 尝试更新已存在的记录
    update_sql = """
        UPDATE crmapp_created_products 
        SET create_result = %s,
            update_msg = %s,
            create_count = create_count + 1,
            last_update_time = NOW()
        WHERE oe_code = %s AND brand = %s
    """
    
    # 插入新记录
    insert_sql = """
        INSERT INTO crmapp_created_products 
        (oe_code, brand, supplier_name, create_result, update_msg, first_create_time)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """
    
    try:
        # 先尝试更新
        affected = db_manager.execute_update(update_sql, (create_result, result_msg, oe_code, brand))
        if affected == 0:
            # 没有更新到，说明是新产品，执行插入
            db_manager.execute_update(insert_sql, (oe_code, brand, supplier_name, create_result, result_msg))
    except Exception as e:
        print(f"❌ 记录创建结果失败 [{oe_code}/{brand}]: {e}")


def get_brand_id_by_name(session, brand, timeout=30):
    """
    根据品牌名称获取品牌ID
    如果找不到，尝试使用别名匹配
    """
    from .crm_brand_id import get_brand_list
    from config import get_auth_headers
    
    headers = get_auth_headers(session)
    
    # 首先尝试直接匹配品牌
    id_params = {'l_name_zh': brand}
    id_response = session.get('https://crm.gzbbr.com/api/Product.Brand/index', params=id_params, headers=headers, timeout=timeout)
    
    if id_response.status_code == 200:
        id_response_data = id_response.json()
        brand_list = id_response_data.get("data", {}).get("list", [])
        
        # 精确匹配l_name_zh与brand
        for brand_item in brand_list:
            if brand_item.get("l_name_zh") == brand:
                brand_id = brand_item.get("brand_id")
                print(f"品牌 '{brand}' -> ID: {brand_id}, 名称: {brand_item.get('l_name_zh')}, 匹配: 直接匹配")
                return brand_id
    
    # 如果直接匹配失败，尝试使用别名
    corrected_brand = find_brand_by_alias(brand)
    
    if corrected_brand:
        # 使用修正后的品牌名再次尝试（即使和原品牌名相同，也要尝试查询）
        id_params = {'l_name_zh': corrected_brand}
        id_response = session.get('https://crm.gzbbr.com/api/Product.Brand/index', params=id_params, headers=headers, timeout=timeout)
        
        if id_response.status_code == 200:
            id_response_data = id_response.json()
            brand_list = id_response_data.get("data", {}).get("list", [])
            
            # 精确匹配l_name_zh与修正后的品牌名
            for brand_item in brand_list:
                if brand_item.get("l_name_zh") == corrected_brand:
                    brand_id = brand_item.get("brand_id")
                    match_type = "别名匹配" if corrected_brand != brand else "别名确认"
                    print(f"品牌 '{brand}' -> ID: {brand_id}, 名称: {brand_item.get('l_name_zh')}, 匹配: {match_type}({corrected_brand})")
                    return brand_id
    
    print(f"品牌 '{brand}' -> 未找到匹配")
    return None


# ============================================================================
# 核心处理函数
# ============================================================================

def process_single_oe(item, product_df, alias_df, db_manager=None, session=None):
    """
    处理单个 OE 号码（核心逻辑）
    
    Args:
        item: 数据项 {oe_number, brand, brand_code(可选)}
        product_df: 产品数据 DataFrame
        alias_df: 别名数据 DataFrame
        db_manager: 数据库管理器（数据库模式用）
        session: 可选，传入已认证的 session，否则使用线程本地 session
    
    Returns:
        结果字符串
    """
    # 使用传入的 session 或线程本地的 session
    if session is None:
        session = get_thread_session()
    
    oe_number = item['oe_number']
    brand = item['brand']
    brand_code = item.get('brand_code', '')
    is_three_column = item.get('mode') == 'three_column'
    
    # 步骤 1: 获取 brand_id（实时查询）
    brand_id = get_brand_id_by_name(session, brand)
    if not brand_id:
        result = f"失败 - 没有匹配到品牌ID: {brand}"
        print(f"❌ {oe_number}: {result}")
        _save_result(db_manager, oe_number, brand, result)
        return result
    
    # 步骤 2: 获取 OE 信息（带重试）
    oe_info = _retry_request(lambda: get_oe_link(oe_number, session), "get_oe_link")
    if not oe_info:
        result = f"失败 - 获取 OE 信息失败"
        print(f"❌ {oe_number}: {result}")
        _save_result(db_manager, oe_number, brand, result)
        return result
    
    product_name = oe_info.get('product_name', '')
    vehicle_name = oe_info.get('vehicle_name', '')
    brand_name = oe_info.get('brand_name', '')
    
    # 步骤 3: 处理缺失字段
    used_excel_name = False
    
    if not product_name:
        # 从 Excel 匹配产品名称
        if product_df is not None:
            matched_name = find_product_name_by_oe(oe_number)
            if matched_name:
                product_name = matched_name
                used_excel_name = True
                print(f"✓ {oe_number}: 从 Excel 匹配到产品名称: {product_name}")
            else:
                result = f"失败 - 未找到产品名称"
                print(f"❌ {oe_number}: {result}")
                _save_result(db_manager, oe_number, brand, result)
                return result
        else:
            result = f"失败 - 产品数据未加载"
            print(f"❌ {oe_number}: {result}")
            _save_result(db_manager, oe_number, brand, result)
            return result
    
    # brand_name 为空则填"其他"
    if not brand_name:
        brand_name = "其他"
    
    # 步骤 4: 准备产品数据
    # 注意：vehicle_name 为空时填"暂无"，但如果CRM不接受，会记录失败
    product_data = {
        "number": oe_number,
        "brand_id": brand_id,
        "l_name_zh": product_name,
        "l_name_zh_store": product_name,
        "cass_oebrand_name": brand_name,
        "l_model_zh": vehicle_name if vehicle_name else "暂无"
    }
    
    # 步骤 5: 发送 crmProductAdd 请求（带重试）
    add_result = _retry_request(
        lambda: add_product(product_data, session),
        "crmProductAdd"
    )
    
    if not add_result:
        result = f"失败 - 添加产品请求失败"
        print(f"❌ {oe_number}: {result}")
        _save_result(db_manager, oe_number, brand, result)
        return result
    
    # 解析响应
    status = add_result.get('status')
    msg = add_result.get('msg', '')
    
    # 检查车型为空的错误（即使 status 是 201，msg 中也可能包含错误信息）
    if not vehicle_name or "车型不能为空" in msg or "车型" in msg and "不能为空" in msg:
        result = f"失败 - 车型不能为空 | 请求: {product_data} | 响应: {add_result}"
        print(f"❌ {oe_number}: {result}")
        _save_result(db_manager, oe_number, brand, result)
        return result
    
    if status == 200:
        product_id = add_result.get('data')
        result = f"成功 - product_id: {product_id}"
        print(f"✅ {oe_number}: {result}")
        
        # 如果使用了 Excel 匹配的名称，需要更新为最佳匹配
        if used_excel_name:
            _update_with_best_match(session, oe_number, brand, product_name)
        
    elif status == 201:
        if "该物料已关联当前组织" in msg:
            result = f"已存在 - {msg}"
            print(f"⚠️  {oe_number}: {result}")
        else:
            result = f"成功 - {msg}"
            print(f"✅ {oe_number}: {result}")
            
        # 已存在也需要更新最佳匹配名称
        if used_excel_name:
            _update_with_best_match(session, oe_number, brand, product_name)
    else:
        result = f"失败 - {msg}"
        print(f"❌ {oe_number}: {result}")
        _save_result(db_manager, oe_number, brand, result)
        return result
    
    # 步骤 6: 三列模式更新 brand_code
    if is_three_column and brand_code:
        update_result = update_brand_code_by_oe(session, oe_number, brand, brand_code)
        if update_result:
            result += f" | brand_code更新成功"
            print(f"✓ {oe_number}: brand_code 更新成功")
        else:
            result += f" | brand_code更新失败"
            print(f"⚠️  {oe_number}: brand_code 更新失败")
    
    _save_result(db_manager, oe_number, brand, result)
    return result


def _update_with_best_match(session, oe_number, brand, product_name):
    """
    使用最佳匹配名称更新产品
    """
    try:
        # 搜索相似产品名称
        from .crm_brand_id import get_brand_list
        search_result = get_brand_list({'product_name': product_name}, session)
        
        if search_result and search_result.get('status') == 200:
            name_list = search_result.get('data', {}).get('name_list', [])
            
            if name_list:
                best_match = find_best_match_product(product_name, name_list)
                if best_match:
                    matched_name = best_match.get('product_name', '')
                    print(f"🔄 {oe_number}: 最佳匹配名称: {matched_name}")
                    
                    # 更新产品名称
                    update_result = update_product_name_by_oe(
                        session, oe_number, brand, matched_name
                    )
                    if update_result:
                        print(f"✓ {oe_number}: 产品名称更新成功")
                    else:
                        print(f"⚠️  {oe_number}: 产品名称更新失败")
    except Exception as e:
        print(f"⚠️  {oe_number}: 更新最佳匹配名称时出错: {e}")


def _retry_request(func, name, max_retries=1):
    """
    带重试的请求包装器
    """
    for i in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if i < max_retries:
                print(f"  {name} 请求失败，重试第 {i+1} 次...")
                time.sleep(1)
            else:
                print(f"  {name} 请求失败: {e}")
                return None
    return None


def _save_result(db_manager, oe_number, brand, result):
    """
    保存结果（数据库模式）
    """
    if db_manager:
        update_msg_with_processed_result(db_manager, oe_number, brand, result)


# ============================================================================
# 三种模式处理函数
# ============================================================================

def process_database_mode(session, product_df, alias_df, supplier_name=None):
    """
    数据库模式处理
    注意：session参数保留用于兼容性，但实际使用线程本地session
    新增：过滤已创建的产品，防止重复创建
    
    Args:
        session: CRM session
        product_df: 产品数据DataFrame
        alias_df: 别名数据DataFrame
        supplier_name: 可选，指定供应商名称筛选数据，如 '佛山万拓'
    """
    if supplier_name:
        print(f"\n【数据库模式 - 供应商筛选: {supplier_name}】")
    else:
        print("\n【数据库模式】")
    
    # 获取数据库连接
    db_manager = get_db_connection()
    if not db_manager:
        print("❌ 数据库连接失败")
        return
    
    try:
        # 1. 初始化 crmapp_created_products 表
        init_crmapp_created_products_table(db_manager)
        
        # 2. 加载数据（传入供应商名称参数）
        data = load_data_from_mysql(supplier_name)
        if not data:
            print("没有数据需要处理")
            return
        
        print(f"从数据库加载了 {len(data)} 条数据...")
        
        # 3. 获取已存在的产品列表
        existing_products = get_existing_products(db_manager)
        
        # 4. 准备处理项，过滤已存在的产品
        items = []
        skipped_count = 0
        for row in data:
            oe_number = str(row['oe_code']).strip()
            brand = row['brand']
            
            # 检查是否已存在
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
            return
        
        # 5. 循环处理（替代并发），传入已认证的 session
        # 处理所有过滤后的产品（无数量限制）
        results = _process_with_loop_with_record(
            items, product_df, alias_df, db_manager, session
        )
        
        # 6. 所有产品处理完成后，统一更新 update_status
        batch_update_status(db_manager)
        
    finally:
        db_manager.close()
        print("数据库连接已关闭")


def process_two_column_mode(session, product_df, alias_df, file_path):
    """
    两列模式处理（oe + brand）
    """
    print("\n【两列模式】")

    # 读取 Excel，使用 dtype=str 保留前导零
    try:
        if file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path, dtype=str)
        else:
            df = pd.read_csv(file_path, dtype=str)
        print(f"读取到 {len(df)} 行数据")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    # 识别列
    oe_col, brand_col = _identify_columns(df)
    if not oe_col or not brand_col:
        print("❌ 未能识别必要的列")
        return
    
    # 准备处理项
    items = []
    for _, row in df.iterrows():
        oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
        if oe and brand:
            items.append({
                'oe_number': oe,
                'brand': brand,
                'mode': 'two_column'
            })
    
    print(f"有效数据: {len(items)} 条")

    # 循环处理（替代并发）
    results = _process_with_loop(
        items, product_df, alias_df, None
    )

    # 保存结果
    _save_excel_results(df, results, oe_col, file_path)


def process_three_column_mode(session, product_df, alias_df, file_path):
    """
    三列模式处理（oe + brand + brand_code）
    """
    print("\n【三列模式】")

    # 读取 Excel，使用 dtype=str 保留前导零
    try:
        if file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path, dtype=str)
        else:
            df = pd.read_csv(file_path, dtype=str)
        print(f"读取到 {len(df)} 行数据")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    # 识别列
    oe_col, brand_col, brand_code_col = _identify_columns_extended(df)
    if not oe_col or not brand_col or not brand_code_col:
        print("❌ 未能识别必要的列")
        return
    
    # 准备处理项
    items = []
    for _, row in df.iterrows():
        oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
        brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
        if oe and brand:
            items.append({
                'oe_number': oe,
                'brand': brand,
                'brand_code': brand_code,
                'mode': 'three_column'
            })
    
    print(f"有效数据: {len(items)} 条")

    # 循环处理（替代并发）
    results = _process_with_loop(
        items, product_df, alias_df, None
    )

    # 保存结果
    _save_excel_results(df, results, oe_col, file_path)


def _process_with_loop(items, product_df, alias_df, db_manager=None, progress_callback=None, progress_offset=0, total_items=None):
    """
    使用循环逐个处理（替代并发）
    避免多线程冲突，提高稳定性
    支持进度回调
    """
    results = {}
    completed = 0
    total = len(items)
    overall_total = total_items if total_items is not None else total
    
    for item in items:
        oe_number = item['oe_number']
        
        try:
            result = process_single_oe(item, product_df, alias_df, db_manager)
            results[oe_number] = result
        except Exception as e:
            result = f"失败 - 处理异常: {e}"
            results[oe_number] = result
            print(f"❌ {oe_number}: {result}")
        
        completed += 1
        if completed % 10 == 0 or completed == total:
            print(f"进度: {completed}/{total}")
        
        # 调用进度回调（每处理一条调用一次，保证实时性）
        if progress_callback:
            overall_progress = progress_offset + completed
            progress_callback(overall_progress, overall_total, f"已处理 {completed}/{total}")
    
    print(f"\n处理完成: {total} 条")
    return results


def _process_with_loop_with_record(items, product_df, alias_df, db_manager=None, session=None):
    """
    使用循环逐个处理，并记录创建结果到 crmapp_created_products 表
    专用于数据库模式
    
    Args:
        items: 待处理的产品列表
        product_df: 产品数据 DataFrame
        alias_df: 别名数据 DataFrame
        db_manager: 数据库管理器
        session: 可选，已认证的 session
    """
    results = {}
    completed = 0
    total = len(items)
    
    for item in items:
        oe_number = item['oe_number']
        brand = item.get('brand', '')
        supplier_name = item.get('supplier_name', '')
        
        try:
            result = process_single_oe(item, product_df, alias_df, db_manager, session)
            results[oe_number] = result
            
            # 记录创建结果到 crmapp_created_products 表
            if db_manager:
                record_create_result(db_manager, oe_number, brand, supplier_name, result)
                
        except Exception as e:
            result = f"失败 - 处理异常: {e}"
            results[oe_number] = result
            print(f"❌ {oe_number}: {result}")
            
            # 记录失败结果
            if db_manager:
                record_create_result(db_manager, oe_number, brand, supplier_name, result)
        
        completed += 1
        if completed % 10 == 0 or completed == total:
            print(f"进度: {completed}/{total}")
    
    print(f"\n处理完成: {total} 条")
    return results


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
            WHEN update_msg LIKE 'OE号【%】处理结果：失败 - 未找到产品名称' THEN '新建失败-未找到产品名称'
            WHEN update_msg LIKE 'OE号【%】处理结果：失败 - 车型不能为空%' THEN '新建失败-车型不能为空'
            WHEN update_msg LIKE '过期时间【%】不能小于当前时间' THEN '上传失败-过期时间错误'
            WHEN update_msg LIKE '品牌名称【%】总部不存在,请核查数据' THEN '上传失败-品牌不存在'
            WHEN update_msg LIKE '物料所属品牌【%】OE号【%】产品数据不存在,请核查数据' THEN '上传失败-产品不存在'
            ELSE '其他'
        END
        WHERE update_status IS NULL OR update_status = ''
    """
    
    try:
        affected_rows = db_manager.execute_update(update_sql)
        print(f"✅ 已更新 {affected_rows} 条记录的 update_status")
    except Exception as e:
        print(f"❌ 更新 update_status 失败: {e}")
        import traceback
        traceback.print_exc()


def _identify_columns(df):
    """
    识别两列模式的列（oe, brand）
    """
    oe_columns = ['oe', 'OE', 'barcode', '物料条码']
    brand_columns = ['brand', '品牌', '品牌名称']
    
    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))
    
    oe_col = None
    brand_col = None
    
    for key in oe_columns:
        if key.lower() in columns_lower:
            oe_col = column_mapping[key.lower()]
            break
    
    for key in brand_columns:
        if key.lower() in columns_lower:
            brand_col = column_mapping[key.lower()]
            break
    
    if oe_col:
        print(f"识别到 OE 列: {oe_col}")
    if brand_col:
        print(f"识别到 Brand 列: {brand_col}")
    
    return oe_col, brand_col


def _identify_columns_extended(df):
    """
    识别三列模式的列（oe, brand, brand_code）
    """
    oe_col, brand_col = _identify_columns(df)
    
    brand_code_columns = ['brand_code', '条码', '物料条码', '品牌代码']
    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))
    
    brand_code_col = None
    for key in brand_code_columns:
        if key.lower() in columns_lower:
            brand_code_col = column_mapping[key.lower()]
            break
    
    if brand_code_col:
        print(f"识别到 Brand_Code 列: {brand_code_col}")
    
    return oe_col, brand_col, brand_code_col


def _save_excel_results(df, results, oe_col, original_file_path):
    """
    保存 Excel 结果
    """
    df['新建结果'] = ''
    
    for idx, row in df.iterrows():
        oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        if oe in results:
            df.at[idx, '新建结果'] = results[oe]
    
    # 生成输出路径
    base_name = os.path.splitext(original_file_path)[0]
    output_path = base_name + '_处理结果.xlsx'
    
    df.to_excel(output_path, index=False)
    print(f"结果已保存: {output_path}")


# ============================================================================
# 主入口
# ============================================================================

def select_mode():
    """
    选择处理模式
    """
    print("\n" + "="*50)
    print("CRM 产品添加工具")
    print("="*50)
    print("1. 数据库模式 - 从 MySQL 读取数据")
    print("2. 两列模式 - 从 Excel 读取 (oe + brand)")
    print("3. 三列模式 - 从 Excel 读取 (oe + brand + brand_code)")
    print("="*50)
    
    while True:
        choice = input("请选择模式 (1/2/3): ").strip()
        if choice in ['1', '2', '3']:
            return int(choice)
        print("无效选择，请重新输入")


def main():
    """
    主函数
    """
    # 选择模式
    mode = select_mode()
    
    # 创建 Session
    print("\n初始化 Session...")
    session = create_crm_session()
    print("Session 创建成功")
    
    # 加载 Excel 数据（所有模式都需要，用于产品名称匹配）
    print("加载 Excel 数据...")
    product_df = load_product_data()
    alias_df = load_alias_data()
    
    # 根据模式处理
    if mode == 1:
        process_database_mode(session, product_df, alias_df)
    elif mode == 2:
        # 两列模式文件路径
        file_path = r"E:\work download\project\BBR\flask项目\beihuo_system\static\excel\两列数据.xlsx"
        if os.path.exists(file_path):
            process_two_column_mode(session, product_df, alias_df, file_path)
        else:
            print(f"❌ 文件不存在: {file_path}")
    elif mode == 3:
        # 三列模式文件路径
        file_path = r"E:\work download\工作文件\锁机已手动处理.xls"
        if os.path.exists(file_path):
            process_three_column_mode(session, product_df, alias_df, file_path)
        else:
            print(f"❌ 文件不存在: {file_path}")
    
    print("\n程序执行完毕")


# ============================================================================
# 外部调用接口
# ============================================================================

def process_database_mode_api(supplier_name=None):
    """
    数据库模式 API 接口
    供虚拟库存上传后调用
    
    Args:
        supplier_name: 可选，指定供应商名称筛选数据，如 '佛山万拓'
    """
    if supplier_name:
        print(f"\n=== CRM Product Add - 数据库模式 (供应商: {supplier_name}) ===")
    else:
        print("\n=== CRM Product Add - 数据库模式 ===")
    
    # 创建 Session
    session = create_crm_session()
    print("Session 创建成功")
    
    # 加载 Excel 数据
    product_df = load_product_data()
    alias_df = load_alias_data()
    
    # 处理数据库模式（传入供应商名称参数）
    process_database_mode(session, product_df, alias_df, supplier_name)
    
    print("\n数据库模式处理完毕")
    return True


def process_excel_two_column_mode_api(file_path):
    """
    两列模式 API 接口
    供前端上传 Excel 后调用
    
    Args:
        file_path: Excel 文件路径
    
    Returns:
        结果文件路径
    """
    print(f"\n=== CRM Product Add - 两列模式 ===")
    print(f"文件: {file_path}")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 创建 Session
    session = create_crm_session()
    print("Session 创建成功")
    
    # 加载 Excel 数据
    product_df = load_product_data()
    alias_df = load_alias_data()
    
    # 处理两列模式
    result_file_path = process_two_column_mode_with_return(session, product_df, alias_df, file_path)
    
    print(f"\n两列模式处理完毕，结果: {result_file_path}")
    return result_file_path


def process_excel_three_column_mode_api(file_path):
    """
    三列模式 API 接口
    供前端上传 Excel 后调用
    
    Args:
        file_path: Excel 文件路径
    
    Returns:
        结果文件路径
    """
    print(f"\n=== CRM Product Add - 三列模式 ===")
    print(f"文件: {file_path}")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 创建 Session
    session = create_crm_session()
    print("Session 创建成功")
    
    # 加载 Excel 数据
    product_df = load_product_data()
    alias_df = load_alias_data()
    
    # 处理三列模式
    result_file_path = process_three_column_mode_with_return(session, product_df, alias_df, file_path)
    
    print(f"\n三列模式处理完毕，结果: {result_file_path}")
    return result_file_path


def process_two_column_mode_with_return(session, product_df, alias_df, file_path):
    """
    两列模式处理，支持多工作表，返回结果文件路径
    """
    print("\n【两列模式 - 多工作表】")
    
    # 读取所有工作表，使用 dtype=str 保留前导零
    try:
        if file_path.endswith('.csv'):
            # CSV 文件只有一个工作表
            all_sheets = {'Sheet1': pd.read_csv(file_path, dtype=str)}
            print(f"CSV文件按单个工作表处理")
        else:
            # Excel 文件读取所有工作表
            all_sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
            print(f"读取到 {len(all_sheets)} 个工作表: {list(all_sheets.keys())}")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        raise
    
    # 筛选符合两列模式的工作表
    valid_sheets = _filter_sheets_by_mode(all_sheets, 'two_column')
    
    if not valid_sheets:
        raise ValueError("没有找到符合两列模式要求的工作表")
    
    print(f"找到 {len(valid_sheets)} 个符合条件的工作表")
    
    # 处理每个工作表
    all_results = {}
    for sheet_name, sheet_info in valid_sheets.items():
        print(f"\n处理工作表: {sheet_name}")
        df = sheet_info['df']
        oe_col, brand_col = sheet_info['columns']
        
        # 准备处理项
        items = []
        for _, row in df.iterrows():
            oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            if oe and brand:
                items.append({
                    'oe_number': oe,
                    'brand': brand,
                    'mode': 'two_column'
                })
        
        print(f"  有效数据: {len(items)} 条")

        # 循环处理（替代并发）
        results = _process_with_loop(items, product_df, alias_df, None)
        all_results[sheet_name] = {'df': df, 'results': results, 'oe_col': oe_col}
    
    # 保存所有工作表结果到一个文件
    result_file_path = _save_multi_sheet_results(all_results, file_path)
    return result_file_path


def process_three_column_mode_with_return(session, product_df, alias_df, file_path):
    """
    三列模式处理，支持多工作表，返回结果文件路径
    """
    print("\n【三列模式 - 多工作表】")

    # 读取所有工作表，使用 dtype=str 保留前导零
    try:
        if file_path.endswith('.csv'):
            # CSV 文件只有一个工作表
            all_sheets = {'Sheet1': pd.read_csv(file_path, dtype=str)}
            print(f"CSV文件按单个工作表处理")
        else:
            # Excel 文件读取所有工作表
            all_sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
            print(f"读取到 {len(all_sheets)} 个工作表: {list(all_sheets.keys())}")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        raise
    
    # 筛选符合三列模式的工作表
    valid_sheets = _filter_sheets_by_mode(all_sheets, 'three_column')
    
    if not valid_sheets:
        raise ValueError("没有找到符合三列模式要求的工作表")
    
    print(f"找到 {len(valid_sheets)} 个符合条件的工作表")
    
    # 处理每个工作表
    all_results = {}
    for sheet_name, sheet_info in valid_sheets.items():
        print(f"\n处理工作表: {sheet_name}")
        df = sheet_info['df']
        oe_col, brand_col, brand_code_col = sheet_info['columns']
        
        # 准备处理项
        items = []
        for _, row in df.iterrows():
            oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
            if oe and brand:
                items.append({
                    'oe_number': oe,
                    'brand': brand,
                    'brand_code': brand_code,
                    'mode': 'three_column'
                })
        
        print(f"  有效数据: {len(items)} 条")

        # 循环处理（替代并发）
        results = _process_with_loop(items, product_df, alias_df, None)
        all_results[sheet_name] = {'df': df, 'results': results, 'oe_col': oe_col}

    # 保存所有工作表结果到一个文件
    result_file_path = _save_multi_sheet_results(all_results, file_path)
    return result_file_path


def _filter_sheets_by_mode(all_sheets, mode):
    """
    根据处理模式筛选符合条件的工作表
    """
    valid_sheets = {}
    for sheet_name, df in all_sheets.items():
        try:
            if mode == 'two_column':
                # 检查是否符合两列模式
                oe_col, brand_col = _identify_columns(df)
                if oe_col and brand_col:
                    valid_sheets[sheet_name] = {
                        'df': df,
                        'columns': (oe_col, brand_col)
                    }
                    print(f"  工作表 '{sheet_name}' 符合两列模式")
                else:
                    print(f"  工作表 '{sheet_name}' 不符合两列模式：缺少必要列")
            else:  # three_column
                # 检查是否符合三列模式
                oe_col, brand_col, brand_code_col = _identify_columns_extended(df)
                if oe_col and brand_col and brand_code_col:
                    valid_sheets[sheet_name] = {
                        'df': df,
                        'columns': (oe_col, brand_col, brand_code_col)
                    }
                    print(f"  工作表 '{sheet_name}' 符合三列模式")
                else:
                    print(f"  工作表 '{sheet_name}' 不符合三列模式：缺少必要列")
        except Exception as e:
            print(f"  工作表 '{sheet_name}' 处理出错: {e}")
            continue
    
    return valid_sheets


def _save_multi_sheet_results(all_results, original_file_path):
    """
    保存多工作表结果到一个 Excel 文件
    """
    # 生成输出路径
    base_name = os.path.splitext(original_file_path)[0]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"{base_name}_处理结果_{timestamp}.xlsx"
    
    # 使用 ExcelWriter 保存多个工作表
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, sheet_data in all_results.items():
            df = sheet_data['df'].copy()
            results = sheet_data['results']
            oe_col = sheet_data['oe_col']
            
            # 添加结果列
            df['新建结果'] = ''
            for idx, row in df.iterrows():
                oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
                if oe in results:
                    df.at[idx, '新建结果'] = results[oe]
            
            # 写入工作表（限制名称长度）
            safe_sheet_name = sheet_name[:31]  # Excel 工作表名称最多31个字符
            df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
    
    print(f"\n结果已保存: {output_path}")
    return output_path


def _save_excel_results_with_return(df, results, oe_col, original_file_path):
    """
    保存 Excel 结果，返回结果文件路径（单工作表兼容）
    """
    df['新建结果'] = ''
    
    for idx, row in df.iterrows():
        oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        if oe in results:
            df.at[idx, '新建结果'] = results[oe]
    
    # 生成输出路径
    base_name = os.path.splitext(original_file_path)[0]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"{base_name}_处理结果_{timestamp}.xlsx"
    
    df.to_excel(output_path, index=False)
    print(f"结果已保存: {output_path}")
    return output_path


def process_excel_async_wrapper(file_path: str, mode: str, progress_callback=None):
    """
    Excel异步处理包装器
    支持进度回调，供异步任务调用
    """
    from config import create_crm_session
    
    # 创建 Session
    session = create_crm_session()
    
    # 加载 Excel 数据
    from .excel_data_loader import load_product_data, load_alias_data
    product_df = load_product_data()
    alias_df = load_alias_data()
    
    # 读取所有工作表
    if file_path.endswith('.csv'):
        all_sheets = {'Sheet1': pd.read_csv(file_path, dtype=str)}
    else:
        all_sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
    
    # 筛选工作表
    valid_sheets = _filter_sheets_by_mode(all_sheets, mode)
    if not valid_sheets:
        raise ValueError("没有找到符合要求的工作表")
    
    # 计算总项目数
    total_items = sum(len(sheet['df']) for sheet in valid_sheets.values())
    
    processed = 0
    all_results = {}
    
    # 处理每个工作表
    for sheet_name, sheet_info in valid_sheets.items():
        df = sheet_info['df']
        columns = sheet_info['columns']
        oe_col = columns[0]
        brand_col = columns[1]
        
        # 准备处理项
        items = []
        for _, row in df.iterrows():
            oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            if oe and brand:
                item = {
                    'oe_number': oe,
                    'brand': brand,
                    'mode': mode
                }
                # 三列模式添加 brand_code
                if mode == 'three_column' and len(columns) > 2:
                    brand_code_col = columns[2]
                    brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
                    item['brand_code'] = brand_code
                items.append(item)
        
        # 处理并更新进度（传递progress_callback实现实时更新）
        results = _process_with_loop(items, product_df, alias_df, None, progress_callback, processed, total_items)
        all_results[sheet_name] = {'df': df, 'results': results, 'oe_col': oe_col}
        
        processed += len(items)
    
    # 保存结果
    result_path = _save_multi_sheet_results(all_results, file_path)
    
    # 清理临时文件
    import os
    os.remove(file_path)
    
    return result_path


if __name__ == "__main__":
    main()
