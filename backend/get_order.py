# backend/get_order.py
import os, requests, json
from flask import Blueprint, request, jsonify, render_template_string
from datetime import datetime
from bs4 import BeautifulSoup
import random
import string
from threading import Thread
import pymysql
from pathlib import Path
from app.utils.database_connection import get_db_connection  # 使用统一的连接池实现

# 创建 Blueprint
get_order_bp = Blueprint('get_order', __name__)

# 全局变量定义（保持不变）
temp_links = {}

def init_db():
    """初始化数据库表"""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS order_links (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_no VARCHAR(50) NOT NULL,
        order_id INT,
        generated_time DATETIME NOT NULL,
        generated_link VARCHAR(100) NOT NULL,
        random_key VARCHAR(50),
        expires_at DATETIME,
        INDEX idx_order_no (order_no),
        INDEX idx_generated_link (generated_link),
        INDEX idx_random_key (random_key)
    ) DEFAULT CHARSET=utf8mb4
    """
    
    cursor.execute(create_table_sql)
    
    # 检查order_id字段是否存在，不存在则添加
    cursor.execute("SHOW COLUMNS FROM order_links LIKE 'order_id'")
    result = cursor.fetchone()
    if not result:
        alter_table_sql = "ALTER TABLE order_links ADD COLUMN order_id INT"
        cursor.execute(alter_table_sql)
    
    cursor.execute("SHOW COLUMNS FROM order_links LIKE 'random_key'")
    result = cursor.fetchone()
    if not result:
        alter_table_sql = "ALTER TABLE order_links ADD COLUMN random_key VARCHAR(50)"
        cursor.execute(alter_table_sql)
        try:
            cursor.execute("CREATE INDEX idx_random_key ON order_links (random_key)")
        except Exception as e:
            pass  # 索引可能已存在
    
    connection.commit()
    cursor.close()
    connection.close()

def get_existing_link_for_order(order_no):
    """检查数据库中是否已有该订单号的链接"""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        sql = "SELECT generated_link, random_key, order_id FROM order_links WHERE order_no = %s ORDER BY generated_time DESC LIMIT 1"
        cursor.execute(sql, (order_no,))
        result = cursor.fetchone()
        return result
    except Exception as e:
        return None
    finally:
        cursor.close()
        connection.close()

def save_order_link_to_db(order_no, generated_link, random_key, order_id=None, expires_at=None):
    """将订单链接信息保存到数据库"""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        sql = """
        INSERT INTO order_links (order_no, generated_time, generated_link, random_key, order_id, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (order_no, datetime.now(), generated_link, random_key, order_id, expires_at))
        connection.commit()
    except Exception as e:
        pass  # 静默处理保存失败的情况
    finally:
        cursor.close()
        connection.close()

def get_crm_cookies():
    url = "http://113.45.176.129:8001/get_crm_cookies?key=fs"
    payload = {}
    request_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en-US;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }
    response = requests.request("GET", url, headers=request_headers, data=payload)
    cookies = json.loads(response.text)['cookie']
    return cookies

CRM_COOKIES = get_crm_cookies()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
    'referer': 'https://crm.gzbbr.com/',
}
headers.update(CRM_COOKIES)


def get_order_detail_by_id(orders_id, order_no):
    """根据订单ID获取订单详情"""
    detail_url = 'https://crm.gzbbr.com/api/Crm.Orders/orders_view'
    detail_params = {'orders_id': str(orders_id)}
    detail_response = requests.get(detail_url, headers=headers, params=detail_params)
    
    if detail_response.status_code == 200:
        detail_data = detail_response.json()
        if 'data' in detail_data:
            # 直接使用 orders_view 接口返回的数据
            order_data = detail_data['data']
            # 确保订单号正确
            if 'TableHeader' in order_data and 'orders_no' in order_data['TableHeader']:
                order_data['orders_no'] = order_data['TableHeader']['orders_no']
            else:
                order_data['orders_no'] = order_no
            return order_data
    return None


