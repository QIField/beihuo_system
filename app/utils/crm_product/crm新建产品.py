import pymysql
import requests
from urllib.parse import quote
import os
from datetime import datetime
import re
import time
import threading
import pandas as pd
import json
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection as get_pooled_db_connection  # 使用统一的连接池实现

# 导入统一的 SessionManager
from app.utils.session_manager import SessionManager, get_session

# 设置 session 工厂函数
def _create_crm_session():
    """创建CRM session的工厂函数"""
    session = requests.Session()
    # 设置连接池参数
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=10,
        max_retries=3
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    # 添加认证信息
    session.headers.update(CRM_HEADERS)
    return session

SessionManager.set_session_factory(_create_crm_session)


# 配置==============================================================================
def get_crm_cookies():
    url = "http://113.45.176.129:8001/get_crm_cookies?key=fs"
    payload = {}
    request_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }
    response = requests.request("GET", url, headers=request_headers, data=payload)
    cookies = json.loads(response.text)['cookie']

    return cookies

# 获取cookies
CRM_HEADERS = get_crm_cookies()

# API请求用的headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
    'referer': 'https://crm.gzbbr.com/',
}
# 将认证信息添加到headers中
headers.update(CRM_HEADERS)

# API接口URL配置
API_CONFIG = {
    'get_url': 'https://crm.gzbbr.com/api/Product.Product/get_oe_link',
    'id_url': 'https://crm.gzbbr.com/api/Product.Brand/index',
    'search_url': 'https://crm.gzbbr.com/api/Product.Product/productNameList',
    'upload_url': 'https://crm.gzbbr.com/api/Product.Product/crmProductAdd',
    'search_id_url': 'https://crm.gzbbr.com/api/Product.Product/list',
    'updateview_url': 'https://crm.gzbbr.com/api/Product.Product/updateView'
}

# MySQL数据库配置
MYSQL_CONFIG = {
    'host': '113.45.176.129',
    'port': 3306,
    'user': 'fsbbr_data',
    'password': 'wRCA8AGn3a568f4X',
    'database': 'fsbbr_data',
    'charset': 'utf8mb4',
    'autocommit': True,
    'use_unicode': True
}


# 全局变量
PRODUCT_DF = None
ALIAS_DF = None  # 新增：用于存储别名数据
PROCESSING_RESULTS = []

# 使用统一的 SessionManager
def get_thread_session():
    """
    获取线程本地的session对象
    每个线程有独立的session，避免多线程冲突
    """
    return get_session()

# 保留GLOBAL_SESSION用于单线程环境（向后兼容）
GLOBAL_SESSION = requests.Session()
# 设置连接池参数
adapter = requests.adapters.HTTPAdapter(
    pool_connections=50,
    pool_maxsize=50,
    max_retries=3
)
GLOBAL_SESSION.mount('http://', adapter)
GLOBAL_SESSION.mount('https://', adapter)
GLOBAL_SESSION.headers.update(CRM_HEADERS)


class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.connection = None
        self.connect()
    
    def connect(self):
        """建立数据库连接"""
        try:
            # 使用连接池获取连接
            self.connection = get_pooled_db_connection()
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False
    
    def check_connection(self):
        """检查数据库连接状态"""
        if self.connection is None:
            return False
        try:
            # 尝试执行简单查询验证连接
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def ensure_connection(self):
        """确保数据库连接可用，否则重连"""
        if not self.check_connection():
            print("数据库连接已断开，正在尝试重连...")
            if self.connect():
                print("数据库重连成功")
                return True
            else:
                print("数据库重连失败")
                return False
        return True
    
    def execute_query(self, query, params=None):
        """执行查询，自动处理断连重连"""
        if not self.ensure_connection():
            raise Exception("数据库连接不可用")
        
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()
                return result
        except Exception as e:
            # 如果查询失败，尝试重连后重试
            if self.ensure_connection():
                with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(query, params)
                    result = cursor.fetchall()
                    return result
            else:
                raise e
    
    def execute_update(self, query, params=None):
        """执行更新操作，自动处理断连重连"""
        if not self.ensure_connection():
            raise Exception("数据库连接不可用")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                return cursor.rowcount
        except Exception as e:
            # 如果更新失败，尝试重连后重试
            if self.ensure_connection():
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    self.connection.commit()
                    return cursor.rowcount
            else:
                raise e
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()

def get_db_connection():
    """获取数据库连接管理器实例"""
    return DatabaseManager(MYSQL_CONFIG)


def load_alias_data():
    """全局加载crm可用别名数据"""
    global ALIAS_DF
    try:
        # 使用基于__file__的绝对路径计算
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        alias_file_path = os.path.join(project_root, "static", "excel", "crm可用别名.xlsx")
        
        # 检查文件是否存在
        if not os.path.exists(alias_file_path):
            raise FileNotFoundError(f"找不到别名文件: {alias_file_path}")
            
        ALIAS_DF = pd.read_excel(alias_file_path)
        print("crm可用别名数据加载完成")
    except Exception as e:
        print(f"读取crm可用别名.xlsx时发生错误: {e}")
        ALIAS_DF = None


def load_product_data():
    """全局加载产品名称数据"""
    global PRODUCT_DF
    try:
        # 使用基于__file__的绝对路径计算
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        product_file_path = os.path.join(project_root, "static", "excel", "产品名称.xlsx")
        
        # 检查文件是否存在
        if not os.path.exists(product_file_path):
            raise FileNotFoundError(f"找不到产品名称文件: {product_file_path}")
            
        PRODUCT_DF = pd.read_excel(product_file_path)
        # 清理cxbianma列的空白字符
        PRODUCT_DF['cxbianma'] = PRODUCT_DF['cxbianma'].astype(str).str.strip()
        print("产品名称数据加载完成")
    except Exception as e:
        print(f"读取产品名称.xlsx时发生错误: {e}")
        PRODUCT_DF = None


def find_brand_by_alias(brand):
    """
    根据别名数据查找正确的品牌名称
    当找不到brand_id时，将brand与Excel文件中pp_names列数据匹配，
    如果brand包含在pp_names中，就用对应的pp_name列数据作为新的brand
    """
    global ALIAS_DF
    
    if ALIAS_DF is None:
        return brand  # 如果没有别名数据，返回原始品牌名
    
    # 检查pp_names列，看是否包含当前brand
    if 'pp_names' in ALIAS_DF.columns and 'pp_name' in ALIAS_DF.columns:
        # 遍历pp_names列
        for idx, pp_name_value in enumerate(ALIAS_DF['pp_names']):
            pp_name_str = str(pp_name_value).strip()
            # 分割pp_names字符串，因为它是以逗号分隔的多个别名
            aliases = [alias.strip() for alias in pp_name_str.split(',')]
            for alias in aliases:
                if alias in brand or brand in alias:
                    # 找到匹配项，返回对应的pp_name列数据
                    correct_brand = str(ALIAS_DF.iloc[idx]['pp_name']).strip()
                    print(f"品牌 '{brand}' 匹配到别名 '{alias}'，使用正确品牌名: '{correct_brand}'")
                    return correct_brand
    
    print(f"品牌 '{brand}' 在别名表中未找到匹配项")
    return None  # 没有匹配到任何别名


def get_brand_id_by_name(session, brand, timeout=30):
    """
    根据品牌名称获取品牌ID
    如果找不到，尝试使用别名匹配
    """
    # 首先尝试直接匹配品牌
    id_params = {'l_name_zh': brand}
    id_response = session.get(API_CONFIG['id_url'], params=id_params, headers=headers, timeout=timeout)
    
    if id_response.status_code == 200:
        id_response_data = id_response.json()
        brand_list = id_response_data.get("data", {}).get("list", [])
        
        # 精确匹配l_name_zh与brand
        for brand_item in brand_list:
            if brand_item.get("l_name_zh") == brand:
                return brand_item.get("brand_id")
    
    # 如果直接匹配失败，尝试使用别名
    corrected_brand = find_brand_by_alias(brand)
    if corrected_brand:
        # 使用修正后的品牌名再次尝试
        id_params = {'l_name_zh': corrected_brand}
        id_response = session.get(API_CONFIG['id_url'], params=id_params, headers=headers, timeout=timeout)
        
        if id_response.status_code == 200:
            id_response_data = id_response.json()
            brand_list = id_response_data.get("data", {}).get("list", [])
            
            # 精确匹配l_name_zh与修正后的品牌名
            for brand_item in brand_list:
                if brand_item.get("l_name_zh") == corrected_brand:
                    return brand_item.get("brand_id")
    
    return None


