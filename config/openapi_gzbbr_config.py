"""B2B 数据平台配置"""
import json
import time
import requests

B2B_CONFIG = {
    'fsbbr': {"AccessKeyId": "tdFsi8qAQVDz0PAotz56CNFJib3evY8H", "AccessKeySecret": "wHsV0V1Fk7MJBQ8tcy6XTd4VhLMxgtEr9vZhDjU9yxrtDwyBTFE8QI0WQY3c7Npp"},
    'zhbbr': {"AccessKeyId": "D6xZVa6tn3zK9vOxd7TGh6d5XLhHWoEe", "AccessKeySecret": "DOYRvIlOHVParozgWaS3I79BgKSs5cBz5ZBCaYAfUwWfDUGGmSryHdKBKxeuKYQ1"},
    'zsbbr': {"AccessKeyId": "4UjFNIabklprFwUtXVn4Rof4xeA2A79m", "AccessKeySecret": "UeJoyb6MeeXKBJmZBtTbgnazHujKDN2X4Xqi3kKZuCAVZdzWZT49V0UKX25D4i7F"},
    'dgby': {"AccessKeyId": "QChRLkBRG8iZTmmC4T3tRk9R1Xgn6EVr", "AccessKeySecret": "BfXAdzONLHKb1yoW2Eeuvb4ui7Z0W6GBjWegO4OZzahKQGzPmofhjOLekLxFhFyX"},
    'dghf': {"AccessKeyId": "p5yr2EjeLxY4MhmWNcTi9gS9mOJi7Unp", "AccessKeySecret": "nvnugyGdVwecdwdUbkUpHsLEDyKdYPXAfGL6aZx1rZnmjqDdyDt5JNYQGCKtRXEK"}
}

# 公司代码与 config_key 映射
COMPANY_KEY_MAP = {
    'fsbbr': 'openapi_gzbbr_com_fs',
    'zhbbr': 'openapi_gzbbr_com_zh',
    'zsbbr': 'openapi_gzbbr_com_zs',
    'dgby': 'openapi_gzbbr_com_by',
    'dghf': 'openapi_gzbbr_com_hf'
}


def get_b2b_token(company):
    """获取 B2B token"""
    url = "https://openapi.gzbbr.com/login/index"
    data = B2B_CONFIG[company]
    
    for attempt in range(3):
        try:
            response = requests.post(url, data=data, timeout=(10, 30))
            return json.loads(response.text)['data']['token']
        except:
            if attempt == 2:
                raise
            time.sleep(5)


def save_b2b_token(config_key, token):
    """保存 token 到数据库"""
    from app.utils.database_connection import db_execute
    from config.config_list_manager.config_cache import refresh_sys_config
    
    sql = """
        UPDATE beihuo_system_config 
        SET config_value = %s, updated_at = NOW() 
        WHERE config_key = %s
    """
    db_execute(sql, (token, config_key))
    
    refresh_sys_config(config_key)
