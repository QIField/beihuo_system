"""
品牌数据爬取脚本
从 CRM API 爬取品牌列表数据并保存到数据库

使用方法:
    python brandCP.py

配置说明:
    修改下方的 DB_CONFIG 配置区即可
"""

import requests
import pymysql
import json
from typing import List, Dict, Optional
from datetime import datetime


# ==================== 配置区 ====================
# 线上数据库配置（硬编码）
DB_CONFIG = {
    'host': '113.45.176.129',
    'port': 3306,
    'user': 'fsbbr_data',
    'password': 'wRCA8AGn3a568f4X',
    'database': 'fsbbr_data',
    'charset': 'utf8mb4',
    'autocommit': True,
    'use_unicode': True
}

# API 配置
API_CONFIG = {
    'base_url': 'https://crm.gzbbr.com/api/Product.Brand/brandList',
    'page_size': 500,  # 每页数量
    'timeout': 30
}

# 表名
TABLE_NAME = 'crm_brand_list'
# ==================== 配置区结束 ====================


# ==================== 数据库连接 ====================
def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def db_execute(sql: str, params: tuple = None) -> int:
    """
    执行 SQL 语句（INSERT/UPDATE/DELETE）
    
    Args:
        sql: SQL 语句
        params: 参数元组
    
    Returns:
        受影响的行数
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            result = cursor.execute(sql, params or ())
            conn.commit()
            return result
    except Exception as e:
        print(f"执行SQL出错: {e}")
        conn.rollback()
        return -1
    finally:
        conn.close()
# ==================== 数据库连接结束 ====================


# ==================== CRM Cookie 获取 ====================
def get_crm_cookies():
    """
    获取 CRM 系统的认证 cookie
    
    Returns:
        dict: CRM 系统的认证 cookie 字典
    """
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


def create_crm_session():
    """
    创建带有 CRM 认证信息的 requests Session
    
    Returns:
        requests.Session: 已配置好认证信息的 session 对象
    """
    # 获取 CRM cookie 认证信息
    crm_cookies = get_crm_cookies()
    
    # 创建 session
    session = requests.Session()
    
    # 设置基础 headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://crm.gzbbr.com/',
    })
    
    # 将 cookie 认证信息添加到 headers
    session.headers.update(crm_cookies)
    
    return session


# 全局 session 对象（初始化时创建）
_crm_session = None


def get_session():
    """
    获取 CRM session（单例模式）
    
    Returns:
        requests.Session: CRM 认证 session
    """
    global _crm_session
    if _crm_session is None:
        _crm_session = create_crm_session()
    return _crm_session
# ==================== CRM Cookie 获取结束 ====================


def get_total_pages() -> int:
    """
    获取总页数
    
    Returns:
        总页数
    """
    url = API_CONFIG['base_url']
    params = {
        'page': 1,
        'limit': API_CONFIG['page_size']
    }
    
    try:
        session = get_session()
        response = session.get(url, params=params, timeout=API_CONFIG['timeout'])
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 200:
            total = data['data'].get('total', 0)
            per_page = data['data'].get('per_page', API_CONFIG['page_size'])
            total_pages = data['data'].get('last_page', 0)
            print(f"总记录数: {total}, 每页: {per_page}, 总页数: {total_pages}")
            return total_pages
        else:
            print(f"API 返回错误: {data.get('msg', '未知错误')}")
            return 0
    except Exception as e:
        print(f"获取总页数失败: {e}")
        return 0


def fetch_page(page: int) -> List[Dict]:
    """
    爬取指定页的数据
    
    Args:
        page: 页码
    
    Returns:
        品牌数据列表
    """
    url = API_CONFIG['base_url']
    params = {
        'page': page,
        'limit': API_CONFIG['page_size']
    }
    
    try:
        session = get_session()
        response = session.get(url, params=params, timeout=API_CONFIG['timeout'])
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 200:
            return data['data'].get('data', [])
        else:
            print(f"第 {page} 页 API 返回错误: {data.get('msg', '未知错误')}")
            return []
    except Exception as e:
        print(f"爬取第 {page} 页失败: {e}")
        return []


def save_brands_to_db(brands: List[Dict]) -> int:
    """
    保存品牌数据到数据库
    
    Args:
        brands: 品牌数据列表
    
    Returns:
        成功保存的记录数
    """
    if not brands:
        return 0
    
    success_count = 0
    
    # 插入 SQL（使用 INSERT IGNORE 避免重复）
    insert_sql = f"""
        INSERT IGNORE INTO {TABLE_NAME} (
            brand_id, l_name_zh, frey_no, seq, short_name, suffix,
            cass_name, type, byname, user_id, company_id, is_kingdee,
            create_time, type_cn, is_kingdee_cn, user_cn, is_parent,
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
        )
    """
    
    for brand in brands:
        try:
            params = (
                brand.get('brand_id'),
                brand.get('l_name_zh', ''),
                brand.get('frey_no', ''),
                brand.get('seq', ''),
                brand.get('short_name', ''),
                brand.get('suffix', ''),
                brand.get('cass_name', ''),
                brand.get('type', ''),
                brand.get('byname', ''),
                brand.get('user_id', ''),
                brand.get('company_id', ''),
                brand.get('is_kingdee', ''),
                brand.get('create_time', ''),
                brand.get('type_cn', ''),
                brand.get('is_kingdee_cn', ''),
                brand.get('user_cn', ''),
                brand.get('is_parent', 0)
            )
            
            db_execute(insert_sql, params)
            success_count += 1
        except Exception as e:
            brand_id = brand.get('brand_id', 'unknown')
            print(f"  保存品牌 {brand_id} 失败: {e}")
    
    return success_count


def crawl_all_brands():
    """
    爬取所有品牌数据
    """
    import sys
    print("=" * 60)
    print("开始爬取品牌数据")
    print("=" * 60)
    sys.stdout.flush()
    
    # 获取总页数
    total_pages = get_total_pages()
    if total_pages == 0:
        print("无法获取总页数，爬取终止")
        sys.stdout.flush()
        return
    
    total_saved = 0
    
    # 循环爬取每一页
    for page in range(1, total_pages + 1):
        print(f"\n正在爬取第 {page}/{total_pages} 页...")
        sys.stdout.flush()
        
        brands = fetch_page(page)
        if not brands:
            print(f"  第 {page} 页无数据")
            sys.stdout.flush()
            continue
        
        print(f"  获取到 {len(brands)} 条数据")
        sys.stdout.flush()
        
        # 保存到数据库
        saved = save_brands_to_db(brands)
        total_saved += saved
        print(f"  成功保存 {saved}/{len(brands)} 条数据")
        sys.stdout.flush()
    
    print("\n" + "=" * 60)
    print("爬取完成!")
    print(f"总计保存: {total_saved} 条数据")
    print("=" * 60)
    sys.stdout.flush()


def main():
    """
    主函数
    """
    print("品牌数据爬取脚本")
    print(f"目标表: {TABLE_NAME}")
    print(f"API: {API_CONFIG['base_url']}")
    print(f"每页数量: {API_CONFIG['page_size']}")
    print("\n开始爬取...")
    
    try:
        crawl_all_brands()
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
