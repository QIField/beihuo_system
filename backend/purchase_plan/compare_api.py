"""
比价模块API
功能：查看询价比价表格、查询功能、导出功能
"""
from flask import Blueprint, request, jsonify, session, Response, render_template, send_file
from functools import wraps
import pandas as pd
import io
import os
import pymysql
from datetime import datetime
from openpyxl.comments import Comment
from app.utils.database_connection import get_db_connection
from app.services.compare_service.compare_data_service import CompareDataService
from app.utils.export_tools.excel_styles import apply_uniform_style

# 创建蓝图
compare_bp = Blueprint('compare', __name__)


@compare_bp.route('/compare_module')
def compare_module_page():
    """比价模块页面"""
    # 检查用户是否有权限
    if 'logged_in' not in session:
        return render_template('login.html')
    if not session.get('can_compare_module') and not session.get('is_admin'):
        return "您没有权限访问此页面", 403
    return render_template('purchase_plan/compare_module.html')


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def compare_permission_required(f):
    """比价模块权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        # 检查是否有比价模块权限或是admin
        if not session.get('can_compare_module') and not session.get('is_admin'):
            return jsonify({'code': 1, 'msg': '您没有权限访问比价模块'}), 403
        return f(*args, **kwargs)
    return decorated_function


def _format_ascii_table(headers, rows):
    """生成 ASCII 表格线文本，用于 Excel 批注"""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def make_line(cells, sep="|"):
        parts = [f" {cell:{col_widths[i]}} " for i, cell in enumerate(cells)]
        return sep + sep.join(parts) + sep

    def make_sep(sep="+", fill="-"):
        parts = [f"{fill}{fill * col_widths[i]}{fill}" for i in range(len(headers))]
        return sep + sep.join(parts) + sep

    lines = [make_line(headers), make_sep()]
    for row in rows:
        lines.append(make_line(row))
    return "\n".join(lines)


def _build_procurement_table_text(records):
    """将采购记录列表转为表格线批注文本"""
    if not records:
        return ""
    sorted_records = sorted(
        records,
        key=lambda r: r.get('purchase_date', ''),
        reverse=True
    )
    rows = []
    for r in sorted_records:
        date = r.get('purchase_date', '')[:7]
        supplier = r.get('supplier_name', '')
        price = f"{float(r.get('purchase_price', 0)):.2f}"
        rows.append([date, supplier, price])
    return _format_ascii_table(["日期", "供应商", "价格"], rows)


@compare_bp.route('/list', methods=['GET'])
@compare_permission_required
def get_compare_list():
    """
    获取比价数据列表（服务端分页+排序）
    支持分页、筛选和排序
    根据用户所在组织过滤数据
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        product_name = request.args.get('product_name', '').strip()
        vehicle_brand = request.args.get('vehicle_brand', '').strip()

        # 获取排序参数
        sort_field = request.args.get('sort_field', '').strip()
        sort_order = request.args.get('sort_order', 'asc').strip().lower()

        # 限制最大每页数量，防止性能问题
        limit = min(limit, 500)

        # 获取用户当前切换到的组织
        company = session.get('current_org', session.get('store', 'fsbbr'))

        # 使用服务层查询数据（传入company过滤）
        data, total = CompareDataService.list_data(
            oe=oe,
            brand=brand,
            product_name=product_name,
            vehicle_brand=vehicle_brand,
            company=company,
            page=page,
            limit=limit,
            order_by='updated_time',
            order_desc=True,
            sort_field=sort_field,
            sort_order=sort_order
        )

        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': data,
            'count': total,
            'page': page,
            'limit': limit
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取数据失败: {str(e)}'}), 500


