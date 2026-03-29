"""
决策因子影响链路 — Knowledge-Graph Style Interactive Visualization
================================================================
Uses st.components.v1.html() to render a full SVG + JS interactive graph
showing how macro signals flow through dimensions to the final D-Score.

Layout (3 layers):
  Layer 1 — Factor Nodes (individual scores per dimension)
  Layer 2 — Dimension Nodes (M / S / T / F aggregated)
  Layer 3 — D-Score → Recommendation

Connections are drawn as SVG bezier curves with:
  - Color: green (positive) / red (negative) / amber (neutral)
  - Thickness: proportional to |score|
  - Hover: highlights the full influence path
"""

import json
import streamlit as st
from typing import Dict, List, Any

from ui.design_tokens import (
    BG_BASE, BG_CARD, BG_ELEVATED, BG_OVERLAY,
    BRAND, UP, DOWN, WARN, INFO,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    BORDER,
    SCORE_MACRO, SCORE_SECTOR, SCORE_TECH, SCORE_FUND,
)

# ══════════════════════════════════════════════════════════
# Factor plain-language explanations (Chinese)
# ══════════════════════════════════════════════════════════

FACTOR_EXPLAIN: Dict[str, Dict[str, str]] = {
    # ── 宏观因子 ──
    "利率周期": {"icon": "🏦", "what": "美国加息/降息", "link": "利率高→钱变贵→股市承压 | 利率低→钱便宜→股市受益"},
    "经济周期": {"icon": "🏭", "what": "中国制造业景气度(PMI)", "link": "PMI>50→经济扩张→企业赚钱 | PMI<49→收缩→要小心"},
    "商品冲击": {"icon": "🛢️", "what": "油价大幅波动", "link": "油价暴涨→通胀压力→资产承压 | 油价稳定→经济正常运转"},
    "利差压力": {"icon": "💱", "what": "中美利差/人民币汇率", "link": "利差大→人民币弱→外资流出 | 利差小→汇率稳→外资放心"},
    "风险偏好": {"icon": "🎲", "what": "全球投资者情绪", "link": "避险(金涨股跌)→大家在跑 | 冒险(股涨金平)→大家在追"},
    # ── 行业因子 ──
    "利率敏感": {"icon": "📉", "what": "该板块对利率变化的反应", "link": "高成长基金对利率特别敏感"},
    "PMI景气":  {"icon": "📊", "what": "经济景气对该板块的传导", "link": "经济好→行业订单多→基金涨"},
    "油价影响": {"icon": "⛽", "what": "油价变动对该板块的影响", "link": "新能源板块反而受益于油价上涨"},
    "北向资金": {"icon": "🏧", "what": "外资对该板块的偏好", "link": "外资流入→买的就是这类优质股"},
    "地缘风险": {"icon": "🌐", "what": "地缘政治对该板块的冲击", "link": "冲突升级→红利防守反而受益"},
    "英伟达信号": {"icon": "🤖", "what": "AI龙头英伟达的涨跌", "link": "英伟达涨→全球AI热→国内AI基金跟涨"},
    "国债收益": {"icon": "🏛️", "what": "中国国债利率", "link": "利率降→高股息更吸引人→红利基金涨"},
    # ── 技术因子 ──
    "均线位置": {"icon": "📈", "what": "当前净值vs历史平均", "link": "均线上方=偏贵 | 均线下方=偏便宜"},
    "RSI":     {"icon": "⚡", "what": "超买/超卖指标", "link": "RSI>70=太热可能回调 | RSI<30=太冷可能反弹"},
    "波动率":  {"icon": "🌊", "what": "价格波动大小", "link": "波动大=风险大但机会也大 | 波动小=比较稳"},
    "趋势强度": {"icon": "🧭", "what": "MACD/趋势方向", "link": "金叉=开始上涨 | 死叉=开始下跌"},
    "持仓状态": {"icon": "📦", "what": "当前持仓盈亏状态", "link": "浮盈多=可考虑止盈 | 浮亏多=需要评估"},
    "仓位空间": {"icon": "📐", "what": "距离目标仓位还有多少空间", "link": "仓位低=可以加 | 仓位满=别追了"},
    # ── 基本面因子 ──
    "持仓估值": {"icon": "💰", "what": "基金持仓的贵不贵", "link": "PE低=持仓便宜有安全垫 | PE高=持仓偏贵"},
    "盈利成长": {"icon": "📈", "what": "持仓公司赚钱能力", "link": "利润增长快→基金有上涨动力"},
    "集中度":  {"icon": "🎯", "what": "持仓分散还是集中", "link": "太集中=风险大 | 适度分散=更安全"},
    "经理能力": {"icon": "👤", "what": "基金经理的历史业绩", "link": "老司机=更让人放心"},
    "持仓稳定": {"icon": "🔒", "what": "基金经理是否频繁换仓", "link": "稳定=有信念 | 频繁换=可能在追热点"},
}


