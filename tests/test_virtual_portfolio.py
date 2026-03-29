"""
QA测试用例 — 虚拟盘引擎 (engine/virtual_portfolio.py)
覆盖：账户创建、买入、卖出、快照、性能指标
使用内存SQLite避免影响生产数据
"""

import unittest
import sys
import os
import sqlite3
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 使用临时数据库
_TEST_DB = os.path.join(tempfile.gettempdir(), "test_fund_monitor.db")


def _patch_db():
    """替换DB路径为临时文件"""
    return patch("engine.virtual_portfolio.DB_PATH", _TEST_DB)


class TestVirtualPortfolioAccount(unittest.TestCase):
    """账户管理测试"""

    def setUp(self):
        # 清理旧测试数据库
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_create_account(self):
        """创建虚拟账户"""
        with _patch_db():
            from engine.virtual_portfolio import init_virtual_tables, get_or_create_account
            init_virtual_tables()
            account = get_or_create_account(initial_cash=300000)
            self.assertIsNotNone(account)
            self.assertEqual(account["initial_cash"], 300000)
            self.assertEqual(account["current_cash"], 300000)

    def test_get_existing_account(self):
        """重复调用返回同一账户"""
        with _patch_db():
            from engine.virtual_portfolio import init_virtual_tables, get_or_create_account
            init_virtual_tables()
            a1 = get_or_create_account(300000)
            a2 = get_or_create_account(300000)
            self.assertEqual(a1["id"], a2["id"])

    def test_account_summary(self):
        """账户汇总信息"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account, get_account_summary
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            summary = get_account_summary(acc["id"])
            self.assertEqual(summary["cash"], 300000)
            self.assertEqual(summary["total_assets"], 300000)
            self.assertEqual(len(summary["holdings"]), 0)
            self.assertEqual(summary["trade_count"], 0)


class TestVirtualBuySell(unittest.TestCase):
    """买卖操作测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_buy_success(self):
        """正常买入"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                execute_virtual_buy, get_account_summary,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            result = execute_virtual_buy(
                acc["id"], "000001", "测试基金", 10000, 1.5,
                scores={"d_score": 1.2}, reasoning="测试买入"
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["direction"], "BUY")
            self.assertAlmostEqual(result["shares"], 10000 / 1.5, places=2)
            # 验证余额
            summary = get_account_summary(acc["id"])
            self.assertAlmostEqual(summary["cash"], 290000, places=0)
            self.assertEqual(len(summary["holdings"]), 1)

    def test_buy_insufficient_funds(self):
        """余额不足买入失败"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account, execute_virtual_buy,
            )
            init_virtual_tables()
            acc = get_or_create_account(1000)
            result = execute_virtual_buy(acc["id"], "000001", "测试", 5000, 1.0)
            self.assertFalse(result["success"])
            self.assertIn("不足", result["error"])

    def test_buy_invalid_params(self):
        """无效参数拒绝"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account, execute_virtual_buy,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            # 金额=0
            result = execute_virtual_buy(acc["id"], "000001", "测试", 0, 1.0)
            self.assertFalse(result["success"])
            # 净值=0
            result = execute_virtual_buy(acc["id"], "000001", "测试", 1000, 0)
            self.assertFalse(result["success"])

    def test_buy_merge_position(self):
        """多次买入同一基金合并持仓"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                execute_virtual_buy, get_account_summary,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            execute_virtual_buy(acc["id"], "000001", "测试", 10000, 1.0)
            execute_virtual_buy(acc["id"], "000001", "测试", 10000, 1.2)
            summary = get_account_summary(acc["id"])
            # 应该只有1个持仓
            self.assertEqual(len(summary["holdings"]), 1)
            h = summary["holdings"][0]
            # 总成本=20000, 份额=10000+8333.33
            self.assertAlmostEqual(h["total_cost"], 20000, places=0)

    def test_sell_success(self):
        """正常卖出"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                execute_virtual_buy, execute_virtual_sell, get_account_summary,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            execute_virtual_buy(acc["id"], "000001", "测试", 10000, 1.0)
            result = execute_virtual_sell(acc["id"], "000001", "测试", 5000, 1.0)
            self.assertTrue(result["success"])
            self.assertEqual(result["direction"], "SELL")
            summary = get_account_summary(acc["id"])
            self.assertAlmostEqual(summary["cash"], 295000, places=0)

    def test_sell_no_holding(self):
        """卖出未持有基金失败"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account, execute_virtual_sell,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            result = execute_virtual_sell(acc["id"], "999999", "不存在", 1000, 1.0)
            self.assertFalse(result["success"])

    def test_sell_over_holding(self):
        """卖出超过持仓量 → 自动调整为全卖"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                execute_virtual_buy, execute_virtual_sell, get_account_summary,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            execute_virtual_buy(acc["id"], "000001", "测试", 10000, 1.0)
            # 尝试卖出20000（超过持有10000）
            result = execute_virtual_sell(acc["id"], "000001", "测试", 20000, 1.0)
            self.assertTrue(result["success"])
            summary = get_account_summary(acc["id"])
            # 应该全部卖出, 持仓清空
            self.assertEqual(len(summary["holdings"]), 0)


class TestDailySnapshot(unittest.TestCase):
    """每日快照测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_take_snapshot(self):
        """拍摄快照"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                take_daily_snapshot, get_performance_history,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            snap = take_daily_snapshot(acc["id"])
            self.assertEqual(snap["total_assets"], 300000)
            # 应有1条历史
            history = get_performance_history(acc["id"])
            self.assertEqual(len(history), 1)

    def test_snapshot_after_trade(self):
        """交易后快照反映持仓变化"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                execute_virtual_buy, update_holdings_nav,
                take_daily_snapshot,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            execute_virtual_buy(acc["id"], "000001", "测试", 10000, 1.0)
            update_holdings_nav(acc["id"], {"000001": 1.1})
            snap = take_daily_snapshot(acc["id"])
            # 现金290000 + 10000份*1.1 = 301000
            self.assertAlmostEqual(snap["total_assets"], 301000, places=0)


