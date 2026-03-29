"""
AI 虚拟盘引擎 — Virtual Portfolio Manager
管理虚拟资金的买卖操作、持仓跟踪、收益计算
"""

import sqlite3
import json
import datetime
import os
import math
from typing import Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "fund_monitor.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_virtual_tables():
    """初始化虚拟盘相关数据库表"""
    conn = _get_conn()
    c = conn.cursor()

    # 虚拟账户表
    c.execute("""
        CREATE TABLE IF NOT EXISTS vp_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            initial_cash REAL NOT NULL DEFAULT 300000,
            current_cash REAL NOT NULL DEFAULT 300000,
            total_invested REAL NOT NULL DEFAULT 0,
            total_withdrawn REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
        )
    """)

    # 虚拟持仓表
    c.execute("""
        CREATE TABLE IF NOT EXISTS vp_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            fund_code TEXT NOT NULL,
            fund_name TEXT NOT NULL,
            shares REAL NOT NULL DEFAULT 0,
            avg_cost_nav REAL NOT NULL DEFAULT 0,
            total_cost REAL NOT NULL DEFAULT 0,
            last_nav REAL,
            last_nav_date TEXT,
            UNIQUE(account_id, fund_code)
        )
    """)

    # 虚拟交易记录表
    c.execute("""
        CREATE TABLE IF NOT EXISTS vp_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            trade_date TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            fund_name TEXT NOT NULL,
            direction TEXT NOT NULL,         -- BUY / SELL
            amount REAL NOT NULL,            -- 金额（元）
            nav REAL,                        -- 成交净值
            shares REAL,                     -- 份额
            d_score REAL,                    -- 决策时的D分
            m_score REAL,                    -- 宏观M分
            s_score REAL,                    -- 行业S分
            c_score REAL,                    -- 微观C分
            regime TEXT,                     -- 市场状态
            recommendation TEXT,             -- BUY/SELL/WAIT
            reasoning TEXT                   -- AI决策理由
        )
    """)

    # 每日净值快照（用于画收益曲线）
    c.execute("""
        CREATE TABLE IF NOT EXISTS vp_daily_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL,
            total_assets REAL NOT NULL,      -- 总资产 = 现金 + 持仓市值
            total_cash REAL NOT NULL,
            total_holdings_value REAL NOT NULL,
            daily_return_pct REAL,           -- 日收益率
            cumulative_return_pct REAL,      -- 累计收益率
            benchmark_return_pct REAL,       -- 基准（沪深300）累计收益率
            UNIQUE(account_id, snapshot_date)
        )
    """)

    # AI迭代日志表
    c.execute("""
        CREATE TABLE IF NOT EXISTS vp_iteration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            iteration_date TEXT NOT NULL,
            iteration_num INTEGER NOT NULL,
            period_start TEXT,
            period_end TEXT,
            total_trades INTEGER,
            win_rate REAL,                   -- 胜率
            total_return_pct REAL,           -- 期间收益率
            benchmark_return_pct REAL,       -- 期间基准收益率
            alpha REAL,                      -- 超额收益
            max_drawdown REAL,               -- 最大回撤
            sharpe_ratio REAL,               -- 夏普比率
            -- 因子权重变更
            old_weights TEXT,                -- JSON: 旧权重
            new_weights TEXT,                -- JSON: 新权重
            weight_changes TEXT,             -- JSON: 变更说明
            -- 因子评估
            factor_accuracy TEXT,            -- JSON: 各因子预测准确率
            factor_contribution TEXT,        -- JSON: 各因子对收益贡献
            -- 决策总结
            best_trades TEXT,                -- JSON: 最佳交易
            worst_trades TEXT,               -- JSON: 最差交易
            lessons_learned TEXT,            -- 本轮迭代总结
            changes_made TEXT                -- 具体修改了什么
        )
    """)

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════
# 账户管理
# ══════════════════════════════════════════════

