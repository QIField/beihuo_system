# -*- coding:utf-8 -*-
"""测试改后的 validate_cookie 方法"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.scripts.spiders.spider_entities.cassmall_login import CassmallLoginService

# 测试1: 无效 cookie
ok, msg = CassmallLoginService.validate_cookie("fake_cookie=invalid_123")
print(f"[无效cookie] 有效={ok}, 消息={msg}")
assert not ok, "无效cookie应该返回False"

# 测试2: 空 cookie
ok, msg = CassmallLoginService.validate_cookie("")
print(f"[空cookie]   有效={ok}, 消息={msg}")
assert not ok, "空cookie应该返回False"

print("\n✅ 无效场景测试通过")
