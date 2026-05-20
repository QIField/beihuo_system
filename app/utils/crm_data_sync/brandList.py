import requests
from app.utils.database_connection import db_cursor


def fetch_brand_page(session, page, limit=500):
    """爬取单页品牌数据"""
    url = f'https://crm.gzbbr.com/api/Product.Brand/brandList?page={page}&limit={limit}'
    response = session.get(url, timeout=30)
    data = response.json()
    
    if data.get('status') == 200:
        return data.get('data', {}).get('data', [])
    return []


def save_brands_to_db(brands, company):
    """批量保存品牌数据到数据库"""
    if not brands:
        return 0
    
    with db_cursor(dict_cursor=False) as cursor:
        sql = """
            INSERT INTO crm_brand_list
            (company, brand_id, l_name_zh, frey_no, seq, short_name, suffix, cass_name,
             type, byname, user_id, company_id, is_kingdee, create_time, type_cn,
             is_kingdee_cn, user_cn, is_parent)
            VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        batch_data = []
        for brand in brands:
            create_time = brand.get('create_time')
            if create_time == '':
                create_time = None
            
            batch_data.append((
                company,
                brand.get('brand_id', ''),
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
                create_time,
                brand.get('type_cn', ''),
                brand.get('is_kingdee_cn', ''),
                brand.get('user_cn', ''),
                brand.get('is_parent', 0)
            ))
        
        cursor.executemany(sql, batch_data)
        return len(batch_data)


def fetch_and_save(session, company):
    """爬取指定组织的全部品牌数据并保存"""
    print(f"\n{'='*60}")
    print(f"开始爬取 [{company}] 的品牌数据")
    print(f"{'='*60}")
    
    all_brands = []
    page = 1
    limit = 500
    
    while True:
        print(f"[{company}] 正在获取第 {page} 页...")
        brands = fetch_brand_page(session, page, limit)
        
        if not brands:
            break
        
        all_brands.extend(brands)
        print(f"[{company}] 第 {page} 页获取 {len(brands)} 条数据")
        
        if len(brands) < limit:
            break
        
        page += 1
    
    print(f"[{company}] 总共获取 {len(all_brands)} 条数据")
    
    count = save_brands_to_db(all_brands, company)
    print(f"[{company}] 已保存 {count} 条数据")
    print(f"{'='*60}\n")
    
    return count