def render_decision_graph(report) -> None:
    """
    Render a full-page interactive knowledge-graph visualization
    of the decision factor influence chain for a single fund.
    """
    st.markdown(
        '<div style="margin-bottom:8px;">'
        f'<span style="font-size:1.15em;font-weight:700;color:{TEXT_PRIMARY};">🧠 决策因子知识图谱</span>'
        f'<span style="color:{TEXT_MUTED};font-size:0.82em;margin-left:12px;">'
        '从全球宏观到最终操作建议 — 每一步推导逻辑和影响程度一目了然'
        '</span></div>',
        unsafe_allow_html=True,
    )

    data = _prepare_graph_data(report)
    html = _build_graph_html(data)

    total_factors = sum(len(d["factors"]) for d in data["dimensions"])
    height = max(780, total_factors * 54 + 260)

    st.components.v1.html(html, height=height, scrolling=False)


# ──────────────────────────────────────────────────────────
# Data preparation
# ──────────────────────────────────────────────────────────

def _prepare_graph_data(report) -> dict:
    """Extract structured data from FundAnalysisReport for the graph."""

    dim_configs = [
        ("M", "宏观环境", report.macro, SCORE_MACRO,
         "全球经济大环境", "利率、PMI、油价、汇率、情绪"),
        ("S", "行业板块", report.sector_score, SCORE_SECTOR,
         "行业景气度", "行业对宏观的敏感度和传导"),
        ("T", "技术面", report.technical, SCORE_TECH,
         "价格信号", "均线、RSI、趋势、波动率"),
        ("F", "基本面", report.fundamental, SCORE_FUND,
         "基金质量", "估值、成长、集中度、经理"),
    ]

    dimensions = []
    for abbr, name, sd, color, short_desc, sub_desc in dim_configs:
        factors = []
        if sd.components:
            for comp_name, comp_val in sd.components.items():
                if isinstance(comp_val, dict):
                    val = comp_val.get("score", 0)
                    detail = comp_val.get("detail", "")
                else:
                    val = comp_val if isinstance(comp_val, (int, float)) else 0
                    detail = ""
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    val = 0.0

                explain = FACTOR_EXPLAIN.get(comp_name, {})
                factors.append({
                    "name": comp_name,
                    "score": round(val, 2),
                    "icon": explain.get("icon", "📌"),
                    "what": explain.get("what", comp_name),
                    "link": explain.get("link", ""),
                    "detail": str(detail) if detail else "",
                })

        dimensions.append({
            "abbr": abbr,
            "name": name,
            "short": short_desc,
            "sub": sub_desc,
            "score": round(sd.score, 2),
            "weight": round(sd.weight, 2),
            "weightPct": round(sd.weight * 100),
            "contribution": round(sd.contribution, 3),
            "color": color,
            "label": sd.label,
            "factors": factors,
        })

    return {
        "fundName": report.fund_name,
        "fundCode": report.fund_code,
        "sector": report.sector,
        "sectorIcon": report.sector_icon,
        "regimeName": getattr(report, "regime_name", ""),
        "regimeIcon": getattr(report, "regime_icon", ""),
        "dimensions": dimensions,
        "dScore": round(report.d_score, 3),
        "dColor": report.d_color,
        "dLabel": report.d_label,
        "recLabel": report.rec_label,
        "recEmoji": report.rec_emoji,
        "confidenceStars": report.confidence_stars,
    }


