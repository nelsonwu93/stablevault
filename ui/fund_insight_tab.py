"""
基金透视页面 — Fund Insight Tab (Tab2)
展示单只基金的四维评分穿透、决策分析、Checklist验证、基本面详情、AI点评
"""

import streamlit as st
from typing import Dict, List, Optional, Callable
from ui.decision_graph import render_decision_graph
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
    """Strip leading whitespace from each line to prevent Streamlit treating indented HTML as code blocks."""
    return '\n'.join(line.lstrip() for line in html.split('\n'))


def render_fund_insight_tab(
    reports: List,
    funds_config: List[Dict],
    load_fund_detail_fn: Optional[Callable] = None,
):
    """
    渲染基金透视Tab

    Args:
        reports: List[FundAnalysisReport] - 分析报告列表
        funds_config: List[Dict] - 基金配置列表（来自config.FUNDS）
        load_fund_detail_fn: optional callable(fund_code) -> dict，用于加载额外基本面详情
    """
    st.markdown("### 🔍 基金透视")
    st.caption("深度分析单只基金的四维评分、决策建议、Checklist验证、基本面详情")

    if not reports:
        st.warning("暂无分析报告数据，请先运行分析引擎")
        return

    # ──────────────────────────────────────────
    # A. Fund Selector
    # ──────────────────────────────────────────
    fund_options = {
        r.fund_code: f"{r.sector_icon} {r.fund_name} ({r.fund_code})"
        for r in reports
    }

    selected_code = st.selectbox(
        "选择基金",
        options=list(fund_options.keys()),
        format_func=lambda x: fund_options[x],
        key="insight_fund_selector",
    )

    selected_report = next((r for r in reports if r.fund_code == selected_code), None)
    if not selected_report:
        st.error("未找到选中基金的分析报告")
        return

    # ──────────────────────────────────────────
    # B. Fund Header Card
    # ──────────────────────────────────────────
    d_color = selected_report.d_color
    rec_badge = _get_recommendation_badge_class(selected_report.recommendation)

    header_html = f'''
<div class="glass-card" style="border-color:rgba({_hex_to_rgb(d_color)},0.2); margin-bottom:20px;">
<div style="display:flex; align-items:center; justify-content:space-between; gap:24px;">
<div style="display:flex; align-items:center; gap:16px;">
<span style="font-size:2.5em;">{selected_report.sector_icon}</span>
<div>
<div class="label-dim" style="font-size:0.8em; margin-bottom:4px;">{selected_report.sector}</div>
<div style="font-size:1.2em; font-weight:700; color:{TEXT_PRIMARY};">{selected_report.fund_name}</div>
<div style="font-size:0.75em; color:{TEXT_DIM}; margin-top:2px;">{selected_report.fund_code}</div>
</div>
</div>
<div style="text-align:center;">
<div class="label-dim" style="font-size:0.75em; margin-bottom:6px;">D-Score</div>
<div style="font-family:monospace; font-size:1.8em; font-weight:700; color:{d_color};">{selected_report.d_score:+.2f}</div>
<div style="font-size:0.7em; color:{TEXT_MUTED}; margin-top:4px;">{selected_report.d_label}</div>
</div>
<div style="text-align:right;">
<span class="{rec_badge}" style="display:inline-block; margin-bottom:8px;">{selected_report.rec_emoji} {selected_report.rec_label}</span>
<div style="color:{TEXT_MUTED}; font-size:0.75em; margin-top:8px;">置信度</div>
<div style="color:{WARN}; font-weight:700; font-size:1em; margin-top:4px;">{selected_report.confidence_stars}</div>
</div>
</div>
</div>
'''
    st.markdown(_h(header_html), unsafe_allow_html=True)

    st.divider()

    # ──────────────────────────────────────────
    # C. 四维评分 (M/S/T/F)
    # ──────────────────────────────────────────
    st.markdown("#### 📊 四维评分穿透")

    dimensions = [
        ("M", "宏观", selected_report.macro, SCORE_MACRO),
        ("S", "行业", selected_report.sector_score, UP),
        ("T", "技术", selected_report.technical, WARN),
        ("F", "基本面", selected_report.fundamental, DOWN),
    ]

    cols = st.columns(4, gap="medium")

    for col_idx, (dim_abbr, dim_name, score_detail, base_color) in enumerate(dimensions):
        with cols[col_idx]:
            bar_pct = min(max((score_detail.score + 2) / 4.0 * 100, 0), 100)
            contribution_pct = min(max(score_detail.contribution * 20 + 50, 0), 100)

            dim_html = f'''
<div class="glass-card" style="border-left:3px solid {base_color}; padding:16px; height:100%;">
<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
<div style="font-size:1.6em; font-weight:700; color:{base_color};">{dim_abbr}</div>
<div style="text-align:right;">
<div style="font-family:{FONT_MONO}; font-size:1.1em; font-weight:700; color:{base_color};">{score_detail.score:+.2f}</div>
<div class="label-dim" style="font-size:0.65em; margin-top:2px;">{score_detail.label}</div>
</div>
</div>
<div style="margin:10px 0;">
<div style="display:flex; justify-content:space-between; font-size:0.7em; margin-bottom:3px;">
<span class="label-dim">权重</span>
<span style="color:{base_color}; font-weight:600;">{score_detail.weight:.0%}</span>
</div>
<div style="width:100%; height:4px; background:rgba(255,255,255,0.05); border-radius:2px; overflow:hidden;">
<div style="width:{score_detail.weight*100}%; height:100%; background:{base_color};"></div>
</div>
</div>
<div style="margin:10px 0; padding-top:10px; border-top:1px solid rgba(255,255,255,0.08);">
<div class="label-dim" style="font-size:0.65em; margin-bottom:6px;">关键成分</div>
'''

            if score_detail.components:
                for comp_name, comp_val in list(score_detail.components.items())[:3]:
                    if isinstance(comp_val, dict):
                        val = comp_val.get("score", 0)
                    else:
                        val = comp_val
                    try:
                        val = float(val)
                    except (TypeError, ValueError):
                        val = 0.0
                    comp_color = UP if val > 0 else DOWN if val < 0 else TEXT_MUTED
                    dim_html += f'''
<div style="display:flex; justify-content:space-between; font-size:0.65em; color:{TEXT_MUTED}; margin-bottom:3px;">
<span>{comp_name[:12]}</span>
<span style="color:{comp_color}; font-weight:600;">{val:+.2f}</span>
</div>
'''
            else:
                dim_html += f'<div style="color:{TEXT_DIM}; font-size:0.65em;">无数据</div>'

            dim_html += '</div></div>'
            st.markdown(_h(dim_html), unsafe_allow_html=True)

    st.divider()

    # ──────────────────────────────────────────
    # D. D-score 公式
    # ──────────────────────────────────────────
    st.markdown("#### 🧮 D-score 合成")

    m_w, m_s = selected_report.macro.weight, selected_report.macro.score
    s_w, s_s = selected_report.sector_score.weight, selected_report.sector_score.score
    t_w, t_s = selected_report.technical.weight, selected_report.technical.score
    f_w, f_s = selected_report.fundamental.weight, selected_report.fundamental.score

    formula_html = f'''
<div class="glass-card" style="padding:16px;">
<div style="font-family:{FONT_MONO}; font-size:0.85em; line-height:1.6; color:{TEXT_SECONDARY};">
D = <span style="color:{SCORE_MACRO}; font-weight:700;">{m_w:.0%}</span>×<span style="color:{SCORE_MACRO};">{m_s:+.2f}</span> + <span style="color:{UP}; font-weight:700;">{s_w:.0%}</span>×<span style="color:{UP};">{s_s:+.2f}</span> + <span style="color:{WARN}; font-weight:700;">{t_w:.0%}</span>×<span style="color:{WARN};">{t_s:+.2f}</span> + <span style="color:{DOWN}; font-weight:700;">{f_w:.0%}</span>×<span style="color:{DOWN};">{f_s:+.2f}</span>
<div style="margin-top:12px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.08);">
= <span style="color:{d_color}; font-weight:700; font-size:1.1em;">{selected_report.d_score:+.3f}</span>
</div>
</div>
</div>
'''
    st.markdown(_h(formula_html), unsafe_allow_html=True)

    st.divider()

    # ──────────────────────────────────────────
    # E. Checklist 验证
    # ──────────────────────────────────────────
    st.markdown("#### ✅ Checklist 验证")

    if selected_report.checklist_items:
        score_pct = selected_report.checklist_score or 0
        all_pass = selected_report.checklist_passed == selected_report.checklist_total
        status_text = "🟢 全部通过" if all_pass else "⚠️ 部分不符"
        status_color = UP if all_pass else WARN

        checklist_html = f'''
<div class="glass-card" style="margin-bottom:12px;">
<div style="display:flex; justify-content:space-between; align-items:center;">
<div>
<span style="color:{status_color}; font-weight:700;">{status_text}</span>
<div style="color:{TEXT_MUTED}; font-size:0.8em; margin-top:4px;">{selected_report.checklist_passed}/{selected_report.checklist_total} 项通过</div>
</div>
<div style="font-family:{FONT_MONO}; font-size:1.3em; font-weight:700; color:{status_color};">{score_pct:.0f}%</div>
</div>
<div style="width:100%; height:6px; background:rgba(255,255,255,0.05); border-radius:3px; margin-top:10px; overflow:hidden;">
<div style="width:{score_pct}%; height:100%; background:{status_color};"></div>
</div>
</div>
'''
        st.markdown(_h(checklist_html), unsafe_allow_html=True)

        checklist_by_dim = _group_checklist_by_dimension(selected_report.checklist_items)

        for dim_name, items in checklist_by_dim.items():
            st.markdown(f"**{dim_name}**", help=None)
            for item in items:
                passed = item.get("passed", False)
                icon = "✅" if passed else "❌"
                color = UP if passed else DOWN
                name = item.get("name", "")
                detail = item.get("detail", "")

                item_html = f'''
<div class="signal-bar" style="border-left-color:{color};">
<div style="color:{color}; font-weight:700; min-width:20px;">{icon}</div>
<div style="flex:1;">
<div style="color:{TEXT_PRIMARY}; font-weight:600; font-size:0.85em;">{name}</div>
<div style="color:{TEXT_MUTED}; font-size:0.75em; margin-top:2px;">{detail}</div>
</div>
</div>
'''
                st.markdown(_h(item_html), unsafe_allow_html=True)
    else:
        st.info("暂无Checklist数据")

    st.divider()

    # ──────────────────────────────────────────
    # F. 基本面详情
    # ──────────────────────────────────────────
    st.markdown("#### 📈 基本面详情")

    f_cols = st.columns(3, gap="medium")

    with f_cols[0]:
        st.markdown('<div class="label-dim" style="font-size:0.8em; margin-bottom:8px;">持仓特征</div>', unsafe_allow_html=True)
        st.write(selected_report.holdings_summary or "暂无数据")

    with f_cols[1]:
        st.markdown('<div class="label-dim" style="font-size:0.8em; margin-bottom:8px;">投资风格</div>', unsafe_allow_html=True)
        st.write(selected_report.style_summary or "暂无数据")

    with f_cols[2]:
        st.markdown('<div class="label-dim" style="font-size:0.8em; margin-bottom:8px;">基金经理</div>', unsafe_allow_html=True)
        st.write(selected_report.manager_summary or "暂无数据")

    holdings_data = selected_report.fundamental_raw.get("holdings", {}) if selected_report.fundamental_raw else {}
    holdings = holdings_data.get("holdings", []) if isinstance(holdings_data, dict) else []

    if holdings:
        st.markdown("**前十大重仓股**")
        for i, h in enumerate(holdings[:10]):
            pct = h.get("hold_pct", 0)
            bar_w = min(pct * 2.5, 100)
            name = h.get("stock_name", "—")

            holding_html = f'''
<div class="signal-bar" style="border-left-color:{SCORE_MACRO}; gap:12px;">
<div style="width:28px; color:{TEXT_DIM}; text-align:center; font-weight:700; font-size:0.85em;">{i+1}</div>
<div style="flex:1;">
<div style="color:{TEXT_PRIMARY}; font-weight:600; font-size:0.85em;">{name}</div>
<div style="width:100%; height:4px; background:{INFO_DIM}; border-radius:2px; margin-top:4px; overflow:hidden;">
<div style="width:{bar_w}%; height:100%; background:linear-gradient(90deg, {SCORE_MACRO}, {UP});"></div>
</div>
</div>
<div style="min-width:50px; text-align:right; color:{SCORE_MACRO}; font-weight:700; font-size:0.8em;">{pct:.2f}%</div>
</div>
'''
            st.markdown(_h(holding_html), unsafe_allow_html=True)

    st.divider()

    # ──────────────────────────────────────────
    # G. 决策因子知识图谱（交互式可视化）
    # ──────────────────────────────────────────
    render_decision_graph(selected_report)

    st.divider()

    # ──────────────────────────────────────────
    # H. AI 点评
    # ──────────────────────────────────────────
    if selected_report.commentary:
        st.markdown("#### 💬 AI 点评")

        comment_html = f'''
<div class="glass-card" style="border-left:3px solid {SCORE_MACRO}; padding:16px;">
<div style="line-height:1.7; color:{TEXT_SECONDARY}; font-size:0.9em;">
{selected_report.commentary}
</div>
</div>
'''
        st.markdown(_h(comment_html), unsafe_allow_html=True)

    st.divider()

    # ──────────────────────────────────────────
    # H. 风险提示
    # ──────────────────────────────────────────
    if selected_report.risk_alerts:
        st.markdown("#### ⚠️ 风险提示")
        for risk in selected_report.risk_alerts:
            st.warning(risk)


