"""
Tab3 操作中心 — 信号排名 + 组合优化 + AI策略 + 今日操作清单
"""

import streamlit as st
from typing import List, Dict, Optional, Callable
from datetime import datetime
import pandas as pd

from ui.design_tokens import (
    BG_BASE, BG_CARD, BG_ELEVATED, BRAND, BRAND_DIM,
    UP, UP_DIM, DOWN, DOWN_DIM, WARN, WARN_DIM,
    INFO, INFO_DIM, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    BORDER, RADIUS_SM, RADIUS_MD, RADIUS_LG,
    SCORE_MACRO, SCORE_SECTOR, SCORE_TECH, SCORE_FUND,
    FONT_MONO, SHADOW_SM, SHADOW_MD,
    score_color, verdict_style, dim_color,
)


def _h(html: str) -> str:
    """Remove common indentation from HTML strings."""
    return "\n".join(line.strip() for line in html.split("\n") if line.strip())


def render_action_center_tab(
    reports: List,
    funds_config: List[Dict],
    market_data: Dict,
    portfolio: Dict,
    load_fund_history_fn: Optional[Callable] = None,
) -> None:
    """Render the action center tab with signals, optimization, strategy, and checklist."""
    st.caption(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if not reports:
        st.info("暂无基金分析数据")
        return

    # Section A: 信号排行榜
    st.markdown("### 🎯 信号排行榜")
    _render_signal_ranking(reports)
    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

    # Section B: 组合优化
    st.markdown("### ⚙️ 组合优化")
    _render_portfolio_optimization(reports, funds_config, portfolio, load_fund_history_fn)
    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

    # Section C: AI策略总结
    st.markdown("### 📋 AI 策略总结")
    _render_strategy_summary(reports)
    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

    # Section D: 今日操作清单
    st.markdown("### ✅ 今日操作清单")
    _render_action_checklist(reports)


def _render_signal_ranking(reports: List) -> None:
    """Render Section A: Signal ranking bars sorted by d_score."""
    sorted_reports = sorted(reports, key=lambda r: r.d_score, reverse=True)

    for report in sorted_reports:
        # Determine border color based on recommendation
        if report.recommendation in ("BUY", "BUY_SMALL"):
            border_color = UP
            bg_color = UP_DIM
        elif report.recommendation == "VETO":
            border_color = DOWN
            bg_color = DOWN_DIM
        else:
            border_color = TEXT_DIM
            bg_color = "transparent"

        # D-score color coding
        d_score = report.d_score
        if d_score >= 0.4:
            d_color = UP
        elif d_score >= -0.2:
            d_color = WARN
        else:
            d_color = DOWN

        # Calculate bar percentage (0-100%)
        bar_pct = min(100, max(0, (d_score + 0.5) * 100))

        # Format suggested amount
        amount_str = f"¥{report.suggested_amount:,.0f}" if report.suggested_amount > 0 else "—"
        trigger_str = (report.trigger_event or "—")[:50]

        html = _h(f"""
        <div class="signal-bar" style="
            border-left: 4px solid {border_color};
            background: {bg_color};
            padding: 14px 16px;
            margin-bottom: 8px;
            border-radius: 8px;
        ">
            <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
                <div style="min-width: 130px;">
                    <span style="font-size: 1.1em;">{report.sector_icon}</span>
                    <span style="font-weight: 700; color: {TEXT_PRIMARY};">{report.fund_short}</span>
                </div>
                <div style="min-width: 80px;">
                    <div style="font-family: {FONT_MONO}; font-weight: 700; color: {d_color}; font-size: 1.1em;">
                        {d_score:+.2f}
                    </div>
                    <div style="width: 60px; height: 3px; background: {BORDER}; border-radius: 2px;">
                        <div style="height: 100%; width: {bar_pct:.0f}%; background: {d_color};"></div>
                    </div>
                </div>
                <div style="min-width: 80px;">
                    <span style="font-size: 1.1em;">{report.rec_emoji}</span>
                    <span style="color: {TEXT_SECONDARY}; font-size: 0.9em;">{report.rec_label}</span>
                </div>
                <div style="min-width: 80px; font-family: {FONT_MONO}; color: {INFO}; font-weight: 600;">
                    {amount_str}
                </div>
                <div style="min-width: 70px; color: {WARN}; font-size: 0.85em;">
                    {report.confidence_stars}
                </div>
                <div style="flex: 1; color: {TEXT_MUTED}; font-size: 0.8em;">{trigger_str}</div>
            </div>
        </div>
        """)
        st.markdown(html, unsafe_allow_html=True)


def _render_portfolio_optimization(
    reports: List,
    funds_config: List[Dict],
    portfolio: Dict,
    load_fund_history_fn: Optional[Callable],
) -> None:
    """Render Section B: Portfolio optimization with strategy comparison and rebalance suggestions."""
    try:
        from engine.portfolio_optimizer import full_portfolio_optimization
    except ImportError:
        st.info("📊 组合优化模块加载中... 如需完整功能请确保 portfolio_optimizer 引擎可用。")
        return

    # Build current weights and fund histories
    total_value = portfolio.get("total_value", 0) or sum(f.get("current_value", 0) for f in funds_config)
    if total_value <= 0:
        st.warning("组合总值无效，无法运行优化。")
        return

    fund_histories = {}
    for f in funds_config:
        code = f.get("code", "")
        if not code or not load_fund_history_fn:
            continue
        try:
            hist = load_fund_history_fn(code)
            if hist is not None and not hist.empty:
                fund_histories[code] = hist
        except Exception:
            pass

    if len(fund_histories) < 2:
        st.info("历史数据不足（至少需要2只基金），暂无法运行组合优化。")
        return

    try:
        factor_scores = {r.fund_code: r.d_score for r in reports}
        result = full_portfolio_optimization(
            fund_histories=fund_histories,
            fund_configs=funds_config,
            factor_scores=factor_scores,
            total_capital=total_value,
        )
    except Exception as e:
        st.warning(f"优化计算失败: {str(e)[:150]}")
        return

    if not result:
        st.warning("组合优化无结果返回")
        return

    # Display strategy comparison table
    strategies = result.get("strategies", {})
    if strategies:
        st.markdown("**优化策略对比：**")
        rows = []
        for key, info in strategies.items():
            # v2.0 fix: 引擎返回 annual_return (已是百分比) 和 annual_vol
            ret_val = info.get("annual_return", info.get("expected_return", 0))
            vol_val = info.get("annual_vol", info.get("volatility", 0))
            # 兼容：如果值 < 1 说明是小数格式，需要 *100
            if isinstance(ret_val, (int, float)) and abs(ret_val) < 1:
                ret_val = ret_val * 100
            if isinstance(vol_val, (int, float)) and abs(vol_val) < 1:
                vol_val = vol_val * 100
            rows.append({
                "策略": info.get("name", key),
                "预期年化收益": f"{ret_val:.1f}%",
                "年化波动率": f"{vol_val:.1f}%",
                "夏普比": f"{info.get('sharpe', 0):.2f}",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # 显示推荐策略
        rec_strategy = result.get("recommended_strategy", "")
        rec_reason = result.get("recommended_reason", "")
        if rec_strategy:
            st.info(f"推荐策略：**{rec_strategy}** — {rec_reason}")

    # Display rebalance suggestions
    rebalance = result.get("rebalance", [])
    if rebalance:
        st.markdown("**调仓建议：**")
        for item in rebalance:
            action = item.get("action", "")
            # v2.0 fix: 字段名对齐 — 引擎返回 "diff_amount" 和 "name"
            amount = abs(item.get("diff_amount", item.get("amount", 0)))
            name = item.get("name", item.get("fund_name", item.get("fund_code", "未知")))
            # v2.0 fix: 引擎返回中文 action（加仓/减仓/持有）
            is_buy = action in ("buy", "加仓")
            is_hold = action in ("hold", "持有")
            if is_hold or amount < 100:
                emoji = "➡️"
                action_text = "维持"
            elif is_buy:
                emoji = "📈"
                action_text = "增加"
            else:
                emoji = "📉"
                action_text = "减少"
            st.markdown(f"{emoji} **{name}** {action_text} ¥{amount:,.0f}")


def _render_strategy_summary(reports: List) -> None:
    """Render Section C: AI strategy summary with LLM fallback."""
    strategy_text = None

    # Try LLM commentary
    try:
        from engine.llm_commentary import generate_strategy_advice

        regime_name = reports[0].regime_name if reports else "放缓期"
        result = generate_strategy_advice(
            regime_name=regime_name,
            fund_results=[{
                "fund_short": r.fund_short,
                "d_score": r.d_score,
                "recommendation": r.recommendation,
                "rec_label": r.rec_label,
            } for r in reports],
        )
        strategy_text = result.get("advice", None) if isinstance(result, dict) else str(result)
    except Exception:
        pass

    # Fallback: Generate summary from report statistics
    if not strategy_text:
        buy_count = sum(1 for r in reports if r.recommendation in ("BUY", "BUY_SMALL"))
        wait_count = sum(1 for r in reports if r.recommendation == "WAIT")
        veto_count = sum(1 for r in reports if r.recommendation == "VETO")
        regime = reports[0].regime_name if reports else "未知"
        avg_d = sum(r.d_score for r in reports) / len(reports) if reports else 0

        parts = [
            f"当前市场处于「{regime}」状态，组合平均D-score为{avg_d:+.3f}。",
            f"共{len(reports)}只基金监控中：{buy_count}只建议买入、{wait_count}只建议观望、{veto_count}只建议规避。",
        ]

        if buy_count > 0:
            top_names = "、".join(r.fund_short for r in sorted(
                [r for r in reports if r.recommendation in ("BUY", "BUY_SMALL")],
                key=lambda r: r.d_score,
                reverse=True
            )[:3])
            parts.append(f"优先关注{top_names}。")

        if veto_count > 0:
            parts.append("注意规避标记为否决的基金，等待信号改善。")

        strategy_text = "".join(parts)

    html = _h(f"""
    <div class="glass-card" style="
        border-color: {INFO_DIM};
        background: {INFO_DIM};
        padding: 14px 16px;
        border-radius: 8px;
        border: 1px solid {INFO_DIM};
    ">
        <div style="color: {TEXT_SECONDARY}; line-height: 1.7; font-size: 0.92em;">
            {strategy_text}
        </div>
    </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def _render_action_checklist(reports: List) -> None:
    """Render Section D: Today's action checklist for BUY recommendations."""
    actionable = [r for r in reports if r.recommendation in ("BUY", "BUY_SMALL")]

    if not actionable:
        st.info("当前无建议操作，请继续观察市场信号变化。")
        return

    # Display each actionable item
    total_amount = 0
    for r in actionable:
        amount = r.suggested_amount or 0
        total_amount += amount
        reason = (r.trigger_event or "综合评分")[:40]
        emoji = "🟢" if r.recommendation == "BUY" else "🟡"

        if amount > 0:
            st.markdown(f"{emoji} **{r.fund_short}** · ¥{amount:,.0f} · _{reason}_")
        else:
            st.markdown(f"{emoji} **{r.fund_short}** · 灵活额度 · _{reason}_")

    st.divider()

    # Display total investment recommendation
    if total_amount > 0:
        html = _h(f"""
        <div style="
            text-align: center;
            padding: 12px;
            background: {UP_DIM};
            border: 1px solid {UP_DIM};
            border-radius: 10px;
        ">
            <span class="label-dim">今日建议投入总额</span><br>
            <span style="
                color: {UP};
                font-family: {FONT_MONO};
                font-size: 1.5em;
                font-weight: 700;
            ">
                ¥{total_amount:,.0f}
            </span>
        </div>
        """)
        st.markdown(html, unsafe_allow_html=True)

    st.caption("⚠️ 以上建议仅供参考，请根据自身风险承受能力决策。")