def extract_oe_numbers_from_msg(update_msg):
    """
    检查update_msg是否符合特定格式
    格式要求：必须同时包含"物料所属品牌"、"OE号"和"产品数据不存在,请核查数据"
    """
    if not update_msg:
        return False
    
    # 检查是否同时包含三个关键词
    required_keywords = ["物料所属品牌", "OE号", "产品数据不存在,请核查数据"]
    return all(keyword in update_msg for keyword in required_keywords)


def update_msg_with_processed_result(db_manager, oe_number, brand, result):
    """
    更新数据库中对应OE号和品牌的update_msg列
    """
    try:
        if db_manager:
            # 使用数据库管理器执行更新
            sql = "UPDATE virtual_inventory SET update_msg = %s WHERE oe_code = %s AND brand = %s"
            new_msg = f"OE号【{oe_number}】处理结果：{result}"
            affected_rows = db_manager.execute_update(sql, (new_msg, oe_number, brand))
            print(f"OE号 {oe_number} 和品牌 {brand} 的处理结果已更新到数据库，影响行数: {affected_rows}")
    except Exception as e:
        print(f"更新数据库中OE号 {oe_number} 和品牌 {brand} 的处理结果时出错: {e}")


def search_products_by_oe_list(session, oe_list, timeout=30):
    """
    调用Product.Product/list接口查询产品信息
    参数:
        session: requests session对象
        oe_list: OE号码列表（注意：API期望字符串而非数组）
        timeout: 请求超时时间
    返回:
        API响应的JSON数据
    """
    try:
        # 修正参数格式：使用字符串而非数组
        payload = {
            "numberlist": oe_list[0] if oe_list else "",
            "page": 1,
            "limit": 200
        }
        
        # 发送POST请求
        response = session.post(
            API_CONFIG['search_id_url'], 
            headers=headers, 
            json=payload, 
            timeout=timeout
        )
        
        # 检查响应状态
        if response.status_code == 200:
            result = response.json()
            # 打印查询结果数量
            total_count = result.get('data', {}).get('total', 0)
            print(f"🔍 OE查询 {oe_list[0]} 返回 {total_count} 条结果")
            return result
        else:
            print(f"❌ OE查询 {oe_list[0]} 失败，状态码: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ OE查询 {oe_list[0]} 出错: {e}")
        return None