@compare_bp.route('/export', methods=['GET'])
@compare_permission_required
def export_compare_data():
    """
    导出比价数据为Excel或CSV
    支持筛选条件，导出列与前端表格保持一致
    包含：最高价、最低价、采购记录（合并显示）
    """
    try:
        import json

        # 获取查询参数
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        product_name = request.args.get('product_name', '').strip()
        vehicle_brand = request.args.get('vehicle_brand', '').strip()
        export_format = request.args.get('format', 'excel').lower()

        # 获取用户当前切换到的组织
        company = session.get('current_org', session.get('store', 'fsbbr'))

        # 获取所有数据（不分页），根据搜索条件过滤
        data, _ = CompareDataService.list_data(
            oe=oe,
            brand=brand,
            product_name=product_name,
            vehicle_brand=vehicle_brand,
            company=company,
            page=1,
            limit=999999  # 获取所有数据
        )

        if not data:
            return jsonify({'code': 1, 'msg': '没有数据可导出'}), 400

        # 从 crmapp_procurement_history 表查询采购记录
        procurement_map = {}
        procurement_detail_map = {}
        if data:
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    # 构建查询条件
                    placeholders = ', '.join(['(%s, %s)'] * len(data))
                    base_params = []
                    for item in data:
                        base_params.append(item.get('oe', ''))
                        base_params.append(item.get('brand', ''))
                    if company:
                        # 查询每月最低价（与悬浮窗逻辑一致）
                        sql = f"""
                            SELECT oe, brand, supplier_name, unit_price, purchase_date
                            FROM crmapp_procurement_history t1
                            WHERE company = %s 
                            AND (oe, brand) IN ({placeholders})
                            AND purchase_date >= '2024-01-01'
                            AND purchase_date <= '2026-12-31'
                            AND unit_price = (
                                SELECT MIN(unit_price)
                                FROM crmapp_procurement_history t2
                                WHERE t2.oe = t1.oe 
                                AND t2.brand = t1.brand
                                AND t2.company = t1.company
                                AND DATE_FORMAT(t2.purchase_date, '%Y-%m') = DATE_FORMAT(t1.purchase_date, '%Y-%m')
                            )
                            ORDER BY purchase_date DESC
                        """
                        params = [company] + base_params
                        cursor.execute(sql, params)
                        rows = cursor.fetchall()
                        for row in rows:
                            key = (row[0], row[1])
                            if key not in procurement_map:
                                procurement_map[key] = []
                            procurement_map[key].append({
                                'supplier_name': row[2],
                                'purchase_price': float(row[3]) if row[3] else 0.0,
                                'purchase_date': row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                            })

                        # 查询全部采购记录（用于最高/最低价批注）
                        sql_detail = f"""
                            SELECT oe, brand, supplier_name, unit_price, purchase_date
                            FROM crmapp_procurement_history
                            WHERE company = %s 
                            AND (oe, brand) IN ({placeholders})
                            AND purchase_date >= '2024-01-01'
                            AND purchase_date <= '2026-12-31'
                            ORDER BY purchase_date DESC
                        """
                        params_detail = [company] + base_params
                        cursor.execute(sql_detail, params_detail)
                        rows = cursor.fetchall()
                        for row in rows:
                            key = (row[0], row[1])
                            if key not in procurement_detail_map:
                                procurement_detail_map[key] = []
                            procurement_detail_map[key].append({
                                'supplier_name': row[2],
                                'purchase_price': float(row[3]) if row[3] else 0.0,
                                'purchase_date': row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                            })
            except Exception as e:
                print(f"查询采购记录失败: {e}")
            finally:
                conn.close()
        
        # 处理数据，构建导出格式
        export_data = []
        row_comments = []
        for idx, item in enumerate(data, start=1):
            # 从 procurement_map 获取每月最低价记录，格式化为多行文本
            procurement_records_str = ''
            key = (item.get('oe', ''), item.get('brand', ''))
            if key in procurement_map and procurement_map[key]:
                try:
                    records = procurement_map[key]
                    if isinstance(records, list) and records:
                        # 按年月分组，每组只取第一条（最低价）
                        monthly_records = {}
                        for record in records:
                            date = record.get('purchase_date', '')
                            if date:
                                year_month = date[:7]  # 提取 YYYY-MM
                                if year_month not in monthly_records:
                                    monthly_records[year_month] = record
                        
                        # 按年月倒序排列，格式化为多行文本
                        sorted_months = sorted(monthly_records.keys(), reverse=True)
                        lines = []
                        for year_month in sorted_months:
                            record = monthly_records[year_month]
                            supplier = record.get('supplier_name', '')
                            price = record.get('purchase_price', '')
                            date = record.get('purchase_date', '')
                            if supplier:
                                lines.append(f"{year_month} {supplier}: ¥{price}")
                        procurement_records_str = '\n'.join(lines)
                except Exception as e:
                    procurement_records_str = ''

            # 格式化价格字段
            def format_price(value):
                if value is None or value == '' or value == 0:
                    return ''
                try:
                    return float(value)
                except:
                    return value

            # 格式化数字字段
            def format_number(value):
                if value is None or value == '' or value == 0:
                    return ''
                try:
                    return int(float(value))
                except:
                    return value

            max_price = format_price(item.get('max_price'))
            min_price = format_price(item.get('min_price'))
            price_pair = f"{max_price} / {min_price}" if (max_price or min_price) else ''

            row = {
                '行号': idx,
                'OE': item.get('oe', ''),
                '品牌': item.get('brand', ''),
                '产品名称': item.get('product_name', ''),
                '车辆品牌': item.get('vehicle_brand', ''),
                '替换号': item.get('replace_number', ''),
                '产品等级': item.get('product_level', ''),
                '供应商价格': format_price(item.get('supplier_price')),
                '最高/最低价': price_pair,
                '采购记录': procurement_records_str,
                '4S含税进价': format_price(item.get('dealer_purchase_price')),
                '4S含税售价': format_price(item.get('dealer_sale_price')),
                '更新价格时间': item.get('price_update_time', ''),
                '今日销量': format_number(item.get('today_sales')),
                '昨日销量': format_number(item.get('yesterday_sales')),
                '近7天销量': format_number(item.get('sales_7d')),
                '本月销量': format_number(item.get('month_sales')),
                '近6个月总销量': format_number(item.get('sales_6m')),
                '近12个月总销量': format_number(item.get('sales_12m')),
                '系统产品备注': item.get('product_remark', ''),
                '品牌编码': item.get('brand_code', '')
            }
            export_data.append(row)

            # 生成最高/最低价单元格的采购明细批注
            comment_text = ''
            if key in procurement_detail_map and procurement_detail_map[key]:
                comment_text = _build_procurement_table_text(procurement_detail_map[key])
            row_comments.append(comment_text)

        # 转换为DataFrame
        df = pd.DataFrame(export_data)

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'比价数据_{timestamp}'
        # 对中文文件名进行URL编码，避免UnicodeEncodeError
        from urllib.parse import quote
        encoded_filename = quote(filename)

        if export_format == 'csv':
            # 导出为CSV
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output.seek(0)

            return Response(
                output.getvalue(),
                mimetype='text/csv; charset=utf-8-sig',
                headers={
                    'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}.csv",
                    'Content-Type': 'text/csv; charset=utf-8-sig'
                }
            )
        else:
            # 导出为Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='比价数据')

                # 获取工作表并设置列宽
                worksheet = writer.sheets['比价数据']
                column_widths = {
                    'A': 8,   # 行号
                    'B': 15,  # OE
                    'C': 12,  # 品牌
                    'D': 25,  # 产品名称
                    'E': 15,  # 车辆品牌
                    'F': 15,  # 替换号
                    'G': 12,  # 产品等级
                    'H': 12,  # 供应商价格
                    'I': 18,  # 最高/最低价
                    'J': 40,  # 采购记录（较宽以显示多行内容）
                    'K': 12,  # 4S含税进价
                    'L': 12,  # 4S含税售价
                    'M': 18,  # 更新价格时间
                    'N': 10,  # 今日销量
                    'O': 10,  # 昨日销量
                    'P': 12,  # 近7天销量
                    'Q': 12,  # 本月销量
                    'R': 16,  # 近6个月总销量
                    'S': 16,  # 近12个月总销量
                    'T': 25,  # 系统产品备注
                    'U': 12   # 品牌编码
                }
                for col, width in column_widths.items():
                    worksheet.column_dimensions[col].width = width

                # 应用比价模块统一样式
                apply_uniform_style(worksheet)

                # 给最高/最低价列添加采购明细批注
                price_col_idx = None
                for col_idx, col_name in enumerate(df.columns, start=1):
                    if col_name == '最高/最低价':
                        price_col_idx = col_idx
                        break
                if price_col_idx:
                    for row_idx, comment_text in enumerate(row_comments, start=2):
                        if comment_text:
                            cell = worksheet.cell(row=row_idx, column=price_col_idx)
                            cell.comment = Comment(comment_text, "采购明细")

            output.seek(0)

            return Response(
                output.getvalue(),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={
                    'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}.xlsx"
                }
            )

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'导出失败: {str(e)}'}), 500


