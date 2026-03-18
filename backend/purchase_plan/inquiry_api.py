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
    使用INSERT IGNORE自动去重（根据oe+brand+supplier+price+company唯一索引）
    """
    if 'file' not in request.files:
        return jsonify({'code': 1, 'msg': '请选择要上传的文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 1, 'msg': '请选择要上传的文件'}), 400

    # 获取当前用户名和公司
    creator = session.get('username', 'unknown')
    company = session.get('current_org', session.get('store', 'fsbbr'))  # 获取当前切换到的组织

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
            'oe': 'oe',
            'OE': 'oe',
            'OE号': 'oe',
            '品牌': 'brand',
            'brand': 'brand',
            '供应商': 'supplier',
            'supplier': 'supplier',
            '单价': 'price',
            'price': 'price',
            '价格': 'price',
            '仓库': 'warehouse',
            'warehouse': 'warehouse',
            '失效时间': 'expire_time',
            'expire_time': 'expire_time',
            '备注': 'remark',
            'remark': 'remark',
            '库存数量': 'stock_quantity',
            'stock_quantity': 'stock_quantity',
            '通用号': 'common_number',
            'common_number': 'common_number'
        }

        # 重命名存在的列
        rename_dict = {}
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                rename_dict[old_col] = new_col

        if rename_dict:
            df = df.rename(columns=rename_dict)

        # 数据清洗
        df = df.where(pd.notnull(df), None)  # 将NaN替换为None

        # 准备批量插入的数据
        insert_data = []
        error_rows = []

        for index, row in df.iterrows():
            try:
                # 跳过空OE的行
                oe = str(row.get('oe', '')).strip() if row.get('oe') else ''
                if not oe:
                    continue

                # 处理失效时间字段
                expire_time = row.get('expire_time')
                if expire_time and pd.notna(expire_time):
                    if isinstance(expire_time, str):
                        try:
                            expire_time = datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')
                        except:
                            try:
                                expire_time = datetime.strptime(expire_time, '%Y-%m-%d')
                            except:
                                expire_time = None
                    elif hasattr(expire_time, 'strftime'):
                        expire_time = expire_time
                else:
                    expire_time = None

                # 处理价格字段
                price = row.get('price')
                if price and pd.notna(price):
                    try:
                        price = float(price)
                    except:
                        price = 0.0
                else:
                    price = 0.0

                # 处理库存数量字段
                stock_quantity = row.get('stock_quantity')
                if stock_quantity and pd.notna(stock_quantity):
                    try:
                        stock_quantity = int(stock_quantity)
                    except:
                        stock_quantity = 0
                else:
                    stock_quantity = 0

                # 准备数据（使用INSERT IGNORE自动去重）
                insert_data.append((
                    oe,
                    str(row.get('brand', '')).strip() if row.get('brand') else None,
                    str(row.get('supplier', '')).strip() if row.get('supplier') else None,
                    price,
                    str(row.get('warehouse', '')).strip() if row.get('warehouse') else None,
                    expire_time,
                    str(row.get('remark', '')).strip() if row.get('remark') else None,
                    stock_quantity,
                    str(row.get('common_number', '')).strip() if row.get('common_number') else None,
                    creator,
                    company  # 自动记录用户所在公司
                ))

            except Exception as e:
                error_rows.append(f'第{index + 2}行处理失败: {str(e)}')

        # 批量插入数据（使用INSERT IGNORE自动去重）
        total_rows = len(insert_data)
        inserted_count = 0
        
        # 调试信息
        print(f"[调试] 准备导入数据: {total_rows} 条")
        print(f"[调试] 用户公司: {company}")
        print(f"[调试] 前3条数据预览: {insert_data[:3] if insert_data else '无'}")

        inserted_count = 0
        updated_count = 0
        
        if insert_data:
            conn = get_db_connection()
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')

            try:
                for data in insert_data:
                    # data 结构: (oe, brand, supplier, price, warehouse, expire_time, remark, stock_quantity, common_number, creator, company)
                    oe, brand, supplier, price, warehouse, expire_time, remark, stock_quantity, common_number, creator, comp = data
                    
                    # 从比价表查询通用号和开思同步字段
                    cursor.execute("""
                        SELECT replace_number, is_cass FROM crmapp_compare_summary 
                        WHERE oe = %s AND brand = %s AND company = %s
                    """, (oe, brand, comp))
                    compare_result = cursor.fetchone()
                    
                    # 获取比价表中的字段值，如果没有则使用默认值
                    sync_common_number = ''
                    sync_ks_sync = 0
                    if compare_result:
                        sync_common_number = compare_result[0] if compare_result[0] else ''
                        # is_cass 是 VARCHAR 类型，'1' 表示已同步，其他值表示未同步
                        is_cass_value = compare_result[1]
                        sync_ks_sync = 1 if is_cass_value and str(is_cass_value) == '1' else 0
                    
                    # 查询是否已存在（只根据 oe + brand + supplier + company）
                    cursor.execute("""
                        SELECT id, import_history FROM crmapp_price_inquiry 
                        WHERE oe = %s AND brand = %s AND supplier = %s AND company = %s
                    """, (oe, brand, supplier, comp))
                    result = cursor.fetchone()
                    
                    # 构建新的导入记录
                    new_record = {
                        'price': float(price) if price else 0.0,
                        'warehouse': warehouse or '',
                        'date': today
                    }
                    
                    if result:
                        # 已存在，只保留 oe/brand/supplier/company，其他全部覆盖
                        record_id = result[0]
                        import_history = result[1]
                        
                        # 解析现有的导入历史
                        history_list = []
                        if import_history:
                            try:
                                if isinstance(import_history, str):
                                    history_list = json.loads(import_history)
                                elif isinstance(import_history, list):
                                    history_list = import_history
                            except:
                                history_list = []
                        
                        # 追加新记录到历史
                        history_list.append(new_record)
                        
                        # 更新记录：除 oe/brand/supplier/company 外，其他全部覆盖
                        # 通用号和开思同步从比价表同步过来
                        cursor.execute("""
                            UPDATE crmapp_price_inquiry 
                            SET price = %s, 
                                warehouse = %s, 
                                expire_time = %s, 
                                remark = %s, 
                                stock_quantity = %s,
                                common_number = %s,  -- 通用号从比价表同步
                                ks_sync = %s,         -- 开思同步从比价表同步
                                import_history = %s
                            WHERE id = %s
                        """, (price, warehouse, expire_time, remark, stock_quantity, 
                              sync_common_number, sync_ks_sync,
                              json.dumps(history_list, ensure_ascii=False), record_id))
                        updated_count += 1
                        print(f"[调试] 更新记录: OE={oe}, 供应商={supplier}, 历史记录数={len(history_list)}, 通用号={sync_common_number}, 开思同步={sync_ks_sync}")
                    else:
                        # 不存在，插入新记录
                        history_list = [new_record]
                        cursor.execute("""
                            INSERT INTO crmapp_price_inquiry 
                            (oe, brand, supplier, price, warehouse, expire_time, remark, 
                             stock_quantity, common_number, ks_sync, company, import_history)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (oe, brand, supplier, price, warehouse, expire_time, remark, 
                              stock_quantity, sync_common_number, sync_ks_sync, comp, 
                              json.dumps(history_list, ensure_ascii=False)))
                        inserted_count += 1
                        print(f"[调试] 插入新记录: OE={oe}, 供应商={supplier}, 通用号={sync_common_number}, 开思同步={sync_ks_sync}")
                
                conn.commit()
                print(f"[调试] 导入完成: 插入={inserted_count}, 更新={updated_count}")

            except Exception as e:
                conn.rollback()
                print(f"[调试] 导入失败: {str(e)}")
                return jsonify({'code': 1, 'msg': f'导入失败: {str(e)}'}), 500
            finally:
                cursor.close()
                conn.close()

        # 同步到比价汇总表和采购记录表
        sync_count = 0
        procurement_count = 0
        if inserted_count > 0 or updated_count > 0:
            print(f"[调试] 开始同步到比价汇总表和采购记录表...")
            
            # 准备同步数据（去重）
            sync_data_map = {}
            procurement_data_list = []  # 用于采购记录表
            
            for data in insert_data:
                oe, brand, supplier, price, warehouse, expire_time, remark, stock_quantity, common_number, creator, comp = data
                
                # 比价汇总表数据（去重）
                key = (oe, brand, comp)
                if key not in sync_data_map:
                    sync_data_map[key] = (oe, brand, comp)
                
                # 采购记录表数据（包含供应商和价格）
                if supplier and price > 0:
                    procurement_data_list.append({
                        'oe': oe,
                        'brand': brand,
                        'supplier': supplier,
                        'price': price,
                        'company': comp
                    })
            
            sync_data_list = list(sync_data_map.values())
            
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # 1. 同步到比价汇总表
                cursor.executemany("""
                    INSERT IGNORE INTO crmapp_compare_summary (oe, brand, company)
                    VALUES (%s, %s, %s)
                """, sync_data_list)
                conn.commit()
                sync_count = cursor.rowcount
                print(f"[调试] 同步到比价汇总表完成: {sync_count} 条")
                
                # 2. 同步到采购记录表（询价自带的供应商价格）
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
                        print(f"[调试] 保存采购记录失败: OE={proc_data['oe']}, 供应商={proc_data['supplier']}, 错误={e}")
                
                print(f"[调试] 同步到采购记录表完成: {procurement_count} 条")
                
            except Exception as e:
                conn.rollback()
                print(f"[调试] 同步到比价表失败: {str(e)}")
            finally:
                cursor.close()
                conn.close()

        # 导入成功后，启动B2B上传任务（异步）
        b2b_task_info = None
        try:
            # 使用处理后的DataFrame启动上传任务
            b2b_task_info = start_upload_task(df, company)
            print(f"[B2B上传] 任务已启动: {b2b_task_info}")
        except Exception as e:
            print(f"[B2B上传] 启动失败: {e}")
            b2b_task_info = {'status': 'error', 'message': str(e)}

        return jsonify({
            'code': 0,
            'msg': f'导入完成，插入{inserted_count}条，更新{updated_count}条，同步比价表{sync_count}条，同步采购记录{procurement_count}条',
            'data': {
                'total_count': total_rows,
                'inserted_count': inserted_count,
                'updated_count': updated_count,
                'sync_count': sync_count,
                'procurement_count': procurement_count,
                'errors': error_rows[:10],  # 返回前10个错误
                'b2b_upload': b2b_task_info  # B2B上传任务信息
            }
        })

    except Exception as e:
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

        if oe:
            where_conditions.append("oe LIKE %s")
            params.append(f"%{oe}%")
        if brand:
            where_conditions.append("brand LIKE %s")
            params.append(f"%{brand}%")
        if supplier:
            where_conditions.append("supplier LIKE %s")
            params.append(f"%{supplier}%")

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
