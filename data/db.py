"""
本地数据库层 - SQLite 存储持仓、决策记录、历史数据缓存
"""

import sqlite3
import json
import datetime
import os
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "fund_monitor.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_conn()
    c = conn.cursor()

    # 决策记录表
    c.execute("""
        CREATE TABLE IF NOT EXISTS decision_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            fund_name TEXT NOT NULL,
            trigger_type TEXT,         -- macro / technical / stoploss
            trigger_event TEXT,        -- 触发事件描述
            checklist_score REAL,      -- Checklist总得分
            checklist_detail TEXT,     -- JSON格式的各项检查结果
            decision_chain TEXT,       -- JSON格式的推理链路
            recommendation TEXT,       -- BUY / SELL / WAIT / BUY_SMALL
            suggested_amount REAL,     -- 建议操作金额
            confidence INTEGER,        -- 置信度 1-5
            reasoning TEXT,            -- 完整推理说明
            user_action TEXT,          -- 用户实际操作（可后填）
            user_action_amount REAL,   -- 用户实际操作金额
            user_action_date TEXT,     -- 用户操作日期
            outcome_return_pct REAL,   -- 操作后收益率（事后填入）
            notes TEXT
        )
    """)

    # NAV历史缓存表
    c.execute("""
        CREATE TABLE IF NOT EXISTS nav_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_code TEXT NOT NULL,
            date TEXT NOT NULL,
            nav REAL,
            daily_return_pct REAL,
            UNIQUE(fund_code, date)
        )
    """)

    # 市场快照缓存表
    c.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            data TEXT NOT NULL,   -- JSON
            UNIQUE(snapshot_date)
        )
    """)

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════
# 决策日志
# ══════════════════════════════════════════════

def save_decision(
    fund_code: str,
    fund_name: str,
    trigger_type: str,
    trigger_event: str,
    checklist_score: float,
    checklist_detail: List[Dict],
    decision_chain: List[str],
    recommendation: str,
    suggested_amount: float,
    confidence: int,
    reasoning: str,
    notes: str = "",
) -> int:
    """保存一条买卖建议决策记录，返回记录ID"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO decision_log (
            created_at, fund_code, fund_name, trigger_type, trigger_event,
            checklist_score, checklist_detail, decision_chain,
            recommendation, suggested_amount, confidence, reasoning, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.datetime.now().isoformat(),
        fund_code, fund_name, trigger_type, trigger_event,
        checklist_score,
        json.dumps(checklist_detail, ensure_ascii=False),
        json.dumps(decision_chain, ensure_ascii=False),
        recommendation, suggested_amount, confidence, reasoning, notes,
    ))
    conn.commit()
    record_id = c.lastrowid
    conn.close()
    return record_id


def get_decisions(limit: int = 50, fund_code: str = None) -> List[Dict]:
    """获取决策历史"""
    conn = get_conn()
    c = conn.cursor()
    if fund_code:
        c.execute(
            "SELECT * FROM decision_log WHERE fund_code=? ORDER BY created_at DESC LIMIT ?",
            (fund_code, limit)
        )
    else:
        c.execute("SELECT * FROM decision_log ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    # 反序列化JSON字段
    for row in rows:
        for field in ["checklist_detail", "decision_chain"]:
            if row.get(field):
                try:
                    row[field] = json.loads(row[field])
                except Exception:
                    pass
    return rows


def update_user_action(decision_id: int, action: str, amount: float, date: str):
    """用户填写实际操作结果"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE decision_log
        SET user_action=?, user_action_amount=?, user_action_date=?
        WHERE id=?
    """, (action, amount, date, decision_id))
    conn.commit()
    conn.close()


def update_outcome(decision_id: int, return_pct: float):
    """事后填入操作收益率"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE decision_log SET outcome_return_pct=? WHERE id=?", (return_pct, decision_id))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════
# NAV缓存
# ══════════════════════════════════════════════

def cache_nav(fund_code: str, records: List[Dict]):
    """批量缓存基金净值数据"""
    conn = get_conn()
    c = conn.cursor()
    for r in records:
        c.execute("""
            INSERT OR REPLACE INTO nav_cache (fund_code, date, nav, daily_return_pct)
            VALUES (?, ?, ?, ?)
        """, (fund_code, str(r.get("date", "")), r.get("nav"), r.get("daily_return_pct")))
    conn.commit()
    conn.close()


def get_cached_nav(fund_code: str, days: int = 90) -> List[Dict]:
    """读取缓存的净值历史"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT date, nav, daily_return_pct FROM nav_cache
        WHERE fund_code=?
        ORDER BY date DESC LIMIT ?
    """, (fund_code, days))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows[::-1]  # 正序返回


# ══════════════════════════════════════════════
# 市场快照缓存
# ══════════════════════════════════════════════

def save_market_snapshot(data: Dict):
    """保存市场快照（每日一次）"""
    today = datetime.date.today().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO market_snapshot (snapshot_date, data)
        VALUES (?, ?)
    """, (today, json.dumps(data, ensure_ascii=False)))
    conn.commit()
    conn.close()


def get_latest_snapshot() -> Optional[Dict]:
    """获取最新市场快照"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT data, snapshot_date FROM market_snapshot ORDER BY snapshot_date DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        try:
            return {"data": json.loads(row["data"]), "date": row["snapshot_date"]}
        except Exception:
            return None
    return None
