# -*- coding:utf-8 -*-
"""
飞书任务同步 - 配置常量
"""

# 飞书开放平台域名
LARK_OPEN_API_HOST = "https://open.feishu.cn"

# 获取 tenant_access_token 接口
TENANT_ACCESS_TOKEN_URL = f"{LARK_OPEN_API_HOST}/open-apis/auth/v3/tenant_access_token/internal"

# 创建任务接口
CREATE_TASK_URL = f"{LARK_OPEN_API_HOST}/open-apis/task/v2/tasks"

# 批量通过手机号/邮箱获取用户 ID 接口
BATCH_GET_USER_ID_URL = f"{LARK_OPEN_API_HOST}/open-apis/contact/v3/users/batch_get_id"

# 飞书配置在 beihuo_system_config 表中的 config_key
LARK_APP_ID_KEY = "lark_app_id"
LARK_APP_SECRET_KEY = "lark_app_secret"
LARK_ENCRYPT_KEY = "lark_encrypt_key"
LARK_TASK_SYNC_ENABLED_KEY = "lark_task_sync_enabled"

# 缓存 key 前缀
TOKEN_CACHE_KEY_PREFIX = "lark_task_sync:tenant_access_token"

# 请求超时（连接超时, 读取超时），单位秒
REQUEST_TIMEOUT = (5, 30)


def get_current_env():
    """
    判断当前环境是 dev 还是 prod。
    与 config/db_config.py 保持一致：只有 /www/wwwroot/beihuo_system 路径下才是线上环境。
    """
    from pathlib import Path
    current_path = str(Path(__file__).resolve()).lower().replace('\\', '/')
    return 'prod' if '/www/wwwroot/beihuo_system' in current_path else 'dev'

# 重试次数与间隔（秒）
RETRY_TIMES = 3
RETRY_DELAYS = {1: 0, 2: 300, 3: 1800}  # 第1次立即，第2次5分钟后，第3次30分钟后
RETRY_INTERVAL = 5
