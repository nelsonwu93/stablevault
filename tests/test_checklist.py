"""
QA测试用例 — Checklist Agent (engine/checklist.py)
覆盖：各检查项逻辑、一票否决、评分计算、维度统计
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.checklist import ChecklistItem, ChecklistAgent
from config import CHECKLIST_DIMENSIONS


def _make_context(
    fed_stance="neutral",
    us10y_chg=0.0,
    cny_chg=0.0,
    rsi=50, rsi_signal="normal",
    above_ma60=True, ma60=1.0, nav=1.05,
    nb_5d=10, nb_signal="positive", nb_pos_days=3,
    total_cost=100000, total_value=105000,
    sector="宽基指数", target_pct=0.10,
    current_value=10000, total_return=500,
    stop_loss=-0.12,
):
    """构建Checklist上下文"""
    return {
        "fed_stance": fed_stance,
        "market": {
            "global": {
                "us_10y": {"price": 4.0, "change_pct": us10y_chg},
                "usd_cny": {"price": 7.2, "change_pct": cny_chg},
            },
            "northbound": {
                "5day_total": nb_5d,
                "signal": nb_signal,
                "5day_positive_days": nb_pos_days,
            },
            "china": {},
        },
        "technical": {
            "rsi": rsi,
            "rsi_signal": rsi_signal,
            "above_ma60": above_ma60,
            "ma60": ma60,
            "latest_nav": nav,
        },
        "portfolio": {
            "total_cost": total_cost,
            "total_value": total_value,
            "total_target": 300000,
            "funds": [
                {"sector": sector, "current_value": current_value},
            ],
        },
        "fund_cfg": {
            "code": "000001",
            "name": "测试基金",
            "sector": sector,
            "target_pct": target_pct,
            "current_value": current_value,
            "total_return": total_return,
            "stop_loss": stop_loss,
        },
    }


class TestChecklistItem(unittest.TestCase):
    """单个检查项测试"""

    def test_global_liquidity_dovish(self):
        """美联储鸽派 → 通过"""
        item = ChecklistItem("global_liquidity", "流动性", "宏观", 25)
        ctx = _make_context(fed_stance="dovish")
        passed, detail = item.run(ctx)
        self.assertTrue(passed)

    def test_global_liquidity_hawkish(self):
        """美联储鹰派 → 不通过"""
        item = ChecklistItem("global_liquidity", "流动性", "宏观", 25)
        ctx = _make_context(fed_stance="hawkish")
        passed, detail = item.run(ctx)
        self.assertFalse(passed)

    def test_global_liquidity_unknown(self):
        """无数据 → 默认通过"""
        item = ChecklistItem("global_liquidity", "流动性", "宏观", 25)
        ctx = _make_context(fed_stance="unknown")
        passed, detail = item.run(ctx)
        self.assertTrue(passed)

    def test_cny_stable(self):
        """汇率稳定 → 通过"""
        item = ChecklistItem("cny_stable", "汇率", "宏观", 10)
        ctx = _make_context(cny_chg=0.3)
        passed, _ = item.run(ctx)
        self.assertTrue(passed)

    def test_cny_volatile(self):
        """汇率大波动 → 不通过"""
        item = ChecklistItem("cny_stable", "汇率", "宏观", 10)
        ctx = _make_context(cny_chg=1.5)
        passed, _ = item.run(ctx)
        self.assertFalse(passed)

    def test_above_ma60_true(self):
        """在60日均线上方 → 通过"""
        item = ChecklistItem("above_ma60", "MA60", "技术", 20)
        ctx = _make_context(above_ma60=True, ma60=1.0, nav=1.05)
        passed, _ = item.run(ctx)
        self.assertTrue(passed)

    def test_above_ma60_false(self):
        """在60日均线下方 → 不通过"""
        item = ChecklistItem("above_ma60", "MA60", "技术", 20)
        ctx = _make_context(above_ma60=False, ma60=1.1, nav=1.0)
        passed, _ = item.run(ctx)
        self.assertFalse(passed)

    def test_above_ma60_no_data(self):
        """无MA60数据 → 默认通过"""
        item = ChecklistItem("above_ma60", "MA60", "技术", 20)
        ctx = _make_context()
        ctx["technical"]["above_ma60"] = None
        passed, detail = item.run(ctx)
        self.assertTrue(passed)
        self.assertIn("暂不扣分", detail)

    def test_rsi_normal(self):
        """RSI正常 → 通过"""
        item = ChecklistItem("rsi_reasonable", "RSI", "技术", 15)
        ctx = _make_context(rsi=50, rsi_signal="normal")
        passed, _ = item.run(ctx)
        self.assertTrue(passed)

    def test_rsi_overbought(self):
        """RSI超买 → 不通过"""
        item = ChecklistItem("rsi_reasonable", "RSI", "技术", 15)
        ctx = _make_context(rsi=75, rsi_signal="overbought")
        passed, _ = item.run(ctx)
        self.assertFalse(passed)

    def test_rsi_oversold(self):
        """RSI超卖 → 通过（好买入时机）"""
        item = ChecklistItem("rsi_reasonable", "RSI", "技术", 15)
        ctx = _make_context(rsi=28, rsi_signal="oversold")
        passed, _ = item.run(ctx)
        self.assertTrue(passed)

    def test_northbound_positive(self):
        """北向资金净流入 → 通过"""
        item = ChecklistItem("northbound_positive", "北向", "市场情绪", 10)
        ctx = _make_context(nb_5d=50, nb_signal="positive", nb_pos_days=4)
        passed, _ = item.run(ctx)
        self.assertTrue(passed)

    def test_northbound_negative(self):
        """北向资金净流出 → 不通过"""
        item = ChecklistItem("northbound_positive", "北向", "市场情绪", 10)
        ctx = _make_context(nb_5d=-30, nb_signal="negative", nb_pos_days=1)
        passed, _ = item.run(ctx)
        self.assertFalse(passed)

    def test_total_drawdown_ok(self):
        """回撤在安全线内 → 通过"""
        item = ChecklistItem("total_drawdown_ok", "回撤", "风险控制", 3, is_veto=True)
        ctx = _make_context(total_cost=100000, total_value=95000)
        passed, _ = item.run(ctx)
        self.assertTrue(passed)

    def test_total_drawdown_exceeded(self):
        """回撤超过-15% → 一票否决"""
        item = ChecklistItem("total_drawdown_ok", "回撤", "风险控制", 3, is_veto=True)
        ctx = _make_context(total_cost=100000, total_value=80000)
        passed, _ = item.run(ctx)
        self.assertFalse(passed)

    def test_not_in_stoploss_safe(self):
        """未触及止损 → 通过"""
        item = ChecklistItem("not_in_stoploss", "止损", "风险控制", 2, is_veto=True)
        ctx = _make_context(current_value=10000, total_return=500, stop_loss=-0.12)
        passed, _ = item.run(ctx)
        self.assertTrue(passed)

    def test_in_stoploss_triggered(self):
        """已触发止损 → 一票否决"""
        item = ChecklistItem("not_in_stoploss", "止损", "风险控制", 2, is_veto=True)
        ctx = _make_context(current_value=10000, total_return=-2000, stop_loss=-0.12)
        passed, _ = item.run(ctx)
        self.assertFalse(passed)


class TestChecklistAgent(unittest.TestCase):
    """ChecklistAgent整体测试"""

    def setUp(self):
        self.agent = ChecklistAgent(CHECKLIST_DIMENSIONS)

    def test_run_returns_required_keys(self):
        """Agent运行返回完整结构"""
        ctx = _make_context()
        result = self.agent.run(ctx)
        for key in ["score", "recommendation", "veto_triggered", "items",
                     "passed_count", "total_count", "summary", "dimension_scores"]:
            self.assertIn(key, result, f"Missing: {key}")

    def test_score_in_range(self):
        """总分在0-100"""
        ctx = _make_context()
        result = self.agent.run(ctx)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    def test_all_items_checked(self):
        """所有检查项都执行"""
        ctx = _make_context()
        result = self.agent.run(ctx)
        self.assertEqual(result["total_count"], len(CHECKLIST_DIMENSIONS))

    def test_veto_overrides_score(self):
        """一票否决项触发时recommendation=VETO"""
        ctx = _make_context(total_cost=100000, total_value=80000)  # 回撤超限
        result = self.agent.run(ctx)
        self.assertTrue(result["veto_triggered"])
        self.assertEqual(result["recommendation"], "VETO")

    def test_high_score_buy(self):
        """高分 → BUY"""
        ctx = _make_context(
            fed_stance="dovish", cny_chg=0.1,
            rsi=40, rsi_signal="normal",
            above_ma60=True,
            nb_5d=50, nb_signal="positive", nb_pos_days=4,
            total_cost=100000, total_value=105000,
        )
        result = self.agent.run(ctx)
        self.assertIn(result["recommendation"], ["BUY", "BUY_SMALL"])

    def test_dimension_scores_coverage(self):
        """维度评分应包含所有维度"""
        ctx = _make_context()
        result = self.agent.run(ctx)
        dims = result["dimension_scores"]
        for d in ["宏观", "技术", "仓位", "市场情绪", "风险控制"]:
            self.assertIn(d, dims, f"Missing dimension: {d}")

    def test_recommendation_valid_values(self):
        """recommendation只能是BUY/BUY_SMALL/WAIT/VETO"""
        ctx = _make_context()
        result = self.agent.run(ctx)
        self.assertIn(result["recommendation"],
                       ["BUY", "BUY_SMALL", "WAIT", "VETO"])


if __name__ == "__main__":
    unittest.main()
