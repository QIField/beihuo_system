# -*- coding:utf-8 -*-
# @Time    : 2026/4/23 09:09
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : excel_data_loader_services.py
# @Software: PyCharm

import os
import pandas as pd
from app.models.orm_models import AccountReceivableList
from app.utils.orm import orm_session


def load_account_receivable_excel(file_path):
    """
    读取应收单Excel文件并返回DataFrame
    
    :param file_path: Excel文件路径
    :return: DataFrame 或 None
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"找不到文件: {file_path}")
        
        # 检查文件扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.xlsx', '.xls']:
            raise ValueError(f"文件格式不支持: {ext}，请使用 .xlsx 或 .xls 格式的Excel文件")
        
        # 读取Excel文件，指定engine以避免格式检测问题
        if ext == '.xlsx':
            df = pd.read_excel(file_path, engine='openpyxl')
        else:
            df = pd.read_excel(file_path, engine='xlrd')
        
        return df
    except Exception as e:
        print(f"读取Excel文件时发生错误: {e}")
        return None


def load_account_receivable_excel_from_file(file_obj, filename):
    """
    从文件对象读取应收单Excel文件并返回DataFrame
    
    :param file_obj: 文件对象
    :param filename: 文件名（用于判断文件格式）
    :return: DataFrame 或 None
    """
    try:
        # 检查文件扩展名
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ['.xlsx', '.xls']:
            raise ValueError(f"文件格式不支持: {ext}，请使用 .xlsx 或 .xls 格式的Excel文件")
        
        # 读取Excel文件，指定engine以避免格式检测问题
        if ext == '.xlsx':
            df = pd.read_excel(file_obj, engine='openpyxl')
        else:
            df = pd.read_excel(file_obj, engine='xlrd')
        
        return df
    except Exception as e:
        print(f"读取Excel文件时发生错误: {e}")
        return None


def process_excel_data(df):
    """
    处理Excel数据，转换为数据库字段格式
    
    :param df: 原始DataFrame
    :return: 处理后的数据字典列表
    """
    if df is None or df.empty:
        return []
    
    data_list = []
    
    # Excel列名映射到数据库字段名
    column_mapping = {
        '业务日期': 'business_date',
        '到期日': 'due_date',
        '单据编号': 'receipt_no',
        '单据状态': 'receipt_status',
        '客户': 'customer_name',
        '价税合计': 'tax_total_amount',
        '总金额': 'total_amount',
        '已收款金额': 'received_amount',
        '客户编码': 'customer_code',
        '收款条件': 'payment_terms',
        '收款组织': 'payment_org',
        '销售员': 'salesperson',
        '备注': 'remark',
        '客户分组': 'customer_group',
        '创建人': 'creator',
        '创建日期': 'create_date',
        '支付类型': 'payment_type'
    }
    
    for _, row in df.iterrows():
        data = {}
        for excel_col, db_col in column_mapping.items():
            if excel_col in row:
                value = row[excel_col]
                # 处理NaN值
                if pd.isna(value):
                    # 金额字段为空时赋值为0
                    if db_col in ['tax_total_amount', 'total_amount', 'received_amount']:
                        value = 0.0
                    else:
                        value = None
                # 处理金额字段，确保是数值类型
                if db_col in ['tax_total_amount', 'total_amount', 'received_amount']:
                    if value is not None:
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            value = 0.0
                # 处理字符串类型，去除首尾空格
                if isinstance(value, str):
                    value = value.strip()
                data[db_col] = value
        data_list.append(data)
    
    return data_list


def save_account_receivable_to_db(data_list, upsert=True):
    """
    将应收单数据保存到数据库
    
    :param data_list: 数据字典列表
    :param upsert: 是否使用upsert模式（存在则更新，不存在则插入）
    :return: 处理的记录数
    """
    if not data_list:
        return 0
    
    try:
        with orm_session() as session:
            if upsert:
                AccountReceivableList.bulk_upsert(session, data_list)
            else:
                AccountReceivableList.bulk_insert(session, data_list)
            return len(data_list)
    except Exception as e:
        print(f"保存数据到数据库时发生错误: {e}")
        raise


def import_account_receivable_excel(file_path, upsert=True):
    """
    完整的导入流程：读取Excel -> 处理数据 -> 保存到数据库
    
    :param file_path: Excel文件路径
    :param upsert: 是否使用upsert模式
    :return: 处理的记录数
    """
    # 1. 读取Excel
    df = load_account_receivable_excel(file_path)
    if df is None:
        return 0
    
    # 2. 处理数据
    data_list = process_excel_data(df)
    if not data_list:
        return 0
    
    # 3. 保存到数据库
    count = save_account_receivable_to_db(data_list, upsert=upsert)
    
    return count


def get_unbackfilled_statistics():
    """
    获取未回填 partner_id 的统计信息
    
    :return: {total: 总记录数, unbackfilled: 未回填数}
    """
    with orm_session() as session:
        # 总记录数
        total = session.query(AccountReceivableList).count()
        
        # 未回填数
        unbackfilled = AccountReceivableList.get_unbackfilled_count(session)
        
        return {
            "total": total,
            "unbackfilled": unbackfilled,
            "backfilled": total - unbackfilled
        }


def execute_partner_id_backfill():
    """
    执行 partner_id 数据回填
    
    :return: {backfilled_count: 回填成功数, statistics: 回填前后的统计信息}
    """
    # 回填前的统计
    before_stats = get_unbackfilled_statistics()
    
    # 执行回填
    with orm_session() as session:
        backfilled_count = AccountReceivableList.backfill_partner_id(session)
    
    # 回填后的统计
    after_stats = get_unbackfilled_statistics()
    
    return {
        "backfilled_count": backfilled_count,
        "before": before_stats,
        "after": after_stats
    }


def import_and_backfill_excel(file_path, upsert=True):
    """
    导入Excel并自动执行数据回填（完整流程）
    
    :param file_path: Excel文件路径
    :param upsert: 是否使用upsert模式
    :return: {import_count: 导入数, backfill_result: 回填结果}
    """
    result = {
        "import_count": 0,
        "backfill_result": None
    }
    
    # 导入Excel
    result["import_count"] = import_account_receivable_excel(file_path, upsert=upsert)
    
    # 必须执行回填
    result["backfill_result"] = execute_partner_id_backfill()
    
    return result


def import_and_backfill_excel_from_file(file_obj, filename, upsert=True):
    """
    从文件对象导入Excel并自动执行数据回填（完整流程）
    
    :param file_obj: 文件对象
    :param filename: 文件名
    :param upsert: 是否使用upsert模式
    :return: {import_count: 导入数, backfill_result: 回填结果}
    """
    result = {
        "import_count": 0,
        "backfill_result": None
    }
    
    # 1. 读取Excel
    df = load_account_receivable_excel_from_file(file_obj, filename)
    if df is None:
        return result
    
    # 2. 处理数据
    data_list = process_excel_data(df)
    if not data_list:
        return result
    
    # 3. 保存到数据库
    result["import_count"] = save_account_receivable_to_db(data_list, upsert=upsert)
    
    # 4. 必须执行回填
    result["backfill_result"] = execute_partner_id_backfill()
    
    return result
