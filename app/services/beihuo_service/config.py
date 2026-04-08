"""
备货数据服务配置

集中管理所有配置项，便于维护和修改。
"""

# 门店配置
COMPANIES = ['fsbbr', 'zsbbr', 'zhbbr', 'dgby', 'dghf']

# 门店名称映射
STORES = {
    'fsbbr': '佛山门店',
    'zsbbr': '中山门店',
    'zhbbr': '珠海门店',
    'dgby': '百业门店',
    'dghf': '合峰门店'
}

# API 配置
UPDATE_API_URL = "http://bi.gzbbr.com/crmapp_api.update_beihuo"
FETCH_API_URL = "http://bi.gzbbr.com/crmapp_api.get_beihuo"

# 请求头配置
DEFAULT_HEADERS = {
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Authorization': 'Basic YWRtaW46ODA4OA==',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'http://bi.gzbbr.com',
    'Pragma': 'no-cache',
    'Referer': 'http://bi.gzbbr.com/crmapp_api.bh_index',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}

# 请求超时配置（秒）
UPDATE_TIMEOUT = 120
FETCH_TIMEOUT = 120

# 批量插入配置
BATCH_SIZE = 10000
COMMIT_INTERVAL = 5

# 字段映射：API字段名 -> 数据库字段名
FIELD_MAPPING = {
    "OE": "oe",
    "今日销量": "今日销量",
    "供应商": "供应商",
    "全国近1个月询价量": "全国近1个月询价量",
    "全国近3个月月均询价量": "全国近3个月月均询价量",
    "内部备注": "内部备注",
    "品牌": "品牌",
    "品牌号": "品牌号",
    "库存数量": "库存数量",
    "库存金额": "库存金额",
    "成品可卖天数": "成品可卖天数",
    "成本价": "成本价",
    "昨日销量": "昨日销量",
    "本月销量": "本月销量",
    "标签": "标签",
    "物料名称": "物料名称",
    "物料条码": "物料条码",
    "车型品牌": "车型品牌",
    "近12个月月均销量": "近12个月月均销量",
    "近12个月销量": "近12个月销量",
    "近1个月询价量": "近1个月询价量",
    "近3个月月均询价量": "近3个月月均询价量",
    "近6个月月均销量": "近6个月月均销量",
    "近6个月销量": "近6个月销量",
    "近7天销量": "近7天销量",
    "预警状态": "预警状态",
    "在途数量": "在途数量",
    "车型": "车型",
}

# 数据库字段列表（按数据库表 crmapp_beihuo 实际字段顺序）
DB_FIELDS = [
    "oe", "今日销量", "供应商", "全国近1个月询价量", "全国近3个月月均询价量",
    "内部备注", "品牌", "品牌号", "库存数量", "库存金额", "成品可卖天数",
    "成本价", "昨日销量", "本月销量", "标签", "物料名称", "物料条码",
    "车型品牌", "近12个月月均销量", "近12个月销量", "近1个月询价量",
    "近3个月月均询价量", "近6个月月均销量", "近6个月销量", "近7天销量",
    "预警状态", "company", "更新时间", "在途数量", "车型", "替换号"
]