def update_product_brand_code(session, product_id, brand_code, timeout=30):
    """
    调用Product.Product/updateView接口更新产品brand_code
    参数:
        session: requests session对象
        product_id: 产品ID
        brand_code: 品牌代码
        timeout: 请求超时时间
    返回:
        API响应的JSON数据
    """
    try:
        # 构造请求数据
        payload = {
            "product_id": product_id,
            "brand_code": brand_code
        }
        
        # 发送POST请求
        response = session.post(
            API_CONFIG['updateview_url'], 
            headers=headers, 
            json=payload, 
            timeout=timeout
        )
        
        # 检查响应状态
        if response.status_code == 200:
            return response.json()
        else:
            print(f"updateView API请求失败，状态码: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"调用Product.Product/updateView接口时发生错误: {e}")
        return None


def process_oe_number_with_timeout(session, oe_number, brand, timeout=30):
    """
    带超时和重试机制处理单个OE号码
    """
    global PRODUCT_DF
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 首先获取品牌ID，这是第一步
            brand_id = get_brand_id_by_name(session, brand, timeout)
            
            # 如果没有获取到品牌ID，直接返回错误
            if not brand_id:
                # 更新数据库为"没有匹配到品牌ID"
                print(f"OE号 {oe_number} 解析品牌ID时发生错误，没有匹配到品牌ID")
                return f"失败 - 没有匹配到品牌ID"
            
            # 品牌ID获取成功后，再发送OE号请求
            # 设置请求超时
            get_params = {
               "number": oe_number 
            }
            response = session.get(API_CONFIG['get_url'], params=get_params, headers=headers, timeout=timeout)
            
            # 解析响应JSON
            try:
                response_data = response.json()
                product_type_name = response_data.get("data", {}).get("product_type_name")
                err_msg = response_data.get("data", {}).get("err_msg1")
                product_name = response_data.get("data", {}).get("product_name", "")
                brand_name = response_data.get("data", {}).get("brand_name", "")
                
                # 判断product_type_name是否为"---"
                if (product_type_name == "---" and not (product_name and brand_name)) or err_msg == "此OE未匹配到，请手动输入":    
                    if PRODUCT_DF is not None:
                        # 精确匹配cxbianma列与当前oe_number
                        product_match = PRODUCT_DF[PRODUCT_DF['cxbianma'] == oe_number]
                        
                        if not product_match.empty:
                            # 获取第一条匹配记录的mingcheng
                            product_name = product_match.iloc[0]['mingcheng'].strip()
                            print(f"OE: {oe_number}, Product Name: {product_name}")
                            
                            # 通过API搜索相似产品名称
                            search_params = {'product_name': product_name}
                            search_response = session.get(API_CONFIG['search_url'], params=search_params, headers=headers, timeout=timeout)
                            if search_response.status_code == 200:
                                search_data = search_response.json()
                                name_list = search_data.get("data", {}).get("name_list", [])
                                
                                if name_list and len(name_list) > 0:
                                    # 查找最佳匹配项
                                    best_match = find_best_match_product(product_name, name_list)
                                    if best_match:
                                        matched_product_name = best_match.get("product_name", "")
                                        print(f"OE: {oe_number}, 最佳匹配产品: {matched_product_name}")
                                        upload_res = session.post(API_CONFIG['upload_url'], json={
                                            'l_name_zh' : product_name,
                                            'l_name_zh_store' : matched_product_name,
                                            "brand_id": brand_id,  # 使用已获取的brand_id
                                            "number": oe_number,
                                            'cass_oebrand_name' : '其他',
                                            'l_model_zh' : '  '
                                            }, headers=headers, timeout=timeout)
                                        print(f"OE: {oe_number}, 上传响应内容: {upload_res.text}")
                                        handle_upload_success(session, upload_res, oe_number, brand, product_name)
                                        return f"成功 - {upload_res.text}"
                                    else:
                                        print(f"OE: {oe_number}, 未找到合适的产品名称匹配")
                                        return f"失败 - 未找到合适的产品名称匹配"
                                else:
                                    # API返回空列表，尝试逐步缩短名称重新请求
                                    print(f"OE: {oe_number}, API未返回匹配的产品名称列表，尝试缩短名称")
                                    result = search_product_with_truncation(session, product_name, oe_number, brand_id, brand)
                                    if result:
                                        return f"成功 - 逐步缩短名称处理完成"
                                    else:
                                        return f"失败 - 逐步缩短名称处理失败"
                        else:
                            print(f"OE: {oe_number}, 未在产品名称.xlsx中找到匹配记录")
                            return f"失败 - 未在产品名称.xlsx中找到匹配记录"
                    else:
                        print(f"OE号 {oe_number} 产品数据未加载")
                        return f"失败 - 产品数据未加载"
                        
                else:
                    # 处理非"---"的情况
                    product_name = response_data.get("data", {}).get("product_name", "")
                    brand_name = response_data.get("data", {}).get("brand_name", "")
                    number = response_data.get("data", {}).get("number", "")
                    vehicle_name = response_data.get("data", {}).get("vehicle_name", "")                
                    
                    # 如果所有必要字段都存在
                    if (product_name and 
                        brand_name and 
                        number and 
                        vehicle_name):
                        if PRODUCT_DF is not None:
                            upload_res = session.post(API_CONFIG['upload_url'], json={
                                'l_name_zh' : product_name,
                                'l_name_zh_store' : product_name,
                                "brand_id": brand_id,  # 使用已获取的brand_id
                                "number": oe_number,
                                'cass_oebrand_name' : brand_name,
                                'l_model_zh' : vehicle_name
                                }, headers=headers, timeout=timeout)
                            print(f"OE: {oe_number}, 上传响应内容: {upload_res.text}")
                            return f"成功 - {upload_res.text}"
                        else:
                            print(f"OE号 {oe_number} 产品数据未加载")
                            return f"失败 - 产品数据未加载"
                            
                
                # 只有在完整信息不可用且尚未处理时才执行这部分
                if (brand_name and number and vehicle_name):
                    if PRODUCT_DF is not None:
                        # 精确匹配cxbianma列与当前oe_number
                        product_match = PRODUCT_DF[PRODUCT_DF['cxbianma'] == oe_number]
                    
                        if not product_match.empty:
                            # 获取第一条匹配记录的mingcheng
                            product_name = product_match.iloc[0]['mingcheng'].strip()
                            print(f"OE: {oe_number}, Product Name: {product_name}")
                            
                            # 通过API搜索相似产品名称
                            search_params = {'product_name': product_name}
                            search_response = session.get(API_CONFIG['search_url'], params=search_params, headers=headers, timeout=timeout)
                            if search_response.status_code == 200:
                                search_data = search_response.json()
                                name_list = search_data.get("data", {}).get("name_list", [])
                                
                                if name_list and len(name_list) > 0:
                                    # 查找最佳匹配项
                                    best_match = find_best_match_product(product_name, name_list)
                                    if best_match:
                                        matched_product_name = best_match.get("product_name", "")
                                        print(f"OE: {oe_number}, 最佳匹配产品: {matched_product_name}")
                                        upload_res = session.post(API_CONFIG['upload_url'], json={
                                            'l_name_zh' : product_name,
                                            'l_name_zh_store' : matched_product_name,
                                            "brand_id": brand_id,  # 使用已获取的brand_id
                                            "number": oe_number,
                                            'cass_oebrand_name' : brand_name,
                                            'l_model_zh' : vehicle_name
                                            }, headers=headers, timeout=timeout)
                                        print(f"OE: {oe_number}, 上传响应内容: {upload_res.text}")
                                        handle_upload_success(session, upload_res, oe_number, brand, product_name)
                                        return f"成功 - {upload_res.text}"
                                    else:
                                        print(f"OE: {oe_number}, 未找到合适的产品名称匹配")
                                        return f"失败 - 未找到合适的产品名称匹配"
                                else:
                                    # API返回空列表，尝试逐步缩短名称重新请求
                                    print(f"OE: {oe_number}, API未返回匹配的产品名称列表，尝试缩短名称")
                                    result = search_product_with_truncation(session, product_name, oe_number, brand_id, brand)
                                    if result:
                                        return f"成功 - 逐步缩短名称处理完成"
                                    else:
                                        return f"失败 - 逐步缩短名称处理失败"
                        else:
                            print(f"OE: {oe_number}, 未在产品名称.xlsx中找到匹配记录")
                            return f"失败 - 未在产品名称.xlsx中找到匹配记录"
                    else:
                        print(f"OE号 {oe_number} 产品数据未加载")
                        return f"失败 - 产品数据未加载"
                else:
                    return "跳过"
            except Exception as e:
                print(f"处理 OE号 {oe_number} 时解析JSON发生错误: {e}")
                return f"解析JSON时发生错误: {e}"
        except requests.exceptions.Timeout:
            print(f"OE号 {oe_number} 请求超时，重试第 {retry_count + 1} 次...")
            retry_count += 1
            time.sleep(2)  # 等待2秒后重试
        except requests.exceptions.RequestException as e:
            print(f"OE号 {oe_number} 请求发生错误: {e}")
            retry_count += 1
            time.sleep(2)  # 等待2秒后重试
        except Exception as e:
            print(f"处理 OE号 {oe_number} 时发生未知错误: {e}")
            return f"发生未知错误: {e}"
    
    # 重试次数用完
    print(f"OE号 {oe_number} 经过 {max_retries} 次重试后仍失败")
    return f"重试次数用完 - 经过 {max_retries} 次重试后仍失败"


def get_current_day_time_range():
    """
    获取当前日期13:00到第二天13:00的时间范围
    例如：今天是16号，则返回16号13:00到17号13:00的时间范围
    """
    now = datetime.now()
    # 当天13:00
    start_time = now.replace(hour=13, minute=0, second=0, microsecond=0)
    
    # 如果当前时间小于当天13:00，则使用前一天13:00到当天13:00
    if now < start_time:
        start_time = start_time - timedelta(days=1)
    
    # 结束时间为start_time + 24小时
    end_time = start_time + timedelta(hours=24)
    
    return start_time.strftime('%Y-%m-%d %H:%M:%S'), end_time.strftime('%Y-%m-%d %H:%M:%S')

def load_data_from_mysql():
    """
    从MySQL数据库读取virtual_inventory表数据
    返回包含oe_code、brand、update_msg和fetch_time列的数据
    筛选条件：update_msg符合特定格式 且 fetch_time在指定时间范围内
    """
    db_manager = get_db_connection()
    try:
        if db_manager is None:
            raise Exception("数据库连接失败")
        
        # 获取时间范围
        start_time, end_time = get_current_day_time_range()
        print(f"时间筛选范围: {start_time} 到 {end_time}")
        
        # 修改SQL查询，添加fetch_time时间范围筛选
        query = """
        SELECT oe_code, brand, update_msg, fetch_time 
        FROM virtual_inventory 
        WHERE update_msg IS NOT NULL 
          AND update_msg != '' 
          AND fetch_time BETWEEN %s AND %s
        """
        results = db_manager.execute_query(query, (start_time, end_time))
        
        print(f"从数据库读取到 {len(results)} 条记录（已按时间范围筛选）")
        
        # 筛选符合特定格式的数据
        filtered_results = []
        for row in results:
            if extract_oe_numbers_from_msg(row['update_msg']):
                filtered_results.append({
                    'oe_code': row['oe_code'],
                    'brand': row['brand'],
                    'update_msg': row['update_msg'],
                    'fetch_time': row['fetch_time']  # 添加fetch_time信息
                })
        
        print(f"筛选出 {len(filtered_results)} 条符合特定格式和时间范围的记录")
        return filtered_results
    except Exception as e:
        print(f"从数据库读取数据时发生错误: {e}")
        return []
    finally:
        db_manager.close()


def find_best_match_product(product_name, name_list):
    """
    查找最佳匹配的产品名称
    """
    if not name_list:
        return None
    
    # 1. 精确匹配 - 找到任何一个精确匹配就返回
    for item in name_list:
        item_name = item.get("product_name", "").strip()
        if item_name == product_name:
            return item
    
    # 2. 模糊匹配 - 找到任何一个模糊匹配就返回
    for item in name_list:
        item_name = item.get("product_name", "").strip()
        if product_name in item_name:
            return item
        elif item_name in product_name:
            return item
    
    # 3. 逐步缩短名称进行匹配 - 找到任何一个部分匹配就返回
    search_name = product_name
    while len(search_name) > 1:
        for item in name_list:
            item_name = item.get("product_name", "").strip()
            if search_name in item_name:
                return item
            elif item_name in search_name:
                return item
        # 删除最后一个字符
        search_name = search_name[:-1]
    
    # 如果都没找到，返回第一个结果
    first_item = name_list[0] if name_list else None
    return first_item


def find_matching_product_id(response_data, oe_number, brand):
    """
    从返回的数据中查找匹配的产品ID
    匹配条件:
    1. number 等于 oe_number
    2. cass_oebrand_name 等于 "其他"
    3. brand_name 等于指定品牌
    """
    try:
        products = response_data.get("data", {}).get("data", [])
        if not products:
            return None
            
        # 遍历所有产品数据寻找匹配项
        for product_group in products:
            children = product_group.get("child", [])
            for child in children:
                number = child.get("number", "")
                cass_oebrand_name = child.get("cass_oebrand_name", "")
                brand_name = child.get("brand_name", "")
                
                # 检查是否匹配所有条件
                if (number == oe_number and 
                    cass_oebrand_name == "其他" and 
                    brand_name == brand):
                    return child.get("product_id")
                    
        return None
    except Exception as e:
        print(f"查找匹配产品ID时出错: {e}")
        return None


def find_matching_product_id_simple(response_data, oe_number, brand):
    """
    从返回的数据中查找匹配的产品ID（严格精准匹配版）
    匹配条件:
    1. original_number 必须等于 oe_number（严格匹配）
    2. brand_name 必须等于指定品牌（严格匹配）
    两者必须同时满足才算匹配成功
    """
    try:
        products = response_data.get("data", {}).get("data", [])
        if not products:
            return None
            
        # 严格匹配：必须同时满足number和brand都精准匹配
        for product_group in products:
            children = product_group.get("child", [])
            for child in children:
                original_number = child.get("original_number", "")
                brand_name = child.get("brand_name", "")
                product_id = child.get("product_id", "")
                
                # 严格双重匹配：number和brand都必须完全相等
                if original_number == oe_number and brand_name == brand:
                    return product_id
        
        # 匹配失败
        return None
            
    except Exception as e:
        print(f"查找匹配产品ID时出错: {e}")
        return None


def search_product_with_truncation(session, product_name, oe_number, brand_id, brand):
    """逐步缩短产品名称并尝试搜索"""
    search_name = product_name
    while len(search_name) > 1:
        search_params = {'product_name': search_name}
        try:
            search_response = session.get(API_CONFIG['search_url'], params=search_params, headers=headers)
            if search_response.status_code == 200:
                search_data = search_response.json()
                retry_name_list = search_data.get("data", {}).get("name_list", [])
                if retry_name_list and len(retry_name_list) > 0:
                    best_match = find_best_match_product(search_name, retry_name_list)
                    if best_match:
                        matched_product_name = best_match.get("product_name", "")
                        print(f"OE: {oe_number}, 缩短匹配产品: {matched_product_name} (原名:'{product_name}', 匹配:'{search_name}')")
                        # 执行上传操作
                        upload_res = session.post(API_CONFIG['upload_url'], json={
                            'l_name_zh': product_name,
                            'l_name_zh_store': matched_product_name,
                            "brand_id": brand_id,  # 使用已获取的brand_id
                            "number": oe_number,
                            'cass_oebrand_name': '其他',
                            'l_model_zh': '  '
                        }, headers=headers)
                        print(f"OE: {oe_number}, 上传响应内容: {upload_res.text}")
                        # 检查响应状态，201表示成功（即使是字段缺失也视为成功）
                        try:
                            res_json = upload_res.json()
                            if res_json.get("status") == 201:
                                print(f"OE: {oe_number}, 上传成功（状态码201）")
                                # 查询产品ID
                                search_id_res = session.post(API_CONFIG['search_id_url'], headers=headers, json={'numberlist': oe_number})
                                
                                # 从返回结果中查找匹配的product_id
                                product_id = find_matching_product_id(search_id_res.json(), oe_number, brand)
                                if product_id:
                                    print(f"OE: {oe_number}, 找到匹配的product_id: {product_id}")
                                    # 使用找到的product_id调用updateview接口
                                    updateview_res = session.post(API_CONFIG['updateview_url'], headers=headers, json={
                                        "product_id": product_id,
                                        "l_name_zh_store": product_name
                                    })
                                    print(f"OE: {oe_number}, updateView响应: {updateview_res.text}")
                                else:
                                    print(f"OE: {oe_number}, 未找到匹配的product_id")
                        except Exception as e:
                            print(f"OE: {oe_number}, 处理上传响应时发生错误: {e}")
                        return best_match
        except Exception as e:
            print(f"OE: {oe_number}, 缩短名称请求时发生错误: {e}")
        # 删除最后一个字符
        search_name = search_name[:-1]
    
    print(f"OE: {oe_number}, 未找到合适的产品名称匹配")
    return None


def handle_upload_success(session, upload_res, oe_number, brand, product_name):
    """处理上传成功后的操作"""
    try:
        res_json = upload_res.json()
        if res_json.get("status") == 201:
            print(f"OE: {oe_number}, 上传成功（状态码201）")
            # 查询产品ID
            search_id_res = session.post(API_CONFIG['search_id_url'], headers=headers, json={'numberlist': oe_number})
            
            # 从返回结果中查找匹配的product_id
            product_id = find_matching_product_id(search_id_res.json(), oe_number, brand)
            if product_id:
                print(f"OE: {oe_number}, 找到匹配的product_id: {product_id}")
                # 使用找到的product_id调用updateview接口
                updateview_res = session.post(API_CONFIG['updateview_url'], headers=headers, json={
                    "product_id": product_id,
                    "l_name_zh_store": product_name
                })
                print(f"OE: {oe_number}, updateView响应: {updateview_res.text}")
            else:
                print(f"OE: {oe_number}, 未找到匹配的product_id")
    except Exception as e:
        print(f"OE: {oe_number}, 处理上传响应时发生错误: {e}")


def save_processing_result(oe_number, status, details=""):
    """暂存处理结果，定期批量写入"""
    global PROCESSING_RESULTS
    result_entry = {
        "oe": oe_number,
        "处理时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "状态": status,
        "详情": details
    }
    PROCESSING_RESULTS.append(result_entry)
    
    # 每处理100条记录写入一次文件
    if len(PROCESSING_RESULTS) >= 100:
        flush_results()


def flush_results():
    """将暂存的结果写入文件"""
    global PROCESSING_RESULTS
    if PROCESSING_RESULTS:
        print(f"正在将 {len(PROCESSING_RESULTS)} 条处理结果写入文件")
        PROCESSING_RESULTS = []  # 清空暂存数据


def make_api_request(data, max_workers=10):  # 降低并发数以减少超时风险
    """
    并发处理数据上传请求
    
    Args:
        data: 要处理的数据
        max_workers: 最大并发线程数
    """
    # 获取数据库连接用于更新结果
    conn = get_db_connection()
    if conn is None:
        print("无法建立数据库连接，无法更新处理结果")
        return
    
    # 使用统一任务管理器并发处理
    from app.core.task_manager import task_manager
    
    # 提交任务
    futures = []
    for row in data:
        future = task_manager.submit(process_single_row_with_db_update, conn, row)
        futures.append((future, row))
    
    # 处理完成的任务
    for future, row in futures:
        oe_number = str(row['oe_code']).strip()
        try:
            result = future.result()
            print(f"OE: {oe_number} 处理完成: {result}")
        except Exception as e:
            print(f"OE: {oe_number} 处理时发生异常: {e}")
    
    conn.close()


def process_single_row_with_db_update(db_manager, row):
    """
    处理单行数据并更新数据库中的update_msg列
    """
    global PRODUCT_DF
    
    oe_number = str(row['oe_code']).strip()
    brand = row.get('brand', '')
    
    # 使用线程本地的session，避免多线程冲突
    session = get_thread_session()
    
    # 处理OE号
    result = process_oe_number_with_timeout(session, oe_number, brand)
    
    # 更新数据库中的update_msg列
    update_msg_with_processed_result(db_manager, oe_number, brand, result)
    
    return result


# 主程序==========================================================================
def main():
    try:
        # 加载别名数据
        load_alias_data()
        
        # 加载产品数据
        load_product_data()
        
        # 从MySQL数据库读取包含update_msg的数据
        data = load_data_from_mysql()
        
        # 检查数据是否为空
        if not data:
            print("从数据库读取的数据为空，程序退出")
            return
        
        # 打印要处理的前五条数据的oe、brand和update_msg
        for i, row in enumerate(data[:5], 1):
            print(f"即将处理 - 记录 {i}: oe_code={row['oe_code']}, brand={row['brand']}, update_msg={row['update_msg']}")
        
        # 使用线程池并发处理数据库数据
        print(f"\n开始并发处理数据库中的 {len(data)} 条记录...")
        
        # 准备处理数据
        processing_items = []
        for row in data:
            processing_items.append({
                'oe_code': row['oe_code'],
                'brand': row['brand'],
                'update_msg': row['update_msg']
            })
        
        # 获取数据库连接管理器
        db_manager = get_db_connection()
        if not db_manager:
            print("无法建立数据库连接，程序退出")
            return
        
        try:
            # 使用统一任务管理器并发处理
            from app.core.task_manager import task_manager
            
            completed_count = 0
            
            # 提交所有任务
            futures = []
            for item in processing_items:
                future = task_manager.submit(process_database_item_batch, db_manager, item)
                futures.append((future, item))
            
            # 收集结果
            for future, item in futures:
                try:
                    result = future.result()
                    completed_count += 1
                    print(f"数据库处理进度: {completed_count}/{len(processing_items)} - OE: {item['oe_code']}, 结果: {result}")
                except Exception as e:
                    print(f"数据库处理OE: {item['oe_code']} 时发生异常: {e}")
                    completed_count += 1
        
        finally:
            db_manager.close()
        
        print(f"\n数据库模式并发处理完成，共处理 {len(data)} 条记录")
        
    except Exception as e:
        print(f"主程序执行时发生错误: {e}")
    finally:
        # 确保最后的数据也被写入
        flush_results()


def process_database_item_batch(db_manager, item):
    """
    批量处理数据库单个项目
    """
    global PRODUCT_DF
    
    oe_number = str(item['oe_code']).strip()
    brand = item['brand']
    
    # 使用线程本地的session，避免多线程冲突
    session = get_thread_session()
    
    # 处理OE号
    result = process_oe_number_with_timeout(session, oe_number, brand)
    
    # 更新数据库中的update_msg列
    update_msg_with_processed_result(db_manager, oe_number, brand, result)
    
    return result


def identify_columns(df):
    """
    自动识别Excel中的关键列
    oe列：oe, OE, 物料条码, barcode
    brand列：brand, 品牌, 品牌名称
    """
    oe_columns = ['oe', 'OE', 'barcode']
    brand_columns = ['brand', '品牌']
    
    oe_col = None
    brand_col = None
    
    # 转换列名为小写进行匹配
    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))
    
    # 查找oe列
    for oe_key in oe_columns:
        oe_key_lower = oe_key.lower()
        if oe_key_lower in columns_lower:
            oe_col = column_mapping[oe_key_lower]
            break
    
    # 查找brand列
    for brand_key in brand_columns:
        brand_key_lower = brand_key.lower()
        if brand_key_lower in columns_lower:
            brand_col = column_mapping[brand_key_lower]
            break
    
    if oe_col is None:
        raise ValueError("未找到oe列，请确保列名为：oe, OE, 物料条码, barcode之一")
    
    if brand_col is None:
        raise ValueError("未找到brand列，请确保列名为：brand, 品牌, 品牌名称之一")
    
    return oe_col, brand_col


