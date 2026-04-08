import re
import requests
import json
from flask import Blueprint, render_template, request, jsonify, session
import pymysql
import os
from urllib.parse import unquote
from functools import partial
from pathlib import Path
from app.utils.search import parse_mixed  # 使用搜索工具包
from app.utils.session_manager import SessionManager  # 使用线程安全的 Session 管理器
from config import create_crm_session  # 使用统一的 CRM session 创建函数
from config.db_config import get_mysql_config  # 使用统一的数据库配置

# 创建蓝图
search_in_crm_bp = Blueprint('search_in_crm', __name__)

# 从主应用获取数据库连接管理函数
def get_db_connection():
    """使用统一的 db_config.py 配置获取数据库连接"""
    config = get_mysql_config()
    # 添加 cursorclass 到配置
    config['cursorclass'] = pymysql.cursors.DictCursor
    connection = pymysql.connect(**config)
    return connection

# ========================================
# 数据库初始化
# ========================================

def init_search_oe_table():
    """初始化CRM OE搜索历史表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 创建搜索历史表
        create_search_oe_table_sql = """
        CREATE TABLE IF NOT EXISTS crmapp_search_oe_in_crm (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL COMMENT '搜索用户',
            company VARCHAR(100) NOT NULL COMMENT '用户公司',
            oe VARCHAR(100) COMMENT 'OE号码',
            物料名称 VARCHAR(255) COMMENT '物料名称',
            品牌 VARCHAR(100) COMMENT '品牌',
            物料条码 VARCHAR(100) COMMENT '物料条码',
            品牌号 VARCHAR(100) COMMENT '品牌号',
            车型品牌 VARCHAR(100) COMMENT '车型品牌',
            车型 TEXT COMMENT '车型',
            库存数量 INT DEFAULT 0 COMMENT '库存数量',
            在途数量 INT DEFAULT 0 COMMENT '在途数量',
            成本价 DECIMAL(10,2) COMMENT '成本价',
            供应商 TEXT COMMENT '供应商',
            内部备注 TEXT COMMENT '内部备注',
            搜索时间 TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '搜索时间',
            今日销量 INT DEFAULT 0 COMMENT '今日销量',
            昨日销量 INT DEFAULT 0 COMMENT '昨日销量',
            本月销量 INT DEFAULT 0 COMMENT '本月销量',
            近7天销量 INT DEFAULT 0 COMMENT '近7天销量',
            近1个月询价量 INT DEFAULT 0 COMMENT '近1个月询价量',
            近3个月月均询价量 INT DEFAULT 0 COMMENT '近3个月月均询价量',
            全国近1个月询价量 INT DEFAULT 0 COMMENT '全国近1个月询价量',
            全国近3个月月均询价量 INT DEFAULT 0 COMMENT '全国近3个月月均询价量',
            库存金额 DECIMAL(12,2) COMMENT '库存金额',
            成品可卖天数 INT DEFAULT 0 COMMENT '成品可卖天数',
            预警状态 VARCHAR(100) COMMENT '预警状态',
            近12个月月均销量 INT DEFAULT 0 COMMENT '近12个月月均销量',
            近6个月月均销量 INT DEFAULT 0 COMMENT '近6个月月均销量',
            标签 VARCHAR(100) COMMENT '标签',
            替换号 TEXT COMMENT '替换号'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='CRM OE搜索历史表';
        """
        cursor.execute(create_search_oe_table_sql)
        print("CRM OE搜索历史表初始化完成")
        
        # 添加索引以提高查询性能
        indexes = [
            ("idx_username_company", "CREATE INDEX idx_username_company ON crmapp_search_oe_in_crm(username, company)"),
            ("idx_oe", "CREATE INDEX idx_oe ON crmapp_search_oe_in_crm(oe)"),
            ("idx_search_time", "CREATE INDEX idx_search_time ON crmapp_search_oe_in_crm(搜索时间)"),
            ("idx_username_company_oe", "CREATE INDEX idx_username_company_oe ON crmapp_search_oe_in_crm(username, company, oe)")
        ]
        
        for index_name, create_index_sql in indexes:
            try:
                cursor.execute(f"SHOW INDEX FROM crmapp_search_oe_in_crm WHERE Key_name = '{index_name}'")
                result = cursor.fetchall()
                if not result:
                    cursor.execute(create_index_sql)
                    print(f"索引 {index_name} 创建完成")
            except Exception as e:
                print(f"创建索引 {index_name} 时出错: {e}")
        
    except Exception as e:
        print(f"初始化CRM OE搜索历史表时出错: {e}")
    finally:
        cursor.close()
        conn.close()

# 初始化数据库表
init_search_oe_table()

# ========================================
# CRM API请求相关 - 使用 SessionManager 管理 session
# ========================================




def get_crm_session():
    """
    获取线程本地的 CRM session
    使用 SessionManager 确保线程安全，避免重复创建 session
    """
    return SessionManager.get_session()


def search_crm_by_oe(oe_number):
    """根据OE号码搜索CRM系统 - 使用 SessionManager 复用 session"""
    try:
        # 获取线程本地的 session（自动复用，避免重复创建）
        crm_session = get_crm_session()
        
        get_params = {
           "number": oe_number 
        }
        
        # 使用 session 发送请求，自动携带认证信息
        response = crm_session.get(
            url='https://crm.gzbbr.com/api/Product.Product/list',
            params=get_params
        )
        response_data = response.json()

        # 检查响应是否成功 - 通常status为200表示成功
        if response_data.get('status') == 200 or response_data.get('msg') == '操作成功':
            return {"code": 0, "msg": "操作成功", "data": response_data}
        else:
            print(f"CRM API返回错误: {response_data}")
            return {"code": 1, "msg": response_data.get('msg', '未知错误'), "data": response_data}
    except Exception as e:
        print(f"查询CRM系统失败: {e}")
        return {"code": 1, "msg": "查询CRM系统失败", "data": []}

def parse_supplier_info(supplier_text):
    """
    解析供应商信息，从原始文本中提取供应商名称和单价
    例如："2026-01-06林建烊,供应商:佛山德孚,采购:2,单价:15.00<br/>2024-09-30周振辉,供应商:广州龙星景丰汽车配件销售有限公司,采购:10,单价:13.63"
    转换为："佛山德孚：15.00 广州龙星景丰汽车配件销售有限公司：13.63"
    """
    if not supplier_text:
        return ""
    
    # 先将 <br/> 替换为换行符，以便统一处理
    supplier_text = supplier_text.replace('<br/>', '\n').replace('<br>', '\n')
    
    # 按换行符分割记录
    records = supplier_text.split('\n')
    supplier_list = []
    
    for record in records:
        record = record.strip()
        if not record:
            continue
        
        # 提取供应商名称 - 供应商: 和 , 之间的内容
        supplier_match = re.search(r'供应商:([^,]+)', record)
        price_match = re.search(r'单价:(\d+\.?\d*)', record)
        
        if supplier_match and price_match:
            supplier_name = supplier_match.group(1).strip()
            price = price_match.group(1).strip()
            
            supplier_list.append(f"{supplier_name}：{price}")
    
    return " ".join(supplier_list)

def save_search_results_batch(username, company, search_results_list):
    """批量保存搜索结果到数据库 - 优化版本"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 删除该用户之前保存的数据
        delete_sql = "DELETE FROM crmapp_search_oe_in_crm WHERE username = %s AND company = %s"
        cursor.execute(delete_sql, (username, company))
        
        # 准备批量插入的数据
        all_data = []
        
        for result in search_results_list:
            # 正确解析API返回的数据结构
            api_data = result.get('data', {})
            if not api_data or not isinstance(api_data, dict):
                continue
                
            inner_data = api_data.get('data', {})
            if not inner_data or not isinstance(inner_data, dict):
                continue
            
            data_list = inner_data.get('data', [])
            if not data_list or not isinstance(data_list, list):
                continue
            
            # 遍历所有返回的数据，提取child中的产品信息
            for item in data_list:
                if isinstance(item, dict) and 'child' in item:
                    for child_item in item['child']:
                        # 映射字段 - 根据实际API响应结构进行提取
                        oe = child_item.get('number', '')
                        物料名称 = child_item.get('l_name_zh', '') or child_item.get('name', '')
                        品牌 = child_item.get('brand_name', '')
                        物料条码 = child_item.get('frey_no', '')
                        品牌号 = child_item.get('brand_code', '')
                        车型品牌 = child_item.get('cass_oebrand_name', '')
                        车型 = child_item.get('l_model_zh', '')
                        库存数量 = int(child_item.get('stock', 0)) if child_item.get('stock', 0) else 0
                        在途数量 = int(child_item.get('stock_zaitu', 0)) if child_item.get('stock_zaitu', 0) else 0
                        成本价 = float(child_item.get('purchase_summary', 0)) if child_item.get('purchase_summary', 0) else 0.0
                        # 解析供应商信息
                        original_supplier = child_item.get('purchasing_record', '')
                        供应商 = parse_supplier_info(original_supplier)
                        内部备注 = child_item.get('company_remark', '')
                        
                        # 获取销量相关数据
                        今日销量 = int(child_item.get('last_day_sales_num', 0)) if child_item.get('last_day_sales_num', 0) else 0
                        近1个月销量 = int(child_item.get('sales_volume1', 0)) if child_item.get('sales_volume1', 0) else 0
                        近3个月月均销量 = int(child_item.get('sales_volume3', 0)) if child_item.get('sales_volume3', 0) else 0
                        近6个月月均销量 = int(child_item.get('sales_volume6', 0)) if child_item.get('sales_volume6', 0) else 0
                        
                        近12个月月均销量 = None 
                        
                        # 其他字段
                        昨日销量 = None  
                        本月销量 = None  
                        近7天销量 = None  
                        近1个月询价量 = None  
                        近3个月月均询价量 = None  
                        全国近1个月询价量 = None  
                        全国近3个月月均询价量 = None  
                        库存金额 = None  
                        成品可卖天数 = None  
                        预警状态 = ''  
                        标签 = ''  
                        # 替换号取number_list的数据
                        替换号 = child_item.get('number_list', '')
                        
                        all_data.append((
                            username, company, oe, 物料名称, 品牌, 物料条码, 品牌号, 车型品牌, 车型, 
                            库存数量, 在途数量, 成本价, 供应商, 内部备注,
                            今日销量, 昨日销量, 本月销量, 近7天销量, 近1个月询价量, 近3个月月均询价量, 
                            全国近1个月询价量, 全国近3个月月均询价量, 库存金额, 成品可卖天数, 预警状态, 
                            近12个月月均销量, 近6个月月均销量, 标签, 替换号
                        ))
        
        # 批量插入数据（如果数据存在）
        if all_data:
            insert_sql = """
            INSERT INTO crmapp_search_oe_in_crm (
                username, company, oe, 物料名称, 品牌, 物料条码, 品牌号, 车型品牌, 车型, 库存数量, 在途数量, 成本价, 供应商, 内部备注,
                今日销量, 昨日销量, 本月销量, 近7天销量, 近1个月询价量, 近3个月月均询价量, 全国近1个月询价量, 全国近3个月月均询价量,
                库存金额, 成品可卖天数, 预警状态, 近12个月月均销量, 近6个月月均销量, 标签, 替换号
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(insert_sql, all_data)
        
        conn.commit()
    except Exception as e:
        print(f"批量保存搜索结果失败: {e}")
        import traceback
        print(f"错误堆栈: {traceback.format_exc()}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def parse_input_oes(input_str):
    """解析输入的OE号码字符串，返回标准化的OE列表"""
    # 使用搜索工具包的混合解析（支持空格、逗号、换行）
    return parse_mixed(input_str)

def search_and_save_crm_data(search_terms, username, company):
    """批量搜索并保存CRM数据 - 使用线程池并发处理API请求"""
    # 使用统一任务管理器并发执行搜索请求
    search_results = []
    failed_oes = []
    
    # 定义单个搜索任务函数
    def single_search(term):
        result = search_crm_by_oe(term)
        return term, result
    
    # 使用 task_manager 并发执行搜索
    from app.core.task_manager import task_manager
    futures = []
    for term in search_terms:
        future = task_manager.submit(single_search, term)
        futures.append((term, future))
    
    # 收集结果
    for term, future in futures:
        try:
            _, result = future.result()
            if result.get('code') == 0:
                search_results.append(result)
            else:
                print(f"查询OE {term} 失败: {result.get('msg')}")
                failed_oes.append({'oe': term, 'error': result.get('msg')})
        except Exception as e:
            print(f"查询OE {term} 时发生异常: {e}")
            failed_oes.append({'oe': term, 'error': str(e)})
    
    success_count = len(search_results)
    
    # 批量保存所有成功的结果
    if search_results:
        save_search_results_batch(username, company, search_results)

    return success_count, failed_oes

# ========================================
# 路由定义
# ========================================

@search_in_crm_bp.route('/search_in_crm')
def search_in_crm():
    # 检查用户是否已登录
    if 'logged_in' not in session:
        return render_template('login.html')
    return render_template('search_in_crm.html')

@search_in_crm_bp.route('/api/search_in_crm', methods=['GET'])
def api_search_in_crm_get():
    """获取搜索历史记录的API"""
    # 分页参数
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 200))
    offset = (page - 1) * limit

    # 排序参数
    field = request.args.get('field', '搜索时间')
    order = request.args.get('order', 'desc')

    # 验证排序字段
    allowed_fields = {
        'oe': 'oe',
        '物料名称': '物料名称',
        '品牌': '品牌',
        '物料条码': '物料条码',
        '品牌号': '品牌号',
        '车型品牌': '车型品牌',
        '车型': '车型',
        '库存数量': '库存数量',
        '在途数量': '在途数量',
        '成本价': '成本价',
        '供应商': '供应商',
        '内部备注': '内部备注',
        '搜索时间': '搜索时间',
    }

    if field not in allowed_fields:
        field = '搜索时间'

    order_clause = f"ORDER BY {allowed_fields[field]} {'ASC' if order == 'asc' else 'DESC'}"

    # 获取当前用户信息
    username = session.get('username', '')
    company = session.get('store', 'fsbbr')

    # 构建查询条件 - 直接查询该用户的数据，无需匹配OE
    where_clause = "WHERE username = %s AND company = %s"
    params = [username, company]

    # 构建SQL查询
    sql = f"""
        SELECT oe, 物料名称, 品牌, 物料条码, 品牌号, 车型品牌, 车型, 库存数量, 在途数量, 成本价, 供应商, 内部备注, 搜索时间, 替换号
        FROM crmapp_search_oe_in_crm
        {where_clause}
        {order_clause}
        LIMIT %s OFFSET %s
    """

    count_sql = f"""
        SELECT COUNT(*) as count
        FROM crmapp_search_oe_in_crm
        {where_clause}
    """

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 获取总数
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()['count']

        # 获取分页数据
        params.extend([limit, offset])
        cursor.execute(sql, params)
        result = cursor.fetchall()

        conn.close()

        return jsonify({
            'code': 0,
            'msg': '',
            'count': total_count,
            'data': result
        })
    except Exception as e:
        conn.close()
        print(f"查询搜索历史失败: {e}")
        return jsonify({
            'code': 1,
            'msg': '查询失败',
            'count': 0,
            'data': []
        })

@search_in_crm_bp.route('/api/search_in_crm', methods=['POST'])
def api_search_in_crm_post():
    """在线搜索CRM系统API并保存结果"""
    data = request.get_json()
    search_oe = data.get('oe', '').strip()
    username = session.get('username', '')
    company = session.get('store', 'fsbbr')

    if not search_oe:
        return jsonify({"code": 1, "msg": "请输入OE号码", "data": []})

    # 解析输入的OE号码，支持多种分隔符
    search_terms = parse_input_oes(search_oe)

    if not search_terms:
        return jsonify({
            'code': 1,
            'msg': '未找到有效的搜索条件',
            'count': 0,
            'data': []
        })

    # 批量搜索并保存结果
    success_count, failed_oes = search_and_save_crm_data(search_terms, username, company)

    # 构建返回消息
    msg_parts = [f'搜索完成，成功处理 {success_count} 个OE号码']
    if failed_oes:
        failed_count = len(failed_oes)
        msg_parts.append(f'，{failed_count} 个OE号码查询失败')
    
    return jsonify({
        'code': 0,
        'msg': ''.join(msg_parts),
        'count': 0,
        'data': [],
        'failed_oes': failed_oes
    })

def register_search_in_crm_routes(app):
    """注册搜索CRM路由"""
    app.register_blueprint(search_in_crm_bp)