"""B2B Token 刷新定时任务"""
from datetime import datetime
from config.data_gzbbr_config import COMPANY_KEY_MAP, get_b2b_token, save_b2b_token


def data_gzbbr_token_task():
    """刷新所有公司 token 并保存到数据库"""
    print(f"\n[Token刷新] 开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for company, config_key in COMPANY_KEY_MAP.items():
        try:
            token = get_b2b_token(company)
            save_b2b_token(config_key, token)
            print(f"[{company}] 成功: {token[:10]}...{token[-5:]}")
        except Exception as e:
            print(f"[{company}] 失败: {e}")


def data_gzbbr_token_register(task_manager):
    """注册定时任务（每6小时）"""
    task_manager.schedule(
        data_gzbbr_token_task,
        'cron',
        'data_gzbbr_token_task',
        hour='*/6',
        minute=0,
        replace_existing=True
    )


if __name__ == '__main__':
    data_gzbbr_token_task()
