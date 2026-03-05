"""
CRM Excel 文件处理模块
支持两列模式 (oe+brand) 和三列模式 (oe+brand+brand_code)
"""

import pandas as pd
import os
from concurrent.futures import ThreadPoolExecutor, as_completed


def identify_columns(df):
    """
    自动识别 Excel 中的关键列（两列模式）
    oe 列：oe, OE, 物料条码，barcode
    brand 列：brand, 品牌，品牌名称
    """
    oe_columns = ['oe', 'OE', 'barcode']
    brand_columns = ['brand', '品牌']
    
    oe_col = None
    brand_col = None
    
    # 转换列名为小写进行匹配
    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))
    
    # 查找 oe 列
    for oe_key in oe_columns:
        oe_key_lower = oe_key.lower()
        if oe_key_lower in columns_lower:
            oe_col = column_mapping[oe_key_lower]
            break
    
    # 查找 brand 列
    for brand_key in brand_columns:
        brand_key_lower = brand_key.lower()
        if brand_key_lower in columns_lower:
            brand_col = column_mapping[brand_key_lower]
            break
    
    if oe_col is None:
        raise ValueError("未找到 oe 列，请确保列名为：oe, OE, 物料条码，barcode 之一")
    
    if brand_col is None:
        raise ValueError("未找到 brand 列，请确保列名为：brand, 品牌，品牌名称之一")
    
    return oe_col, brand_col


def identify_columns_extended(df):
    """
    扩展的列识别函数，支持识别 brand_code 列（三列模式）
    oe 列：oe, OE, 物料条码，barcode
    brand 列：brand, 品牌，品牌名称
    brand_code 列：brand_code, 条码，物料条码
    """
    oe_columns = ['oe', 'OE', 'barcode']
    brand_columns = ['brand', '品牌']
    brand_code_columns = ['brand_code', '条码', '物料条码']
    
    oe_col = None
    brand_col = None
    brand_code_col = None
    
    # 转换列名为小写进行匹配
    columns_lower = [str(col).lower().strip() for col in df.columns]
    column_mapping = dict(zip(columns_lower, df.columns))
    
    # 查找 oe 列
    for oe_key in oe_columns:
        oe_key_lower = oe_key.lower()
        if oe_key_lower in columns_lower:
            oe_col = column_mapping[oe_key_lower]
            break
    
    # 查找 brand 列
    for brand_key in brand_columns:
        brand_key_lower = brand_key.lower()
        if brand_key_lower in columns_lower:
            brand_col = column_mapping[brand_key_lower]
            break
    
    # 查找 brand_code 列
    for brand_code_key in brand_code_columns:
        brand_code_key_lower = brand_code_key.lower()
        if brand_code_key_lower in columns_lower:
            brand_code_col = column_mapping[brand_code_key_lower]
            break
    
    if oe_col is None:
        raise ValueError("未找到 oe 列，请确保列名为：oe, OE, 物料条码，barcode 之一")
    
    if brand_col is None:
        raise ValueError("未找到 brand 列，请确保列名为：brand, 品牌，品牌名称之一")
    
    # brand_code 列是可选的
    return oe_col, brand_col, brand_code_col


def add_result_column(df, results_dict, oe_col):
    """
    在 DataFrame 末尾添加"新建结果"列
    """
    # 创建结果列，初始化为空字符串
    df['新建结果'] = ''
    
    # 根据 oe_code 填充结果
    for index, row in df.iterrows():
        oe_code = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        if oe_code in results_dict:
            df.at[index, '新建结果'] = results_dict[oe_code]
    
    return df


def filter_sheets_by_mode(all_sheets, mode):
    """
    根据处理模式筛选符合条件的工作表
    """
    valid_sheets = {}
    for sheet_name, df in all_sheets.items():
        try:
            if mode == 'two_column':
                # 检查是否符合两列模式
                oe_col, brand_col = identify_columns(df)
                valid_sheets[sheet_name] = {
                    'df': df,
                    'columns': (oe_col, brand_col)
                }
                print(f"工作表 '{sheet_name}' 符合两列模式：oe 列={oe_col}, brand 列={brand_col}")
            else:  # three_column
                # 检查是否符合三列模式
                oe_col, brand_col, brand_code_col = identify_columns_extended(df)
                if brand_code_col:  # 必须有 brand_code 列
                    valid_sheets[sheet_name] = {
                        'df': df,
                        'columns': (oe_col, brand_col, brand_code_col)
                    }
                    print(f"工作表 '{sheet_name}' 符合三列模式：oe 列={oe_col}, brand 列={brand_col}, brand_code 列={brand_code_col}")
                else:
                    print(f"工作表 '{sheet_name}' 不符合三列模式：缺少 brand_code 列")
        except ValueError as e:
            print(f"工作表 '{sheet_name}' 不符合{mode}模式要求：{e}")
            continue
    
    return valid_sheets