class TestPerformanceMetrics(unittest.TestCase):
    """性能指标测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_empty_metrics(self):
        """无数据时返回零值"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                calculate_performance_metrics,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            metrics = calculate_performance_metrics(acc["id"])
            self.assertEqual(metrics["total_return_pct"], 0)
            self.assertEqual(metrics["total_trades"], 0)

    def test_trade_history(self):
        """交易历史记录"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                execute_virtual_buy, get_trade_history,
            )
            init_virtual_tables()
            acc = get_or_create_account(300000)
            execute_virtual_buy(acc["id"], "000001", "基金A", 5000, 1.0)
            execute_virtual_buy(acc["id"], "000002", "基金B", 3000, 2.0)
            trades = get_trade_history(acc["id"])
            self.assertEqual(len(trades), 2)


class TestIterationLog(unittest.TestCase):
    """迭代日志测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_save_and_retrieve_log(self):
        """保存和读取迭代日志"""
        with _patch_db():
            from engine.virtual_portfolio import (
                init_virtual_tables, save_iteration_log, get_iteration_logs,
            )
            init_virtual_tables()
            log = {
                "iteration_date": "2026-03-29",
                "iteration_num": 1,
                "total_trades": 5,
                "win_rate": 60.0,
                "total_return_pct": 2.5,
                "benchmark_return_pct": 1.0,
                "alpha": 1.5,
                "max_drawdown": -3.0,
                "sharpe_ratio": 1.2,
                "old_weights": {"macro": 0.35, "sector": 0.35, "micro": 0.30},
                "new_weights": {"macro": 0.33, "sector": 0.37, "micro": 0.30},
                "weight_changes": ["宏观因子权重下调"],
                "factor_accuracy": {"macro": {"accuracy_pct": 60}},
                "lessons_learned": "测试经验",
            }
            log_id = save_iteration_log(log)
            self.assertGreater(log_id, 0)
            logs = get_iteration_logs(limit=5)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["iteration_num"], 1)


if __name__ == "__main__":
    unittest.main()
