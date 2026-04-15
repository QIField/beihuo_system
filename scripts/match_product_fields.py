"""
产品字段匹配脚本
通过OE+品牌+company从数据库查询匹配产品名称、车型、替换号、销量、产品等级
同时匹配三个价格表（万景、塞得、QY）的价格

使用方法:
    python match_product_fields.py

配置说明:
    修改下方的 DEFAULT_CONFIG 配置区即可
"""

import pandas as pd
import sys
import os
import argparse
from typing import Optional, Dict

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.utils.database_connection import db_query_one


# ==================== 配置区 ====================
DEFAULT_CONFIG = {
    # 主文件配置
    'input_file': r'G:\work\work_documents\414促销下单.xls',
    'brand': '原厂',
    'company': 'fsbbr',
    'oe_col': '编码',  # 主文件中OE编码的列名
    
    # 价格表配置
    'price_files': {
        '万景': {
            'path': r'G:\work\work_documents\万景.xlsx',
            'oe_col': '原厂号',
            'price_col': '价格'
        },
        '塞得': {
            'path': r'G:\work\work_documents\塞得.xlsx',
            'oe_col': '促销零件号\xa0\xa0\xa0\xa0\xa0 (Promotion part number)',
            'price_col': '价格'
        },
        'QY': {
            'path': r'G:\work\work_documents\QY.xlsx',
            'oe_col': '促销零件号',
            'price_col': '现金采购价'
        },
        'HY': {
            'path': r'G:\work\work_documents\414促销定货.xlsx',
            'oe_col': '促销零件号\xa0\xa0\xa0\xa0\xa0 (Promotion part number)',
            'price_col': '促销价'
        }
    }
}
# ==================== 配置区结束 ====================


def load_price_data(file_config: Dict) -> Dict[str, str]:
    """
    加载价格表数据，返回 {oe: price} 字典
    
    Args:
        file_config: 文件配置，包含 path, oe_col, price_col
    
    Returns:
        价格字典 {oe: price}
    """
    path = file_config['path']
    oe_col = file_config['oe_col']
    price_col = file_config['price_col']
    
    if not os.path.exists(path):
        print(f"  警告: 价格表不存在: {path}")
        return {}
    
    try:
        # 读取价格表
        if path.endswith('.csv'):
            df = pd.read_csv(path, dtype=str)
        else:
            df = pd.read_excel(path, dtype=str)
        
        # 检查列是否存在
        if oe_col not in df.columns:
            print(f"  警告: 价格表中未找到编码列 '{oe_col}'")
            print(f"  可用列: {list(df.columns)}")
            return {}
        
        if price_col not in df.columns:
            print(f"  警告: 价格表中未找到价格列 '{price_col}'")
            print(f"  可用列: {list(df.columns)}")
            return {}
        
        # 构建价格字典
        price_dict = {}
        for _, row in df.iterrows():
            oe = str(row[oe_col]).strip() if pd.notna(row[oe_col]) else ''
            price = str(row[price_col]).strip() if pd.notna(row[price_col]) else ''
            if oe:
                price_dict[oe] = price
        
        print(f"  成功加载 {len(price_dict)} 条价格数据")
        return price_dict
        
    except Exception as e:
        print(f"  错误: 加载价格表失败: {e}")
        return {}


