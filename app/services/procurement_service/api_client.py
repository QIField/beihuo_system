"""
采购模块 API 客户端
用于调用 CRM 接口获取产品信息

核心功能:
    1. 调用 CRM 产品列表接口
    2. 根据 OE 号和品牌匹配产品
    3. 提取指定字段返回

使用示例:
    from api_client import fetch_product_info
    
    session = get_crm_session()
    product = fetch_product_info(session, "11427585403", "原厂")
    if product:
        print(product['product_name'])
"""

from typing import Optional, Dict, Any


# CRM 产品列表接口地址
CRM_PRODUCT_LIST_URL = 'https://crm.gzbbr.com/api/Product.Product/list'


# 产品等级映射
PRODUCT_GRADE_MAP = {
    '1': 'A类',
    '2': 'B类',
    '3': 'C类',
    '4': 'D类',
    '5': '淘汰品',
    '6': '无'
}


def fetch_product_info(session, oe_number: str, brand_name: str) -> Optional[Dict[str, Any]]:
    """
    根据 OE 号和品牌名称从 CRM 获取产品信息

     Args:
        session: CRM session 对象（包含认证信息）
        oe_number: OE 号（如 "11427585403"）
        brand_name: 品牌名称（如 "原厂"）

    Returns:
        包含产品字段的字典，如果未找到返回 None
        {
            'product_name': '涡轮增压回油管',      # l_name_zh
            'vehicle_brand': '宝马',              # cass_oebrand_name
            'is_cass': '1',                       # is_cass（是否同步开思）
            'product_remark': '',                 # company_remark（系统产品备注）
            'brand_code': '',                     # brand_code（品牌编码）
            'purchasing_record': '...',           # purchasing_record（采购记录）
            'purchase_summary': 0.00,             # purchase_summary（采购汇总价）
            'replace_number': '',                 # number_list（替换号/通用号）
            'product_level': 'A类'                # product_grade（产品等级）
        }
    
    示例:
        >>> session = get_crm_session()
        >>> result = fetch_product_info(session, "11427585403", "原厂")
        >>> print(result)
        {
            'product_name': '涡轮增压回油管',
            'vehicle_brand': '宝马',
            'is_cass': '1',
            'product_remark': '',
            'brand_code': '',
            'purchasing_record': '2026-01-12佛山采购专用,供应商:上海福宝盟汽配,采购:5,单价:112.00'
        }
    """
    try:
        # 构建请求参数
        params = {
            "number": oe_number
        }
        
        # 发送 GET 请求
        response = session.get(CRM_PRODUCT_LIST_URL, params=params)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        # 检查响应状态
        if result.get('status') != 200 and result.get('msg') != '操作成功':
            print(f"CRM API 返回错误: {result.get('msg', '未知错误')}")
            return None
        
        # 获取产品数据列表
        data = result.get('data', {})
        product_list = data.get('data', [])
        
        # 遍历产品列表，根据 brand_name 匹配
        for product_group in product_list:
            child_list = product_group.get('child', [])
            
            for product in child_list:
                # 匹配品牌名称
                if product.get('brand_name') == brand_name:
                    # 提取需要的字段
                    # 转换产品等级
                    product_grade = str(product.get('product_grade', '6'))
                    product_level = PRODUCT_GRADE_MAP.get(product_grade, '无')

                    return {
                        'product_name': product.get('l_name_zh', ''),
                        'vehicle_brand': product.get('cass_oebrand_name', ''),
                        'is_cass': product.get('is_cass', ''),
                        'product_remark': product.get('company_remark', ''),
                        'brand_code': product.get('brand_code', ''),
                        'purchasing_record': product.get('purchasing_record', ''),
                        'purchase_summary': float(product.get('purchase_summary', 0)) if product.get('purchase_summary') else 0.0,
                        'replace_number': product.get('number_list', ''),
                        'product_level': product_level
                    }
        
        # 未找到匹配的产品
        print(f"未找到匹配的产品: OE={oe_number}, 品牌={brand_name}")
        return None
        
    except Exception as e:
        print(f"获取产品信息失败: OE={oe_number}, 品牌={brand_name}, 错误={e}")
        return None


def fetch_product_info_batch(session, oe_brand_list: list) -> list:
    """
    批量获取产品信息
    
    Args:
        session: CRM session 对象
        oe_brand_list: OE 和品牌列表，格式：[(oe1, brand1), (oe2, brand2), ...]
    
    Returns:
        产品信息列表，每个元素包含 oe、brand 和提取的字段
        [
            {
                'oe': '11427585403',
                'brand': '原厂',
                'product_name': '涡轮增压回油管',
                'vehicle_brand': '宝马',
                'is_cass': '1',
                'product_remark': '',
                'brand_code': ''
            },
            ...
        ]
    """
    results = []
    
    for oe_number, brand_name in oe_brand_list:
        product_info = fetch_product_info(session, oe_number, brand_name)
        
        if product_info:
            results.append({
                'oe': oe_number,
                'brand': brand_name,
                **product_info
            })
        else:
            # 未找到产品，记录空结果
            results.append({
                'oe': oe_number,
                'brand': brand_name,
                'product_name': None,
                'vehicle_brand': None,
                'is_cass': None,
                'product_remark': None,
                'brand_code': None
            })
    
    return results