# ══════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════

def _hex_to_rgb(hex_color: str) -> str:
    """Convert hex color to R,G,B format string. E.g., #4f8df7 -> '0,212,255'"""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"{r},{g},{b}"
    return "0,0,0"


def _get_recommendation_badge_class(recommendation: str) -> str:
    """Return CSS class for recommendation badge"""
    badge_map = {
        "BUY": "badge-buy",
        "BUY_SMALL": "badge-buy",
        "WAIT": "badge-wait",
        "VETO": "badge-sell",
        "SELL": "badge-sell",
    }
    badge_class = badge_map.get(recommendation, "badge-wait")
    return f"status-badge {badge_class}"


def _group_checklist_by_dimension(checklist_items: List[Dict]) -> Dict[str, List[Dict]]:
    """Group checklist items by dimension field"""
    grouped = {}
    dimension_icons = {
        "宏观": "🌍",
        "技术": "📊",
        "仓位": "📦",
        "市场情绪": "😊",
        "风险控制": "🛡️",
    }

    for item in checklist_items:
        dim = item.get("dimension", "未分类")
        dim_with_icon = f"{dimension_icons.get(dim, '')} {dim}"

        if dim_with_icon not in grouped:
            grouped[dim_with_icon] = []
        grouped[dim_with_icon].append(item)

    return grouped


    # (Old _render_decision_chain and _FACTOR_EXPLAIN removed — now in ui/decision_graph.py)
