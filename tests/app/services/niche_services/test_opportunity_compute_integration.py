# -*- coding:utf-8 -*-
"""
商机计算集成测试

目标：验证从 wechat_daily_quote_detail 到 niche_opportunity 的完整计算流程。
测试会操作真实数据库，使用遥远的未来日期避免影响生产数据。
"""

import sys
import os
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from sqlalchemy import text

from app.utils.orm.session import orm_session
from app.dao.niche_dao.niche_opportunity_dao import fetch_inquiry_stats
from app.services.niche_services import opportunity_compute_service


TEST_STAT_DATE = '2099-01-15'
TEST_OE_CODE = 'TEST_OE_99999'


def _insert_test_inquiry(create_date, oe_code, is_oos, customer, quote_no):
    """向 wechat_daily_quote_detail 插入一条测试数据"""
    sql = text("""
        INSERT INTO wechat_daily_quote_detail (
            weixin_decoding_result_id, quote_number, create_date,
            inquiry_customer_id, inquiry_customer, part_name,
            oe_code, is_out_of_stock, deal_status, inquiry_type
        ) VALUES (
            :weixin_decoding_result_id, :quote_number, :create_date,
            1, :inquiry_customer, '测试配件',
            :oe_code, :is_out_of_stock, 0, 2
        )
    """)
    with orm_session() as session:
        session.execute(sql, {
            'weixin_decoding_result_id': quote_no,
            'quote_number': quote_no,
            'create_date': create_date,
            'inquiry_customer': customer,
            'oe_code': oe_code,
            'is_out_of_stock': 1 if is_oos else 0,
        })


def _clean_test_data():
    """清理测试数据"""
    with orm_session() as session:
        session.execute(text("""
            DELETE FROM wechat_daily_quote_detail
            WHERE oe_code = :oe_code
        """), {'oe_code': TEST_OE_CODE})
        session.execute(text("""
            DELETE FROM niche_opportunity
            WHERE oe_code = :oe_code OR stat_date = :stat_date
        """), {'oe_code': TEST_OE_CODE, 'stat_date': TEST_STAT_DATE})


class TestFetchInquiryStatsIntegration(unittest.TestCase):
    """测试从 wechat_daily_quote_detail 聚合询价统计"""

    @classmethod
    def setUpClass(cls):
        _clean_test_data()

        # 构造近30天数据：2次询价，1次缺货，2个不同客户
        base = datetime.strptime(TEST_STAT_DATE, '%Y-%m-%d')
        for i in range(2):
            _insert_test_inquiry(
                (base - timedelta(days=i)).strftime('%Y-%m-%d %H:%M:%S'),
                TEST_OE_CODE,
                is_oos=(i == 0),
                customer=f'客户{i + 1}',
                quote_no=i + 1,
            )

        # 构造上一个30天数据：1次询价
        _insert_test_inquiry(
            (base - timedelta(days=35)).strftime('%Y-%m-%d %H:%M:%S'),
            TEST_OE_CODE,
            is_oos=False,
            customer='客户旧',
            quote_no=3,
        )

    @classmethod
    def tearDownClass(cls):
        _clean_test_data()

    def test_aggregate_current_window(self):
        rows = fetch_inquiry_stats(TEST_STAT_DATE)
        row = next((r for r in rows if r['oe_code'] == TEST_OE_CODE), None)

        self.assertIsNotNone(row)
        self.assertEqual(row['inquiry_count_30d'], 2)
        self.assertEqual(row['out_of_stock_count_30d'], 1)
        self.assertEqual(row['out_of_stock_rate_30d'], 0.5)
        self.assertEqual(row['customer_count_30d'], 2)

    def test_aggregate_prev_window(self):
        rows = fetch_inquiry_stats(TEST_STAT_DATE)
        row = next((r for r in rows if r['oe_code'] == TEST_OE_CODE), None)

        self.assertIsNotNone(row)
        self.assertEqual(row['inquiry_count_prev_30d'], 1)


class TestRunComputeIntegration(unittest.TestCase):
    """测试完整商机计算流程"""

    @classmethod
    def setUpClass(cls):
        _clean_test_data()

        base = datetime.strptime(TEST_STAT_DATE, '%Y-%m-%d')
        # 构造足够多的数据让 P80 计算有意义
        for i in range(5):
            _insert_test_inquiry(
                (base - timedelta(days=i % 30)).strftime('%Y-%m-%d %H:%M:%S'),
                TEST_OE_CODE,
                is_oos=True,
                customer=f'客户{i}',
                quote_no=i + 10,
            )

    @classmethod
    def tearDownClass(cls):
        _clean_test_data()

    def test_run_compute_returns_summary(self):
        result = opportunity_compute_service.run_compute(TEST_STAT_DATE)

        self.assertEqual(result['status'], 'completed')
        self.assertIn('total_count', result)
        self.assertIn('inserted_count', result)
        self.assertIn('total_elapsed_time', result)
        self.assertGreaterEqual(result['total_count'], 1)
        self.assertEqual(result['inserted_count'], result['total_count'])

    def test_niche_opportunity_has_test_record(self):
        opportunity_compute_service.run_compute(TEST_STAT_DATE)

        with orm_session() as session:
            sql = text("""
                SELECT * FROM niche_opportunity
                WHERE oe_code = :oe_code AND stat_date = :stat_date
            """)
            result = session.execute(sql, {
                'oe_code': TEST_OE_CODE,
                'stat_date': TEST_STAT_DATE,
            }).mappings().all()

            self.assertEqual(len(result), 1)
            row = result[0]
            self.assertEqual(row['oe_code'], TEST_OE_CODE)
            self.assertEqual(row['part_name'], '测试配件')
            self.assertIn(row['opportunity_level'], ['S', 'A', 'B', 'C', 'D'])


if __name__ == '__main__':
    unittest.main()
