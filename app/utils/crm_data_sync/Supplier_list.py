import requests
from app.utils.database_connection import db_cursor


def fetch_supplier_list_page(session, page, limit=500):
    """获取供应商列表（单页）"""
    url = 'https://crm.gzbbr.com/api/Crm.Supplier/Supplier_list'
    payload = {"page": page, "limit": limit, "fullname": None, "contacts": None, "contacts_phone": None}
    
    response = session.post(url, json=payload, timeout=30)
    data = response.json()
    
    if data.get('status') == 200:
        return data.get('data', {}).get('data', [])
    return []


def fetch_supplier_detail(session, supplier_link_id):
    """获取单个供应商详情"""
    url = 'https://crm.gzbbr.com/api/Crm.Supplier/ViewSupplierDetails'
    payload = {"supplier_link_id": str(supplier_link_id)}
    
    response = session.post(url, json=payload, timeout=30)
    data = response.json()
    
    if data.get('status') == 200:
        return data.get('data', {})
    return None


def save_suppliers_to_db(suppliers, company):
    """批量保存供应商数据到数据库"""
    if not suppliers:
        return 0
    
    with db_cursor(dict_cursor=False) as cursor:
        sql = """
            INSERT INTO crm_supplier_list
            (company, supplier_link_id, short_name, transfer_company_id, is_parent,
             tax_no, is_tax, cust_source_name, cust_source_id, kingdee_group,
             supplier_group_id, sap_no, company_name, company_id, name, user_id,
             fullname, partner_id, payment_description, payment_method, currency_name,
             currency_id, countryname, country, region_name, region, status, contacts,
             telephone, address, organization, organizationname, is_disabled, name_abbr)
            VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
             %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        batch_data = []
        for supplier in suppliers:
            batch_data.append((
                company,
                supplier.get('supplier_link_id', ''),
                supplier.get('short_name', ''),
                supplier.get('transfer_company_id', ''),
                supplier.get('is_parent', 0),
                supplier.get('tax_no', ''),
                supplier.get('is_tax'),
                supplier.get('cust_source_name', ''),
                supplier.get('cust_source_id', ''),
                supplier.get('kingdee_group', ''),
                supplier.get('supplier_group_id'),
                supplier.get('sap_no', ''),
                supplier.get('company_name', ''),
                supplier.get('company_id'),
                supplier.get('name', ''),
                supplier.get('user_id'),
                supplier.get('fullname', ''),
                supplier.get('partner_id', ''),
                supplier.get('payment_description', ''),
                supplier.get('payment_method', ''),
                supplier.get('currency_name', ''),
                supplier.get('currency_id', ''),
                supplier.get('countryname', ''),
                supplier.get('country', ''),
                supplier.get('region_name', ''),
                supplier.get('region', ''),
                supplier.get('status'),
                supplier.get('contacts', ''),
                supplier.get('telephone', ''),
                supplier.get('address', ''),
                supplier.get('organization', ''),
                supplier.get('organizationname', ''),
                supplier.get('is_disabled', 0),
                supplier.get('name_abbr', '')
            ))
        
        cursor.executemany(sql, batch_data)
        return len(batch_data)


def fetch_and_save_suppliers(session, company):
    """爬取指定组织的全部供应商数据并保存"""
    print(f"\n{'='*60}")
    print(f"开始爬取 [{company}] 的供应商数据")
    print(f"{'='*60}")
    
    # 1. 获取所有供应商列表
    all_supplier_ids = []
    page = 1
    limit = 500
    
    while True:
        print(f"[{company}] 正在获取供应商列表第 {page} 页...")
        suppliers = fetch_supplier_list_page(session, page, limit)
        
        if not suppliers:
            break
        
        for supplier in suppliers:
            supplier_id = supplier.get('supplier_link_id')
            if supplier_id:
                all_supplier_ids.append(supplier_id)
        
        print(f"[{company}] 第 {page} 页获取 {len(suppliers)} 条数据")
        
        if len(suppliers) < limit:
            break
        
        page += 1
    
    print(f"[{company}] 总共获取 {len(all_supplier_ids)} 个供应商ID")
    
    # 2. 循环获取每个供应商详情
    all_supplier_details = []
    for idx, supplier_id in enumerate(all_supplier_ids, 1):
        print(f"[{company}] 正在获取详情 [{idx}/{len(all_supplier_ids)}] ID: {supplier_id}")
        detail = fetch_supplier_detail(session, supplier_id)
        if detail:
            all_supplier_details.append(detail)
    
    print(f"[{company}] 成功获取 {len(all_supplier_details)} 个供应商详情")
    
    # 3. 保存到数据库
    count = save_suppliers_to_db(all_supplier_details, company)
    print(f"[{company}] 已保存 {count} 条供应商数据")
    print(f"{'='*60}\n")
    
    return count
