# -*- coding:utf-8 -*-
# @Time    : 2026/07/25
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test_stock_safe_refund_ref.py
# @Software: trae-cn

"""
安全库存退货关联表 - Service层测试

测试环境要求：
1. 数据库连接配置正确（app/utils/orm/session.py）
2. sales_order_history表存在且包含真实数据（只读）
3. stock_safe_refund_ref表已创建（可读写）

测试策略：
- 仅测试Service层业务逻辑，不测试DAO层数据库操作
- 使用真实数据进行测试
- 验证Service层各方法的返回值格式和业务逻辑正确性

测试用例：
1. Service层测试：run_step1, run_step2, run_step3, run_full_process, get_summary

运行方式：
    python -m tests.conversion_rate.test_stock_safe_refund_ref
"""

import sys
import os
import logging

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def create_logger():
    logger = logging.getLogger("stock_safe_test")
    logger.setLevel(logging.DEBUG)
    
    if logger.handlers:
        return logger
    
    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    return logger


test_logger = create_logger()


try:
    from app.services.stock_safe_service.stock_safe_refund_ref_service import (
        run_step1,
        run_step2,
        run_step3,
        run_full_process,
        get_summary,
    )
    
    test_logger.info("[成功] 导入所有测试模块")
except ImportError as e:
    test_logger.error(f"[失败] 导入模块失败: {e}")
    sys.exit(1)


# ==================== Service层测试 ====================
def test_service_run_step1():
    test_logger.info("\n" + "=" * 60)
    test_logger.info("[测试] Service - run_step1")
    test_logger.info("=" * 60)
    
    try:
        result = run_step1(batch_size=100)
        test_logger.info(f"[结果] {result}")
        
        required_keys = ["step", "action", "inserted_count", "batch_size", "elapsed_time", "timestamp"]
        for key in required_keys:
            assert key in result, f"结果字典缺少必要键: {key}"
        assert result["step"] == "step1", f"step应为'step1'，实际为{result['step']}"
        assert result["action"] == "insert_unmatched_refund_orders", f"action应为'insert_unmatched_refund_orders'"
        assert isinstance(result["inserted_count"], int), f"inserted_count应为整数"
        assert isinstance(result["elapsed_time"], float), f"elapsed_time应为浮点数"
        
        test_logger.info("[成功] run_step1测试通过")
        return True
        
    except AssertionError as e:
        test_logger.error(f"[失败] run_step1测试失败: {e}")
        return False
    except Exception as e:
        test_logger.error(f"[失败] run_step1执行异常: {e}")
        return False


def test_service_run_step2():
    test_logger.info("\n" + "=" * 60)
    test_logger.info("[测试] Service - run_step2")
    test_logger.info("=" * 60)
    
    try:
        result = run_step2(batch_size=10, max_retries=1)
        test_logger.info(f"[结果] {result}")
        
        required_keys = ["step", "action", "total_processed", "matched_count", 
                        "unmatched_count", "batch_size", "max_retries", "elapsed_time", "timestamp"]
        for key in required_keys:
            assert key in result, f"结果字典缺少必要键: {key}"
        assert result["step"] == "step2", f"step应为'step2'，实际为{result['step']}"
        assert result["action"] == "match_refund_orders_batch", f"action应为'match_refund_orders_batch'"
        assert isinstance(result["total_processed"], int), f"total_processed应为整数"
        assert isinstance(result["matched_count"], int), f"matched_count应为整数"
        assert isinstance(result["unmatched_count"], int), f"unmatched_count应为整数"
        assert result["total_processed"] == result["matched_count"] + result["unmatched_count"], \
            "total_processed应等于matched_count + unmatched_count"
        
        test_logger.info("[成功] run_step2测试通过")
        return True
        
    except AssertionError as e:
        test_logger.error(f"[失败] run_step2测试失败: {e}")
        return False
    except Exception as e:
        test_logger.error(f"[失败] run_step2执行异常: {e}")
        return False


