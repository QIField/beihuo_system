#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 · 状态机与常量定义

明细状态机（qpl_order_item.status）：
    pending → quoted / failed_biz / failed_temp
    failed_temp --(冷却4h, 重试≤3)--> pending
    failed_temp --(重试耗尽)--> failed_biz
    failed_biz --(手动重试)--> pending
"""

# ---------------------------------------------------------------------------
# 明细状态机
# ---------------------------------------------------------------------------

STATUS_PENDING = 'pending'          # 待处理（新明细入库 / 重试到期）
STATUS_QUOTED = 'quoted'            # 报价成功（终态）
STATUS_FAILED_BIZ = 'failed_biz'    # 确定性失败（终态，不自动重试）
STATUS_FAILED_TEMP = 'failed_temp'  # 临时失败（冷却后重试）

TERMINAL_STATUSES = (STATUS_QUOTED, STATUS_FAILED_BIZ)

# 每轮拉取待处理明细的状态范围（R2/P2 过滤依据）
RETRYABLE_STATUSES = (STATUS_PENDING, STATUS_FAILED_TEMP)

# ---------------------------------------------------------------------------
# 尝试流水 action / result
# ---------------------------------------------------------------------------

ACTION_MATCH = 'match'              # 匹配价格源
ACTION_PRICE_CHECK = 'price_check'  # 价格校验
ACTION_SUBMIT = 'submit'            # 提交汽配龙
ACTION_FETCH_LIST = 'fetch_list'    # 拉取订单列表
ACTION_FETCH_DETAIL = 'fetch_detail'  # 拉取订单详情
ACTION_MANUAL_RETRY = 'manual_retry'  # 手动重试

RESULT_SUCCESS = '成功'
RESULT_FAIL = '失败'
RESULT_SKIP = '跳过'

# ---------------------------------------------------------------------------
# 重试策略（已与业务确认：确定性失败不重试，临时失败冷却4h重试≤3）
# ---------------------------------------------------------------------------

COOLING_HOURS = 4   # 临时失败冷却时长（小时）
MAX_RETRY = 3       # 临时失败最大重试次数，耗尽转 failed_biz

# ---------------------------------------------------------------------------
# 报价来源
# ---------------------------------------------------------------------------

SOURCE_CRM = 'CRM现货'
SOURCE_BENZ = '奔驰接口'
SOURCE_BMW = '宝马接口'

# ---------------------------------------------------------------------------
# 汽配龙接口固定值（来自新页面 HAR 分析）
# ---------------------------------------------------------------------------

QUOTE_TYPE_PAGE_QUOTE = 'PAGE_QUOTE'  # 提交接口 quoteType 固定值
DETAIL_QUERY_TYPE_PAGE = 'PAGE'       # 详情接口 queryType
DETAIL_PAGE_SIZE = 20                 # 详情接口分页大小
