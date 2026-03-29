"""
Tab1 仪表盘 — 投资组合总览 + 宏观环境解读 + 风险预警
面向投资小白：所有指标附带通俗中文解释
"""

import streamlit as st
from typing import List, Dict, Any

from config import FUNDS
from ui.design_tokens import (
    BG_BASE, BG_CARD, BG_ELEVATED, BRAND, BRAND_DIM, BRAND_GLOW,
    UP, UP_DIM, DOWN, DOWN_DIM, WARN, WARN_DIM,
    INFO, INFO_DIM, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    BORDER, BORDER_HOVER, RADIUS_SM, RADIUS_MD, RADIUS_LG,
    SCORE_MACRO, SCORE_SECTOR, SCORE_TECH, SCORE_FUND,
    FONT_FAMILY, FONT_MONO, SHADOW_SM, SHADOW_MD,
    score_color, verdict_style, dim_color,
)


# ═══════════════════════════════════════════════════════════════
# 白话解读字典 — 让小白秒懂
# ═══════════════════════════════════════════════════════════════

REGIME_EXPLAIN = {
    "外部冲击": {
        "title": "外部冲击期 — 全球有大事发生",
        "what": "国际上正在发生重大事件（如地缘冲突、油价暴涨、大国贸易摩擦），金融市场波动剧烈。",
        "impact": "这种时候，所有基金都可能受拖累，不是你选的基金差，而是整个市场环境恶劣。",
        "advice": "建议暂停加仓，持有现金观望。等风暴过去再行动，\"留得青山在\"比\"抄底\"更重要。",
        "color": DOWN,
    },
    "放缓期": {
        "title": "经济放缓期 — 市场在犹豫",
        "what": "经济增长放慢但没有大跌，制造业景气度（PMI）在50附近徘徊，市场方向不明。",
        "impact": "这时候选对行业比选个股更重要，有些板块还能赚钱，有些已经开始走弱。",
        "advice": "可以小额试探性买入，重点关注防守型（红利ETF）和政策支持型（科技/新能源）基金。",
        "color": WARN,
    },
    "扩张期": {
        "title": "经济扩张期 — 赚钱的好时候",
        "what": "经济蓬勃发展，企业赚钱增多，市场信心足，资金在积极入场。",
        "impact": "大部分基金都在涨，尤其是成长型、科技型基金表现更好。",
        "advice": "可以积极加仓，选好的基金（D-Score高的），分批买入把握上涨机会。",
        "color": UP,
    },
    "衰退修复": {
        "title": "衰退修复期 — 最坏的已过去",
        "what": "经济见底了，政策在发力救市（降息/刺激），市场开始慢慢恢复。",
        "impact": "虽然还没完全好，但是\"黎明前\"，提前布局可能获得较好收益。",
        "advice": "可以适度加仓，但要分批进入，重点关注政策受益的板块。",
        "color": INFO,
    },
    "流动性危机": {
        "title": "流动性危机 — 市场\"缺钱\"了",
        "what": "利率太高、资金在撤离，市场上钱变少了，所有资产都在被\"甩卖\"。",
        "impact": "几乎所有基金都在跌，这是最危险的时期，不要贸然抄底。",
        "advice": "强烈建议持有现金、大幅减仓。等利率回落、资金重新流入后再考虑买入。",
        "color": "#a855f7",
    },
}

MACRO_EXPLAIN = {
    "US 10Y": {
        "name": "美国10年期国债利率",
        "simple": "全球资金的\"价格\"。利率越高，钱越\"贵\"，股市越吃亏",
        "good": "< 4.0% → 钱便宜，利好股市",
        "bad": "> 4.5% → 钱贵了，股市承压",
    },
    "黄金": {
        "name": "国际金价",
        "simple": "避险情绪的\"温度计\"。金价暴涨通常说明市场在恐慌",
        "good": "稳定 → 市场平静",
        "bad": "单日涨>2% → 有人在避险，注意风险",
    },
    "油价": {
        "name": "国际原油价格",
        "simple": "经济活动的\"血压\"。油价暴涨通常意味着供应出了问题",
        "good": "60-85$/桶 → 正常范围",
        "bad": "> 95$ 或单日涨>3% → 可能引发通胀/冲击",
    },
    "PMI": {
        "name": "中国制造业采购经理指数",
        "simple": "工厂忙不忙的\"信号灯\"。50是荣枯线——以上经济扩张，以下经济收缩",
        "good": "> 50 → 工厂在扩产，经济向好",
        "bad": "< 49 → 工厂在收缩，经济走弱",
    },
    "USD/CNY": {
        "name": "美元对人民币汇率",
        "simple": "人民币\"值不值钱\"。汇率上升=人民币贬值，外资可能撤离A股",
        "good": "< 7.10 → 人民币稳，外资安心",
        "bad": "> 7.25 → 人民币弱，资金外流压力",
    },
    "北向5日": {
        "name": "外资5日净买入(亿元)",
        "simple": "外国投资者这5天是在买A股还是卖A股。正数=买入=看好",
        "good": "> 50亿 → 外资积极流入，看好A股",
        "bad": "< -30亿 → 外资在撤，要谨慎",
    },
}