def identify_columns_extended(df):
    """
    扩展的列识别函数，支持识别brand_code列
    oe列：oe, OE, 物料条码, barcode
    brand列：brand, 品牌, 品牌名称
    brand_code列：brand_code, 条码, 物料条码
    """
    oe_columns = ['oe', 'OE', 'barcode']
    brand_columns = ['brand', '品牌']
    brand_code_columns = ['brand_code', '条码', '物料条码']
    
    oe_col = None
    brand_col = None
    brand_code_col = None
    
    # 转换列名为小写进行匹配
    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))
    
    # 查找oe列
    for oe_key in oe_columns:
        oe_key_lower = oe_key.lower()
        if oe_key_lower in columns_lower:
            oe_col = column_mapping[oe_key_lower]
            break
    
    # 查找brand列
    for brand_key in brand_columns:
        brand_key_lower = brand_key.lower()
        if brand_key_lower in columns_lower:
            brand_col = column_mapping[brand_key_lower]
            break
    
    # 查找brand_code列
    for brand_code_key in brand_code_columns:
        brand_code_key_lower = brand_code_key.lower()
        if brand_code_key_lower in columns_lower:
            brand_code_col = column_mapping[brand_code_key_lower]
            break
    
    if oe_col is None:
        raise ValueError("未找到oe列，请确保列名为：oe, OE, 物料条码, barcode之一")
    
    if brand_col is None:
        raise ValueError("未找到brand列，请确保列名为：brand, 品牌, 品牌名称之一")
    
    # brand_code列是可选的
    return oe_col, brand_col, brand_code_col