# ──────────────────────────────────────────────────────────
# HTML / CSS / JS builder
# ──────────────────────────────────────────────────────────

def _build_graph_html(data: dict) -> str:
    """Return a self-contained HTML document for the knowledge graph."""

    data_json = json.dumps(data, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
/* ── Reset & base ── */
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{
  background:{BG_BASE};
  color:{TEXT_PRIMARY};
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  -webkit-font-smoothing:antialiased;
  padding:16px 12px;
  overflow-x:hidden;
}}

/* ── Graph container ── */
.graph-wrap{{
  position:relative;
  width:100%;
}}
.graph-svg{{
  position:absolute;
  top:0;left:0;
  width:100%;height:100%;
  pointer-events:none;
  z-index:1;
}}
.graph-body{{
  position:relative;
  z-index:2;
  display:grid;
  grid-template-columns:33% 6% 22% 6% 1fr;
  gap:0;
}}

/* ── Layer containers ── */
.factor-col{{
  display:flex;
  flex-direction:column;
  gap:6px;
}}
.dim-col{{
  display:flex;
  flex-direction:column;
  justify-content:space-around;
  gap:16px;
  padding:8px 0;
}}
.result-col{{
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:12px;
}}

/* ── Factor group ── */
.factor-group{{
  margin-bottom:10px;
}}
.factor-group-header{{
  font-size:0.72em;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:0.5px;
  margin-bottom:5px;
  padding-left:4px;
  opacity:0.5;
}}

/* ── Factor node ── */
.factor-node{{
  display:flex;
  align-items:center;
  gap:8px;
  padding:6px 10px;
  background:rgba(28,29,34,0.4);
  border:1px solid {BORDER};
  border-radius:8px;
  cursor:pointer;
  transition:all 0.25s ease;
  position:relative;
}}
.factor-node:hover{{
  background:{BG_ELEVATED};
  border-color:{BORDER};
  transform:translateX(3px);
}}
.factor-icon{{font-size:1em;flex:0 0 20px;text-align:center;}}
.factor-info{{flex:1;min-width:0;}}
.factor-name{{
  font-size:0.78em;
  font-weight:600;
  color:{TEXT_PRIMARY};
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}}
.factor-what{{
  font-size:0.65em;
  color:{TEXT_MUTED};
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  margin-top:1px;
}}
.factor-score{{
  font-family:"SF Mono",Monaco,Consolas,monospace;
  font-size:0.82em;
  font-weight:700;
  flex:0 0 auto;
  padding:2px 6px;
  border-radius:4px;
}}
.factor-bar{{
  position:absolute;
  bottom:0;left:0;
  height:2px;
  border-radius:0 0 8px 8px;
  transition:width 0.3s ease;
}}

/* ── Dimension node ── */
.dim-node{{
  padding:16px 14px;
  border-radius:12px;
  border:1.5px solid;
  text-align:center;
  transition:all 0.3s ease;
  cursor:pointer;
  position:relative;
}}
.dim-node:hover{{
  transform:scale(1.04);
}}
.dim-abbr{{
  font-size:1.6em;
  font-weight:800;
  line-height:1;
}}
.dim-name{{
  font-size:0.72em;
  margin-top:4px;
  opacity:0.7;
}}
.dim-score-val{{
  font-family:"SF Mono",Monaco,Consolas,monospace;
  font-size:1.15em;
  font-weight:700;
  margin-top:8px;
}}
.dim-meta{{
  display:flex;
  justify-content:center;
  gap:12px;
  margin-top:6px;
  font-size:0.68em;
  opacity:0.6;
}}
.dim-contribution{{
  margin-top:6px;
  font-size:0.72em;
  font-weight:600;
  padding:3px 8px;
  border-radius:4px;
  display:inline-block;
}}

