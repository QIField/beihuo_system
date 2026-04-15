"""
开思商家平台接口配置

包含接口URL、请求头、默认参数等配置信息
"""

# 基础配置
BASE_URL = "https://www.cassmall.com"

# 接口路径配置
API_ENDPOINTS = {
    # 接口1：每日事件总数统计
    "event_summary": "/merchant/seller/merchant/alarm/all/Statistics",
    # 接口2：每日事件详情
    "event_detail": "/merchant/seller/merchant/alarm/Statistics",
    # 接口3：经营分析概览
    "business_indicator": "/merchant/seller/operation/analysis/view/OVERVIEW",
}

# 默认请求头
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://www.cassmall.com",
    "Referer": "https://www.cassmall.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# 接口3的默认请求体
DEFAULT_BUSINESS_INDICATOR_PAYLOAD = {
    "searchType": "D",
    "carBrandIds": [],
    "provinceIds": [],
    "cityIds": [],
    "areaIds": [],
    "firstCatIds": [],
    "secondCatIds": []
}

# 指标字段映射（接口3的indicator名称 -> 数据库字段名）
INDICATOR_FIELD_MAPPING = {
    "销售额(元)": "sales_amount",
    "系统报价成交额比例(%)": "system_quote_rate",
    "下单客户数(个)": "order_customer_count",
    "总报出率(%)": "total_quote_rate",
    "系统报出率(%)": "system_quote_rate_detail",
    "人工报出率(%)": "manual_quote_rate",
    "整单报出率(%)": "whole_order_quote_rate",
    "现货报出率(%)": "spot_quote_rate",
    "报出转化率(%)": "quote_conversion_rate",
    "系统报出转化率(%)": "system_quote_conversion_rate",
    "平均报出品质数(个)": "avg_quote_quality_count",
    "退货SKU数(个)": "return_sku_count",
    "SKU退货率(%)": "sku_return_rate",
    "退货金额(元)": "return_amount",
    "金额退货率(%)": "amount_return_rate",
}

# 日期字段映射（date1-date7对应的实际日期偏移）
# 需要根据heads中的日期动态解析，这里仅作占位
DATE_FIELD_MAPPING = {
    "date1": 0,  # 第1天
    "date2": 1,  # 第2天
    "date3": 2,  # 第3天
    "date4": 3,  # 第4天
    "date5": 4,  # 第5天
    "date6": 5,  # 第6天
    "date7": 6,  # 第7天
}