def add_result_column(df, results_dict, oe_col):
    """
    在DataFrame末尾添加"新建结果"列
    """
    # 创建结果列，初始化为空字符串
    df['新建结果'] = ''
    
    # 根据oe_code填充结果
    for index, row in df.iterrows():
        oe_code = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        if oe_code in results_dict:
            df.at[index, '新建结果'] = results_dict[oe_code]
    
    return df


def filter_sheets_by_mode(all_sheets, mode):
    """
    根据处理模式筛选符合条件的工作表
    """
    valid_sheets = {}
    for sheet_name, df in all_sheets.items():
        try:
            if mode == 'two_column':
                # 检查是否符合两列模式
                oe_col, brand_col = identify_columns(df)
                valid_sheets[sheet_name] = {
                    'df': df,
                    'columns': (oe_col, brand_col)
                }
                print(f"工作表 '{sheet_name}' 符合两列模式: oe列={oe_col}, brand列={brand_col}")
            else:  # three_column
                # 检查是否符合三列模式
                oe_col, brand_col, brand_code_col = identify_columns_extended(df)
                if brand_code_col:  # 必须有brand_code列
                    valid_sheets[sheet_name] = {
                        'df': df,
                        'columns': (oe_col, brand_col, brand_code_col)
                    }
                    print(f"工作表 '{sheet_name}' 符合三列模式: oe列={oe_col}, brand列={brand_col}, brand_code列={brand_code_col}")
                else:
                    print(f"工作表 '{sheet_name}' 不符合三列模式：缺少brand_code列")
        except ValueError as e:
            print(f"工作表 '{sheet_name}' 不符合{mode}模式要求: {e}")
            continue
    
    return valid_sheets


def process_single_sheet(session, sheet_info, mode):
    """
    处理单个工作表
    """
    df = sheet_info['df']
    columns = sheet_info['columns']
    
    if mode == 'two_column':
        oe_col, brand_col = columns
    else:
        oe_col, brand_col, brand_code_col = columns
    
    results_dict = {}
    
    # 处理每一行数据
    for index, row in df.iterrows():
        oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
        
        if not oe_number or not brand:
            results_dict[oe_number] = "失败 - OE号或品牌为空"
            continue
        
        # 处理单个OE号
        result = process_oe_number_with_timeout(session, oe_number, brand)
        results_dict[oe_number] = result
        print(f"工作表处理进度: {index + 1}/{len(df)} - OE: {oe_number}, 结果: {result}")
        
        # 三列模式额外处理
        if mode == 'three_column' and result.startswith("成功"):
            brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
            if brand_code:
                # 获取product_id
                search_result = search_products_by_oe_list(session, [oe_number])
                if search_result:
                    product_id = find_matching_product_id_simple(search_result, oe_number, brand)
                    if product_id:
                        # 更新brand_code
                        update_result = update_product_brand_code(session, product_id, brand_code)
                        result += f" | brand_code更新: {update_result}"
                        print(f"OE: {oe_number} brand_code更新结果: {update_result}")
                    else:
                        result += " | 未找到匹配的product_id"
                        print(f"OE: {oe_number} 未找到匹配的product_id")
                else:
                    result += " | 查询产品列表失败"
                    print(f"OE: {oe_number} 查询产品列表失败")
            elif not brand_code:
                result += " | 无brand_code数据"
    
    return results_dict


def process_excel_two_column_mode(file_path):
    """
    两列模式处理函数：使用线程池并发处理Excel所有工作表
    """
    global PRODUCT_DF, ALIAS_DF
    
    try:
        # 读取Excel所有工作表
        print(f"正在读取文件: {file_path}")
        all_sheets = pd.read_excel(file_path, sheet_name=None) if file_path.endswith(('.xlsx', '.xls')) else None
        
        if all_sheets is None:
            # CSV文件处理（单个工作表）
            df = pd.read_csv(file_path)
            all_sheets = {'Sheet1': df}
            print("CSV文件按单个工作表处理")
        else:
            print(f"读取到 {len(all_sheets)} 个工作表: {list(all_sheets.keys())}")
        
        # 筛选符合两列模式的工作表
        valid_sheets = filter_sheets_by_mode(all_sheets, 'two_column')
        
        if not valid_sheets:
            raise ValueError("没有找到符合两列模式要求的工作表")
        
        print(f"找到 {len(valid_sheets)} 个符合条件的工作表")
        
        # 加载必要的数据
        if PRODUCT_DF is None:
            load_product_data()
        if ALIAS_DF is None:
            load_alias_data()
        
        # 注意：不在主线程创建session，每个工作线程会使用自己的session
        
        # 处理每个符合条件的工作表（使用线程池并发处理）
        for sheet_name, sheet_info in valid_sheets.items():
            print(f"\n开始并发处理工作表: {sheet_name}")
            df = sheet_info['df']
            oe_col, brand_col = sheet_info['columns']
            
            # 准备处理数据
            processing_items = []
            for index, row in df.iterrows():
                oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
                brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
                if oe_number and brand:
                    processing_items.append({
                        'index': index,
                        'oe_number': oe_number,
                        'brand': brand,
                        'row': row
                    })
            
            # 使用统一任务管理器并发处理
            from app.core.task_manager import task_manager
            
            results_dict = {}
            
            # 提交所有任务（不传递session，每个线程使用自己的session）
            futures = []
            for item in processing_items:
                future = task_manager.submit(process_single_item_batch, item)
                futures.append((future, item))
            
            # 收集结果
            completed_count = 0
            for future, item in futures:
                try:
                    result = future.result()
                    results_dict[item['oe_number']] = result
                    completed_count += 1
                    print(f"工作表 {sheet_name} 处理进度: {completed_count}/{len(processing_items)} - OE: {item['oe_number']}, 结果: {result}")
                except Exception as e:
                    print(f"工作表 {sheet_name} 处理OE: {item['oe_number']} 时发生异常: {e}")
                    results_dict[item['oe_number']] = f"失败 - {str(e)}"
            
            # 添加结果列到原工作表
            df['新建结果'] = ''
            for index, row in df.iterrows():
                oe_code = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
                if oe_code in results_dict:
                    df.at[index, '新建结果'] = results_dict[oe_code]
            
            # 更新原工作表数据
            all_sheets[sheet_name] = df
            print(f"工作表 {sheet_name} 并发处理完成")
        
        # 保存处理后的文件（保持原有工作表结构）
        base_name = os.path.splitext(file_path)[0]
        output_file_path = base_name + '_处理结果.xlsx'
        
        # 保存Excel文件（多工作表）
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            for sheet_name, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"两列模式并发处理完成，结果文件保存至: {output_file_path}")
        return output_file_path
        
    except Exception as e:
        print(f"处理Excel文件时发生错误: {e}")
        raise e


