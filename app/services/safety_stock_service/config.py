"""
安全库存计算配置
包含ABC分类、季节性调整、预警阈值等参数
"""

# ABC分类配置
# A类: 高销量产品，高服务水平，高安全库存
# B类: 中销量产品，中等服务水平
# C类: 低销量产品，低服务水平，低安全库存
ABC_CONFIG = {
    'A': {
        'percent': 0.2,      # 前20%产品
        'z_factor': 1.5,     # 服务水平系数
        'cover_days': 10     # 覆盖天数
    },
    'B': {
        'percent': 0.6,      # 中间60%产品
        'z_factor': 1.2,     # 服务水平系数
        'cover_days': 20     # 覆盖天数
    },
    'C': {
        'percent': 0.2,      # 后20%产品
        'z_factor': 0.8,     # 服务水平系数
        'cover_days': 30     # 覆盖天数
    }
}

# 季节性调整配置
SEASONAL_CONFIG = {
    'min_factor': 0.7,   # 淡季最低系数（降低30%）
    'max_factor': 1.3,   # 旺季最高系数（增加30%）
}

# 积压判定阈值
# 当可用库存超过目标库存的此倍数时，判定为积压
OVERSTOCK_THRESHOLD = 1.3  # 超过上限30%

# 预警阈值（天数）
WARNING_DAYS = 3  # 可卖天数<=3判定为库存偏低

# 补货周期（天）
# 当日达，补货周期为1天
LEAD_TIME = 1

# 数据库表名
TABLE_NAME = 'crmapp_safety_stock_calculation'

# 计算时使用的销量数据时间范围（天）
SALES_HISTORY_DAYS = 365  # 近1年
