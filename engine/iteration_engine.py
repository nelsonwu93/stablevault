"""
AI 自我迭代引擎 — Self-Iteration Engine
每周自动评估虚拟盘表现，对比预测vs实际，调整因子权重
"""

import datetime
import json
import math
import os
from typing import Dict, List, Tuple, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "fund_monitor.db")


def _get_conn():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════
# 核心：自动迭代分析
# ══════════════════════════════════════════════

def run_weekly_iteration(
    account_id: int,
    current_weights: Dict,
    regimes_config: Dict,
) -> Dict:
    """
    运行一轮完整的自我迭代分析
    1. 评估过去7天（或自上次迭代以来）的交易表现
    2. 分析每个因子的预测准确度
    3. 计算新的因子权重
    4. 生成迭代报告

    返回：迭代日志dict，包含新权重和变更说明
    """
    conn = _get_conn()
    c = conn.cursor()

    # 确定评估周期
    c.execute("""
        SELECT MAX(iteration_date) as last_date
        FROM vp_iteration_log
    """)
    row = c.fetchone()
    last_date = row["last_date"] if row and row["last_date"] else None

    if last_date:
        period_start = last_date
    else:
        period_start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    period_end = datetime.date.today().isoformat()

    # 获取期间交易
    c.execute("""
        SELECT * FROM vp_trades
        WHERE account_id=? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (account_id, period_start, period_end))
    trades = [dict(r) for r in c.fetchall()]

    # 获取期间快照
    c.execute("""
        SELECT * FROM vp_daily_snapshot
        WHERE account_id=? AND snapshot_date >= ? AND snapshot_date <= ?
        ORDER BY snapshot_date
    """, (account_id, period_start, period_end))
    snapshots = [dict(r) for r in c.fetchall()]

    # 获取迭代次数
    c.execute("SELECT COUNT(*) as cnt FROM vp_iteration_log")
    iteration_num = c.fetchone()["cnt"] + 1

    conn.close()

    # ── 1. 计算期间表现 ──
    if len(snapshots) >= 2:
        start_assets = snapshots[0]["total_assets"]
        end_assets = snapshots[-1]["total_assets"]
        period_return = ((end_assets - start_assets) / start_assets * 100) if start_assets else 0
        benchmark_return = (snapshots[-1].get("benchmark_return_pct", 0) or 0) - (snapshots[0].get("benchmark_return_pct", 0) or 0)
    else:
        period_return = 0
        benchmark_return = 0

    alpha = period_return - benchmark_return

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

    # 夏普比率
    daily_returns = [s.get("daily_return_pct", 0) or 0 for s in snapshots]
    if len(daily_returns) > 1:
        import numpy as np
        dr = np.array(daily_returns)
        avg = np.mean(dr)
        std = np.std(dr)
        sharpe = ((avg - 2.0/252) / std * math.sqrt(252)) if std > 0 else 0
    else:
        sharpe = 0

    # ── 2. 分析因子准确度 ──
    factor_accuracy = _analyze_factor_accuracy(trades, snapshots)

    # ── 3. 找出最佳和最差交易 ──
    best_trades, worst_trades = _find_notable_trades(trades)

    # ── 4. 计算新权重 ──
    new_weights, weight_changes = _adjust_weights(
        current_weights, factor_accuracy, period_return, alpha, regimes_config
    )

    # ── 5. 生成总结 ──
    lessons = _generate_lessons(
        period_return, benchmark_return, alpha,
        factor_accuracy, best_trades, worst_trades, trades
    )

    changes_desc = _describe_weight_changes(current_weights, new_weights, weight_changes)

    # 胜率
    buy_trades = [t for t in trades if t["direction"] == "BUY"]
    win_count = 0
    for t in buy_trades:
        # 简化判断：买入后D分越高越可能赚钱
        if (t.get("d_score") or 0) > 0:
            win_count += 1
    win_rate = (win_count / len(buy_trades) * 100) if buy_trades else 0

    log = {
        "iteration_date": period_end,
        "iteration_num": iteration_num,
        "period_start": period_start,
        "period_end": period_end,
        "total_trades": len(trades),
        "win_rate": round(win_rate, 1),
        "total_return_pct": round(period_return, 2),
        "benchmark_return_pct": round(benchmark_return, 2),
        "alpha": round(alpha, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "old_weights": current_weights,
        "new_weights": new_weights,
        "weight_changes": weight_changes,
        "factor_accuracy": factor_accuracy,
        "factor_contribution": {},
        "best_trades": best_trades,
        "worst_trades": worst_trades,
        "lessons_learned": lessons,
        "changes_made": changes_desc,
    }

    return log


# ══════════════════════════════════════════════
# 因子准确度分析
# ══════════════════════════════════════════════

def _analyze_factor_accuracy(trades: List[Dict], snapshots: List[Dict]) -> Dict:
    """
    分析各因子预测方向的准确度
    通过对比交易时的因子分数与后续实际表现
    """
    accuracy = {
        "macro": {"correct": 0, "total": 0, "avg_score": 0},
        "sector": {"correct": 0, "total": 0, "avg_score": 0},
        "micro": {"correct": 0, "total": 0, "avg_score": 0},
        "composite": {"correct": 0, "total": 0, "avg_score": 0},
    }

    if not trades or not snapshots:
        return accuracy

    # 简化逻辑：如果期间收益>0，那么看多（正D分）的交易算正确
    # 如果期间收益<0，那么看空（负D分）的交易算正确
    period_positive = (snapshots[-1]["total_assets"] > snapshots[0]["total_assets"]) if len(snapshots) >= 2 else True

    m_scores = []
    s_scores = []
    c_scores = []
    d_scores = []

    for t in trades:
        m = t.get("m_score") or 0
        s = t.get("s_score") or 0
        c = t.get("c_score") or 0
        d = t.get("d_score") or 0

        m_scores.append(m)
        s_scores.append(s)
        c_scores.append(c)
        d_scores.append(d)

        # 宏观因子：正分预测市场好 → 实际涨了就算对
        accuracy["macro"]["total"] += 1
        if (m > 0 and period_positive) or (m < 0 and not period_positive):
            accuracy["macro"]["correct"] += 1

        accuracy["sector"]["total"] += 1
        if (s > 0 and period_positive) or (s < 0 and not period_positive):
            accuracy["sector"]["correct"] += 1

        accuracy["micro"]["total"] += 1
        if (c > 0 and period_positive) or (c < 0 and not period_positive):
            accuracy["micro"]["correct"] += 1

        accuracy["composite"]["total"] += 1
        if (d > 0 and period_positive) or (d < 0 and not period_positive):
            accuracy["composite"]["correct"] += 1

    # 计算准确率和平均分
    for key, scores in [("macro", m_scores), ("sector", s_scores),
                         ("micro", c_scores), ("composite", d_scores)]:
        total = accuracy[key]["total"]
        if total > 0:
            accuracy[key]["accuracy_pct"] = round(accuracy[key]["correct"] / total * 100, 1)
            accuracy[key]["avg_score"] = round(sum(scores) / len(scores), 3)
        else:
            accuracy[key]["accuracy_pct"] = 0

    return accuracy


def _find_notable_trades(trades: List[Dict]) -> Tuple[List, List]:
    """找出最佳和最差交易"""
    if not trades:
        return [], []

    buy_trades = [t for t in trades if t["direction"] == "BUY"]
    sell_trades = [t for t in trades if t["direction"] == "SELL"]

    # 按D分排序：最高D分的买入=最有信心的买入
    best = sorted(buy_trades, key=lambda x: x.get("d_score", 0) or 0, reverse=True)[:3]
    # 最低D分的卖出（或最低D分的买入=最冒险的操作）
    worst = sorted(trades, key=lambda x: x.get("d_score", 0) or 0)[:3]

    best_summary = [
        {"fund": t["fund_name"], "direction": t["direction"],
         "amount": t["amount"], "d_score": t.get("d_score", 0),
         "reasoning": t.get("reasoning", "")}
        for t in best
    ]
    worst_summary = [
        {"fund": t["fund_name"], "direction": t["direction"],
         "amount": t["amount"], "d_score": t.get("d_score", 0),
         "reasoning": t.get("reasoning", "")}
        for t in worst
    ]

    return best_summary, worst_summary


# ══════════════════════════════════════════════
# 权重自动调整
# ══════════════════════════════════════════════

def _adjust_weights(
    current_weights: Dict,
    factor_accuracy: Dict,
    period_return: float,
    alpha: float,
    regimes_config: Dict,
) -> Tuple[Dict, List]:
    """
    基于因子准确度自动调整权重

    规则：
    1. 准确率高的因子 → 权重上调
    2. 准确率低的因子 → 权重下调
    3. 调整幅度受限（每轮最多±5%），避免剧烈变化
    4. 权重归一化，确保总和=1
    """
    changes = []
    new_weights = {}

    # 当前权重
    macro_w = current_weights.get("macro", 0.35)
    sector_w = current_weights.get("sector", 0.35)
    micro_w = current_weights.get("micro", 0.30)

    # 计算调整量
    macro_acc = factor_accuracy.get("macro", {}).get("accuracy_pct", 50)
    sector_acc = factor_accuracy.get("sector", {}).get("accuracy_pct", 50)
    micro_acc = factor_accuracy.get("micro", {}).get("accuracy_pct", 50)

    # 基准线：50%准确率不调整
    # 每偏离10%准确率，调整2%权重
    adjustments = {
        "macro": max(-0.05, min(0.05, (macro_acc - 50) / 10 * 0.02)),
        "sector": max(-0.05, min(0.05, (sector_acc - 50) / 10 * 0.02)),
        "micro": max(-0.05, min(0.05, (micro_acc - 50) / 10 * 0.02)),
    }

    # 如果整体亏损且alpha为负，额外降低最不准确因子的权重
    if period_return < 0 and alpha < 0:
        worst_factor = min(["macro", "sector", "micro"],
                          key=lambda k: factor_accuracy.get(k, {}).get("accuracy_pct", 50))
        adjustments[worst_factor] -= 0.02
        changes.append(f"期间亏损且跑输基准，额外降低最不准确的{worst_factor}因子权重")

    # 应用调整
    new_macro = macro_w + adjustments["macro"]
    new_sector = sector_w + adjustments["sector"]
    new_micro = micro_w + adjustments["micro"]

    # 确保不低于最低值
    new_macro = max(0.15, new_macro)
    new_sector = max(0.15, new_sector)
    new_micro = max(0.15, new_micro)

    # 归一化
    total = new_macro + new_sector + new_micro
    new_macro = new_macro / total
    new_sector = new_sector / total
    new_micro = new_micro / total

    # 归一化后再次确保不低于最低值（归一化可能压低）
    # 迭代收敛到满足约束的权重分配
    for _ in range(5):
        new_macro = max(0.15, new_macro)
        new_sector = max(0.15, new_sector)
        new_micro = max(0.15, new_micro)
        t = new_macro + new_sector + new_micro
        new_macro = new_macro / t
        new_sector = new_sector / t
        new_micro = new_micro / t
    new_macro = round(new_macro, 3)
    new_sector = round(new_sector, 3)
    new_micro = round(1 - new_macro - new_sector, 3)
    # 最终保障
    new_micro = max(0.15, new_micro)

    new_weights = {"macro": new_macro, "sector": new_sector, "micro": new_micro}

    # 记录变更
    for key in ["macro", "sector", "micro"]:
        old = current_weights.get(key, 0)
        new = new_weights[key]
        diff = new - old
        if abs(diff) > 0.001:
            direction = "上调" if diff > 0 else "下调"
            acc = factor_accuracy.get(key, {}).get("accuracy_pct", 0)
            name = {"macro": "宏观", "sector": "行业", "micro": "微观"}[key]
            changes.append(
                f"{name}因子权重{direction} {abs(diff)*100:.1f}%（{old*100:.1f}%→{new*100:.1f}%），"
                f"准确率{acc:.0f}%"
            )

    if not changes:
        changes.append("本轮各因子表现均衡，权重保持不变")

    return new_weights, changes


def _generate_lessons(
    period_return, benchmark_return, alpha,
    factor_accuracy, best_trades, worst_trades, trades,
) -> str:
    """生成本轮迭代的经验总结"""
    parts = []

    # 整体表现
    if period_return > 0:
        parts.append(f"本周期虚拟盘收益 +{period_return:.2f}%")
    else:
        parts.append(f"本周期虚拟盘亏损 {period_return:.2f}%")

    if alpha > 0:
        parts.append(f"跑赢基准 {alpha:.2f}%，策略有效")
    elif alpha < -1:
        parts.append(f"跑输基准 {alpha:.2f}%，需要检视策略")

    # 因子分析
    macro_acc = factor_accuracy.get("macro", {}).get("accuracy_pct", 0)
    sector_acc = factor_accuracy.get("sector", {}).get("accuracy_pct", 0)
    micro_acc = factor_accuracy.get("micro", {}).get("accuracy_pct", 0)

    best_factor = max([("宏观", macro_acc), ("行业", sector_acc), ("微观", micro_acc)], key=lambda x: x[1])
    worst_factor = min([("宏观", macro_acc), ("行业", sector_acc), ("微观", micro_acc)], key=lambda x: x[1])

    parts.append(f"表现最好的因子：{best_factor[0]}（准确率{best_factor[1]:.0f}%）")
    if worst_factor[1] < 40:
        parts.append(f"需改进的因子：{worst_factor[0]}（准确率仅{worst_factor[1]:.0f}%）")

    # 交易量
    parts.append(f"本期共执行 {len(trades)} 笔交易")

    return "；".join(parts)


def _describe_weight_changes(old: Dict, new: Dict, changes: List) -> str:
    """描述权重变更"""
    if not changes:
        return "权重未变更"
    return "\n".join(changes)
