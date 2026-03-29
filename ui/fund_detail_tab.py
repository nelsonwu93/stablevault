"""
基金详情页面 — Fund Detail Tab
展示单只基金的完整信息：走势图、技术指标、基本信息、持仓、业绩
"""

import streamlit as st
import pandas as pd
import numpy as np
import datetime
from typing import Dict, List
from ui.design_tokens import (
    BRAND, BRAND_DIM, UP, DOWN, WARN, INFO,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM
)


def render_fund_detail_tab(
    funds_config: List[Dict],
    load_fund_history_fn,
    load_fund_realtime_fn,
    load_technical_fn,
):
    """渲染基金详情Tab"""
    st.markdown("### 📈 基金详情")
    st.caption("选择一只基金，查看实时行情、历史走势、技术指标和基本信息")

    # ── 基金选择器 ──
    fund_names = {f["code"]: f["name"] for f in funds_config}
    selected_code = st.selectbox(
        "选择基金",
        options=[f["code"] for f in funds_config],
        format_func=lambda c: f'{next(f["sector_icon"] for f in funds_config if f["code"]==c)} {fund_names[c]} ({c})',
        key="detail_fund_selector",
    )
    selected_fund = next(f for f in funds_config if f["code"] == selected_code)

    # ── 获取数据 ──
    with st.spinner("正在获取基金数据..."):
        realtime = load_fund_realtime_fn(selected_code)
        df_history = load_fund_history_fn(selected_code)
        tech = load_technical_fn(selected_code)

        # 基金详情（延迟导入避免循环依赖）
        try:
            from data.fund_detail import get_fund_full_detail
            detail = get_fund_full_detail(selected_code)
        except Exception:
            detail = {"basic": {}, "holdings": [], "performance": {}}

    # 数据源提示
    data_source = detail.get("basic", {}).get("source", "")
    if data_source == "static_cache":
        st.markdown(
            f'<div style="background:{WARN_DIM}; border:1px solid rgba(245,158,11,0.3); '
            f'border-radius:8px; padding:8px 16px; margin-bottom:12px; font-size:0.85em; color:{WARN};">'
            f'⚡ 当前使用离线缓存数据（API暂不可用），部分信息可能非最新</div>',
            unsafe_allow_html=True,
        )

    # ═════════════════════════════════════════
    # SECTION 1: 实时行情
    # ═════════════════════════════════════════
    basic = detail.get("basic", {})
    fund_type = basic.get("type", selected_fund.get("sector", ""))
    risk_level = basic.get("risk_level", "")

    nav = realtime.get("nav")
    est_nav = realtime.get("est_nav") or realtime.get("nav")
    est_change = realtime.get("est_change_pct")
    fund_full_name = basic.get("name") or selected_fund["name"]

    hero_html = f'<div class="hero-section"><div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;"><span style="font-size:1.8em;">{selected_fund["sector_icon"]}</span><div><div class="hero-label">{fund_type}</div><div class="hero-value" style="font-size:2.2em; margin:8px 0;">{fund_full_name}</div></div></div></div>'
    st.markdown(hero_html, unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("最新净值", f"¥{nav:.4f}" if nav else "—", help="昨日收盘净值")
    col2.metric("今日估算", f"¥{est_nav:.4f}" if est_nav else "—", delta=f"{est_change:+.2f}%" if est_change else None, help="盘中实时估算")
    col3.metric("基金类型", fund_type or "—")
    col4.metric("风险等级", risk_level or "—")
    ret_color = UP if selected_fund.get("total_return", 0) >= 0 else DOWN
    col5.metric("我的持仓", f"¥{selected_fund['current_value']:,.0f}", delta=f"{selected_fund['total_return']:+,.0f}" if selected_fund.get("total_return") else None)

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 2: 历史净值走势图
    # ═════════════════════════════════════════
    st.markdown("#### 📊 历史净值走势")

    if not df_history.empty and "nav" in df_history.columns:
        chart_df = df_history[["date", "nav"]].copy()
        chart_df["date"] = pd.to_datetime(chart_df["date"])
        chart_df = chart_df.set_index("date").sort_index()

        # 计算均线
        if len(chart_df) >= 20:
            chart_df["MA20"] = chart_df["nav"].rolling(20).mean()
        if len(chart_df) >= 60:
            chart_df["MA60"] = chart_df["nav"].rolling(60).mean()

        # 使用Streamlit原生图表（避免plotly依赖问题）
        st.line_chart(chart_df, use_container_width=True)

        # 技术指标摘要
        if tech:
            ti_cols = st.columns(6)
            ti_cols[0].metric("MA20", f"{tech['ma20']:.4f}" if tech.get("ma20") else "—")
            ti_cols[1].metric("MA60", f"{tech['ma60']:.4f}" if tech.get("ma60") else "—")
            ti_cols[2].metric("RSI(14)", f"{tech['rsi']:.1f}" if tech.get("rsi") else "—",
                              help="<35超卖（买入机会），>70超买（警惕回调）")
            macd_val = tech.get("macd")
            ti_cols[3].metric("MACD", f"{macd_val:.4f}" if macd_val is not None else "—")
            ti_cols[4].metric("趋势", _trend_cn(tech.get("trend", "unknown")))
            ti_cols[5].metric("MACD信号", _macd_cn(tech.get("macd_cross", "unknown")))

            # RSI Visualization
            rsi = tech.get("rsi")
            if rsi is not None:
                rsi_color = DOWN if rsi > 70 else UP if rsi < 35 else WARN
                rsi_word = "超买⚠️" if rsi > 70 else "超卖💡" if rsi < 35 else "正常"
                st.markdown(f'<div style="display:flex; align-items:center; gap:12px; margin:12px 0;"><span class="label-dim">RSI强弱：</span><div style="flex:1; height:14px; background:linear-gradient(90deg, {UP} 0%, {WARN} 50%, {DOWN} 100%); border-radius:8px; position:relative; box-shadow:0 0 12px {BRAND_DIM};"><div style="position:absolute; left:{rsi}%; top:-4px; width:6px; height:22px; background:white; border-radius:3px; box-shadow:0 0 8px rgba(255,255,255,0.8); transform:translateX(-50%);"></div></div><span style="color:{rsi_color}; font-weight:700; font-size:0.9em; min-width:60px;">{rsi:.1f}% {rsi_word}</span></div>', unsafe_allow_html=True)
    else:
        st.info("暂无历史净值数据")

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 3: 基本信息 + 持仓明细
    # ═════════════════════════════════════════
    col_info, col_holdings = st.columns([1, 1])

    with col_info:
        st.markdown("#### 📋 基本信息")
        info_items = [
            ("基金全称", basic.get("name", selected_fund["name"])),
            ("基金代码", selected_code),
            ("基金类型", fund_type),
            ("基金经理", basic.get("manager", "—")),
            ("基金公司", basic.get("company", "—")),
            ("成立日期", basic.get("inception_date", "—")),
            ("基金规模", f'{basic.get("scale", "—")}亿元' if basic.get("scale") else "—"),
            ("管理费率", f'{basic.get("fee_rate", "—")}%/年' if basic.get("fee_rate") else "—"),
            ("风险等级", risk_level or "—"),
            ("所属板块", f'{selected_fund["sector_icon"]} {selected_fund["sector"]}'),
            ("目标仓位", f'{selected_fund["target_pct"]*100:.0f}% (¥{300000*selected_fund["target_pct"]:,.0f})'),
            ("止盈线", f'{selected_fund["stop_profit"]*100:.0f}%'),
            ("止损线", f'{selected_fund["stop_loss"]*100:.0f}%'),
        ]
        for label, value in info_items:
            st.markdown(
                f'<div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.04);">'
                f'<span style="color:{TEXT_MUTED};">{label}</span>'
                f'<span style="color:{TEXT_PRIMARY}; font-weight:500;">{value}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_holdings:
        st.markdown("#### 🏢 前十大重仓股")
        holdings = detail.get("holdings", [])
        if holdings:
            for i, h in enumerate(holdings):
                pct = h.get("hold_pct", 0)
                bar_w = min(pct * 2.5, 100)
                st.markdown(f'<div class="signal-bar" style="border-left-color:{BRAND}; gap:12px;"><div style="width:30px; color:{TEXT_DIM}; text-align:center; font-weight:700;">{i+1}</div><div style="flex:1;"><div style="color:{TEXT_PRIMARY}; font-weight:600; font-size:0.9em;">{h.get("stock_name", "—")}</div><div style="width:100%; height:6px; background:{BRAND_DIM}; border-radius:4px; margin-top:4px;"><div style="width:{bar_w}%; height:100%; background:linear-gradient(90deg, {BRAND}, {UP}); border-radius:4px;"></div></div></div><div style="min-width:50px; text-align:right; color:{BRAND}; font-weight:700;">{pct:.2f}%</div></div>', unsafe_allow_html=True)
        else:
            st.caption("持仓数据暂不可用（部分基金不公开持仓或正在获取中）")

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 4: 历史业绩
    # ═════════════════════════════════════════
    st.markdown("#### 📈 历史业绩")
    performance = detail.get("performance", {})
    if performance:
        perf_cols = st.columns(min(len(performance), 8))
        for i, (period, val) in enumerate(performance.items()):
            if val is not None:
                clr = DOWN if val < 0 else UP
                perf_cols[i % len(perf_cols)].metric(period, f"{val:+.2f}%")
            else:
                perf_cols[i % len(perf_cols)].metric(period, "—")
    else:
        st.caption("业绩数据正在获取中...")

    # ═════════════════════════════════════════
    # SECTION 5: 微观深度分析
    # ═════════════════════════════════════════
    st.markdown("#### 🔬 微观深度分析")
    st.caption("分析基金持仓公司的经营情况、持仓变动、投资风格，形成微观层投资建议")

    try:
        from engine.micro_analysis import full_micro_analysis
        with st.spinner("正在分析持仓公司基本面..."):
            micro = full_micro_analysis(selected_code)

        # Comprehensive Micro Score
        micro_score = micro.get("composite_micro_score", 0)
        micro_rec = micro.get("recommendation", "")
        ms_color = UP if micro_score > 0.5 else WARN if micro_score > -0.5 else DOWN
        st.markdown(f'<div class="glass-card" style="border-color:rgba({int(ms_color[1:3],16) if len(ms_color) > 1 else 0},{int(ms_color[3:5],16) if len(ms_color) > 3 else 0},{int(ms_color[5:7],16) if len(ms_color) > 5 else 0},0.3);"><div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap;"><div style="text-align:center; min-width:100px;"><div class="label-dim">微观评分</div><div class="num-lg" style="color:{ms_color}; margin-top:8px;">{micro_score:+.1f}</div></div><div style="flex:1;"><div style="color:{TEXT_PRIMARY}; font-weight:600;">{micro_rec}</div><div style="color:{TEXT_MUTED}; font-size:0.85em; margin-top:6px;">{micro.get("holdings_analysis", {}).get("summary", "")}</div></div></div></div>', unsafe_allow_html=True)

        # Holdings Analysis
        holdings_a = micro.get("holdings_analysis", {})
        analyzed_holdings = holdings_a.get("holdings", [])
        if analyzed_holdings:
            st.markdown("##### 📊 持仓公司经营情况")
            for h in analyzed_holdings:
                pe_str = f"PE {h['pe']:.0f}" if h.get("pe") else "PE —"
                growth_str = f"{h['profit_growth']:+.0f}%" if h.get("profit_growth") is not None else "—"
                cap_str = h.get("cap_class", "")
                val_color = UP if h.get("valuation") in ("偏低", "合理") else WARN if h.get("valuation") == "适中偏高" else DOWN
                grow_color = UP if h.get("growth_score", 0) > 0 else DOWN if h.get("growth_score", 0) < 0 else TEXT_DIM
                industry = h.get("industry", "")

                st.markdown(f'<div style="display:flex; align-items:center; gap:8px; padding:7px 0; border-bottom:1px solid rgba(255,255,255,0.04); font-size:0.85em;"><span style="color:{TEXT_PRIMARY}; font-weight:600; min-width:100px;">{h["stock_name"]}</span><span style="color:{TEXT_DIM}; min-width:45px;">{h["hold_pct"]:.1f}%</span><span style="color:{val_color}; font-weight:600; min-width:60px;">{pe_str}</span><span style="color:{grow_color}; font-weight:600; min-width:70px;">增{growth_str}</span><span style="color:{TEXT_DIM}; min-width:50px;">{cap_str}</span><span style="color:{TEXT_DIM}; flex:1; font-size:0.8em;">{industry}</span><span style="color:{val_color}; font-weight:600; min-width:50px; text-align:right;">{h.get("valuation", "")}</span></div>', unsafe_allow_html=True)

            # Industry Distribution
            ind_dist = holdings_a.get("industry_distribution", {})
            if ind_dist:
                st.markdown("##### 🏭 持仓行业分布")
                sorted_ind = sorted(ind_dist.items(), key=lambda x: x[1], reverse=True)
                for ind_name, ind_pct in sorted_ind:
                    bar_w = min(ind_pct * 2, 100)
                    st.markdown(f'<div style="display:flex; align-items:center; gap:8px; padding:6px 0; font-size:0.85em;"><span style="color:{TEXT_SECONDARY}; min-width:100px; font-weight:500;">{ind_name}</span><div style="flex:1; height:8px; background:{BRAND_DIM}; border-radius:4px;"><div style="width:{bar_w}%; height:100%; background:linear-gradient(90deg, {BRAND}, {UP}); border-radius:4px;"></div></div><span style="color:{BRAND}; font-weight:700; min-width:50px; text-align:right;">{ind_pct:.1f}%</span></div>', unsafe_allow_html=True)

        # Position Changes
        changes = micro.get("position_changes", {})
        change_list = changes.get("changes", [])
        if change_list:
            st.markdown("##### 🔄 持仓变动追踪")
            st.caption(changes.get("summary", ""))
            for c in change_list[:10]:
                ct = c.get("change_type", "")
                ct_color = {"新进": UP, "增持": BRAND, "减持": WARN, "退出": DOWN, "不变": TEXT_DIM}.get(ct, TEXT_MUTED)
                ct_emoji = {"新进": "🆕", "增持": "📈", "减持": "📉", "退出": "🚪", "不变": "➡️"}.get(ct, "")
                change_pct = c.get("change_pct", 0)
                st.markdown(f'<div style="display:flex; align-items:center; gap:12px; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.04); font-size:0.85em;"><span style="color:{ct_color}; font-weight:700; min-width:50px;">{ct_emoji} {ct}</span><span style="color:{TEXT_PRIMARY}; flex:1; font-weight:500;">{c["stock_name"]}</span><span style="color:{TEXT_DIM};">占比 {c.get("hold_pct", 0):.1f}%</span><span style="color:{ct_color}; font-weight:700; min-width:60px; text-align:right;">{change_pct:+.1f}%</span></div>', unsafe_allow_html=True)

        # ─── 投资风格 ───
        style = micro.get("style_analysis", {})
        if style.get("style") != "未知":
            st.markdown("##### 🎨 投资风格分析")
            st.caption(style.get("summary", ""))
            scol1, scol2, scol3 = st.columns(3)
            scol1.metric("风格定位", style.get("style", "—"))
            scol2.metric("大盘股占比", f'{style.get("large_cap_pct", 0):.1f}%')
            scol3.metric("小盘股占比", f'{style.get("small_cap_pct", 0):.1f}%')

        # ─── 基金经理 ───
        mgr = micro.get("manager_analysis", {})
        if mgr.get("manager") != "未知":
            st.markdown("##### 👤 基金经理评估")
            st.caption(mgr.get("summary", ""))

        # ─── 微观风险提示 ───
        risks = micro.get("risks", [])
        if risks:
            st.markdown("##### ⚠️ 微观风险提示")
            for r in risks:
                st.warning(r)

    except Exception as e:
        st.caption(f"微观分析模块加载中... ({e})")

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 6: 日收益率分布
    # ═════════════════════════════════════════
    if not df_history.empty and "daily_return_pct" in df_history.columns:
        with st.expander("📊 日收益率分布（高级）", expanded=False):
            returns = df_history["daily_return_pct"].dropna()
            if len(returns) > 5:
                ret_cols = st.columns(4)
                ret_cols[0].metric("平均日收益", f"{returns.mean():.3f}%")
                ret_cols[1].metric("日波动率", f"{returns.std():.3f}%")
                ret_cols[2].metric("最大单日涨幅", f"{returns.max():+.2f}%")
                ret_cols[3].metric("最大单日跌幅", f"{returns.min():+.2f}%")

                hist_df = pd.DataFrame({"日收益率(%)": returns.values})
                st.bar_chart(hist_df, use_container_width=True)


# ── 辅助函数 ──

def _trend_cn(trend: str) -> str:
    return {
        "uptrend": "📈 上升趋势",
        "downtrend": "📉 下降趋势",
        "sideways": "➡️ 横盘震荡",
        "unknown": "❓ 未知",
    }.get(trend, "❓ 未知")


def _macd_cn(signal: str) -> str:
    return {
        "bullish": "🟢 金叉看多",
        "bearish": "🔴 死叉看空",
        "neutral": "⚪ 中性",
        "unknown": "❓ 未知",
    }.get(signal, "❓ 未知")
