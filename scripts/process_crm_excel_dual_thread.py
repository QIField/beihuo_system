"""
CRM Excel 双线程并发处理脚本
基于 main.py 的两列模式处理逻辑，改为双线程并发处理

用法:
    python process_crm_excel_dual_thread.py

功能:
    1. 读取 Excel 文件 (oe + brand 两列模式)
    2. 将数据平均分成两组
    3. 启动两个线程并发处理
    4. 合并结果并保存
"""

import os
import sys
import time
import threading
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 导入 CRM Session 创建函数
from config import create_crm_session

# 导入 CRM 相关模块
from app.utils.crm_product.crm_productAdd.crm_brand_id import get_brand_dict
from app.utils.crm_product.crm_productAdd.crm_get_oe_link import get_oe_link
from app.utils.crm_product.crm_productAdd.crm_Product_Add import add_product
from app.utils.crm_product.crm_productAdd.crm_product_id import get_product_id
from app.utils.crm_product.crm_productAdd.crm_updateView import update_product_name_by_oe, update_brand_code_by_oe

# 导入 Excel 数据模块
from app.utils.crm_product.crm_productAdd.excel_data_loader import (
    load_alias_data,
    load_product_data,
    find_brand_by_alias,
    find_product_name_by_oe,
    find_best_match_product
)

# 导入统一的 SessionManager
from app.utils.session_manager import SessionManager, get_session


# ============================================================================
# 全局结果存储（线程安全）
# ============================================================================

class ThreadSafeResults:
    """线程安全的结果存储类"""
    
    def __init__(self):
        self.results = {}
        self.lock = threading.Lock()
        self.completed_count = 0
    
    def add_result(self, oe_number: str, result: str):
        """添加单个结果"""
        with self.lock:
            self.results[oe_number] = result
            self.completed_count += 1
    
    def get_results(self) -> Dict[str, str]:
        """获取所有结果"""
        with self.lock:
            return self.results.copy()
    
    def get_completed_count(self) -> int:
        """获取已完成数量"""
        with self.lock:
            return self.completed_count


# ============================================================================
# 核心处理函数（从 main.py 复制并适配）
# ============================================================================

def get_brand_id_by_name(session, brand: str, timeout: int = 30) -> int:
    """
    根据品牌名称获取品牌ID
    如果找不到，尝试使用别名匹配
    """
    from app.utils.crm_product.crm_productAdd.crm_brand_id import get_brand_list
    from config import get_auth_headers
    
    headers = get_auth_headers(session)
    
    # 首先尝试直接匹配品牌
    id_params = {'l_name_zh': brand}
    id_response = session.get('https://crm.gzbbr.com/api/Product.Brand/index', params=id_params, headers=headers, timeout=timeout)
    
    if id_response.status_code == 200:
        id_response_data = id_response.json()
        brand_list = id_response_data.get("data", {}).get("list", [])
        
        # 精确匹配l_name_zh与brand
        for brand_item in brand_list:
            if brand_item.get("l_name_zh") == brand:
                brand_id = brand_item.get("brand_id")
                print(f"[线程-{threading.current_thread().name}] 品牌 '{brand}' -> ID: {brand_id}, 名称: {brand_item.get('l_name_zh')}, 匹配: 直接匹配")
                return brand_id
    
    # 如果直接匹配失败，尝试使用别名
    corrected_brand = find_brand_by_alias(brand)
    
    if corrected_brand:
        # 使用修正后的品牌名再次尝试
        id_params = {'l_name_zh': corrected_brand}
        id_response = session.get('https://crm.gzbbr.com/api/Product.Brand/index', params=id_params, headers=headers, timeout=timeout)
        
        if id_response.status_code == 200:
            id_response_data = id_response.json()
            brand_list = id_response_data.get("data", {}).get("list", [])
            
            # 精确匹配l_name_zh与修正后的品牌名
            for brand_item in brand_list:
                if brand_item.get("l_name_zh") == corrected_brand:
                    brand_id = brand_item.get("brand_id")
                    match_type = "别名匹配" if corrected_brand != brand else "别名确认"
                    print(f"[线程-{threading.current_thread().name}] 品牌 '{brand}' -> ID: {brand_id}, 名称: {brand_item.get('l_name_zh')}, 匹配: {match_type}({corrected_brand})")
                    return brand_id
    
    print(f"[线程-{threading.current_thread().name}] 品牌 '{brand}' -> 未找到匹配")
    return None


