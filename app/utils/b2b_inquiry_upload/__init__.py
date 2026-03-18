"""
B2B询价上传模块
功能：询价数据导入后自动上传到B2B系统并新建产品
"""

import threading
from .uploader import upload_inquiry_data
from .product_creator import batch_create_products
from .result_merger import merge_results, generate_result_message
from .excel_exporter import generate_result_excel, get_recent_results
from .cleanup import cleanup_old_results


def process_inquiry_upload(df, company='fsbbr'):
    """
    完整的询价上传流程：
    1. B2B上传
    2. 新建产品（上传成功的数据）
    3. 合并结果
    4. 生成Excel
    5. 清理旧文件
    
    Args:
        df: 询价导入的DataFrame
        company: 公司代码
    
    Returns:
        dict: {
            'result_file': '结果文件路径',
            'stats': {...}
        }
    """
    print(f"\n{'='*60}")
    print("开始处理询价数据B2B上传 + 新建产品")
    print(f"{'='*60}")
    
    # 1. B2B上传
    upload_data = upload_inquiry_data(df, company)
    b2b_results = upload_data['b2b_results']
    valid_items = upload_data['valid_items']
    skipped_items = upload_data['skipped_items']
    
    # 2. 筛选上传失败（产品不存在）的数据进行新建产品
    # 根据B2B返回的错误信息判断是否需要新建
    def need_create_product(b2b_result):
        """判断是否需要新建产品"""
        if b2b_result.get('status') != 'error':
            return False
        msg = b2b_result.get('msg', '')
        # 检查是否包含"产品数据不存在"的关键词
        return "产品数据不存在" in msg or "产品不存在" in msg
    
    need_create_items = [
        item for item in valid_items
        if need_create_product(b2b_results.get(item['oe'], {}))
    ]
    
    print(f"\n需要新建产品的数据：{len(need_create_items)}条")
    
    create_results = {}
    if need_create_items:
        create_results = batch_create_products(need_create_items)
    
    # 3. 合并结果
    merged_results = merge_results(df, skipped_items, b2b_results, create_results)
    
    # 4. 生成结果Excel
    result_file = generate_result_excel(df, merged_results)
    
    # 5. 生成统计信息
    stats = generate_result_message(
        b2b_results, 
        create_results, 
        len(skipped_items)
    )
    
    # 6. 清理旧文件
    cleanup_old_results()
    
    print(f"\n{'='*60}")
    print("处理完成统计：")
    print(f"  总数：{len(df)}")
    print(f"  B2B上传成功：{stats['upload_success']}")
    print(f"  B2B上传失败：{stats['upload_failed']}")
    print(f"  新建成功：{stats['created']}")
    print(f"  已存在：{stats['exists']}")
    print(f"  新建失败：{stats['create_failed']}")
    print(f"  跳过：{stats['skipped']}")
    print(f"{'='*60}\n")
    
    return {
        'result_file': result_file,
        'stats': stats
    }


def start_upload_task(df, company='fsbbr'):
    """
    启动异步上传任务
    
    Args:
        df: 询价导入的DataFrame
        company: 公司代码
    
    Returns:
        dict: {'status': 'started', 'message': '...'}
    """
    def task():
        try:
            process_inquiry_upload(df, company)
        except Exception as e:
            print(f"上传任务失败：{e}")
            import traceback
            traceback.print_exc()
    
    # 启动后台线程
    thread = threading.Thread(target=task, daemon=True)
    thread.start()
    
    return {
        'status': 'started',
        'message': 'B2B上传和新建产品任务已启动'
    }


__all__ = [
    'process_inquiry_upload',
    'start_upload_task',
    'get_recent_results',
    'cleanup_old_results'
]
