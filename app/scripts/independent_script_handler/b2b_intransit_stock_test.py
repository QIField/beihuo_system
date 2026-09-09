# -*- coding: utf-8 -*-
"""
物料在途库存接口 - 联通测试脚本

仅调用"获取物料在途库存列表"接口并展示响应，不写入数据库。

用法：
    1. 指定 token（推荐，无需连库）：
       python app/scripts/independent_script_handler/b2b_intransit_stock_test.py <token>
    2. 不传参数：自动从系统配置表读取 openapi_gzbbr_com_fs（只读）
       python app/scripts/independent_script_handler/b2b_intransit_stock_test.py
"""

import json
import os
import sys
from datetime import datetime

# 引导项目根目录进入 sys.path，支持直接 python 运行
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _get_token(argv_token):
    """优先取命令行传入的 token；否则从系统配置读取（只读）"""
    if argv_token:
        return argv_token
    from config.config_list_manager.config_cache import get_config_value
    from app.services.b2b_intransit_service.config import TOKEN_CONFIG_KEY
    token = get_config_value(TOKEN_CONFIG_KEY)
    if not token:
        raise RuntimeError(f"未传入 token 且系统配置中不存在: {TOKEN_CONFIG_KEY}")
    return token


def main():
    argv_token = sys.argv[1] if len(sys.argv) > 1 else None
    token = _get_token(argv_token)
    print(f"[测试] 使用 token: {token[:10]}...{token[-5:]}")

    # 1. 调用接口（含重试），打印原始响应
    from app.services.b2b_intransit_service.api_client import fetch_in_transit_stock
    payload = fetch_in_transit_stock(token)

    print("\n" + "=" * 80)
    print("【1】接口原始响应")
    print("=" * 80)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    # 2. 走解析+校验流程（纯内存，不入库），展示展平结果
    from app.services.b2b_intransit_service.data_processor import extract_products, flatten_and_validate
    products = extract_products(payload)
    records, stats = flatten_and_validate(products, datetime.now())

    print("\n" + "=" * 80)
    print("【2】解析与校验结果（不入库）")
    print("=" * 80)
    print(f"产品数: {stats['product_count']}")
    print(f"在途明细总数: {stats['item_count']}")
    print(f"校验通过: {stats['valid_count']}")
    print(f"校验丢弃: {stats['invalid_count']}")

    print("\n前 5 条展平明细示例:")
    for idx, record in enumerate(records[:5], 1):
        show = dict(record)
        show['sync_time'] = show['sync_time'].strftime('%Y-%m-%d %H:%M:%S')
        for date_field in ('order_date', 'expected_delivery_date'):
            if show.get(date_field):
                show[date_field] = str(show[date_field])
        if show.get('price') is not None:
            show['price'] = str(show['price'])
        print(f"  [{idx}] {json.dumps(show, ensure_ascii=False)}")

    print("\n[测试] 完成（未执行任何数据库写入）")


if __name__ == '__main__':
    main()
