#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：单独调用CRM全量爬取，爬取所有组织的数据（多线程并发）
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import threading
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import STORE_KEY_MAP
from app.services.procurement_service.crawl_service import CRMDataCrawlService

# 线程安全的打印锁
_print_lock = threading.Lock()

def thread_safe_print(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

def crawl_single_company(company):
    """单个门店的爬取任务（在线程中运行）"""
    try:
        thread_safe_print(f"\n{'='*80}")
        thread_safe_print(f"🚀 开始处理: {company}")
        thread_safe_print(f"{'='*80}")
        
        service = CRMDataCrawlService(company)
        result = service.crawl_all()
        
        thread_safe_print(f"\n✅ {company} 完成！")
        return (company, result)
        
    except Exception as e:
        thread_safe_print(f"\n❌ {company} 异常: {e}")
        import traceback
        with _print_lock:
            traceback.print_exc()
        return (company, {'error': str(e)})


def test_all_organizations():
    start_time = datetime.now()
    thread_safe_print(f"\n{'='*80}")
    thread_safe_print(f"🚀 CRM全量爬取 - 多线程并发模式")
    thread_safe_print(f"开始时间: {start_time}")
    thread_safe_print(f"待处理门店: {', '.join(STORE_KEY_MAP.keys())}")
    thread_safe_print(f"{'='*80}")
    
    companies = list(STORE_KEY_MAP.keys())
    all_results = {
        'total_saved': 0,
        'total_failed': 0,
        'tasks': {}
    }
    
    # 使用线程池并发执行（最多3个线程，剩下的排队）
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(crawl_single_company, company): company for company in companies}
        
        for future in as_completed(futures):
            company, result = future.result()
            all_results['tasks'][company] = result
            
            if 'saved' in result:
                all_results['total_saved'] += result.get('saved', 0)
                all_results['total_failed'] += result.get('failed', 0)
    
    # 输出最终统计
    end_time = datetime.now()
    duration = end_time - start_time
    
    thread_safe_print(f"\n{'='*80}")
    thread_safe_print(f"📊 全部完成！总耗时: {duration}")
    thread_safe_print(f"📊 总同步记录: {all_results['total_saved']}")
    thread_safe_print(f"❌ 总失败: {all_results['total_failed']}")
    thread_safe_print(f"{'='*80}")
    
    # 打印每个门店的详细结果
    thread_safe_print(f"\n📋 各门店结果:")
    for company, result in all_results['tasks'].items():
        if 'error' in result:
            thread_safe_print(f"  ❌ {company}: {result['error']}")
        else:
            thread_safe_print(f"  ✅ {company}: 成功{result.get('saved',0)}条, 失败{result.get('failed',0)}条")
    
    return all_results


if __name__ == '__main__':
    test_all_organizations()