def get_product_fields_from_db(oe: str, brand: str, company: str = 'fsbbr') -> Optional[dict]:
    """
    通过OE+品牌+company从数据库查询产品字段
    从crmapp_compare_summary取基本信息，从crmapp_beihuo取销量数据
    
    Args:
        oe: OE编码
        brand: 品牌名称
        company: 公司代码，默认'fsbbr'
    
    Returns:
        包含产品字段的字典，如果没找到返回None
    """
    # 1. 从crmapp_compare_summary取基本信息
    sql_basic = """
        SELECT 
            product_name AS 名称,
            l_model_zh AS 车型,
            replace_number AS 替换号,
            product_level AS 产品等级
        FROM crmapp_compare_summary
        WHERE oe = %s AND brand = %s AND company = %s
        LIMIT 1
    """
    result_basic = db_query_one(sql_basic, (oe, brand, company), dict_cursor=True)
    
    if not result_basic:
        return None
    
    # 2. 从crmapp_beihuo取销量数据
    sql_sales = """
        SELECT 
            `今日销量` AS 今日销量,
            `昨日销量` AS 昨日销量,
            `近7天销量` AS 近7天销量,
            `本月销量` AS 近1个月销量,
            `近6个月销量` AS 近6个月销量,
            `近12个月销量` AS 近12个月销量
        FROM crmapp_beihuo
        WHERE oe = %s AND 品牌 = %s
        LIMIT 1
    """
    result_sales = db_query_one(sql_sales, (oe, brand), dict_cursor=True)
    
    # 合并结果
    result = result_basic.copy()
    if result_sales:
        result.update(result_sales)
    else:
        # 如果beihuo表没有数据，销量字段设为0
        result.update({
            '今日销量': 0,
            '昨日销量': 0,
            '近7天销量': 0,
            '近1个月销量': 0,
            '近6个月销量': 0,
            '近12个月销量': 0
        })
    
    return result


def identify_oe_column(df: pd.DataFrame, custom_col: Optional[str] = None) -> str:
    """
    自动识别OE编码列
    
    Args:
        df: DataFrame
        custom_col: 用户指定的列名
    
    Returns:
        OE列名
    """
    if custom_col and custom_col in df.columns:
        return custom_col
    
    # 可能的OE列名
    oe_candidates = ['oe', 'OE', '编码', '零件号', 'number', 'OE号', 'oe_code', 'OE编码']
    
    columns_lower = {str(col).lower().strip(): col for col in df.columns}
    
    for candidate in oe_candidates:
        if candidate.lower() in columns_lower:
            return columns_lower[candidate.lower()]
    
    # 如果没找到，尝试第一列
    if len(df.columns) > 0:
        first_col = df.columns[0]
        print(f"警告: 未找到OE列，使用第一列 '{first_col}' 作为OE列")
        return first_col
    
    raise ValueError("无法识别OE列，请使用 --oe-col 参数指定")