def process_excel_three_column_mode(file_path):
    """
    三列模式处理函数：使用线程池并发处理Excel所有工作表
    """
    global PRODUCT_DF, ALIAS_DF, GLOBAL_SESSION
    
    try:
        # 读取Excel所有工作表
        print(f"正在读取文件: {file_path}")
        all_sheets = pd.read_excel(file_path, sheet_name=None) if file_path.endswith(('.xlsx', '.xls')) else None
        
        if all_sheets is None:
            # CSV文件处理（单个工作表）
            df = pd.read_csv(file_path)
            all_sheets = {'Sheet1': df}
            print("CSV文件按单个工作表处理")
        else:
            print(f"读取到 {len(all_sheets)} 个工作表: {list(all_sheets.keys())}")
        
        # 筛选符合三列模式的工作表
        valid_sheets = filter_sheets_by_mode(all_sheets, 'three_column')
        
        if not valid_sheets:
            raise ValueError("没有找到符合三列模式要求的工作表")
        
        print(f"找到 {len(valid_sheets)} 个符合条件的工作表")
        
        # 加载必要的数据
        if PRODUCT_DF is None:
            load_product_data()
        if ALIAS_DF is None:
            load_alias_data()
        
        # 使用全局session
        session = GLOBAL_SESSION
        
        # 处理每个符合条件的工作表（使用线程池并发处理）
        for sheet_name, sheet_info in valid_sheets.items():
            print(f"\n开始并发处理工作表: {sheet_name}")
            df = sheet_info['df']
            oe_col, brand_col, brand_code_col = sheet_info['columns']
            
            # 准备处理数据
            processing_items = []
            for index, row in df.iterrows():
                oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
                brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
                brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else '' if 'brand_code_col' in locals() else ''
                if oe_number and brand:
                    processing_items.append({
                        'index': index,
                        'oe_number': oe_number,
                        'brand': brand,
                        'brand_code': brand_code,
                        'row': row,
                        'mode': 'three_column'
                    })
            
            # 使用统一任务管理器并发处理
            from app.core.task_manager import task_manager
            
            results_dict = {}
            
            # 提交所有任务
            futures = []
            for item in processing_items:
                future = task_manager.submit(process_single_item_batch, session, item)
                futures.append((future, item))
            
            # 收集结果
            completed_count = 0
            for future, item in futures:
                try:
                    result = future.result()
                    results_dict[item['oe_number']] = result
                    completed_count += 1
                    print(f"工作表 {sheet_name} 处理进度: {completed_count}/{len(processing_items)} - OE: {item['oe_number']}, 结果: {result}")
                except Exception as e:
                    print(f"工作表 {sheet_name} 处理OE: {item['oe_number']} 时发生异常: {e}")
                    results_dict[item['oe_number']] = f"失败 - {str(e)}"
            
            # 添加结果列到原工作表
            df['新建结果'] = ''
            for index, row in df.iterrows():
                oe_code = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
                if oe_code in results_dict:
                    df.at[index, '新建结果'] = results_dict[oe_code]
            
            # 更新原工作表数据
            all_sheets[sheet_name] = df
            print(f"工作表 {sheet_name} 并发处理完成")
        
        # 保存处理后的文件（保持原有工作表结构）
        base_name = os.path.splitext(file_path)[0]
        output_file_path = base_name + '_处理结果.xlsx'
        
        # 保存Excel文件（多工作表）
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            for sheet_name, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"三列模式并发处理完成，结果文件保存至: {output_file_path}")
        return output_file_path
        
    except Exception as e:
        print(f"处理Excel文件时发生错误: {e}")
        raise e


def process_oe_number_with_timeout(session, oe_number, brand, timeout=30):
    """
    带超时和重试机制处理单个OE号码
    改进版：添加重试机制，完善已存在情况处理
    """
    global PRODUCT_DF
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 首先获取品牌ID，这是第一步
            brand_id = get_brand_id_by_name(session, brand, timeout)
            
            # 如果没有获取到品牌ID，直接返回错误
            if not brand_id:
                print(f"OE号 {oe_number} 解析品牌ID时发生错误，没有匹配到品牌ID")
                return f"失败 - 没有匹配到品牌ID"
            
            # 品牌ID获取成功后，再发送OE号请求
            get_params = {
               "number": oe_number 
            }
            response = session.get(API_CONFIG['get_url'], params=get_params, headers=headers, timeout=timeout)
            
            # 解析响应JSON
            try:
                response_data = response.json()
                product_type_name = response_data.get("data", {}).get("product_type_name")
                err_msg = response_data.get("data", {}).get("err_msg1")
                product_name = response_data.get("data", {}).get("product_name", "")
                brand_name = response_data.get("data", {}).get("brand_name", "")
                
                # 判断product_type_name是否为"---"
                if (product_type_name == "---" and not (product_name and brand_name)) or err_msg == "此OE未匹配到，请手动输入":    
                    if PRODUCT_DF is not None:
                        # 精确匹配cxbianma列与当前oe_number
                        product_match = PRODUCT_DF[PRODUCT_DF['cxbianma'] == oe_number]
                        
                        if not product_match.empty:
                            # 获取第一条匹配记录的mingcheng
                            product_name = product_match.iloc[0]['mingcheng'].strip()
                            print(f"OE: {oe_number}, Product Name: {product_name}")
                            
                            # 通过API搜索相似产品名称
                            search_params = {'product_name': product_name}
                            search_response = session.get(API_CONFIG['search_url'], params=search_params, headers=headers, timeout=timeout)
                            if search_response.status_code == 200:
                                search_data = search_response.json()
                                name_list = search_data.get("data", {}).get("name_list", [])
                                
                                if name_list and len(name_list) > 0:
                                    # 找到最匹配的产品名称
                                    best_match = find_best_match_product(product_name, name_list)
                                    
                                    if best_match:
                                        matched_product_name = best_match.get("product_name", "")
                                        print(f"OE: {oe_number}, 匹配产品: {matched_product_name} (原名:'{product_name}')")
                                        
                                        # 执行上传操作
                                        upload_res = session.post(API_CONFIG['upload_url'], json={
                                            'l_name_zh': product_name,
                                            'l_name_zh_store': matched_product_name,
                                            "brand_id": brand_id,
                                            "number": oe_number,
                                            'cass_oebrand_name': '其他',
                                            'l_model_zh': '  '
                                        }, headers=headers, timeout=timeout)
                                        
                                        print(f"OE: {oe_number}, 上传响应内容: {upload_res.text}")
                                        
                                        # 处理上传响应
                                        try:
                                            res_json = upload_res.json()
                                            status = res_json.get("status")
                                            
                                            if status == 200:
                                                # 成功且有data字段，返回完整响应
                                                return f"成功 - {upload_res.text}"
                                            elif status == 201:
                                                # 201状态码处理（包括已存在的情况）
                                                msg = res_json.get("msg", "")
                                                if "该物料已关联当前组织" in msg:
                                                    # 已存在的情况，返回特殊标识
                                                    return "已存在 - 该物料已关联当前组织"
                                                else:
                                                    # 其他201状态，当作成功处理
                                                    return f"成功 - {upload_res.text}"
                                            else:
                                                # 其他状态码
                                                return f"失败 - 状态码{status}: {res_json.get('msg', '未知错误')}"
                                                
                                        except Exception as json_error:
                                            print(f"OE: {oe_number}, 解析上传响应JSON时出错: {json_error}")
                                            return f"失败 - 解析响应错误: {str(json_error)}"
                                            
                                    else:
                                        print(f"OE: {oe_number}, 未找到匹配的产品名称")
                                        return "失败 - 未找到匹配的产品名称"
                                else:
                                    print(f"OE: {oe_number}, 搜索API返回空列表")
                                    return "失败 - 搜索API返回空列表"
                            else:
                                print(f"OE: {oe_number}, 搜索API请求失败，状态码: {search_response.status_code}")
                                return f"失败 - 搜索API请求失败: {search_response.status_code}"
                        else:
                            print(f"OE: {oe_number}, 在产品数据库中未找到匹配记录")
                            return "失败 - 未在产品名称.xlsx中找到匹配记录"
                    else:
                        print(f"OE: {oe_number}, 产品数据库未加载")
                        return "失败 - 产品数据库未加载"
                else:
                    # 已经存在匹配的产品信息，跳过处理
                    print(f"OE: {oe_number}, 已存在匹配信息，跳过处理")
                    return "跳过"
                    
            except Exception as json_error:
                print(f"OE: {oe_number}, 解析响应JSON时出错: {json_error}")
                # 如果是超时错误且还有重试机会，继续重试
                if "timed out" in str(json_error).lower() and retry_count < max_retries - 1:
                    retry_count += 1
                    print(f"OE: {oe_number}, 超时重试第{retry_count}次...")
                    import time
                    time.sleep(1)  # 等待1秒后重试
                    continue
                else:
                    return f"失败 - 解析JSON时发生错误: {json_error}"
            
        except requests.exceptions.Timeout:
            retry_count += 1
            if retry_count < max_retries:
                print(f"OE: {oe_number}, 请求超时，重试第{retry_count}次...")
                import time
                time.sleep(2)  # 超时重试等待2秒
                continue
            else:
                print(f"OE: {oe_number}, 请求超时，已达最大重试次数")
                return f"失败 - 请求超时，已重试{max_retries}次"
                
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                print(f"OE: {oe_number}, 发生错误: {e}，重试第{retry_count}次...")
                import time
                time.sleep(1)
                continue
            else:
                print(f"OE: {oe_number}, 处理过程中发生错误: {e}，已达最大重试次数")
                return f"失败 - 处理过程中发生错误: {e}"
    
    # 如果循环结束还没返回，说明重试完了
    return f"失败 - 达到最大重试次数({max_retries})"