def render_dashboard_tab(
    reports: List[Any],
    summary: Dict[str, Any],
    market_data: Dict[str, Any],
    regime_name: str,
    regime_cfg: Dict[str, Any],
) -> None:
    """主仪表盘渲染"""

    # ═══════════════════════════════════════════════
    # SECTION A: Portfolio Pulse (KPIs)
    # ═══════════════════════════════════════════════

    total_value = sum(f["current_value"] for f in FUNDS)
    total_return = sum(f["total_return"] for f in FUNDS)
    total_cost = total_value - total_return
    return_pct = (total_return / total_cost * 100) if total_cost > 0 else 0
    return_color = UP if total_return >= 0 else DOWN

    avg_d = summary.get("avg_d_score", 0)
    d_color = summary.get("avg_d_color", "#f59e0b")
    buy_count = summary.get("buy_count", 0)
    wait_count = summary.get("wait_count", 0)
    veto_count = summary.get("veto_count", 0)
    regime_icon = regime_cfg.get("icon", "🌧️")

    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        st.markdown(f'<div class="kpi-card"><div class="label-dim">总资产</div><div class="num-lg" style="color:{INFO};">¥{total_value:,.0f}</div><div style="font-size:0.85em;color:{return_color};">收益 {total_return:+,.0f} ({return_pct:+.1f}%)</div></div>', unsafe_allow_html=True)

    with col2:
        # D-Score 解释
        if avg_d >= 0.4:
            d_hint = "偏积极，可适当加仓"
        elif avg_d >= -0.2:
            d_hint = "中性，建议观望"
        else:
            d_hint = "偏消极，建议谨慎"
        st.markdown(f'<div class="kpi-card"><div class="label-dim">综合评分 D-Score</div><div class="num-lg" style="color:{d_color};">{avg_d:+.2f}</div><div style="font-size:0.8em;color:{TEXT_MUTED};">{d_hint}</div></div>', unsafe_allow_html=True)

    with col3:
        st.markdown(f'<div class="kpi-card"><div class="label-dim">当前市场环境</div><div style="font-size:2em;margin:6px 0;">{regime_icon}</div><div style="font-size:0.9em;color:{TEXT_PRIMARY};font-weight:600;">{regime_name}</div></div>', unsafe_allow_html=True)

    with col4:
        total_signals = buy_count + wait_count + veto_count
        st.markdown(f'<div class="kpi-card"><div class="label-dim">操作信号</div><div style="display:flex;gap:8px;margin-top:10px;"><div style="flex:1;text-align:center;"><div style="font-size:1.4em;font-weight:700;color:{UP};">{buy_count}</div><div style="font-size:0.7em;color:{TEXT_MUTED};">可买入</div></div><div style="flex:1;text-align:center;"><div style="font-size:1.4em;font-weight:700;color:{WARN};">{wait_count}</div><div style="font-size:0.7em;color:{TEXT_MUTED};">等一等</div></div><div style="flex:1;text-align:center;"><div style="font-size:1.4em;font-weight:700;color:{DOWN};">{veto_count}</div><div style="font-size:0.7em;color:{TEXT_MUTED};">别碰</div></div></div></div>', unsafe_allow_html=True)

    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════
    # SECTION A2: Regime 白话解读
    # ═══════════════════════════════════════════════
    regime_info = REGIME_EXPLAIN.get(regime_name, REGIME_EXPLAIN["放缓期"])
    rc = regime_info["color"]

    st.markdown(
        f'<div class="glass-card" style="border-left:4px solid {rc}; padding:20px;">'
        f'<div style="font-size:1.1em;font-weight:700;color:{rc};margin-bottom:10px;">{regime_icon} {regime_info["title"]}</div>'
        f'<div style="color:{TEXT_MUTED};font-size:0.9em;line-height:1.8;">'
        f'<div style="margin-bottom:8px;">📌 <b style="color:{TEXT_PRIMARY};">发生了什么？</b> {regime_info["what"]}</div>'
        f'<div style="margin-bottom:8px;">💡 <b style="color:{TEXT_PRIMARY};">对我的基金意味着什么？</b> {regime_info["impact"]}</div>'
        f'<div>🎯 <b style="color:{TEXT_PRIMARY};">我应该怎么做？</b> <span style="color:{rc};font-weight:600;">{regime_info["advice"]}</span></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════
    # SECTION B: Fund Score Matrix
    # ═══════════════════════════════════════════════
    st.markdown(f'<div style="font-size:1.15em;font-weight:700;color:{TEXT_PRIMARY};margin-bottom:4px;">📈 基金评分一览</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:{TEXT_DIM};font-size:0.82em;margin-bottom:16px;">D-Score越高越好，绿色=建议买入 · 橙色=观望 · 红色=回避</div>', unsafe_allow_html=True)

    if reports:
        sorted_reports = sorted(reports, key=lambda r: r.d_score, reverse=True)
        for i in range(0, len(sorted_reports), 4):
            cols = st.columns(4, gap="small")
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(sorted_reports):
                    break
                with col:
                    _render_fund_card(sorted_reports[idx])
    else:
        st.info("暂无基金分析数据")

    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════
    # SECTION C: Macro Environment (with explanations)
    # ═══════════════════════════════════════════════
    st.markdown(f'<div style="font-size:1.15em;font-weight:700;color:{TEXT_PRIMARY};margin-bottom:4px;">🌍 宏观环境概览</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:{TEXT_DIM};font-size:0.82em;margin-bottom:16px;">这些全球经济指标直接影响你的基金涨跌，点击展开看详细解读</div>', unsafe_allow_html=True)

    _render_macro_indicators(market_data)

    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════
    # SECTION D: Risk Radar
    # ═══════════════════════════════════════════════
    st.markdown(f'<div style="font-size:1.15em;font-weight:700;color:{TEXT_PRIMARY};margin-bottom:4px;">⚠️ 风险雷达</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:{TEXT_DIM};font-size:0.82em;margin-bottom:16px;">系统自动检测的风险预警，红色=必须关注 · 黄色=需留意 · 蓝色=参考</div>', unsafe_allow_html=True)
    _render_risk_radar(reports)


# ══════════════════════════════════════════════
# Helper: Fund Mini-Card
# ══════════════════════════════════════════════

def _render_fund_card(report) -> None:
    d = report.d_score
    bar_pct = getattr(report, 'd_bar_pct', min(max((d + 2) / 4 * 100, 0), 100))

    if d >= 0.4:
        bar_color, bg_tint = UP, UP_DIM
    elif d >= -0.2:
        bar_color, bg_tint = INFO, INFO_DIM
    else:
        bar_color, bg_tint = DOWN, DOWN_DIM

    html = (
        f'<div class="fund-card" style="background:{bg_tint};border-left:3px solid {bar_color};padding:12px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
        f'<span style="font-size:0.85em;font-weight:600;">{report.sector_icon} {report.fund_short}</span>'
        f'<span style="font-family:monospace;font-weight:700;color:{bar_color};font-size:0.9em;">{d:+.2f}</span>'
        f'</div>'
        f'<div style="width:100%;height:4px;background:{BORDER};border-radius:2px;overflow:hidden;margin-bottom:8px;">'
        f'<div style="height:100%;width:{bar_pct:.0f}%;background:{bar_color};border-radius:2px;"></div>'
        f'</div>'
        f'<div style="font-size:0.75em;color:{TEXT_MUTED};text-align:center;">{report.rec_emoji} {report.rec_label}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# Helper: Macro Indicators (with beginner explanations)
# ══════════════════════════════════════════════

def _render_macro_indicators(market_data: Dict) -> None:
    g = market_data.get("global", {})
    c = market_data.get("china", {})
    nb = market_data.get("northbound", {})

    indicators = [
        ("US 10Y", g.get("us_10y", {}).get("price"), g.get("us_10y", {}).get("change_pct"), ".2f", "%"),
        ("黄金", g.get("gold", {}).get("price"), g.get("gold", {}).get("change_pct"), ",.0f", "$/oz"),
        ("油价", g.get("oil", {}).get("price"), g.get("oil", {}).get("change_pct"), ".1f", "$/桶"),
        ("PMI", c.get("pmi", {}).get("pmi"), None, ".1f", ""),
        ("USD/CNY", g.get("usd_cny", {}).get("price"), g.get("usd_cny", {}).get("change_pct"), ".4f", ""),
        ("北向5日", nb.get("5day_total"), None, "+.1f", "亿"),
    ]

    # Row 1: 指标值显示
    cols = st.columns(6, gap="small")
    for i, col in enumerate(cols):
        label, value, change, fmt, unit = indicators[i]
        with col:
            if value is None:
                val_str, color, change_str = "—", TEXT_DIM, ""
            else:
                try:
                    val_str = f"{value:{fmt}}"
                except (ValueError, TypeError):
                    val_str = str(value)
                color = TEXT_PRIMARY
                if change is not None and change != 0:
                    arrow = "▲" if change > 0 else "▼"
                    chg_color = UP if change > 0 else DOWN
                    change_str = f'<span style="color:{chg_color};font-size:0.8em;">{arrow} {abs(change):.2f}%</span>'
                else:
                    change_str = ""

            # 健康状态指示
            health = _indicator_health(label, value)
            dot_color = {"good": UP, "neutral": WARN, "bad": DOWN}.get(health, TEXT_DIM)

            html = (
                f'<div class="data-tile" style="padding:12px;text-align:center;">'
                f'<div class="label-dim" style="font-size:0.7em;margin-bottom:4px;">'
                f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{dot_color};margin-right:4px;vertical-align:middle;"></span>'
                f'{label}</div>'
                f'<div style="font-family:monospace;font-size:1.1em;font-weight:700;color:{color};">{val_str}</div>'
                f'<div style="font-size:0.7em;color:{TEXT_DIM};">{unit}</div>'
                f'<div>{change_str}</div>'
                f'</div>'
            )
            st.markdown(html, unsafe_allow_html=True)

    # Row 2: 白话解读（可展开）
    with st.expander("📖 看不懂这些数字？点这里看白话解读", expanded=False):
        for label, value, change, fmt, unit in indicators:
            info = MACRO_EXPLAIN.get(label, {})
            if not info:
                continue
            health = _indicator_health(label, value)
            health_emoji = {"good": "🟢", "neutral": "🟡", "bad": "🔴"}.get(health, "⚪")
            health_text = {"good": info.get("good", ""), "neutral": "处于中性区间", "bad": info.get("bad", "")}.get(health, "")

            try:
                val_display = f"{value:{fmt}}{unit}" if value is not None else "暂无数据"
            except (ValueError, TypeError):
                val_display = str(value) if value is not None else "暂无数据"

            st.markdown(
                f'<div class="signal-bar" style="margin-bottom:4px;padding:10px 14px;">'
                f'<div style="flex:1;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="color:{TEXT_PRIMARY};font-weight:600;font-size:0.9em;">{health_emoji} {info.get("name", label)}</span>'
                f'<span style="font-family:monospace;color:{INFO};font-weight:600;">{val_display}</span>'
                f'</div>'
                f'<div style="color:{TEXT_MUTED};font-size:0.82em;margin-top:4px;">{info.get("simple", "")}</div>'
                f'<div style="color:{_health_color(health)};font-size:0.78em;margin-top:2px;font-weight:600;">{health_text}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )


def _health_color(health: str) -> str:
    return {"good": UP, "neutral": WARN, "bad": DOWN}.get(health, TEXT_MUTED)


def _indicator_health(label: str, value) -> str:
    """判断指标健康状态: good / neutral / bad"""
    if value is None:
        return "neutral"
    try:
        v = float(value)
    except (ValueError, TypeError):
        return "neutral"

    if label == "US 10Y":
        return "good" if v < 4.0 else "bad" if v > 4.5 else "neutral"
    elif label == "PMI":
        return "good" if v > 50.0 else "bad" if v < 49.0 else "neutral"
    elif label == "USD/CNY":
        return "good" if v < 7.10 else "bad" if v > 7.25 else "neutral"
    elif label == "油价":
        return "good" if 55 <= v <= 85 else "bad" if v > 95 else "neutral"
    elif label == "北向5日":
        return "good" if v > 50 else "bad" if v < -30 else "neutral"
    elif label == "黄金":
        return "neutral"  # Gold is complex, always neutral display
    return "neutral"


# ══════════════════════════════════════════════
# Helper: Risk Radar
# ══════════════════════════════════════════════

def _render_risk_radar(reports: List) -> None:
    alerts = []
    for r in reports:
        for alert_text in (r.risk_alerts or []):
            if "无特别风险" in alert_text or "当前无" in alert_text:
                continue
            alerts.append((r.fund_short, alert_text))

    if not alerts:
        st.success("✅ 当前未发现需要特别关注的风险预警，你的持仓相对安全。")
        return

    for fund_name, msg in alerts:
        if any(kw in msg for kw in ("止损", "深度负值", "一票否决", "系统性风险")):
            border_color, level = DOWN, "🔴 重要"
        elif any(kw in msg for kw in ("止盈", "超买", "高弹性", "汇率")):
            border_color, level = WARN, "🟡 留意"
        else:
            border_color, level = INFO, "🔵 参考"

        html = (
            f'<div class="signal-bar" style="border-left:4px solid {border_color};padding:10px 14px;margin-bottom:6px;">'
            f'<span style="color:{border_color};font-weight:600;font-size:0.8em;min-width:60px;display:inline-block;">{level}</span>'
            f'<span style="color:{TEXT_PRIMARY};font-weight:600;font-size:0.85em;min-width:70px;display:inline-block;">{fund_name}</span>'
            f'<span style="color:{TEXT_MUTED};font-size:0.85em;">{msg}</span>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)
