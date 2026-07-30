# -*- coding: utf-8 -*-
"""
卓之星同步模块配置

包含供应商配置、API配置等信息
"""

# 卓之星API基础配置
API_BASE_URL = "http://api.inheartsoft.com/dw-api/kc2018"
API_PSIGN = "7be06d54152d0bd916f09b0b055f76ad"

# 供应商配置
SUPPLIERS = {
    '广星': {
        'name': '广星',
        'gsign': '9F478C130BCD573232B129C5928F0B42',
        'description': '广星供应商库存数据'
    },
    '鑫峰': {
        'name': '鑫峰',
        'gsign': 'B810A2A5ABAE10EAEE19B3BE563B24A9',
        'description': '鑫峰供应商库存数据'
    },
    '佛山万拓': {
        'name': '佛山万拓',
        'gsign': 'EFA9CC150A42AA1AAD67B069606C3B71',
        'description': '佛山万拓供应商库存数据'
    },
    '盛旻': {
        'name': '盛旻',
        'gsign': '925A988C98A919C18C1D393F85A693A5',
        'description': '盛旻供应商库存数据'
    }
}

# 数据库表名
DB_TABLE_NAME = 'zhuozhixing_inventory'

# 字段映射配置（API字段 -> 数据库字段）
# 与原Excel导出保持一致
FIELD_MAPPING = {
    "pjid": "配件ID",
    "pjcode": "零件编码",
    "pjoemcode": "制造编码",
    "pjname": "零件名称",
    "pjename": "零件英文名称",
    "pjsize": "零件车型",
    "pjfactory": "产地",
    "xsprice": "价格",
    "kcamount": "库存数",
    "pjpp": "零件品牌",
    "pjbrand": "品牌",
    "ppcode": "品牌编码",
    "gxcode": "公会编码",
    "pjgensize": "通用车型",
    "hhcode": "互换码",
    "Isgx": "是否共享",
    "kcid": "商家库存表自增ID",
    "kcdepot": "库号",
    "sxpfprice": "sxpfprice",
    "openprice1": "openprice1"
}

# 数据库字段列表（按顺序）
DB_FIELDS = [
    'supplier_name',
    '配件ID',
    '零件编码',
    '制造编码',
    '零件名称',
    '零件英文名称',
    '零件车型',
    '产地',
    '价格',
    '库存数',
    '零件品牌',
    '品牌',
    '品牌编码',
    '公会编码',
    '通用车型',
    '互换码',
    '是否共享',
    '商家库存表自增ID',
    '库号',
    'sxpfprice',
    'openprice1'
]

# 批量插入批次大小
BATCH_SIZE = 1000

# 请求重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1  # 秒
