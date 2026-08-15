from datetime import datetime, timedelta

# 获取前10天日期，格式 Y-m-d
pre_10day = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
print(pre_10day)