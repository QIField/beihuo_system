"""
询价模块API
功能：导入Excel/CSV文件、查看询价比价表格
"""
from flask import Blueprint, request, jsonify, session, render_template
from functools import wraps
import pandas as pd
import math
from datetime import datetime
from app.utils.database_connection import get_db_connection

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

        if insert_data:
            conn = get_db_connection()
            cursor = conn.cursor()

            try:
                # 检查唯一索引是否存在
                cursor.execute("""
                    SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'crmapp_price_inquiry' 
                    AND INDEX_NAME = 'uk_oe_brand_supplier_price_company'
                """)
                index_exists = cursor.fetchone()
                print(f"[调试] 唯一索引是否存在: {index_exists is not None}")
                
                # 先查询数据库中已存在的数据量
                cursor.execute("SELECT COUNT(*) FROM crmapp_price_inquiry WHERE company = %s", (company,))
                before_count = cursor.fetchone()[0]
                print(f"[调试] 导入前数据库中 {company} 的数据量: {before_count}")
                
                # 检查第一条数据是否已存在
                first_data = insert_data[0]
                cursor.execute("""
                    SELECT COUNT(*) FROM crmapp_price_inquiry 
                    WHERE oe = %s AND brand = %s AND supplier = %s AND price = %s AND company = %s
                """, (first_data[0], first_data[1], first_data[2], first_data[3], first_data[10]))
                existing_count = cursor.fetchone()[0]
                print(f"[调试] 第一条数据是否已存在: {existing_count > 0}, oe={first_data[0]}")
                
                # 使用INSERT IGNORE，重复数据会自动忽略
                cursor.executemany("""
                    INSERT IGNORE INTO crmapp_price_inquiry
                    (oe, brand, supplier, price, warehouse, expire_time, remark, stock_quantity, common_number, creator, company)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, insert_data)

                conn.commit()
                
                # 再查询数据库中的数据量
                cursor.execute("SELECT COUNT(*) FROM crmapp_price_inquiry WHERE company = %s", (company,))
                after_count = cursor.fetchone()[0]
                print(f"[调试] 导入后数据库中 {company} 的数据量: {after_count}")
                
                # 计算实际插入数量
                inserted_count = after_count - before_count
                print(f"[调试] 实际插入数量: {inserted_count}")

            except Exception as e:
                conn.rollback()
                print(f"[调试] 批量插入失败: {str(e)}")
                return jsonify({'code': 1, 'msg': f'批量插入失败: {str(e)}'}), 500
            finally:
                cursor.close()
                conn.close()

        # 计算重复数量
        duplicate_count = total_rows - inserted_count
        print(f"[调试] 重复忽略数量: {duplicate_count}")
        
        # 同步到比价汇总表（使用INSERT IGNORE批量插入）
        sync_count = 0
        if inserted_count > 0:
            print(f"[调试] 开始同步到比价汇总表...")
            
            # 准备同步数据（去重）
            sync_data_map = {}
            for data in insert_data:
                key = (data[0], data[1], data[10])  # oe, brand, company
                if key not in sync_data_map:
                    sync_data_map[key] = (data[0], data[1], data[10])
            
            sync_data_list = list(sync_data_map.values())
            
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # 使用INSERT IGNORE批量插入
                cursor.executemany("""
                    INSERT IGNORE INTO crmapp_compare_summary (oe, brand, company)
                    VALUES (%s, %s, %s)
                """, sync_data_list)
                conn.commit()
                sync_count = cursor.rowcount
                print(f"[调试] 同步到比价汇总表完成: {sync_count} 条")
            except Exception as e:
                conn.rollback()
                print(f"[调试] 同步到比价表失败: {str(e)}")
            finally:
                cursor.close()
                conn.close()

        return jsonify({
            'code': 0,
            'msg': f'导入完成，成功{inserted_count}条，重复忽略{duplicate_count}条，同步比价表{sync_count}条',
            'data': {
                'total_count': total_rows,
                'success_count': inserted_count,
                'duplicate_count': duplicate_count,
                'sync_count': sync_count,
                'errors': error_rows[:10]  # 返回前10个错误
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
            ORDER BY oe, brand, created_time DESC
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
