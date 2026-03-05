"""
批量处理 Excel 文件并添加产品到 CRM - 三列模式版本
简化版：直接在全局注入 cookie 到 headers
"""

import pandas as pd
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os
import requests
import json

# 获取项目根目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..', '..', '..')
sys.path.insert(0, project_root)

# 使用包的方式导入
from config import get_crm_cookies


# ============================================================================
# 全局配置 - 模仿 crm新建产品.py 的方式
# ============================================================================

# 获取 cookie 并更新到 headers
CRM_COOKIES = get_crm_cookies()

# API 请求用的 headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
    'referer': 'https://crm.gzbbr.com/',
}
# 将 cookie 认证信息添加到headers 中
HEADERS.update(CRM_COOKIES)

# 创建全局 session
GLOBAL_SESSION = requests.Session()
GLOBAL_SESSION.headers.update(HEADERS)


# ============================================================================
# 功能模块
# ============================================================================

def setup_logging():
    """配置日志系统"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'crm_batch_process_{timestamp}.log'
    
    # 配置日志格式
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        encoding='utf-8'
    )
    
    # 同时输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logging.getLogger('').addHandler(console_handler)
    
    return log_filename


def read_excel_three_column(file_path):
    """
    读取 Excel 文件（三列模式）
    
    Args:
        file_path: Excel 文件路径
    
    Returns:
        list: 处理项列表，每项包含 oe_number, brand, brand_code
    """
    logging.info(f"开始读取 Excel 文件：{file_path}")
    
    try:
        # 读取所有工作表
        all_sheets = pd.read_excel(file_path, sheet_name=None)
        logging.info(f"读取到 {len(all_sheets)} 个工作表：{list(all_sheets.keys())}")
        
        all_items = []
        
        for sheet_name, df in all_sheets.items():
            try:
                # 识别三列模式的列
                from crm_excel import identify_columns_extended
                oe_col, brand_col, brand_code_col = identify_columns_extended(df)
                
                if brand_code_col is None:
                    logging.warning(f"工作表 '{sheet_name}' 不符合三列模式要求，跳过")
                    continue
                
                logging.info(f"工作表 '{sheet_name}': oe 列={oe_col}, brand 列={brand_col}, brand_code 列={brand_code_col}")
                
                # 提取数据
                for index, row in df.iterrows():
                    oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
                    brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
                    brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
                    
                    if oe_number and brand:
                        all_items.append({
                            'index': index,
                            'oe_number': oe_number,
                            'brand': brand,
                            'brand_code': brand_code,
                            'sheet_name': sheet_name
                        })
                
                logging.info(f"从工作表 '{sheet_name}' 提取了 {len([i for i in all_items if i['sheet_name'] == sheet_name])} 条有效数据")
                
            except ValueError as e:
                logging.warning(f"工作表 '{sheet_name}' 列识别失败：{e}")
                continue
        
        logging.info(f"总共提取 {len(all_items)} 条有效数据")
        return all_items
        
    except Exception as e:
        logging.error(f"读取 Excel 文件时发生错误：{e}")
        raise


def get_brand_id_by_name(brand, session):
    """
    根据品牌名称获取品牌 ID
    
    Args:
        brand: 品牌名称
        session: requests session 对象
    
    Returns:
        品牌 ID，找不到返回 None
    """
    url = 'https://crm.gzbbr.com/api/Product.Brand/index'
    params = {'l_name_zh': brand}
    
    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result and result.get('status') == 200:
            brand_list = result.get('data', {}).get('list', [])
            for brand_item in brand_list:
                if brand_item.get('l_name_zh') == brand:
                    return brand_item.get('brand_id')
        
        return None
    except Exception as e:
        logging.error(f"获取品牌 ID 失败：{e}")
        return None


def get_oe_link(number, session):
    """
    获取 OE 链接信息
    
    Args:
        number: 产品编号
        session: requests session 对象
    
    Returns:
        包含 product_name, vehicle_name, brand_name 的字典，失败返回 None
    """
    url = 'https://crm.gzbbr.com/api/Product.Product/get_oe_link'
    params = {'number': number}
    
    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result and result.get('status') == 200:
            data = result.get('data', {})
            return {
                'product_name': data.get('product_name'),
                'vehicle_name': data.get('vehicle_name'),
                'brand_name': data.get('brand_name')
            }
        return None
    except Exception as e:
        logging.error(f"获取 OE 信息失败：{e}")
        return None


def add_product(product_data, session):
    """
    添加产品到 CRM
    
    Args:
        product_data: 产品数据字典
        session: requests session 对象
    """
    url = 'https://crm.gzbbr.com/api/Product.Product/crmProductAdd'
    
    try:
        response = session.post(url, json=product_data, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"添加产品失败：{e}")
        return None


def process_single_item(item, session):
    """
    处理单条数据
    
    Args:
        item: 数据项字典
        session: requests session 对象（已包含 cookie）
    
    Returns:
        dict: 处理结果
    """
    oe_number = item['oe_number']
    brand = item['brand']
    brand_code = item.get('brand_code', '')
    sheet_name = item.get('sheet_name', '')
    
    result = {
        'oe_number': oe_number,
        'brand': brand,
        'brand_code': brand_code,
        'sheet_name': sheet_name,
        'request_params': {},
        'response': None,
        'success': False,
        'error': None
    }
    
    try:
        # 步骤 1: 获取 brand_id
        brand_id = get_brand_id_by_name(brand, session)
        if not brand_id:
            error_msg = f"未找到品牌 '{brand}' 对应的 brand_id"
            logging.warning(error_msg)
            result['error'] = error_msg
            return result
        
        logging.info(f"[{sheet_name}] OE: {oe_number}, 品牌：{brand}, brand_id: {brand_id}")
        
        # 步骤 2: 获取 OE 信息
        logging.info(f"  → 获取 OE 信息：{oe_number}")
        oe_info = get_oe_link(oe_number, session)
        
        if not oe_info:
            error_msg = f"获取 OE 信息失败：{oe_number}"
            logging.warning(error_msg)
            result['error'] = error_msg
            return result
        
        product_name = oe_info.get('product_name')
        vehicle_name = oe_info.get('vehicle_name')
        brand_name = oe_info.get('brand_name')
        
        logging.info(f"  → OE 信息：product_name={product_name}, vehicle_name={vehicle_name}, brand_name={brand_name}")
        
        if not product_name:
            error_msg = f"OE 信息中缺少 product_name"
            logging.warning(error_msg)
            result['error'] = error_msg
            return result
        
        # 步骤 3: 添加产品到 CRM
        logging.info(f"  → 添加产品到 CRM")
        request_params = {
            "number": oe_number,
            "brand_id": brand_id,
            "l_name_zh": product_name,
            "l_name_zh_store": product_name,
            "cass_oebrand_name": brand_name,
            "l_model_zh": vehicle_name
        }
        result['request_params'] = request_params
        
        # 记录完整的请求参数
        logging.info(f"  → 【请求参数】{json.dumps(request_params, ensure_ascii=False)}")
        
        response = add_product(request_params, session)
        result['response'] = response
        
        # 记录完整的响应结果
        if response:
            logging.info(f"  → 【完整响应】{json.dumps(response, ensure_ascii=False)}")
            
            if response.get('status') == 200:
                logging.info(f"  ✓ 添加成功：{response.get('msg', 'Success')}")
                result['success'] = True
            else:
                logging.warning(f"  ✗ 添加失败：{response.get('msg', 'Unknown error')}")
                result['error'] = f"API 返回错误：{response.get('msg', 'Unknown error')}"
        else:
            logging.error(f"  ✗ 请求失败：无响应")
            result['error'] = "API 无响应"
        
    except Exception as e:
        error_msg = f"处理过程中发生异常：{str(e)}"
        logging.error(error_msg)
        result['error'] = error_msg
    
    return result


def main():
    """主函数"""
    # 配置日志
    log_filename = setup_logging()
    logging.info("=" * 80)
    logging.info("CRM 批量产品添加程序启动（简化版 - 全局 Headers）")
    logging.info("=" * 80)
    
    # Excel 文件路径
    excel_file_path = r"E:\work download\工作文件\锁机已手动处理.xls"
    logging.info(f"Excel 文件路径：{excel_file_path}")
    
    # 检查文件是否存在
    if not os.path.exists(excel_file_path):
        logging.error(f"文件不存在：{excel_file_path}")
        print(f"错误：文件不存在 - {excel_file_path}")
        return
    
    try:
        # 使用全局 session（已经注入 cookie）
        session = GLOBAL_SESSION
        logging.info("Cookie 已注入到全局 Headers，Session 已准备")
        
        # 步骤 1: 获取 Brand ID 字典
        logging.info("\n正在获取品牌列表...")
        brand_url = 'https://crm.gzbbr.com/api/Product.Brand/index'
        brand_response = session.get(brand_url)
        brand_result = brand_response.json()
        
        if not brand_result or brand_result.get('status') != 200:
            logging.error("获取品牌字典失败")
            print("错误：无法获取品牌字典")
            return
        
        brand_list = brand_result.get('data', {}).get('list', [])
        brand_dict = {
            item['brand_id']: item['l_name_zh'] 
            for item in brand_list 
            if 'brand_id' in item and 'l_name_zh' in item
        }
        
        # 反转字典：{l_name_zh: brand_id}
        brand_name_to_id_dict = {v: k for k, v in brand_dict.items()}
        logging.info(f"获取到 {len(brand_name_to_id_dict)} 个品牌")
        
        # 打印所有品牌，方便查找
        all_brands = list(brand_name_to_id_dict.keys())
        logging.info(f"所有品牌列表：{', '.join(all_brands[:50])}")
        if len(all_brands) > 50:
            logging.info(f"... 还有 {len(all_brands) - 50} 个品牌")
        
        # 步骤 2: 读取 Excel 文件
        items = read_excel_three_column(excel_file_path)
        
        if not items:
            logging.warning("没有可处理的数据")
            print("提示：Excel 中没有可处理的数据")
            return
        
        # 步骤 3: 并发处理数据（共享同一个 session）
        logging.info(f"\n开始并发处理 {len(items)} 条数据...")
        max_workers = min(20, len(items))  # 最多 20 个并发线程
        logging.info(f"并发线程数：{max_workers}")
        
        results = []
        success_count = 0
        fail_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务（每个任务都使用同一个 session）
            future_to_item = {
                executor.submit(process_single_item, item, session): item
                for item in items
            }
            
            # 收集结果
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['success']:
                        success_count += 1
                    else:
                        fail_count += 1
                    
                    # 打印进度
                    total = len(items)
                    current = success_count + fail_count
                    progress = f"[{current}/{total}]"
                    status = "✓" if result['success'] else "✗"
                    logging.info(f"{progress} {status} OE: {result['oe_number']}, 品牌：{result['brand']} - {result.get('error', '成功')}")
                    
                except Exception as e:
                    logging.error(f"处理 OE: {item['oe_number']} 时发生异常：{e}")
                    fail_count += 1
        
        # 步骤 4: 汇总结果
        logging.info("\n" + "=" * 80)
        logging.info("处理完成！")
        logging.info(f"总计：{len(items)} 条")
        logging.info(f"成功：{success_count} 条")
        logging.info(f"失败：{fail_count} 条")
        logging.info(f"成功率：{success_count/len(items)*100:.2f}%")
        logging.info(f"日志文件：{log_filename}")
        logging.info("=" * 80)
        
        # 打印摘要到控制台
        print(f"\n{'='*80}")
        print(f"处理完成！")
        print(f"总计：{len(items)} 条 | 成功：{success_count} 条 | 失败：{fail_count} 条")
        print(f"日志文件：{log_filename}")
        print(f"{'='*80}")
        
        # 保存失败记录到文件（包含完整的请求参数和响应）
        if fail_count > 0:
            fail_log_file = log_filename.replace('.log', '_failed.txt')
            with open(fail_log_file, 'w', encoding='utf-8') as f:
                f.write("失败记录详情\n")
                f.write("=" * 80 + "\n\n")
                for result in results:
                    if not result['success']:
                        f.write(f"OE: {result['oe_number']}\n")
                        f.write(f"品牌：{result['brand']}\n")
                        f.write(f"品牌代码：{result['brand_code']}\n")
                        f.write(f"工作表：{result['sheet_name']}\n")
                        f.write(f"请求参数：{json.dumps(result['request_params'], ensure_ascii=False, indent=2)}\n")
                        f.write(f"完整响应：{json.dumps(result['response'], ensure_ascii=False, indent=2) if result['response'] else '无响应'}\n")
                        f.write(f"错误原因：{result['error']}\n")
                        f.write("-" * 80 + "\n\n")
            logging.info(f"失败记录已保存到：{fail_log_file}")
        
    except Exception as e:
        logging.error(f"程序执行失败：{e}", exc_info=True)
        print(f"错误：{e}")


if __name__ == '__main__':
    main()
