"""
采购模块数据库服务
用于将 CRM 获取的产品信息保存到比价汇总表

核心功能:
    1. 更新比价汇总表的产品字段
    2. 根据 OE + 品牌 + 公司定位记录
    3. 批量更新支持

依赖:
    - app.services.compare_service.compare_data_service.CompareDataService
    - crmapp_compare_summary 表

使用示例:
    from db_service import update_product_fields
    
    data = {
        'oe': '11427585403',
        'brand': '原厂',
        'company': 'fsbbr',
        'product_name': '涡轮增压回油管',
        'vehicle_brand': '宝马',
        'is_cass': '1',
        'product_remark': '',
        'brand_code': ''
    }
    update_product_fields(data)
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.compare_service.compare_data_service import CompareDataService


def update_product_fields(data: dict) -> bool:
    """
    更新比价汇总表的产品字段

    根据 OE + 品牌 + 公司 定位记录，更新从 CRM 获取的字段

    Args:
        data: 数据字典，必须包含以下字段：
            - oe: OE 号（必填）
            - brand: 品牌（可选）
            - company: 公司/组织（必填）
            - product_name: 产品名称（可选）
            - vehicle_brand: 车辆品牌（可选）
            - is_cass: 是否同步开思（可选）
            - product_remark: 系统产品备注（可选）
            - brand_code: 品牌编码（可选）
            - replace_number: 替换号/通用号（可选）
            - product_level: 产品等级（可选）

    Returns:
        True 表示更新成功，False 表示失败或记录不存在

    示例:
        >>> data = {
        ...     'oe': '11427585403',
        ...     'brand': '原厂',
        ...     'company': 'fsbbr',
        ...     'product_name': '涡轮增压回油管',
        ...     'vehicle_brand': '宝马',
        ...     'is_cass': '1',
        ...     'product_remark': '',
        ...     'brand_code': '',
        ...     'replace_number': '11367537692,11367537692 PIE',
        ...     'product_level': 'A类'
        ... }
        >>> update_product_fields(data)
        True
    """
    # 验证必填字段
    if not data.get('oe'):
        print("更新失败: OE 号不能为空")
        return False
    
    if not data.get('company'):
        print("更新失败: 公司/组织不能为空")
        return False
    
    try:
        # 构建更新数据（只包含 CRM 相关的字段）
        update_data = {
            'oe': data['oe'],
            'brand': data.get('brand', ''),
            'company': data['company']
        }
        
        # 添加可选字段（如果有值）
        if data.get('product_name') is not None:
            update_data['product_name'] = data['product_name']

        if data.get('vehicle_brand') is not None:
            update_data['vehicle_brand'] = data['vehicle_brand']

        if data.get('is_cass') is not None:
            update_data['is_cass'] = data['is_cass']

        if data.get('product_remark') is not None:
            update_data['product_remark'] = data['product_remark']

        if data.get('brand_code') is not None:
            update_data['brand_code'] = data['brand_code']

        if data.get('replace_number') is not None:
            update_data['replace_number'] = data['replace_number']

        if data.get('product_level') is not None:
            update_data['product_level'] = data['product_level']
        
        # 使用 CompareDataService 的 upsert 方法
        # 如果记录存在则更新，不存在则插入
        record_id = CompareDataService.upsert_by_oe_brand_company(update_data)
        
        if record_id:
            print(f"更新成功: OE={data['oe']}, 品牌={data.get('brand', '')}, ID={record_id}")
            return True
        else:
            print(f"更新失败: OE={data['oe']}, 品牌={data.get('brand', '')}")
            return False
            
    except Exception as e:
        print(f"更新数据库时出错: OE={data.get('oe')}, 错误={e}")
        return False


def batch_update_product_fields(data_list: list) -> dict:
    """
    批量更新产品字段
    
    Args:
        data_list: 数据字典列表，每个元素格式同 update_product_fields 的 data 参数
    
    Returns:
        统计结果字典
        {
            'total': 100,      # 总记录数
            'success': 95,     # 成功数
            'failed': 5        # 失败数
        }
    
    示例:
        >>> data_list = [
        ...     {'oe': '11427585403', 'brand': '原厂', 'company': 'fsbbr', ...},
        ...     {'oe': '11427585404', 'brand': '原厂', 'company': 'fsbbr', ...}
        ... ]
        >>> batch_update_product_fields(data_list)
        {'total': 2, 'success': 2, 'failed': 0}
    """
    total = len(data_list)
    success = 0
    failed = 0
    
    for i, data in enumerate(data_list, 1):
        print(f"[{i}/{total}] 处理: OE={data.get('oe')}, 品牌={data.get('brand', '')}")
        
        if update_product_fields(data):
            success += 1
        else:
            failed += 1
    
    print(f"\n批量更新完成: 总计={total}, 成功={success}, 失败={failed}")
    
    return {
        'total': total,
        'success': success,
        'failed': failed
    }


def get_pending_oe_list(company: str, limit: int = 1000) -> list:
    """
    获取待处理（缺少产品信息）的 OE 列表
    
    从比价汇总表中查询 product_name 为空的记录
    
    Args:
        company: 公司/组织代码
        limit: 最大返回数量
    
    Returns:
        OE 和品牌列表，格式：[(oe1, brand1), (oe2, brand2), ...]
    
    示例:
        >>> get_pending_oe_list('fsbbr', 100)
        [('11427585403', '原厂'), ('11427585404', '品牌A')]
    """
    try:
        # 查询缺少产品信息的记录
        data, total = CompareDataService.list_data(
            company=company,
            product_name='',  # 空字符串表示查询 product_name 为空或 NULL 的记录
            limit=limit
        )
        
        # 提取 OE 和品牌
        oe_brand_list = []
        for item in data:
            oe = item.get('oe')
            brand = item.get('brand', '')
            if oe:
                oe_brand_list.append((oe, brand))
        
        print(f"获取到 {len(oe_brand_list)} 条待处理的 OE 记录")
        return oe_brand_list
        
    except Exception as e:
        print(f"获取待处理 OE 列表失败: {e}")
        return []
