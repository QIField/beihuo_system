# -*- coding: utf-8 -*-
"""
物料在途库存同步 - 配置

接口：GET https://openapi.gzbbr.com/Product.ProductStock/getInTransitStockList
认证：请求头 token，复用 B2B 平台令牌（由 openapi_gzbbr_token_task 每6小时自动刷新）
"""

# 接口地址
API_URL = "https://openapi.gzbbr.com/Product.ProductStock/getInTransitStockList"

# token 在 beihuo_system_config 表中的 config_key
# 保留单公司兼容入口
TOKEN_CONFIG_KEY = 'openapi_gzbbr_com_fs'

# 五家公司 token 配置（公司代码 -> config_key）
COMPANY_TOKEN_CONFIGS = [
    {'company': 'fsbbr', 'token_config_key': 'openapi_gzbbr_com_fs'},
    {'company': 'zhbbr', 'token_config_key': 'openapi_gzbbr_com_zh'},
    {'company': 'zsbbr', 'token_config_key': 'openapi_gzbbr_com_zs'},
    {'company': 'dgby', 'token_config_key': 'openapi_gzbbr_com_by'},
    {'company': 'dghf', 'token_config_key': 'openapi_gzbbr_com_hf'},
]

# 请求超时（连接超时, 读取超时），单位秒
REQUEST_TIMEOUT = (10, 30)

# 网络异常重试次数与间隔（秒）
RETRY_TIMES = 3
RETRY_INTERVAL = 5

# 批量插入每批条数
BATCH_SIZE = 500