def test_service_run_step3():
    test_logger.info("\n" + "=" * 60)
    test_logger.info("[测试] Service - run_step3")
    test_logger.info("=" * 60)
    
    try:
        result = run_step3()
        test_logger.info(f"[结果] {result}")
        
        required_keys = ["step", "action", "updated_count", "pending_count_before", 
                        "pending_count_after", "elapsed_time", "timestamp"]
        for key in required_keys:
            assert key in result, f"结果字典缺少必要键: {key}"
        assert result["step"] == "step3", f"step应为'step3'，实际为{result['step']}"
        assert result["action"] == "update_remaining_unmatched", f"action应为'update_remaining_unmatched'"
        assert isinstance(result["updated_count"], int), f"updated_count应为整数"
        assert isinstance(result["pending_count_after"], int), f"pending_count_after应为整数"
        
        test_logger.info("[成功] run_step3测试通过")
        return True
        
    except AssertionError as e:
        test_logger.error(f"[失败] run_step3测试失败: {e}")
        return False
    except Exception as e:
        test_logger.error(f"[失败] run_step3执行异常: {e}")
        return False


def test_service_run_full_process():
    test_logger.info("\n" + "=" * 60)
    test_logger.info("[测试] Service - run_full_process")
    test_logger.info("=" * 60)
    
    try:
        result = run_full_process(batch_size_step1=100, batch_size_step2=10)
        test_logger.info(f"[结果] 总耗时: {result['total_elapsed_time']}秒")
        test_logger.info(f"[结果] Step1: {result['step1']}")
        test_logger.info(f"[结果] Step2: {result['step2']}")
        test_logger.info(f"[结果] Step3: {result['step3']}")
        test_logger.info(f"[结果] Summary: {result['summary']}")
        
        required_keys = ["total_elapsed_time", "step1", "step2", "step3", "summary", "timestamp"]
        for key in required_keys:
            assert key in result, f"结果字典缺少必要键: {key}"
        assert result["step1"]["step"] == "step1", "step1的step应为'step1'"
        assert result["step2"]["step"] == "step2", "step2的step应为'step2'"
        assert result["step3"]["step"] == "step3", "step3的step应为'step3'"
        
        test_logger.info("[成功] run_full_process测试通过")
        return True
        
    except AssertionError as e:
        test_logger.error(f"[失败] run_full_process测试失败: {e}")
        return False
    except Exception as e:
        test_logger.error(f"[失败] run_full_process执行异常: {e}")
        return False


def test_service_get_summary():
    test_logger.info("\n" + "=" * 60)
    test_logger.info("[测试] Service - get_summary")
    test_logger.info("=" * 60)
    
    try:
        result = get_summary()
        test_logger.info(f"[结果] {result}")
        
        required_keys = ["type_distribution", "pending_count", "timestamp"]
        for key in required_keys:
            assert key in result, f"结果字典缺少必要键: {key}"
        assert isinstance(result["type_distribution"], list), f"type_distribution应为列表"
        assert isinstance(result["pending_count"], int), f"pending_count应为整数"
        
        test_logger.info("[成功] get_summary测试通过")
        return True
        
    except AssertionError as e:
        test_logger.error(f"[失败] get_summary测试失败: {e}")
        return False
    except Exception as e:
        test_logger.error(f"[失败] get_summary执行异常: {e}")
        return False


# ==================== 主测试函数 ====================
def run_all_tests():
    test_logger.info("\n" + "=" * 80)
    test_logger.info("[开始] 运行安全库存退货关联表Service层测试套件")
    test_logger.info("=" * 80)
    
    test_results = []

    # ==================== Service层测试 ====================
    test_logger.info("\n" + "-" * 80)
    test_logger.info("【Service层测试】")
    test_logger.info("-" * 80)

    test_results.append(("Service - run_step1", test_service_run_step1()))
    test_results.append(("Service - run_step2", test_service_run_step2()))
    test_results.append(("Service - run_step3", test_service_run_step3()))
    test_results.append(("Service - run_full_process", test_service_run_full_process()))
    test_results.append(("Service - get_summary", test_service_get_summary()))

    test_logger.info("\n" + "=" * 80)
    test_logger.info("[结束] 测试结果汇总")
    test_logger.info("=" * 80)
    
    passed = sum(1 for _, result in test_results if result)
    failed = len(test_results) - passed
    
    test_logger.info(f"\n测试总数: {len(test_results)}")
    test_logger.info(f"通过: {passed}")
    test_logger.info(f"失败: {failed}")
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        test_logger.info(f"  {status} - {test_name}")
    
    if failed == 0:
        test_logger.info("\n🎉 所有测试通过！")
    else:
        test_logger.info("\n⚠️ 部分测试失败，请检查日志")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)