def retry_request(func, name: str, max_retries: int = 1):
    """带重试的请求包装器"""
    for i in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if i < max_retries:
                print(f"  [线程-{threading.current_thread().name}] {name} 请求失败，重试第 {i+1} 次...")
                time.sleep(1)
            else:
                print(f"  [线程-{threading.current_thread().name}] {name} 请求失败: {e}")
                return None
    return None


def process_single_oe_thread(item: Dict[str, Any], product_df, alias_df, session) -> str:
    """
    处理单个 OE 号码（线程版本）
    
    Args:
        item: 数据项 {oe_number, brand, brand_code(可选)}
        product_df: 产品数据 DataFrame
        alias_df: 别名数据 DataFrame
        session: 已认证的 session
    
    Returns:
        结果字符串
    """
    oe_number = item['oe_number']
    brand = item['brand']
    brand_code = item.get('brand_code', '')
    is_three_column = item.get('mode') == 'three_column'
    
    # 步骤 1: 获取 brand_id（实时查询）
    brand_id = get_brand_id_by_name(session, brand)
    if not brand_id:
        result = f"失败 - 没有匹配到品牌ID: {brand}"
        print(f"[线程-{threading.current_thread().name}] ❌ {oe_number}: {result}")
        return result
    
    # 步骤 2: 获取 OE 信息（带重试）
    oe_info = retry_request(lambda: get_oe_link(oe_number, session), "get_oe_link")
    if not oe_info:
        result = f"失败 - 获取 OE 信息失败"
        print(f"[线程-{threading.current_thread().name}] ❌ {oe_number}: {result}")
        return result
    
    product_name = oe_info.get('product_name', '')
    vehicle_name = oe_info.get('vehicle_name', '')
    brand_name = oe_info.get('brand_name', '')
    
    # 步骤 3: 处理缺失字段
    used_excel_name = False
    
    if not product_name:
        # 从 Excel 匹配产品名称
        if product_df is not None:
            matched_name = find_product_name_by_oe(oe_number)
            if matched_name:
                product_name = matched_name
                used_excel_name = True
                print(f"[线程-{threading.current_thread().name}] ✓ {oe_number}: 从 Excel 匹配到产品名称: {product_name}")
            else:
                result = f"失败 - 未找到产品名称"
                print(f"[线程-{threading.current_thread().name}] ❌ {oe_number}: {result}")
                return result
        else:
            result = f"失败 - 产品数据未加载"
            print(f"[线程-{threading.current_thread().name}] ❌ {oe_number}: {result}")
            return result
    
    # brand_name 为空则填"其他"
    if not brand_name:
        brand_name = "其他"
    
    # 步骤 4: 准备产品数据
    product_data = {
        "number": oe_number,
        "brand_id": brand_id,
        "l_name_zh": product_name,
        "l_name_zh_store": product_name,
        "cass_oebrand_name": brand_name,
        "l_model_zh": vehicle_name if vehicle_name else "暂无"
    }
    
    # 步骤 5: 发送 crmProductAdd 请求（带重试）
    add_result = retry_request(
        lambda: add_product(product_data, session),
        "crmProductAdd"
    )
    
    if not add_result:
        result = f"失败 - 添加产品请求失败"
        print(f"[线程-{threading.current_thread().name}] ❌ {oe_number}: {result}")
        return result
    
    # 解析响应
    status = add_result.get('status')
    msg = add_result.get('msg', '')
    
    # 检查车型为空的错误
    if not vehicle_name or "车型不能为空" in msg or ("车型" in msg and "不能为空" in msg):
        result = f"失败 - 车型不能为空 | 请求: {product_data} | 响应: {add_result}"
        print(f"[线程-{threading.current_thread().name}] ❌ {oe_number}: {result}")
        return result
    
    if status == 200:
        product_id = add_result.get('data')
        result = f"成功 - product_id: {product_id}"
        print(f"[线程-{threading.current_thread().name}] ✅ {oe_number}: {result}")
        
        # 如果使用了 Excel 匹配的名称，需要更新为最佳匹配
        if used_excel_name:
            _update_with_best_match_thread(session, oe_number, brand, product_name)
        
    elif status == 201:
        if "该物料已关联当前组织" in msg:
            result = f"已存在 - {msg}"
            print(f"[线程-{threading.current_thread().name}] ⚠️  {oe_number}: {result}")
        else:
            result = f"成功 - {msg}"
            print(f"[线程-{threading.current_thread().name}] ✅ {oe_number}: {result}")
            
        # 已存在也需要更新最佳匹配名称
        if used_excel_name:
            _update_with_best_match_thread(session, oe_number, brand, product_name)
    else:
        result = f"失败 - {msg}"
        print(f"[线程-{threading.current_thread().name}] ❌ {oe_number}: {result}")
        return result
    
    # 步骤 6: 三列模式更新 brand_code
    if is_three_column and brand_code:
        update_result = update_brand_code_by_oe(session, oe_number, brand, brand_code)
        if update_result:
            result += f" | brand_code更新成功"
            print(f"[线程-{threading.current_thread().name}] ✓ {oe_number}: brand_code 更新成功")
        else:
            result += f" | brand_code更新失败"
            print(f"[线程-{threading.current_thread().name}] ⚠️  {oe_number}: brand_code 更新失败")
    
    return result


