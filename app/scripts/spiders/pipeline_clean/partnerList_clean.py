# -*- coding:utf-8 -*-
# @Time    : 2026/4/14 17:49
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : partnerList_clean.py
# @Software: PyCharm
import pandas as pd


def remove_duplicate(data_list):
    # 要保留的字段
    model_fields = [
        'partner_id',           # 合作伙伴id 主键
        'contacts',             # 联系人
        'contacts_phone',       # 联系电话
        'country',              # 国家
        'create_time',          # 创建时间（秒级时间戳）
        'currency_name',        # 货币名称
        'fullname',             # 全名
        'is_disabled',          # 是否禁用
        'language_types',       # 语言类型
        'level_name',           # 客户等级（临时字段，将转换为 level_id）
        'orderTimes',           # 订单统计（份）
        'payment_description',  # 付款说明
        'payment_method',       # 付款方式
        'real_name',            # 所属业务员
        'region',               # 区域
        'remenber_code',        # 
        'sap_no',               # 
        'short_name',           # 
        'street',               # 街道
        'upload_sap',           # 
        'user_name'             # 创建人
    ]


    # 初始化空的 DataFrame（冗余代码，保留原格式）
    # df = pd.DataFrame()
    # 将数据列表转换为 DataFrame
    df = pd.DataFrame(data_list)
    # print("+",data_list)
    # 删除 partner_id 为空的记录，使用 copy() 避免 SettingWithCopyWarning
    df = df.dropna(subset=['partner_id']).copy()



    # 先选择需要的字段
    df = df[model_fields]

    # 把空字符串、空白、None 全部替换成 0
    df['orderTimes'] = df['orderTimes'].replace(['', None], 0)
    df['is_disabled'] = df['is_disabled'].replace(['', None], -1)
    df['create_time'] = df['create_time'].replace(['', None], 0)

    # 将 level_name 复制命名为 level_id
    df['level_id'] = df['level_name'].copy()
  

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')

    # 返回过滤后的订单数据列表，供调用者进行入库操作
    return clean_data_list