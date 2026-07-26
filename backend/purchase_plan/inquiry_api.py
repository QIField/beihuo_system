"""
询价模块API
功能：导入Excel/CSV文件、查看询价比价表格、B2B上传

【新流程】
1. B2B上传 → 返回update_msg
2. 筛选"产品不存在"的失败项 → CRM新建
3. 根据update_msg + create_result 判断九大类 → 生成"处理结果"
4. 生成"详情"列（有新建用新建结果，否则用update_msg）
5. 二次上传（针对新建成功的产品）
6. 生成Excel结果文件（原列 + 处理结果 + 详情 + 二次上传）
7. 将"处理结果"="上传成功"或二次上传成功的数据导入询价表
"""
from flask import Blueprint, request, jsonify, session, render_template, send_from_directory
from functools import wraps
import pandas as pd
import math
import os
import tempfile
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection
from app.services.procurement_service import add_inquiry_record, GzbbrQuoteService
from app.utils.search.parser import parse_space, parse_comma

# 导入B2B上传模块
from app.utils.b2b_inquiry_upload import get_recent_results

# 创建蓝图
inquiry_bp = Blueprint('inquiry', __name__)


@inquiry_bp.route('/inquiry_module')
def inquiry_module_page():
    """询价模块页面"""
    # 检查用户是否有权限
    if 'logged_in' not in session:
        return render_template('login.html')
    if not session.get('can_inquiry_module') and not session.get('is_admin'):
        return "您没有权限访问此页面", 403
    return render_template('purchase_plan/inquiry_module.html')


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def inquiry_permission_required(f):
    """询价模块权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        # 检查是否有询价模块权限或是admin
        if not session.get('can_inquiry_module') and not session.get('is_admin'):
            return jsonify({'code': 1, 'msg': '您没有权限访问询价模块'}), 403
        return f(*args, **kwargs)
    return decorated_function


def _get_current_store_code():
    """获取当前用户门店代码"""
    return session.get('current_org') or session.get('store') or 'fsbbr'


@inquiry_bp.route('/import', methods=['POST'])
@login_required
def import_price_data():
    """
    导入Excel或CSV文件到询价比价表（异步版本）
    提交任务后立即返回task_id，前端通过task_id轮询状态
    """
    if 'file' not in request.files:
        return jsonify({'code': 1, 'msg': '请选择要上传的文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 1, 'msg': '请选择要上传的文件'}), 400

    # 获取当前用户名和公司
    creator = session.get('username', 'unknown')
    company = session.get('current_org', session.get('store', 'fsbbr'))

    try:
        # 保存临时文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(tempfile.gettempdir(), f"inquiry_async_{timestamp}_{file.filename}")
        file.save(temp_path)
        
        # 获取加价倍数
        markup_rate = request.form.get('markup_rate', '1')
        
        # 获取是否跳过B2B推送
        skip_b2b = request.form.get('skip_b2b', 'false').lower() == 'true'
        
        # 获取是否启用采购历史比对
        enable_compare = request.form.get('enable_compare', 'false').lower() == 'true'
        
        # 提交异步任务
        from app.core.async_task_store import submit_excel_task
        task_id = submit_excel_task(
            process_inquiry_import_async,
            temp_path,
            markup_rate,
            creator,
            company,
            skip_b2b,
            enable_compare
        )
        
        return jsonify({
            'code': 0,
            'msg': '任务已提交',
            'data': {'task_id': task_id}
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'提交失败: {str(e)}'}), 500


@inquiry_bp.route('/import/status/<task_id>', methods=['GET'])
@login_required
def get_inquiry_import_status(task_id):
    """查询询价导入任务状态"""
    from app.core.async_task_store import get_task_status
    
    status = get_task_status(task_id)
    if not status:
        return jsonify({'code': 1, 'msg': '任务不存在'}), 404
    
    return jsonify({
        'code': 0,
        'msg': '获取成功',
        'data': status
    })


@inquiry_bp.route('/import/download/<task_id>', methods=['GET'])
@login_required
def download_inquiry_import_result(task_id):
    """下载询价导入结果文件"""
    from app.core.async_task_store import get_task_status
    from flask import send_file
    import os
    
    status = get_task_status(task_id)
    if not status:
        return jsonify({'code': 1, 'msg': '任务不存在'}), 404
    
    if status['status'] != 'completed':
        return jsonify({'code': 1, 'msg': '任务尚未完成'}), 400
    
    result_file = status.get('result_file')
    if not result_file or not os.path.exists(result_file):
        return jsonify({'code': 1, 'msg': '结果文件不存在'}), 404
    
    return send_file(
        result_file,
        as_attachment=True,
        download_name=os.path.basename(result_file)
    )


def process_inquiry_import_async(file_path: str, markup_rate: str, creator: str, company: str, skip_b2b: bool = False, enable_compare: bool = False, progress_callback=None):
    """
    询价导入异步处理函数（完整版）
    支持进度回调，包含完整8步流程
    
    参数:
        skip_b2b: 是否跳过B2B推送，直接入库
    """
    # 读取文件
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path, encoding='utf-8', dtype=str)
    else:
        df = pd.read_excel(file_path, dtype=str)
    
    # 保存原始列名
    original_columns = list(df.columns)
    
    # 列名映射
    column_mapping = {
        'oe': 'oe', 'OE': 'oe', 'OE号': 'oe',
        '品牌': 'brand', 'brand': 'brand',
        '供应商': 'supplier', 'supplier': 'supplier',
        '单价': 'price', 'price': 'price', '价格': 'price',
        '仓库': 'warehouse', 'warehouse': 'warehouse',
        '失效时间': 'expire_time', 'expire_time': 'expire_time',
        '备注': 'remark', 'remark': 'remark',
        '库存数量': 'stock_quantity', 'stock_quantity': 'stock_quantity',
        '通用号': 'common_number', 'common_number': 'common_number'
    }
    
    rename_dict = {old: new for old, new in column_mapping.items() 
                   if old in df.columns and new not in df.columns}
    if rename_dict:
        df = df.rename(columns=rename_dict)
    
    df = df.where(pd.notnull(df), None)
    
    # 价格加价处理
    try:
        markup_rate = float(markup_rate)
    except:
        markup_rate = 1
    
    if markup_rate != 1 and 'price' in df.columns:
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['original_price'] = df['price'].copy()
        df['price'] = (df['price'] * markup_rate).round(2)
    
    # 准备数据（询价模块不使用品牌别名映射）
    from app.utils.b2b_inquiry_upload.uploader import prepare_data, batch_upload_with_callback
    valid_items, skipped_items = prepare_data(df)

    # 询价模块专用：过滤价格为空或为0的数据
    for item in valid_items[:]:
        price = item.get('price', 0)
        if not price or price == 0:
            item['skip_reason'] = '价格为空或为0'
            skipped_items.append(item)
            valid_items.remove(item)

    if not valid_items:
        raise ValueError('没有有效的数据可导入')
    
    total = len(valid_items)
    processed = 0
    
    # 如果跳过B2B推送，直接走直接入库流程
    if skip_b2b:
        return _process_direct_import(
            valid_items, skipped_items, df, original_columns, column_mapping,
            file_path, creator, company, markup_rate, progress_callback
        )
    
    # 步骤1：B2B上传（带进度回调）
    def item_callback(result):
        nonlocal processed
        processed += 1
        if progress_callback:
            progress_callback(processed, total, f"B2B上传: {result.get('oe', '')}")
    
    b2b_results = batch_upload_with_callback(valid_items, callback=item_callback, brand_mapping={})
    
    # 合并结果到valid_items（询价模块保持原始品牌）
    for item in valid_items:
        oe = item['oe']
        result = b2b_results.get(oe, {})
        item['update_msg'] = result.get('update_msg', '未知错误')
        item['b2b_status'] = result.get('status', 'error')
    
    # 步骤2：筛选需要CRM新建的项（询价模块保持原始品牌，不做别名映射）
    need_create_items = []
    for item in valid_items:
        if '产品数据不存在' in item.get('update_msg', ''):
            need_create_items.append({
                'oe_number': item['oe'],
                'brand': item['brand'],
                'supplier_name': item.get('supplier', ''),
                'mode': 'inquiry'
            })
    
    # 步骤3：CRM新建
    create_results = {}
    if need_create_items:
        from config import create_crm_session
        from app.utils.crm_product.crm_productAdd.excel_data_loader import load_alias_data, load_product_data
        from app.utils.crm_product.crm_productAdd.crm_processor import process_items, _format_result_message

        alias_df = load_alias_data()
        product_df = load_product_data()
        session = create_crm_session()
        try:
            raw_results = process_items(need_create_items, product_df, alias_df, session, use_brand_alias=False)
            create_results = {
                (oe, brand): _format_result_message(result)
                for (oe, brand), result in raw_results.items()
            }
        finally:
            session.close()

        if progress_callback:
            progress_callback(total, total, "CRM新建完成")
    
    # 步骤4：二次上传（针对新建成功的产品，询价模块保持原始品牌）
    second_upload_items = []
    for item in valid_items:
        oe = item['oe']
        brand = item['brand']
        create_result = create_results.get((oe, brand), '')
        if create_result and ('已存在' in create_result or ('成功' in create_result and '失败' not in create_result)):
            second_upload_items.append(item)
    
    second_upload_results = {}
    if second_upload_items:
        second_b2b_results = batch_upload_with_callback(second_upload_items, callback=item_callback, brand_mapping={})
        for item in second_upload_items:
            oe = item['oe']
            result = second_b2b_results.get(oe, {})
            second_upload_results[oe] = result.get('update_msg', '')
    
    # 步骤5：九分类判断
    category_count = {
        '上传成功': 0, '新建成功-已存在': 0, '新建成功-新创建': 0,
        '新建失败-未返回产品名称': 0, '新建失败-未返回车型': 0, '新建失败-未返回原厂品牌': 0,
        '上传失败-过期时间错误': 0, '上传失败-品牌不存在': 0,
        '上传失败-产品不存在': 0, '其他': 0
    }
    
    for item in valid_items:
        oe = item['oe']
        brand = item['brand']
        update_msg = item.get('update_msg', '')
        create_result = create_results.get((oe, brand), '')
        
        category = _classify_nine_category(update_msg, create_result)
        item['处理结果'] = category
        item['详情'] = _get_detail_message(update_msg, create_result)
        item['二次上传'] = second_upload_results.get(oe, '')
        category_count[category] = category_count.get(category, 0) + 1
    
    for item in skipped_items:
        item['处理结果'] = '其他'
        item['详情'] = f"跳过: {item.get('skip_reason', '')}"
        item['二次上传'] = ''
        category_count['其他'] = category_count.get('其他', 0) + 1
    
    # 步骤6：生成Excel结果文件
    all_items = valid_items + skipped_items
    result_data = []
    
    for item in all_items:
        row_data = {}
        for orig_col in original_columns:
            english_col = column_mapping.get(orig_col, orig_col)
            if english_col in ['oe', 'brand', 'supplier', 'price', 'warehouse', 'expire_time', 'stock_quantity', 'remark']:
                value = item.get(english_col, '')
                if value is None or (isinstance(value, float) and math.isnan(value)) or str(value).lower() == 'nan':
                    value = ''
                row_data[orig_col] = value
            else:
                idx = item.get('index')
                if idx is not None and idx < len(df):
                    value = df.iloc[idx].get(english_col, '')
                    if value is None or (isinstance(value, float) and math.isnan(value)) or str(value).lower() == 'nan':
                        value = ''
                    row_data[orig_col] = value
                else:
                    row_data[orig_col] = ''
        
        row_data['处理结果'] = item.get('处理结果', '')
        row_data['详情'] = item.get('详情', '')
        row_data['二次上传'] = item.get('二次上传', '')
        result_data.append(row_data)
    
    result_df = pd.DataFrame(result_data)
    output_cols = list(original_columns) + ['处理结果', '详情', '二次上传']
    result_df = result_df[output_cols]
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_filename = f'inquiry_upload_result_{timestamp}.xlsx'
    result_dir = 'static/uploads/b2b_results'
    os.makedirs(result_dir, exist_ok=True)
    result_path = os.path.join(result_dir, result_filename)
    result_df.to_excel(result_path, index=False)
    
    # 步骤7：导入数据库
    upload_success_items = []
    for item in valid_items:
        if item.get('处理结果') == '上传成功':
            upload_success_items.append(item)
        elif item.get('二次上传'):
            second_msg = item.get('二次上传', '')
            if '上传add成功' in second_msg or '上传update成功' in second_msg:
                upload_success_items.append(item)
    
    inserted_count = 0
    if upload_success_items:
        insert_data = []
        for item in upload_success_items:
            oe = item['oe']
            brand = item.get('brand') or None
            supplier = item.get('supplier') or None
            price = item.get('price', 0)
            original_price = item.get('original_price', price)
            try:
                markup_amount = round(float(price) - float(original_price), 2) if price and original_price else 0
            except (ValueError, TypeError):
                markup_amount = 0
            warehouse = item.get('warehouse') or None
            expire_time = item.get('expire_time')
            remark = item.get('remark')
            if remark and str(remark).lower() == 'nan':
                remark = None
            elif remark:
                remark = str(remark).strip() or None
            stock_quantity = item.get('stock_quantity', 0)
            
            # 处理失效时间
            if expire_time and pd.notna(expire_time):
                if isinstance(expire_time, str):
                    expire_time = expire_time.strip()
                    parsed = False
                    for fmt in ['%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y/%m/%d']:
                        try:
                            expire_time = datetime.strptime(expire_time, fmt)
                            parsed = True
                            break
                        except ValueError:
                            continue
                    if not parsed:
                        expire_time = None
            else:
                expire_time = None
            
            insert_data.append({
                'oe': oe, 'brand': brand, 'supplier': supplier, 'price': price,
                'original_price': original_price, 'markup_rate': markup_rate,
                'markup_amount': markup_amount,
                'warehouse': warehouse,
                'expire_time': expire_time, 'remark': remark,
                'stock_quantity': stock_quantity, 'common_number': None,
                'company': company
            })
        
        if insert_data:
            conn = get_db_connection()
            cursor = conn.cursor()
            batch_insert_data = []
            for data in insert_data:
                cursor.execute("""
                    SELECT replace_number, is_cass FROM crmapp_compare_summary 
                    WHERE oe = %s AND brand = %s AND company = %s
                """, (data['oe'], data['brand'], data['company']))
                compare_result = cursor.fetchone()
                
                # 使用字段名访问，兼容字典和元组两种返回格式
                if compare_result:
                    if isinstance(compare_result, dict):
                        sync_common_number = compare_result.get('replace_number', '') or ''
                        sync_ks_sync = 1 if compare_result.get('is_cass') and str(compare_result.get('is_cass')) == '1' else 0
                    else:
                        sync_common_number = compare_result[0] if compare_result[0] else ''
                        sync_ks_sync = 1 if compare_result[1] and str(compare_result[1]) == '1' else 0
                else:
                    sync_common_number = ''
                    sync_ks_sync = 0
                
                batch_insert_data.append((
                    data['oe'], data['brand'], data['supplier'], data['price'], data['original_price'], data['markup_rate'], data['markup_amount'], data['warehouse'],
                    data['expire_time'], data['remark'], data['stock_quantity'],
                    sync_common_number, sync_ks_sync, data['company']
                ))

            # 使用 INSERT ... ON DUPLICATE KEY UPDATE 实现覆盖更新
            for row_data in batch_insert_data:
                cursor.execute("""
                    INSERT INTO crmapp_price_inquiry
                    (oe, brand, supplier, price, original_price, markup_rate, markup_amount, warehouse, expire_time, remark,
                     stock_quantity, common_number, ks_sync, company)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        original_price = VALUES(original_price),
                        markup_rate = VALUES(markup_rate),
                        markup_amount = VALUES(markup_amount),
                        warehouse = VALUES(warehouse),
                        expire_time = VALUES(expire_time),
                        remark = VALUES(remark),
                        stock_quantity = VALUES(stock_quantity),
                        common_number = VALUES(common_number),
                        ks_sync = VALUES(ks_sync),
                        import_time = CURRENT_TIMESTAMP
                """, row_data)
            
            conn.commit()
            inserted_count = len(batch_insert_data)
            cursor.close()
            conn.close()
    
    # 步骤8：触发聚合和同步（异步执行，不阻塞返回）
    if inserted_count > 0:
        _trigger_aggregate_async(company, upload_success_items)

    # 清理临时文件
    os.remove(file_path)

    return result_path


def _process_direct_import(valid_items, skipped_items, df, original_columns, column_mapping, 
                           file_path, creator, company, markup_rate, progress_callback):
    """
    处理直接入库流程（跳过B2B推送）
    """
    import os
    from datetime import datetime
    
    total = len(valid_items)
    
    # 直接入库，所有数据都标记为成功（询价模块保持原始品牌，不做别名映射）
    for item in valid_items:
        item['处理结果'] = '直接入库'
        item['详情'] = '跳过B2B推送，直接入库'
        item['二次上传'] = ''
        
        if progress_callback:
            progress_callback(valid_items.index(item) + 1, total, f"处理: {item.get('oe', '')}")
    
    for item in skipped_items:
        item['处理结果'] = '其他'
        item['详情'] = f"跳过: {item.get('skip_reason', '')}"
        item['二次上传'] = ''
    
    # 生成Excel结果文件
    all_items = valid_items + skipped_items
    result_data = []
    
    for item in all_items:
        row_data = {}
        for orig_col in original_columns:
            english_col = column_mapping.get(orig_col, orig_col)
            if english_col in ['oe', 'brand', 'supplier', 'price', 'warehouse', 'expire_time', 'stock_quantity', 'remark']:
                value = item.get(english_col, '')
                if value is None or (isinstance(value, float) and math.isnan(value)) or str(value).lower() == 'nan':
                    value = ''
                row_data[orig_col] = value
            else:
                idx = item.get('index')
                if idx is not None and idx < len(df):
                    value = df.iloc[idx].get(english_col, '')
                    if value is None or (isinstance(value, float) and math.isnan(value)) or str(value).lower() == 'nan':
                        value = ''
                    row_data[orig_col] = value
                else:
                    row_data[orig_col] = ''
        
        row_data['处理结果'] = item.get('处理结果', '')
        row_data['详情'] = item.get('详情', '')
        row_data['二次上传'] = item.get('二次上传', '')
        result_data.append(row_data)
    
    result_df = pd.DataFrame(result_data)
    output_cols = list(original_columns) + ['处理结果', '详情', '二次上传']
    result_df = result_df[output_cols]
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_filename = f'inquiry_direct_result_{timestamp}.xlsx'
    result_dir = 'static/uploads/b2b_results'
    os.makedirs(result_dir, exist_ok=True)
    result_path = os.path.join(result_dir, result_filename)
    result_df.to_excel(result_path, index=False)
    
    # 导入到直接入库表（所有有效数据）
    insert_data = []
    for item in valid_items:
        oe = item['oe']
        brand = item.get('brand') or None
        supplier = item.get('supplier') or None
        price = item.get('price', 0)
        original_price = item.get('original_price', price)
        try:
            markup_amount = round(float(price) - float(original_price), 2) if price and original_price else 0
        except (ValueError, TypeError):
            markup_amount = 0
        warehouse = item.get('warehouse') or None
        expire_time = item.get('expire_time')
        remark = item.get('remark')
        if remark and str(remark).lower() == 'nan':
            remark = None
        elif remark:
            remark = str(remark).strip() or None
        stock_quantity = item.get('stock_quantity', 0)
        
        # 处理失效时间
        if expire_time and pd.notna(expire_time):
            if isinstance(expire_time, str):
                expire_time = expire_time.strip()
                parsed = False
                for fmt in ['%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y/%m/%d']:
                    try:
                        expire_time = datetime.strptime(expire_time, fmt)
                        parsed = True
                        break
                    except ValueError:
                        continue
                if not parsed:
                    expire_time = None
        else:
            expire_time = None
        
        insert_data.append({
            'oe': oe, 'brand': brand, 'supplier': supplier, 'price': price,
            'original_price': original_price, 'markup_rate': markup_rate,
            'markup_amount': markup_amount,
            'warehouse': warehouse,
            'expire_time': expire_time, 'remark': remark,
            'stock_quantity': stock_quantity, 'common_number': None,
            'company': company, 'creator': creator,
            'source_file': os.path.basename(file_path)
        })
    
    inserted_count = 0
    if insert_data:
        conn = get_db_connection()
        cursor = conn.cursor()
        batch_insert_data = []
        for data in insert_data:
            cursor.execute("""
                SELECT replace_number, is_cass FROM crmapp_compare_summary 
                WHERE oe = %s AND brand = %s AND company = %s
            """, (data['oe'], data['brand'], data['company']))
            compare_result = cursor.fetchone()
            
            # 使用字段名访问，兼容字典和元组两种返回格式
            if compare_result:
                if isinstance(compare_result, dict):
                    sync_common_number = compare_result.get('replace_number', '') or ''
                    sync_ks_sync = 1 if compare_result.get('is_cass') and str(compare_result.get('is_cass')) == '1' else 0
                else:
                    sync_common_number = compare_result[0] if compare_result[0] else ''
                    sync_ks_sync = 1 if compare_result[1] and str(compare_result[1]) == '1' else 0
            else:
                sync_common_number = ''
                sync_ks_sync = 0
            
            batch_insert_data.append((
                data['oe'], data['brand'], data['supplier'], data['price'], data['original_price'], data['markup_rate'], data['markup_amount'], data['warehouse'],
                data['expire_time'], data['remark'], data['stock_quantity'],
                sync_common_number, sync_ks_sync, data['company'], data['creator'], data['source_file']
            ))

        # 使用 INSERT ... ON DUPLICATE KEY UPDATE 实现覆盖更新
        for row_data in batch_insert_data:
            cursor.execute("""
                INSERT INTO crmapp_price_inquiry_direct
                (oe, brand, supplier, price, original_price, markup_rate, markup_amount, warehouse, expire_time, remark,
                 stock_quantity, common_number, ks_sync, company, creator, source_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    original_price = VALUES(original_price),
                    markup_rate = VALUES(markup_rate),
                    markup_amount = VALUES(markup_amount),
                    warehouse = VALUES(warehouse),
                    expire_time = VALUES(expire_time),
                    remark = VALUES(remark),
                    stock_quantity = VALUES(stock_quantity),
                    common_number = VALUES(common_number),
                    ks_sync = VALUES(ks_sync),
                    creator = VALUES(creator),
                    source_file = VALUES(source_file),
                    import_time = CURRENT_TIMESTAMP
            """, row_data)
        
        conn.commit()
        inserted_count = len(batch_insert_data)
        cursor.close()
        conn.close()
    
    # 触发聚合和同步（异步执行，不阻塞返回）
    # 直接入库模式不传 upload_success_items，跳过 BatchChannel 推送
    if inserted_count > 0:
        _trigger_aggregate_async(company)

    # 清理临时文件
    os.remove(file_path)

    return result_path


def _trigger_aggregate_async(company: str, upload_success_items: list = None):
    """
    异步触发聚合和同步任务
    不阻塞主流程，在后台线程中执行

    Args:
        company: 门店代码
        upload_success_items: 上传成功的数据列表（仅上传模式有值）
    """
    import threading

    def run_aggregate():
        try:
            print(f"[InquiryImport] 开始异步聚合和同步, company={company}")

            # 1. 聚合三个表数据
            from app.services.procurement_service.purchase_history_aggregate_service import PurchaseHistoryAggregateService
            aggregate_service = PurchaseHistoryAggregateService()
            aggregate_result = aggregate_service.aggregate_and_update(
                sources=['procurement_detail', 'price_inquiry', 'price_inquiry_direct'],
                company=company
            )
            print(f"[InquiryImport] 聚合完成: {aggregate_result}")

            # 2. 同步到比价表
            from app.services.procurement_service.purchase_sync_service import PurchaseSyncService
            sync_service = PurchaseSyncService()
            sync_result = sync_service.sync_to_compare_summary(company)
            print(f"[InquiryImport] 同步完成: {sync_result}")

            # 3. 批量推送渠道价格（仅在上传模式下）
            if upload_success_items:
                from app.services.procurement_service.batch_channel_push_service import push_to_batch_channel
                push_to_batch_channel(upload_success_items, company)

        except Exception as e:
            print(f"[InquiryImport] 异步聚合同步失败: {e}")
            import traceback
            traceback.print_exc()

    # 在后台线程中执行
    thread = threading.Thread(target=run_aggregate)
    thread.daemon = True
    thread.start()
    print(f"[InquiryImport] 已启动异步聚合线程")


def _classify_nine_category(update_msg: str, create_result: str) -> str:
    """九分类判断"""
    if '上传add成功' in update_msg or '上传update成功' in update_msg:
        return '上传成功'
    elif '新建成功' in create_result and '已存在' in create_result:
        return '新建成功-已存在'
    elif '新建成功' in create_result and '失败' not in create_result:
        return '新建成功-新创建'
    elif '未返回产品名称' in create_result:
        return '新建失败-未返回产品名称'
    elif '未返回车型' in create_result:
        return '新建失败-未返回车型'
    elif '未返回原厂品牌' in create_result:
        return '新建失败-未返回原厂品牌'
    elif '过期时间' in update_msg and '错误' in update_msg:
        return '上传失败-过期时间错误'
    elif '品牌不存在' in update_msg:
        return '上传失败-品牌不存在'
    elif '产品数据不存在' in update_msg:
        return '上传失败-产品不存在'
    else:
        return '其他'


def _get_detail_message(update_msg: str, create_result: str) -> str:
    """获取详情信息"""
    if create_result:
        return create_result
    return update_msg


@inquiry_bp.route('/list', methods=['GET'])
@inquiry_permission_required
def get_inquiry_list():
    """
    获取询价比价表格数据
    返回扁平化数据，用于AG Grid
    根据用户所在组织过滤数据
    """
    try:
        # 获取查询参数
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        supplier = request.args.get('supplier', '').strip()
        
        # 获取用户当前切换到的组织
        company = session.get('current_org', session.get('store', 'fsbbr'))

        # 构建查询条件
        where_conditions = []
        params = []

        # 必须按用户所在组织过滤
        where_conditions.append("company = %s")
        params.append(company)

        # 处理多行搜索
        oe_list = parse_space(oe) if oe else []
        brand_list = parse_comma(brand) if brand else []
        supplier_list = parse_comma(supplier) if supplier else []

        if oe_list:
            or_conditions = []
            for item in oe_list:
                or_conditions.append("oe LIKE %s")
                params.append(f"%{item}%")
            where_conditions.append("(" + " OR ".join(or_conditions) + ")")

        if brand_list:
            or_conditions = []
            for item in brand_list:
                or_conditions.append("brand LIKE %s")
                params.append(f"%{item}%")
            where_conditions.append("(" + " OR ".join(or_conditions) + ")")

        if supplier_list:
            or_conditions = []
            for item in supplier_list:
                or_conditions.append("supplier LIKE %s")
                params.append(f"%{item}%")
            where_conditions.append("(" + " OR ".join(or_conditions) + ")")

        where_clause = "WHERE " + " AND ".join(where_conditions)

        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        # 查询所有数据
        data_sql = f"""
            SELECT id, oe, brand, supplier, price, original_price, markup_rate, markup_amount, warehouse, expire_time, remark, stock_quantity, common_number, ks_sync, import_time
            FROM crmapp_price_inquiry
            {where_clause}
            ORDER BY oe, brand, id DESC
        """
        cursor.execute(data_sql, params)

        # 获取列名和数据
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        # 转换为字典列表并格式化日期
        data_list = []
        for row in rows:
            # 如果row已经是字典，直接使用；否则进行zip转换
            if isinstance(row, dict):
                item = row
            else:
                item = dict(zip(columns, row))
            # 格式化失效时间（仅当是datetime类型时）
            if item.get('expire_time') and hasattr(item['expire_time'], 'strftime'):
                item['expire_time'] = item['expire_time'].strftime('%Y-%m-%d %H:%M:%S')
            # 格式化上传时间（仅当是datetime类型时）
            if item.get('import_time') and hasattr(item['import_time'], 'strftime'):
                item['import_time'] = item['import_time'].strftime('%Y-%m-%d %H:%M:%S')
            # 处理备注字段：如果是None或'None'字符串，设为空值
            if item.get('remark') is None or item.get('remark') == 'None':
                item['remark'] = ''
            data_list.append(item)

        cursor.close()
        conn.close()

        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': data_list,
            'total': len(data_list)
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取数据失败: {str(e)}'}), 500


@inquiry_bp.route('/direct/list', methods=['GET'])
@inquiry_permission_required
def get_direct_inquiry_list():
    """
    获取直接入库数据列表
    返回扁平化数据，用于AG Grid
    根据用户所在组织过滤数据
    """
    try:
        # 获取查询参数
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        supplier = request.args.get('supplier', '').strip()
        
        # 获取用户当前切换到的组织
        company = session.get('current_org', session.get('store', 'fsbbr'))

        # 构建查询条件
        where_conditions = []
        params = []

        # 必须按用户所在组织过滤
        where_conditions.append("company = %s")
        params.append(company)

        # 处理多行搜索
        oe_list = parse_space(oe) if oe else []
        brand_list = parse_comma(brand) if brand else []
        supplier_list = parse_comma(supplier) if supplier else []

        if oe_list:
            or_conditions = []
            for item in oe_list:
                or_conditions.append("oe LIKE %s")
                params.append(f"%{item}%")
            where_conditions.append("(" + " OR ".join(or_conditions) + ")")

        if brand_list:
            or_conditions = []
            for item in brand_list:
                or_conditions.append("brand LIKE %s")
                params.append(f"%{item}%")
            where_conditions.append("(" + " OR ".join(or_conditions) + ")")

        if supplier_list:
            or_conditions = []
            for item in supplier_list:
                or_conditions.append("supplier LIKE %s")
                params.append(f"%{item}%")
            where_conditions.append("(" + " OR ".join(or_conditions) + ")")

        where_clause = "WHERE " + " AND ".join(where_conditions)

        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        # 查询所有数据
        data_sql = f"""
            SELECT id, oe, brand, supplier, price, original_price, markup_rate, markup_amount, warehouse, expire_time, remark, stock_quantity, common_number, ks_sync, import_time
            FROM crmapp_price_inquiry_direct
            {where_clause}
            ORDER BY oe, brand, id DESC
        """
        cursor.execute(data_sql, params)

        # 获取列名和数据
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        # 转换为字典列表并格式化日期
        data_list = []
        for row in rows:
            # 如果row已经是字典，直接使用；否则进行zip转换
            if isinstance(row, dict):
                item = row
            else:
                item = dict(zip(columns, row))
            # 格式化失效时间（仅当是datetime类型时）
            if item.get('expire_time') and hasattr(item['expire_time'], 'strftime'):
                item['expire_time'] = item['expire_time'].strftime('%Y-%m-%d %H:%M:%S')
            # 格式化上传时间（仅当是datetime类型时）
            if item.get('import_time') and hasattr(item['import_time'], 'strftime'):
                item['import_time'] = item['import_time'].strftime('%Y-%m-%d %H:%M:%S')
            # 处理备注字段：如果是None或'None'字符串，设为空值
            if item.get('remark') is None or item.get('remark') == 'None':
                item['remark'] = ''
            data_list.append(item)

        cursor.close()
        conn.close()

        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': data_list,
            'total': len(data_list)
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取数据失败: {str(e)}'}), 500


@inquiry_bp.route('/b2b_upload_history', methods=['GET'])
@login_required
def get_b2b_upload_history():
    """
    获取B2B上传历史记录（7天内）
    """
    try:
        files = get_recent_results(days=7)
        
        # 添加下载链接
        for file in files:
            file['download_url'] = f"/api/purchase_plan/inquiry/b2b_upload_download/{file['filename']}"
        
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': files
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取历史记录失败: {str(e)}'}), 500


@inquiry_bp.route('/b2b_upload_download/<filename>', methods=['GET'])
@login_required
def download_b2b_result(filename):
    """
    下载B2B上传结果文件
    """
    try:
        output_dir = 'static/uploads/b2b_results'
        # 安全检查：防止目录遍历
        safe_filename = os.path.basename(filename)
        
        return send_from_directory(
            output_dir,
            safe_filename,
            as_attachment=True,
            download_name=safe_filename
        )
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'下载失败: {str(e)}'}), 500


@inquiry_bp.route('/crm_brands', methods=['GET'])
@login_required
def get_crm_brands():
    """
    查询CRM品牌列表
    根据关键字搜索品牌，返回所有匹配的l_name_zh
    """
    keyword = request.args.get('keyword', '').strip()
    
    try:
        # 导入CRM品牌查询模块
        from app.utils.crm_product.crm_productAdd.crm_brand_id import get_brand_list
        from config import create_crm_session
        
        # 创建CRM session
        session = create_crm_session()
        
        # 准备请求参数
        params = {}
        if keyword:
            params['l_name_zh'] = keyword
        
        # 调用CRM API获取品牌列表
        result = get_brand_list(params=params, session=session)
        
        if result and result.get('status') == 200:
            brand_list = result.get('data', {}).get('list', [])
            # 提取所有l_name_zh字段
            brand_names = [item['l_name_zh'] for item in brand_list if item.get('l_name_zh')]
            
            return jsonify({
                'code': 0,
                'msg': '获取成功',
                'data': brand_names,
                'total': len(brand_names)
            })
        else:
            return jsonify({
                'code': 1,
                'msg': result.get('msg', '查询失败'),
                'data': []
            }), 500
            
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'查询品牌失败: {str(e)}', 'data': []}), 500


@inquiry_bp.route('/b2b_suppliers', methods=['GET'])
@login_required
def get_b2b_suppliers():
    """
    获取B2B供应商列表
    返回所有供应商名称列表
    """
    try:
        from app.utils.b2b_inquiry_upload.uploader import login, getAllSupplierChannel
        
        token = login('fsbbr')
        supplier_df = getAllSupplierChannel(token)
        
        if supplier_df is None or supplier_df.empty:
            return jsonify({
                'code': 0,
                'msg': '获取成功',
                'data': [],
                'total': 0
            })
        
        supplier_names = supplier_df['name'].dropna().astype(str).tolist()
        
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': supplier_names,
            'total': len(supplier_names)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'获取供应商失败: {str(e)}', 'data': []}), 500


def _parse_inquiry_file(file):
    """
    解析询价模块上传文件，返回DataFrame
    """
    # 保存临时文件
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_path = os.path.join(tempfile.gettempdir(), f"precheck_{timestamp}_{file.filename}")
    file.save(temp_path)
    
    try:
        # 读取文件
        if file.filename.endswith('.csv'):
            df = pd.read_csv(temp_path, encoding='utf-8', dtype=str)
        else:
            df = pd.read_excel(temp_path, dtype=str)
        
        # 列名映射
        column_mapping = {
            'oe': 'oe', 'OE': 'oe', 'OE号': 'oe',
            '品牌': 'brand', 'brand': 'brand',
            '供应商': 'supplier', 'supplier': 'supplier',
            '单价': 'price', 'price': 'price', '价格': 'price',
            '仓库': 'warehouse', 'warehouse': 'warehouse',
            '失效时间': 'expire_time', 'expire_time': 'expire_time',
            '备注': 'remark', 'remark': 'remark',
            '库存数量': 'stock_quantity', 'stock_quantity': 'stock_quantity',
            '通用号': 'common_number', 'common_number': 'common_number'
        }
        
        rename_dict = {old: new for old, new in column_mapping.items() 
                       if old in df.columns and new not in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        return df, temp_path
    except Exception:
        os.remove(temp_path)
        raise


@inquiry_bp.route('/precheck', methods=['POST'])
@login_required
def precheck_inquiry_file():
    """
    询价模块上传文件预检
    提取文件中的品牌和供应商，分别与CRM品牌、B2B供应商进行精准匹配
    返回未匹配的品牌和供应商列表
    
    请求: multipart/form-data, file
    返回:
    {
        "code": 0,
        "data": {
            "unmatched_brands": ["品牌1", ...],
            "unmatched_suppliers": ["供应商1", ...],
            "brand_count": 1,
            "supplier_count": 1
        }
    }
    """
    if 'file' not in request.files:
        return jsonify({'code': 1, 'msg': '请选择要上传的文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 1, 'msg': '请选择要上传的文件'}), 400

    temp_path = None
    try:
        df, temp_path = _parse_inquiry_file(file)
        df = df.where(pd.notnull(df), None)
        
        # 提取唯一的品牌和供应商
        brands = set()
        suppliers = set()
        for _, row in df.iterrows():
            brand = str(row.get('brand', '')).strip() if row.get('brand') else ''
            supplier = str(row.get('supplier', '')).strip() if row.get('supplier') else ''
            if brand:
                brands.add(brand)
            if supplier:
                suppliers.add(supplier)
        
        # 获取CRM品牌列表（全量）
        from app.utils.crm_product.crm_productAdd.crm_brand_id import get_brand_dict
        from config import create_crm_session
        session = create_crm_session()
        try:
            crm_brand_dict = get_brand_dict(session)
            crm_brand_names = set(crm_brand_dict.values())
        finally:
            session.close()
        
        # 获取B2B供应商列表（全量）
        from app.utils.b2b_inquiry_upload.uploader import login, getAllSupplierChannel
        token = login('fsbbr')
        supplier_df = getAllSupplierChannel(token)
        if supplier_df is None or supplier_df.empty:
            b2b_supplier_names = set()
        else:
            b2b_supplier_names = set(supplier_df['name'].dropna().astype(str).tolist())
        
        # 精确匹配
        unmatched_brands = sorted([b for b in brands if b not in crm_brand_names])
        unmatched_suppliers = sorted([s for s in suppliers if s not in b2b_supplier_names])
        
        return jsonify({
            'code': 0,
            'msg': '预检完成',
            'data': {
                'unmatched_brands': unmatched_brands,
                'unmatched_suppliers': unmatched_suppliers,
                'brand_count': len(brands),
                'supplier_count': len(suppliers)
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'预检失败: {str(e)}'}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@inquiry_bp.route('/parse_oe_list', methods=['POST'])
@login_required
def parse_oe_list():
    """
    解析上传文件，返回OE列表（用于采购历史比对）
    
    返回:
    {
        "code": 0,
        "data": [{"oe": "12345", "brand": "博世"}, ...]
    }
    """
    if 'file' not in request.files:
        return jsonify({'code': 1, 'msg': '请选择要上传的文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 1, 'msg': '请选择要上传的文件'}), 400

    try:
        # 保存临时文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(tempfile.gettempdir(), f"parse_oe_{timestamp}_{file.filename}")
        file.save(temp_path)
        
        # 读取文件
        if file.filename.endswith('.csv'):
            df = pd.read_csv(temp_path, encoding='utf-8', dtype=str)
        else:
            df = pd.read_excel(temp_path, dtype=str)
        
        # 列名映射
        column_mapping = {
            'oe': 'oe', 'OE': 'oe', 'OE号': 'oe',
            '品牌': 'brand', 'brand': 'brand',
            '单价': 'price', '价格': 'price', 'price': 'price', '价格/促销价': 'price',
        }
        
        rename_dict = {old: new for old, new in column_mapping.items() 
                       if old in df.columns and new not in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        # 提取OE、品牌和价格
        oe_list = []
        for _, row in df.iterrows():
            oe = str(row.get('oe', '')).strip() if pd.notna(row.get('oe')) else ''
            brand = str(row.get('brand', '')).strip() if pd.notna(row.get('brand')) else ''
            price = str(row.get('price', '')).strip() if pd.notna(row.get('price')) else ''
            if oe:
                oe_list.append({'oe': oe, 'brand': brand, 'price': price})
        
        # 清理临时文件
        os.remove(temp_path)
        
        return jsonify({
            'code': 0,
            'msg': '解析成功',
            'data': oe_list
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'解析失败: {str(e)}'}), 500


@inquiry_bp.route('/gzbbr_quote_search', methods=['GET'])
@inquiry_permission_required
def gzbbr_quote_search():
    """搜索 data.gzbbr.com 报价列表"""
    oe = request.args.get('oe', '')
    supplier = request.args.get('supplier', '')
    limit = request.args.get('limit', 500, type=int)

    try:
        rows = GzbbrQuoteService.search_quote_prices(
            store_code=_get_current_store_code(),
            oe=oe,
            supplier=supplier,
            limit=limit
        )
        return jsonify({'code': 0, 'msg': '查询成功', 'data': rows})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'查询失败: {str(e)}'}), 500


@inquiry_bp.route('/gzbbr_quote_update', methods=['POST'])
@inquiry_permission_required
def gzbbr_quote_update():
    """批量更新 data.gzbbr.com 报价失效时间"""
    data = request.get_json() or {}
    records = data.get('records', [])
    lose_date = data.get('lose_date', '')

    if not records:
        return jsonify({'code': 1, 'msg': '请选择要更新的记录'}), 400
    if not lose_date:
        return jsonify({'code': 1, 'msg': '请设置新的失效时间'}), 400

    try:
        result = GzbbrQuoteService.batch_update_lose_date(
            store_code=_get_current_store_code(),
            records=records,
            lose_date=lose_date
        )
        return jsonify({'code': 0, 'msg': '更新完成', 'data': result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'更新失败: {str(e)}'}), 500