def read_excel_file(file_path):
    """
    读取 Excel 文件，返回所有工作表数据
    """
    try:
        print(f"正在读取文件：{file_path}")
        
        if file_path.endswith('.csv'):
            # CSV 文件处理（单个工作表）
            df = pd.read_csv(file_path)
            all_sheets = {'Sheet1': df}
            print("CSV 文件按单个工作表处理")
        elif file_path.endswith(('.xlsx', '.xls')):
            # Excel 文件处理（多个工作表）
            all_sheets = pd.read_excel(file_path, sheet_name=None)
            print(f"读取到 {len(all_sheets)} 个工作表：{list(all_sheets.keys())}")
        else:
            raise ValueError(f"不支持的文件格式：{file_path}")
        
        return all_sheets
        
    except Exception as e:
        print(f"读取 Excel 文件时发生错误：{e}")
        raise e


def prepare_two_column_data(sheet_df, sheet_name):
    """
    准备两列模式的数据
    """
    try:
        # 识别两列模式的列
        oe_col, brand_col = identify_columns(sheet_df)
        
        # 准备处理数据
        items = []
        for index, row in sheet_df.iterrows():
            oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            
            if oe_number and brand:
                items.append({
                    'index': index,
                    'oe_number': oe_number,
                    'brand': brand,
                    'sheet_name': sheet_name,
                    'mode': 'two_column'
                })
        
        return items
    except Exception as e:
        print(f"准备两列模式数据时出错：{e}")
        return None


def prepare_three_column_data(sheet_df, sheet_name):
    """
    准备三列模式的数据
    """
    try:
        # 识别三列模式的列
        oe_col, brand_col, brand_code_col = identify_columns_extended(sheet_df)
        
        if brand_code_col is None:
            print(f"工作表 {sheet_name} 不符合三列模式要求")
            return None
            
        # 准备处理数据
        items = []
        for index, row in sheet_df.iterrows():
            oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
            brand_code = str(row[brand_code_col]).strip() if pd.notna(row[brand_code_col]) else ''
            
            if oe_number and brand:
                items.append({
                    'index': index,
                    'oe_number': oe_number,
                    'brand': brand,
                    'brand_code': brand_code,
                    'sheet_name': sheet_name,
                    'mode': 'three_column'
                })
        
        return items
    except Exception as e:
        print(f"准备三列模式数据时出错：{e}")
        return None


def save_results_to_excel(results, original_file_path):
    """
    将处理结果保存到 Excel 文件
    """
    try:
        # 读取原始文件
        all_sheets = pd.read_excel(original_file_path, sheet_name=None)
        
        # 为每个工作表添加结果列
        for sheet_name, df in all_sheets.items():
            df['处理结果'] = ''
            for index, row in df.iterrows():
                # 根据不同的列识别方式找到 oe_code
                oe_cols = ['oe', 'oe_code', 'OE', 'OE 编号', '零件号']
                oe_value = None
                
                for col in oe_cols:
                    if col in df.columns:
                        oe_value = str(row[col]).strip() if pd.notna(row[col]) else ''
                        break
                
                if oe_value and oe_value in results:
                    df.at[index, '处理结果'] = results[oe_value]
        
        # 生成输出文件路径
        base_name = os.path.splitext(original_file_path)[0]
        output_file_path = base_name + '_处理结果.xlsx'
        
        # 保存文件
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            for sheet_name, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return output_file_path
        
    except Exception as e:
        print(f"保存结果到 Excel 时出错：{e}")
        return None


def process_single_sheet_batch(session, sheet_info, mode, process_func):
    """
    处理单个工作表（并发版本）
    
    Args:
        session: requests session 对象
        sheet_info: 工作表信息（包含 df 和 columns）
        mode: 处理模式 ('two_column' 或 'three_column')
        process_func: 处理单个项目的函数
    
    Returns:
        results_dict: 处理结果字典
    """
    df = sheet_info['df']
    columns = sheet_info['columns']
    
    if mode == 'two_column':
        oe_col, brand_col = columns
    else:
        oe_col, brand_col, brand_code_col = columns
    
    results_dict = {}
    
    # 准备处理数据
    processing_items = []
    for index, row in df.iterrows():
        oe_number = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
        brand = str(row[brand_col]).strip() if pd.notna(row[brand_col]) else ''
        brand_code = str(row[brand_code_col]).strip() if pd.notna(row.get('brand_code_col', '')) else '' if mode == 'three_column' else ''
        
        if oe_number and brand:
            item = {
                'index': index,
                'oe_number': oe_number,
                'brand': brand,
                'row': row
            }
            if mode == 'three_column':
                item['brand_code'] = brand_code
                item['mode'] = 'three_column'
            else:
                item['mode'] = 'two_column'
            
            processing_items.append(item)
    
    # 使用线程池并发处理
    max_workers = min(10, len(processing_items))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_item = {
            executor.submit(process_func, session, item): item 
            for item in processing_items
        }
        
        # 收集结果
        completed_count = 0
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                result = future.result()
                results_dict[item['oe_number']] = result
                completed_count += 1
                print(f"工作表处理进度：{completed_count}/{len(processing_items)} - OE: {item['oe_number']}, 结果：{result}")
            except Exception as e:
                print(f"工作表处理 OE: {item['oe_number']} 时发生异常：{e}")
                results_dict[item['oe_number']] = f"失败 - {str(e)}"
    
    return results_dict