@compare_bp.route('/import_search', methods=['POST'])
@compare_permission_required
def import_search_compare_data():
    """
    导入Excel模板，使用采购历史比对功能生成结果Excel并记录导入日志
    支持列：OE、品牌、价格/促销价（可选）、品牌号（可选）
    """
    try:
        if 'file' not in request.files:
            return jsonify({'code': 1, 'msg': '请上传文件'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'code': 1, 'msg': '请上传文件'}), 400

        # 读取Excel
        try:
            df = pd.read_excel(file, dtype=str)
        except Exception as e:
            return jsonify({'code': 1, 'msg': f'读取Excel失败: {str(e)}'}), 400

        if df.empty:
            return jsonify({'code': 1, 'msg': 'Excel中没有数据'}), 400

        # 列名映射（与询价模块 parse_oe_list 保持一致）
        columns = {str(col).strip().lower(): str(col).strip() for col in df.columns}

        oe_col = None
        brand_col = None
        price_col = None
        brand_code_col = None

        for key in ['oe', 'oe号', 'oe_no', 'oe编号']:
            if key in columns:
                oe_col = columns[key]
                break

        for key in ['品牌', 'brand', 'pinpai']:
            if key in columns:
                brand_col = columns[key]
                break

        for key in ['价格', 'price', '单价', '价格/促销价']:
            if key in columns:
                price_col = columns[key]
                break

        for key in ['品牌号', 'brand_code', '品牌编码']:
            if key in columns:
                brand_code_col = columns[key]
                break

        if not oe_col:
            return jsonify({'code': 1, 'msg': 'Excel中未找到 OE 列，请使用模板格式'}), 400
        if not brand_col:
            return jsonify({'code': 1, 'msg': 'Excel中未找到 品牌 列，请使用模板格式'}), 400

        # 提取有效 items（oe+品牌 或 brand_code 有值其一即可）
        items = []
        for _, row in df.iterrows():
            oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            price = str(row[price_col]).strip() if price_col and pd.notna(row[price_col]) else ''
            brand_code = str(row[brand_code_col]).strip() if brand_code_col and pd.notna(row[brand_code_col]) else ''

            if not ((oe and brand) or brand_code):
                continue

            item = {'oe': oe, 'brand': brand, 'price': price}
            if brand_code:
                item['brand_code'] = brand_code
            items.append(item)

        import_count = len(items)
        if import_count == 0:
            return jsonify({'code': 1, 'msg': 'Excel中没有有效的OE和品牌数据'}), 400

        # 获取用户当前组织和操作人
        company = session.get('current_org', session.get('store', 'fsbbr'))
        operator = session.get('username', '')

        # 调用采购历史比对服务生成结果
        from app.services.compare_service.procurement_compare_service import ProcurementCompareService
        from app.utils.export_tools.purchase_history_excel_writer import PurchaseHistoryExcelWriter
        from app.utils.logger_config import get_task_logger

        logger = get_task_logger('purchase_history_compare')
        logger.info(f"[比价导入] 开始处理: file={file.filename}, items={import_count}, company={company}")

        results = ProcurementCompareService.batch_generate_compare_results(items, company)

        match_count = len(results)
        result_file_path = ''

        if results:
            from app.utils.logger_config import BASE_LOG_DIR
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
            output_filename = f"compare_import_{safe_filename}_{timestamp}.xlsx"
            task_dir = os.path.join(BASE_LOG_DIR, 'compare_import', company)
            os.makedirs(task_dir, exist_ok=True)
            output_path = os.path.join(task_dir, output_filename)

            PurchaseHistoryExcelWriter.generate_excel(results, output_path)
            result_file_path = output_path
            logger.info(f"[比价导入] Excel生成完成: {output_path}, 结果行数={match_count}")

        # 保存导入日志
        log_id = CompareDataService.save_import_log(
            company=company,
            file_name=file.filename,
            import_count=import_count,
            match_count=match_count,
            operator=operator,
            result_file_path=result_file_path
        )

        return jsonify({
            'code': 0,
            'msg': '导入查询成功',
            'log_id': log_id,
            'file_name': file.filename,
            'import_count': import_count,
            'match_count': match_count,
            'download_url': f'/api/purchase_plan/compare/download_import_result/{log_id}' if result_file_path else ''
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'导入查询失败: {str(e)}'}), 500


