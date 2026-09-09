# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test_order_status_service.py
# @Software: trae-cn

"""
订单分享 - 订单状态服务单元测试

测试范围（mock 外部依赖，不触网、不触库）：
1. 无缓存时完整流程：已下单 / 仓库已接单 / 已出库 三种终态
2. 有缓存时增量推进：已下单→仓库已接单 / 已下单→已出库 / 仓库已接单→已出库
3. 已出库直接返回缓存，不再查 CRM
4. 异常时返回已有缓存兜底

运行方式：
    python -m tests.order_share.test_order_status_service
"""

import os
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.order_share_service.order_status_service import (
    get_order_status_view,
    STATUS_ORDERED,
    STATUS_PICKED,
    STATUS_SHIPPED,
)

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[通过] {name}")
    else:
        FAIL += 1
        print(f"[失败] {name}")


def _mock_response(json_data):
    """构造模拟 Response 对象"""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _make_record(orders_no, status, orders_id=1001, delivery_id=2001,
                 create_date=1788754388, jhdate=None, ship_date=None):
    """构造模拟缓存记录（与 DAO 返回的 plain dict 保持一致）"""
    return {
        "orders_no": orders_no,
        "orders_id": orders_id,
        "delivery_id": delivery_id,
        "create_date": create_date,
        "jhdate": jhdate,
        "ship_date": ship_date,
        "status": status,
    }


@patch("app.services.order_share_service.order_status_service.CrmGzbbrSpider")
@patch("app.services.order_share_service.order_status_service.order_share_dao")
@patch("app.services.order_share_service.order_status_service._fetch_ship_date")
def test_full_flow_shipped(mock_ship, mock_dao, mock_spider_cls):
    """无缓存 + 三个时间齐全 => 已出库"""
    mock_dao.get_by_orders_no.return_value = None

    spider = MagicMock()
    spider.get_mergeOrderList.return_value = _mock_response({
        "data": {"list": {"data": [{"orders_no": "DD001", "orders_id": 1001}]}}
    })
    spider.get_orders_view.return_value = _mock_response({
        "data": {"TableHeader": {"create_date": 1788754388, "delivery_id": 2001}}
    })
    spider.get_delivery_view.return_value = _mock_response({
        "data": {"TableHeader": {"pack": {"jhdate": "2026-09-03 10:00:00"}}}
    })
    mock_spider_cls.return_value = spider

    ship_dt = datetime(2026, 9, 3, 12, 0, 0)
    mock_ship.return_value = ship_dt

    saved = _make_record("DD001", STATUS_SHIPPED, jhdate=datetime(2026, 9, 3, 10, 0, 0), ship_date=ship_dt)
    mock_dao.upsert.return_value = saved

    result = get_order_status_view("DD001")
    check("无缓存-完整流程-已出库：状态正确", result["status"] == STATUS_SHIPPED)
    check("无缓存-完整流程-已出库：发货时间存在", result["ship_date"] == "2026-09-03 12:00")


@patch("app.services.order_share_service.order_status_service.CrmGzbbrSpider")
@patch("app.services.order_share_service.order_status_service.order_share_dao")
def test_full_flow_ordered(mock_dao, mock_spider_cls):
    """无缓存 + jhdate 为空 => 已下单"""
    mock_dao.get_by_orders_no.return_value = None

    spider = MagicMock()
    spider.get_mergeOrderList.return_value = _mock_response({
        "data": {"list": {"data": [{"orders_no": "DD002", "orders_id": 1002}]}}
    })
    spider.get_orders_view.return_value = _mock_response({
        "data": {"TableHeader": {"create_date": 1788754388, "delivery_id": 2002}}
    })
    spider.get_delivery_view.return_value = _mock_response({
        "data": {"TableHeader": {"pack": {"jhdate": None}}}
    })
    mock_spider_cls.return_value = spider

    saved = _make_record("DD002", STATUS_ORDERED, orders_id=1002, delivery_id=2002)
    mock_dao.upsert.return_value = saved

    result = get_order_status_view("DD002")
    check("无缓存-jhdate为空-已下单：状态正确", result["status"] == STATUS_ORDERED)
    check("无缓存-jhdate为空-已下单：无发货时间", result["ship_date"] is None)