def process_single_item_batch(item):
    """
    批量处理单个项目 - 改进版
    完善已存在情况的处理和重试机制
    每个线程使用独立的session，避免多线程冲突
    """
    oe_number = item['oe_number']
    brand = item['brand']
    
    # 使用线程本地的session，避免多线程冲突
    session = get_thread_session()
    
    # 处理基础的OE号新建
    result = process_oe_number_with_timeout(session, oe_number, brand)
    
    # 分析处理结果类型并获取product_id
    product_id = None
    
    if result.startswith("成功"):
        # 情况1：新建成功 - 直接从结果提取ID
        try:
            import re
            match = re.search(r'"data":(\d+)', result)
            if match:
                product_id = match.group(1)
                print(f"✅ 新建成功，提取到product_id: {product_id}")
            else:
                print(f"⚠️  新建成功但响应中无data字段: {result}")
                # 新建成功但没有ID，需要查询获取
                search_result = search_products_by_oe_list(session, [oe_number])
                if search_result:
                    product_id = find_matching_product_id_simple(search_result, oe_number, brand)
                    if product_id:
                        print(f"✅ 通过查询获取到product_id: {product_id}")
                    else:
                        print(f"❌ 查询未找到匹配的product_id")
        except Exception as e:
            print(f"❌ 提取product_id时出错: {e}")
            
    elif result.startswith("已存在"):
        # 情况2：已存在 - 需要查询获取ID
        print(f"🔄 OE已存在，查询获取ID: {oe_number}")
        try:
            search_result = search_products_by_oe_list(session, [oe_number])
            if search_result:
                product_id = find_matching_product_id_simple(search_result, oe_number, brand)
                if product_id:
                    print(f"✅ 已存在OE查询到product_id: {product_id}")
                else:
                    print(f"⚠️  已存在OE但未查询到匹配的product_id")
            else:
                print(f"❌ 已存在OE查询失败")
        except Exception as e:
            print(f"❌ 查询已存在OE时出错: {e}")
            
    elif result == "跳过":
        # 情况3：跳过 - 需要查询获取ID
        print(f"🔄 OE跳过处理，查询获取ID: {oe_number}")
        try:
            search_result = search_products_by_oe_list(session, [oe_number])
            if search_result:
                product_id = find_matching_product_id_simple(search_result, oe_number, brand)
                if product_id:
                    print(f"✅ 跳过OE查询到product_id: {product_id}")
                else:
                    print(f"⚠️  跳过OE但未查询到匹配的product_id")
            else:
                print(f"❌ 跳过OE查询失败")
        except Exception as e:
            print(f"❌ 查询跳过OE时出错: {e}")
            
    else:
        # 情况4：失败 - 不处理
        print(f"❌ OE处理失败: {result}")
    
    # 如果有product_id且是三列模式，更新brand_code
    if (item.get('mode') == 'three_column' and 
        product_id and 
        item.get('brand_code')):
        
        brand_code = item['brand_code']
        print(f"🔄 更新brand_code: product_id={product_id}, brand_code={brand_code}")
        
        try:
            update_result = update_product_brand_code(session, product_id, brand_code)
            result += f" | brand_code更新: {update_result}"
            print(f"✅ brand_code更新完成: {update_result}")
        except Exception as e:
            error_msg = f"brand_code更新失败: {str(e)}"
            result += f" | {error_msg}"
            print(f"❌ {error_msg}")
            
    elif item.get('mode') == 'three_column' and not product_id:
        if result.startswith("成功"):
            result += " | 新建成功但未获取到product_id"
        elif result.startswith("已存在"):
            result += " | 已存在但未查询到product_id"
        elif result == "跳过":
            result += " | 跳过但未查询到product_id"
        else:
            result += " | 处理失败无需更新brand_code"
            
    elif item.get('mode') == 'three_column' and not item.get('brand_code'):
        result += " | 无brand_code数据"
    
    return result


def prepare_three_column_data(sheet_df, sheet_name):
    """
    准备三列模式的数据
    """
    try:
        # 识别三列模式的列
        oe_col, brand_col, brand_code_col = identify_columns_extended(sheet_df)
        
        if brand_code_col is None:
            print(f"工作表 {sheet_name} 不符合三列模式要求")
            return None
            
        # 准备处理数据
        items = []
        for index, row in sheet_df.iterrows():
            oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
            
            if oe_number and brand:
                items.append({
                    'index': index,
                    'oe_number': oe_number,
                    'brand': brand,
                    'brand_code': brand_code,
                    'sheet_name': sheet_name,
                    'mode': 'three_column'
                })
        
        return items
    except Exception as e:
        print(f"准备三列模式数据时出错: {e}")
        return None

def prepare_two_column_data(sheet_df, sheet_name):
    """
    准备两列模式的数据
    """
    try:
        # 识别两列模式的列
        oe_col, brand_col = identify_columns(sheet_df)
        
        # 准备处理数据
        items = []
        for index, row in sheet_df.iterrows():
            oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            
            if oe_number and brand:
                items.append({
                    'index': index,
                    'oe_number': oe_number,
                    'brand': brand,
                    'sheet_name': sheet_name,
                    'mode': 'two_column'
                })
        
        return items
    except Exception as e:
        print(f"准备两列模式数据时出错: {e}")
        return None

def get_global_session():
    """
    获取全局session
    """
    global GLOBAL_SESSION
    return GLOBAL_SESSION

def process_batch_items(session, items, max_workers=3):
    """
    批量处理多个项目（并发版本）
    """
    results = {}
    
    # 使用统一任务管理器进行并发处理
    from app.core.task_manager import task_manager
    
    # 提交所有任务
    futures = []
    for item in items:
        future = task_manager.submit(process_single_item_batch, session, item)
        futures.append((future, item))
    
    # 收集结果
    completed = 0
    total = len(items)
    
    for future, item in futures:
        oe_number = item['oe_number']
        
        try:
            result = future.result()
            results[oe_number] = result
            completed += 1
            print(f"工作表 {item.get('sheet_name', 'Unknown')} 处理进度: {completed}/{total} - OE: {oe_number}, 结果: {result}")
        except Exception as e:
            results[oe_number] = f"处理出错: {str(e)}"
            completed += 1
            print(f"工作表 {item.get('sheet_name', 'Unknown')} 处理进度: {completed}/{total} - OE: {oe_number}, 结果: 处理出错: {str(e)}")
    
    return results