@compare_bp.route('/import_logs', methods=['GET'])
@compare_permission_required
def get_import_logs():
    """
    获取导入日志列表
    """
    try:
        company = session.get('current_org', session.get('store', 'fsbbr'))
        limit = int(request.args.get('limit', 50))
        limit = min(limit, 200)

        logs = CompareDataService.get_import_logs(company=company, limit=limit)

        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': logs
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取导入日志失败: {str(e)}'}), 500


@compare_bp.route('/download_import_result/<int:log_id>', methods=['GET'])
@compare_permission_required
def download_import_result(log_id):
    """
    下载导入结果Excel文件
    """
    try:
        company = session.get('current_org', session.get('store', 'fsbbr'))
        log = CompareDataService.get_import_log_by_id(log_id=log_id, company=company)

        if not log:
            return jsonify({'code': 1, 'msg': '记录不存在'}), 404

        file_path = log.get('result_file_path', '')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'code': 1, 'msg': '文件不存在或已过期'}), 404

        return send_file(
            file_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=log.get('file_name', '比价导入结果.xlsx').replace('.xlsx', '') + '_结果.xlsx'
        )

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'下载失败: {str(e)}'}), 500


@compare_bp.route('/statistics', methods=['GET'])
@compare_permission_required
def get_statistics():
    """
    获取比价数据统计信息
    """
    try:
        stats = CompareDataService.get_statistics()

        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': stats
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取统计信息失败: {str(e)}'}), 500





