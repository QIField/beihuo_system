"""
询价模块API
功能：导入Excel/CSV文件、查看询价比价表格、B2B上传
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


@inquiry_bp.route('/import', methods=['POST'])
@login_required
def import_price_data():
    """
    导入Excel或CSV文件到询价比价表
    支持字段：oe, brand, supplier, price, warehouse, expire_time, remark, stock_quantity, common_number
    
    【改进点】
    1. 先进行B2B上传验证，只将上传成功的数据导入数据库
    2. 同一产品新数据不覆盖旧数据（存在则跳过）
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
            df = pd.read_csv(file, encoding='utf-8')
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
            return jsonify({'code': 1, 'msg': '不支持的文件格式，请上传Excel或CSV文件'}), 400

        # 检查必需的列
        required_columns = ['oe']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({'code': 1, 'msg': f'文件缺少必需的列: {", ".join(missing_columns)}'}), 400

        # 重命名列以匹配数据库字段（支持中英文列名）
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

        # 重命名存在的列
        rename_dict = {old_col: new_col for old_col, new_col in column_mapping.items() 
                      if old_col in df.columns and new_col not in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)

        # 数据清洗
        df = df.where(pd.notnull(df), None)

        # ==================== 第一步：数据预处理和验证 ====================
        # 先进行B2B上传验证，筛选出能成功上传的数据
        print(f"\n{'='*60}")
        print("【询价导入】开始处理，先进行B2B上传验证...")
        print(f"{'='*60}")
        
        # 导入B2B验证模块
        from app.utils.b2b_inquiry_upload.uploader import prepare_data, validate_b2b_upload
        
        # 准备数据并验证B2B上传可行性
        valid_items, skipped_items = prepare_data(df)
        
        if not valid_items:
            return jsonify({
                'code': 1, 
                'msg': '没有有效的数据可导入，请检查数据是否完整（需要包含oe、supplier、warehouse等字段）',
                'data': {'skipped_count': len(skipped_items), 'skipped_reasons': [item.get('skip_reason', '') for item in skipped_items[:5]]}
            }), 400
        
        # 进行B2B上传验证（只验证，获取哪些数据能上传成功）
        print(f"[询价导入] 开始进行B2B上传验证，共 {len(valid_items)} 条数据...")
        b2b_validation_results = validate_b2b_upload(valid_items, company)
        
        # 筛选出B2B上传成功的数据
        upload_success_items = []
        upload_failed_items = []
        
        for item in valid_items:
            oe = item['oe']
            result = b2b_validation_results.get(oe, {})
            if result.get('status') == 'success':
                upload_success_items.append(item)
            else:
                item['fail_reason'] = result.get('msg', 'B2B上传验证失败')
                upload_failed_items.append(item)
        
        print(f"[询价导入] B2B验证结果: 成功={len(upload_success_items)}, 失败={len(upload_failed_items)}, 跳过={len(skipped_items)}")
        
        # 如果没有成功上传的数据，直接返回错误
        if not upload_success_items:
            return jsonify({
                'code': 1,
                'msg': '所有数据B2B上传验证失败，未导入任何数据',
                'data': {
                    'total': len(df),
                    'upload_failed': len(upload_failed_items),
                    'skipped': len(skipped_items),
                    'failed_reasons': [f"{item['oe']}: {item.get('fail_reason', '')}" for item in upload_failed_items[:10]]
                }
            }), 400

        # ==================== 第二步：只将B2B上传成功的数据导入数据库 ====================
        # 准备导入数据（只包含上传成功的）
        insert_data = []
        error_rows = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        for item in upload_success_items:
            try:
                oe = item['oe']
                brand = item['brand'] or None
                supplier = item['supplier'] or None
                price = item['price']
                warehouse = item['warehouse'] or None
                expire_time = item['expire_time']
                remark = item['remark'] or None
                stock_quantity = item['stock_quantity']
                
                # 处理失效时间
                if expire_time and pd.notna(expire_time):
                    if isinstance(expire_time, str):
                        try:
                            expire_time = datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')
                        except:
                            try:
                                expire_time = datetime.strptime(expire_time, '%Y-%m-%d')
                            except:
                                expire_time = None
                else:
                    expire_time = None
                
                insert_data.append({
                    'oe': oe,
                    'brand': brand,
                    'supplier': supplier,
                    'price': price,
                    'warehouse': warehouse,
                    'expire_time': expire_time,
                    'remark': remark,
                    'stock_quantity': stock_quantity,
                    'common_number': None,  # 从比价表同步
                    'company': company
                })
            except Exception as e:
                error_rows.append(f"OE={item.get('oe', 'unknown')} 处理失败: {str(e)}")

        # 批量插入数据（使用INSERT IGNORE）
        # 【关键逻辑】
        # 唯一索引: uk_oe_brand_supplier_price_company (oe, brand, supplier, price, company)
        # - 同一产品+品牌+供应商+不同价格 -> 插入新记录（保存历史价格）
        # - 同一产品+品牌+供应商+相同价格 -> 忽略（跳过重复）
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
                # 利用唯一索引自动去重：同一价格跳过，不同价格插入
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
                
                print(f"[询价导入] 数据库导入完成: 尝试插入={len(batch_insert_data)}, 成功={inserted_count}, 跳过(同价格已存在)={skipped_exists_count}")

            except Exception as e:
                conn.rollback()
                print(f"[询价导入] 数据库导入失败: {str(e)}")
                return jsonify({'code': 1, 'msg': f'导入失败: {str(e)}'}), 500
            finally:
                cursor.close()
                conn.close()

        # ==================== 第三步：同步到比价表和采购记录表 ====================
        sync_count = 0
        procurement_count = 0
        
        if inserted_count > 0:
            print(f"[询价导入] 开始同步到比价汇总表和采购记录表...")
            
            # 准备同步数据
            sync_data_map = {}
            procurement_data_list = []
            
            for data in insert_data:
                # 比价汇总表数据（去重）
                key = (data['oe'], data['brand'], data['company'])
                if key not in sync_data_map:
                    sync_data_map[key] = key
                
                # 采购记录表数据
                if data['supplier'] and data['price'] > 0:
                    procurement_data_list.append({
                        'oe': data['oe'],
                        'brand': data['brand'],
                        'supplier': data['supplier'],
                        'price': data['price'],
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
                    print(f"[询价导入] 同步到比价汇总表完成: {sync_count} 条")
                
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
                        print(f"[询价导入] 保存采购记录失败: OE={proc_data['oe']}, 错误={e}")
                
                print(f"[询价导入] 同步到采购记录表完成: {procurement_count} 条")
                
                # 3. 触发采购数据同步到比价表
                if procurement_count > 0:
                    print(f"[询价导入] 开始同步采购数据到比价表...")
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
                        
                        print(f"[询价导入] 采购数据同步到比价表完成")
                    except Exception as e:
                        print(f"[询价导入] 同步采购数据到比价表失败: {str(e)}")
                
            except Exception as e:
                conn.rollback()
                print(f"[询价导入] 同步到比价表失败: {str(e)}")
            finally:
                cursor.close()
                conn.close()

        # ==================== 第四步：生成结果报告 ====================
        print(f"\n{'='*60}")
        print("【询价导入】处理完成统计：")
        print(f"  文件总行数: {len(df)}")
        print(f"  B2B上传成功: {len(upload_success_items)}")
        print(f"  B2B上传失败: {len(upload_failed_items)}")
        print(f"  数据不完整跳过: {len(skipped_items)}")
        print(f"  数据库插入(新价格): {inserted_count}")
        print(f"  数据库跳过(同价格已存在): {skipped_exists_count}")
        print(f"{'='*60}\n")

        return jsonify({
            'code': 0,
            'msg': f'导入完成：B2B验证通过{len(upload_success_items)}条，新价格导入{inserted_count}条，同价格跳过{skipped_exists_count}条',
            'data': {
                'total_count': len(df),
                'upload_success': len(upload_success_items),
                'upload_failed': len(upload_failed_items),
                'skipped_invalid': len(skipped_items),
                'inserted_count': inserted_count,  # 新价格记录数
                'skipped_same_price': skipped_exists_count,  # 同价格跳过数
                'sync_count': sync_count,
                'procurement_count': procurement_count,
                'upload_failed_details': [
                    {'oe': item['oe'], 'reason': item.get('fail_reason', '')} 
                    for item in upload_failed_items[:10]
                ],
                'errors': error_rows[:10]
            }
        })

    except Exception as e:
        import traceback
        print(f"[询价导入] 异常: {str(e)}")
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
