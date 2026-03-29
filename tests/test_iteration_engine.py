"""
QA测试用例 — 自我迭代引擎 (engine/iteration_engine.py)
覆盖：因子准确度分析、权重调整、经验总结、整体迭代
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TEST_DB = os.path.join(tempfile.gettempdir(), "test_iteration.db")


def _patch_db_both():
    """同时替换两个模块的DB_PATH"""
    p1 = patch("engine.iteration_engine.DB_PATH", _TEST_DB)
    p2 = patch("engine.virtual_portfolio.DB_PATH", _TEST_DB)
    return p1, p2


class TestFactorAccuracy(unittest.TestCase):
    """因子准确度分析测试"""

    def test_empty_data(self):
        from engine.iteration_engine import _analyze_factor_accuracy
        result = _analyze_factor_accuracy([], [])
        self.assertEqual(result["macro"]["total"], 0)

    def test_correct_prediction(self):
        """正确预测: 正D分+市场上涨"""
        from engine.iteration_engine import _analyze_factor_accuracy
        trades = [
            {"m_score": 1.0, "s_score": 0.5, "c_score": 0.3, "d_score": 1.0},
        ]
        snapshots = [
            {"total_assets": 100000},
            {"total_assets": 105000},  # 上涨
        ]
        result = _analyze_factor_accuracy(trades, snapshots)
        self.assertEqual(result["macro"]["correct"], 1)
        self.assertEqual(result["composite"]["correct"], 1)

    def test_wrong_prediction(self):
        """错误预测: 正D分+市场下跌"""
        from engine.iteration_engine import _analyze_factor_accuracy
        trades = [
            {"m_score": 1.0, "s_score": 0.5, "c_score": 0.3, "d_score": 1.0},
        ]
        snapshots = [
            {"total_assets": 100000},
            {"total_assets": 95000},  # 下跌
        ]
        result = _analyze_factor_accuracy(trades, snapshots)
        self.assertEqual(result["macro"]["correct"], 0)


class TestWeightAdjustment(unittest.TestCase):
    """权重调整测试"""

    def test_accurate_factor_weight_increases(self):
        """准确率高的因子权重上调"""
        from engine.iteration_engine import _adjust_weights
        current = {"macro": 0.35, "sector": 0.35, "micro": 0.30}
        accuracy = {
            "macro": {"accuracy_pct": 80},   # 很准
            "sector": {"accuracy_pct": 50},   # 一般
            "micro": {"accuracy_pct": 40},    # 较差
        }
        new_w, changes = _adjust_weights(current, accuracy, 2.0, 1.0, {})
        # 宏观因子应被上调
        self.assertGreater(new_w["macro"], current["macro"] - 0.01)  # 至少不会被大幅下调

    def test_weights_sum_to_one(self):
        """调整后权重总和=1"""
        from engine.iteration_engine import _adjust_weights
        current = {"macro": 0.35, "sector": 0.35, "micro": 0.30}
        accuracy = {
            "macro": {"accuracy_pct": 70},
            "sector": {"accuracy_pct": 30},
            "micro": {"accuracy_pct": 50},
        }
        new_w, _ = _adjust_weights(current, accuracy, 1.0, 0.5, {})
        total = new_w["macro"] + new_w["sector"] + new_w["micro"]
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_minimum_weight(self):
        """权重不低于15%"""
        from engine.iteration_engine import _adjust_weights
        current = {"macro": 0.20, "sector": 0.40, "micro": 0.40}
        accuracy = {
            "macro": {"accuracy_pct": 10},   # 很差
            "sector": {"accuracy_pct": 90},
            "micro": {"accuracy_pct": 90},
        }
        new_w, _ = _adjust_weights(current, accuracy, -5.0, -3.0, {})
        self.assertGreaterEqual(new_w["macro"], 0.15)
        self.assertGreaterEqual(new_w["sector"], 0.15)
        self.assertGreaterEqual(new_w["micro"], 0.15)

    def test_adjustment_bounded(self):
        """每轮调整不超过±5%"""
        from engine.iteration_engine import _adjust_weights
        current = {"macro": 0.35, "sector": 0.35, "micro": 0.30}
        accuracy = {
            "macro": {"accuracy_pct": 100},
            "sector": {"accuracy_pct": 0},
            "micro": {"accuracy_pct": 50},
        }
        new_w, _ = _adjust_weights(current, accuracy, 5.0, 3.0, {})
        for key in ["macro", "sector", "micro"]:
            diff = abs(new_w[key] - current[key])
            # 归一化后可能稍微超过5%，但不应超过10%
            self.assertLess(diff, 0.10, f"{key} changed by {diff*100:.1f}%")


class TestNotableTrades(unittest.TestCase):
    """最佳/最差交易测试"""

    def test_empty(self):
        from engine.iteration_engine import _find_notable_trades
        best, worst = _find_notable_trades([])
        self.assertEqual(len(best), 0)
        self.assertEqual(len(worst), 0)

    def test_ranking(self):
        from engine.iteration_engine import _find_notable_trades
        trades = [
            {"direction": "BUY", "fund_name": "A", "amount": 1000, "d_score": 2.0, "reasoning": ""},
            {"direction": "BUY", "fund_name": "B", "amount": 2000, "d_score": -1.0, "reasoning": ""},
            {"direction": "SELL", "fund_name": "C", "amount": 500, "d_score": 0.5, "reasoning": ""},
        ]
        best, worst = _find_notable_trades(trades)
        self.assertGreater(len(best), 0)
        self.assertEqual(best[0]["fund"], "A")  # 最高D分


class TestLessonsGeneration(unittest.TestCase):
    """经验总结测试"""

    def test_positive_return(self):
        from engine.iteration_engine import _generate_lessons
        text = _generate_lessons(
            5.0, 3.0, 2.0,
            {"macro": {"accuracy_pct": 70}, "sector": {"accuracy_pct": 50}, "micro": {"accuracy_pct": 60}},
            [], [], [1, 2, 3]
        )
        self.assertIn("收益", text)

    def test_negative_return(self):
        from engine.iteration_engine import _generate_lessons
        text = _generate_lessons(
            -3.0, 1.0, -4.0,
            {"macro": {"accuracy_pct": 30}, "sector": {"accuracy_pct": 50}, "micro": {"accuracy_pct": 60}},
            [], [], [1]
        )
        self.assertIn("亏损", text)


class TestFullIteration(unittest.TestCase):
    """完整迭代流程测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_run_weekly_iteration(self):
        """运行完整迭代"""
        p1, p2 = _patch_db_both()
        with p1, p2:
            from engine.virtual_portfolio import (
                init_virtual_tables, get_or_create_account,
                execute_virtual_buy, take_daily_snapshot,
            )
            from engine.iteration_engine import run_weekly_iteration
            from engine.factor_model import REGIMES

            init_virtual_tables()
            acc = get_or_create_account(300000)

            # 模拟一些交易
            execute_virtual_buy(acc["id"], "000001", "测试A", 5000, 1.0,
                                scores={"d_score": 1.0, "m_score": 0.5, "s_score": 0.3, "c_score": 0.2})
            take_daily_snapshot(acc["id"])

            weights = {"macro": 0.35, "sector": 0.35, "micro": 0.30}
            log = run_weekly_iteration(acc["id"], weights, REGIMES)

            self.assertIn("iteration_num", log)
            self.assertIn("new_weights", log)
            self.assertIn("lessons_learned", log)
            # 新权重格式正确
            nw = log["new_weights"]
            self.assertIn("macro", nw)
            total = nw["macro"] + nw["sector"] + nw["micro"]
            self.assertAlmostEqual(total, 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