def _update_with_best_match_thread(session, oe_number: str, brand: str, product_name: str):
    """使用最佳匹配名称更新产品（线程版本）"""
    try:
        from app.utils.crm_product.crm_productAdd.crm_brand_id import get_brand_list
        search_result = get_brand_list({'product_name': product_name}, session)
        
        if search_result and search_result.get('status') == 200:
            name_list = search_result.get('data', {}).get('name_list', [])
            
            if name_list:
                best_match = find_best_match_product(product_name, name_list)
                if best_match:
                    matched_name = best_match.get('product_name', '')
                    print(f"[线程-{threading.current_thread().name}] 🔄 {oe_number}: 最佳匹配名称: {matched_name}")
                    
                    # 更新产品名称
                    update_result = update_product_name_by_oe(
                        session, oe_number, brand, matched_name
                    )
                    if update_result:
                        print(f"[线程-{threading.current_thread().name}] ✓ {oe_number}: 产品名称更新成功")
                    else:
                        print(f"[线程-{threading.current_thread().name}] ⚠️  {oe_number}: 产品名称更新失败")
    except Exception as e:
        print(f"[线程-{threading.current_thread().name}] ⚠️  {oe_number}: 更新最佳匹配名称时出错: {e}")


# ============================================================================
# 双线程处理函数
# ============================================================================

def worker_thread(thread_name: str, items: List[Dict], product_df, alias_df, results_store: ThreadSafeResults):
    """
    工作线程函数
    
    Args:
        thread_name: 线程名称
        items: 要处理的数据项列表
        product_df: 产品数据 DataFrame
        alias_df: 别名数据 DataFrame
        results_store: 线程安全的结果存储对象
    """
    print(f"\n[{thread_name}] 启动，处理 {len(items)} 条数据")
    
    # 创建独立的 session
    try:
        session = create_crm_session()
        print(f"[{thread_name}] Session 创建成功")
    except Exception as e:
        print(f"[{thread_name}] ❌ Session 创建失败: {e}")
        # 记录所有失败
        for item in items:
            results_store.add_result(item['oe_number'], f"失败 - Session创建失败: {e}")
        return
    
    # 处理数据
    completed = 0
    for item in items:
        try:
            result = process_single_oe_thread(item, product_df, alias_df, session)
            results_store.add_result(item['oe_number'], result)
        except Exception as e:
            result = f"失败 - 处理异常: {e}"
            results_store.add_result(item['oe_number'], result)
            print(f"[{thread_name}] ❌ {item['oe_number']}: {result}")
        
        completed += 1
        if completed % 10 == 0 or completed == len(items):
            print(f"[{thread_name}] 进度: {completed}/{len(items)}")
    
    print(f"[{thread_name}] 完成，共处理 {completed} 条数据")


def process_with_dual_threads(items: List[Dict], product_df, alias_df) -> Dict[str, str]:
    """
    使用双线程并发处理数据
    
    Args:
        items: 所有要处理的数据项
        product_df: 产品数据 DataFrame
        alias_df: 别名数据 DataFrame
    
    Returns:
        处理结果字典 {oe_number: result}
    """
    if not items:
        return {}
    
    # 创建线程安全的结果存储
    results_store = ThreadSafeResults()
    
    # 将数据平均分成两组
    mid = len(items) // 2
    group1 = items[:mid]
    group2 = items[mid:]
    
    print(f"\n数据分组完成:")
    print(f"  组1: {len(group1)} 条")
    print(f"  组2: {len(group2)} 条")
    print(f"  总计: {len(items)} 条")
    
    # 创建两个线程
    thread1 = threading.Thread(
        target=worker_thread,
        args=("Thread-1", group1, product_df, alias_df, results_store),
        name="Thread-1"
    )
    thread2 = threading.Thread(
        target=worker_thread,
        args=("Thread-2", group2, product_df, alias_df, results_store),
        name="Thread-2"
    )
    
    # 启动线程
    start_time = time.time()
    print(f"\n开始双线程并发处理...")
    thread1.start()
    thread2.start()
    
    # 等待两个线程完成
    thread1.join()
    thread2.join()
    
    elapsed_time = time.time() - start_time
    print(f"\n双线程处理完成，耗时: {elapsed_time:.2f} 秒")
    print(f"平均每条处理时间: {elapsed_time/len(items):.2f} 秒")
    
    return results_store.get_results()