def get_or_create_account(initial_cash: float = 300000) -> Dict:
    """获取或创建虚拟账户"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM vp_account WHERE status='active' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row:
        result = dict(row)
        conn.close()
        return result

    c.execute(
        "INSERT INTO vp_account (created_at, initial_cash, current_cash) VALUES (?, ?, ?)",
        (datetime.datetime.now().isoformat(), initial_cash, initial_cash)
    )
    conn.commit()
    account_id = c.lastrowid
    c.execute("SELECT * FROM vp_account WHERE id=?", (account_id,))
    result = dict(c.fetchone())
    conn.close()
    return result


def get_account_summary(account_id: int) -> Dict:
    """获取账户汇总信息"""
    conn = _get_conn()
    c = conn.cursor()

    c.execute("SELECT * FROM vp_account WHERE id=?", (account_id,))
    account = dict(c.fetchone())

    # 持仓列表
    c.execute("SELECT * FROM vp_holdings WHERE account_id=? AND shares > 0", (account_id,))
    holdings = [dict(r) for r in c.fetchall()]

    # 计算持仓总市值
    total_holdings_value = sum(
        h["shares"] * (h["last_nav"] or h["avg_cost_nav"])
        for h in holdings
    )

    # 总资产
    total_assets = account["current_cash"] + total_holdings_value
    initial = account["initial_cash"]
    total_return = total_assets - initial
    total_return_pct = (total_return / initial * 100) if initial else 0

    # 交易统计
    c.execute("SELECT COUNT(*) as cnt FROM vp_trades WHERE account_id=?", (account_id,))
    trade_count = c.fetchone()["cnt"]

    c.execute("""
        SELECT COUNT(*) as cnt FROM vp_trades
        WHERE account_id=? AND direction='SELL'
        AND amount > 0
    """, (account_id,))
    sell_count = c.fetchone()["cnt"]

    # 最近快照
    c.execute("""
        SELECT * FROM vp_daily_snapshot
        WHERE account_id=?
        ORDER BY snapshot_date DESC LIMIT 1
    """, (account_id,))
    latest_snap = c.fetchone()
    latest_snap = dict(latest_snap) if latest_snap else None

    conn.close()

    return {
        "account": account,
        "holdings": holdings,
        "total_holdings_value": total_holdings_value,
        "total_assets": total_assets,
        "total_return": total_return,
        "total_return_pct": total_return_pct,
        "trade_count": trade_count,
        "cash": account["current_cash"],
        "latest_snapshot": latest_snap,
    }


# ══════════════════════════════════════════════
# 交易执行
# ══════════════════════════════════════════════

def execute_virtual_buy(
    account_id: int,
    fund_code: str,
    fund_name: str,
    amount: float,
    nav: float,
    scores: Dict = None,
    reasoning: str = "",
) -> Dict:
    """执行虚拟买入"""
    if amount <= 0 or nav <= 0:
        return {"success": False, "error": "金额或净值无效"}

    conn = _get_conn()
    c = conn.cursor()

    # 检查余额
    c.execute("SELECT current_cash FROM vp_account WHERE id=?", (account_id,))
    cash = c.fetchone()["current_cash"]
    if cash < amount:
        conn.close()
        return {"success": False, "error": f"现金不足：可用 ¥{cash:,.0f}，需要 ¥{amount:,.0f}"}

    shares = amount / nav
    scores = scores or {}

    # 更新现金
    c.execute(
        "UPDATE vp_account SET current_cash = current_cash - ?, total_invested = total_invested + ? WHERE id=?",
        (amount, amount, account_id)
    )

    # 更新持仓（合并成本）
    c.execute(
        "SELECT * FROM vp_holdings WHERE account_id=? AND fund_code=?",
        (account_id, fund_code)
    )
    existing = c.fetchone()
    if existing:
        old_shares = existing["shares"]
        old_cost = existing["total_cost"]
        new_shares = old_shares + shares
        new_cost = old_cost + amount
        new_avg = new_cost / new_shares if new_shares > 0 else 0
        c.execute("""
            UPDATE vp_holdings
            SET shares=?, avg_cost_nav=?, total_cost=?, last_nav=?, last_nav_date=?
            WHERE account_id=? AND fund_code=?
        """, (new_shares, new_avg, new_cost, nav,
              datetime.date.today().isoformat(), account_id, fund_code))
    else:
        c.execute("""
            INSERT INTO vp_holdings (account_id, fund_code, fund_name, shares, avg_cost_nav, total_cost, last_nav, last_nav_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (account_id, fund_code, fund_name, shares, nav, amount, nav,
              datetime.date.today().isoformat()))

    # 记录交易
    c.execute("""
        INSERT INTO vp_trades (account_id, trade_date, fund_code, fund_name, direction,
            amount, nav, shares, d_score, m_score, s_score, c_score, regime, recommendation, reasoning)
        VALUES (?, ?, ?, ?, 'BUY', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        account_id, datetime.date.today().isoformat(), fund_code, fund_name,
        amount, nav, shares,
        scores.get("d_score"), scores.get("m_score"), scores.get("s_score"),
        scores.get("c_score"), scores.get("regime"), scores.get("recommendation"),
        reasoning,
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "direction": "BUY",
        "fund_code": fund_code,
        "amount": amount,
        "nav": nav,
        "shares": shares,
    }


def execute_virtual_sell(
    account_id: int,
    fund_code: str,
    fund_name: str,
    amount: float,
    nav: float,
    scores: Dict = None,
    reasoning: str = "",
) -> Dict:
    """执行虚拟卖出"""
    if amount <= 0 or nav <= 0:
        return {"success": False, "error": "金额或净值无效"}

    conn = _get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT * FROM vp_holdings WHERE account_id=? AND fund_code=?",
        (account_id, fund_code)
    )
    holding = c.fetchone()
    if not holding or holding["shares"] <= 0:
        conn.close()
        return {"success": False, "error": f"未持有 {fund_name}"}

    shares_to_sell = amount / nav
    if shares_to_sell > holding["shares"]:
        shares_to_sell = holding["shares"]
        amount = shares_to_sell * nav

    scores = scores or {}

    # 更新现金
    c.execute(
        "UPDATE vp_account SET current_cash = current_cash + ?, total_withdrawn = total_withdrawn + ? WHERE id=?",
        (amount, amount, account_id)
    )

    # 更新持仓
    new_shares = holding["shares"] - shares_to_sell
    new_cost = holding["total_cost"] * (new_shares / holding["shares"]) if holding["shares"] > 0 else 0
    if new_shares < 0.01:
        c.execute("DELETE FROM vp_holdings WHERE account_id=? AND fund_code=?", (account_id, fund_code))
    else:
        c.execute("""
            UPDATE vp_holdings SET shares=?, total_cost=?, last_nav=?, last_nav_date=?
            WHERE account_id=? AND fund_code=?
        """, (new_shares, new_cost, nav, datetime.date.today().isoformat(), account_id, fund_code))

    # 记录交易
    c.execute("""
        INSERT INTO vp_trades (account_id, trade_date, fund_code, fund_name, direction,
            amount, nav, shares, d_score, m_score, s_score, c_score, regime, recommendation, reasoning)
        VALUES (?, ?, ?, ?, 'SELL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        account_id, datetime.date.today().isoformat(), fund_code, fund_name,
        amount, nav, shares_to_sell,
        scores.get("d_score"), scores.get("m_score"), scores.get("s_score"),
        scores.get("c_score"), scores.get("regime"), scores.get("recommendation"),
        reasoning,
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "direction": "SELL",
        "fund_code": fund_code,
        "amount": amount,
        "nav": nav,
        "shares": shares_to_sell,
    }


# ══════════════════════════════════════════════
# 每日快照 & 收益计算
# ══════════════════════════════════════════════

def update_holdings_nav(account_id: int, nav_map: Dict[str, float]):
    """更新所有持仓的最新净值"""
    conn = _get_conn()
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    for code, nav in nav_map.items():
        if nav and nav > 0:
            c.execute("""
                UPDATE vp_holdings SET last_nav=?, last_nav_date=?
                WHERE account_id=? AND fund_code=? AND shares > 0
            """, (nav, today, account_id, code))
    conn.commit()
    conn.close()


def take_daily_snapshot(account_id: int, benchmark_cumulative: float = 0.0) -> Dict:
    """拍摄每日净值快照"""
    conn = _get_conn()
    c = conn.cursor()

    c.execute("SELECT * FROM vp_account WHERE id=?", (account_id,))
    account = dict(c.fetchone())

    c.execute("SELECT * FROM vp_holdings WHERE account_id=? AND shares > 0", (account_id,))
    holdings = [dict(r) for r in c.fetchall()]

    total_holdings = sum(h["shares"] * (h["last_nav"] or h["avg_cost_nav"]) for h in holdings)
    total_assets = account["current_cash"] + total_holdings
    initial = account["initial_cash"]
    cum_return = ((total_assets - initial) / initial * 100) if initial else 0

    # 获取前一天快照计算日收益
    c.execute("""
        SELECT total_assets FROM vp_daily_snapshot
        WHERE account_id=? ORDER BY snapshot_date DESC LIMIT 1
    """, (account_id,))
    prev = c.fetchone()
    prev_assets = prev["total_assets"] if prev else initial
    daily_return = ((total_assets - prev_assets) / prev_assets * 100) if prev_assets else 0

    today = datetime.date.today().isoformat()
    c.execute("""
        INSERT OR REPLACE INTO vp_daily_snapshot
        (account_id, snapshot_date, total_assets, total_cash, total_holdings_value,
         daily_return_pct, cumulative_return_pct, benchmark_return_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (account_id, today, total_assets, account["current_cash"],
          total_holdings, daily_return, cum_return, benchmark_cumulative))

    conn.commit()
    conn.close()

    return {
        "date": today,
        "total_assets": total_assets,
        "cash": account["current_cash"],
        "holdings_value": total_holdings,
        "daily_return_pct": daily_return,
        "cumulative_return_pct": cum_return,
    }


def get_performance_history(account_id: int, days: int = 90) -> List[Dict]:
    """获取收益曲线历史"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM vp_daily_snapshot
        WHERE account_id=?
        ORDER BY snapshot_date DESC LIMIT ?
    """, (account_id, days))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows[::-1]


def get_trade_history(account_id: int, limit: int = 50) -> List[Dict]:
    """获取交易历史"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM vp_trades
        WHERE account_id=?
        ORDER BY trade_date DESC, id DESC LIMIT ?
    """, (account_id, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ══════════════════════════════════════════════
# 性能指标计算
# ══════════════════════════════════════════════

def calculate_performance_metrics(account_id: int) -> Dict:
    """计算完整性能指标"""
    snapshots = get_performance_history(account_id, days=365)
    trades = get_trade_history(account_id, limit=500)

    if not snapshots:
        return {
            "total_return_pct": 0, "annual_return_pct": 0,
            "max_drawdown_pct": 0, "sharpe_ratio": 0,
            "win_rate": 0, "total_trades": 0,
            "avg_trade_return": 0, "profit_factor": 0,
            "trading_days": 0,
        }

    # 累计收益
    total_return_pct = snapshots[-1].get("cumulative_return_pct", 0)
    trading_days = len(snapshots)

    # 年化收益
    if trading_days > 1:
        years = trading_days / 252
        annual_factor = (1 + total_return_pct / 100)
        annual_return_pct = ((annual_factor ** (1 / years)) - 1) * 100 if years > 0 else 0
    else:
        annual_return_pct = 0

    # 最大回撤
    peak = 0
    max_dd = 0
    for snap in snapshots:
        val = snap["total_assets"]
        if val > peak:
            peak = val
        dd = (val - peak) / peak if peak > 0 else 0
        if dd < max_dd:
            max_dd = dd

    # 夏普比率 (假设无风险利率 2%)
    daily_returns = [s.get("daily_return_pct", 0) or 0 for s in snapshots]
    if len(daily_returns) > 1:
        import numpy as np
        dr = np.array(daily_returns)
        avg_daily = np.mean(dr)
        std_daily = np.std(dr)
        sharpe = ((avg_daily - 2.0 / 252) / std_daily * math.sqrt(252)) if std_daily > 0 else 0
    else:
        sharpe = 0

    # 胜率（基于卖出交易）
    sell_trades = [t for t in trades if t["direction"] == "SELL"]
    total_trades = len(trades)
    # 简化：暂用日收益正负来估算
    positive_days = sum(1 for d in daily_returns if d > 0)
    win_rate = (positive_days / len(daily_returns) * 100) if daily_returns else 0

    return {
        "total_return_pct": round(total_return_pct, 2),
        "annual_return_pct": round(annual_return_pct, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "win_rate": round(win_rate, 1),
        "total_trades": total_trades,
        "trading_days": trading_days,
        "daily_returns": daily_returns,
    }


# ══════════════════════════════════════════════
# AI 自动分析 & 执行
# ══════════════════════════════════════════════

def ai_daily_analysis(
    account_id: int,
    funds_config: List[Dict],
    snapshot: Dict,
    score_macro_fn,
    score_sector_fn,
    score_fund_micro_fn,
    composite_score_fn,
    detect_regime_fn,
    get_fund_realtime_fn,
    compute_technical_fn,
    get_fund_history_fn,
) -> List[Dict]:
    """
    AI每日自动分析所有基金并执行虚拟交易
    返回今日所有交易操作列表
    """
    regime_name, regime_cfg = detect_regime_fn(snapshot)
    m_result = score_macro_fn(snapshot)
    m_sc = m_result["score"]

    actions = []

    for fund_cfg in funds_config:
        code = fund_cfg["code"]
        name = fund_cfg["name"]
        sector = fund_cfg.get("sector", "")

        # 获取实时净值
        realtime = get_fund_realtime_fn(code)
        nav = realtime.get("nav") or realtime.get("est_nav")
        if not nav:
            continue

        # 技术指标
        df = get_fund_history_fn(code, page_size=180)
        tech = compute_technical_fn(df) if not df.empty else {}

        # 三层评分
        s_result = score_sector_fn(sector, snapshot)
        s_sc = s_result["score"]
        c_result = score_fund_micro_fn(fund_cfg, tech)
        c_sc = c_result["score"]
        comp = composite_score_fn(m_sc, s_sc, c_sc, regime_name)

        d_score = comp["d_score"]
        rec = comp["recommendation"]

        scores_dict = {
            "d_score": d_score,
            "m_score": m_sc,
            "s_score": s_sc,
            "c_score": c_sc,
            "regime": regime_name,
            "recommendation": rec,
        }

        # 决定操作
        action = None
        target_pct = fund_cfg.get("target_pct", 0.08)
        summary = get_account_summary(account_id)
        total_assets = summary["total_assets"]
        target_amount = total_assets * target_pct
        cash = summary["cash"]

        # 查找当前持仓
        current_holding = next(
            (h for h in summary["holdings"] if h["fund_code"] == code), None
        )
        current_value = (current_holding["shares"] * nav) if current_holding else 0

        if rec == "BUY" and d_score >= 1.0:
            gap = target_amount - current_value
            buy_amount = min(gap * 0.4, cash * 0.15, 10000)
            if buy_amount >= 100:
                result = execute_virtual_buy(
                    account_id, code, name, round(buy_amount / 100) * 100,
                    nav, scores_dict,
                    f"D={d_score:+.2f} 积极买入：全球{m_sc:+.1f} 行业{s_sc:+.1f} 基金{c_sc:+.1f}"
                )
                if result["success"]:
                    action = result

        elif rec == "BUY_SMALL" and d_score >= 0.3:
            gap = target_amount - current_value
            buy_amount = min(gap * 0.2, cash * 0.08, 5000)
            if buy_amount >= 100:
                result = execute_virtual_buy(
                    account_id, code, name, round(buy_amount / 100) * 100,
                    nav, scores_dict,
                    f"D={d_score:+.2f} 小额买入：信号偏正但不够强"
                )
                if result["success"]:
                    action = result

        elif rec == "VETO" and d_score < -0.8 and current_holding:
            sell_pct = 0.25 if d_score < -1.2 else 0.15
            sell_amount = current_value * sell_pct
            if sell_amount >= 100:
                result = execute_virtual_sell(
                    account_id, code, name, round(sell_amount / 100) * 100,
                    nav, scores_dict,
                    f"D={d_score:+.2f} 风险减仓：多维度发出警告"
                )
                if result["success"]:
                    action = result

        if action:
            action["fund_name"] = name
            action["d_score"] = d_score
            action["rec"] = rec
            actions.append(action)

    return actions


# ══════════════════════════════════════════════
# 迭代日志
# ══════════════════════════════════════════════

def get_iteration_logs(limit: int = 20) -> List[Dict]:
    """获取迭代日志"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM vp_iteration_log ORDER BY iteration_date DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for row in rows:
        for field in ["old_weights", "new_weights", "weight_changes",
                       "factor_accuracy", "factor_contribution",
                       "best_trades", "worst_trades"]:
            if row.get(field):
                try:
                    row[field] = json.loads(row[field])
                except Exception:
                    pass
    return rows


def save_iteration_log(log: Dict) -> int:
    """保存一轮迭代结果"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO vp_iteration_log (
            iteration_date, iteration_num, period_start, period_end,
            total_trades, win_rate, total_return_pct, benchmark_return_pct,
            alpha, max_drawdown, sharpe_ratio,
            old_weights, new_weights, weight_changes,
            factor_accuracy, factor_contribution,
            best_trades, worst_trades, lessons_learned, changes_made
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log.get("iteration_date", datetime.date.today().isoformat()),
        log.get("iteration_num", 1),
        log.get("period_start"), log.get("period_end"),
        log.get("total_trades", 0), log.get("win_rate", 0),
        log.get("total_return_pct", 0), log.get("benchmark_return_pct", 0),
        log.get("alpha", 0), log.get("max_drawdown", 0),
        log.get("sharpe_ratio", 0),
        json.dumps(log.get("old_weights", {}), ensure_ascii=False),
        json.dumps(log.get("new_weights", {}), ensure_ascii=False),
        json.dumps(log.get("weight_changes", []), ensure_ascii=False),
        json.dumps(log.get("factor_accuracy", {}), ensure_ascii=False),
        json.dumps(log.get("factor_contribution", {}), ensure_ascii=False),
        json.dumps(log.get("best_trades", []), ensure_ascii=False),
        json.dumps(log.get("worst_trades", []), ensure_ascii=False),
        log.get("lessons_learned", ""),
        log.get("changes_made", ""),
    ))
    conn.commit()
    log_id = c.lastrowid
    conn.close()
    return log_id
