"""
QA测试用例 — 配置完整性 (config.py)
覆盖：FUNDS配置字段、SECTOR_TARGETS一致性、CHECKLIST配置
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    FUNDS, PORTFOLIO_CONFIG, SECTOR_TARGETS,
    MACRO_INDICATORS, CHECKLIST_DIMENSIONS, MACRO_TRANSMISSION,
)


class TestFundsConfig(unittest.TestCase):
    """基金配置完整性"""

    def test_funds_not_empty(self):
        self.assertGreater(len(FUNDS), 0)

    def test_required_fields(self):
        """每只基金必须有必要字段"""
        required = ["code", "name", "sector", "current_value",
                     "target_pct", "stop_profit", "stop_loss"]
        for f in FUNDS:
            for field in required:
                self.assertIn(field, f, f"基金{f.get('name','')} 缺少字段: {field}")

    def test_code_format(self):
        """基金代码是6位数字"""
        for f in FUNDS:
            self.assertEqual(len(f["code"]), 6, f"基金代码长度错误: {f['code']}")
            self.assertTrue(f["code"].isdigit(), f"基金代码非数字: {f['code']}")

    def test_target_pct_range(self):
        """target_pct在合理范围 0-1"""
        for f in FUNDS:
            self.assertGreater(f["target_pct"], 0)
            self.assertLessEqual(f["target_pct"], 1.0)

    def test_stop_profit_positive(self):
        """止盈线为正"""
        for f in FUNDS:
            self.assertGreater(f["stop_profit"], 0)

    def test_stop_loss_negative(self):
        """止损线为负"""
        for f in FUNDS:
            self.assertLess(f["stop_loss"], 0)

    def test_sector_exists_in_targets(self):
        """每只基金的板块在SECTOR_TARGETS中有定义"""
        for f in FUNDS:
            self.assertIn(f["sector"], SECTOR_TARGETS,
                          f"基金{f['name']}的板块'{f['sector']}'不在SECTOR_TARGETS中")

    def test_target_pct_sum_reasonable(self):
        """所有基金目标占比之和应≤1"""
        total = sum(f["target_pct"] for f in FUNDS)
        self.assertLessEqual(total, 1.05)  # 允许小误差


class TestPortfolioConfig(unittest.TestCase):
    """投资组合配置测试"""

    def test_required_keys(self):
        for key in ["total_target", "risk_profile", "max_drawdown_alert",
                     "entry_batches", "remaining_to_invest"]:
            self.assertIn(key, PORTFOLIO_CONFIG)

    def test_total_target_positive(self):
        self.assertGreater(PORTFOLIO_CONFIG["total_target"], 0)

    def test_remaining_less_than_total(self):
        self.assertLessEqual(
            PORTFOLIO_CONFIG["remaining_to_invest"],
            PORTFOLIO_CONFIG["total_target"]
        )


class TestSectorTargets(unittest.TestCase):
    """板块目标配置测试"""

    def test_sector_pct_sum_to_one(self):
        """板块目标占比之和=1"""
        total = sum(s["target_pct"] for s in SECTOR_TARGETS.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_colors_are_hex(self):
        """颜色是有效hex"""
        for name, cfg in SECTOR_TARGETS.items():
            self.assertTrue(cfg["color"].startswith("#"),
                            f"{name} color invalid: {cfg['color']}")


class TestChecklistDimensions(unittest.TestCase):
    """Checklist维度配置测试"""

    def test_not_empty(self):
        self.assertGreater(len(CHECKLIST_DIMENSIONS), 0)

    def test_required_fields(self):
        for dim in CHECKLIST_DIMENSIONS:
            for key in ["id", "name", "dimension", "weight"]:
                self.assertIn(key, dim, f"维度缺少字段: {key}")

    def test_weights_sum_to_100(self):
        """权重之和=100"""
        total = sum(d["weight"] for d in CHECKLIST_DIMENSIONS)
        self.assertEqual(total, 100)

    def test_has_veto_items(self):
        """至少有一票否决项"""
        veto_items = [d for d in CHECKLIST_DIMENSIONS if d.get("veto")]
        self.assertGreater(len(veto_items), 0)

    def test_unique_ids(self):
        """id不重复"""
        ids = [d["id"] for d in CHECKLIST_DIMENSIONS]
        self.assertEqual(len(ids), len(set(ids)))


class TestMacroTransmission(unittest.TestCase):
    """宏观传导配置测试"""

    def test_not_empty(self):
        self.assertGreater(len(MACRO_TRANSMISSION), 0)

    def test_chain_is_list(self):
        """每个传导逻辑的chain是列表"""
        for key, cfg in MACRO_TRANSMISSION.items():
            self.assertIsInstance(cfg.get("chain"), list,
                                  f"{key} chain不是列表")
            self.assertGreater(len(cfg["chain"]), 0,
                                f"{key} chain为空")

    def test_impact_valid(self):
        for key, cfg in MACRO_TRANSMISSION.items():
            self.assertIn(cfg.get("impact"),
                          ["positive", "negative", "mixed"],
                          f"{key} impact无效: {cfg.get('impact')}")


if __name__ == "__main__":
    unittest.main()