@compare_bp.route('/upsert', methods=['POST'])
@compare_permission_required
def upsert_data():
    """
    插入或更新单条数据
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 1, 'msg': '请求数据不能为空'}), 400

        if 'oe' not in data or not data['oe']:
            return jsonify({'code': 1, 'msg': 'OE号不能为空'}), 400

        record_id = CompareDataService.upsert_by_oe(data)

        return jsonify({
            'code': 0,
            'msg': '保存成功',
            'data': {'id': record_id}
        })

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'保存失败: {str(e)}'}), 500


@compare_bp.route('/delete/<int:record_id>', methods=['DELETE'])
@compare_permission_required
def delete_data(record_id):
    """
    根据ID删除数据
    """
    try:
        affected = CompareDataService.delete_by_id(record_id)

        if affected > 0:
            return jsonify({
                'code': 0,
                'msg': '删除成功'
            })
        else:
            return jsonify({
                'code': 1,
                'msg': '记录不存在'
            }), 404

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'删除失败: {str(e)}'}), 500


@compare_bp.route('/get/<int:record_id>', methods=['GET'])
@compare_permission_required
def get_by_id(record_id):
    """
    根据ID获取单条数据
    """
    try:
        data = CompareDataService.get_by_id(record_id)

        if data:
            return jsonify({
                'code': 0,
                'msg': '获取成功',
                'data': data
            })
        else:
            return jsonify({
                'code': 1,
                'msg': '记录不存在'
            }), 404

    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取失败: {str(e)}'}), 500


@compare_bp.route('/quote_history/batch', methods=['POST'])
@compare_permission_required
def get_quote_history_batch():
    """
    批量查询多个产品的询价历史
    请求体格式：{"products": [{"oe": "xxx", "brand": "xxx"}, ...]}
    返回：每个产品的近36个月询价次数
    """
    try:
        data = request.get_json()
        if not data or 'products' not in data:
            return jsonify({'code': 1, 'msg': '请求参数错误，需要提供products列表'}), 400
        
        products = data['products']
        if not isinstance(products, list) or len(products) == 0:
            return jsonify({'code': 1, 'msg': 'products必须是非空数组'}), 400
        
        # 限制单次查询数量，防止性能问题
        if len(products) > 500:
            return jsonify({'code': 1, 'msg': '单次查询最多支持500个产品'}), 400
        
        # 构建产品标识列表
        product_keys = []
        for p in products:
            if 'oe' in p and 'brand' in p:
                product_keys.append((p['oe'], p['brand']))
        
        if not product_keys:
            return jsonify({'code': 1, 'msg': '产品信息不完整，需要oe和brand字段'}), 400
        
        # 获取用户当前组织
        company = session.get('current_org', session.get('store', 'fsbbr'))
        
        # 批量查询询价历史
        result = CompareDataService.get_quote_history_batch(product_keys, company=company, months=36)
        
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取询价历史失败: {str(e)}'}), 500


@compare_bp.route('/procurement_history', methods=['GET'])
@compare_permission_required
def get_procurement_history():
    """
    查询单个产品的采购历史
    参数：oe, brand
    返回：采购记录列表
    """
    try:
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        
        if not oe or not brand:
            return jsonify({'code': 1, 'msg': 'OE号和品牌不能为空'}), 400
        
        # 获取用户当前组织
        company = session.get('current_org', session.get('store', 'fsbbr'))
        
        # 查询采购历史
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                    SELECT supplier_name, unit_price, purchase_date
                    FROM crmapp_procurement_history
                    WHERE oe = %s AND brand = %s AND company = %s
                    ORDER BY purchase_date DESC
                """
                cursor.execute(sql, (oe, brand, company))
                rows = cursor.fetchall()
                records = []
                for row in rows:
                    records.append({
                        'supplier_name': row['supplier_name'],
                        'purchase_price': float(row['unit_price']) if row['unit_price'] else 0.0,
                        'purchase_date': row['purchase_date'].strftime('%Y-%m-%d') if hasattr(row['purchase_date'], 'strftime') else str(row['purchase_date'])
                    })
                return jsonify({
                    'code': 0,
                    'msg': '获取成功',
                    'data': {
                        'oe': oe,
                        'brand': brand,
                        'history': records
                    }
                })
        except Exception as e:
            return jsonify({'code': 1, 'msg': f'获取采购历史失败: {str(e)}'}), 500
        finally:
            conn.close()
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取采购历史失败: {str(e)}'}), 500


