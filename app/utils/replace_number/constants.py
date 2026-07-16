"""
更新替换号模块常量
"""

# 原厂品牌集合，这些品牌必须同时匹配 OE 和品牌
ORIGINAL_BRANDS = {"原厂", "原厂国内4S件"}

# CRM 接口地址
CRM_PRODUCT_LIST_URL = "https://crm.gzbbr.com/api/Product.Product/list"
UPDATE_NUMBER_URL = "https://crm.gzbbr.com/api/Product.Product/updateNumber"

# 重试次数
RETRY_TIMES = 2

# 搜索每页数量
SEARCH_LIMIT = 200

# Excel 列名候选
OE_COLUMN_CANDIDATES = ["oe", "OE", "物料条码", "barcode"]
BRAND_COLUMN_CANDIDATES = ["brand", "品牌", "品牌名称"]
REPLACE_NUMBER_COLUMN_CANDIDATES = ["替换号", "replace_number"]
