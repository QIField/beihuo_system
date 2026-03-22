"""
新建产品模块
复用crm_product的新建产品逻辑
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

# 导入配置
from config import create_crm_session

# 复用现有模块
from app.utils.crm_product.crm_productAdd.main import (
    process_single_oe,
    load_product_data,
    load_alias_data,
)


def item_to_oe_format(item):
    """
    将询价数据项转换为新建产品模块期望的格式
    """
    return {
        'oe_number': item['oe'],
        'brand': item['brand'],
        'brand_code': item.get('brand_code', ''),  # 可选
        'mode': 'two_column',  # 使用两列模式
    }


def create_single_product(item, product_df, alias_df):
    """
    单条数据新建产品
    复用process_single_oe函数
    """
    # 转换为新建产品模块格式
    oe_item = item_to_oe_format(item)
    
    # 创建session
    session = create_crm_session()
    
    try:
        # 调用现有的process_single_oe函数
        # 注意：process_single_oe期望item格式为 {'oe_number': ..., 'brand': ..., 'mode': ...}
        result = process_single_oe(oe_item, product_df, alias_df, db_manager=None)
        return {
            'oe': item['oe'],
            'result': result
        }
    except Exception as e:
        return {
            'oe': item['oe'],
            'result': f"失败 - 处理异常: {str(e)}"
        }


def batch_create_products(items, max_workers=5):
    """
    批量新建产品
    
    Args:
        items: 上传成功的数据项列表
        max_workers: 并发数
    
    Returns:
        dict: {oe: result_string}
    """
    if not items:
        return {}
    
    print(f"\n开始批量新建产品，共{len(items)}条...")
    
    # 加载产品数据
    product_df = load_product_data()
    alias_df = load_alias_data()
    
    results = {}
    
    # 串行循环处理（改为循环执行）
    completed = 0
    total = len(items)
    
    for item in items:
        try:
            result = create_single_product(item, product_df, alias_df)
            results[result['oe']] = result['result']
            completed += 1
            
            if completed % 10 == 0 or completed == total:
                print(f"新建进度: {completed}/{total}")
                
        except Exception as e:
            results[item['oe']] = f"失败 - 异常: {str(e)}"
            completed += 1
    
    # 统计
    success = sum(1 for r in results.values() if '成功' in r)
    exists = sum(1 for r in results.values() if '已存在' in r)
    failed = sum(1 for r in results.values() if '失败' in r)
    
    print(f"新建完成：新建{success}条，已存在{exists}条，失败{failed}条")
    
    return results
