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
import json
import os
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection
from app.services.procurement_service import add_inquiry_record
from app.utils.search.parser import parse_space, parse_comma

# 导入B2B上传模块
from app.utils.b2b_inquiry_upload import start_upload_task, get_recent_results

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


def classify_nine_category(update_msg, create_result=None):
    """
    根据update_msg和create_result判断九大类
    
    九大类：
    1. 上传成功 - B2B直接上传成功
    2. 新建成功-已存在 - B2B失败+新建时发现已存在
    3. 新建成功-新创建 - B2B失败+新建成功
    4. 新建失败-未找到产品名称 - 新建失败（无产品名）
    5. 新建失败-车型不能为空 - 新建失败（无车型）
    6. 上传失败-过期时间错误 - B2B返回过期时间错误
    7. 上传失败-品牌不存在 - B2B返回品牌不存在
    8. 上传失败-产品不存在 - B2B返回产品不存在但没走新建
    9. 其他 - 其他错误
    """
    if not update_msg:
        return '其他'
    
    # 上传成功
    if '成功' in update_msg and ('上传' in update_msg or 'update' in update_msg.lower() or 'add' in update_msg.lower()):
        return '上传成功'
    
    # 有新建结果的情况
    if create_result:
        if '已存在' in create_result:
            return '新建成功-已存在'
        elif '成功' in create_result and '失败' not in create_result:
            return '新建成功-新创建'
        elif '未找到产品名称' in create_result:
            return '新建失败-未找到产品名称'
        elif '车型不能为空' in create_result:
            return '新建失败-车型不能为空'
        else:
            return '新建失败-其他'
    
    # 无新建结果，根据B2B错误分类
    # 注意：判定顺序很重要，先判定特定的，再判定通用的
    if '过期时间' in update_msg or '失效时间' in update_msg:
        return '上传失败-过期时间错误'
    elif '产品数据不存在' in update_msg or '物料所属品牌' in update_msg and '产品数据不存在' in update_msg:
        # 格式：物料所属品牌【XXX】OE号【XXX】产品数据不存在
        return '上传失败-产品不存在'
    elif '品牌名称' in update_msg and '总部不存在' in update_msg:
        # 格式：品牌名称【XXX】总部不存在
        return '上传失败-品牌不存在'
    else:
        return '其他'


def get_detail_message(update_msg, create_result=None):
    """
    生成详情列内容
    如果有新建结果，用新建结果覆盖；否则用update_msg
    """
    if create_result:
        return create_result
    return update_msg


