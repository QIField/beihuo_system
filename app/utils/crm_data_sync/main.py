from config.cookie_config import create_crm_session
from app.utils.database_connection import db_cursor
from .brandList import fetch_and_save as fetch_and_save_brands
from .Supplier_list import fetch_and_save_suppliers


STORE_CODES = ['fsbbr', 'zhbbr', 'zsbbr', 'dgby', 'dghf']


def truncate_brand_table():
    """清空品牌表"""
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute("TRUNCATE TABLE crm_brand_list")
        print("已清空 crm_brand_list 表")


def truncate_supplier_table():
    """清空供应商表"""
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute("TRUNCATE TABLE crm_supplier_list")
        print("已清空 crm_supplier_list 表")


def crawl_brands():
    """爬取所有门店的品牌数据"""
    print("\n" + "="*60)
    print("开始爬取CRM品牌档案")
    print("="*60 + "\n")
    
    truncate_brand_table()
    
    total_count = 0
    
    for store_code in STORE_CODES:
        print(f"[{store_code}] 正在获取session...")
        session = create_crm_session(store_code)
        count = fetch_and_save_brands(session, store_code)
        total_count += count
    
    print("\n" + "="*60)
    print(f"品牌爬取完成，共 {total_count} 条数据")
    print("="*60 + "\n")
    
    return total_count


def crawl_suppliers():
    """爬取所有门店的供应商数据"""
    print("\n" + "="*60)
    print("开始爬取CRM供应商档案")
    print("="*60 + "\n")
    
    truncate_supplier_table()
    
    total_count = 0
    
    for store_code in STORE_CODES:
        print(f"[{store_code}] 正在获取session...")
        session = create_crm_session(store_code)
        count = fetch_and_save_suppliers(session, store_code)
        total_count += count
    
    print("\n" + "="*60)
    print(f"供应商爬取完成，共 {total_count} 条数据")
    print("="*60 + "\n")
    
    return total_count


def main():
    """主函数：爬取所有CRM数据"""
    crawl_brands()
    crawl_suppliers()
    
    print("\n" + "="*60)
    print("所有CRM数据爬取完成")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
