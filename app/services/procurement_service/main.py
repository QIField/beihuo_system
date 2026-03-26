"""
采购模块主入口
协调 CRM 数据获取和数据库更新

核心流程:
    1. 获取 CRM Session（使用 SessionManager 复用）
    2. 从数据库获取待处理的 OE 列表
    3. 调用 CRM 接口获取产品信息
    4. 更新数据库

使用示例:
    # 方式1: 处理指定 OE
    from main import process_single_oe
    process_single_oe('11427585403', '原厂', 'fsbbr')
    
    # 方式2: 批量处理所有待处理 OE
    from main import process_all_pending_oes
    process_all_pending_oes('fsbbr')
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.utils.session_manager import SessionManager

from .api_client import fetch_product_info, fetch_product_info_batch
from .db_service import update_product_fields, batch_update_product_fields, get_pending_oe_list


def get_crm_session():
    """获取 CRM session（线程安全，自动复用）"""
    return SessionManager.get_session()


def process_single_oe(oe_number: str, brand_name: str, company: str) -> bool:
    """
    处理单个 OE 号
    
    从 CRM 获取产品信息并更新到比价汇总表：
    crmapp_compare_summary - 产品基本信息
    
    Args:
        oe_number: OE 号
        brand_name: 品牌名称
        company: 公司/组织代码
    
    Returns:
        True 表示成功，False 表示失败
    
    示例:
        >>> process_single_oe('11427585403', '原厂', 'fsbbr')
        [1/1] 获取 CRM 数据: OE=11427585403, 品牌=原厂
        更新产品信息成功: OE=11427585403, 品牌=原厂, ID=123
        True
    """
    print(f"[1/1] 获取 CRM 数据: OE={oe_number}, 品牌={brand_name}")
    
    # 获取 CRM session
    session = get_crm_session()
    
    # 从 CRM 获取产品信息
    product_info = fetch_product_info(session, oe_number, brand_name)
    
    if not product_info:
        print(f"未获取到产品信息: OE={oe_number}, 品牌={brand_name}")
        return False
    
    # 步骤 1: 更新产品基本信息到比价汇总表
    print("步骤 1: 更新产品基本信息...")
    update_data = {
        'oe': oe_number,
        'brand': brand_name,
        'company': company,
        'product_name': product_info.get('product_name'),
        'vehicle_brand': product_info.get('vehicle_brand'),
        'is_cass': product_info.get('is_cass'),
        'product_remark': product_info.get('product_remark'),
        'brand_code': product_info.get('brand_code'),
        'replace_number': product_info.get('replace_number'),
        'product_level': product_info.get('product_level')
    }
    
    success = update_product_fields(update_data)
    if not success:
        print(f"更新产品信息失败: OE={oe_number}")
        return False

    print(f"更新产品信息成功: OE={oe_number}, 品牌={brand_name}")
    return True


def process_oe_list(oe_brand_list: list, company: str) -> dict:
    """
    批量处理 OE 列表
    
    更新到比价汇总表：
    crmapp_compare_summary - 产品基本信息
    
    Args:
        oe_brand_list: OE 和品牌列表，格式：[(oe1, brand1), (oe2, brand2), ...]
        company: 公司/组织代码
    
    Returns:
        统计结果字典
        {
            'total': 100,           # 总记录数
            'product_success': 95,  # 产品信息更新成功数
            'failed': 5             # 失败数
        }
    
    示例:
        >>> oe_list = [('11427585403', '原厂'), ('11427585404', '品牌A')]
        >>> process_oe_list(oe_list, 'fsbbr')
        开始批量处理 2 个 OE 号...
        步骤 1: 从 CRM 获取产品信息...
        步骤 2: 更新产品基本信息...
        {'total': 2, 'product_success': 2, 'failed': 0}
    """
    if not oe_brand_list:
        print("OE 列表为空，无需处理")
        return {'total': 0, 'product_success': 0, 'record_success': 0, 'failed': 0}
    
    total = len(oe_brand_list)
    print(f"开始批量处理 {total} 个 OE 号...\n")
    
    # 获取 CRM session
    session = get_crm_session()
    
    # 批量获取产品信息
    print("步骤 1: 从 CRM 获取产品信息...")
    product_list = fetch_product_info_batch(session, oe_brand_list)
    
    # 构建产品更新数据列表
    update_data_list = []
    product_success = 0
    failed = 0
    
    for product in product_list:
        update_data = {
            'oe': product['oe'],
            'brand': product['brand'],
            'company': company,
            'product_name': product.get('product_name'),
            'vehicle_brand': product.get('vehicle_brand'),
            'is_cass': product.get('is_cass'),
            'product_remark': product.get('product_remark'),
            'brand_code': product.get('brand_code'),
            'replace_number': product.get('replace_number'),
            'product_level': product.get('product_level')
        }
        update_data_list.append(update_data)
    
    # 步骤 2: 批量更新产品基本信息
    print("\n步骤 2: 更新产品基本信息...")
    product_result = batch_update_product_fields(update_data_list)
    product_success = product_result['success']
    failed = product_result['failed']

    print(f"\n批量处理完成:")
    print(f"  - 产品信息: 成功={product_success}, 失败={failed}")

    return {
        'total': total,
        'product_success': product_success,
        'failed': failed
    }


def process_all_pending_oes(company: str, batch_size: int = 100) -> dict:
    """
    处理所有待处理的 OE（缺少产品信息的记录）
    
    从比价汇总表获取 product_name 为空的记录，
    从 CRM 获取产品信息后更新到数据库
    
    Args:
        company: 公司/组织代码
        batch_size: 每批处理数量，默认 100
    
    Returns:
        统计结果字典
        {
            'total_pending': 150,    # 待处理总数
            'processed': 100,        # 实际处理数
            'success': 95,           # 成功数
            'failed': 5              # 失败数
        }
    
    示例:
        >>> process_all_pending_oes('fsbbr')
        获取到 150 条待处理的 OE 记录
        开始批量处理 150 个 OE 号...
        ...
        {'total_pending': 150, 'processed': 150, 'success': 148, 'failed': 2}
    """
    # 获取待处理的 OE 列表
    oe_brand_list = get_pending_oe_list(company, limit=batch_size)
    
    if not oe_brand_list:
        print("没有待处理的 OE 记录")
        return {
            'total_pending': 0,
            'processed': 0,
            'success': 0,
            'failed': 0
        }
    
    total_pending = len(oe_brand_list)
    
    # 批量处理
    result = process_oe_list(oe_brand_list, company)
    
    return {
        'total_pending': total_pending,
        'processed': result['total'],
        'success': result['success'],
        'failed': result['failed']
    }


def main():
    """
    主函数（命令行入口）
    
    支持两种模式:
        1. 单条处理: python main.py single <oe> <brand> <company>
        2. 批量处理: python main.py batch <company>
    
    示例:
        python main.py single 11427585403 原厂 fsbbr
        python main.py batch fsbbr
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='采购模块 - CRM 产品信息同步工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 单条处理命令
    single_parser = subparsers.add_parser('single', help='处理单个 OE')
    single_parser.add_argument('oe', help='OE 号')
    single_parser.add_argument('brand', help='品牌名称')
    single_parser.add_argument('company', help='公司/组织代码')
    
    # 批量处理命令
    batch_parser = subparsers.add_parser('batch', help='批量处理所有待处理 OE')
    batch_parser.add_argument('company', help='公司/组织代码')
    batch_parser.add_argument('--batch-size', type=int, default=100, help='每批处理数量（默认100）')
    
    args = parser.parse_args()
    
    if args.command == 'single':
        success = process_single_oe(args.oe, args.brand, args.company)
        sys.exit(0 if success else 1)
    
    elif args.command == 'batch':
        result = process_all_pending_oes(args.company, args.batch_size)
        print(f"\n处理结果: 总计={result['total_pending']}, 成功={result['success']}, 失败={result['failed']}")
        sys.exit(0 if result['failed'] == 0 else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
