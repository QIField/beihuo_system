import pandas as pd
import os


def load_alias_data():
    """全局加载crm可用别名数据"""
    try:
        # 使用基于__file__的绝对路径计算
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        alias_file_path = os.path.join(project_root, "static", "excel", "crm可用别名.xlsx")
        
        # 检查文件是否存在
        if not os.path.exists(alias_file_path):
            raise FileNotFoundError(f"找不到别名文件: {alias_file_path}")
            
        alias_df = pd.read_excel(alias_file_path)
        print("crm可用别名数据加载完成")
        return alias_df
    except Exception as e:
        print(f"读取crm可用别名.xlsx时发生错误: {e}")
        return None


def load_product_data():
    """全局加载产品名称数据"""
    try:
        # 使用基于__file__的绝对路径计算
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        product_file_path = os.path.join(project_root, "static", "excel", "产品名称.xlsx")
        
        # 检查文件是否存在
        if not os.path.exists(product_file_path):
            raise FileNotFoundError(f"找不到产品名称文件: {product_file_path}")
            
        product_df = pd.read_excel(product_file_path)
        # 清理cxbianma列的空白字符
        product_df['cxbianma'] = product_df['cxbianma'].astype(str).str.strip()
        print("产品名称数据加载完成")
        return product_df
    except Exception as e:
        print(f"读取产品名称.xlsx时发生错误: {e}")
        return None


def find_brand_by_alias(brand, alias_df):
    """
    根据别名数据查找正确的品牌名称
    当找不到brand_id时，将brand与Excel文件中pp_names列数据匹配，
    如果brand包含在pp_names中，就用对应的pp_name列数据作为新的brand
    """
    if alias_df is None:
        return brand  # 如果没有别名数据，返回原始品牌名
    
    # 检查pp_names列，看是否包含当前brand
    if 'pp_names' in alias_df.columns and 'pp_name' in alias_df.columns:
        # 遍历pp_names列
        for idx, pp_name_value in enumerate(alias_df['pp_names']):
            pp_name_str = str(pp_name_value).strip()
            # 分割pp_names字符串，因为它是以逗号分隔的多个别名
            aliases = [alias.strip() for alias in pp_name_str.split(',')]
            for alias in aliases:
                if alias in brand or brand in alias:
                    # 找到匹配项，返回对应的pp_name列数据
                    correct_brand = str(alias_df.iloc[idx]['pp_name']).strip()
                    print(f"品牌 '{brand}' 匹配到别名 '{alias}'，使用正确品牌名: '{correct_brand}'")
                    return correct_brand
    
    print(f"品牌 '{brand}' 在别名表中未找到匹配项")
    return brand  # 没有匹配到任何别名


def find_matching_product(product_oe, product_df):
    """
    根据OE码在产品数据中查找匹配的产品
    """
    if product_df is None:
        return None  # 如果没有产品数据，返回None
    
    # 精确匹配cxbianma列与当前oe_number
    product_match = product_df[product_df['cxbianma'] == product_oe]
    
    if not product_match.empty:
        # 获取第一条匹配记录的mingcheng
        product_name = product_match.iloc[0]['mingcheng'].strip()
        print(f"OE: {product_oe}, Product Name: {product_name}")
        return product_name
    else:
        print(f"OE: {product_oe}, 未在产品名称.xlsx中找到匹配记录")
        return None


def get_full_path(relative_path):
    """
    获取项目中的完整路径
    """
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    return os.path.join(project_root, relative_path)


if __name__ == "__main__":
    # 示例：如何使用这些函数
    print("开始加载数据...")
    
    # 加载别名数据
    alias_data = load_alias_data()
    
    # 加载产品数据
    product_data = load_product_data()
    
    # 示例：查找别名
    if alias_data is not None:
        correct_brand = find_brand_by_alias("SomeAlias", alias_data)
        print(f"Corrected brand: {correct_brand}")
    
    # 示例：根据OE码查找产品
    if product_data is not None:
        product_name = find_matching_product("some_oe_code", product_data)
        print(f"Found product: {product_name}")
    
    print("数据加载完成")