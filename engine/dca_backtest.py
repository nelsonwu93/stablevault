"""
定投回测引擎 — DCA Backtest Engine
参考 xalpha 思路，实现多种定投策略回测：
  1. 普通定投 (Fixed DCA)
  2. 智慧定投 (Smart DCA - 低位多投高位少投)
  3. 止盈定投 (Take-Profit DCA)
  4. 均线偏离定投 (MA-Deviation DCA)
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 核心回测框架
# ══════════════════════════════════════════════

class DCABacktestResult:
    """定投回测结果"""

    def __init__(self):
        self.strategy_name = ""
        self.fund_code = ""
        self.fund_name = ""
        self.start_date = None
        self.end_date = None
        self.total_invested = 0.0       # 累计投入
        self.final_value = 0.0          # 期末市值
        self.total_return = 0.0         # 总收益金额
        self.total_return_pct = 0.0     # 总收益率%
        self.annualized_return = 0.0    # 年化收益率%
        self.max_drawdown = 0.0         # 最大回撤%
        self.invest_count = 0           # 投资次数
        self.avg_cost_nav = 0.0         # 平均成本净值
        self.total_shares = 0.0         # 持有份额
        self.history = []               # 逐期明细

    def to_dict(self) -> Dict:
        return {
            "strategy_name": self.strategy_name,
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "start_date": str(self.start_date) if self.start_date else "",
            "end_date": str(self.end_date) if self.end_date else "",
            "total_invested": round(self.total_invested, 2),
            "final_value": round(self.final_value, 2),
            "total_return": round(self.total_return, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return": round(self.annualized_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "invest_count": self.invest_count,
            "avg_cost_nav": round(self.avg_cost_nav, 4),
        }


def _get_monthly_dates(df: pd.DataFrame, day_of_month: int = 15) -> List:
    """从历史数据中按月取定投日期（取最近的交易日）"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    monthly = []
    seen_months = set()
    for _, row in df.iterrows():
        key = (row["date"].year, row["date"].month)
        if key not in seen_months and row["date"].day >= day_of_month:
            monthly.append(row)
            seen_months.add(key)

    if not monthly:
        # 每月取第一个交易日
        for _, row in df.iterrows():
            key = (row["date"].year, row["date"].month)
            if key not in seen_months:
                monthly.append(row)
                seen_months.add(key)

    return monthly


def _compute_backtest_metrics(result: DCABacktestResult, history: List[Dict]):
    """计算回测汇总指标"""
    if not history:
        return

    result.history = history
    result.invest_count = sum(1 for h in history if h["invest_amount"] > 0)
    result.total_invested = sum(h["invest_amount"] for h in history)
    result.total_shares = sum(h["shares_bought"] for h in history)
    result.start_date = history[0]["date"]
    result.end_date = history[-1]["date"]

    last_nav = history[-1]["nav"]
    result.final_value = result.total_shares * last_nav
    result.total_return = result.final_value - result.total_invested
    result.total_return_pct = (result.total_return / result.total_invested * 100) if result.total_invested > 0 else 0
    result.avg_cost_nav = (result.total_invested / result.total_shares) if result.total_shares > 0 else 0

    # 年化收益率
    if result.start_date and result.end_date:
        days = (pd.Timestamp(result.end_date) - pd.Timestamp(result.start_date)).days
        if days > 30 and result.total_invested > 0:
            # 使用内部收益率的近似：(1 + total_return)^(365/days) - 1
            # 但定投的IRR更复杂，这里用简化版
            years = days / 365.25
            if result.total_return_pct > -100:
                result.annualized_return = ((1 + result.total_return_pct / 100) ** (1 / years) - 1) * 100

    # 最大回撤
    peak_value = 0
    max_dd = 0
    cum_invested = 0
    cum_shares = 0
    for h in history:
        cum_invested += h["invest_amount"]
        cum_shares += h["shares_bought"]
        market_val = cum_shares * h["nav"]
        if market_val > peak_value:
            peak_value = market_val
        if peak_value > 0:
            dd = (peak_value - market_val) / peak_value * 100
            max_dd = max(max_dd, dd)
    result.max_drawdown = max_dd


# ══════════════════════════════════════════════
# 策略1：普通定投 (Fixed DCA)
# ══════════════════════════════════════════════

