"""
通用数据导出工具模块
支持多表导出、复合搜索条件、维度切换
"""

import io
import json
from datetime import datetime
from flask import Response, jsonify
from app.utils.database_connection import get_db_connection
import pymysql


def parse_purchase_records(records_json):
    """
    解析 purchase_records JSON，提取日期、供应商名称和价格。

    与购物车页面 supplier-render.js 解析逻辑保持一致：
    数据格式：'[{"supplier_name":"佛山德孚","purchase_price":15.0,"purchase_date":"2026-01-12"}]'

    Args:
        records_json: purchase_records JSON 字符串

    Returns:
        list: [(日期, 供应商名称, 价格), ...]；解析失败或为空时返回空列表
    """
    if not records_json or not isinstance(records_json, str):
        return []

    try:
        records = json.loads(records_json)
        if isinstance(records, list):
            suppliers = []
            for r in records:
                name = r.get('supplier_name', '').strip()
                price = r.get('purchase_price', 0.0)
                date = r.get('purchase_date', '').strip()
                if name:
                    suppliers.append((date, name, f"{price:.2f}"))
            return suppliers
    except (json.JSONDecodeError, TypeError):
        pass

    return []


def build_supplier_field(original_supplier, purchase_records):
    """
    构建供应商字段值：优先使用 purchase_records JSON，没有则回退到原始供应商字符串。

    输出格式与购物车页面 tooltip 一致：
      - 有日期："日期 - 供应商 - 单价"
      - 无日期："供应商 - 单价"

    Args:
        original_supplier: 原始供应商字段值
        purchase_records: purchase_records JSON 字符串

    Returns:
        str: 格式化后的供应商字符串，多个供应商用换行分隔
    """
    records = parse_purchase_records(purchase_records)
    if records:
        parts = []
        for date, name, price in records:
            if date:
                parts.append(f"{date} - {name} - {price}")
            else:
                parts.append(f"{name} - {price}")
        return '\n'.join(parts)
    return original_supplier or ''


def parse_supplier_string(supplier_str):
    """
    解析供应商字符串，将多个供应商拆分成列表
    
    Args:
        supplier_str: 供应商字符串，格式如 "供应商A: 100\n供应商B: 200"
    
    Returns:
        list: [(供应商名称, 价格), ...]
    """
    if not supplier_str or not isinstance(supplier_str, str):
        return [(supplier_str or "N/A", "N/A")]

    # 按换行符分割供应商信息
    supplier_parts = supplier_str.split('\n')

    suppliers = []
    for part in supplier_parts:
        part = part.strip()
        if not part:
            continue

        # 查找冒号分隔的供应商名称和价格
        colon_index = part.rfind(':')
        if colon_index == -1:
            colon_index = part.rfind('：')  # 尝试中文冒号

        if colon_index != -1:
            name = part[:colon_index].strip()
            price = part[colon_index + 1:].strip()
            suppliers.append((name, price))
        else:
            # 如果没有找到冒号，整个部分作为供应商名称
            suppliers.append((part, "N/A"))

    return suppliers if suppliers else [("N/A", "N/A")]


