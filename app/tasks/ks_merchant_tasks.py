"""
开思商家数据定时任务

每10分钟执行一次，同步三个表的数据
"""

import requests
from datetime import datetime
from app.services.ks_merchant_service.sync_service import sync_ks_merchant_data

# Cookie API 地址（复用询价单监控的配置）
COOKIE_API_URL = "http://113.45.176.129:8001/md_ks.get_cookies"


def get_cookies(md_code: str = "fs") -> dict:
    """
    获取开思商家平台的 cookies
    
    Args:
        md_code: 门店代码，默认佛山(fs)
        
    Returns:
        cookies 字典
    """
    try:
        resp = requests.get(f"{COOKIE_API_URL}?md={md_code}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get('cookie', {})
        else:
            print(f"[Cookie] 获取失败，状态码: {resp.status_code}")
            return {}
    except Exception as e:
        print(f"[Cookie] 获取异常: {e}")
        return {}


def ks_merchant_sync_task():
    """
    开思商家数据同步定时任务
    
    职责：
    1. 准备参数（获取cookies）
    2. 调用服务层执行业务逻辑
    3. 捕获异常、记录日志
    """
    print(f"\n[定时任务] 开思商家数据同步开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 获取 cookies
        cookies = get_cookies("fs")
        if not cookies:
            print("[定时任务] 获取 cookies 失败，跳过本次同步")
            return
        
        print(f"[定时任务] 成功获取 cookies")
        
        # 调用服务层执行业务逻辑
        result = sync_ks_merchant_data(cookies)
        
        print(f"[定时任务] 同步完成："
              f"汇总 {result['summary_count']} 条，"
              f"明细 {result['detail_count']} 条，"
              f"指标 {result['indicator_count']} 条")
        
    except Exception as e:
        print(f"[定时任务] 同步失败: {e}")
        # TODO: 记录错误日志、发送告警通知
        raise
    
    print(f"[定时任务] 开思商家数据同步结束\n")
