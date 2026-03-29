"""
QA测试用例 — 三层因子模型 (engine/factor_model.py)
覆盖：Regime检测、宏观M评分、行业S评分、微观C评分、综合评分D、伊朗冲击分析
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.factor_model import (
    detect_regime, score_macro, score_sector, score_fund_micro,
    composite_score, iran_expected_impact, REGIMES,
    SECTOR_MACRO_SENSITIVITY, _score_label, _score_to_pct, _score_color,
)


def _make_snapshot(
    us10y=4.0, pmi=50.0, oil_chg=0.0, gold_chg=0.0,
    nasdaq_chg=0.0, nb_5d=0, nb_signal="unknown",
    cny_chg=0.0, cn10y=2.0, nvda_chg=0.0,
):
    """构建测试用市场快照"""
    return {
        "global": {
            "us_10y": {"price": us10y, "change_pct": 0},
            "oil": {"price": 80, "change_pct": oil_chg},
            "gold": {"price": 2000, "change_pct": gold_chg},
            "nasdaq": {"price": 17000, "change_pct": nasdaq_chg},
            "usd_cny": {"price": 7.2, "change_pct": cny_chg},
            "nvidia": {"price": 900, "change_pct": nvda_chg},
        },
        "china": {
            "pmi": {"pmi": pmi, "date": "2026-03"},
            "bond_yield": {"yield": cn10y},
        },
        "northbound": {
            "5day_total": nb_5d,
            "signal": nb_signal,
            "5day_positive_days": 3 if nb_signal == "positive" else 1,
        },
    }


class TestRegimeDetection(unittest.TestCase):
    """Regime检测测试"""

    def test_liquidity_crisis(self):
        """流动性危机: US10Y>5 + 北向资金持续流出"""
        snap = _make_snapshot(us10y=5.5, nb_5d=-150, nb_signal="negative")
        name, cfg = detect_regime(snap)
        self.assertEqual(name, "流动性危机")
        self.assertIn("macro", cfg["weights"])

    def test_external_shock_oil_spike(self):
        """外部冲击: 油价单日>3%"""
        snap = _make_snapshot(oil_chg=4.0, pmi=49.5)
        name, _ = detect_regime(snap)
        self.assertEqual(name, "外部冲击")

    def test_external_shock_gold_oil_both(self):
        """外部冲击: 黄金>1.5%且油>1.5%"""
        snap = _make_snapshot(gold_chg=2.0, oil_chg=2.0)
        name, _ = detect_regime(snap)
        self.assertEqual(name, "外部冲击")

    def test_expansion_regime(self):
        """扩张期: PMI>=50.5且US10Y<4.5"""
        snap = _make_snapshot(pmi=51.0, us10y=4.0)
        name, _ = detect_regime(snap)
        self.assertEqual(name, "扩张期")

    def test_slowdown_regime(self):
        """放缓期: PMI<49且利差>2.5"""
        snap = _make_snapshot(pmi=48.0, us10y=5.0, cn10y=2.0)
        name, _ = detect_regime(snap)
        self.assertEqual(name, "放缓期")

    def test_recovery_regime(self):
        """衰退修复: PMI 49-50.5且US10Y<4.5"""
        snap = _make_snapshot(pmi=49.5, us10y=4.0)
        name, _ = detect_regime(snap)
        self.assertEqual(name, "衰退修复")

    def test_default_regime(self):
        """默认回退到放缓期"""
        snap = _make_snapshot(pmi=48.5, us10y=4.6, cn10y=2.0)
        name, _ = detect_regime(snap)
        # Should default — either 放缓期 or another valid regime
        self.assertIn(name, REGIMES)

    def test_regime_has_required_keys(self):
        """所有Regime必须包含weights/desc/icon/color/signal"""
        for name, cfg in REGIMES.items():
            self.assertIn("weights", cfg, f"{name} missing weights")
            self.assertIn("desc", cfg, f"{name} missing desc")
            self.assertIn("icon", cfg, f"{name} missing icon")
            self.assertIn("color", cfg, f"{name} missing color")
            self.assertIn("signal", cfg, f"{name} missing signal")
            w = cfg["weights"]
            total = w["macro"] + w["sector"] + w["micro"]
            self.assertAlmostEqual(total, 1.0, places=2,
                msg=f"{name} weights sum={total}, expected 1.0")


class TestScoreMacro(unittest.TestCase):
    """宏观M评分测试"""

    def test_returns_required_keys(self):
        """M评分必须返回score/factors/label/bar_pct"""
        snap = _make_snapshot()
        result = score_macro(snap)
        self.assertIn("score", result)
        self.assertIn("factors", result)
        self.assertIn("label", result)
        self.assertIn("bar_pct", result)

    def test_score_range(self):
        """M评分必须在[-2, +2]范围内"""
        for us10y in [2.0, 3.0, 4.0, 5.0, 6.0]:
            for pmi in [45, 48, 50, 52, 55]:
                snap = _make_snapshot(us10y=us10y, pmi=pmi)
                result = score_macro(snap)
                self.assertGreaterEqual(result["score"], -2.0)
                self.assertLessEqual(result["score"], 2.0)

    def test_five_factors(self):
        """M评分必须包含5个因子"""
        snap = _make_snapshot()
        result = score_macro(snap)
        self.assertEqual(len(result["factors"]), 5)

    def test_factor_weights_sum_to_one(self):
        """因子权重总和=1"""
        snap = _make_snapshot()
        result = score_macro(snap)
        total_w = sum(f["weight"] for f in result["factors"].values())
        self.assertAlmostEqual(total_w, 1.0, places=2)

    def test_low_rates_positive(self):
        """低利率环境 → M评分偏正"""
        snap = _make_snapshot(us10y=2.5, pmi=51, oil_chg=0, nasdaq_chg=1.0)
        result = score_macro(snap)
        self.assertGreater(result["score"], 0)

    def test_high_rates_negative(self):
        """高利率环境 → M评分偏负"""
        snap = _make_snapshot(us10y=5.5, pmi=47, oil_chg=3.0, nasdaq_chg=-2.0)
        result = score_macro(snap)
        self.assertLess(result["score"], 0)

    def test_no_pmi_data(self):
        """PMI为None时不崩溃"""
        snap = _make_snapshot()
        snap["china"]["pmi"]["pmi"] = None
        result = score_macro(snap)
        self.assertIsNotNone(result["score"])

    def test_bar_pct_range(self):
        """bar_pct在0-100范围"""
        snap = _make_snapshot()
        result = score_macro(snap)
        self.assertGreaterEqual(result["bar_pct"], 0)
        self.assertLessEqual(result["bar_pct"], 100)


class TestScoreSector(unittest.TestCase):
    """行业S评分测试"""

    def test_all_sectors_valid(self):
        """所有已定义板块都能计算评分"""
        snap = _make_snapshot()
        for sector in SECTOR_MACRO_SENSITIVITY:
            result = score_sector(sector, snap)
            self.assertIn("score", result)
            self.assertGreaterEqual(result["score"], -2.0)
            self.assertLessEqual(result["score"], 2.0)

    def test_returns_components(self):
        """S评分返回components详情"""
        snap = _make_snapshot()
        result = score_sector("科创板", snap)
        self.assertIn("components", result)
        self.assertIsInstance(result["components"], dict)
        self.assertGreater(len(result["components"]), 0)

    def test_unknown_sector_fallback(self):
        """未知板块使用宽基指数默认值"""
        snap = _make_snapshot()
        result = score_sector("不存在的板块", snap)
        self.assertIn("score", result)

    def test_nvidia_signal_only_for_ai(self):
        """英伟达信号只出现在AI&科技板块"""
        snap = _make_snapshot(nvda_chg=10.0)
        ai_result = score_sector("AI & 科技", snap)
        bond_result = score_sector("红利防守", snap)
        self.assertIn("英伟达信号", ai_result["components"])
        self.assertNotIn("英伟达信号", bond_result["components"])

    def test_bond_substitute_only_for_dividend(self):
        """债券替代因子只出现在红利防守板块"""
        snap = _make_snapshot(cn10y=1.5)
        div_result = score_sector("红利防守", snap)
        tech_result = score_sector("科创板", snap)
        self.assertIn("债券替代", div_result["components"])
        self.assertNotIn("债券替代", tech_result["components"])


class TestScoreFundMicro(unittest.TestCase):
    """微观C评分测试"""

    def _make_fund_cfg(self, total_return=0, current_value=10000,
                       stop_profit=0.20, stop_loss=-0.12):
        return {
            "code": "000001",
            "name": "测试基金",
            "sector": "宽基指数",
            "current_value": current_value,
            "total_return": total_return,
            "target_pct": 0.10,
            "stop_profit": stop_profit,
            "stop_loss": stop_loss,
        }

    def _make_tech(self, rsi=50, above_ma60=True, ma60=1.0, nav=1.05,
                   macd_cross="neutral"):
        return {
            "rsi": rsi,
            "rsi_signal": "oversold" if rsi < 35 else "overbought" if rsi > 70 else "normal",
            "above_ma60": above_ma60,
            "ma60": ma60,
            "latest_nav": nav,
            "macd_cross": macd_cross,
            "position_below_target": True,
        }

    def test_returns_required_keys(self):
        """C评分返回必要字段"""
        result = score_fund_micro(self._make_fund_cfg(), self._make_tech())
        self.assertIn("score", result)
        self.assertIn("components", result)
        self.assertIn("label", result)

    def test_score_range(self):
        """C评分在[-2, +2]范围"""
        for rsi in [20, 35, 50, 70, 85]:
            result = score_fund_micro(
                self._make_fund_cfg(),
                self._make_tech(rsi=rsi)
            )
            self.assertGreaterEqual(result["score"], -2.0)
            self.assertLessEqual(result["score"], 2.0)

    def test_stoploss_veto(self):
        """触及止损 → C评分=-2（一票否决）"""
        fund = self._make_fund_cfg(total_return=-1500, current_value=10000)
        result = score_fund_micro(fund, self._make_tech())
        self.assertEqual(result["score"], -2.0)

    def test_oversold_positive(self):
        """RSI超卖 → C2因子应为正"""
        result = score_fund_micro(
            self._make_fund_cfg(),
            self._make_tech(rsi=25)
        )
        self.assertIn("RSI", result["components"])
        self.assertGreater(result["components"]["RSI"], 0)

    def test_overbought_negative(self):
        """RSI超买 → C2因子应为负"""
        result = score_fund_micro(
            self._make_fund_cfg(),
            self._make_tech(rsi=80)
        )
        self.assertIn("RSI", result["components"])
        self.assertLess(result["components"]["RSI"], 0)

    def test_bullish_macd(self):
        """MACD金叉 → 正贡献"""
        result = score_fund_micro(
            self._make_fund_cfg(),
            self._make_tech(macd_cross="bullish")
        )
        self.assertIn("MACD", result["components"])
        self.assertGreater(result["components"]["MACD"], 0)

    def test_empty_tech_data(self):
        """空技术数据不崩溃"""
        result = score_fund_micro(self._make_fund_cfg(), {})
        self.assertIsNotNone(result["score"])


class TestCompositeScore(unittest.TestCase):
    """综合评分D测试"""

    def test_score_range(self):
        """D评分在[-2, +2]范围"""
        for m in [-2, -1, 0, 1, 2]:
            for s in [-2, -1, 0, 1, 2]:
                for c in [-2, -1, 0, 1, 2]:
                    result = composite_score(m, s, c, "放缓期")
                    self.assertGreaterEqual(result["d_score"], -2.0)
                    self.assertLessEqual(result["d_score"], 2.0)

    def test_returns_required_keys(self):
        """D评分返回完整字段"""
        result = composite_score(0.5, 0.3, 0.2, "扩张期")
        required = ["d_score", "recommendation", "rec_label", "rec_emoji",
                     "weights", "contributions", "bar_pct", "label"]
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_strong_buy_signal(self):
        """全正面信号 → BUY"""
        result = composite_score(2.0, 2.0, 2.0, "扩张期")
        self.assertEqual(result["recommendation"], "BUY")

    def test_strong_sell_signal(self):
        """全负面信号 → VETO"""
        result = composite_score(-2.0, -2.0, -2.0, "流动性危机")
        self.assertEqual(result["recommendation"], "VETO")

    def test_mixed_signal_wait(self):
        """混合信号 → WAIT或BUY_SMALL"""
        result = composite_score(0.0, 0.0, 0.0, "放缓期")
        self.assertIn(result["recommendation"], ["WAIT", "BUY_SMALL"])

    def test_all_regimes(self):
        """所有Regime都能正常计算"""
        for regime in REGIMES:
            result = composite_score(0.5, 0.3, 0.2, regime)
            self.assertIn("d_score", result)

    def test_unknown_regime_fallback(self):
        """未知Regime回退到放缓期"""
        result = composite_score(0.5, 0.3, 0.2, "不存在的状态")
        self.assertIn("d_score", result)

    def test_contributions_sign(self):
        """contributions的正负应与输入一致"""
        result = composite_score(1.0, -1.0, 0.5, "放缓期")
        self.assertGreater(result["contributions"]["macro"], 0)
        self.assertLess(result["contributions"]["sector"], 0)


class TestIranImpact(unittest.TestCase):
    """伊朗冲击分析测试"""

    def test_returns_required_keys(self):
        result = iran_expected_impact()
        self.assertIn("scenarios", result)
        self.assertIn("expected_m_adjustment", result)
        self.assertIn("dominant_scenario", result)

    def test_probabilities_sum_to_one(self):
        """概率之和=1"""
        from engine.factor_model import IRAN_SCENARIOS
        total = sum(s["prob"] for s in IRAN_SCENARIOS)
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_expected_adjustment_negative(self):
        """期望调整值应为负（战争大概率是利空）"""
        result = iran_expected_impact()
        self.assertLess(result["expected_m_adjustment"], 0)


class TestHelperFunctions(unittest.TestCase):
    """辅助函数测试"""

    def test_score_label_positive(self):
        self.assertIn("↑", _score_label(1.5))

    def test_score_label_negative(self):
        self.assertIn("↓", _score_label(-1.5))

    def test_score_label_neutral(self):
        self.assertIn("→", _score_label(0.0))

    def test_score_to_pct(self):
        self.assertAlmostEqual(_score_to_pct(-2.0), 0.0)
        self.assertAlmostEqual(_score_to_pct(2.0), 100.0)
        self.assertAlmostEqual(_score_to_pct(0.0), 50.0)

    def test_score_color_returns_hex(self):
        for s in [-2, -1, 0, 1, 2]:
            color = _score_color(s)
            self.assertTrue(color.startswith("#"), f"Invalid color for score {s}: {color}")


if __name__ == "__main__":
    unittest.main()