# ============================================================================
# Excel 处理函数
# ============================================================================

def identify_columns(df):
    """识别两列模式的列（oe, brand）"""
    oe_columns = ['oe', 'OE', 'barcode', '物料条码']
    brand_columns = ['brand', '品牌', '品牌名称']
    
    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))
    
    oe_col = None
    brand_col = None
    
    for key in oe_columns:
        if key.lower() in columns_lower:
            oe_col = column_mapping[key.lower()]
            break
    
    for key in brand_columns:
        if key.lower() in columns_lower:
            brand_col = column_mapping[key.lower()]
            break
    
    if oe_col:
        print(f"识别到 OE 列: {oe_col}")
    if brand_col:
        print(f"识别到 Brand 列: {brand_col}")
    
    return oe_col, brand_col


def save_excel_results(df, results: Dict[str, str], oe_col: str, original_file_path: str) -> str:
    """保存 Excel 结果"""
    df['新建结果'] = ''
    
    for idx, row in df.iterrows():
        oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        if oe in results:
            df.at[idx, '新建结果'] = results[oe]
    
    # 生成输出路径
    base_name = os.path.splitext(original_file_path)[0]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"{base_name}_处理结果_{timestamp}.xlsx"
    
    df.to_excel(output_path, index=False)
    print(f"\n结果已保存: {output_path}")
    return output_path


def process_excel_file(file_path: str) -> str:
    """
    处理 Excel 文件（双线程版本）
    
    Args:
        file_path: Excel 文件路径
    
    Returns:
        结果文件路径
    """
    print(f"\n{'='*60}")
    print("CRM Excel 双线程并发处理")
    print(f"{'='*60}")
    print(f"文件: {file_path}")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 加载 Excel 数据
    print("\n加载辅助数据...")
    product_df = load_product_data()
    alias_df = load_alias_data()
    
    # 读取 Excel 文件
    print(f"\n读取 Excel 文件...")
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str)
            print(f"CSV 文件，读取到 {len(df)} 行数据")
        else:
            df = pd.read_excel(file_path, dtype=str)
            print(f"Excel 文件，读取到 {len(df)} 行数据")
    except Exception as e:
        raise Exception(f"读取文件失败: {e}")
    
    # 识别列
    oe_col, brand_col = identify_columns(df)
    if not oe_col or not brand_col:
        raise ValueError("未能识别必要的列 (oe 和 brand)")
    
    # 准备处理项
    items = []
    for _, row in df.iterrows():
        oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
        if oe and brand:
            items.append({
                'oe_number': oe,
                'brand': brand,
                'mode': 'two_column'
            })
    
    print(f"有效数据: {len(items)} 条")
    
    if not items:
        print("没有有效数据需要处理")
        return None
    
    # 双线程并发处理
    results = process_with_dual_threads(items, product_df, alias_df)
    
    # 保存结果
    result_file_path = save_excel_results(df, results, oe_col, file_path)
    
    # 统计结果
    print(f"\n{'='*60}")
    print("处理统计:")
    success_count = sum(1 for r in results.values() if '成功' in r or '已存在' in r)
    fail_count = sum(1 for r in results.values() if '失败' in r)
    print(f"  成功/已存在: {success_count} 条")
    print(f"  失败: {fail_count} 条")
    print(f"  总计: {len(results)} 条")
    print(f"{'='*60}")
    
    return result_file_path


# ============================================================================
# 主入口
# ============================================================================

def main():
    """主函数"""
    # 默认文件路径
    default_file_path = r"G:\work\BBR\FLASK\beihuo_system-main\unmatched_oe_brand_company_20260513_164041.xlsx"
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = default_file_path
    
    try:
        result_path = process_excel_file(file_path)
        if result_path:
            print(f"\n✅ 处理完成！")
            print(f"结果文件: {result_path}")
        else:
            print("\n⚠️ 没有数据被处理")
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