def save_results_to_excel(results, original_file_path):
    """
    将处理结果保存到Excel文件
    """
    try:
        # 读取原始文件
        all_sheets = pd.read_excel(original_file_path, sheet_name=None)
        
        # 为每个工作表添加结果列
        for sheet_name, df in all_sheets.items():
            df['处理结果'] = ''
            for index, row in df.iterrows():
                # 根据不同的列识别方式找到oe_code
                oe_cols = ['oe', 'oe_code', 'OE', 'OE编号', '零件号']
                oe_value = None
                
                for col in oe_cols:
                    if col in df.columns:
                        oe_value = str(row[col]).strip() if pd.notna(row[col]) else ''
                        break
                
                if oe_value and oe_value in results:
                    df.at[index, '处理结果'] = results[oe_value]
        
        # 生成输出文件路径
        base_name = os.path.splitext(original_file_path)[0]
        output_file_path = base_name + '_处理结果.xlsx'
        
        # 保存文件
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            for sheet_name, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return output_file_path
        
    except Exception as e:
        print(f"保存结果到Excel时出错: {e}")
        return None


def show_debug_info(products, target_oe, target_brand):
    """显示调试信息帮助排查匹配失败原因"""
    print(f"\n🔍 调试信息:")
    print(f"   目标OE: {target_oe}")
    print(f"   目标品牌: {target_brand}")
    
    # 统计找到的相关记录
    oe_matches = 0
    brand_matches = 0
    partial_matches = []
    
    for product_group in products[:1]:  # 只检查第一组数据
        if 'child' in product_group:
            for child in product_group['child'][:10]:  # 前10个子产品
                original_number = child.get("original_number", "")
                brand_name = child.get("brand_name", "")
                product_id = child.get("product_id", "")
                
                oe_match = original_number == target_oe
                brand_match = brand_name == target_brand
                
                if oe_match:
                    oe_matches += 1
                if brand_match:
                    brand_matches += 1
                if oe_match or brand_match:
                    partial_matches.append({
                        'oe': original_number,
                        'brand': brand_name,
                        'id': product_id,
                        'oe_match': oe_match,
                        'brand_match': brand_match
                    })
    
    print(f"   OE号匹配数: {oe_matches}")
    print(f"   品牌匹配数: {brand_matches}")
    print(f"   部分匹配记录 ({len(partial_matches)}条):")
    
    for item in partial_matches:
        status = []
        if item['oe_match']:
            status.append("✅ OE匹配")
        else:
            status.append(f"❌ OE={item['oe']}")
            
        if item['brand_match']:
            status.append("✅ 品牌匹配")
        else:
            status.append(f"❌ 品牌={item['brand']}")
            
        print(f"     ID:{item['id']} | {' | '.join(status)}")


def process_excel_file_mode(file_path):
    """
    新模式：处理前端上传的Excel文件
    支持两列模式(oe+brand)和三列模式(oe+brand+brand_code)
    """
    global PRODUCT_DF, ALIAS_DF, GLOBAL_SESSION
    
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path) if file_path.endswith(('.xlsx', '.xls')) else pd.read_csv(file_path)
        print(f"读取文件成功，共 {len(df)} 行数据")
        
        # 识别关键列（扩展版本，支持brand_code）
        oe_col, brand_col, brand_code_col = identify_columns_extended(df)
        print(f"识别到oe列为: {oe_col}, brand列为: {brand_col}")
        if brand_code_col:
            print(f"识别到brand_code列为: {brand_code_col}")
        
        # 判断是两列模式还是三列模式
        is_three_column_mode = brand_code_col is not None
        print(f"处理模式: {'三列模式' if is_three_column_mode else '两列模式'}")
        
        # 加载必要的数据
        if PRODUCT_DF is None:
            load_product_data()
        if ALIAS_DF is None:
            load_alias_data()
        
        # 存储处理结果
        results_dict = {}
        
        # 使用全局session
        session = GLOBAL_SESSION
        
        # 处理每一行数据
        for index, row in df.iterrows():
            oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            
            if not oe_number or not brand:
                results_dict[oe_number] = "失败 - OE号或品牌为空"
                continue
            
            # 处理单个OE号（原有逻辑）
            result = process_oe_number_with_timeout(session, oe_number, brand)
            results_dict[oe_number] = result
            print(f"处理进度: {index + 1}/{len(df)} - OE: {oe_number}, 结果: {result}")
            
            # 如果是三列模式，额外处理brand_code更新
            if is_three_column_mode and result.startswith("成功"):
                brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
                if brand_code:
                    # 新建成功的情况 - 直接从结果提取ID
                    product_id = None
                    try:
                        import re
                        match = re.search(r'"data":(\d+)', result)
                        if match:
                            product_id = match.group(1)
                            print(f"✅ 新建成功，提取到product_id: {product_id}")
                    except Exception as e:
                        print(f"❌ 提取product_id时出错: {e}")
                    
                    if product_id:
                        # 更新brand_code
                        update_result = update_product_brand_code(session, product_id, brand_code)
                        print(f"OE: {oe_number} brand_code更新结果: {update_result}")
                        results_dict[oe_number] += f" | brand_code更新: {update_result}"
                    else:
                        print(f"OE: {oe_number} 新建成功但未获取到product_id")
                        results_dict[oe_number] += " | 新建成功但未获取到product_id"
                else:
                    results_dict[oe_number] += " | 无brand_code数据"
            elif is_three_column_mode and result == "跳过":
                # 已存在的情况 - 需要查询获取ID
                brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
                if brand_code:
                    print(f"🔄 OE已存在，需要查询获取ID: {oe_number}")
                    try:
                        search_result = search_products_by_oe_list(session, [oe_number])
                        if search_result:
                            product_id = find_matching_product_id_simple(search_result, oe_number, brand)
                            if product_id:
                                print(f"✅ 已存在OE查询到product_id: {product_id}")
                                update_result = update_product_brand_code(session, product_id, brand_code)
                                print(f"OE: {oe_number} brand_code更新结果: {update_result}")
                                results_dict[oe_number] += f" | brand_code更新: {update_result}"
                            else:
                                print(f"OE: {oe_number} 已存在但未查询到匹配的product_id")
                                results_dict[oe_number] += " | 已存在但未查询到product_id"
                        else:
                            print(f"OE: {oe_number} 已存在OE查询失败")
                            results_dict[oe_number] += " | 已存在OE查询失败"
                    except Exception as e:
                        print(f"OE: {oe_number} 查询已存在OE时出错: {e}")
                        results_dict[oe_number] += f" | 查询失败: {str(e)}"
                else:
                    results_dict[oe_number] += " | 无brand_code数据"
        
        # 添加结果列
        df = add_result_column(df, results_dict, oe_col)
        
        # 保存处理后的文件
        output_file_path = file_path.replace('.xlsx', '_处理结果.xlsx').replace('.xls', '_处理结果.xlsx').replace('.csv', '_处理结果.csv')
        if file_path.endswith(('.xlsx', '.xls')):
            df.to_excel(output_file_path, index=False)
        else:
            df.to_csv(output_file_path, index=False, encoding='utf-8-sig')
        
        print(f"处理完成，结果文件保存至: {output_file_path}")
        return output_file_path
        
    except Exception as e:
        print(f"处理Excel文件时发生错误: {e}")
        raise e


def create_zip_package(file_path):
    """
    将处理后的文件打包成zip压缩包
    """
    import zipfile
    import os
    
    try:
        # 创建zip文件路径
        zip_path = file_path.replace('_处理结果.xlsx', '.zip').replace('_处理结果.csv', '.zip')
        
        # 创建zip文件
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加处理后的文件到zip
            zipf.write(file_path, os.path.basename(file_path))
        
        print(f"压缩包创建成功: {zip_path}")
        return zip_path
        
    except Exception as e:
        print(f"创建压缩包时发生错误: {e}")
        raise e


# 为新模式添加单独的主函数
def main_excel_mode(input_file_path):
    """
    Excel模式的主入口函数
    """
    try:
        # 处理Excel文件
        processed_file = process_excel_file_mode(input_file_path)
        
        # 创建压缩包
        zip_file = create_zip_package(processed_file)
        
        return zip_file
        
    except Exception as e:
        print(f"Excel模式处理失败: {e}")
        raise e

if __name__ == "__main__":
    main()