/* ── D-Score node ── */
.d-node{{
  padding:24px 20px;
  border-radius:16px;
  border:2px solid;
  text-align:center;
  transition:all 0.3s ease;
  cursor:pointer;
  min-width:160px;
}}
.d-node:hover{{
  transform:scale(1.05);
}}
.d-node-label{{font-size:0.75em;opacity:0.6;font-weight:600;letter-spacing:1px;}}
.d-node-score{{
  font-family:"SF Mono",Monaco,Consolas,monospace;
  font-size:2.2em;
  font-weight:800;
  line-height:1.1;
  margin-top:6px;
}}
.d-node-rec{{
  font-size:0.9em;
  font-weight:700;
  margin-top:10px;
  padding:4px 12px;
  border-radius:20px;
  display:inline-block;
}}
.d-node-confidence{{
  font-size:0.85em;
  margin-top:8px;
  color:{WARN};
}}
.d-node-sublabel{{
  font-size:0.65em;
  margin-top:4px;
  opacity:0.5;
}}

/* ── Recommendation badge below ── */
.rec-box{{
  padding:12px 16px;
  border-radius:10px;
  text-align:center;
  font-size:0.78em;
  line-height:1.5;
  max-width:180px;
}}

/* ── Tooltip (on hover) ── */
.graph-tooltip{{
  position:fixed;
  z-index:100;
  padding:10px 14px;
  background:rgba(13,14,18,0.95);
  border:1px solid {BORDER};
  border-radius:10px;
  font-size:0.78em;
  line-height:1.5;
  color:{TEXT_SECONDARY};
  max-width:280px;
  pointer-events:none;
  opacity:0;
  transform:translateY(4px);
  transition:opacity 0.2s ease, transform 0.2s ease;
  backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);
  box-shadow:0 8px 24px rgba(0,0,0,0.4);
}}
.graph-tooltip.visible{{
  opacity:1;
  transform:translateY(0);
}}
.graph-tooltip .tt-title{{font-weight:700;color:{TEXT_PRIMARY};margin-bottom:4px;}}
.graph-tooltip .tt-score{{font-family:monospace;font-weight:700;}}
.graph-tooltip .tt-link{{color:{TEXT_MUTED};font-size:0.92em;margin-top:4px;border-top:1px solid {BORDER};padding-top:4px;}}

/* ── Hover dimming ── */
.graph-wrap.hovering .factor-node{{opacity:0.2;transition:opacity 0.25s;}}
.graph-wrap.hovering .dim-node{{opacity:0.2;transition:opacity 0.25s;}}
.graph-wrap.hovering .d-node{{opacity:0.2;transition:opacity 0.25s;}}
.graph-wrap.hovering .factor-node.hl{{opacity:1;}}
.graph-wrap.hovering .dim-node.hl{{opacity:1;}}
.graph-wrap.hovering .d-node.hl{{opacity:1;}}

/* ── Legend ── */
.legend{{
  display:flex;
  gap:20px;
  justify-content:center;
  margin-top:16px;
  padding-top:12px;
  border-top:1px solid {BORDER};
  font-size:0.72em;
  color:{TEXT_MUTED};
  flex-wrap:wrap;
}}
.legend-item{{display:flex;align-items:center;gap:5px;}}
.legend-line{{width:24px;height:3px;border-radius:2px;}}
.legend-dot{{width:8px;height:8px;border-radius:50%;}}
</style>
</head>
<body>

<!-- Tooltip -->
<div class="graph-tooltip" id="tooltip"></div>

<!-- Graph -->
<div class="graph-wrap" id="graphWrap">
  <svg class="graph-svg" id="svg"></svg>
  <div class="graph-body" id="graphBody">
    <!-- Col 1: Factors -->
    <div class="factor-col" id="factorCol"></div>
    <!-- Col 2: Spacer for connections -->
    <div></div>
    <!-- Col 3: Dimensions -->
    <div class="dim-col" id="dimCol"></div>
    <!-- Col 4: Spacer for connections -->
    <div></div>
    <!-- Col 5: Result -->
    <div class="result-col" id="resultCol"></div>
  </div>