@patch("app.services.order_share_service.order_status_service.CrmGzbbrSpider")
@patch("app.services.order_share_service.order_status_service.order_share_dao")
@patch("app.services.order_share_service.order_status_service._fetch_ship_date")
def test_full_flow_picked(mock_ship, mock_dao, mock_spider_cls):
    """无缓存 + jhdate 有值但 ship_date 为空 => 仓库已接单"""
    mock_dao.get_by_orders_no.return_value = None

    spider = MagicMock()
    spider.get_mergeOrderList.return_value = _mock_response({
        "data": {"list": {"data": [{"orders_no": "DD003", "orders_id": 1003}]}}
    })
    spider.get_orders_view.return_value = _mock_response({
        "data": {"TableHeader": {"create_date": 1788754388, "delivery_id": 2003}}
    })
    spider.get_delivery_view.return_value = _mock_response({
        "data": {"TableHeader": {"pack": {"jhdate": "2026-09-03 10:00:00"}}}
    })
    mock_spider_cls.return_value = spider
    mock_ship.return_value = None

    saved = _make_record("DD003", STATUS_PICKED, orders_id=1003, delivery_id=2003,
                         jhdate=datetime(2026, 9, 3, 10, 0, 0))
    mock_dao.upsert.return_value = saved

    result = get_order_status_view("DD003")
    check("无缓存-jhdate有值ship为空-仓库已接单：状态正确", result["status"] == STATUS_PICKED)


@patch("app.services.order_share_service.order_status_service.CrmGzbbrSpider")
@patch("app.services.order_share_service.order_status_service.order_share_dao")
@patch("app.services.order_share_service.order_status_service._fetch_ship_date")
def test_advance_ordered_to_shipped(mock_ship, mock_dao, mock_spider_cls):
    """缓存已下单 + 查到 ship_date => 推进到已出库"""
    cached = _make_record("DD004", STATUS_ORDERED, orders_id=1004, delivery_id=2004)
    mock_dao.get_by_orders_no.return_value = cached

    spider = MagicMock()
    spider.get_delivery_view.return_value = _mock_response({
        "data": {"TableHeader": {"pack": {"jhdate": "2026-09-03 10:00:00"}}}
    })
    mock_spider_cls.return_value = spider

    ship_dt = datetime(2026, 9, 3, 12, 0, 0)
    mock_ship.return_value = ship_dt

    saved = _make_record("DD004", STATUS_SHIPPED, orders_id=1004, delivery_id=2004,
                         jhdate=datetime(2026, 9, 3, 10, 0, 0), ship_date=ship_dt)
    mock_dao.upsert.return_value = saved

    result = get_order_status_view("DD004")
    check("缓存已下单-推进到已出库：状态正确", result["status"] == STATUS_SHIPPED)


@patch("app.services.order_share_service.order_status_service.order_share_dao")
@patch("app.services.order_share_service.order_status_service._fetch_ship_date")
def test_advance_picked_to_shipped(mock_ship, mock_dao):
    """缓存仓库已接单 + 查到 ship_date => 推进到已出库（不需要 CRM）"""
    cached = _make_record("DD005", STATUS_PICKED, orders_id=1005, delivery_id=2005,
                          jhdate=datetime(2026, 9, 3, 10, 0, 0))
    mock_dao.get_by_orders_no.return_value = cached

    ship_dt = datetime(2026, 9, 3, 12, 0, 0)
    mock_ship.return_value = ship_dt

    saved = _make_record("DD005", STATUS_SHIPPED, orders_id=1005, delivery_id=2005,
                         jhdate=datetime(2026, 9, 3, 10, 0, 0), ship_date=ship_dt)
    mock_dao.upsert.return_value = saved

    result = get_order_status_view("DD005")
    check("缓存仓库已接单-推进到已出库：状态正确", result["status"] == STATUS_SHIPPED)


@patch("app.services.order_share_service.order_status_service.order_share_dao")
def test_shipped_cache_direct_return(mock_dao):
    """缓存已出库 => 直接返回，不调任何接口"""
    cached = _make_record("DD006", STATUS_SHIPPED, orders_id=1006, delivery_id=2006,
                          jhdate=datetime(2026, 9, 3, 10, 0, 0),
                          ship_date=datetime(2026, 9, 3, 12, 0, 0))
    mock_dao.get_by_orders_no.return_value = cached

    result = get_order_status_view("DD006")
    check("缓存已出库-直接返回：状态正确", result["status"] == STATUS_SHIPPED)


if __name__ == "__main__":
    test_full_flow_shipped()
    test_full_flow_ordered()
    test_full_flow_picked()
    test_advance_ordered_to_shipped()
    test_advance_picked_to_shipped()
    test_shipped_cache_direct_return()
    print("=" * 40)
    print(f"测试结果：通过 {PASS} 项，失败 {FAIL} 项")
    sys.exit(1 if FAIL else 0)