def get_order_detail(target_orders_no):
    """获取订单详情，包括产品明细"""
    print(f"获取订单详情: 正在请求 mergeOrderList 接口获取订单 {target_orders_no} 的概要信息")
    order_url = 'https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList'
    params = {'orders_no': target_orders_no, 'page': '1', 'limit': '20'}
    response = requests.get(order_url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and 'list' in data['data']:
            order_list = data['data']['list']['data']
            for order_summary in order_list:
                if order_summary.get('orders_no') == target_orders_no:
                    orders_id = order_summary.get('orders_id')
                    if orders_id:
                        print(f"获取订单详情: 正在请求 orders_view 接口获取订单 {target_orders_no} 的详细信息，ID: {orders_id}")
                        order_data = get_order_detail_by_id(orders_id, target_orders_no)
                        if order_data:
                            print(f"获取订单详情: 成功获取订单 {target_orders_no} 的完整信息")
                            return order_data
                        else:
                            print(f"获取订单详情: 请求 orders_view 接口失败")
                            return order_summary
                    print(f"获取订单详情: 订单 {target_orders_no} 没有找到有效的订单ID")
                    return order_summary
    print(f"获取订单详情: 未能获取订单 {target_orders_no} 的详情")
    return None


@get_order_bp.route('/api/order_preview', methods=['POST'])
def get_order_preview():
    """获取订单预览 HTML"""
    try:
        data = request.get_json()
        order_no = data.get('order_no')
        order_id = data.get('order_id')  # 接收order_id参数
        key = data.get('key')  # 接收key参数用于更新数据库
        
        if not order_no:
            return jsonify({'code': 1, 'msg': '缺少订单号'}), 400
        
        # 如果提供了有效的order_id，直接使用order_id获取订单详情
        # 检查order_id是否为有效值（非空、非None、非'None'、非'null'等）
        if order_id and str(order_id).strip() != '' and str(order_id).lower() != 'none' and str(order_id).lower() != 'null':
            print(f"获取订单预览: 订单 {order_no} 有ID {order_id}，直接请求orders_view接口")
            order_data = get_order_detail_by_id(order_id, order_no)
            if not order_data:
                return jsonify({'code': 1, 'msg': '无法连接到CRM系统获取订单详情'}), 404
        else:
            # 如果没有提供有效的order_id，使用旧方法获取订单详情
            print(f"获取订单预览: 订单 {order_no} 没有有效的ID，使用旧方法获取订单详情")
            
            # 通过mergeOrderList获取订单ID
            order_url = 'https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList'
            params = {'orders_no': order_no, 'page': '1', 'limit': '20'}
            response = requests.get(order_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data_response = response.json()
                if 'data' in data_response and 'list' in data_response['data']:
                    order_list = data_response['data']['list']['data']
                    for order_summary in order_list:
                        if order_summary.get('orders_no') == order_no:
                            orders_id = order_summary.get('orders_id')
                            if orders_id:
                                order_data = get_order_detail_by_id(orders_id, order_no)
                                if not order_data:
                                    print(f"获取订单预览: 无法连接到CRM系统获取订单 {order_no} 的详情")
                                    return jsonify({'code': 1, 'msg': '无法连接到CRM系统获取订单详情'}), 404
                                
                                # 如果获取到了订单详情，尝试从中获取order_id并更新到数据库
                                if order_data and 'orders_id' in order_data and key:
                                    updated_order_id = order_data.get('orders_id')
                                    
                                    # 更新数据库中的order_id字段
                                    try:
                                        update_connection = get_db_connection()
                                        update_cursor = update_connection.cursor()
                                        
                                        # 使用传入的key参数更新正确的记录
                                        update_sql = "UPDATE order_links SET order_id = %s WHERE random_key = %s"
                                        update_cursor.execute(update_sql, (updated_order_id, key))
                                        update_connection.commit()
                                        
                                        print(f"已更新订单 {order_no} 的 order_id 为 {updated_order_id}")
                                    except Exception as e:
                                        print(f"Error updating order_id in database: {e}")
                                    finally:
                                        update_cursor.close()
                                        update_connection.close()
                                
                                break
                            else:
                                print(f"获取订单预览: 订单 {order_no} 没有有效的ID")
                                return jsonify({'code': 1, 'msg': '订单没有有效的ID'}), 404
            else:
                print(f"获取订单预览: 未能获取订单 {order_no} 的概要信息")
                return jsonify({'code': 1, 'msg': '未能获取订单概要信息'}), 404

        if not order_data:
            print(f"获取订单预览: 未找到订单 {order_no}")
            return jsonify({'code': 1, 'msg': '未找到订单'}), 404
        
        # 生成 HTML 内容
        html_content = generate_order_html_content(order_data)
        
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': {
                'html': html_content
            }
        })
        
    except Exception as e:
        print(f"获取订单预览失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': '获取预览失败'}), 500

def replace_span_content(html_content, label_text, new_value):
    """替换HTML中特定标签的内容"""
    soup = BeautifulSoup(html_content, 'html.parser')
    detail_items = soup.find_all('div', class_='detail-item')
    
    for item in detail_items:
        label = item.find('span', class_='detail-label')
        if label and label.get_text().strip() == label_text:
            span = label.find_next_sibling('span')
            if span:
                span.string = str(new_value)
    
    return str(soup)

def replace_image_sources(html_content):
    """替换图片路径为绝对路径"""
    import re
    html_content = re.sub(r'src="[^"]*frey_logo\.png"', 'src="/static/images/frey_logo.png"', html_content)
    html_content = re.sub(r'src="[^"]*bbr_logo\.png"', 'src="/static/images/bbr_logo.png"', html_content)
    return html_content

def generate_order_html_content(api_response_data):
    """
    根据API响应数据生成订单HTML内容（在内存中处理）
    """
    # 使用相对于项目根目录的路径
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'order_preview.html')
    
    with open(template_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # 提取订单数据
    order_data = api_response_data
    
    # 从TableHeader获取关键字段，如果不存在则从顶层获取
    table_header = order_data.get('TableHeader', {})
    
    # 获取具体字段值
    # 根据API响应结构，优先从TableHeader获取关键信息
    fullname = table_header.get('fullname', order_data.get('fullname', ''))
    customer_phone = table_header.get('phone', order_data.get('customer_phone', ''))
    create_timestamp = table_header.get('create_date', order_data.get('create_date', ''))
    
    # 地址字段获取逻辑
    street_raw = table_header.get('street', order_data.get('street', ''))
    if isinstance(street_raw, dict):
        address = street_raw.get('street', '')
    else:
        address = street_raw
    
    orders_no = order_data.get('orders_no', '')
    
    # 获取备注信息 - 从多个可能的位置查找
    # 优先级：order_data -> TableHeader -> abstract
    remark = order_data.get('remark', '') 
    if not remark:
        remark = table_header.get('remark', '')
    if not remark:
        remark = order_data.get('abstract', '')
    if not remark:
        remark = table_header.get('abstract', '')
    
    # 获取self_lifting值和其他物流相关信息
    self_lifting = table_header.get('self_lifting', order_data.get('TableHeader', {}).get('self_lifting', 0))
    
    # 检查物流信息，优先从TableHeader获取
    logistics_name = table_header.get('logistics_name', order_data.get('logistics_name', ''))
    logistics_shift = table_header.get('logistics_shift', order_data.get('logistics_shift', ''))
    logistics_pay_type = table_header.get('logistics_pay_type', order_data.get('logistics_pay_type', ''))
    logistics_transport_type = table_header.get('logistics_transport_type', order_data.get('logistics_transport_type', ''))
    
    # 转换时间戳为日期格式
    if isinstance(create_timestamp, (int, float)) and create_timestamp > 0:
        create_datetime = datetime.fromtimestamp(create_timestamp)
        formatted_date = create_datetime.strftime('%Y-%m-%d %H:%M:%S')
    else:
        formatted_date = ''
    
    # 确保空值显示为空白而不是'None'
    fullname = fullname if fullname and str(fullname).lower() != 'none' else ''
    customer_phone = customer_phone if customer_phone and str(customer_phone).lower() != 'none' else ''
    address = address if address and str(address).lower() != 'none' else ''
    formatted_date = formatted_date if formatted_date and str(formatted_date).lower() != 'none' else ''
    remark = remark if remark and str(remark).lower() != 'none' else ''
    
    # 替换HTML中的基本订单信息
    html_content = replace_span_content(html_content, '购买单位：', fullname)
    html_content = replace_span_content(html_content, '单据编号：', orders_no)
    html_content = replace_span_content(html_content, '电话：', customer_phone)
    html_content = replace_span_content(html_content, '日期时间：', formatted_date)
    html_content = replace_span_content(html_content, '地址：', address)
    
    # 替换HTML标题为订单号
    html_content = html_content.replace('<title></title>', f'<title>订单 {orders_no}</title>')
    
    # 只有当备注存在时才填入说明字段
    if remark and remark != 'None' and remark != '':
        html_content = replace_span_content(html_content, '说明：', remark)
    
    # 根据self_lifting值填写发货物流字段
    if self_lifting == 1:
        logistics_info = "客户自提"
    else:
        # 将四个物流字段拼接，中间用空格分隔
        logistics_parts = [logistics_name, logistics_shift, logistics_pay_type, logistics_transport_type]
        # 过滤掉空值和None
        logistics_parts = [part for part in logistics_parts if part and str(part).lower() != 'none' and part != '']
        logistics_info = " ".join(logistics_parts) if logistics_parts else ""
    
    html_content = replace_span_content(html_content, '发货物流：', logistics_info)
    
    # 获取产品信息 - 修复获取逻辑以适应API响应结构
    quotelineitems = order_data.get('Quotelineitem', {}).get('data', [])
    total_info = table_header.get('total', order_data.get('total', {}))
    
    # 使用BeautifulSoup解析HTML，准备处理表格
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 找到表格主体
    tbody = soup.find('tbody')
    if tbody:
        # 清空现有表格行
        tbody.clear()
        
        # 添加产品行
        for idx, item in enumerate(quotelineitems, start=1):
            row = soup.new_tag('tr')
            
            # 创建各列
            no_cell = soup.new_tag('td', style='text-align: center;')
            no_cell.string = str(idx)
            
            oe_cell = soup.new_tag('td')
            oe_val = item.get('number', '')
            oe_cell.string = str(oe_val) if oe_val and str(oe_val).lower() != 'none' else ''
            
            name_cell = soup.new_tag('td')
            name_val = item.get('product_name', '')
            name_cell.string = str(name_val) if name_val and str(name_val).lower() != 'none' else ''
            
            brand_cell = soup.new_tag('td')
            brand_val = item.get('brand', '')
            brand_cell.string = str(brand_val) if brand_val and str(brand_val).lower() != 'none' else ''
            
            models_cell = soup.new_tag('td')
            models_val = item.get('models', '')
            models_cell.string = str(models_val) if models_val and str(models_val).lower() != 'none' else ''
            
            quantity_cell = soup.new_tag('td', style='text-align: center;')
            qty_val = item.get('quantity', '')
            quantity_cell.string = str(qty_val) if qty_val and str(qty_val).lower() != 'none' else ''
            
            price_cell = soup.new_tag('td', style='text-align: right;')
            price_val = item.get('price', '')
            price_cell.string = str(price_val) if price_val and str(price_val).lower() != 'none' else ''
            
            amount_cell = soup.new_tag('td', style='text-align: right;')
            amount_val = item.get('total_price', '')
            amount_cell.string = str(amount_val) if amount_val and str(amount_val).lower() != 'none' else ''
            
            # 将单元格添加到行
            row.extend([no_cell, oe_cell, name_cell, brand_cell, 
                       models_cell, quantity_cell, price_cell, amount_cell])
            
            # 将行添加到表格体
            tbody.append(row)
    
    # 更新总计信息
    total_row = soup.find('tfoot').find('tr', class_='total-row') if soup.find('tfoot') else None
    if total_row:
        # 找到总计行中的数量和金额列并更新
        tds = total_row.find_all(['th', 'td'])  # 同时查找th和td元素
        
        # 优先使用从订单详情中获取的总数，否则使用主响应中的值
        total_quantity = total_info.get('quantity') or order_data.get('total_quantity', '0')
        total_price = total_info.get('totalprice') or order_data.get('total_price', '0.00')
        
        # 确保总计信息也不显示'None'
        total_quantity = str(total_quantity) if total_quantity and str(total_quantity).lower() != 'none' else '0'
        total_price = str(total_price) if total_price and str(total_price).lower() != 'none' else '0.00'
        
        # 在总计行中，第2个单元格(td)是数量，第4个单元格(td)是总额
        if len(tds) >= 2:
            # 更新数量 - 第2个单元格 (索引1)
            tds[1].string = total_quantity
        
        if len(tds) >= 4:
            # 更新总金额 - 第4个单元格 (索引3)
            tds[3].string = total_price
        elif len(tds) >= 2:
            # 如果没有专门的金额列，更新最后一个单元格
            tds[-1].string = total_price
    
    return str(soup)

def generate_random_string(length=32):
    """生成指定长度的随机字符串"""
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for i in range(length))

