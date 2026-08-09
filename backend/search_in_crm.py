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
            替换号 TEXT COMMENT '替换号',
            purchase_records TEXT COMMENT '采购记录(JSON格式)，与crmapp_compare_summary/crmapp_cart统一'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='CRM OE搜索历史表';
        """
        cursor.execute(create_search_oe_table_sql)

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
            except Exception:
                pass

    except Exception:
        pass
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


def search_crm_by_oe(oe_number, store_code='fsbbr'):
    """根据OE号码搜索CRM系统 - 根据门店代码使用对应的CRM cookie"""
    try:
        # 根据门店代码创建对应的 CRM session
        from config import create_crm_session
        crm_session = create_crm_session(store_code)
        
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
            return {"code": 1, "msg": response_data.get('msg', '未知错误'), "data": response_data}
    except Exception:
        return {"code": 1, "msg": "查询CRM系统失败", "data": []}

def _extract_replace_numbers(display_number):
    """
    从 display_number 数组中提取通用号，用中文逗号分隔
    与 crawl_service.py 中的提取逻辑保持一致
    """
    if not display_number or not isinstance(display_number, list):
        return ''

    numbers = []
    for item in display_number:
        if isinstance(item, dict):
            num = item.get('number', '').strip()
            if num:
                numbers.append(num)

    # 去重并保持顺序
    unique_numbers = list(dict.fromkeys(numbers))
    return '，'.join(unique_numbers)


def parse_supplier_info(supplier_text):
    """
    解析供应商信息，从原始文本中提取日期、供应商名称和单价
    使用与 crawl_service.py 一致的 parse_purchasing_record 解析逻辑

    返回 purchase_records JSON 字符串（与 crmapp_compare_summary/crmapp_cart 统一），
    不再生成竖线分隔的字符串格式。
    """
    import json
    from app.services.procurement_service.procurement_record_service import parse_purchasing_record

    if not supplier_text:
        return None

    parsed_records = parse_purchasing_record(supplier_text)
    return json.dumps(parsed_records, ensure_ascii=False) if parsed_records else None


# ========================================
# 字段映射配置（新增：集中管理，避免硬编码）
# ========================================

# CRM child_item 字段 → 搜索记录字典字段的映射
CRM_FIELD_MAPPING = {
    'number': 'oe',
    'l_name_zh': '物料名称',
    'name': '物料名称',
    'brand_name': '品牌',
    'frey_no': '物料条码',
    'brand_code': '品牌号',
    'cass_oebrand_name': '车型品牌',
    'l_model_zh': '车型',
    'stock': '库存数量',
    'stock_zaitu': '在途数量',
    'purchase_summary': '成本价',
    'company_remark': '内部备注',
}

# 需要转为 int 的字段
CRM_INT_FIELDS = {'库存数量', '在途数量'}

# 需要转为 float 的字段
CRM_FLOAT_FIELDS = {'成本价'}

# 备货表 → 搜索表的同名字段覆盖列表
BEIHUO_OVERRIDE_FIELDS = [
    'oe', '物料名称', '品牌', '物料条码', '品牌号', '车型品牌', '车型',
    '库存数量', '在途数量', '成本价', '内部备注', '标签', '替换号',
    '今日销量', '昨日销量', '本月销量', '近7天销量',
    '近1个月询价量', '近3个月月均询价量',
    '全国近1个月询价量', '全国近3个月月均询价量',
    '库存金额', '成品可卖天数', '预警状态',
    '近12个月月均销量', '近6个月月均销量',
    'purchase_records'
]

# beihuo 特殊字段映射（字段名不一致的情况）
BEIHUO_SPECIAL_MAPPING = {
    '今日销售': '今日销量',  # beihuo 的 "今日销售" → 搜索表的 "今日销量"
}


def _build_crm_record(child_item, username, company):
    """
    从 CRM child_item 构建一条搜索记录字典

    Args:
        child_item: CRM API 返回的 child 字典
        username: 搜索用户
        company: 用户公司/门店

    Returns:
        Dict: 结构化记录字典
    """
    oe = child_item.get('number', '')
    物料条码 = child_item.get('frey_no', '')

    record = {
        'username': username,
        'company': company,
        'oe': oe,
        '物料名称': child_item.get('l_name_zh', '') or child_item.get('name', ''),
        '品牌': child_item.get('brand_name', ''),
        '物料条码': 物料条码,
        '品牌号': child_item.get('brand_code', ''),
        '车型品牌': child_item.get('cass_oebrand_name', ''),
        '车型': child_item.get('l_model_zh', ''),
        '库存数量': int(child_item.get('stock', 0)) if child_item.get('stock', 0) else 0,
        '在途数量': int(child_item.get('stock_zaitu', 0)) if child_item.get('stock_zaitu', 0) else 0,
        '成本价': float(child_item.get('purchase_summary', 0)) if child_item.get('purchase_summary', 0) else 0.0,
        '供应商': None,
        'purchase_records': parse_supplier_info(child_item.get('purchasing_record', '')),
        '内部备注': child_item.get('company_remark', ''),
        '今日销量': None,
        '昨日销量': None,
        '本月销量': None,
        '近7天销量': None,
        '近1个月询价量': None,
        '近3个月月均询价量': None,
        '全国近1个月询价量': None,
        '全国近3个月月均询价量': None,
        '库存金额': None,
        '成品可卖天数': None,
        '预警状态': '',
        '近12个月月均销量': None,
        '近6个月月均销量': None,
        '标签': '',
        '替换号': _extract_replace_numbers(child_item.get('display_number')),
    }
    return record


def parse_crm_response(search_results_list, username, company):
    """
    第1阶段：解析 CRM 返回数据为结构化记录列表

    Args:
        search_results_list: CRM API 返回结果列表
        username: 搜索用户
        company: 用户公司/门店

    Returns:
        Tuple[List[Dict], int]: (记录列表, 原始 item 总数)
    """
    records = []
    total_items = 0

    for result in search_results_list:
        api_data = result.get('data', {})
        if not api_data or not isinstance(api_data, dict):
            continue
        inner_data = api_data.get('data', {})
        if not inner_data or not isinstance(inner_data, dict):
            continue
        data_list = inner_data.get('data', [])
        if not data_list or not isinstance(data_list, list):
            continue

        for item in data_list:
            if isinstance(item, dict) and 'child' in item:
                for child_item in item['child']:
                    total_items += 1
                    records.append(_build_crm_record(child_item, username, company))

    return records, total_items


def fetch_beihuo_data(cursor, barcodes, company):
    """
    第2阶段：按物料条码+company查询备货表

    Args:
        cursor: 数据库游标
        barcodes: 物料条码列表（非空）
        company: 公司/门店代码

    Returns:
        Dict[str, Dict]: key=物料条码, value=备货表整行数据
    """
    if not barcodes:
        return {}

    placeholders = ','.join(['%s'] * len(barcodes))
    sql = f"""
        SELECT * FROM crmapp_beihuo
        WHERE company = %s AND 物料条码 IN ({placeholders})
    """
    cursor.execute(sql, [company] + barcodes)
    rows = cursor.fetchall()

    beihuo_dict = {}
    for row in rows:
        key = row.get('物料条码', '')
        if key:
            beihuo_dict[key] = row
    return beihuo_dict


def merge_with_beihuo(crm_records, beihuo_dict):
    """
    第3阶段：用备货表数据覆盖匹配的 CRM 记录

    Args:
        crm_records: CRM 解析后的记录列表
        beihuo_dict: 备货表字典（key=物料条码）

    Returns:
        Tuple[int, List[str], List[Dict]]:
            (匹配成功数, 未匹配条码列表, 替换明细日志)
    """
    matched_count = 0
    unmatched_barcodes = set()
    replaced_fields_log = []

    for record in crm_records:
        barcode = record['物料条码']
        if not barcode:
            continue

        if barcode in beihuo_dict:
            beihuo_row = beihuo_dict[barcode]
            matched_count += 1
            changed_fields = []

            # 同名字段直接覆盖
            for field in BEIHUO_OVERRIDE_FIELDS:
                beihuo_val = beihuo_row.get(field)
                if beihuo_val is not None and beihuo_val != '':
                    old_val = record.get(field)
                    record[field] = beihuo_val
                    if old_val != beihuo_val:
                        changed_fields.append(field)

            # 特殊字段映射覆盖
            for beihuo_field, search_field in BEIHUO_SPECIAL_MAPPING.items():
                beihuo_val = beihuo_row.get(beihuo_field)
                if beihuo_val is not None and beihuo_val != '':
                    if search_field == '今日销量' and beihuo_field == '今日销售':
                        try:
                            beihuo_val = int(float(beihuo_val))
                        except (ValueError, TypeError):
                            continue
                    old_val = record.get(search_field)
                    record[search_field] = beihuo_val
                    if old_val != beihuo_val:
                        changed_fields.append(f"{search_field}(来自{beihuo_field})")

            if changed_fields:
                replaced_fields_log.append({
                    'oe': record['oe'],
                    'barcode': barcode,
                    'changed_fields': changed_fields
                })
        else:
            unmatched_barcodes.add(barcode)

    return matched_count, list(unmatched_barcodes), replaced_fields_log


def _record_to_tuple(record):
    """将记录字典转为数据库插入所需的 tuple"""
    return (
        record['username'], record['company'], record['oe'],
        record['物料名称'], record['品牌'], record['物料条码'], record['品牌号'],
        record['车型品牌'], record['车型'], record['库存数量'], record['在途数量'],
        record['成本价'], record['供应商'], record['内部备注'],
        record['今日销量'], record['昨日销量'], record['本月销量'], record['近7天销量'],
        record['近1个月询价量'], record['近3个月月均询价量'],
        record['全国近1个月询价量'], record['全国近3个月月均询价量'],
        record['库存金额'], record['成品可卖天数'], record['预警状态'],
        record['近12个月月均销量'], record['近6个月月均销量'],
        record['标签'], record['替换号'], record['purchase_records']
    )


def batch_insert_search_records(cursor, records):
    """
    第4阶段：批量插入替换后的数据到搜索表

    Args:
        cursor: 数据库游标
        records: 记录字典列表

    Returns:
        int: 插入的记录数
    """
    if not records:
        return 0

    all_data = [_record_to_tuple(r) for r in records]

    insert_sql = """
    INSERT INTO crmapp_search_oe_in_crm (
        username, company, oe, 物料名称, 品牌, 物料条码, 品牌号, 车型品牌, 车型, 库存数量, 在途数量, 成本价, 供应商, 内部备注,
        今日销量, 昨日销量, 本月销量, 近7天销量, 近1个月询价量, 近3个月月均询价量, 全国近1个月询价量, 全国近3个月月均询价量,
        库存金额, 成品可卖天数, 预警状态, 近12个月月均销量, 近6个月月均销量, 标签, 替换号, purchase_records
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.executemany(insert_sql, all_data)
    return len(all_data)


def save_search_results_batch(username, company, search_results_list):
    """
    批量保存搜索结果到数据库 - 编排函数

    流程：
        1. parse_crm_response    → 解析 CRM 返回数据
        2. fetch_beihuo_data     → 查询备货表
        3. merge_with_beihuo     → 用备货表数据覆盖匹配记录
        4. batch_insert_search_records → 批量插入搜索表
    """
    from app.utils.logger_config import get_task_logger
    logger = get_task_logger('purchase_history_compare')

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 0. 清理旧数据
        cursor.execute(
            "DELETE FROM crmapp_search_oe_in_crm WHERE username = %s AND company = %s",
            (username, company)
        )

        # 1. 解析 CRM 数据
        crm_records, total_crm_items = parse_crm_response(search_results_list, username, company)
        if not crm_records:
            conn.commit()
            return

        # 2. 查询备货表
        barcodes = list({r['物料条码'] for r in crm_records if r['物料条码']})
        beihuo_dict = fetch_beihuo_data(cursor, barcodes, company)
        logger.info(f"[备货表匹配] CRM解析共{total_crm_items}条, 去重条码{len(barcodes)}个, 备货表命中{len(beihuo_dict)}条")

        # 3. 合并覆盖
        matched_count, unmatched_barcodes, replaced_log = merge_with_beihuo(crm_records, beihuo_dict)
        logger.info(f"[备货表匹配] 匹配成功{matched_count}条, 未匹配{len(unmatched_barcodes)}条(条码数)")
        if unmatched_barcodes:
            logger.info(f"[备货表匹配] 未匹配条码: {unmatched_barcodes}")
        if replaced_log:
            for item in replaced_log[:10]:
                logger.info(f"[备货表替换] OE={item['oe']}, 条码={item['barcode']}, 替换字段={item['changed_fields']}")
            if len(replaced_log) > 10:
                logger.info(f"[备货表替换] ... 还有{len(replaced_log) - 10}条替换记录未展示")

        # 4. 批量插入
        inserted_count = batch_insert_search_records(cursor, crm_records)
        logger.info(f"[保存完成] 成功写入{inserted_count}条记录到搜索表")

        conn.commit()

    except Exception as e:
        logger.exception(f"批量保存搜索结果失败: {e}")
        conn.rollback()
        raise
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

    # 定义单个搜索任务函数，传入 store_code 参数
    def single_search(term, store_code):
        result = search_crm_by_oe(term, store_code)
        return term, result

    # 使用 task_manager 并发执行搜索
    from app.core.task_manager import task_manager
    futures = []
    for term in search_terms:
        future = task_manager.submit(single_search, term, company)
        futures.append((term, future))
    
    # 收集结果
    for term, future in futures:
        try:
            _, result = future.result()
            if result.get('code') == 0:
                search_results.append(result)
            else:
                failed_oes.append({'oe': term, 'error': result.get('msg')})
        except Exception as e:
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

    # 构建SQL查询 - 返回所有字段，确保备货表替换后的数据完整展示
    sql = f"""
        SELECT *
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
    except Exception:
        conn.close()
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