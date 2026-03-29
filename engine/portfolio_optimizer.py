"""
组合优化引擎 — Portfolio Optimizer Engine
参考 PyPortfolioOpt 思路，实现：
  1. 均值-方差优化 (Mean-Variance Optimization / Markowitz)
  2. 有效前沿计算 (Efficient Frontier)
  3. 风险平价 (Risk Parity)
  4. Black-Litterman 模型 (结合因子模型主观观点)
  5. 再平衡建议 (Rebalance Suggestions)
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 1. 收益率 & 协方差矩阵估算
# ══════════════════════════════════════════════

def estimate_returns_and_cov(
    fund_histories: Dict[str, "pd.DataFrame"],
    annualize: bool = True,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    从基金历史净值推算期望收益率和协方差矩阵
    fund_histories: {fund_code: DataFrame(date, nav, daily_return_pct)}
    返回: (expected_returns [n,], cov_matrix [n,n], fund_codes [n])
    """
    import pandas as pd

    codes = sorted(fund_histories.keys())
    if not codes:
        return np.array([]), np.array([[]]), []

    # 构建日收益率矩阵
    returns_dict = {}
    for code in codes:
        df = fund_histories[code]
        if df.empty or "daily_return_pct" not in df.columns:
            continue
        s = df.set_index("date")["daily_return_pct"].dropna() / 100.0
        if len(s) < 20:
            continue
        returns_dict[code] = s

    valid_codes = [c for c in codes if c in returns_dict]
    if len(valid_codes) < 2:
        return np.array([]), np.array([[]]), []

    ret_df = pd.DataFrame(returns_dict)
    ret_df = ret_df.dropna()
    if len(ret_df) < 20:
        return np.array([]), np.array([[]]), []

    mu = ret_df.mean().values
    cov = ret_df.cov().values

    if annualize:
        mu = mu * 252
        cov = cov * 252

    return mu, cov, list(ret_df.columns)


# ══════════════════════════════════════════════
# 2. 均值-方差优化 (Markowitz)
# ══════════════════════════════════════════════

def max_sharpe_weights(
    mu: np.ndarray,
    cov: np.ndarray,
    risk_free_rate: float = 0.02,
    weight_bounds: Tuple[float, float] = (0.02, 0.35),
) -> np.ndarray:
    """
    最大化夏普比率的最优权重
    使用蒙特卡洛模拟 + 梯度搜索（无需scipy.optimize）
    """
    n = len(mu)
    if n == 0:
        return np.array([])

    best_sharpe = -1e10
    best_w = np.ones(n) / n
    lo, hi = weight_bounds

    # 蒙特卡洛搜索
    np.random.seed(42)
    for _ in range(20000):
        w = np.random.dirichlet(np.ones(n))
        # 应用权重上下限
        w = np.clip(w, lo, hi)
        w = w / w.sum()

        port_ret = w @ mu
        port_vol = np.sqrt(w @ cov @ w)
        sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 0 else 0

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_w = w.copy()

    return best_w


def min_volatility_weights(
    cov: np.ndarray,
    weight_bounds: Tuple[float, float] = (0.02, 0.35),
) -> np.ndarray:
    """最小波动率组合权重"""
    n = cov.shape[0]
    if n == 0:
        return np.array([])

    best_vol = 1e10
    best_w = np.ones(n) / n
    lo, hi = weight_bounds

    np.random.seed(123)
    for _ in range(20000):
        w = np.random.dirichlet(np.ones(n))
        w = np.clip(w, lo, hi)
        w = w / w.sum()
        port_vol = np.sqrt(w @ cov @ w)
        if port_vol < best_vol:
            best_vol = port_vol
            best_w = w.copy()

    return best_w


# ══════════════════════════════════════════════
# 3. 有效前沿 (Efficient Frontier)
# ══════════════════════════════════════════════