</div>

<!-- Legend -->
<div class="legend">
  <div class="legend-item"><div class="legend-line" style="background:{UP};"></div> 正面影响</div>
  <div class="legend-item"><div class="legend-line" style="background:{DOWN};"></div> 负面影响</div>
  <div class="legend-item"><div class="legend-line" style="background:{WARN};"></div> 中性</div>
  <div class="legend-item"><div class="legend-dot" style="border:2px solid {SCORE_MACRO};background:transparent;"></div> 维度节点</div>
  <div class="legend-item">线粗 = 影响程度大</div>
  <div class="legend-item">悬停查看详情</div>
</div>

<script>
// ─── Data ───
const D = {data_json};

// ─── Color helpers ───
function scoreColor(v) {{
  if (v > 0.1) return '{UP}';
  if (v < -0.1) return '{DOWN}';
  return '{WARN}';
}}
function scoreBg(v) {{
  if (v > 0.1) return 'rgba(76,175,80,0.12)';
  if (v < -0.1) return 'rgba(255,107,107,0.12)';
  return 'rgba(245,158,11,0.10)';
}}
function hexToRgba(hex, a) {{
  hex = hex.replace('#','');
  const r = parseInt(hex.substring(0,2),16);
  const g = parseInt(hex.substring(2,4),16);
  const b = parseInt(hex.substring(4,6),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}
function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}

// ─── Build factor column ───
const factorCol = document.getElementById('factorCol');
D.dimensions.forEach((dim, di) => {{
  const group = document.createElement('div');
  group.className = 'factor-group';
  group.innerHTML = `<div class="factor-group-header" style="color:${{dim.color}}">${{dim.abbr}} ${{dim.name}}</div>`;

  dim.factors.forEach((f, fi) => {{
    const sc = scoreColor(f.score);
    const barW = clamp(Math.abs(f.score) / 2.0 * 100, 4, 100);
    const node = document.createElement('div');
    node.className = 'factor-node';
    node.dataset.dim = dim.abbr;
    node.dataset.fi = fi;
    node.id = `f-${{dim.abbr}}-${{fi}}`;
    node.innerHTML = `
      <span class="factor-icon">${{f.icon}}</span>
      <div class="factor-info">
        <div class="factor-name">${{f.name}}</div>
        <div class="factor-what">${{f.what}}</div>
      </div>
      <span class="factor-score" style="color:${{sc}};background:${{scoreBg(f.score)}}">${{f.score > 0 ? '+' : ''}}${{f.score.toFixed(2)}}</span>
      <div class="factor-bar" style="width:${{barW}}%;background:${{sc}};"></div>
    `;
    // Tooltip
    node.addEventListener('mouseenter', (e) => {{
      showTooltip(e, `
        <div class="tt-title">${{f.icon}} ${{f.name}}</div>
        <div>${{f.what}}</div>
        <div class="tt-score" style="color:${{sc}}">得分: ${{f.score > 0 ? '+' : ''}}${{f.score.toFixed(2)}}</div>
        <div class="tt-link">🔗 ${{f.link}}</div>
        ${{f.detail ? '<div style="margin-top:4px;color:{TEXT_MUTED};font-style:italic;">' + f.detail + '</div>' : ''}}
      `);
      highlightFactor(dim.abbr, fi);
    }});
    node.addEventListener('mouseleave', () => {{ hideTooltip(); clearHighlight(); }});
    node.addEventListener('mousemove', moveTooltip);
    group.appendChild(node);
  }});

  factorCol.appendChild(group);
}});

// ─── Build dimension column ───
const dimCol = document.getElementById('dimCol');
D.dimensions.forEach((dim, di) => {{
  const node = document.createElement('div');
  node.className = 'dim-node';
  node.id = `dim-${{dim.abbr}}`;
  node.style.borderColor = hexToRgba(dim.color, 0.4);
  node.style.background = hexToRgba(dim.color, 0.06);

  const contribColor = dim.contribution >= 0 ? '{UP}' : '{DOWN}';

  node.innerHTML = `
    <div class="dim-abbr" style="color:${{dim.color}}">${{dim.abbr}}</div>
    <div class="dim-name">${{dim.name}}</div>
    <div class="dim-score-val" style="color:${{dim.color}}">${{dim.score > 0 ? '+' : ''}}${{dim.score.toFixed(2)}}</div>
    <div class="dim-meta">
      <span>权重 ${{dim.weightPct}}%</span>
      <span>${{dim.label}}</span>
    </div>
    <div class="dim-contribution" style="color:${{contribColor}};background:${{dim.contribution >= 0 ? 'rgba(76,175,80,0.1)' : 'rgba(255,107,107,0.1)'}}">
      贡献 ${{dim.contribution > 0 ? '+' : ''}}${{dim.contribution.toFixed(3)}}
    </div>
  `;

  node.addEventListener('mouseenter', (e) => {{
    showTooltip(e, `
      <div class="tt-title" style="color:${{dim.color}}">${{dim.abbr}} ${{dim.name}}</div>
      <div>${{dim.short}} — ${{dim.sub}}</div>
      <div class="tt-score" style="color:${{dim.color}}">综合得分: ${{dim.score > 0 ? '+' : ''}}${{dim.score.toFixed(2)}}</div>
      <div>权重: ${{dim.weightPct}}% | 贡献: ${{dim.contribution > 0 ? '+' : ''}}${{dim.contribution.toFixed(3)}}</div>
      <div class="tt-link">计算方式: ${{dim.weightPct}}% × ${{dim.score.toFixed(2)}} = ${{dim.contribution.toFixed(3)}}</div>
    `);
    highlightDim(dim.abbr);
  }});
  node.addEventListener('mouseleave', () => {{ hideTooltip(); clearHighlight(); }});
  node.addEventListener('mousemove', moveTooltip);
  dimCol.appendChild(node);
}});

// ─── Build result column ───
const resultCol = document.getElementById('resultCol');
const dColor = D.dColor;
const recBg = D.dScore >= 0.4 ? 'rgba(76,175,80,0.12)' : D.dScore >= -0.2 ? 'rgba(245,158,11,0.10)' : 'rgba(255,107,107,0.12)';
const recBorder = D.dScore >= 0.4 ? '{UP}' : D.dScore >= -0.2 ? '{WARN}' : '{DOWN}';

resultCol.innerHTML = `
  <div class="d-node" id="d-node" style="border-color:${{hexToRgba(dColor, 0.5)}};background:${{hexToRgba(dColor, 0.06)}};">
    <div class="d-node-label">D - SCORE</div>
    <div class="d-node-score" style="color:${{dColor}}">${{D.dScore > 0 ? '+' : ''}}${{D.dScore.toFixed(3)}}</div>
    <div class="d-node-sublabel">${{D.dLabel}}</div>
    <div class="d-node-rec" style="color:${{recBorder}};background:${{recBg}}">${{D.recEmoji}} ${{D.recLabel}}</div>
    <div class="d-node-confidence">${{D.confidenceStars}}</div>
  </div>
  <div class="rec-box" style="background:${{hexToRgba(dColor, 0.05)}};border:1px solid ${{hexToRgba(dColor, 0.15)}};color:{TEXT_MUTED};">
    <div style="font-weight:700;color:${{dColor}};margin-bottom:4px;">${{D.sectorIcon}} ${{D.fundName}}</div>
    <div style="font-size:0.9em;">${{D.regimeIcon}} ${{D.regimeName}}</div>
    <div style="margin-top:6px;font-size:0.88em;">
      D = ${{D.dimensions.map(d => '<span style="color:' + d.color + '">' + d.weightPct + '%×' + (d.score>0?'+':'') + d.score.toFixed(1) + '</span>').join(' + ')}}
    </div>
  </div>
`;

const dNode = document.getElementById('d-node');
dNode.addEventListener('mouseenter', (e) => {{
  showTooltip(e, `
    <div class="tt-title" style="color:${{dColor}}">D-Score 综合决策分</div>
    <div>四维加权求和：M×w + S×w + T×w + F×w</div>
    <div class="tt-score" style="color:${{dColor}}">${{D.dScore > 0 ? '+' : ''}}${{D.dScore.toFixed(3)}}</div>
    <div>操作建议: ${{D.recEmoji}} ${{D.recLabel}}</div>
    <div>置信度: ${{D.confidenceStars}}</div>
  `);
  highlightAll();
}});
dNode.addEventListener('mouseleave', () => {{ hideTooltip(); clearHighlight(); }});
dNode.addEventListener('mousemove', moveTooltip);

// ─── Draw SVG connections ───
function drawConnections() {{
  const svg = document.getElementById('svg');
  const wrap = document.getElementById('graphWrap');
  const wrapRect = wrap.getBoundingClientRect();

  svg.setAttribute('width', wrapRect.width);
  svg.setAttribute('height', wrapRect.height);
  svg.innerHTML = '';  // clear

  // Defs for glow filter
  const defs = document.createElementNS('http://www.w3.org/2000/svg','defs');
  defs.innerHTML = `
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  `;
  svg.appendChild(defs);

  // Factor → Dimension connections
  D.dimensions.forEach((dim) => {{
    const dimEl = document.getElementById('dim-' + dim.abbr);
    if (!dimEl) return;
    const dimRect = dimEl.getBoundingClientRect();
    const dimX = dimRect.left - wrapRect.left;
    const dimY = dimRect.top - wrapRect.top + dimRect.height / 2;

    dim.factors.forEach((f, fi) => {{
      const fEl = document.getElementById('f-' + dim.abbr + '-' + fi);
      if (!fEl) return;
      const fRect = fEl.getBoundingClientRect();
      const fX = fRect.right - wrapRect.left;
      const fY = fRect.top - wrapRect.top + fRect.height / 2;

      const color = scoreColor(f.score);
      const thickness = clamp(Math.abs(f.score) / 2.0 * 4 + 0.8, 0.8, 5);
      const opacity = clamp(Math.abs(f.score) / 2.0 * 0.6 + 0.15, 0.15, 0.75);

      const cpX = (fX + dimX) / 2;
      const d = `M${{fX}},${{fY}} C${{cpX}},${{fY}} ${{cpX}},${{dimY}} ${{dimX}},${{dimY}}`;

      const path = document.createElementNS('http://www.w3.org/2000/svg','path');
      path.setAttribute('d', d);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', color);
      path.setAttribute('stroke-width', thickness);
      path.setAttribute('opacity', opacity);
      path.setAttribute('stroke-linecap', 'round');
      path.classList.add('conn', 'conn-f2d', 'conn-dim-' + dim.abbr, 'conn-f-' + dim.abbr + '-' + fi);
      svg.appendChild(path);
    }});
  }});

  // Dimension → D-Score connections
  const dEl = document.getElementById('d-node');
  if (!dEl) return;
  const dRect = dEl.getBoundingClientRect();
  const dX = dRect.left - wrapRect.left;
  const dCY = dRect.top - wrapRect.top + dRect.height / 2;

  D.dimensions.forEach((dim) => {{
    const dimEl = document.getElementById('dim-' + dim.abbr);
    if (!dimEl) return;
    const dimRect = dimEl.getBoundingClientRect();
    const dimRX = dimRect.right - wrapRect.left;
    const dimCY = dimRect.top - wrapRect.top + dimRect.height / 2;

    const thickness = clamp(dim.weight * 10 + 1, 1.5, 7);
    const opacity = clamp(dim.weight + 0.2, 0.3, 0.85);

    const cpX = (dimRX + dX) / 2;
    const d = `M${{dimRX}},${{dimCY}} C${{cpX}},${{dimCY}} ${{cpX}},${{dCY}} ${{dX}},${{dCY}}`;

    const path = document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', dim.color);
    path.setAttribute('stroke-width', thickness);
    path.setAttribute('opacity', opacity);
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('filter', 'url(#glow)');
    path.classList.add('conn', 'conn-d2d', 'conn-dim-' + dim.abbr);
    svg.appendChild(path);
  }});
}}

// ─── Hover highlight logic ───
const wrap = document.getElementById('graphWrap');

function highlightFactor(dimAbbr, fi) {{
  wrap.classList.add('hovering');
  // Highlight this factor node
  const fNode = document.getElementById('f-' + dimAbbr + '-' + fi);
  if (fNode) fNode.classList.add('hl');
  // Highlight its dimension
  const dimNode = document.getElementById('dim-' + dimAbbr);
  if (dimNode) dimNode.classList.add('hl');
  // Highlight D node
  const dN = document.getElementById('d-node');
  if (dN) dN.classList.add('hl');
  // SVG: highlight relevant connections, dim others
  document.querySelectorAll('.conn').forEach(p => {{
    if (p.classList.contains('conn-f-' + dimAbbr + '-' + fi) ||
        (p.classList.contains('conn-d2d') && p.classList.contains('conn-dim-' + dimAbbr))) {{
      p.style.opacity = '0.9';
      p.style.filter = 'url(#glow)';
    }} else {{
      p.style.opacity = '0.04';
      p.style.filter = 'none';
    }}
  }});
}}

function highlightDim(dimAbbr) {{
  wrap.classList.add('hovering');
  // Highlight all factors in this dimension
  D.dimensions.forEach((dim) => {{
    if (dim.abbr === dimAbbr) {{
      dim.factors.forEach((_, fi) => {{
        const el = document.getElementById('f-' + dimAbbr + '-' + fi);
        if (el) el.classList.add('hl');
      }});
    }}
  }});
  const dimNode = document.getElementById('dim-' + dimAbbr);
  if (dimNode) dimNode.classList.add('hl');
  const dN = document.getElementById('d-node');
  if (dN) dN.classList.add('hl');
  // SVG
  document.querySelectorAll('.conn').forEach(p => {{
    if (p.classList.contains('conn-dim-' + dimAbbr)) {{
      p.style.opacity = '0.9';
      p.style.filter = 'url(#glow)';
    }} else {{
      p.style.opacity = '0.04';
      p.style.filter = 'none';
    }}
  }});
}}

function highlightAll() {{
  wrap.classList.add('hovering');
  document.querySelectorAll('.factor-node,.dim-node,.d-node').forEach(el => el.classList.add('hl'));
  document.querySelectorAll('.conn').forEach(p => {{
    p.style.opacity = '0.8';
    p.style.filter = 'url(#glow)';
  }});
}}

function clearHighlight() {{
  wrap.classList.remove('hovering');
  document.querySelectorAll('.hl').forEach(el => el.classList.remove('hl'));
  // Restore original opacities
  document.querySelectorAll('.conn-f2d').forEach(p => {{
    p.style.filter = 'none';
    // Read original opacity from data or recalculate
  }});
  // Simpler: just redraw
  drawConnections();
}}

// ─── Tooltip ───
const tooltip = document.getElementById('tooltip');
function showTooltip(e, html) {{
  tooltip.innerHTML = html;
  tooltip.classList.add('visible');
  moveTooltip(e);
}}
function moveTooltip(e) {{
  const x = e.clientX + 14;
  const y = e.clientY + 14;
  const tw = tooltip.offsetWidth;
  const th = tooltip.offsetHeight;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  tooltip.style.left = (x + tw > vw - 10 ? x - tw - 28 : x) + 'px';
  tooltip.style.top = (y + th > vh - 10 ? y - th - 28 : y) + 'px';
}}
function hideTooltip() {{
  tooltip.classList.remove('visible');
}}

// ─── Init ───
requestAnimationFrame(() => {{
  requestAnimationFrame(() => {{
    drawConnections();
  }});
}});
// Redraw on resize
window.addEventListener('resize', () => {{ drawConnections(); }});
</script>
</body>
</html>'''