@compare_bp.route('/procurement_history/batch', methods=['POST'])
@compare_permission_required
def get_procurement_history_batch():
    """
    批量查询多个产品的采购历史
    请求体格式：{"products": [{"oe": "xxx", "brand": "xxx"}, ...]}
    返回：每个产品的采购记录列表
    """
    try:
        data = request.get_json()
        if not data or 'products' not in data:
            return jsonify({'code': 1, 'msg': '请求参数错误，需要提供products列表'}), 400
        
        products = data['products']
        if not isinstance(products, list) or len(products) == 0:
            return jsonify({'code': 1, 'msg': 'products必须是非空数组'}), 400
        
        # 限制单次查询数量，防止性能问题
        if len(products) > 500:
            return jsonify({'code': 1, 'msg': '单次查询最多支持500个产品'}), 400
        
        # 构建产品标识列表
        product_keys = []
        for p in products:
            if 'oe' in p and 'brand' in p:
                product_keys.append((p['oe'], p['brand']))
        
        if not product_keys:
            return jsonify({'code': 1, 'msg': '产品信息不完整，需要oe和brand字段'}), 400
        
        # 获取用户当前组织
        company = session.get('current_org', session.get('store', 'fsbbr'))
        
        # 批量查询采购历史
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 构建查询条件
                placeholders = ', '.join(['(%s, %s)'] * len(product_keys))
                params = []
                for oe, brand in product_keys:
                    params.append(oe)
                    params.append(brand)
                params.insert(0, company)
                
                sql = f"""
                    SELECT oe, brand, supplier_name, unit_price, purchase_date
                    FROM crmapp_procurement_history
                    WHERE company = %s AND (oe, brand) IN ({placeholders})
                    ORDER BY purchase_date DESC
                """
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                # 按产品分组
                result = {}
                for row in rows:
                    key = f"{row['oe']}|{row['brand']}"
                    if key not in result:
                        result[key] = []
                    result[key].append({
                        'supplier_name': row['supplier_name'],
                        'purchase_price': float(row['unit_price']) if row['unit_price'] else 0.0,
                        'purchase_date': row['purchase_date'].strftime('%Y-%m-%d') if hasattr(row['purchase_date'], 'strftime') else str(row['purchase_date'])
                    })
                
                return jsonify({
                    'code': 0,
                    'msg': '获取成功',
                    'data': result
                })
        except Exception as e:
            return jsonify({'code': 1, 'msg': f'获取采购历史失败: {str(e)}'}), 500
        finally:
            conn.close()
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取采购历史失败: {str(e)}'}), 500


@compare_bp.route('/quote_history', methods=['GET'])
@compare_permission_required
def get_quote_history():
    """
    查询单个产品的询价历史
    参数：oe, brand
    返回：近36个月的询价次数列表
    """
    try:
        oe = request.args.get('oe', '').strip()
        brand = request.args.get('brand', '').strip()
        
        if not oe or not brand:
            return jsonify({'code': 1, 'msg': 'OE号和品牌不能为空'}), 400
        
        # 获取用户当前组织
        company = session.get('current_org', session.get('store', 'fsbbr'))
        
        # 查询询价历史
        result = CompareDataService.get_quote_history(oe, brand, company=company, months=36)
        
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': {
                'oe': oe,
                'brand': brand,
                'history': result
            }
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取询价历史失败: {str(e)}'}), 500