def backtest_fixed_dca(
    df: pd.DataFrame,
    monthly_amount: float = 1000,
    day_of_month: int = 15,
    fund_code: str = "",
    fund_name: str = "",
) -> DCABacktestResult:
    """普通定额定投：每月固定金额买入"""
    result = DCABacktestResult()
    result.strategy_name = "普通定投"
    result.fund_code = fund_code
    result.fund_name = fund_name

    monthly_dates = _get_monthly_dates(df, day_of_month)
    if not monthly_dates:
        return result

    history = []
    for row in monthly_dates:
        nav = float(row["nav"])
        if nav <= 0:
            continue
        shares = monthly_amount / nav
        history.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "nav": nav,
            "invest_amount": monthly_amount,
            "shares_bought": shares,
        })

    _compute_backtest_metrics(result, history)
    return result


# ══════════════════════════════════════════════
# 策略2：智慧定投 (Smart DCA)
# ══════════════════════════════════════════════

def backtest_smart_dca(
    df: pd.DataFrame,
    base_amount: float = 1000,
    ma_window: int = 60,
    day_of_month: int = 15,
    fund_code: str = "",
    fund_name: str = "",
) -> DCABacktestResult:
    """
    智慧定投：根据净值相对均线的位置调整投入金额
    低于均线 → 多投（最多2倍）
    高于均线 → 少投（最少0.5倍）
    """
    result = DCABacktestResult()
    result.strategy_name = f"智慧定投(MA{ma_window})"
    result.fund_code = fund_code
    result.fund_name = fund_name

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df[f"ma{ma_window}"] = df["nav"].rolling(ma_window, min_periods=10).mean()

    monthly_dates = _get_monthly_dates(df, day_of_month)
    if not monthly_dates:
        return result

    history = []
    for row in monthly_dates:
        nav = float(row["nav"])
        if nav <= 0:
            continue

        # 查找该日期的MA值
        date_mask = df["date"] == row["date"]
        ma_val = df.loc[date_mask, f"ma{ma_window}"].values
        ma = float(ma_val[0]) if len(ma_val) > 0 and not pd.isna(ma_val[0]) else nav

        # 计算偏离度
        if ma > 0:
            deviation = (nav - ma) / ma
        else:
            deviation = 0

        # 根据偏离度调整金额
        # 偏离度 < -20%: 投2倍 | -10%: 1.5倍 | 0: 1倍 | +10%: 0.7倍 | >+20%: 0.5倍
        if deviation < -0.20:
            multiplier = 2.0
        elif deviation < -0.10:
            multiplier = 1.5
        elif deviation < 0:
            multiplier = 1.0 + abs(deviation) * 5  # 线性插值
        elif deviation < 0.10:
            multiplier = 1.0 - deviation * 3
        elif deviation < 0.20:
            multiplier = 0.7
        else:
            multiplier = 0.5

        multiplier = max(0.3, min(2.5, multiplier))
        invest = round(base_amount * multiplier, 2)
        shares = invest / nav

        history.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "nav": nav,
            "invest_amount": invest,
            "shares_bought": shares,
            "ma": round(ma, 4),
            "deviation": round(deviation * 100, 1),
            "multiplier": round(multiplier, 2),
        })

    _compute_backtest_metrics(result, history)
    return result


# ══════════════════════════════════════════════
# 策略3：止盈定投 (Take-Profit DCA)
# ══════════════════════════════════════════════