def compute_efficient_frontier(
    mu: np.ndarray,
    cov: np.ndarray,
    n_points: int = 30,
    weight_bounds: Tuple[float, float] = (0.02, 0.35),
) -> List[Dict]:
    """
    计算有效前沿上的点
    返回: [{return, volatility, sharpe, weights}, ...]
    """
    n = len(mu)
    if n == 0:
        return []

    # 先找收益率范围
    lo, hi = weight_bounds
    min_ret = mu.min()
    max_ret = mu.max()
    target_rets = np.linspace(min_ret * 0.8, max_ret * 1.1, n_points)

    frontier = []
    np.random.seed(77)

    for target in target_rets:
        best_vol = 1e10
        best_w = np.ones(n) / n

        for _ in range(5000):
            w = np.random.dirichlet(np.ones(n))
            w = np.clip(w, lo, hi)
            w = w / w.sum()

            port_ret = w @ mu
            if abs(port_ret - target) > 0.03:
                continue

            port_vol = np.sqrt(w @ cov @ w)
            if port_vol < best_vol:
                best_vol = port_vol
                best_w = w.copy()

        if best_vol < 1e9:
            port_ret = best_w @ mu
            sharpe = (port_ret - 0.02) / best_vol if best_vol > 0 else 0
            frontier.append({
                "return": round(port_ret * 100, 2),
                "volatility": round(best_vol * 100, 2),
                "sharpe": round(sharpe, 3),
                "weights": best_w.tolist(),
            })

    # 去重并按波动率排序
    frontier.sort(key=lambda x: x["volatility"])
    return frontier


# ══════════════════════════════════════════════
# 4. 风险平价 (Risk Parity)
# ══════════════════════════════════════════════

def risk_parity_weights(cov: np.ndarray, max_iter: int = 500) -> np.ndarray:
    """
    风险平价权重：每个资产对组合风险的贡献相等
    使用迭代算法（Spinu 2013）
    """
    n = cov.shape[0]
    if n == 0:
        return np.array([])

    w = np.ones(n) / n
    for _ in range(max_iter):
        port_vol = np.sqrt(w @ cov @ w)
        if port_vol == 0:
            break
        # 边际风险贡献
        mrc = cov @ w / port_vol
        # 风险贡献
        rc = w * mrc
        # 目标：每个资产的风险贡献相等
        target_rc = port_vol / n
        # 调整权重
        w_new = w * (target_rc / (rc + 1e-10))
        w_new = np.maximum(w_new, 0.01)
        w_new = w_new / w_new.sum()

        if np.max(np.abs(w_new - w)) < 1e-8:
            break
        w = w_new

    return w


# ══════════════════════════════════════════════
# 5. Black-Litterman 模型
# ══════════════════════════════════════════════

def black_litterman_returns(
    mu_market: np.ndarray,
    cov: np.ndarray,
    views: Dict[int, float],
    view_confidence: Dict[int, float] = None,
    tau: float = 0.05,
) -> np.ndarray:
    """
    Black-Litterman 模型：结合市场均衡收益和主观观点
    views: {asset_index: expected_return}  主观观点（如来自因子模型的D分数）
    view_confidence: {asset_index: confidence}  观点置信度（0~1）
    tau: 不确定性缩放参数
    """
    n = len(mu_market)
    if n == 0 or not views:
        return mu_market

    # 构建观点矩阵 P 和观点收益向量 Q
    k = len(views)
    P = np.zeros((k, n))
    Q = np.zeros(k)
    omega_diag = np.zeros(k)

    if view_confidence is None:
        view_confidence = {idx: 0.5 for idx in views}

    for i, (idx, view_ret) in enumerate(views.items()):
        P[i, idx] = 1.0
        Q[i] = view_ret
        conf = view_confidence.get(idx, 0.5)
        # 置信度越高 omega 越小（不确定性越低）
        omega_diag[i] = (1.0 / (conf + 0.01)) * (P[i] @ (tau * cov) @ P[i].T)

    Omega = np.diag(omega_diag)

    # BL公式：mu_BL = [(τΣ)⁻¹ + P'Ω⁻¹P]⁻¹ [(τΣ)⁻¹π + P'Ω⁻¹Q]
    tau_cov_inv = np.linalg.inv(tau * cov + np.eye(n) * 1e-8)
    omega_inv = np.linalg.inv(Omega + np.eye(k) * 1e-8)

    A = tau_cov_inv + P.T @ omega_inv @ P
    b = tau_cov_inv @ mu_market + P.T @ omega_inv @ Q

    mu_bl = np.linalg.solve(A + np.eye(n) * 1e-8, b)
    return mu_bl