@inquiry_bp.route('/import', methods=['POST'])
@login_required
def import_price_data():
    """
    导入Excel或CSV文件到询价比价表
    新流程：B2B上传 → CRM新建 → 九分类 → 二次上传 → 生成结果文件 → 导入数据库
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
        # 根据文件扩展名选择读取方式
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, encoding='utf-8', dtype=str)
        elif file.filename.endswith(('.xls', '.xlsx')):
            # 使用dtype=str将所有列读取为字符串，保持原始数据格式（如OE号前导零）
            df = pd.read_excel(file, dtype=str)
        else:
            return jsonify({'code': 1, 'msg': '不支持的文件格式，请上传Excel或CSV文件'}), 400

        # 检查必需的列
        required_columns = ['oe', 'OE', 'OE号']
        has_oe = any(col in df.columns for col in required_columns)
        if not has_oe:
            return jsonify({'code': 1, 'msg': '文件缺少必需的列: oe/OE/OE号'}), 400

        # 保存原始列名（用于输出时保持中文表头）
        original_columns = list(df.columns)
        
        # 列名映射：中文 -> 英文（内部处理用）
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

        # 创建反向映射：英文 -> 原始中文列名（用于输出）
        reverse_mapping = {}
        for col in original_columns:
            if col in column_mapping:
                english_name = column_mapping[col]
                reverse_mapping[english_name] = col
            else:
                # 已经是英文或未知列，保持原样
                reverse_mapping[col] = col
        
        # 保存原始品牌列名（用于输出）
        original_brand_col = None
        for col in original_columns:
            if col in ['品牌', 'brand']:
                original_brand_col = col
                break

        # 重命名存在的列（内部处理用英文）
        rename_dict = {old_col: new_col for old_col, new_col in column_mapping.items() 
                      if old_col in df.columns and new_col not in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)

        # 数据清洗
        df = df.where(pd.notnull(df), None)
        
        # ==================== 价格加价处理 ====================
        # 获取加价倍数参数（从前端传入）
        # 1 = 价格不变, 1.1 = 价格×1.1, 1.5 = 价格×1.5
        markup_rate = request.form.get('markup_rate', '1')
        try:
            markup_rate = float(markup_rate)
        except:
            markup_rate = 1
        
        # 如果加价倍数不等于1，对价格进行加价处理
        if markup_rate != 1 and 'price' in df.columns:
            try:
                # 将价格转换为数值类型
                df['price'] = pd.to_numeric(df['price'], errors='coerce')
                # 保存原价格（用于采购记录表）
                df['original_price'] = df['price'].copy()
                # 价格处理：原始价格 × 加价倍数，四舍五入保留两位小数
                # 例如：原价100，倍数1.0 → 100 × 1.0 = 100（不变）
                #      原价100，倍数1.1 → 100 × 1.1 = 110（加价10%）
                #      原价100，倍数1.5 → 100 × 1.5 = 150（加价50%）
                df['price'] = (df['price'] * markup_rate).round(2)
            except Exception as e:
                print(f"价格加价处理失败: {e}")
        
        # 加载品牌别名映射（用于后续处理）
        from app.utils.b2b_inquiry_upload.uploader import load_crm_aliases_mapping
        brand_aliases_mapping = load_crm_aliases_mapping()

        # ==================== 第一步：B2B上传 ====================
        # 导入B2B上传模块
        from app.utils.b2b_inquiry_upload.uploader import prepare_data, batch_upload
        
        # 准备数据
        valid_items, skipped_items = prepare_data(df)
        
        if not valid_items:
            return jsonify({
                'code': 1, 
                'msg': '没有有效的数据可导入，请检查数据是否完整（需要包含oe、supplier、warehouse等字段）',
                'data': {'skipped_count': len(skipped_items), 'skipped_reasons': [item.get('skip_reason', '') for item in skipped_items[:5]]}
            }), 400
        
        # B2B上传（循环处理）
        b2b_results = batch_upload(valid_items)
        
        # 将B2B结果合并到valid_items中，并处理品牌别名映射
        for item in valid_items:
            oe = item['oe']
            result = b2b_results.get(oe, {})
            item['update_msg'] = result.get('update_msg', '未知错误')
            item['b2b_status'] = result.get('status', 'error')
            
            # 品牌别名映射：使用匹配后的标准品牌名
            original_brand = item.get('brand', '')
            mapped_brand = brand_aliases_mapping.get(original_brand, original_brand)
            item['mapped_brand'] = mapped_brand  # 保存映射后的品牌名
            
            # 如果B2B返回了mapped_brand（说明有别名映射），优先使用B2B的映射结果
            b2b_mapped_brand = result.get('mapped_brand')
            if b2b_mapped_brand:
                item['mapped_brand'] = b2b_mapped_brand
        
        # ==================== 第二步：筛选需要新建的项 ====================
        # 筛选需要去CRM新建的项（产品不存在的情况）
        # 格式：物料所属品牌【XXX】OE号【XXX】产品数据不存在,请核查数据
        need_create_keywords = [
            '产品数据不存在',  # 主要格式：物料所属品牌【XXX】OE号【XXX】产品数据不存在
            '物料所属品牌'     # 辅助匹配
        ]
        need_create_items = []
        
        for item in valid_items:
            update_msg = item.get('update_msg', '')
            if any(keyword in update_msg for keyword in need_create_keywords):
                # 使用映射后的品牌名进行新建
                need_create_items.append({
                    'oe_number': item['oe'],
                    'brand': item.get('mapped_brand', item['brand']),  # 使用映射后的品牌
                    'supplier_name': item.get('supplier', ''),
                    'mode': 'inquiry'
                })
        
        # ==================== 第三步：CRM新建 ====================
        create_results = {}
        if need_create_items:
            # 导入CRM产品创建模块
            from app.utils.crm_product.crm_productAdd.main import (
                load_alias_data, load_product_data, _process_with_loop
            )
            
            # 加载产品数据和别名数据
            alias_df = load_alias_data()
            product_df = load_product_data()
            
            # 循环处理新建
            create_results = _process_with_loop(need_create_items, product_df, alias_df, None)
        
        # ==================== 第四步：二次上传（针对新建成功的产品）====================
        # 筛选出新建成功的产品，尝试二次上传
        second_upload_items = []
        for item in valid_items:
            oe = item['oe']
            create_result = create_results.get(oe, '')
            # 新建成功-已存在 或 新建成功-新创建
            if create_result and ('已存在' in create_result or ('成功' in create_result and '失败' not in create_result)):
                second_upload_items.append(item)
        
        second_upload_results = {}
        if second_upload_items:
            # 使用相同的batch_upload函数进行二次上传
            second_b2b_results = batch_upload(second_upload_items)
            
            for item in second_upload_items:
                oe = item['oe']
                result = second_b2b_results.get(oe, {})
                second_upload_results[oe] = result.get('update_msg', '')
        
        # ==================== 第五步：九分类判断 ====================
        # 统计各分类数量
        category_count = {
            '上传成功': 0,
            '新建成功-已存在': 0,
            '新建成功-新创建': 0,
            '新建失败-未找到产品名称': 0,
            '新建失败-车型不能为空': 0,
            '上传失败-过期时间错误': 0,
            '上传失败-品牌不存在': 0,
            '上传失败-产品不存在': 0,
            '其他': 0
        }
        
        for item in valid_items:
            oe = item['oe']
            update_msg = item.get('update_msg', '')
            create_result = create_results.get(oe)
            
            # 九分类判断
            category = classify_nine_category(update_msg, create_result)
            item['处理结果'] = category
            category_count[category] = category_count.get(category, 0) + 1
            
            # 详情列
            item['详情'] = get_detail_message(update_msg, create_result)
            
            # 二次上传结果
            item['二次上传'] = second_upload_results.get(oe, '')
        
        # 处理跳过的项
        for item in skipped_items:
            item['处理结果'] = '其他'
            item['详情'] = f"跳过: {item.get('skip_reason', '')}"
            item['二次上传'] = ''
            category_count['其他'] = category_count.get('其他', 0) + 1
        
        # ==================== 第六步：生成Excel结果文件 ====================
        # 合并所有数据
        all_items = valid_items + skipped_items
        
        # 创建结果DataFrame - 保持原Excel的列顺序和中文表头
        result_data = []
        for item in all_items:
            # 获取原始行数据（保持原Excel的列）
            row_data = {}
            
            # 根据原始列名来构建数据
            for orig_col in original_columns:
                # 获取对应的英文列名
                english_col = column_mapping.get(orig_col, orig_col)
                
                if english_col == 'brand':
                    # 品牌列使用映射后的标准品牌名
                    row_data[orig_col] = item.get('mapped_brand', item.get('brand', ''))
                elif english_col in ['oe', 'supplier', 'price', 'warehouse', 'expire_time', 'stock_quantity', 'remark']:
                    value = item.get(english_col, '')
                    # 处理 nan 值：为空或 nan 时设为空字符串
                    if value is None or (isinstance(value, float) and math.isnan(value)) or str(value).lower() == 'nan':
                        value = ''
                    row_data[orig_col] = value
                else:
                    # 其他列从原始df中获取
                    idx = item.get('index')
                    if idx is not None and idx < len(df):
                        value = df.iloc[idx].get(english_col, '')
                        # 处理 nan 值：为空或 nan 时设为空字符串
                        if value is None or (isinstance(value, float) and math.isnan(value)) or str(value).lower() == 'nan':
                            value = ''
                        row_data[orig_col] = value
                    else:
                        row_data[orig_col] = ''
            
            # 添加处理结果、详情和二次上传列
            row_data['处理结果'] = item.get('处理结果', '')
            row_data['详情'] = item.get('详情', '')
            row_data['二次上传'] = item.get('二次上传', '')
            
            result_data.append(row_data)
        
        result_df = pd.DataFrame(result_data)
        
        # 确保列顺序：原df的列 + 处理结果 + 详情 + 二次上传（保持中文表头）
        output_cols = list(original_columns)  # 使用原始中文列名
        if '处理结果' not in output_cols:
            output_cols.append('处理结果')
        if '详情' not in output_cols:
            output_cols.append('详情')
        if '二次上传' not in output_cols:
            output_cols.append('二次上传')
        result_df = result_df[output_cols]
        
        # 保存结果文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_filename = f'inquiry_upload_result_{timestamp}.xlsx'
        result_dir = 'static/uploads/b2b_results'
        os.makedirs(result_dir, exist_ok=True)
        result_path = os.path.join(result_dir, result_filename)
        result_df.to_excel(result_path, index=False)
        
        # ==================== 第七步：导入数据库（上传成功 + 二次上传成功）====================
        # 筛选需要导入的数据：
        # 1. 处理结果 = "上传成功" 的
        # 2. 二次上传成功（包含"上传add成功"或"上传update成功"）的
        upload_success_items = []
        for item in valid_items:
            # 情况1：直接上传成功
            if item.get('处理结果') == '上传成功':
                upload_success_items.append(item)
            # 情况2：二次上传成功
            elif item.get('二次上传'):
                second_upload_msg = item.get('二次上传', '')
                if '上传add成功' in second_upload_msg or '上传update成功' in second_upload_msg:
                    upload_success_items.append(item)
        
        insert_data = []
        error_rows = []
        
        for item in upload_success_items:
            try:
                oe = item['oe']
                # 使用映射后的品牌名导入数据库
                brand = item.get('mapped_brand') or item.get('brand') or None
                supplier = item.get('supplier') or None
                price = item.get('price', 0)
                # 获取原价格（用于采购记录表）
                original_price = item.get('original_price', price)
                warehouse = item.get('warehouse') or None
                expire_time = item.get('expire_time')
                # 处理备注：为空或nan时设为None
                remark = item.get('remark')
                if remark and str(remark).lower() == 'nan':
                    remark = None
                elif remark:
                    remark = str(remark).strip() or None
                stock_quantity = item.get('stock_quantity', 0)
                
                # 处理失效时间 - 支持多种格式自动转换
                # 格式1: 2026/3/22 18:36 (斜杠分隔，无秒)
                # 格式2: 2026-12-31 11:36:19 (横杠分隔，有秒)
                if expire_time and pd.notna(expire_time):
                    if isinstance(expire_time, str):
                        expire_time = expire_time.strip()
                        # 尝试多种格式解析
                        parsed = False
                        # 格式1: 2026/3/22 18:36 (斜杠分隔，无秒)
                        if not parsed:
                            try:
                                expire_time = datetime.strptime(expire_time, '%Y/%m/%d %H:%M')
                                parsed = True
                            except ValueError:
                                pass
                        # 格式2: 2026-12-31 11:36:19 (横杠分隔，有秒)
                        if not parsed:
                            try:
                                expire_time = datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')
                                parsed = True
                            except ValueError:
                                pass
                        # 格式3: 2026-12-31 11:36 (横杠分隔，无秒)
                        if not parsed:
                            try:
                                expire_time = datetime.strptime(expire_time, '%Y-%m-%d %H:%M')
                                parsed = True
                            except ValueError:
                                pass
                        # 格式4: 纯日期 2026-03-22
                        if not parsed:
                            try:
                                expire_time = datetime.strptime(expire_time, '%Y-%m-%d')
                                parsed = True
                            except ValueError:
                                pass
                        # 格式5: 纯日期 2026/3/22
                        if not parsed:
                            try:
                                expire_time = datetime.strptime(expire_time, '%Y/%m/%d')
                                parsed = True
                            except ValueError:
                                pass
                        # 都解析失败则设为None
                        if not parsed:
                            expire_time = None
                else:
                    expire_time = None
                
                insert_data.append({
                    'oe': oe,
                    'brand': brand,
                    'supplier': supplier,
                    'price': price,
                    'original_price': original_price,
                    'warehouse': warehouse,
                    'expire_time': expire_time,
                    'remark': remark,
                    'stock_quantity': stock_quantity,
                    'common_number': None,
                    'company': company
                })
            except Exception as e:
                error_rows.append(f"OE={item.get('oe', 'unknown')} 处理失败: {str(e)}")
        
        # 批量插入数据
        inserted_count = 0
        skipped_exists_count = 0
        
        if insert_data:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                # 准备批量插入的数据
                batch_insert_data = []
                for data in insert_data:
                    oe = data['oe']
                    brand = data['brand']
                    supplier = data['supplier']
                    comp = data['company']
                    
                    # 从比价表查询通用号和开思同步字段
                    cursor.execute("""
                        SELECT replace_number, is_cass FROM crmapp_compare_summary 
                        WHERE oe = %s AND brand = %s AND company = %s
                    """, (oe, brand, comp))
                    compare_result = cursor.fetchone()
                    
                    sync_common_number = compare_result[0] if compare_result and compare_result[0] else ''
                    sync_ks_sync = 1 if compare_result and compare_result[1] and str(compare_result[1]) == '1' else 0
                    
                    batch_insert_data.append((
                        oe, brand, supplier, data['price'], data['warehouse'],
                        data['expire_time'], data['remark'], data['stock_quantity'],
                        sync_common_number, sync_ks_sync, comp
                    ))
                
                # 使用 INSERT IGNORE 批量插入
                cursor.executemany("""
                    INSERT IGNORE INTO crmapp_price_inquiry 
                    (oe, brand, supplier, price, warehouse, expire_time, remark, 
                     stock_quantity, common_number, ks_sync, company)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, batch_insert_data)
                
                conn.commit()
                
                # 统计结果
                inserted_count = cursor.rowcount
                skipped_exists_count = len(batch_insert_data) - inserted_count

            except Exception as e:
                conn.rollback()
                return jsonify({'code': 1, 'msg': f'导入失败: {str(e)}'}), 500
            finally:
                cursor.close()
                conn.close()
        
        # ==================== 第八步：同步到比价表和采购记录表 ====================
        sync_count = 0
        procurement_count = 0
        
        if inserted_count > 0:
            # 准备同步数据
            sync_data_map = {}
            procurement_data_list = []
            
            for data in insert_data:
                # 比价汇总表数据（去重）
                key = (data['oe'], data['brand'], data['company'])
                if key not in sync_data_map:
                    sync_data_map[key] = key
                
                # 采购记录表数据 - 使用原价格（不加价）
                # 从insert_data中获取原价格
                original_price = data.get('original_price', data['price'])
                if data['supplier'] and original_price > 0:
                    procurement_data_list.append({
                        'oe': data['oe'],
                        'brand': data['brand'],
                        'supplier': data['supplier'],
                        'price': original_price,
                        'company': data['company']
                    })
            
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # 1. 同步到比价汇总表
                if sync_data_map:
                    cursor.executemany("""
                        INSERT IGNORE INTO crmapp_compare_summary (oe, brand, company)
                        VALUES (%s, %s, %s)
                    """, list(sync_data_map.values()))
                    conn.commit()
                    sync_count = cursor.rowcount
                
                # 2. 同步到采购记录表
                for proc_data in procurement_data_list:
                    try:
                        success = add_inquiry_record(
                            proc_data['oe'],
                            proc_data['brand'],
                            proc_data['supplier'],
                            proc_data['price'],
                            proc_data['company']
                        )
                        if success:
                            procurement_count += 1
                    except Exception as e:
                        pass
                
                # 3. 触发采购数据同步到比价表
                if procurement_count > 0:
                    try:
                        from app.services.procurement_service.purchase_sync_service import PurchaseSyncService
                        sync_service = PurchaseSyncService()
                        
                        # 只同步有采购记录的 OE+品牌 组合
                        for proc_data in procurement_data_list:
                            sync_service.sync_single_product(
                                proc_data['oe'], 
                                proc_data['brand'], 
                                proc_data['company']
                            )
                    except Exception as e:
                        pass
                
            except Exception as e:
                conn.rollback()
            finally:
                cursor.close()
                conn.close()

        return jsonify({
            'code': 0,
            'msg': f'导入完成：上传成功{category_count.get("上传成功", 0)}条，新建成功{category_count.get("新建成功-已存在", 0) + category_count.get("新建成功-新创建", 0)}条，数据库导入{inserted_count}条',
            'data': {
                'total_count': len(df),
                'category_count': category_count,
                'inserted_count': inserted_count,
                'skipped_same_price': skipped_exists_count,
                'sync_count': sync_count,
                'procurement_count': procurement_count,
                'result_file': result_filename,
                'errors': error_rows[:10]
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'导入失败: {str(e)}'}), 500


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
            SELECT id, oe, brand, supplier, price, warehouse, expire_time, remark, stock_quantity, common_number, ks_sync
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
            item = dict(zip(columns, row))
            if item.get('expire_time'):
                item['expire_time'] = item['expire_time'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(item['expire_time'], 'strftime') else str(item['expire_time'])
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