def is_local_environment():
    """判断是否为本地开发环境"""
    current_file_path = Path(__file__).resolve()
    current_path_str = str(current_file_path).lower().replace('\\', '/')  # 将反斜杠替换为正斜杠

    is_local_development = (
        current_path_str.startswith('g:/work/') or          
        current_path_str.startswith('e:/work download/') or  
        os.environ.get('FLASK_ENV') == 'development' or   
        'localhost' in os.environ.get('HOSTNAME', '').lower()
    )
    return is_local_development

def get_server_base_url():
    """获取服务器基础URL"""
    if is_local_environment():
        return "http://localhost:5000"
    else:
        return "http://113.45.176.129:8005"  # 生产环境服务器地址

@get_order_bp.route('/api/order_link', methods=['POST'])
def generate_order_link_api():
    """生成订单链接"""
    try:
        data = request.get_json()
        order_no = data.get('order_no')
        
        if not order_no:
            return jsonify({'code': 1, 'msg': '缺少订单号'}), 400
        
        # 检查是否已存在链接
        existing = get_existing_link_for_order(order_no)
        if existing:
            return jsonify({
                'code': 0,
                'msg': '链接已存在',
                'data': {
                    'link': existing['generated_link'],
                    'random_key': existing['random_key']
                }
            })
        
        # 获取订单ID
        order_id = get_order_id_by_number(order_no)
        
        # 生成随机密钥
        random_key = generate_random_string(32)
        
        # 根据环境生成临时链接
        server_base_url = get_server_base_url()
        generated_link = f"{server_base_url}/order/{random_key}"
        
        # 保存到数据库
        save_order_link_to_db(order_no, generated_link, random_key, order_id)
        
        return jsonify({
            'code': 0,
            'msg': '链接生成成功',
            'data': {
                'link': generated_link,
                'random_key': random_key
            }
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'msg': '生成链接失败'}), 500