def backtest_takeprofit_dca(
    df: pd.DataFrame,
    monthly_amount: float = 1000,
    take_profit_pct: float = 20.0,
    day_of_month: int = 15,
    fund_code: str = "",
    fund_name: str = "",
) -> DCABacktestResult:
    """
    止盈定投：累计收益率达到阈值时赎回全部，重新开始定投
    模拟止盈后将收益落袋为安
    """
    result = DCABacktestResult()
    result.strategy_name = f"止盈定投({take_profit_pct:.0f}%)"
    result.fund_code = fund_code
    result.fund_name = fund_name

    monthly_dates = _get_monthly_dates(df, day_of_month)
    if not monthly_dates:
        return result

    history = []
    cum_invested = 0
    cum_shares = 0
    realized_profit = 0
    total_invested_all = 0

    for row in monthly_dates:
        nav = float(row["nav"])
        if nav <= 0:
            continue

        # 检查止盈
        if cum_shares > 0 and cum_invested > 0:
            market_val = cum_shares * nav
            profit_pct = (market_val - cum_invested) / cum_invested * 100
            if profit_pct >= take_profit_pct:
                realized_profit += (market_val - cum_invested)
                cum_invested = 0
                cum_shares = 0
                history.append({
                    "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
                    "nav": nav,
                    "invest_amount": 0,
                    "shares_bought": 0,
                    "event": f"止盈赎回 +{profit_pct:.1f}%",
                })
                continue

        # 正常定投
        shares = monthly_amount / nav
        cum_invested += monthly_amount
        cum_shares += shares
        total_invested_all += monthly_amount

        history.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "nav": nav,
            "invest_amount": monthly_amount,
            "shares_bought": shares,
        })

    # 补充止盈收益到最终结果
    _compute_backtest_metrics(result, history)
    result.total_invested = total_invested_all
    result.final_value = cum_shares * monthly_dates[-1]["nav"] + realized_profit + (total_invested_all - cum_invested)
    result.total_return = result.final_value - total_invested_all
    result.total_return_pct = (result.total_return / total_invested_all * 100) if total_invested_all > 0 else 0

    return result


# ══════════════════════════════════════════════
# 策略4：均线偏离定投 (MA-Deviation DCA)
# ══════════════════════════════════════════════

def backtest_ma_deviation_dca(
    df: pd.DataFrame,
    base_amount: float = 1000,
    ma_window: int = 120,
    threshold_buy: float = -0.10,
    threshold_skip: float = 0.15,
    day_of_month: int = 15,
    fund_code: str = "",
    fund_name: str = "",
) -> DCABacktestResult:
    """
    均线偏离定投：
    - 低于MA 10%以上：投2倍
    - 低于MA 0~10%：正常投
    - 高于MA 0~15%：正常投但减半
    - 高于MA 15%以上：暂停定投
    """
    result = DCABacktestResult()
    result.strategy_name = f"均线偏离(MA{ma_window})"
    result.fund_code = fund_code
    result.fund_name = fund_name

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df[f"ma{ma_window}"] = df["nav"].rolling(ma_window, min_periods=20).mean()

    monthly_dates = _get_monthly_dates(df, day_of_month)
    if not monthly_dates:
        return result

    history = []
    for row in monthly_dates:
        nav = float(row["nav"])
        if nav <= 0:
            continue

        date_mask = df["date"] == row["date"]
        ma_val = df.loc[date_mask, f"ma{ma_window}"].values
        ma = float(ma_val[0]) if len(ma_val) > 0 and not pd.isna(ma_val[0]) else nav

        deviation = (nav - ma) / ma if ma > 0 else 0

        if deviation < threshold_buy:
            invest = base_amount * 2.0
        elif deviation < 0:
            invest = base_amount * 1.0
        elif deviation < threshold_skip:
            invest = base_amount * 0.5
        else:
            invest = 0  # 暂停

        shares = invest / nav if invest > 0 else 0
        history.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "nav": nav,
            "invest_amount": round(invest, 2),
            "shares_bought": shares,
            "ma": round(ma, 4),
            "deviation": round(deviation * 100, 1),
        })

    _compute_backtest_metrics(result, history)
    return result


# ══════════════════════════════════════════════
# 综合回测对比
# ══════════════════════════════════════════════

def run_all_strategies(
    df: pd.DataFrame,
    monthly_amount: float = 1000,
    fund_code: str = "",
    fund_name: str = "",
) -> List[DCABacktestResult]:
    """运行所有定投策略并返回对比结果"""
    results = []

    # 1. 普通定投
    r1 = backtest_fixed_dca(df, monthly_amount, fund_code=fund_code, fund_name=fund_name)
    results.append(r1)

    # 2. 智慧定投 (MA60)
    r2 = backtest_smart_dca(df, monthly_amount, ma_window=60, fund_code=fund_code, fund_name=fund_name)
    results.append(r2)

    # 3. 止盈定投 (20%)
    r3 = backtest_takeprofit_dca(df, monthly_amount, take_profit_pct=20.0, fund_code=fund_code, fund_name=fund_name)
    results.append(r3)

    # 4. 均线偏离 (MA120)
    r4 = backtest_ma_deviation_dca(df, monthly_amount, ma_window=120, fund_code=fund_code, fund_name=fund_name)
    results.append(r4)

    return results
