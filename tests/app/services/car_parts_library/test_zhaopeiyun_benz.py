# -*- coding:utf-8 -*-
"""兆配云奔驰爬取测试 - 30行精简版"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.car_parts_library_service.zhaopeiyun_benz import get_zpy_token, fetch_and_save_benz_part_zpy

# 1. 获取token
token = get_zpy_token()
print(f"[1] Token: {len(token)} 字符") if token else (print("[1] Token为空"), exit(1))

# 2. 调API看原始结构
from app.scripts.spiders.spider_entities.zhaopeiyun import ZhaoPeiYunSpider
spider = ZhaoPeiYunSpider(token=token)
resp = spider.get_oe_detail(brand_code='benz', part_code='A1265845526')
d = resp.json() if resp else None
print(f"[2] statusCode={d.get('statusCode') if d else None}, data keys={list(d['data'].keys()) if d and d.get('data') else 'EMPTY'}")
if d and d.get('data'):
    pi = d['data'].get('partInfo') or {}
    print(f"    partName={pi.get('partName')}, price={pi.get('price')}, stockInfos={len(d['data'].get('stockInfos') or [])}")
spider.close()

# 3. 测试完整爬取入库流程
for pn in ['A1265845526', 'A1698202140']:
    r = fetch_and_save_benz_part_zpy(pn)
    print(f"[3] {pn}: part_success={r['part_success']}, stock_count={r['stock_count']}")
print("Done")