# 添加与原版兼容的路由
@get_order_bp.route('/generate_order_link', methods=['POST'])
def generate_order_link_legacy():
    """兼容原版的生成订单链接路由"""
    try:
        data = request.get_json()
        order_no = data.get('order_no')
        
        if not order_no:
            return {"error": "缺少订单号"}, 400
        
        # 检查是否已存在链接
        existing_result = get_existing_link_for_order(order_no)
        if existing_result:
            # 如果已存在，直接返回存在的链接
            link = existing_result['generated_link']
            return {"link": link}
        
        # 获取订单ID
        order_id = get_order_id_by_number(order_no)
        
        # 生成32位随机字符串作为链接
        random_key = generate_random_string(32)
        
        # 根据环境生成链接
        server_base_url = get_server_base_url()
        link = f"{server_base_url}/order/{random_key}"
        
        # 保存订单链接信息到数据库
        save_order_link_to_db(order_no, link, random_key, order_id)
        
        # 返回生成的链接
        return {"link": link}
        
    except Exception as e:
        return {"error": "生成链接失败"}, 500

@get_order_bp.route('/order/<key>')
def show_order(key):
    """显示订单页面，使用异步方式获取订单数据"""
    # 从数据库查询该随机key对应的订单号和订单ID
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        sql = "SELECT order_no, order_id FROM order_links WHERE random_key = %s"
        cursor.execute(sql, (key,))
        result = cursor.fetchone()
        
        if not result:
            return "订单链接无效或已过期", 404
        
        order_no = result['order_no']
        order_id = result['order_id']
    except Exception as e:
        return "订单链接无效或已过期", 404
    finally:
        cursor.close()
        connection.close()
    
    # 返回带加载动画的HTML页面，使用AJAX异步获取订单数据
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>订单 {order_no} - 加载中...</title>
    <style>
        body {{
            font-family: "Microsoft YaHei", Arial, sans-serif;
            margin: 0 5%;
            padding: 8px;
            background-color: #ffffff;
            min-width: 1200px;
        }}

        .invoice-wrapper {{
            max-width: 1000px;
            margin: 20px auto !important;
            background: white;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }}

        .invoice-header {{
            padding: 10px 10%;
            border-bottom: none;
            background-color: #ffffff;
        }}

        .company-info {{
            display: flex;
            justify-content: center;
            align-items: center;
        }}

        .company-logo {{
            display: flex;
            align-items: center;
        }}

        .company-logo img {{
            height: 70px;
            margin-right: 8px;
        }}

        .company-details {{
            text-align: center;
            flex: 1;
            margin-left: 0;
        }}

        .company-details h2 {{
            font-size: 28px;
            margin: 0 0 2px 0;
            color: #333;
        }}

        .company-details p {{
            margin: 0;
            color: #666;
            font-size: 16px;
        }}

        .invoice-details {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
            margin-top: 5px;
            justify-content: center;
            max-width: 800px;
            margin: 5px auto;
            padding: 0;
        }}

        .detail-item {{
            margin-bottom: 2px;
            display: flex;
        }}

        .detail-label {{
            font-weight: bold;
            min-width: 80px;
            font-size: 14px;
        }}

        .invoice-body {{
            padding: 10px 5%;
            display: flex;
            justify-content: center;
        }}

        .invoice-table {{
            width: 90%;
            border-collapse: collapse;
            font-size: 11px;
        }}

        .invoice-table th,
        .invoice-table td {{
            border: 1px solid #333;
            padding: 4px 3px;
            text-align: left;
        }}

        .invoice-table th {{
            background-color: #f2f2f2;
            font-weight: bold;
            color: #333;
        }}

        .total-row {{
            font-weight: bold;
            background-color: #f9f9f9;
        }}

        .invoice-footer {{
            padding: 12px 5%;
        }}

        .signature-section {{
            display: flex;
            justify-content: flex-start;
            margin-bottom: 2px;
            font-size: 14px;
            width: 100%;
            margin: 2px auto;
            text-align: left;
            padding: 0 5%;
        }}

        .signature-box {{
            text-align: left;
            width: 140px;
            padding: 0;
        }}

        /* 隐藏签名确认文字 */
        .signature-line {{
            display: none;
        }}

        .contact-info {{
            width: 90%;
            border-top: none;
            padding-top: 8px;
            margin-top: 2px;
            font-size: 14px;
            padding: 0 5%;
        }}

        .terms {{
            margin: 4px auto;
            padding: 4px 5%;
            background-color: transparent;
            border-radius: 4px;
            font-size: 13px;
            line-height: 1.2;
            border: none;
            width: 90%;
            max-width: 1000px;
        }}
        
        /* 隐藏大写金额 */
        .amount-in-words {{
            display: none;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            
            .invoice-wrapper {{
                box-shadow: none;
                max-width: 100%;
            }}
        }}

        /* 加载动画样式 */
        .loading-container {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            background-color: rgba(245, 245, 245, 0.9);
            z-index: 9999;
            backdrop-filter: blur(2px);
        }}
        
        .spinner {{
            width: 50px;
            height: 50px;
            border: 5px solid rgba(0, 0, 0, 0.1);
            border-left-color: #007bff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 20px;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .loading-text {{
            font-size: 18px;
            color: #333;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="loading-container" id="loadingContainer">
        <div class="spinner"></div>
        <div class="loading-text">正在加载订单数据...</div>
        <p><small>订单号: {order_no}</small></p>
    </div>
    
    <div class="invoice-wrapper" id="invoiceWrapper">
        <!-- 订单内容将通过JavaScript动态填充 -->
    </div>

    <script>
        // 页面加载后异步获取订单数据
        document.addEventListener('DOMContentLoaded', function() {{
            // 构建请求数据
            const requestData = {{
                'order_no': '{order_no}',
                'order_id': '{order_id or ""}',
                'key': '{key}'
            }};
            
            console.log('发送请求数据:', requestData);
            
            fetch('/api/order_preview', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify(requestData)
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.code === 0) {{
                    // 隐藏加载动画和背景
                    document.getElementById('loadingContainer').style.display = 'none';
                    
                    // 显示发票内容
                    const invoiceWrapper = document.getElementById('invoiceWrapper');
                    invoiceWrapper.innerHTML = data.data.html;
                    
                    // 确保图片路径正确
                    const images = invoiceWrapper.querySelectorAll('img');
                    images.forEach(img => {{
                        if(img.src && img.src.includes('frey_logo.png') && !img.src.includes('/static/images/')) {{
                            img.src = '/static/images/frey_logo.png';
                        }}
                        if(img.src && img.src.includes('bbr_logo.png') && !img.src.includes('/static/images/')) {{
                            img.src = '/static/images/bbr_logo.png';
                        }}
                    }});
                    
                    // 滚动到订单内容位置
                    setTimeout(() => {{
                        invoiceWrapper.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                    }}, 100);
                    
                    // 更新页面标题
                    document.title = '订单 {order_no}';
                }} else {{
                    showError(data.msg || '获取订单数据失败');
                }}
            }})
            .catch(error => {{
                console.error('请求错误:', error);
                showError('请求过程中发生错误，请稍后重试');
            }});
        }});
        
        function showError(message) {{
            // 隐藏加载动画
            document.getElementById('loadingContainer').style.display = 'none';
            
            // 显示错误信息
            document.body.innerHTML = `
                <div style="color: red; text-align: center; padding: 50px; font-size: 18px;">
                    <h2>错误</h2>
                    <p>\${{message}}</p>
                    <button onclick="window.history.back()" style="padding: 10px 20px; margin-top: 20px;">返回</button>
                </div>
            `;
        }}
    </script>