def export_data_to_excel(data, headers_config, field_list, filename='export.xlsx', sheet_name='数据'):
    """
    将数据导出为Excel格式（默认格式）
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return jsonify({'code': 1, 'msg': '缺少openpyxl库，无法导出Excel'}), 500
    
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    
    # 写入表头
    header_row = [headers_config.get(field, field) for field in field_list]
    for col_num, header in enumerate(header_row, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # 写入数据
    for row_num, row_data in enumerate(data, 2):
        for col_num, field in enumerate(field_list, 1):
            value = row_data.get(field, '')
            if value is None:
                value = ''
            ws.cell(row=row_num, column=col_num, value=value)
    
    # 调整列宽
    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        for cell in column:
            try:
                if cell.value and len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # 保存到字节流
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    # 对文件名进行URL编码以支持中文
    from urllib.parse import quote
    encoded_filename = quote(filename)
    
    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment;filename*=UTF-8''{encoded_filename}"
        }
    )


def export_beihuo(store, search_params=None):
    """
    导出备货数据
    
    Args:
        store: 门店代码
        search_params: 搜索条件字典，支持复合搜索
    """
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 前端展示字段（与表格显示一致）
        fields = [
            'oe', '物料名称', '品牌', '物料条码', '车型品牌', '标签',
            '库存金额', '成本价', '库存数量', '近12个月月均销量', '近6个月月均销量',
            '本月销量', '近7天销量', '昨日销量', '今日销量', '成品可卖天数',
            '预警状态', '供应商', '近1个月询价量', '近3个月月均询价量',
            '全国近1个月询价量', '全国近3个月月均询价量', '品牌号', '内部备注',
            '在途数量', '车型'
        ]
        
        # 表头映射
        headers = {
            'oe': 'OE', '物料名称': '物料名称', '品牌': '品牌', '物料条码': '物料条码',
            '车型品牌': '车型品牌', '标签': '标签', '库存金额': '库存金额', '成本价': '成本价',
            '库存数量': '库存数量', '近12个月月均销量': '近12个月月均销量',
            '近6个月月均销量': '近6个月月均销量', '本月销量': '本月销量',
            '近7天销量': '近7天销量', '昨日销量': '昨日销量', '今日销量': '今日销量',
            '成品可卖天数': '成品可卖天数', '预警状态': '预警状态', '供应商': '供应商',
            '近1个月询价量': '近1个月询价量', '近3个月月均询价量': '近3个月月均询价量',
            '全国近1个月询价量': '全国近1个月询价量', '全国近3个月月均询价量': '全国近3个月月均询价量',
            '品牌号': '品牌号', '内部备注': '内部备注', '在途数量': '在途数量',
            '车型': '车型'
        }
        
        # 构建SQL
        fields_str = ', '.join([f'`{f}`' for f in fields])
        where_parts = ["`company` = %s"]
        params = [store]
        
        # 复合搜索条件
        if search_params:
            # OE搜索
            if search_params.get('oe'):
                where_parts.append("`oe` LIKE %s")
                params.append(f"%{search_params['oe']}%")
            
            # 供应商搜索
            if search_params.get('supplier'):
                where_parts.append("`供应商` LIKE %s")
                params.append(f"%{search_params['supplier']}%")
            
            # 品牌搜索
            if search_params.get('brand'):
                where_parts.append("`品牌` = %s")
                params.append(search_params['brand'])
            
            # 物料名称搜索
            if search_params.get('material_name'):
                where_parts.append("`物料名称` LIKE %s")
                params.append(f"%{search_params['material_name']}%")
            
            # 标签搜索
            if search_params.get('tag'):
                where_parts.append("`标签` = %s")
                params.append(search_params['tag'])
            
            # 物料条码搜索
            if search_params.get('barcode'):
                where_parts.append("`物料条码` LIKE %s")
                params.append(f"%{search_params['barcode']}%")
            
            # 车型品牌搜索
            if search_params.get('car_brand'):
                where_parts.append("`车型品牌` = %s")
                params.append(search_params['car_brand'])
        
        where_clause = " WHERE " + " AND ".join(where_parts)
        sql = f"SELECT {fields_str} FROM `crmapp_beihuo`{where_clause} ORDER BY CASE WHEN `oe` IS NULL OR `oe` = '' THEN 1 ELSE 0 END, `oe`"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        if not rows:
            return jsonify({'code': 1, 'msg': '没有数据可导出'}), 400
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"备货数据_{timestamp}.xlsx"
        
        return export_data_to_excel(rows, headers, fields, filename, '备货数据')
        
    except Exception as e:
        print(f"导出备货数据失败: {e}")
        return jsonify({'code': 1, 'msg': f'导出失败: {str(e)}'}), 500
    finally:
        conn.close()


def export_cart(store, search_params=None):
    """
    导出购物车数据
    
    Args:
        store: 门店代码
        search_params: 搜索条件字典，支持复合搜索和维度切换
    """
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取维度（默认产品维度）
        dimension = 'product'
        if search_params:
            dimension = search_params.get('dimension', 'product')
        
        # 字段配置（两个维度字段相同）
        fields = [
            'oe', 'supplier', 'brand', 'material_name', 'barcode', 'brand_code',
            'car_brand', 'tag', 'car_model', 'stock', 'on_way',
            'today_sales', 'sales_yesterday', 'sales_7d', 'sales_month', 'avg_sales_6m', 'avg_sales_12m',
            'inquiry_1m', 'inquiry_3m', 'national_inquiry_1m', 'national_inquiry_3m',
            'internal_remarks', 'stock_amount', 'sellable_days', 'cost_price', 'warning_status',
            'quantity', 'added_time', 'added_by'
        ]

        headers = {
            'oe': 'OE', 'supplier': '供应商', 'brand': '品牌', 'material_name': '物料名称',
            'barcode': '物料条码', 'brand_code': '品牌号',
            'car_brand': '车型品牌', 'tag': '标签', 'car_model': '车型',
            'stock': '库存数量', 'on_way': '在途数量',
            'today_sales': '今日销量', 'sales_yesterday': '昨日销量', 'sales_7d': '近7天销量',
            'sales_month': '本月销量', 'avg_sales_6m': '近6个月月均销量', 'avg_sales_12m': '近12个月月均销量',
            'inquiry_1m': '近1个月询价量', 'inquiry_3m': '近3个月月均询价量',
            'national_inquiry_1m': '全国近1个月询价量', 'national_inquiry_3m': '全国近3个月月均询价量',
            'internal_remarks': '内部备注', 'stock_amount': '库存金额',
            'sellable_days': '成品可卖天数', 'cost_price': '成本价', 'warning_status': '预警状态',
            'quantity': '数量', 'added_time': '加入时间', 'added_by': '账户名'
        }
        
        # 构建SQL
        fields_str = ', '.join([f'`{f}`' for f in fields])
        where_parts = ["`store` = %s"]
        params = [store]
        
        # 复合搜索条件
        if search_params:
            # OE搜索
            if search_params.get('oe'):
                where_parts.append("`oe` LIKE %s")
                params.append(f"%{search_params['oe']}%")
            
            # 物料条码/品牌号搜索
            if search_params.get('barcode'):
                where_parts.append("(`barcode` LIKE %s OR `brand_code` LIKE %s)")
                params.append(f"%{search_params['barcode']}%")
                params.append(f"%{search_params['barcode']}%")
            
            # 物料名称搜索
            if search_params.get('material_name'):
                where_parts.append("`material_name` LIKE %s")
                params.append(f"%{search_params['material_name']}%")
            
            # 品牌搜索
            if search_params.get('brand'):
                where_parts.append("`brand` = %s")
                params.append(search_params['brand'])
            
            # 标签搜索
            if search_params.get('tag'):
                where_parts.append("`tag` = %s")
                params.append(search_params['tag'])
            
            # 车型搜索
            if search_params.get('car_model'):
                where_parts.append("`car_model` LIKE %s")
                params.append(f"%{search_params['car_model']}%")
        
        where_clause = " WHERE " + " AND ".join(where_parts)
        sql = f"SELECT {fields_str} FROM `crmapp_cart`{where_clause} ORDER BY added_time DESC"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            return jsonify({'code': 1, 'msg': '没有数据可导出'}), 400

        # 如果是供应商维度，拆分供应商数据
        if dimension == 'supplier':
            expanded_rows = []
            for row in rows:
                supplier_str = row.get('supplier', '')
                suppliers = parse_supplier_string(supplier_str)
                for supplier_name, price in suppliers:
                    # 创建新行，复制原行数据
                    new_row = row.copy()
                    new_row['supplier'] = f"{supplier_name}: {price}"
                    expanded_rows.append(new_row)
            rows = expanded_rows

        # 生成文件名（始终包含维度信息）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dim_text = '供应商维度' if dimension == 'supplier' else '产品维度'
        filename = f"购物车_{dim_text}_{timestamp}.xlsx"

        return export_data_to_excel(rows, headers, fields, filename, f'购物车-{dim_text}')
        
    except Exception as e:
        print(f"导出购物车数据失败: {e}")
        return jsonify({'code': 1, 'msg': f'导出失败: {str(e)}'}), 500
    finally:
        conn.close()


def handle_export_request(export_type, store=None, search_params=None):
    """
    处理导出请求的入口函数
    
    Args:
        export_type: 导出类型（beihuo/cart）
        store: 门店权限
        search_params: 搜索条件字典（支持复合搜索）
    
    Returns:
        Response: Flask响应对象
    """
    if export_type == 'beihuo':
        return export_beihuo(store, search_params=search_params)
    elif export_type == 'cart':
        return export_cart(store, search_params=search_params)
    else:
        return jsonify({'code': 1, 'msg': f'未知的导出类型: {export_type}'}), 400
