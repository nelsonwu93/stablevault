"""
QA测试用例 — 数据库层 (data/db.py)
覆盖：初始化、决策记录CRUD、NAV缓存、市场快照
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TEST_DB = os.path.join(tempfile.gettempdir(), "test_db_layer.db")


def _patch_db():
    return patch("data.db.DB_PATH", _TEST_DB)


class TestDbInit(unittest.TestCase):
    """数据库初始化测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_init_creates_tables(self):
        with _patch_db():
            from data.db import init_db, get_conn
            init_db()
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r["name"] for r in c.fetchall()]
            conn.close()
            self.assertIn("decision_log", tables)
            self.assertIn("nav_cache", tables)
            self.assertIn("market_snapshot", tables)

    def test_init_idempotent(self):
        """多次初始化不报错"""
        with _patch_db():
            from data.db import init_db
            init_db()
            init_db()  # 第二次不应报错


class TestDecisionLog(unittest.TestCase):
    """决策记录测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_save_and_get(self):
        with _patch_db():
            from data.db import init_db, save_decision, get_decisions
            init_db()
            rid = save_decision(
                fund_code="000001", fund_name="测试",
                trigger_type="macro", trigger_event="测试事件",
                checklist_score=85.0,
                checklist_detail=[{"name": "a", "passed": True}],
                decision_chain=["step1", "step2"],
                recommendation="BUY",
                suggested_amount=5000,
                confidence=4,
                reasoning="测试推理",
            )
            self.assertGreater(rid, 0)
            rows = get_decisions(limit=10)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["fund_code"], "000001")
            self.assertEqual(rows[0]["recommendation"], "BUY")

    def test_filter_by_fund_code(self):
        with _patch_db():
            from data.db import init_db, save_decision, get_decisions
            init_db()
            save_decision("000001", "A", "macro", "", 80, [], [], "BUY", 5000, 4, "")
            save_decision("000002", "B", "macro", "", 60, [], [], "WAIT", 0, 2, "")
            rows = get_decisions(fund_code="000001")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["fund_code"], "000001")

    def test_update_user_action(self):
        with _patch_db():
            from data.db import init_db, save_decision, update_user_action, get_decisions
            init_db()
            rid = save_decision("000001", "A", "macro", "", 80, [], [], "BUY", 5000, 4, "")
            update_user_action(rid, "BUY", 5000, "2026-03-29")
            rows = get_decisions()
            self.assertEqual(rows[0]["user_action"], "BUY")
            self.assertEqual(rows[0]["user_action_amount"], 5000)

    def test_update_outcome(self):
        with _patch_db():
            from data.db import init_db, save_decision, update_outcome, get_decisions
            init_db()
            rid = save_decision("000001", "A", "macro", "", 80, [], [], "BUY", 5000, 4, "")
            update_outcome(rid, 5.5)
            rows = get_decisions()
            self.assertAlmostEqual(rows[0]["outcome_return_pct"], 5.5)


class TestNavCache(unittest.TestCase):
    """NAV缓存测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_cache_and_retrieve(self):
        with _patch_db():
            from data.db import init_db, cache_nav, get_cached_nav
            init_db()
            records = [
                {"date": "2026-03-28", "nav": 1.5, "daily_return_pct": 0.5},
                {"date": "2026-03-29", "nav": 1.52, "daily_return_pct": 1.3},
            ]
            cache_nav("000001", records)
            cached = get_cached_nav("000001", days=10)
            self.assertEqual(len(cached), 2)
            # 正序返回，最早的在前
            self.assertEqual(cached[0]["date"], "2026-03-28")

    def test_upsert(self):
        """重复日期应更新"""
        with _patch_db():
            from data.db import init_db, cache_nav, get_cached_nav
            init_db()
            cache_nav("000001", [{"date": "2026-03-29", "nav": 1.5, "daily_return_pct": 0.5}])
            cache_nav("000001", [{"date": "2026-03-29", "nav": 1.6, "daily_return_pct": 6.67}])
            cached = get_cached_nav("000001", days=10)
            self.assertEqual(len(cached), 1)
            self.assertAlmostEqual(cached[0]["nav"], 1.6)


class TestMarketSnapshot(unittest.TestCase):
    """市场快照测试"""

    def setUp(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def tearDown(self):
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def test_save_and_get(self):
        with _patch_db():
            from data.db import init_db, save_market_snapshot, get_latest_snapshot
            init_db()
            data = {"global": {"us_10y": 4.0}, "china": {"pmi": 50}}
            save_market_snapshot(data)
            snap = get_latest_snapshot()
            self.assertIsNotNone(snap)
            self.assertEqual(snap["data"]["global"]["us_10y"], 4.0)

    def test_no_snapshot(self):
        with _patch_db():
            from data.db import init_db, get_latest_snapshot
            init_db()
            snap = get_latest_snapshot()
            self.assertIsNone(snap)


if __name__ == "__main__":
    unittest.main()
