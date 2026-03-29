"""
定投回测页面 — DCA Backtest Tab
展示多种定投策略的回测对比、收益曲线、参数调整
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List

from ui.design_tokens import (
    BG_BASE, BG_CARD, BG_ELEVATED, BRAND, BRAND_DIM,
    UP, UP_DIM, DOWN, DOWN_DIM, WARN, WARN_DIM,
    INFO, INFO_DIM, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    BORDER, RADIUS_SM, RADIUS_MD, RADIUS_LG,
    FONT_MONO, SHADOW_SM, SHADOW_MD,
    score_color,
)


def render_dca_backtest_tab(
    funds_config: List[Dict],
    load_fund_history_fn,
):
    """渲染定投回测Tab"""
    st.markdown(
        f'<div style="font-size:1.8em; font-weight:700; margin-bottom:8px;">📈 定投回测实验室</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="label-dim">对比多种定投策略 · 回测历史收益 · 找到最适合你的定投方式</div>',
        unsafe_allow_html=True,
    )

    # ── 参数设置 ──
    col_fund, col_amount, col_day = st.columns([2, 1, 1])
    with col_fund:
        fund_names = {f["code"]: f["name"] for f in funds_config}
        selected_code = st.selectbox(
            "选择基金",
            options=[f["code"] for f in funds_config],
            format_func=lambda c: f'{next(f["sector_icon"] for f in funds_config if f["code"]==c)} {fund_names[c]} ({c})',
            key="dca_fund_selector",
        )
    with col_amount:
        monthly_amount = st.number_input("每月定投金额（元）", min_value=100, max_value=50000, value=1000, step=100, key="dca_amount")
    with col_day:
        day_of_month = st.number_input("每月扣款日", min_value=1, max_value=28, value=15, step=1, key="dca_day")

    selected_fund = next(f for f in funds_config if f["code"] == selected_code)

    # ── 加载历史数据 ──
    with st.spinner("正在加载基金历史数据..."):
        df = load_fund_history_fn(selected_code)

    if df.empty or len(df) < 30:
        st.warning("历史数据不足（至少需要30天），暂无法进行回测")
        return

    st.caption(f"回测区间：{df['date'].min()} ~ {df['date'].max()} | 共 {len(df)} 个交易日")

    # ── 运行所有策略 ──
    with st.spinner("正在回测多种定投策略..."):
        from engine.dca_backtest import run_all_strategies
        results = run_all_strategies(df, monthly_amount, fund_code=selected_code, fund_name=selected_fund["name"])

    if not results:
        st.error("回测失败，请检查数据")
        return

    # ═════════════════════════════════════════
    # SECTION 1: 策略对比总览
    # ═════════════════════════════════════════
    st.markdown("#### 📊 策略对比总览")

    # 找到最优策略
    best = max(results, key=lambda r: r.total_return_pct)

    cols = st.columns(len(results))
    for i, r in enumerate(results):
        is_best = r.strategy_name == best.strategy_name
        border_color = UP if is_best else "rgba(255,255,255,0.06)"
        badge = f'<span style="background:{UP}; color:#000; padding:2px 8px; border-radius:4px; font-size:0.7em; font-weight:700;">推荐</span>' if is_best else ""

        ret_color = UP if r.total_return_pct >= 0 else DOWN
        ann_color = UP if r.annualized_return >= 0 else DOWN

        cols[i].markdown(
            f'<div class="glass-card" style="border-color:{border_color}; padding:16px;">'
            f'<div style="font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;">{r.strategy_name} {badge}</div>'
            f'<div style="display:flex; flex-direction:column; gap:8px;">'
            f'<div><span class="label-dim">总收益率</span><div class="num-lg" style="color:{ret_color};">{r.total_return_pct:+.1f}%</div></div>'
            f'<div><span class="label-dim">年化收益</span><div style="color:{ann_color}; font-weight:600;">{r.annualized_return:+.1f}%</div></div>'
            f'<div><span class="label-dim">累计投入</span><div style="color:{TEXT_SECONDARY};">¥{r.total_invested:,.0f}</div></div>'
            f'<div><span class="label-dim">期末市值</span><div style="color:{TEXT_SECONDARY};">¥{r.final_value:,.0f}</div></div>'
            f'<div><span class="label-dim">最大回撤</span><div style="color:{WARN};">{r.max_drawdown:.1f}%</div></div>'
            f'<div><span class="label-dim">投资次数</span><div style="color:{TEXT_SECONDARY};">{r.invest_count}次</div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 2: 收益对比表
    # ═════════════════════════════════════════
    st.markdown("#### 📋 详细对比")

    compare_data = []
    for r in results:
        compare_data.append({
            "策略": r.strategy_name,
            "总收益率%": f"{r.total_return_pct:+.1f}%",
            "年化收益%": f"{r.annualized_return:+.1f}%",
            "累计投入": f"¥{r.total_invested:,.0f}",
            "期末市值": f"¥{r.final_value:,.0f}",
            "总收益额": f"¥{r.total_return:,.0f}",
            "最大回撤%": f"{r.max_drawdown:.1f}%",
            "平均成本": f"¥{r.avg_cost_nav:.4f}",
            "投资次数": r.invest_count,
        })
    st.dataframe(pd.DataFrame(compare_data), use_container_width=True, hide_index=True)

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 3: 累计收益曲线
    # ═════════════════════════════════════════
    st.markdown("#### 📈 累计市值曲线")

    chart_data = {}
    for r in results:
        if not r.history:
            continue
        cum_shares = 0
        dates = []
        values = []
        for h in r.history:
            cum_shares += h["shares_bought"]
            dates.append(h["date"])
            values.append(cum_shares * h["nav"])
        if dates:
            chart_data[r.strategy_name] = pd.Series(values, index=pd.to_datetime(dates))

    if chart_data:
        chart_df = pd.DataFrame(chart_data)
        st.line_chart(chart_df, use_container_width=True)

    # 累计投入曲线
    st.markdown("#### 💰 累计投入对比")
    invest_data = {}
    for r in results:
        if not r.history:
            continue
        cum_invest = 0
        dates = []
        values = []
        for h in r.history:
            cum_invest += h["invest_amount"]
            dates.append(h["date"])
            values.append(cum_invest)
        if dates:
            invest_data[r.strategy_name] = pd.Series(values, index=pd.to_datetime(dates))

    if invest_data:
        invest_df = pd.DataFrame(invest_data)
        st.line_chart(invest_df, use_container_width=True)

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 4: 策略解读
    # ═════════════════════════════════════════
    st.markdown("#### 💡 策略解读")

    explanations = {
        "普通定投": "每月固定日期、固定金额买入，最简单的投资方式。优势在于纪律性强、操作简单，通过时间分散降低平均成本。",
        "智慧定投": "根据净值与均线的偏离度动态调整金额：净值低于均线时多投（最多2倍），高于均线时少投（最少0.5倍）。核心思想是'越跌越买'。",
        "止盈定投": "在普通定投基础上增加止盈机制：当累计收益达到设定阈值（如20%），自动赎回全部持仓，锁定收益后重新开始定投。",
        "均线偏离": "更激进的均线策略：净值远低于长期均线时加倍投入，远高于均线时暂停定投。适合有一定市场判断能力的投资者。",
    }

    for r in results:
        short_name = r.strategy_name.split("(")[0]
        explanation = explanations.get(short_name, "")
        is_best = r.strategy_name == best.strategy_name
        icon = "🏆" if is_best else "📌"
        st.markdown(
            f'<div class="signal-bar" style="border-left-color:{UP if is_best else INFO};">'
            f'<div><b style="color:{TEXT_PRIMARY};">{icon} {r.strategy_name}</b>'
            f'<span style="color:{UP if r.total_return_pct >= 0 else DOWN}; float:right; font-weight:700;">{r.total_return_pct:+.1f}%</span></div>'
            f'<div style="color:{TEXT_MUTED}; font-size:0.85em; margin-top:4px;">{explanation}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 5: 本期具体执行信号
    # ═════════════════════════════════════════
    _render_execution_signals(df, monthly_amount, selected_fund, results, best)


def _render_execution_signals(df, monthly_amount, selected_fund, results, best):
    """基于当前最新数据，为每种策略生成本期具体执行信号"""

    st.markdown("#### 🎯 本期执行信号")
    st.caption("基于最新净值与技术指标，给出各策略本期的具体操作建议")

    # 准备最新数据
    df_calc = df.copy()
    df_calc["date"] = pd.to_datetime(df_calc["date"])
    df_calc = df_calc.sort_values("date").reset_index(drop=True)
    df_calc["nav"] = pd.to_numeric(df_calc["nav"], errors="coerce")

    if df_calc.empty:
        st.warning("无法获取最新净值数据")
        return

    latest = df_calc.iloc[-1]
    current_nav = float(latest["nav"])
    current_date = str(latest["date"].date()) if hasattr(latest["date"], "date") else str(latest["date"])

    # 计算各均线
    ma60 = df_calc["nav"].rolling(60, min_periods=10).mean().iloc[-1]
    ma120 = df_calc["nav"].rolling(120, min_periods=20).mean().iloc[-1]

    ma60 = float(ma60) if not pd.isna(ma60) else current_nav
    ma120 = float(ma120) if not pd.isna(ma120) else current_nav

    dev_60 = (current_nav - ma60) / ma60 if ma60 > 0 else 0
    dev_120 = (current_nav - ma120) / ma120 if ma120 > 0 else 0

    # 最近持仓盈亏（用回测最后一期数据近似）
    last_history_items = {}
    for r in results:
        if r.history:
            last_history_items[r.strategy_name] = r

    fund_icon = selected_fund.get("sector_icon", "📊")
    fund_name = selected_fund.get("name", "")

    # ── 指标面板 ──
    st.markdown(
        f'<div class="glass-card" style="border-left:3px solid {INFO}; padding:16px;">'
        f'<div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:16px;">'
        f'<div><div class="label-dim">基金</div><div style="color:{TEXT_PRIMARY}; font-weight:700; font-size:1.1em;">{fund_icon} {fund_name}</div></div>'
        f'<div><div class="label-dim">最新净值</div><div style="color:{INFO}; font-weight:700; font-size:1.1em;">{current_nav:.4f}</div></div>'
        f'<div><div class="label-dim">MA60</div><div style="color:{WARN}; font-weight:600;">{ma60:.4f} <span style="font-size:0.8em;">({dev_60:+.1%})</span></div></div>'
        f'<div><div class="label-dim">MA120</div><div style="color:{DOWN}; font-weight:600;">{ma120:.4f} <span style="font-size:0.8em;">({dev_120:+.1%})</span></div></div>'
        f'<div><div class="label-dim">数据日期</div><div style="color:{TEXT_MUTED};">{current_date}</div></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("")

    # ── 各策略信号 ──
    signals = _compute_all_signals(current_nav, ma60, ma120, dev_60, dev_120, monthly_amount, last_history_items)

    for sig in signals:
        is_best_strategy = sig["strategy"] == best.strategy_name.split("(")[0]
        border = UP if is_best_strategy else sig["color"]
        best_tag = f' <span style="background:{UP}; color:#000; padding:1px 6px; border-radius:4px; font-size:0.65em; font-weight:700; vertical-align:middle;">推荐策略</span>' if is_best_strategy else ""

        action_bg = {"买入": UP_DIM, "加倍买入": f"rgba(76,175,80,0.2)", "减半买入": WARN_DIM, "暂停": DOWN_DIM, "止盈赎回": f"rgba(245,158,11,0.2)"}
        bg = action_bg.get(sig["action"], "rgba(255,255,255,0.05)")

        st.markdown(
            f'<div class="glass-card" style="border-left:4px solid {border}; padding:16px; margin-bottom:8px; background:{bg};">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">'
            f'<div style="font-weight:700; color:{TEXT_PRIMARY}; font-size:1.05em;">{sig["icon"]} {sig["strategy"]}{best_tag}</div>'
            f'<div style="display:flex; gap:12px; align-items:center;">'
            f'<span style="background:{sig["color"]}; color:#000; padding:4px 12px; border-radius:6px; font-weight:700; font-size:0.9em;">{sig["action"]}</span>'
            f'<span style="color:{sig["color"]}; font-weight:700; font-size:1.2em;">¥{sig["amount"]:,.0f}</span>'
            f'</div></div>'
            f'<div style="color:{TEXT_SECONDARY}; font-size:0.85em; line-height:1.6;">{sig["reason"]}</div>'
            f'<div style="margin-top:8px; padding-top:8px; border-top:1px solid {BORDER}; color:{TEXT_MUTED}; font-size:0.78em;">'
            f'📋 <b>执行方式：</b>{sig["how"]}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    # ── 综合建议 ──
    st.markdown("")
    buy_signals = [s for s in signals if s["amount"] > 0]
    if buy_signals:
        avg_amount = sum(s["amount"] for s in buy_signals) / len(buy_signals)
        best_sig = next((s for s in signals if s["strategy"] == best.strategy_name.split("(")[0]), signals[0])
        st.markdown(
            f'<div class="glass-card" style="border:1px solid {UP_DIM}; padding:16px;">'
            f'<div style="font-weight:700; color:{UP}; font-size:1.05em; margin-bottom:8px;">📌 综合执行建议</div>'
            f'<div style="color:{TEXT_SECONDARY}; line-height:1.8;">'
            f'基于回测表现最优的 <b style="color:{UP};">{best.strategy_name}</b> 策略，'
            f'本期建议操作：<b style="color:{best_sig["color"]};">{best_sig["action"]}</b>，'
            f'金额 <b style="color:{INFO};">¥{best_sig["amount"]:,.0f}</b>。'
            f'<br>四策略平均建议投入 ¥{avg_amount:,.0f}，'
            f'{"所有策略一致看多，信号较强" if all(s["amount"] > 0 for s in signals) else "部分策略建议暂停或减投，信号偏弱"}。'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="glass-card" style="border:1px solid {DOWN_DIM}; padding:16px;">'
            f'<div style="font-weight:700; color:{DOWN}; font-size:1.05em; margin-bottom:8px;">⏸️ 综合执行建议</div>'
            f'<div style="color:{TEXT_SECONDARY};">所有策略均建议暂停本期定投，当前净值偏离均线过高，建议等待回调后再执行。</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _compute_all_signals(current_nav, ma60, ma120, dev_60, dev_120, base_amount, last_history_items):
    """根据最新数据计算所有策略的执行信号"""
    signals = []

    # ── 1. 普通定投 ──
    signals.append({
        "strategy": "普通定投",
        "icon": "📅",
        "action": "买入",
        "amount": base_amount,
        "color": UP,
        "reason": f"固定定投不择时，本期按计划投入 ¥{base_amount:,.0f}。当前净值 {current_nav:.4f}，可买入约 {base_amount/current_nav:.2f} 份。",
        "how": f"在定投日（每月扣款日）通过基金APP/银行渠道提交 ¥{base_amount:,.0f} 买入申请，T+1确认份额。",
    })

    # ── 2. 智慧定投 (MA60) ──
    if dev_60 < -0.20:
        multiplier = 2.0
        action = "加倍买入"
        color = UP
        reason_detail = f"净值 {current_nav:.4f} 低于MA60 ({ma60:.4f}) 超过20%（偏离 {dev_60:+.1%}），触发最高档加倍信号"
    elif dev_60 < -0.10:
        multiplier = 1.5
        action = "加倍买入"
        color = UP
        reason_detail = f"净值低于MA60 10%-20%（偏离 {dev_60:+.1%}），触发1.5倍加投信号"
    elif dev_60 < 0:
        multiplier = 1.0 + abs(dev_60) * 5
        action = "买入"
        color = UP
        reason_detail = f"净值略低于MA60（偏离 {dev_60:+.1%}），小幅加投 {multiplier:.1f}倍"
    elif dev_60 < 0.10:
        multiplier = 1.0 - dev_60 * 3
        action = "减半买入" if multiplier < 0.8 else "买入"
        color = WARN if multiplier < 0.8 else UP
        reason_detail = f"净值高于MA60（偏离 {dev_60:+.1%}），适当缩减投入至 {multiplier:.1f}倍"
    elif dev_60 < 0.20:
        multiplier = 0.7
        action = "减半买入"
        color = WARN
        reason_detail = f"净值高于MA60 10%-20%（偏离 {dev_60:+.1%}），缩减至0.7倍"
    else:
        multiplier = 0.5
        action = "减半买入"
        color = WARN
        reason_detail = f"净值高于MA60 超过20%（偏离 {dev_60:+.1%}），仅投入基础金额的一半"

    multiplier = max(0.3, min(2.5, multiplier))
    smart_amount = round(base_amount * multiplier, 0)
    signals.append({
        "strategy": "智慧定投",
        "icon": "🧠",
        "action": action,
        "amount": smart_amount,
        "color": color,
        "reason": f"{reason_detail}。本期建议投入 ¥{smart_amount:,.0f}（基础 ¥{base_amount:,.0f} × {multiplier:.1f}倍），可买约 {smart_amount/current_nav:.2f} 份。",
        "how": f"在定投日手动调整本期金额为 ¥{smart_amount:,.0f}，部分平台支持设置智能定投自动调节。",
    })

    # ── 3. 止盈定投 ──
    tp_result = last_history_items.get("止盈定投(20%)")
    if tp_result and tp_result.total_invested > 0 and tp_result.total_shares > 0:
        # 用回测的累计数据估算当前持仓收益
        unrealized_pct = tp_result.total_return_pct
        if unrealized_pct >= 20:
            tp_action = "止盈赎回"
            tp_color = WARN
            tp_amount = 0
            tp_reason = f"累计收益率已达 {unrealized_pct:+.1f}%（≥20%止盈线），应全部赎回锁定收益，下期重新开始定投。"
            tp_how = "通过基金APP提交全部赎回申请，收益落袋为安。下个扣款日重新开始新一轮定投。"
        else:
            tp_action = "买入"
            tp_color = UP
            tp_amount = base_amount
            tp_reason = f"当前累计收益率 {unrealized_pct:+.1f}%，未触及20%止盈线。正常定投 ¥{base_amount:,.0f}，继续积累份额。"
            tp_how = f"按正常定投计划投入 ¥{base_amount:,.0f}。盈利达20%时系统会提示止盈。"
    else:
        tp_action = "买入"
        tp_color = UP
        tp_amount = base_amount
        tp_reason = f"新一轮定投周期，按标准金额 ¥{base_amount:,.0f} 买入建仓。"
        tp_how = f"提交 ¥{base_amount:,.0f} 买入申请，开始新一轮止盈定投周期。"

    signals.append({
        "strategy": "止盈定投",
        "icon": "🎯",
        "action": tp_action,
        "amount": tp_amount,
        "color": tp_color,
        "reason": tp_reason,
        "how": tp_how,
    })

    # ── 4. 均线偏离 (MA120) ──
    if dev_120 < -0.10:
        ma_action = "加倍买入"
        ma_multiplier = 2.0
        ma_color = UP
        ma_reason_detail = f"净值 {current_nav:.4f} 远低于MA120 ({ma120:.4f})，偏离 {dev_120:+.1%} 超过-10%，触发双倍加仓信号"
    elif dev_120 < 0:
        ma_action = "买入"
        ma_multiplier = 1.0
        ma_color = UP
        ma_reason_detail = f"净值低于MA120（偏离 {dev_120:+.1%}），属于均值回归区间，正常投入"
    elif dev_120 < 0.15:
        ma_action = "减半买入"
        ma_multiplier = 0.5
        ma_color = WARN
        ma_reason_detail = f"净值高于MA120 0-15%（偏离 {dev_120:+.1%}），高于长期均线，减半投入观望"
    else:
        ma_action = "暂停"
        ma_multiplier = 0
        ma_color = DOWN
        ma_reason_detail = f"净值高于MA120 超过15%（偏离 {dev_120:+.1%}），严重偏离长期均值，暂停本期定投等待回调"

    ma_amount = round(base_amount * ma_multiplier, 0)
    if ma_amount > 0:
        ma_how = f"本期投入 ¥{ma_amount:,.0f}（基础 ¥{base_amount:,.0f} × {ma_multiplier:.1f}倍），可买约 {ma_amount/current_nav:.2f} 份。"
    else:
        ma_how = "本期不操作，持续跟踪净值与MA120关系。当净值回落至MA120附近（偏离<15%）后恢复定投。"

    signals.append({
        "strategy": "均线偏离",
        "icon": "📐",
        "action": ma_action,
        "amount": ma_amount,
        "color": ma_color,
        "reason": f"{ma_reason_detail}。{'建议投入 ¥' + f'{ma_amount:,.0f}' if ma_amount > 0 else '建议暂停投入，保留现金等待更好买点'}。",
        "how": ma_how,
    })

    return signals
