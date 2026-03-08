"""
Excel 数据加载和匹配模块
负责读取 crm可用别名.xlsx 和 产品名称.xlsx，提供数据匹配功能
"""

import os
import sys
import pandas as pd


# 全局缓存
_alias_df = None
_product_df = None


def _get_project_root():
    """获取项目根目录"""
    # 尝试多种方式找到项目根目录
    current_file = os.path.abspath(__file__)
    
    # 方式1: 根据当前文件位置向上回溯
    # crm_productAdd/excel_data_loader.py -> crm_productAdd -> crm_product -> utils -> app -> project_root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))
    
    # 检查是否正确（通过检查 static 目录是否存在）
    static_path = os.path.join(project_root, "static", "excel")
    if os.path.exists(static_path):
        return project_root
    
    # 方式2: 尝试从 sys.path 中找到项目根目录
    for path in sys.path:
        static_path = os.path.join(path, "static", "excel")
        if os.path.exists(static_path):
            return path
    
    # 方式3: 使用当前工作目录
    cwd = os.getcwd()
    static_path = os.path.join(cwd, "static", "excel")
    if os.path.exists(static_path):
        return cwd
    
    # 默认返回方式1的结果
    return project_root


def load_alias_data():
    """
    加载 crm可用别名.xlsx
    返回 DataFrame 或 None
    """
    global _alias_df
    
    if _alias_df is not None:
        return _alias_df
    
    try:
        project_root = _get_project_root()
        alias_file_path = os.path.join(project_root, "static", "excel", "crm可用别名.xlsx")
        
        if not os.path.exists(alias_file_path):
            raise FileNotFoundError(f"找不到别名文件: {alias_file_path}")
        
        _alias_df = pd.read_excel(alias_file_path)
        print("crm可用别名数据加载完成")
        return _alias_df
    except Exception as e:
        print(f"读取 crm可用别名.xlsx 时发生错误: {e}")
        return None


def load_product_data():
    """
    加载 产品名称.xlsx
    返回 DataFrame 或 None
    """
    global _product_df
    
    if _product_df is not None:
        return _product_df
    
    try:
        project_root = _get_project_root()
        product_file_path = os.path.join(project_root, "static", "excel", "产品名称.xlsx")
        
        if not os.path.exists(product_file_path):
            raise FileNotFoundError(f"找不到产品名称文件: {product_file_path}")
        
        _product_df = pd.read_excel(product_file_path)
        _product_df['cxbianma'] = _product_df['cxbianma'].astype(str).str.strip()
        print("产品名称数据加载完成")
        return _product_df
    except Exception as e:
        print(f"读取 产品名称.xlsx 时发生错误: {e}")
        return None


def find_brand_by_alias(brand, verbose=True):
    """
    根据品牌别名查找正确的品牌名称
    在 pp_names 列中查找匹配，返回对应的 pp_name
    
    Args:
        brand: 品牌名称
        verbose: 是否打印日志，默认为 True
    """
    alias_df = load_alias_data()
    if alias_df is None:
        return brand
    
    if 'pp_names' not in alias_df.columns or 'pp_name' not in alias_df.columns:
        return brand
    
    # 第一轮：精确匹配
    for idx, pp_name_value in enumerate(alias_df['pp_names']):
        pp_name_str = str(pp_name_value).strip()
        aliases = [alias.strip() for alias in pp_name_str.split(',') if alias.strip()]
        for alias in aliases:
            if alias == brand:
                correct_brand = str(alias_df.iloc[idx]['pp_name']).strip()
                print(f"品牌 '{brand}' 精确匹配到别名 '{alias}'，使用正确品牌名: '{correct_brand}'")
                return correct_brand
    
    # 第二轮：包含匹配（别名长度至少3个字符，且不能是子串匹配）
    for idx, pp_name_value in enumerate(alias_df['pp_names']):
        pp_name_str = str(pp_name_value).strip()
        aliases = [alias.strip() for alias in pp_name_str.split(',') if alias.strip()]
        for alias in aliases:
            # 别名至少3个字符，且品牌名包含别名（不是子串匹配）
            if len(alias) >= 3 and (brand in alias or alias in brand):
                # 额外检查：避免 "BS" 匹配 "ABS" 这种情况
                # 如果品牌名比别名长很多，可能是误匹配
                if len(brand) <= len(alias) + 5:  # 允许一定长度差异
                    correct_brand = str(alias_df.iloc[idx]['pp_name']).strip()
                    print(f"品牌 '{brand}' 模糊匹配到别名 '{alias}'，使用正确品牌名: '{correct_brand}'")
                    return correct_brand
    
    print(f"品牌 '{brand}' 在别名表中未找到匹配项")
    return brand


def find_product_name_by_oe(oe_number):
    """
    根据 OE 码查找产品名称
    匹配 cxbianma 列，返回 mingcheng
    """
    product_df = load_product_data()
    if product_df is None:
        return None
    
    product_match = product_df[product_df['cxbianma'] == oe_number]
    
    if not product_match.empty:
        product_name = product_match.iloc[0]['mingcheng'].strip()
        print(f"OE: {oe_number}, Product Name: {product_name}")
        return product_name
    else:
        print(f"OE: {oe_number}, 未在产品名称.xlsx 中找到匹配记录")
        return None


def find_best_match_product(product_name, name_list):
    """
    从 name_list 中查找最佳匹配的产品名称
    匹配策略：精确匹配 → 模糊匹配 → 逐步缩短名称匹配
    """
    if not name_list:
        return None
    
    # 1. 精确匹配
    for item in name_list:
        item_name = item.get("product_name", "").strip()
        if item_name == product_name:
            return item
    
    # 2. 模糊匹配
    for item in name_list:
        item_name = item.get("product_name", "").strip()
        if product_name in item_name or item_name in product_name:
            return item
    
    # 3. 逐步缩短名称匹配
    search_name = product_name
    while len(search_name) > 1:
        for item in name_list:
            item_name = item.get("product_name", "").strip()
            if search_name in item_name or item_name in search_name:
                return item
        search_name = search_name[:-1]
    
    # 返回第一个结果
    return name_list[0] if name_list else None


def clear_cache():
    """
    清除数据缓存，强制下次重新加载
    """
    global _alias_df, _product_df
    _alias_df = None
    _product_df = None
    print("Excel 数据缓存已清除")