# ══════════════════════════════════════════════
# 6. 综合优化 + 再平衡建议
# ══════════════════════════════════════════════

def full_portfolio_optimization(
    fund_histories: Dict[str, "pd.DataFrame"],
    fund_configs: List[Dict],
    factor_scores: Dict[str, float] = None,
    total_capital: float = 300000,
    risk_free_rate: float = 0.02,
) -> Dict:
    """
    一站式组合优化
    fund_histories: {code: DataFrame}
    fund_configs: FUNDS配置列表
    factor_scores: {code: D分数} 来自三层因子模型
    total_capital: 总资金
    返回完整的优化报告
    """
    mu, cov, codes = estimate_returns_and_cov(fund_histories)

    if len(codes) < 2:
        return {
            "status": "insufficient_data",
            "message": "有效基金历史数据不足，至少需要2只基金有20天以上的历史",
            "strategies": {},
        }

    n = len(codes)
    code_to_idx = {c: i for i, c in enumerate(codes)}

    # ── 当前权重 ──
    current_values = {}
    for f in fund_configs:
        if f["code"] in code_to_idx:
            current_values[f["code"]] = f.get("current_value", 0)
    total_current = sum(current_values.values())
    current_weights = np.array([
        current_values.get(c, 0) / total_current if total_current > 0 else 1.0 / n
        for c in codes
    ])

    # ── 目标权重（config中的target_pct）──
    cfg_map = {f["code"]: f for f in fund_configs}
    target_weights = np.array([
        cfg_map[c].get("target_pct", 0.1) if c in cfg_map else 0.1
        for c in codes
    ])
    target_weights = target_weights / target_weights.sum()

    # ── 策略1：最大夏普比率 ──
    w_sharpe = max_sharpe_weights(mu, cov, risk_free_rate)
    port_ret_sharpe = w_sharpe @ mu
    port_vol_sharpe = np.sqrt(w_sharpe @ cov @ w_sharpe)
    sharpe_ratio = (port_ret_sharpe - risk_free_rate) / port_vol_sharpe if port_vol_sharpe > 0 else 0

    # ── 策略2：最小波动率 ──
    w_minvol = min_volatility_weights(cov)
    port_ret_minvol = w_minvol @ mu
    port_vol_minvol = np.sqrt(w_minvol @ cov @ w_minvol)

    # ── 策略3：风险平价 ──
    w_riskparity = risk_parity_weights(cov)
    port_ret_rp = w_riskparity @ mu
    port_vol_rp = np.sqrt(w_riskparity @ cov @ w_riskparity)

    # ── 策略4：Black-Litterman（结合因子模型）──
    w_bl = None
    if factor_scores:
        views = {}
        view_conf = {}
        for code, d_score in factor_scores.items():
            if code in code_to_idx:
                idx = code_to_idx[code]
                # D分数 [-2,+2] 转化为预期超额收益
                views[idx] = d_score * 0.05  # 1分≈年化5%超额
                view_conf[idx] = min(1.0, max(0.2, 0.5 + d_score * 0.15))

        if views:
            mu_bl = black_litterman_returns(mu, cov, views, view_conf)
            w_bl = max_sharpe_weights(mu_bl, cov, risk_free_rate)
            port_ret_bl = w_bl @ mu_bl
            port_vol_bl = np.sqrt(w_bl @ cov @ w_bl)

    # ── 有效前沿 ──
    frontier = compute_efficient_frontier(mu, cov, n_points=20)

    # ── 推荐策略（综合评分）──
    if w_bl is not None:
        recommended_weights = w_bl
        recommended_strategy = "Black-Litterman"
        rec_reason = "结合因子模型观点的最优组合"
    else:
        recommended_weights = w_sharpe
        recommended_strategy = "最大夏普比率"
        rec_reason = "在给定风险下追求最高收益"

    # ── 再平衡建议 ──
    rebalance = []
    for i, code in enumerate(codes):
        curr_w = current_weights[i]
        opt_w = recommended_weights[i]
        diff = opt_w - curr_w
        diff_amount = diff * total_capital
        fund_name = cfg_map[code]["name"] if code in cfg_map else code

        action = "持有"
        if diff > 0.02:
            action = "加仓"
        elif diff < -0.02:
            action = "减仓"

        rebalance.append({
            "code": code,
            "name": fund_name,
            "current_weight": round(curr_w * 100, 1),
            "optimal_weight": round(opt_w * 100, 1),
            "target_weight": round(target_weights[i] * 100, 1),
            "diff_pct": round(diff * 100, 1),
            "diff_amount": round(diff_amount, 0),
            "action": action,
        })

    rebalance.sort(key=lambda x: abs(x["diff_pct"]), reverse=True)

    # ── 组合统计 ──
    curr_ret = current_weights @ mu
    curr_vol = np.sqrt(current_weights @ cov @ current_weights)
    curr_sharpe = (curr_ret - risk_free_rate) / curr_vol if curr_vol > 0 else 0

    result = {
        "status": "ok",
        "fund_codes": codes,
        "n_funds": n,
        "strategies": {
            "max_sharpe": {
                "name": "最大夏普比率",
                "desc": "在给定风险下追求最高收益",
                "weights": {c: round(w_sharpe[i] * 100, 1) for i, c in enumerate(codes)},
                "annual_return": round(port_ret_sharpe * 100, 1),
                "annual_vol": round(port_vol_sharpe * 100, 1),
                "sharpe": round(sharpe_ratio, 2),
            },
            "min_volatility": {
                "name": "最小波动率",
                "desc": "最大程度降低组合波动风险",
                "weights": {c: round(w_minvol[i] * 100, 1) for i, c in enumerate(codes)},
                "annual_return": round(port_ret_minvol * 100, 1),
                "annual_vol": round(port_vol_minvol * 100, 1),
                "sharpe": round((port_ret_minvol - risk_free_rate) / port_vol_minvol, 2) if port_vol_minvol > 0 else 0,
            },
            "risk_parity": {
                "name": "风险平价",
                "desc": "每只基金对组合风险的贡献相等",
                "weights": {c: round(w_riskparity[i] * 100, 1) for i, c in enumerate(codes)},
                "annual_return": round(port_ret_rp * 100, 1),
                "annual_vol": round(port_vol_rp * 100, 1),
                "sharpe": round((port_ret_rp - risk_free_rate) / port_vol_rp, 2) if port_vol_rp > 0 else 0,
            },
        },
        "current_portfolio": {
            "weights": {c: round(current_weights[i] * 100, 1) for i, c in enumerate(codes)},
            "annual_return": round(curr_ret * 100, 1),
            "annual_vol": round(curr_vol * 100, 1),
            "sharpe": round(curr_sharpe, 2),
        },
        "recommended_strategy": recommended_strategy,
        "recommended_reason": rec_reason,
        "recommended_weights": {c: round(recommended_weights[i] * 100, 1) for i, c in enumerate(codes)},
        "rebalance": rebalance,
        "efficient_frontier": frontier,
    }

    # 添加BL策略
    if w_bl is not None:
        result["strategies"]["black_litterman"] = {
            "name": "Black-Litterman",
            "desc": "融合因子模型观点的贝叶斯优化",
            "weights": {c: round(w_bl[i] * 100, 1) for i, c in enumerate(codes)},
            "annual_return": round(port_ret_bl * 100, 1),
            "annual_vol": round(port_vol_bl * 100, 1),
            "sharpe": round((port_ret_bl - risk_free_rate) / port_vol_bl, 2) if port_vol_bl > 0 else 0,
        }

    return result