def process_excel(config: Dict):
    """
    处理Excel文件，匹配数据库字段和价格表
    
    Args:
        config: 配置字典
    """
    input_path = config['input_file']
    brand = config['brand']
    company = config['company']
    oe_col = config['oe_col']
    price_files = config['price_files']
    
    print(f"正在读取主文件: {input_path}")
    
    # 读取主文件
    if input_path.endswith('.csv'):
        df = pd.read_csv(input_path, dtype=str)
    else:
        df = pd.read_excel(input_path, dtype=str)
    
    print(f"读取完成，共 {len(df)} 行数据")
    
    # 识别OE列
    oe_column = identify_oe_column(df, oe_col)
    print(f"OE列识别为: {oe_column}")
    
    # 加载价格表数据
    print("\n正在加载价格表...")
    price_data = {}
    for name, file_config in price_files.items():
        print(f"\n加载 [{name}] 价格表:")
        price_data[name] = load_price_data(file_config)
    
    # 准备新列
    df['名称'] = ''
    df['车型'] = ''
    df['替换号'] = ''
    df['产品等级'] = ''
    df['今日销量'] = ''
    df['昨日销量'] = ''
    df['近7天销量'] = ''
    df['近1个月销量'] = ''
    df['近6个月销量'] = ''
    df['近12个月销量'] = ''
    df['万景'] = ''
    df['塞得'] = ''
    df['QY'] = ''
    df['HY'] = ''
    
    # 匹配数据
    db_matched_count = 0
    price_matched_count = {'万景': 0, '塞得': 0, 'QY': 0, 'HY': 0}
    not_found_list = []
    
    print(f"\n开始匹配数据 (品牌: {brand}, 公司: {company})...")
    
    for idx, row in df.iterrows():
        oe = str(row[oe_column]).strip() if pd.notna(row[oe_column]) else ''
        
        if not oe:
            continue
        
        # 1. 从数据库查询产品字段
        db_result = get_product_fields_from_db(oe, brand, company)
        
        if db_result:
            df.at[idx, '名称'] = db_result.get('名称', '') or ''
            df.at[idx, '车型'] = db_result.get('车型', '') or ''
            df.at[idx, '替换号'] = db_result.get('替换号', '') or ''
            df.at[idx, '产品等级'] = db_result.get('产品等级', '') or ''
            df.at[idx, '今日销量'] = db_result.get('今日销量', '') if db_result.get('今日销量') is not None else ''
            df.at[idx, '昨日销量'] = db_result.get('昨日销量', '') if db_result.get('昨日销量') is not None else ''
            df.at[idx, '近7天销量'] = db_result.get('近7天销量', '') if db_result.get('近7天销量') is not None else ''
            df.at[idx, '近1个月销量'] = db_result.get('近1个月销量', '') if db_result.get('近1个月销量') is not None else ''
            df.at[idx, '近6个月销量'] = db_result.get('近6个月销量', '') if db_result.get('近6个月销量') is not None else ''
            df.at[idx, '近12个月销量'] = db_result.get('近12个月销量', '') if db_result.get('近12个月销量') is not None else ''
            db_matched_count += 1
            db_status = "✓"
        else:
            db_status = "✗"
        
        # 2. 从价格表匹配价格
        price_status = []
        for name in ['万景', '塞得', 'QY', 'HY']:
            if oe in price_data.get(name, {}):
                df.at[idx, name] = price_data[name][oe]
                price_matched_count[name] += 1
                price_status.append(f"{name}✓")
            else:
                price_status.append(f"{name}✗")
        
        # 输出进度
        if db_result or any(oe in price_data.get(name, {}) for name in ['万景', '塞得', 'QY']):
            print(f"  [{idx+1}/{len(df)}] OE: {oe} - 数据库:{db_status}, 价格:{', '.join(price_status)}")
        else:
            not_found_list.append(oe)
            print(f"  [{idx+1}/{len(df)}] OE: {oe} - 未找到任何数据")
    
    # 保存结果
    output_path = input_path.rsplit('.', 1)[0] + '_已匹配.xlsx'
    df.to_excel(output_path, index=False)
    
    # 输出统计
    print("\n" + "="*60)
    print("处理完成!")
    print("="*60)
    print(f"总记录数: {len(df)}")
    print(f"\n数据库匹配:")
    print(f"  匹配成功: {db_matched_count}")
    print(f"\n价格表匹配:")
    for name, count in price_matched_count.items():
        print(f"  {name}: {count}")
    print(f"\n完全未找到: {len(not_found_list)}")
    print(f"输出文件: {output_path}")
    
    if not_found_list:
        print(f"\n未找到的OE列表 (共{len(not_found_list)}个):")
        for oe in not_found_list[:20]:
            print(f"  - {oe}")
        if len(not_found_list) > 20:
            print(f"  ... 还有 {len(not_found_list) - 20} 个")


def main():
    parser = argparse.ArgumentParser(
        description='通过OE+品牌+company从数据库匹配产品字段，并匹配四个价格表（万景、塞得、QY、HY）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用配置区的默认配置直接运行
  python match_product_fields.py
  
  # 或指定主文件路径
  python match_product_fields.py --input G:\\work\\work_documents\\414促销下单.xls
        """
    )
    
    parser.add_argument('--input', help='主文件路径 (可选，默认使用配置区设置)')
    
    args = parser.parse_args()
    
    # 使用配置区的配置
    config = DEFAULT_CONFIG.copy()
    if args.input:
        config['input_file'] = args.input
    
    # 检查主文件是否存在
    if not os.path.exists(config['input_file']):
        print(f"错误: 主文件不存在: {config['input_file']}")
        print(f"请检查配置区的 'input_file' 路径是否正确")
        sys.exit(1)
    
    # 显示配置信息
    print("="*60)
    print("配置信息:")
    print(f"  主文件: {config['input_file']}")
    print(f"  品牌: {config['brand']}")
    print(f"  公司: {config['company']}")
    print(f"  OE列: {config['oe_col']}")
    print("\n价格表:")
    for name, file_config in config['price_files'].items():
        print(f"  {name}: {file_config['path']}")
    print("="*60)
    
    # 处理文件
    try:
        process_excel(config)
    except Exception as e:
        print(f"处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
