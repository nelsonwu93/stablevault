"""
QA测试用例 — 微观分析引擎 (engine/micro_analysis.py)
注意：数据获取依赖网络，这里测试逻辑层（使用mock数据）
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.micro_analysis import (
    analyze_holdings_fundamentals,
    analyze_position_changes,
    analyze_fund_style,
    analyze_fund_manager,
    full_micro_analysis,
)


class TestAnalyzeHoldingsFundamentals(unittest.TestCase):
    """持仓基本面分析测试"""

    @patch("engine.micro_analysis._get_fund_holdings_detail")
    @patch("engine.micro_analysis._get_stock_fundamentals")
    def test_normal_holdings(self, mock_fund, mock_holdings):
        """正常持仓数据分析"""
        mock_holdings.return_value = [
            {"stock_code": "600036", "stock_name": "招商银行", "hold_pct": 8.0, "market": "SH"},
            {"stock_code": "000001", "stock_name": "平安银行", "hold_pct": 6.0, "market": "SZ"},
        ]
        mock_fund.return_value = {
            "pe": 10, "pb": 1.2, "market_cap": 5000,
            "industry": "银行", "revenue_growth": 8.0,
            "profit_growth": 12.0, "roe": 15.0,
        }
        result = analyze_holdings_fundamentals("000001")
        self.assertIn("holdings", result)
        self.assertEqual(len(result["holdings"]), 2)
        self.assertIn("avg_pe", result)
        self.assertIn("micro_score", result)
        self.assertGreaterEqual(result["micro_score"], -2)
        self.assertLessEqual(result["micro_score"], 2)

    @patch("engine.micro_analysis._get_fund_holdings_detail")
    def test_empty_holdings(self, mock_holdings):
        """无持仓数据"""
        mock_holdings.return_value = []
        result = analyze_holdings_fundamentals("000001")
        self.assertEqual(result["score"], 0)
        self.assertEqual(len(result["holdings"]), 0)

    @patch("engine.micro_analysis._get_fund_holdings_detail")
    @patch("engine.micro_analysis._get_stock_fundamentals")
    def test_high_pe_risk(self, mock_fund, mock_holdings):
        """高PE触发风险提示"""
        mock_holdings.return_value = [
            {"stock_code": "300001", "stock_name": "高PE股", "hold_pct": 10.0, "market": "SZ"},
        ]
        mock_fund.return_value = {
            "pe": 100, "pb": 5.0, "market_cap": 200,
            "industry": "科技", "revenue_growth": 5.0,
            "profit_growth": -30.0, "roe": 3.0,
        }
        result = analyze_holdings_fundamentals("000001")
        self.assertTrue(len(result.get("risk_flags", [])) > 0)

    @patch("engine.micro_analysis._get_fund_holdings_detail")
    @patch("engine.micro_analysis._get_stock_fundamentals")
    def test_concentration_risk(self, mock_fund, mock_holdings):
        """集中度风险"""
        mock_holdings.return_value = [
            {"stock_code": "600036", "stock_name": "A", "hold_pct": 15.0, "market": "SH"},
            {"stock_code": "600037", "stock_name": "B", "hold_pct": 12.0, "market": "SH"},
            {"stock_code": "600038", "stock_name": "C", "hold_pct": 10.0, "market": "SH"},
        ]
        mock_fund.return_value = {
            "pe": 20, "pb": 2.0, "market_cap": 3000,
            "industry": "金融", "revenue_growth": 10.0,
            "profit_growth": 15.0, "roe": 12.0,
        }
        result = analyze_holdings_fundamentals("000001")
        self.assertEqual(result["concentration_risk"], "高")


class TestAnalyzePositionChanges(unittest.TestCase):
    """持仓变动测试"""

    @patch("engine.micro_analysis._get_position_changes")
    def test_no_changes(self, mock_changes):
        mock_changes.return_value = []
        result = analyze_position_changes("000001")
        self.assertEqual(result["turnover_signal"], "unknown")

    @patch("engine.micro_analysis._get_position_changes")
    def test_high_turnover(self, mock_changes):
        mock_changes.return_value = [
            {"stock_code": "001", "stock_name": "A", "hold_pct": 5, "change_type": "新进"},
            {"stock_code": "002", "stock_name": "B", "hold_pct": 4, "change_type": "新进"},
            {"stock_code": "003", "stock_name": "C", "hold_pct": 0, "change_type": "退出"},
            {"stock_code": "004", "stock_name": "D", "hold_pct": 0, "change_type": "退出"},
            {"stock_code": "005", "stock_name": "E", "hold_pct": 0, "change_type": "退出"},
        ]
        result = analyze_position_changes("000001")
        self.assertEqual(result["turnover_signal"], "high")


class TestAnalyzeFundStyle(unittest.TestCase):
    """基金风格分析测试"""

    def test_large_cap_value(self):
        """大盘价值风格"""
        holdings = {
            "holdings": [
                {"cap_class": "大盘股", "hold_pct": 30},
                {"cap_class": "大盘股", "hold_pct": 20},
                {"cap_class": "中盘股", "hold_pct": 10},
            ],
            "avg_pe": 12,
            "avg_growth_score": -0.2,
            "industry_distribution": {"银行": 30, "地产": 20},
        }
        result = analyze_fund_style("000001", holdings)
        self.assertEqual(result["cap_style"], "大盘")
        self.assertEqual(result["value_style"], "价值")

    def test_small_cap_growth(self):
        """小盘成长风格"""
        holdings = {
            "holdings": [
                {"cap_class": "小盘股", "hold_pct": 25},
                {"cap_class": "小盘股", "hold_pct": 20},
                {"cap_class": "中盘股", "hold_pct": 15},
            ],
            "avg_pe": 60,
            "avg_growth_score": 1.5,
            "industry_distribution": {"科技": 30, "医药": 30},
        }
        result = analyze_fund_style("000001", holdings)
        self.assertEqual(result["cap_style"], "小盘")
        self.assertEqual(result["value_style"], "成长")

    def test_empty_data(self):
        result = analyze_fund_style("000001", {"holdings": []})
        self.assertEqual(result["style"], "未知")


class TestAnalyzeFundManager(unittest.TestCase):
    """基金经理评估测试"""

    @patch("engine.micro_analysis._get_manager_info")
    def test_experienced_manager(self, mock_info):
        mock_info.return_value = {
            "name": "张三",
            "experience_years": 10,
            "funds_count": 3,
        }
        result = analyze_fund_manager("000001")
        self.assertEqual(result["manager"], "张三")
        self.assertGreater(result["score"], 0)

    @patch("engine.micro_analysis._get_manager_info")
    def test_novice_manager(self, mock_info):
        mock_info.return_value = {
            "name": "新人",
            "experience_years": 1,
            "funds_count": 2,
        }
        result = analyze_fund_manager("000001")
        self.assertLess(result["score"], 0)

    @patch("engine.micro_analysis._get_manager_info")
    def test_overloaded_manager(self, mock_info):
        """管理基金过多扣分"""
        mock_info.return_value = {
            "name": "忙人",
            "experience_years": 5,
            "funds_count": 12,
        }
        result = analyze_fund_manager("000001")
        # 经验加分被管理过多扣分部分抵消
        self.assertIn("管理精力", result["summary"])

    @patch("engine.micro_analysis._get_manager_info")
    def test_no_data(self, mock_info):
        mock_info.return_value = {}
        result = analyze_fund_manager("000001")
        self.assertEqual(result["manager"], "未知")


class TestFullMicroAnalysis(unittest.TestCase):
    """综合微观分析测试"""

    @patch("engine.micro_analysis._get_manager_info")
    @patch("engine.micro_analysis._get_position_changes")
    @patch("engine.micro_analysis._get_stock_fundamentals")
    @patch("engine.micro_analysis._get_fund_holdings_detail")
    def test_full_report(self, mock_holdings, mock_fund, mock_changes, mock_manager):
        mock_holdings.return_value = [
            {"stock_code": "600036", "stock_name": "招行", "hold_pct": 8, "market": "SH"},
        ]
        mock_fund.return_value = {
            "pe": 10, "pb": 1.2, "market_cap": 5000,
            "industry": "银行", "revenue_growth": 8, "profit_growth": 12, "roe": 15,
        }
        mock_changes.return_value = []
        mock_manager.return_value = {"name": "经理A", "experience_years": 8, "funds_count": 3}

        result = full_micro_analysis("000001")
        self.assertIn("holdings_analysis", result)
        self.assertIn("position_changes", result)
        self.assertIn("style_analysis", result)
        self.assertIn("manager_analysis", result)
        self.assertIn("composite_micro_score", result)
        self.assertGreaterEqual(result["composite_micro_score"], -2)
        self.assertLessEqual(result["composite_micro_score"], 2)


if __name__ == "__main__":
    unittest.main()
