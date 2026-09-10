import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.scripts.spiders.spider_entities.cassmall_login import CassmallLoginService

try:
    cookie = CassmallLoginService.get_valid_config("fsbbr")
    print(f"✅ 登录成功！Cookie 长度: {len(cookie)}")
    print(f"前 150 字符: {cookie[:150]}")
except Exception as e:
    print(f"❌ 登录失败: {e}")