</body>
</html>
    """
    
    return html_content

@get_order_bp.route('/order/<key>/frey_logo.png')
def order_frey_logo(key):
    """处理从订单页面发出的 frey_logo.png 请求，重定向到静态文件"""
    from flask import redirect, url_for
    # 重定向到应用的静态文件路由
    return redirect(url_for('static', filename='images/frey_logo.png'))

@get_order_bp.route('/order/<key>/bbr_logo.png')
def order_bbr_logo(key):
    """处理从订单页面发出的 bbr_logo.png 请求，重定向到静态文件"""
    from flask import redirect, url_for
    # 重定向到应用的静态文件路由
    return redirect(url_for('static', filename='images/bbr_logo.png'))

def get_order_id_by_number(order_no):
    """根据订单号获取订单ID"""
    print(f"获取订单ID: 正在请求 mergeOrderList 接口获取订单 {order_no} 的ID")
    order_url = 'https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList'
    params = {'orders_no': order_no, 'page': '1', 'limit': '1'}
    response = requests.get(order_url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and 'list' in data['data']:
            order_list = data['data']['list']['data']
            for order_summary in order_list:
                if order_summary.get('orders_no') == order_no:
                    order_id = order_summary.get('orders_id')
                    print(f"获取订单ID: 成功获取订单 {order_no} 的ID: {order_id}")
                    return order_id
    print(f"获取订单ID: 未能获取订单 {order_no} 的ID")
    return None

# 初始化数据库表（在首次加载时执行）
init_db()