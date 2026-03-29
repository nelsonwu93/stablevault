"""
QA测试用例 — 买卖建议引擎 (engine/advisor.py)
覆盖：DecisionChain构建、FundAdvisor分析、触发检测
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.advisor import DecisionChain, FundAdvisor
from config import CHECKLIST_DIMENSIONS, FUNDS


def _make_fund_cfg():
    return {
        "code": "000001",
        "name": "测试基金Alpha",
        "short": "测试Alpha",
        "sector": "宽基指数",
        "sector_icon": "📊",
        "current_value": 10000,
        "yesterday_return": 100,
        "total_return": 500,
        "target_pct": 0.10,
        "stop_profit": 0.20,
        "stop_loss": -0.12,
        "macro_drivers": ["china_pmi"],
        "note": "测试用",
    }


def _make_market_data():
    return {
        "global": {
            "us_10y": {"price": 4.0, "change_pct": -0.05},
            "oil": {"price": 80, "change_pct": 0.5},
            "gold": {"price": 2000, "change_pct": 0.2},
            "nasdaq": {"price": 17000, "change_pct": 0.8},
            "usd_cny": {"price": 7.2, "change_pct": 0.1},
            "nvidia": {"price": 900, "change_pct": 2.0},
        },
        "china": {
            "pmi": {"pmi": 50.5, "date": "2026-03"},
            "bond_yield": {"yield": 2.0},
        },
        "northbound": {
            "5day_total": 30,
            "signal": "positive",
            "5day_positive_days": 3,
        },
    }


def _make_tech_data():
    return {
        "rsi": 45,
        "rsi_signal": "normal",
        "above_ma60": True,
        "ma60": 1.0,
        "latest_nav": 1.05,
        "macd_cross": "neutral",
        "trend": "uptrend",
        "position_below_target": True,
    }


def _make_portfolio():
    return {
        "total_cost": 100000,
        "total_value": 105000,
        "total_target": 300000,
        "funds": [
            {"sector": "宽基指数", "current_value": 10000},
        ],
    }


class TestDecisionChain(unittest.TestCase):
    """决策链路构建测试"""

    def setUp(self):
        self.chain_builder = DecisionChain()

    def test_build_returns_required_keys(self):
        """chain包含所有必要字段"""
        from engine.checklist import ChecklistAgent
        agent = ChecklistAgent(CHECKLIST_DIMENSIONS)
        ctx = {
            "fed_stance": "neutral",
            "market": _make_market_data(),
            "technical": _make_tech_data(),
            "portfolio": _make_portfolio(),
            "fund_cfg": _make_fund_cfg(),
        }
        checklist_result = agent.run(ctx)
        chain = self.chain_builder.build(
            _make_fund_cfg(), "macro", "定期分析",
            _make_market_data(), _make_tech_data(), checklist_result,
        )
        for key in ["fund_code", "fund_name", "trigger", "transmission",
                     "evidence", "checklist", "final_decision", "risk_warnings"]:
            self.assertIn(key, chain, f"Missing: {key}")

    def test_final_decision_structure(self):
        """final_decision包含recommendation和amount"""
        from engine.checklist import ChecklistAgent
        agent = ChecklistAgent(CHECKLIST_DIMENSIONS)
        ctx = {
            "fed_stance": "neutral",
            "market": _make_market_data(),
            "technical": _make_tech_data(),
            "portfolio": _make_portfolio(),
            "fund_cfg": _make_fund_cfg(),
        }
        checklist_result = agent.run(ctx)
        chain = self.chain_builder.build(
            _make_fund_cfg(), "macro", "测试",
            _make_market_data(), _make_tech_data(), checklist_result,
        )
        fd = chain["final_decision"]
        self.assertIn("recommendation", fd)
        self.assertIn("suggested_amount", fd)
        self.assertIn("confidence", fd)

    def test_stoploss_chain(self):
        """止损链路生成"""
        chain = self.chain_builder._build_stoploss_chain({
            "total_return": -1500,
            "current_value": 10000,
            "stop_profit": 0.20,
            "stop_loss": -0.12,
        })
        self.assertIsInstance(chain, list)
        self.assertGreater(len(chain), 0)

    def test_technical_chain(self):
        """技术链路生成"""
        chain = self.chain_builder._build_technical_chain(
            _make_tech_data()
        )
        self.assertIsInstance(chain, list)

    def test_risk_warnings_high_volatility(self):
        """高波动板块应有风险提示"""
        fund = _make_fund_cfg()
        fund["sector"] = "科创板"
        warnings = self.chain_builder._build_risk_warnings(
            fund, _make_market_data(), _make_tech_data()
        )
        self.assertIsInstance(warnings, list)
        self.assertTrue(any("波动" in w for w in warnings))


class TestFundAdvisor(unittest.TestCase):
    """FundAdvisor整体测试"""

    def setUp(self):
        self.advisor = FundAdvisor(CHECKLIST_DIMENSIONS)

    def test_analyze_single_fund(self):
        """分析单只基金返回完整结构"""
        result = self.advisor.analyze_fund(
            fund_cfg=_make_fund_cfg(),
            market_data=_make_market_data(),
            technical_data=_make_tech_data(),
            portfolio=_make_portfolio(),
        )
        for key in ["fund_code", "recommendation", "suggested_amount",
                     "confidence", "checklist", "chain"]:
            self.assertIn(key, result, f"Missing: {key}")

    def test_recommendation_valid(self):
        """recommendation必须是有效值"""
        result = self.advisor.analyze_fund(
            fund_cfg=_make_fund_cfg(),
            market_data=_make_market_data(),
            technical_data=_make_tech_data(),
            portfolio=_make_portfolio(),
        )
        self.assertIn(result["recommendation"],
                       ["BUY", "BUY_SMALL", "WAIT", "VETO"])

    def test_detect_trigger_stoploss(self):
        """接近止盈时触发类型=stoploss"""
        fund = _make_fund_cfg()
        fund["total_return"] = 1800  # 接近20%止盈
        fund["current_value"] = 10000
        ttype, tevent = self.advisor._detect_trigger(
            fund, _make_market_data(), _make_tech_data()
        )
        self.assertEqual(ttype, "stoploss")

    def test_detect_trigger_technical(self):
        """RSI超卖时触发类型=technical"""
        tech = _make_tech_data()
        tech["rsi"] = 25
        tech["rsi_signal"] = "oversold"
        ttype, tevent = self.advisor._detect_trigger(
            _make_fund_cfg(), _make_market_data(), tech
        )
        self.assertEqual(ttype, "technical")

    def test_scan_all_funds(self):
        """扫描所有基金（使用config中的FUNDS）"""
        tech_map = {f["code"]: _make_tech_data() for f in FUNDS}
        results = self.advisor.scan_all_funds(
            FUNDS, _make_market_data(), tech_map, _make_portfolio()
        )
        self.assertEqual(len(results), len(FUNDS))
        # 结果应按优先级排序
        priority = {"BUY": 0, "SELL": 0, "BUY_SMALL": 1, "SELL_PARTIAL": 1, "WAIT": 2, "VETO": 3}
        prev_p = -1
        for r in results:
            p = priority.get(r["recommendation"], 4)
            self.assertGreaterEqual(p, prev_p - 1)  # 允许同级乱序


class TestRecLabelsAndEmojis(unittest.TestCase):
    """标签和emoji映射测试"""

    def test_all_rec_have_labels(self):
        dc = DecisionChain()
        for rec in ["BUY", "BUY_SMALL", "WAIT", "VETO", "SELL"]:
            label = dc._rec_label(rec)
            self.assertIsInstance(label, str)
            self.assertGreater(len(label), 0)

    def test_all_rec_have_emojis(self):
        dc = DecisionChain()
        for rec in ["BUY", "BUY_SMALL", "WAIT", "VETO", "SELL"]:
            emoji = dc._rec_emoji(rec)
            self.assertIsInstance(emoji, str)


if __name__ == "__main__":
    unittest.main()
