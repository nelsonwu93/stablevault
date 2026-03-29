"""
基金智能监控系统 - StableVault 主界面
运行方式: streamlit run app.py
v2.4 - run_fundamental=True, NoneType fixes, 2s timeout, CSS via components.html
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    FUNDS, PORTFOLIO_CONFIG, SECTOR_TARGETS,
    MACRO_INDICATORS, CHECKLIST_DIMENSIONS, MACRO_TRANSMISSION,
)
from data.fetcher import (
    get_fund_realtime, get_fund_history, compute_technical_indicators,
    fetch_market_snapshot, assess_fed_stance,
)
from data.db import init_db, save_decision, get_decisions
from engine.advisor import FundAdvisor
from engine.factor_model import (
    detect_regime, score_macro, score_sector, score_fund_micro,
    composite_score, iran_expected_impact, REGIMES, _score_color,
)
from engine.unified_analyzer import (
    analyze_all_funds, summarize_portfolio_status,
)
import contextlib

# ══════════════════════════════════════════════
# 页面基础设置
# ══════════════════════════════════════════════

st.set_page_config(
    page_title="StableVault 基金监控",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化数据库
init_db()

# 全局CSS样式 — StableVault Design System v1.0
from ui.design_tokens import (
    CSS_VARIABLES, CSS_ANIMATIONS, JS_COUNTUP, LOADING_OVERLAY_HTML,
    BRAND, UP, DOWN, WARN, INFO,
    BG_ELEVATED, BG_BASE, BG_CARD,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    BORDER, BRAND_DIM, UP_DIM, DOWN_DIM,
)

# ═══════════════════════════════════════════════════════════════
# CSS 注入 — 通过 components.html 将 <style> 写入 parent <head>
# st.markdown(unsafe_allow_html) 无法可靠渲染 <style> 标签，
# 因此使用 iframe + parent.document.head.appendChild 方式。
# ═══════════════════════════════════════════════════════════════

# 先拼装完整 CSS 字符串 (纯 Python, 无 f-string brace 问题)
_COMPONENT_CSS = """

/* ═══════════════════════════════════════════════════════════════
   GLOBAL RESETS & STREAMLIT OVERRIDES
   ═══════════════════════════════════════════════════════════════ */
html, body {
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-family) !important;
}

/* Hide Streamlit defaults */
#MainMenu { display: none; }
footer { display: none; }
.stDeployButton { display: none; }

/* Streamlit container overrides */
.stApp {
    background: var(--bg-base) !important;
    font-family: var(--font-family) !important;
}

/* Remove default Streamlit padding */
.main > .block-container {
    padding-top: var(--sp-4) !important;
    padding-bottom: var(--sp-4) !important;
    padding-left: var(--sp-6) !important;
    padding-right: var(--sp-6) !important;
    max-width: 100% !important;
}

/* Sidebar styling */
.stSidebar, section[data-testid="stSidebar"] {
    background-color: var(--bg-card) !important;
    border-right: 1px solid var(--border) !important;
}

.stSidebar [data-testid="stSidebarContent"] {
    background-color: var(--bg-card) !important;
}

/* Sidebar nav buttons — SPA style */
.stSidebar .stButton > button {
    background: transparent !important;
    border: none !important;
    border-left: 3px solid transparent !important;
    border-radius: 0 var(--radius-md) var(--radius-md) 0 !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: var(--font-base) !important;
    text-align: left !important;
    padding: var(--sp-3) var(--sp-4) !important;
    transition: all 0.2s ease !important;
    font-family: var(--font-family) !important;
}
.stSidebar .stButton > button:hover {
    background: var(--bg-elevated) !important;
    color: var(--text-primary) !important;
}
/* Active nav button (primary type) */
.stSidebar .stButton > button[kind="primary"],
.stSidebar .stButton > button[data-testid="stBaseButton-primary"] {
    background: var(--brand-dim) !important;
    color: var(--brand) !important;
    border-left-color: var(--brand) !important;
    font-weight: 600 !important;
}

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] {
    gap: var(--sp-2);
    border-bottom: 1px solid var(--border);
    padding: 0 var(--sp-4);
}

.stTabs [data-baseweb="tab"] {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary);
    font-weight: 500;
    padding: var(--sp-3) var(--sp-4);
    transition: all var(--duration-micro) var(--ease-default);
    font-family: var(--font-family);
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: var(--brand);
    border-bottom-color: var(--brand);
}

.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-primary);
}

/* Metrics styling */
[data-testid="stMetric"] {
    background: transparent !important;
    padding: 0 !important;
}

[data-testid="stMetric"] > div:first-child {
    color: var(--text-muted) !important;
    font-size: var(--font-xs) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    font-family: var(--font-family) !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: var(--font-mono) !important;
    color: var(--text-primary) !important;
    font-size: 2em !important;
}

/* Expander styling */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
}

[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: var(--sp-4) !important;
}

/* Data frame styling */
.stDataFrame {
    background: var(--bg-card) !important;
}

.stDataFrame table {
    color: var(--text-primary) !important;
    font-family: var(--font-family) !important;
}

.stDataFrame th {
    background: var(--bg-elevated) !important;
    color: var(--text-secondary) !important;
    font-weight: 600;
    border-bottom: 1px solid var(--border) !important;
}

.stDataFrame td {
    border-bottom: 1px solid var(--border) !important;
}

/* ═══════════════════════════════════════════════════════════════
   HERO SECTION — Primary spotlight area
   ═══════════════════════════════════════════════════════════════ */
.hero-section {
    background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elevated) 100%);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--sp-10) var(--sp-8);
    margin: var(--sp-4) 0;
    box-shadow: var(--shadow-md);
    position: relative;
    overflow: hidden;
}

.hero-value {
    font-family: var(--font-mono);
    font-size: var(--font-2xl);
    font-weight: 700;
    color: var(--text-primary);
    margin: var(--sp-3) 0;
    letter-spacing: -0.01em;
    line-height: 1.2;
}

.hero-label {
    color: var(--text-muted);
    font-size: var(--font-sm);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: var(--sp-2);
    font-weight: 500;
}

/* ═══════════════════════════════════════════════════════════════
   KPI CARDS — Key Performance Indicators
   ═══════════════════════════════════════════════════════════════ */
.kpi-row {
    display: flex;
    gap: var(--sp-4);
    margin: var(--sp-6) 0;
    overflow-x: auto;
    padding: 0;
}

.kpi-card {
    flex: 1;
    min-width: 140px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--sp-4);
    display: flex;
    flex-direction: column;
    gap: var(--sp-2);
    transition: all var(--duration-micro) var(--ease-default);
    position: relative;
}

.kpi-card:hover {
    border-color: var(--border-hover);
    background: var(--bg-elevated);
    box-shadow: var(--shadow-sm);
}

.kpi-label {
    color: var(--text-muted);
    font-size: var(--font-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}

.kpi-value {
    font-family: var(--font-mono);
    font-size: var(--font-lg);
    font-weight: 700;
    color: var(--text-primary);
}

.kpi-delta {
    font-size: var(--font-sm);
    font-weight: 600;
    color: var(--text-secondary);
}

/* ═══════════════════════════════════════════════════════════════
   GLASS CARD — Primary container with subtle elevation
   ═══════════════════════════════════════════════════════════════ */
.glass-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--sp-6);
    margin: var(--sp-4) 0;
    box-shadow: var(--shadow-sm);
    transition: all var(--duration-micro) var(--ease-default);
}

.glass-card:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-md);
}

.glass-card-green {
    border-color: var(--up-glow);
    background: var(--up-dim);
}

.glass-card-red {
    border-color: var(--down-glow);
    background: var(--down-dim);
}

.glass-card-gold {
    border-color: var(--warn-glow);
    background: var(--warn-dim);
}

/* ═══════════════════════════════════════════════════════════════
   STATUS BADGES — Visual status indicators
   ═══════════════════════════════════════════════════════════════ */
.status-badge {
    display: inline-block;
    padding: var(--sp-1) var(--sp-3);
    border-radius: var(--radius-sm);
    font-size: var(--font-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border: 1px solid;
    transition: all var(--duration-micro) var(--ease-default);
}

.badge-buy {
    background: var(--up-dim);
    color: var(--up);
    border-color: var(--up-glow);
}

.badge-buy:hover {
    background: var(--up-glow);
}

.badge-sell {
    background: var(--down-dim);
    color: var(--down);
    border-color: var(--down-glow);
}

.badge-sell:hover {
    background: var(--down-glow);
}

.badge-wait {
    background: var(--warn-dim);
    color: var(--warn);
    border-color: var(--warn-glow);
}

.badge-wait:hover {
    background: var(--warn-glow);
}

/* ═══════════════════════════════════════════════════════════════
   STATUS DOTS — Pulsing indicators
   ═══════════════════════════════════════════════════════════════ */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
    margin-right: var(--sp-2);
    animation: sv-pulse 2s ease-in-out infinite;
}

.status-dot-green {
    background: var(--up);
    box-shadow: 0 0 8px var(--up-glow);
}

.status-dot-red {
    background: var(--down);
    box-shadow: 0 0 8px var(--down-glow);
}

.status-dot-amber {
    background: var(--warn);
    box-shadow: 0 0 8px var(--warn-glow);
}

@keyframes sv-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* ═══════════════════════════════════════════════════════════════
   PROGRESS BARS
   ═══════════════════════════════════════════════════════════════ */
.progress-futuristic {
    width: 100%;
    height: 12px;
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    overflow: hidden;
    border: 1px solid var(--border);
    position: relative;
    margin: var(--sp-4) 0;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--brand), var(--up));
    border-radius: var(--radius-sm);
    transition: width var(--duration-standard) var(--ease-default);
    position: relative;
}

/* ═══════════════════════════════════════════════════════════════
   SIGNAL BAR — Alert/signal rows with left accent
   ═══════════════════════════════════════════════════════════════ */
.signal-bar {
    display: flex;
    align-items: center;
    gap: var(--sp-4);
    padding: var(--sp-3) var(--sp-4);
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    margin: var(--sp-2) 0;
    border-left: 3px solid var(--brand);
    transition: all var(--duration-micro) var(--ease-default);
}

.signal-bar:hover {
    background: var(--brand-dim);
    border-left-color: var(--up);
}

.signal-name {
    flex: 1;
    color: var(--text-secondary);
    font-size: var(--font-base);
    font-weight: 500;
}

.signal-value {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: var(--font-base);
    color: var(--text-primary);
}
/* ═══════════════════════════════════════════════════════════════
   FUND CARD — Individual fund holding cards
   ═══════════════════════════════════════════════════════════════ */
.fund-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--brand);
    border-radius: var(--radius-md);
    padding: var(--sp-5);
    margin: var(--sp-3) 0;
    transition: all var(--duration-micro) var(--ease-default);
    position: relative;
}

.fund-card:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}

.fund-card-profit {
    border-left-color: var(--up);
}

.fund-card-profit:hover {
    box-shadow: 0 4px 12px var(--up-dim);
}

.fund-card-loss {
    border-left-color: var(--down);
}

.fund-card-loss:hover {
    box-shadow: 0 4px 12px var(--down-dim);
}

.fund-card-breakeven {
    border-left-color: var(--warn);
}

.fund-card-breakeven:hover {
    box-shadow: 0 4px 12px var(--warn-dim);
}

/* ═══════════════════════════════════════════════════════════════
   DATA TILE — Compact data display
   ═══════════════════════════════════════════════════════════════ */
.data-tile {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: var(--sp-4);
    text-align: center;
    transition: all var(--duration-micro) var(--ease-default);
}

.data-tile:hover {
    border-color: var(--border-hover);
    background: var(--brand-dim);
}

.data-tile-label {
    color: var(--text-muted);
    font-size: var(--font-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: var(--sp-2);
    font-weight: 600;
}

.data-tile-value {
    font-family: var(--font-mono);
    font-size: var(--font-lg);
    font-weight: 700;
    color: var(--brand);
}

/* ═══════════════════════════════════════════════════════════════
   TYPOGRAPHY — Number and label styles
   ═══════════════════════════════════════════════════════════════ */
.num-xl {
    font-family: var(--font-mono);
    font-size: var(--font-2xl);
    font-weight: 700;
    color: var(--text-primary);
}

.num-lg {
    font-family: var(--font-mono);
    font-size: var(--font-lg);
    font-weight: 700;
    color: var(--text-primary);
}

.num-md {
    font-family: var(--font-mono);
    font-size: var(--font-md);
    font-weight: 600;
    color: var(--text-secondary);
}

.label-dim {
    color: var(--text-muted);
    font-size: var(--font-sm);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}

.label-bright {
    color: var(--text-primary);
    font-weight: 600;
    font-size: var(--font-base);
}

/* ═══════════════════════════════════════════════════════════════
   COLOR UTILITIES — Semantic color classes
   ═══════════════════════════════════════════════════════════════ */
.text-brand { color: var(--brand); }
.text-green { color: var(--up); }
.text-amber { color: var(--warn); }
.text-red { color: var(--down); }
.text-info { color: var(--info); }
.text-dim { color: var(--text-dim); }
.text-muted { color: var(--text-muted); }

/* Legacy aliases */
.text-cyan { color: var(--brand); }

.glow-brand { text-shadow: 0 0 8px var(--brand-glow); }
.glow-green { text-shadow: 0 0 8px var(--up-glow); }
.glow-red { text-shadow: 0 0 8px var(--down-glow); }
.glow-cyan { text-shadow: 0 0 8px var(--brand-glow); }

/* ═══════════════════════════════════════════════════════════════
   GRID LAYOUTS
   ═══════════════════════════════════════════════════════════════ */
.grid-2x4 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: var(--sp-4);
    margin: var(--sp-6) 0;
}

/* ═══════════════════════════════════════════════════════════════
   DIVIDER — Section separator
   ═══════════════════════════════════════════════════════════════ */
.divider-glow {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
    margin: var(--sp-6) 0;
}

/* ═══════════════════════════════════════════════════════════════
   SCORE BAR — Factor / progress bars
   ═══════════════════════════════════════════════════════════════ */
.score-bar {
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    height: 10px;
    overflow: hidden;
    border: 1px solid var(--border);
}

.score-fill {
    height: 100%;
    border-radius: var(--radius-sm);
    background: linear-gradient(90deg, var(--brand), var(--up));
    transition: width var(--duration-standard) var(--ease-default);
}

/* ═══════════════════════════════════════════════════════════════
   RECOMMENDATION CARDS
   ═══════════════════════════════════════════════════════════════ */
.rec-buy {
    background: var(--up-dim);
    border: 1px solid var(--up-glow);
    border-radius: var(--radius-md);
    padding: var(--sp-5) var(--sp-6);
    margin: var(--sp-3) 0;
}

.rec-wait {
    background: var(--warn-dim);
    border: 1px solid var(--warn-glow);
    border-radius: var(--radius-md);
    padding: var(--sp-5) var(--sp-6);
    margin: var(--sp-3) 0;
}

.rec-veto {
    background: var(--down-dim);
    border: 1px solid var(--down-glow);
    border-radius: var(--radius-md);
    padding: var(--sp-5) var(--sp-6);
    margin: var(--sp-3) 0;
}

/* ═══════════════════════════════════════════════════════════════
   FEATURE CARDS
   ═══════════════════════════════════════════════════════════════ */
.ft-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--sp-5) var(--sp-6);
    margin: var(--sp-3) 0;
    box-shadow: var(--shadow-sm);
    transition: all var(--duration-micro) var(--ease-default);
}

.ft-card:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-md);
}

.ft-explainer {
    background: var(--info-dim);
    border: 1px solid var(--info-glow);
    border-radius: var(--radius-sm);
    padding: var(--sp-4) var(--sp-5);
    margin: var(--sp-3) 0;
    font-size: var(--font-base);
    color: var(--text-secondary);
    line-height: 1.5;
}

.ft-scenario-card {
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    padding: var(--sp-4);
    height: 100%;
    border: 1px solid var(--border);
    transition: all var(--duration-micro) var(--ease-default);
}

.ft-scenario-card:hover {
    border-color: var(--border-hover);
    background: var(--brand-dim);
}

/* Legacy compat */
.fund-card-break {
    border-left-color: var(--warn) !important;
}

/* ═══════════════════════════════════════════════════════════════
   WATERFALL ANIMATION — Card entry animation
   ═══════════════════════════════════════════════════════════════ */
@keyframes sv-waterfall {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.sv-animate {
    animation: sv-waterfall var(--duration-standard) var(--ease-decel) forwards;
    opacity: 0;
}

/* Stagger delays for card groups */
.sv-animate:nth-child(1) { animation-delay: 0.05s; }
.sv-animate:nth-child(2) { animation-delay: 0.10s; }
.sv-animate:nth-child(3) { animation-delay: 0.15s; }
.sv-animate:nth-child(4) { animation-delay: 0.20s; }
.sv-animate:nth-child(5) { animation-delay: 0.25s; }
.sv-animate:nth-child(6) { animation-delay: 0.30s; }
.sv-animate:nth-child(7) { animation-delay: 0.35s; }
.sv-animate:nth-child(8) { animation-delay: 0.40s; }

/* ═══════════════════════════════════════════════════════════════
   4D SCORE DIMENSION COLORS
   ═══════════════════════════════════════════════════════════════ */
.dim-macro { color: var(--score-macro); }
.dim-sector { color: var(--score-sector); }
.dim-tech { color: var(--score-tech); }
.dim-fund { color: var(--score-fund); }

.dim-macro-bg { background: var(--score-macro); }
.dim-sector-bg { background: var(--score-sector); }
.dim-tech-bg { background: var(--score-tech); }
.dim-fund-bg { background: var(--score-fund); }
"""

# 拼装完整 CSS — 将 tokens + component styles + animations 合为一个字符串
_FULL_CSS = CSS_VARIABLES + "\n" + _COMPONENT_CSS + "\n" + CSS_ANIMATIONS

# 通过 iframe script 注入到 parent <head> (可靠地绕过 st.markdown 限制)
_CSS_INJECT_HTML = (
    '<script>'
    'var css = document.getElementById("sv-custom-css");'
    'if(!css){'
    '  css = document.createElement("style");'
    '  css.id = "sv-custom-css";'
    '  (window.parent || window).document.head.appendChild(css);'
    '}'
    '</script>'
)
# 使用 components.html 确保 script 执行
import streamlit.components.v1 as _stc
_stc.html(
    f'<style>{_FULL_CSS}</style>'
    '<script>'
    'var pDoc=(window.parent||window).document;'
    'if(!pDoc.getElementById("sv-css")){'
    '  var s=pDoc.createElement("style");s.id="sv-css";'
    '  s.textContent=document.querySelector("style").textContent;'
    '  pDoc.head.appendChild(s);'
    '}'
    '</script>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">',
    height=0,
)


# ══════════════════════════════════════════════
# 缓存数据加载（避免重复请求）
# ══════════════════════════════════════════════

@st.cache_data(ttl=900)  # 15分钟缓存
def load_fund_realtime(fund_code: str):
    return get_fund_realtime(fund_code)

@st.cache_data(ttl=3600)  # 1小时缓存
def load_fund_history(fund_code: str):
    df = get_fund_history(fund_code, page_size=180)
    return df

@st.cache_data(ttl=1800)  # 30分钟缓存
def load_market_snapshot():
    return fetch_market_snapshot(MACRO_INDICATORS)

@st.cache_data(ttl=3600)
def load_technical(fund_code: str):
    df = get_fund_history(fund_code, page_size=180)
    if df.empty:
        return {}
    return compute_technical_indicators(df)


# ══════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════

def color_return(val):
    """数值着色：正红负绿（中国习惯）"""
    from ui.design_tokens import DOWN, UP, TEXT_SECONDARY
    if val is None:
        return f"color:{TEXT_SECONDARY}"
    return f"color:{DOWN}" if val > 0 else f"color:{UP}" if val < 0 else f"color:{TEXT_SECONDARY}"

def format_amount(val):
    if val is None:
        return "—"
    if abs(val) >= 10000:
        return f"{val/10000:.2f}万"
    return f"{val:.2f}"

def rec_color(rec):
    from ui.design_tokens import UP, WARN, DOWN, TEXT_SECONDARY
    mapping = {"BUY": UP, "BUY_SMALL": WARN, "WAIT": TEXT_SECONDARY,
               "VETO": DOWN, "SELL": DOWN, "SELL_PARTIAL": WARN}
    return mapping.get(rec, TEXT_SECONDARY)

def confidence_stars(n):
    return "★" * n + "☆" * (5 - n)


# (render_sidebar removed — replaced by _render_nav_sidebar in main section below)


# ══════════════════════════════════════════════
# Tab 1: 持仓总览
# ══════════════════════════════════════════════

def render_portfolio_tab():
    # ═════ HERO SECTION ═════
    total_target = PORTFOLIO_CONFIG["total_target"]
    current_total = sum(f["current_value"] for f in FUNDS)
    total_return = sum(f["total_return"] for f in FUNDS)
    yesterday_return = sum(f["yesterday_return"] for f in FUNDS)
    total_cost = current_total - total_return
    return_pct = total_return / total_cost * 100 if total_cost > 0 else 0

    hero_html = f'<div class="hero-section sv-wf"><div class="hero-label">📊 组合总市值</div><div class="hero-value" data-countup="{current_total}" data-prefix="¥" data-decimals="0">¥{current_total:,.0f}</div><div style="color:{TEXT_MUTED}; font-size:0.9em; margin-top:8px;">↳ 目标完成度 <span style="color:{BRAND}; font-weight:700;">{current_total/total_target*100:.1f}%</span></div></div>'
    st.markdown(hero_html, unsafe_allow_html=True)

    # ═════ KPI ROW ═════
    kpi_html = '<div class="kpi-row">'
    kpi_html += f'<div class="kpi-card sv-wf sv-card-hover"><div class="kpi-label">昨日收益</div><div class="kpi-value" style="color:{DOWN if yesterday_return >= 0 else UP};" data-countup="{yesterday_return}" data-prefix="¥" data-decimals="0">{"+" if yesterday_return >= 0 else ""}¥{yesterday_return:,.0f}</div><div class="kpi-delta" style="color:{DOWN if yesterday_return/current_total*100 >= 0 else UP};">{yesterday_return/current_total*100:+.3f}%</div></div>'
    kpi_html += f'<div class="kpi-card sv-wf sv-card-hover"><div class="kpi-label">持有总收益</div><div class="kpi-value" style="color:{DOWN if total_return >= 0 else UP};" data-countup="{total_return}" data-prefix="¥" data-decimals="0">{"+" if total_return >= 0 else ""}¥{total_return:,.0f}</div><div class="kpi-delta" style="color:{DOWN if return_pct >= 0 else UP};">{return_pct:+.2f}%</div></div>'
    kpi_html += f'<div class="kpi-card sv-wf sv-card-hover"><div class="kpi-label">待投余额</div><div class="kpi-value" style="color:{WARN};" data-countup="{total_target-current_total}" data-prefix="¥" data-decimals="0">¥{total_target-current_total:,.0f}</div><div class="kpi-delta">{(total_target-current_total)/total_target*100:.1f}%</div></div>'
    kpi_html += f'<div class="kpi-card sv-wf sv-card-hover"><div class="kpi-label">持仓基金数</div><div class="kpi-value" style="color:{INFO};" data-countup="{len(FUNDS)}" data-decimals="0">{len(FUNDS)}</div><div class="kpi-delta">配置完成</div></div>'
    kpi_html += '</div>'
    st.markdown(kpi_html, unsafe_allow_html=True)

    st.divider()

    # 板块分配图（plotly）
    try:
        import plotly.graph_objects as go
        import plotly.express as px

        col_chart, col_table = st.columns([1, 1])

        with col_chart:
            st.markdown("#### 📐 当前板块占比 vs 目标")
            sector_current = {}
            for f in FUNDS:
                s = f["sector"]
                sector_current[s] = sector_current.get(s, 0) + f["current_value"]

            sectors = list(SECTOR_TARGETS.keys())
            current_pcts = [sector_current.get(s, 0) / total_target * 100 for s in sectors]
            target_pcts = [SECTOR_TARGETS[s]["target_pct"] * 100 for s in sectors]
            colors = [SECTOR_TARGETS[s]["color"] for s in sectors]

            fig = go.Figure()
            fig.add_trace(go.Bar(name="当前占比", x=sectors, y=current_pcts,
                                  marker_color=colors, opacity=0.8))
            fig.add_trace(go.Scatter(name="目标占比", x=sectors, y=target_pcts,
                                      mode="markers+lines",
                                      marker=dict(size=10, color="white", symbol="diamond"),
                                      line=dict(dash="dash", color="white", width=1)))
            fig.update_layout(
                height=300, template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=20, b=0),
                legend=dict(orientation="h", y=-0.2),
                yaxis_title="占总目标%",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_chart:
            # 板块差距提示
            for s in sectors:
                cur = sector_current.get(s, 0) / total_target * 100
                tgt = SECTOR_TARGETS[s]["target_pct"] * 100
                gap = tgt - cur
                icon = SECTOR_TARGETS[s].get("color", "")
                emoji = "📉" if gap > 3 else "✅" if abs(gap) <= 3 else "📈"
                if gap > 3:
                    st.caption(f"{emoji} **{s}** 低配 {gap:.1f}%，可补仓 ¥{gap/100*total_target:,.0f}")
                elif gap < -3:
                    st.caption(f"{emoji} **{s}** 超配 {abs(gap):.1f}%，可适当减仓")

    except ImportError:
        st.info("安装 plotly 后可查看图表: pip install plotly")

    st.divider()

    # 每只基金卡片
    st.markdown("#### 🗂️ 各基金明细")
    for f in FUNDS:
        _render_fund_card(f)


def _render_fund_card(f: dict):
    """渲染单只基金卡片"""
    total_ret = f["total_return"]
    yest_ret = f["yesterday_return"]
    cost = f["current_value"] - total_ret
    ret_pct = total_ret / cost * 100 if cost > 0 else 0

    # 状态分类
    if ret_pct >= f["stop_profit"] * 100 * 0.8:
        status = "🟡 接近止盈"
        card_style = "fund-card"
    elif ret_pct <= f["stop_loss"] * 100 * 0.8:
        status = "🔴 接近止损"
        card_style = "fund-card fund-card-loss"
    elif ret_pct > 0:
        status = "🟢 盈利"
        card_style = "fund-card"
    else:
        status = "🔵 微亏"
        card_style = "fund-card fund-card-break"

    with st.expander(
        f"{f['sector_icon']} {f['name']}  |  ¥{f['current_value']:,.2f}  "
        f"|  {status}  |  持有{ret_pct:+.2f}%",
        expanded=False
    ):
        cols = st.columns(4)
        cols[0].metric("持仓市值", f"¥{f['current_value']:,.2f}")
        cols[1].metric("昨日收益",
                       f"¥{yest_ret:+,.2f}",
                       delta=f"{yest_ret/f['current_value']*100:+.2f}%")
        cols[2].metric("持有总收益",
                       f"¥{total_ret:+,.2f}",
                       delta=f"{ret_pct:+.1f}%")
        cols[3].metric("板块", f"{f['sector_icon']} {f['sector']}")

        # 止盈止损进度条
        col_l, col_r = st.columns(2)
        with col_l:
            st.caption(f"止损线: {f['stop_loss']*100:.0f}%  |  当前: {ret_pct:+.1f}%  |  止盈线: {f['stop_profit']*100:.0f}%")
            # 进度条可视化
            min_ret = f["stop_loss"] * 100
            max_ret = f["stop_profit"] * 100
            norm = (ret_pct - min_ret) / (max_ret - min_ret)
            norm = max(0.0, min(1.0, norm))
            color = UP if norm > 0.5 else WARN if norm > 0.3 else DOWN
            st.markdown(
                f'<div class="score-bar"><div class="score-fill" '
                f'style="width:{norm*100:.0f}%; background:{color};"></div></div>',
                unsafe_allow_html=True
            )
        with col_r:
            target_amount = PORTFOLIO_CONFIG["total_target"] * f["target_pct"]
            gap = target_amount - f["current_value"]
            st.caption(f"目标仓位: ¥{target_amount:,.0f}  |  缺口: ¥{gap:+,.0f}")

        # 关注的宏观因子
        drivers = f.get("macro_drivers", [])
        if drivers:
            st.caption(f"📡 关注宏观因子: {' · '.join(drivers)}")

        if f.get("note"):
            st.caption(f"📝 {f['note']}")


# ══════════════════════════════════════════════
# Tab 2: 宏观监控
# ══════════════════════════════════════════════

def render_macro_tab():
    st.markdown('<div class="sv-wf" style="font-size:1.8em; font-weight:700; margin-bottom:8px;">🌍 全球宏观指挥中心</div>', unsafe_allow_html=True)
    st.markdown('<div class="label-dim">实时市场脉动 · 地缘风险评估 · 策略信号同步</div>', unsafe_allow_html=True)

    with st.spinner("正在获取全球市场数据..."):
        snapshot = load_market_snapshot()

    if not snapshot:
        st.error("市场数据获取失败，请检查网络连接后点击刷新")
        return

    global_data = snapshot.get("global", {})
    china_data  = snapshot.get("china", {})
    nb_data     = snapshot.get("northbound", {})
    errors      = snapshot.get("errors", [])

    # ── 数据获取状态 ──
    total_count = len(global_data)
    if errors:
        with st.expander(f"⚠️ {len(errors)} 个数据源获取失败（点击展开查看详情）", expanded=False):
            for err in errors:
                st.caption(f"  · {err}")
            st.caption("数据通过 新浪财经 + 腾讯财经 + 东方财富 + AKShare 四重数据源获取")
    else:
        st.success(f"✅ 全部 {total_count} 个全球指标数据获取成功", icon="✅")

    # ══════════════════════════════════════════
    # 🎯 SECTION 1: Regime 市场状态识别
    # ══════════════════════════════════════════
    regime_name, regime_cfg = detect_regime(snapshot)
    m_result = score_macro(snapshot)
    iran_info = iran_expected_impact()

    wm = regime_cfg["weights"]["macro"]
    ws = regime_cfg["weights"]["sector"]
    wc = regime_cfg["weights"]["micro"]

    # 通俗化 regime 描述
    regime_plain_macro = {
        "外部冲击":   "战争/油价等外部事件主导，投资需重点看全球大环境",
        "放缓期":     "经济增速放慢，选对行业比什么都重要",
        "扩张期":     "经济快速增长，大部分基金都有机会",
        "衰退修复":   "经济最差时期可能过去，政策在发力，适合逐步布局",
        "流动性危机": "全球资金链紧绷，风险极高，应保住现金",
    }
    regime_desc_plain = regime_plain_macro.get(regime_name, regime_cfg['desc'])
    st.markdown(
        f'<div class="sv-wf sv-card-hover" style="background:{regime_cfg["color"]}18; border-left:5px solid {regime_cfg["color"]}; padding:16px 20px; border-radius:10px; margin-bottom:8px;">'
        f'<div style="font-size:1.4em; font-weight:700; color:{regime_cfg["color"]};">{regime_cfg["icon"]} 当前市场环境：{regime_name}</div>'
        f'<div style="color:{TEXT_SECONDARY}; margin-top:6px;">{regime_desc_plain}</div>'
        f'<div style="color:{TEXT_MUTED}; margin-top:8px; font-size:0.88em;">💡 {regime_cfg["signal"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════
    # 🌐 SECTION 2: 全球关键指标（原有）
    # ══════════════════════════════════════════
    st.markdown("#### 🌐 全球关键指标")
    cols = st.columns(4)
    display_keys = [
        ("nasdaq",     "纳斯达克(QQQ)", "🇺🇸"),
        ("nvidia",     "英伟达",        "🖥️"),
        ("usd_cny",    "美元/人民币",   "💱"),
        ("us_10y",     "美国10Y国债",   "📉"),
        ("sp500",      "标普500(SPY)",  "🇺🇸"),
        ("gold",       "黄金(GLD)",     "🥇"),
        ("oil",        "原油(USO)",     "🛢️"),
        ("lithium_etf","锂矿ETF",       "⚡"),
    ]
    for i, (key, label, icon) in enumerate(display_keys):
        d = global_data.get(key, {})
        price  = d.get("price")
        change = d.get("change_pct")
        source = d.get("source", "")
        source_badge = " 🟢" if source in ("sina","tencent","yahoo","stooq","akshare","eastmoney","em_dc") else " 🔴"
        with cols[i % 4]:
            if price is not None:
                delta_str = f"{change:+.2f}%" if change is not None else None
                st.metric(f"{icon} {label}{source_badge}", f"{price:,.2f}{' '+d.get('unit','')}", delta=delta_str, help=f"数据来源: {source}")
            else:
                st.metric(f"{icon} {label} 🔴", "—", help="数据获取失败，请刷新重试")

    st.divider()

    # ══════════════════════════════════════════
    # 📊 SECTION 3: 宏观因子评分雷达
    # ══════════════════════════════════════════
    st.markdown("#### 📊 全球经济环境评估")
    st.caption("从利率、经济、战争、汇率、资金5个维度，综合评估当前全球经济对投资的影响")

    m_score = m_result["score"]
    m_color = _score_color(m_score)
    m_emoji = _score_emoji(m_score)
    m_word = _score_cn_word(m_score)
    factors = m_result["factors"]

    col_score, col_factors = st.columns([1, 2])
    with col_score:
        st.markdown(
            f'<div class="sv-wf" style="text-align:center; padding:20px; background:{BG_ELEVATED}; border-radius:12px; border:2px solid {m_color};">'
            f'<div style="color:{TEXT_MUTED}; font-size:0.85em;">全球经济对投资的影响</div>'
            f'<div style="color:{m_color}; font-size:2.5em; font-weight:700; line-height:1.2;">{m_emoji} {m_word}</div>'
            f'<div style="color:{m_color}; font-size:1.1em; margin-top:4px;">{m_score:+.2f}</div>'
            f'<div style="color:{TEXT_DIM}; font-size:0.75em; margin-top:8px;">-2 = 非常不利 → +2 = 非常有利</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_factors:
        for fname, fdata in factors.items():
            fs = fdata["score"]
            fw = fdata["weight"]
            fc = _score_color(fs)
            bar_fill = int((fs + 2) / 4 * 100)
            plain_name, plain_tip = _plain_factor_name(fname)
            fe = _score_emoji(fs)
            fw_cn = _score_cn_word(fs)
            st.markdown(
                f'<div class="sv-list-item" style="margin-bottom:10px;">'
                f'<div style="display:flex; justify-content:space-between; margin-bottom:3px;">'
                f'<span style="color:{TEXT_SECONDARY}; font-size:0.85em;">{fdata["icon"]} {plain_name}</span>'
                f'<span style="color:{fc}; font-weight:700; font-size:0.85em;">{fe} {fw_cn}</span>'
                f'</div>'
                f'<div style="background:{BORDER}; border-radius:6px; height:10px; position:relative;">'
                f'<div style="position:absolute; left:50%; top:0; bottom:0; width:1px; background:{TEXT_DIM};"></div>'
                f'<div style="height:100%; border-radius:6px; background:{fc}; width:{bar_fill}%;"></div>'
                f'</div>'
                f'<div style="color:{TEXT_DIM}; font-size:0.72em; margin-top:2px;">{plain_tip}</div>'
                f'<div style="color:{TEXT_DIM}; font-size:0.72em;">{fdata["detail"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ══════════════════════════════════════════
    # 🛢️ SECTION 4: 伊朗战争情景分析
    # ══════════════════════════════════════════
    with st.expander("🛢️ 伊朗局势对投资的影响（情景分析）", expanded=True):
        adj_val = iran_info['expected_m_adjustment']
        adj_word = "负面影响较大" if adj_val < -0.3 else "有一定负面影响" if adj_val < 0 else "影响偏正面"
        st.markdown(f"综合评估：伊朗局势目前**{adj_word}**（风险调整值 {adj_val:+.3f}）")

        scen_cols = st.columns(4)
        for idx, s in enumerate(iran_info["scenarios"]):
            col = scen_cols[idx]
            prob_pct = int(s["prob"] * 100)
            adj = s["m_adjustment"]
            adj_color = UP if adj > 0 else DOWN
            is_dominant = s == iran_info["dominant_scenario"]
            border = f"border:2px solid {WARN};" if is_dominant else f"border:1px solid {BORDER};"
            dominant_tag = f'<div style="color:{WARN}; font-size:0.7em; margin-top:4px;">★ 基准情景</div>' if is_dominant else ''
            card_html = (
                f'<div class="sv-wf sv-card-hover" style="background:{BG_ELEVATED}; border-radius:10px; padding:12px; {border}">'
                f'<div style="font-size:0.78em; font-weight:700; color:{TEXT_SECONDARY};">{s["name"]}</div>'
                f'<div style="color:{WARN}; font-size:1.4em; font-weight:700; margin:4px 0;">概率 {prob_pct}%</div>'
                f'<div style="color:{TEXT_MUTED}; font-size:0.72em;">油价 {s["oil_range"]} 美元/桶</div>'
                f'<div style="color:{TEXT_MUTED}; font-size:0.72em;">持续 {s["duration"]}</div>'
                f'<div style="color:{adj_color}; font-weight:700; margin-top:6px; font-size:0.85em;">对投资影响 {adj:+.2f}</div>'
                f'<div style="color:{TEXT_DIM}; font-size:0.7em; margin-top:4px;">{s["desc"]}</div>'
                f'{dominant_tag}'
                f'</div>'
            )
            col.markdown(card_html, unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════
    # 🏭 SECTION 5: 美联储 + 北向 + 国内宏观
    # ══════════════════════════════════════════
    us10y = global_data.get("us_10y", {})
    fed_stance = assess_fed_stance(us10y.get("change_pct"))
    fed_labels = {
        "dovish_strong": ("🟢 资金宽松", UP, "美国国债利率大幅下降 → 全球借贷成本降低 → 更多资金流向股市，有利于投资"),
        "dovish":        ("🟡 偏宽松",   WARN, "美国国债利率小幅下降 → 资金环境略微改善，对股市温和利好"),
        "neutral":       ("⚪ 不松不紧", TEXT_MUTED, "美国国债利率基本没变 → 资金环境平稳，无明显影响"),
        "hawkish":       ("🟠 偏紧张",   WARN, "美国国债利率上升 → 全球借贷变贵 → 部分资金从股市流出，偏不利"),
        "hawkish_strong":("🔴 非常紧张", DOWN, "美国国债利率大幅上升 → 资金大量回流美国 → 对A股和新兴市场很不利"),
        "unknown":       ("❓ 暂无数据", TEXT_MUTED, "当前非美国交易时段或数据源暂不可用，稍后再看"),
    }
    fed_label, fed_color, fed_desc = fed_labels.get(fed_stance, ("❓", TEXT_MUTED, ""))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🏦 全球资金松紧程度")
        st.markdown(f"<span class='sv-wf' style='font-size:1.5em; font-weight:700; color:{fed_color};'>{fed_label}</span>", unsafe_allow_html=True)
        st.caption(fed_desc)
        us10y_val = us10y.get("price")
        if us10y_val:
            tightness = "偏紧" if us10y_val > 4.5 else "适中" if us10y_val > 3.5 else "偏松"
            st.caption(f"美国10年国债利率：**{us10y_val:.2f}%**（{tightness}）")

    with col2:
        st.markdown("#### 📈 外资动向（北向资金近5日）")
        st.caption("北向资金 = 境外投资者买卖A股的资金，流入说明外资看好中国市场")
        total_5d = nb_data.get("5day_total")
        if total_5d is not None:
            nb_color = UP if total_5d > 0 else DOWN
            nb_word = "净流入（外资在买入）" if total_5d > 0 else "净流出（外资在卖出）"
            st.markdown(f"<span class='sv-wf' style='color:{nb_color}; font-size:1.8em; font-weight:700;'>{'+' if total_5d > 0 else ''}{total_5d:.1f}亿元</span>", unsafe_allow_html=True)
            st.caption(f"5个交易日{nb_word}，其中 {nb_data.get('5day_positive_days', 0)} 天为净流入")
        else:
            st.caption("当前非交易时段或周末，北向资金数据暂不可用")

    st.divider()

    st.markdown("#### 🏭 中国经济指标")
    pmi  = china_data.get("pmi", {})
    bond = china_data.get("bond_yield", {})
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**制造业景气度（PMI）**")
        st.caption("PMI是衡量制造业冷热的指标：>50代表扩张（经济热），<50代表收缩（经济冷）")
        if pmi.get("pmi"):
            pv = pmi["pmi"]
            pc = UP if pv >= 50 else DOWN
            pmi_word = "经济在扩张 ↑" if pv >= 50 else "经济在收缩 ↓"
            st.markdown(f"<span style='color:{pc}; font-size:2.2em; font-weight:700;'>{pv}</span> <span style='color:{TEXT_SECONDARY};'>（{pmi_word}）</span>", unsafe_allow_html=True)
            st.caption(f"数据月份: {pmi.get('date', '')} | 上月: {pmi.get('prev_pmi', '')}")
            if pv < 49:
                st.warning(f"PMI={pv}，制造业在收缩，企业利润可能下降，对股票基金不利")
        else:
            st.caption("PMI数据暂时不可用（通常月初发布上月数据）")
    with col2:
        st.markdown("**中美利差**")
        st.caption("中美利差 = 美国国债利率 - 中国国债利率。利差越大，资金越倾向流向美国")
        if bond.get("yield"):
            yld = bond["yield"]
            us10y_v = us10y.get("price") or 4.44
            spread = us10y_v - yld
            spread_word = "利差较大，资金外流压力大" if spread > 2.5 else "利差适中" if spread > 1.5 else "利差较小，压力不大"
            st.markdown(f"<span style='font-size:2.2em; font-weight:700;'>{spread:.2f}%</span> <span style='color:{TEXT_SECONDARY};'>（{spread_word}）</span>", unsafe_allow_html=True)
            st.caption(f"中国10年国债 {yld:.3f}% vs 美国10年国债 {us10y_v:.2f}%")
            if spread > 2.5:
                st.warning(f"利差 {spread:.2f}% 偏高，外资有流出A股的压力")
        else:
            st.caption("国债收益率数据暂时不可用")

    st.divider()

    # ══════════════════════════════════════════
    # 📋 SECTION 6: 各板块因子评分对比
    # ══════════════════════════════════════════
    st.markdown("#### 📋 各板块投资评分")
    st.caption("综合全球经济和行业自身状况，为每个板块打分：越绿越适合投资，越红越需要谨慎")
    sectors = list(SECTOR_TARGETS.keys())
    sector_rows = []
    for sec in sectors:
        s_result = score_sector(sec, snapshot)
        s_s = s_result["score"]
        # 用中性微观分（0）作占位
        comp = composite_score(m_score, s_s, 0.0, regime_name)
        d_s = comp["d_score"]
        rec_emoji = comp["rec_emoji"]
        m_emoji = _score_emoji(m_score)
        s_emoji = _score_emoji(s_s)
        d_emoji = _score_emoji(d_s)
        sector_rows.append({
            "板块": SECTOR_TARGETS[sec].get("desc", sec),
            "全球经济": f"{m_emoji} {_score_cn_word(m_score)}",
            "行业状况": f"{s_emoji} {_score_cn_word(s_s)}",
            "综合判断": f"{d_emoji} {_score_cn_word(d_s)}",
            "操作建议": f"{rec_emoji} {comp['rec_label']}",
        })

    df_sectors = pd.DataFrame(sector_rows)
    st.dataframe(df_sectors, hide_index=True, use_container_width=True)
    st.caption("说明：以上评分综合了全球经济和行业自身因素。具体到某只基金的买卖建议，请到「💡 买卖建议」页面分析。")

    st.divider()

    # ══════════════════════════════════════════
    # 🔗 SECTION 7: 宏观→基金传导对照表（原有）
    # ══════════════════════════════════════════
    with st.expander("🔗 宏观信号 → 持仓基金影响对照表", expanded=False):
        rows = []
        for key, info in MACRO_TRANSMISSION.items():
            rows.append({
                "指标": f"{info['icon']} {info['label']}",
                "影响板块": "、".join(info["affected_sectors"]),
                "影响方向": "📈 正面" if info["impact"] == "positive" else "📉 负面" if info["impact"] == "negative" else "↔️ 中性",
                "影响强度": "⭐⭐⭐" if info["strength"] == "strong" else "⭐⭐" if info["strength"] == "moderate" else "⭐",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════
# Tab 3: 买卖建议（三层因子模型 + Checklist）
# ══════════════════════════════════════════════

# ─── 因子通俗名翻译字典 ───
_FACTOR_PLAIN = {
    "利率周期": ("全球借贷成本", "美国国债利率越高，说明全球资金越紧张，股市越容易跌"),
    "经济周期": ("中国经济冷热", "PMI>50说明制造业在扩张（经济热），<50说明在收缩（经济冷）"),
    "大宗冲击": ("石油涨跌冲击", "油价暴涨会推高通胀、增加企业成本，对股市偏负面"),
    "利差汇率": ("中美资金流向", "中美利率差越大，资金越容易往美国跑，A股承压"),
    "风险偏好": ("市场情绪温度", "投资者愿不愿意冒险买股票——黄金涨+股票跌=避险情绪浓"),
    "利率敏感": ("利率冲击程度", "这个板块受美联储加息/降息影响有多大"),
    "PMI景气":  ("经济景气传导", "中国经济好转时，这个板块能受益多少"),
    "油价影响": ("油价波动影响", "油价大涨对这个板块是利好还是利空"),
    "北向资金": ("外资买卖方向", "外资（北向资金）最近在买入还是卖出这个板块"),
    "地缘风险": ("战争冲突影响", "伊朗、中美等地缘冲突对这个板块的冲击程度"),
    "英伟达信号": ("AI龙头风向标", "英伟达是全球AI指标股，它涨跌直接影响A股AI板块"),
    "债券替代": ("存款vs股息", "国债利率很低时，高分红股票更有吸引力"),
    "持仓状态": ("你赚了还是亏了", "当前持仓的盈亏情况——亏损时补仓更划算，大赚时不宜追高"),
    "RSI":      ("短期买卖强度", "RSI<30说明最近跌太多（超卖，可能反弹），>70说明涨太多（可能回调）"),
    "均线位置": ("中期趋势方向", "价格在60日均线上方=上升趋势，下方=下降趋势"),
    "MACD":     ("动量转向信号", "MACD金叉=趋势转向上涨，死叉=趋势转向下跌"),
    "仓位空间": ("还能买多少", "当前持仓金额离目标还差多少——差得多说明还有加仓空间"),
    # 微观深度因子
    "公司盈利": ("持仓公司赚钱能力", "基金持有的公司利润是否在增长——增长越快，基金越可能涨"),
    "持仓估值": ("持仓公司贵不贵", "PE市盈率越低越便宜，越高越贵——买贵了容易亏"),
    "经理能力": ("基金经理靠不靠谱", "从业年限、历史业绩、管理基金数量——经验越丰富越好"),
    "持仓变动": ("基金经理最近在买什么", "基金经理增减持动作——大幅调仓说明策略可能有变化"),
    "集中度":   ("鸡蛋放了几个篮子", "前几大持仓占比——过于集中风险高，适度分散更安全"),
}

import contextlib

@contextlib.contextmanager
def _noop_ctx():
    """占位上下文管理器"""
    yield


def _plain_factor_name(key: str) -> tuple:
    """返回 (通俗名, 一句话解释)"""
    for k, v in _FACTOR_PLAIN.items():
        if k in key:
            return v
    return (key, "")

def _score_emoji(score: float) -> str:
    if score >= 1.0:  return "🟢"
    if score >= 0.3:  return "🟡"
    if score >= -0.3: return "⚪"
    if score >= -1.0: return "🟠"
    return "🔴"

def _score_cn_word(score: float) -> str:
    if score >= 1.0:  return "利好"
    if score >= 0.3:  return "偏好"
    if score >= -0.3: return "中性"
    if score >= -1.0: return "偏差"
    return "利空"


def _compute_action_amount(fund_cfg, comp, regime_name):
    """计算具体操作金额（元）"""
    rec = comp["recommendation"]
    d   = comp["d_score"]
    target_amount = PORTFOLIO_CONFIG["total_target"] * fund_cfg.get("target_pct", 0.10)
    current       = fund_cfg.get("current_value", 0)
    gap           = target_amount - current
    remaining     = PORTFOLIO_CONFIG.get("remaining_to_invest", 0)
    batches       = max(PORTFOLIO_CONFIG.get("entry_batches", 6), 1)
    per_batch     = remaining / batches  # 每批次基础金额

    if rec == "BUY":
        # 积极加仓：基础批次 × 1.5，但不超过缺口和剩余资金
        amount = min(per_batch * 1.5, gap, remaining)
        return max(round(amount / 100) * 100, 0), "加仓", "买入"
    elif rec == "BUY_SMALL":
        amount = min(per_batch * 0.6, gap * 0.4, remaining)
        return max(round(amount / 100) * 100, 0), "小额加仓", "买入"
    elif rec == "VETO":
        # 减仓：持仓的 20~30%
        sell_pct = 0.25 if d < -1.2 else 0.15
        amount = current * sell_pct
        return max(round(amount / 100) * 100, 0), "减仓", "卖出"
    else:
        return 0, "观望", "不操作"


def _analyze_all_funds(snapshot, regime_name, regime_cfg):
    """分析所有基金，返回分析结果列表（带缓存）"""
    if "all_fund_analysis" in st.session_state:
        return st.session_state["all_fund_analysis"]

    _rw = regime_cfg.get("weights", {"macro": 0.35, "sector": 0.40, "micro": 0.25})
    wm, ws, wc = _rw["macro"], _rw["sector"], _rw["micro"]
    m_result = score_macro(snapshot)
    m_sc = m_result["score"]
    iran_info = iran_expected_impact()

    portfolio = {
        "total_value": sum(f["current_value"] for f in FUNDS),
        "total_cost":  sum(f["current_value"] - f["total_return"] for f in FUNDS),
        "total_target": PORTFOLIO_CONFIG["total_target"],
        "funds": FUNDS,
    }

    results = []
    for fund_cfg in FUNDS:
        tech_data = load_technical(fund_cfg["code"])
        s_result = score_sector(fund_cfg.get("sector", ""), snapshot)
        c_result = score_fund_micro(fund_cfg, tech_data)
        comp = composite_score(m_sc, s_result["score"], c_result["score"], regime_name)
        action_amount, action_word, action_verb = _compute_action_amount(fund_cfg, comp, regime_name)

        advisor = FundAdvisor(CHECKLIST_DIMENSIONS)
        adv_result = advisor.analyze_fund(
            fund_cfg=fund_cfg, market_data=snapshot,
            technical_data=tech_data, portfolio=portfolio,
            trigger_type="macro", trigger_event="自动定期分析",
        )

        results.append({
            "fund": fund_cfg,
            "comp": comp,
            "m_result": m_result,
            "s_result": s_result,
            "c_result": c_result,
            "iran_info": iran_info,
            "advisor_result": adv_result,
            "action_amount": action_amount,
            "action_word": action_word,
            "action_verb": action_verb,
            "regime_name": regime_name,
            "regime_cfg": regime_cfg,
            "wm": wm, "ws": ws, "wc": wc,
        })

    st.session_state["all_fund_analysis"] = results
    return results


def render_recommendation_tab():
    st.markdown('<div class="sv-wf" style="font-size:1.8em; font-weight:700; margin-bottom:8px;">💡 智能决策面板</div>', unsafe_allow_html=True)
    st.markdown('<div class="label-dim">三层因子智能分析 · 实时操作建议 · 风险提示同步</div>', unsafe_allow_html=True)

    # ── 获取数据并分析 ──
    snapshot = load_market_snapshot() or {}
    regime_name, regime_cfg = detect_regime(snapshot)
    _rw = regime_cfg.get("weights", {"macro": 0.35, "sector": 0.40, "micro": 0.25})
    wm, ws, wc = _rw["macro"], _rw["sector"], _rw["micro"]

    regime_plain = {
        "外部冲击":   ("战争/油价等外部冲击主导市场", DOWN, "市场被外部事件主导，投资以防守为主"),
        "放缓期":     ("经济放缓，需精选行业", WARN, "经济增速在放慢，选对行业很重要"),
        "扩张期":     ("经济扩张，积极布局", UP, "经济在增长，大部分基金都有机会"),
        "衰退修复":   ("经济触底回升中", BRAND, "经济最差的时候可能过去了，适合逐步布局"),
        "流动性危机": ("资金紧张，全面防守", DOWN, "市场风险极高，保住现金"),
    }
    r_plain, r_color, r_explain = regime_plain.get(regime_name, ("未知", TEXT_MUTED, ""))

    # ═════ Market Regime Card ═════
    regime_html = f'<div class="glass-card sv-wf sv-card-hover" style="border-color:rgba({int(r_color[1:3],16)},{int(r_color[3:5],16)},{int(r_color[5:7],16)},0.25);"><div style="display:flex; align-items:center; gap:16px;"><div style="font-size:2.2em;">{regime_cfg.get("icon","⚡")}</div><div><div style="color:{r_color}; font-size:1.2em; font-weight:700; margin-bottom:4px;">{r_plain}</div><div style="color:{TEXT_MUTED}; font-size:0.85em;">{r_explain}</div></div></div></div>'
    st.markdown(regime_html, unsafe_allow_html=True)

    # ── 自动分析所有基金 ──
    with st.spinner("正在分析所有基金..."):
        all_results = _analyze_all_funds(snapshot, regime_name, regime_cfg)

    if st.button("🔄 重新分析", use_container_width=False):
        if "all_fund_analysis" in st.session_state:
            del st.session_state["all_fund_analysis"]
        st.rerun()

    # ── 所有基金操作建议总览 ──
    rec_order = {"BUY": 0, "BUY_SMALL": 1, "WAIT": 2, "VETO": 3, "SELL": 4}
    sorted_results = sorted(all_results, key=lambda r: rec_order.get(r["comp"]["recommendation"], 5))

    buy_count = sum(1 for r in all_results if r["comp"]["recommendation"] in ("BUY", "BUY_SMALL"))
    wait_count = sum(1 for r in all_results if r["comp"]["recommendation"] == "WAIT")
    sell_count = sum(1 for r in all_results if r["comp"]["recommendation"] in ("VETO", "SELL"))

    st.markdown("##### 📊 操作建议总览")
    sum_cols = st.columns(4)
    sum_cols[0].metric("🟢 买入", f"{buy_count} 只", help="D分较高，适合加仓的基金")
    sum_cols[1].metric("⚪ 观望", f"{wait_count} 只", help="信号不明确，等待更好时机")
    sum_cols[2].metric("🔴 减仓", f"{sell_count} 只", help="风险较高，建议降低仓位")
    sum_cols[3].metric("📍 时间", datetime.datetime.now().strftime("%H:%M"))

    st.markdown("")

    # ── 每只基金的操作卡片 ──
    for r in sorted_results:
        fund = r["fund"]
        comp = r["comp"]
        rec = comp["recommendation"]
        d = comp["d_score"]
        rec_label = comp["rec_label"]
        rec_emoji = comp["rec_emoji"]
        action_amount = r["action_amount"]
        action_word = r["action_word"]
        action_verb = r["action_verb"]

        rec_colors = {"BUY": UP, "BUY_SMALL": WARN, "WAIT": WARN, "VETO": DOWN, "SELL": DOWN}
        rc = rec_colors.get(rec, TEXT_MUTED)

        m_s = r["m_result"]["score"]
        s_s = r["s_result"]["score"]
        c_s = r["c_result"]["score"]

        # 紧凑的操作卡片
        amount_str = f"¥{action_amount:,.0f}" if action_amount > 0 else "—"
        st.markdown(
            f'<div class="sv-list-item sv-card-hover" style="display:flex; align-items:center; gap:16px; padding:14px 18px; margin:6px 0; background:rgba(255,255,255,0.02); border-left:4px solid {rc}; border-radius:0 10px 10px 0;">'
            f'<div style="min-width:140px;">'
            f'<div style="color:{TEXT_PRIMARY}; font-weight:600;">{fund["sector_icon"]} {fund["name"]}</div>'
            f'<div style="color:{TEXT_DIM}; font-size:0.78em;">持仓 ¥{fund["current_value"]:,.0f}</div>'
            f'</div>'
            f'<div style="min-width:90px; text-align:center;">'
            f'<div style="color:{rc}; font-size:1.2em; font-weight:700;">{rec_emoji} {rec_label}</div>'
            f'</div>'
            f'<div style="min-width:90px; text-align:center;">'
            f'<div style="color:{rc}; font-size:1.1em; font-weight:600;">{action_verb} {amount_str}</div>'
            f'</div>'
            f'<div style="flex:1; display:flex; gap:12px; justify-content:center;">'
            f'<span style="color:{TEXT_MUTED}; font-size:0.78em;">经济{_score_emoji(m_s)}</span>'
            f'<span style="color:{TEXT_MUTED}; font-size:0.78em;">行业{_score_emoji(s_s)}</span>'
            f'<span style="color:{TEXT_MUTED}; font-size:0.78em;">基金{_score_emoji(c_s)}</span>'
            f'</div>'
            f'<div style="min-width:70px; text-align:right;">'
            f'<div style="color:{rc}; font-size:0.9em; font-weight:600;">D {d:+.2f}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ═════════════════════════════════════════
    # NEW: LLM 市场综述 + 风险预警
    # ═════════════════════════════════════════
    try:
        from engine.llm_commentary import generate_market_summary, generate_risk_report, generate_strategy_advice

        market_sum = generate_market_summary(snapshot, regime_name, regime_cfg, all_results)
        risk_rpt = generate_risk_report(snapshot, all_results, regime_name)

        # ── AI 市场综述 ──
        st.markdown("#### 🧠 AI 市场综述")
        sentiment_colors = {"乐观": UP, "谨慎": WARN, "警惕": DOWN}
        s_color = sentiment_colors.get(market_sum["sentiment"], TEXT_MUTED)
        st.markdown(
            f'<div class="glass-card sv-wf" style="border-color:rgba({int(s_color[1:3],16)},{int(s_color[3:5],16)},{int(s_color[5:7],16)},0.25);">'
            f'<div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">'
            f'<span style="font-size:1.5em;">🧠</span>'
            f'<span style="color:{TEXT_PRIMARY}; font-weight:700; font-size:1.1em;">AI每日研判</span>'
            f'<span style="background:{s_color}; color:#000; padding:2px 10px; border-radius:4px; font-size:0.8em; font-weight:700;">{market_sum["sentiment"]}</span>'
            f'<span style="color:{TEXT_DIM}; font-size:0.8em; margin-left:auto;">{market_sum["date"]}</span>'
            f'</div>'
            f'<div style="color:{TEXT_SECONDARY}; font-size:0.9em; line-height:1.6; margin-bottom:10px;">{market_sum["macro_summary"]}</div>'
            f'<div style="color:{TEXT_SECONDARY}; font-size:0.85em; line-height:1.5; border-top:1px solid rgba(255,255,255,0.05); padding-top:8px;">{market_sum["regime_commentary"]}</div>'
            f'{"<div style=&quot;color:" + TEXT_SECONDARY + "; font-size:0.85em; margin-top:8px; border-top:1px solid rgba(255,255,255,0.05); padding-top:8px;&quot;>" + market_sum["portfolio_commentary"] + "</div>" if market_sum["portfolio_commentary"] else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── 风险预警面板 ──
        level_colors = {"正常": UP, "关注": WARN, "预警": DOWN, "危险": DOWN}
        level_icons = {"正常": "✅", "关注": "⚡", "预警": "⚠️", "危险": "🚨"}
        lv_cn = risk_rpt["level_cn"]
        lv_color = level_colors.get(lv_cn, TEXT_MUTED)
        lv_icon = level_icons.get(lv_cn, "❓")

        with st.expander(f"{lv_icon} 风险预警：{lv_cn}（{risk_rpt['total_alerts']}项）", expanded=risk_rpt["level"] in ("warning", "danger")):
            for alert in risk_rpt["alerts"]:
                a_color = {"high": DOWN, "medium": WARN, "low": UP}.get(alert["level"], TEXT_MUTED)
                a_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert["level"], "⚪")
                st.markdown(
                    f'<div class="sv-list-item" style="display:flex; gap:12px; padding:8px 12px; margin:4px 0; border-left:3px solid {a_color}; background:rgba(255,255,255,0.02); border-radius:0 6px 6px 0;">'
                    f'<span>{a_icon}</span>'
                    f'<div><div style="color:{TEXT_PRIMARY}; font-weight:600; font-size:0.9em;">{alert["title"]}</div>'
                    f'<div style="color:{TEXT_MUTED}; font-size:0.8em;">{alert["detail"]}</div></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    except Exception as e:
        st.caption(f"AI分析模块加载中... ({e})")

    st.divider()

    # ═════════════════════════════════════════
    # NEW: 组合优化 (Portfolio Optimization)
    # ═════════════════════════════════════════
    st.markdown("#### 🎯 组合优化引擎")
    st.caption("基于均值-方差理论，结合因子模型观点，计算最优基金配置权重")

    try:
        from engine.portfolio_optimizer import full_portfolio_optimization

        # 收集基金历史和因子分数
        fund_histories = {}
        factor_scores = {}
        for r in all_results:
            code = r["fund"]["code"]
            with st.spinner(f"加载{r['fund']['name']}历史数据...") if len(fund_histories) == 0 else _noop_ctx():
                df_h = load_fund_history(code)
                if not df_h.empty:
                    fund_histories[code] = df_h
            factor_scores[code] = r["comp"]["d_score"]

        opt = full_portfolio_optimization(
            fund_histories, FUNDS, factor_scores,
            total_capital=PORTFOLIO_CONFIG["total_target"],
        )

        if opt["status"] == "ok":
            # 策略选择
            strategy_names = list(opt["strategies"].keys())
            strategy_labels = {k: v["name"] for k, v in opt["strategies"].items()}

            strat_cols = st.columns(len(strategy_names) + 1)
            strat_cols[0].markdown(
                f'<div class="glass-card sv-wf sv-card-hover" style="padding:12px; border-color:rgba(255,255,255,0.1);">'
                f'<div class="label-dim">当前组合</div>'
                f'<div style="color:{TEXT_SECONDARY}; font-size:0.9em; margin-top:4px;">年化 {opt["current_portfolio"]["annual_return"]}%</div>'
                f'<div style="color:{TEXT_SECONDARY}; font-size:0.9em;">波动 {opt["current_portfolio"]["annual_vol"]}%</div>'
                f'<div style="color:{BRAND}; font-weight:700;">夏普 {opt["current_portfolio"]["sharpe"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            for j, skey in enumerate(strategy_names):
                s = opt["strategies"][skey]
                is_rec = s["name"] == opt["recommended_strategy"]
                border = UP if is_rec else "rgba(255,255,255,0.06)"
                badge = f' <span style="background:{UP}; color:#000; padding:1px 6px; border-radius:3px; font-size:0.65em;">推荐</span>' if is_rec else ""
                strat_cols[j+1].markdown(
                    f'<div class="glass-card sv-wf sv-card-hover" style="padding:12px; border-color:{border};">'
                    f'<div class="label-dim">{s["name"]}{badge}</div>'
                    f'<div style="color:{TEXT_SECONDARY}; font-size:0.9em; margin-top:4px;">年化 {s["annual_return"]}%</div>'
                    f'<div style="color:{TEXT_SECONDARY}; font-size:0.9em;">波动 {s["annual_vol"]}%</div>'
                    f'<div style="color:{BRAND}; font-weight:700;">夏普 {s["sharpe"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # 再平衡建议
            st.markdown("##### 🔄 再平衡建议")
            st.caption(f"推荐策略：{opt['recommended_strategy']} — {opt['recommended_reason']}")

            for rb in opt["rebalance"]:
                act = rb["action"]
                act_color = {"加仓": UP, "减仓": DOWN, "持有": TEXT_MUTED}.get(act, TEXT_MUTED)
                act_icon = {"加仓": "📈", "减仓": "📉", "持有": "➡️"}.get(act, "•")
                diff_str = f"¥{abs(rb['diff_amount']):,.0f}" if rb['diff_amount'] != 0 else "—"

                st.markdown(
                    f'<div class="sv-list-item" style="display:flex; align-items:center; gap:14px; padding:10px 16px; margin:4px 0; '
                    f'border-left:3px solid {act_color}; background:rgba(255,255,255,0.02); border-radius:0 8px 8px 0;">'
                    f'<span style="min-width:140px; color:{TEXT_PRIMARY}; font-weight:600;">{rb["name"]}</span>'
                    f'<span style="min-width:60px; color:{TEXT_MUTED}; font-size:0.85em;">当前 {rb["current_weight"]}%</span>'
                    f'<span style="color:rgba(255,255,255,0.2);">→</span>'
                    f'<span style="min-width:60px; color:{BRAND}; font-weight:600;">{rb["optimal_weight"]}%</span>'
                    f'<span style="min-width:80px; color:{act_color}; font-weight:700;">{act_icon} {act} {diff_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # AI 策略总结
            try:
                strategy_text = generate_strategy_advice(regime_name, opt, risk_rpt, all_results)
                st.markdown("##### 📝 AI 策略总结")
                st.markdown(
                    f'<div style="background:rgba({int(BRAND[1:3],16)},{int(BRAND[3:5],16)},{int(BRAND[5:7],16)},0.04); border:1px solid rgba({int(BRAND[1:3],16)},{int(BRAND[3:5],16)},{int(BRAND[5:7],16)},0.15); '
                    f'border-radius:10px; padding:16px; color:{TEXT_SECONDARY}; font-size:0.9em; line-height:1.7; white-space:pre-wrap;">'
                    f'{strategy_text}</div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                pass

        else:
            st.info(opt.get("message", "组合优化数据不足"))

    except Exception as e:
        st.caption(f"组合优化模块加载中... ({e})")

    st.divider()

    # ── 点击查看单只基金详细分析 ──
    st.markdown("#### 🔍 查看单只基金详细分析")
    fund_names = {f["code"]: f["name"] for f in FUNDS}
    selected_code = st.selectbox(
        "选择基金查看详情",
        options=[f["code"] for f in FUNDS],
        format_func=lambda c: f"{next(f['sector_icon'] for f in FUNDS if f['code']==c)} {fund_names[c]}",
        key="rec_detail_selector",
    )

    # 找到对应分析结果
    selected_r = next((r for r in all_results if r["fund"]["code"] == selected_code), None)
    if selected_r:
        factor_data = {
            "regime_name": selected_r["regime_name"],
            "regime_cfg": selected_r["regime_cfg"],
            "m_result": selected_r["m_result"],
            "s_result": selected_r["s_result"],
            "c_result": selected_r["c_result"],
            "comp": selected_r["comp"],
            "iran_info": selected_r["iran_info"],
            "fund": selected_r["fund"],
            "wm": selected_r["wm"], "ws": selected_r["ws"], "wc": selected_r["wc"],
        }
        _render_full_decision(selected_r["advisor_result"], factor_data)


def _render_full_decision(result: dict, factor: dict = None):
    """渲染完整决策报告 — 小白友好版（扁平HTML，避免DOM错误）"""
    st.divider()
    chain     = result.get("chain", {})
    checklist = result.get("checklist", {})
    final     = chain.get("final_decision", {})

    if not factor:
        st.warning("因子模型数据未加载，请重新运行分析")
        return

    comp        = factor["comp"]
    rec         = comp["recommendation"]
    d           = comp["d_score"]
    rec_label   = comp["rec_label"]
    rec_emoji   = comp["rec_emoji"]
    m_result    = factor["m_result"]
    s_result    = factor["s_result"]
    c_result    = factor["c_result"]
    regime_name = factor["regime_name"]
    wm = factor.get("wm", 0.35)
    ws = factor.get("ws", 0.35)
    wc = factor.get("wc", 0.30)
    m_s = m_result["score"]
    s_s = s_result["score"]
    c_s = c_result["score"]
    fund_cfg  = factor["fund"]
    fund_name = fund_cfg.get("name", result.get("fund_name", ""))
    sector    = fund_cfg.get("sector", "")

    # 计算具体操作金额
    action_amount, action_word, action_verb = _compute_action_amount(fund_cfg, comp, regime_name)

    # ═════════════════════════════════════════════
    # SECTION 1: 明确操作建议（用原生Streamlit组件，避免复杂HTML）
    # ═════════════════════════════════════════════
    rec_c = {"BUY": UP, "BUY_SMALL": WARN, "WAIT": WARN, "VETO": DOWN, "SELL": DOWN}.get(rec, TEXT_MUTED)

    if rec == "BUY":
        action_desc = f"当前全球经济和行业面都支持加仓，建议买入 ¥{action_amount:,.0f}"
        action_reason = "全球经济、行业状况、基金自身三个维度都偏正面"
    elif rec == "BUY_SMALL":
        action_desc = f"当前环境整体偏正面但有不确定性，建议小额买入 ¥{action_amount:,.0f}"
        action_reason = "大方向还行，但有些指标不够理想，先小额试探"
    elif rec == "VETO":
        action_desc = f"当前风险较高，建议卖出 ¥{action_amount:,.0f} 降低仓位"
        action_reason = "多个维度发出警告信号，应该先保住本金"
    else:
        action_desc = "当前信号不够明确，建议不操作，继续观望"
        action_reason = "利好和利空因素相互抵消，等待更清晰的信号"

    target_val = PORTFOLIO_CONFIG["total_target"] * fund_cfg.get("target_pct", 0.10)
    current_val = fund_cfg.get("current_value", 0)
    gap_val = target_val - current_val

    # 用简单HTML + Streamlit原生组件代替深嵌套
    st.markdown(f"### {rec_emoji} {fund_name}：{rec_label}")
    st.markdown(f"<p style='color:{rec_c}; font-size:1.2em; font-weight:600;'>{action_desc}</p>", unsafe_allow_html=True)
    st.caption(action_reason)

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("当前持仓", f"¥{current_val:,.0f}")
    mc2.metric("目标金额", f"¥{target_val:,.0f}")
    mc3.metric("距目标差距", f"¥{gap_val:,.0f}")
    mc4.metric(f"建议{action_verb}金额", f"¥{action_amount:,.0f}")

    st.markdown("")

    # ═════════════════════════════════════════════
    # SECTION 2: 决策是怎么来的？——可视化流程图
    # ═════════════════════════════════════════════
    st.markdown("#### 📊 这个建议是怎么得出的？")
    st.markdown(
        '<div class="ft-explainer">'
        '系统从三个角度给这只基金打分：<b>全球经济环境</b>（利率、油价、战争等）、'
        '<b>所在行业状况</b>（这个板块受经济影响多大）、<b>基金自身状态</b>（你的盈亏、技术指标等），'
        '然后加权汇总得到一个综合评分，评分越高说明越值得买入。'
        '</div>',
        unsafe_allow_html=True,
    )

    # 流程图用 Streamlit columns 替代深嵌套HTML
    m_e = _score_emoji(m_s)
    s_e = _score_emoji(s_s)
    c_e = _score_emoji(c_s)
    d_color = _score_color(d)

    fc1, fa1, fc2, fa2, fc3, fa3, fc4 = st.columns([3, 1, 3, 1, 3, 1, 3])
    fc1.markdown(f"<div class='sv-wf' style='text-align:center; padding:10px; background:rgba({int(WARN[1:3],16)},{int(WARN[3:5],16)},{int(WARN[5:7],16)},0.06); border:1px solid rgba({int(WARN[1:3],16)},{int(WARN[3:5],16)},{int(WARN[5:7],16)},0.2); border-radius:10px;'><div style='font-size:0.75em; color:{WARN};'>全球经济</div><div style='font-size:1.4em; font-weight:700; color:{_score_color(m_s)};'>{m_e} {_score_cn_word(m_s)}</div></div>", unsafe_allow_html=True)
    fa1.markdown("<div style='text-align:center; padding:16px 0; color:rgba(255,255,255,0.2); font-size:1.5em;'>+</div>", unsafe_allow_html=True)
    fc2.markdown(f"<div class='sv-wf' style='text-align:center; padding:10px; background:rgba({int(INFO[1:3],16)},{int(INFO[3:5],16)},{int(INFO[5:7],16)},0.06); border:1px solid rgba({int(INFO[1:3],16)},{int(INFO[3:5],16)},{int(INFO[5:7],16)},0.2); border-radius:10px;'><div style='font-size:0.75em; color:{INFO};'>{sector}行业</div><div style='font-size:1.4em; font-weight:700; color:{_score_color(s_s)};'>{s_e} {_score_cn_word(s_s)}</div></div>", unsafe_allow_html=True)
    fa2.markdown("<div style='text-align:center; padding:16px 0; color:rgba(255,255,255,0.2); font-size:1.5em;'>+</div>", unsafe_allow_html=True)
    fc3.markdown(f"<div class='sv-wf' style='text-align:center; padding:10px; background:rgba(192,132,252,0.06); border:1px solid rgba(192,132,252,0.2); border-radius:10px;'><div style='font-size:0.75em; color:#C084FC;'>基金状态</div><div style='font-size:1.4em; font-weight:700; color:{_score_color(c_s)};'>{c_e} {_score_cn_word(c_s)}</div></div>", unsafe_allow_html=True)
    fa3.markdown(f"<div style='text-align:center; padding:16px 0; color:rgba(255,255,255,0.2); font-size:1.5em;'>&#10132;</div>", unsafe_allow_html=True)
    fc4.markdown(f"<div class='sv-wf' style='text-align:center; padding:10px; background:rgba(255,255,255,0.06); border:2px solid {d_color}; border-radius:10px;'><div style='font-size:0.75em; color:{TEXT_SECONDARY};'>综合结果</div><div style='font-size:1.4em; font-weight:700; color:{d_color};'>{rec_emoji} {rec_label}</div></div>", unsafe_allow_html=True)

    # 仪表盘 — 分两个简单HTML块
    gauge_pct = max(0, min(100, (d + 2) / 4 * 100))
    st.markdown(f"<div style='display:flex; justify-content:space-between; font-size:0.75em; color:{TEXT_DIM}; max-width:600px; margin:16px auto 4px;'><span>减仓</span><span>观望</span><span>加仓</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='ft-gauge' style='max-width:600px; margin:0 auto;'><div class='ft-gauge-marker' style='left:{gauge_pct}%;'></div></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:center; margin-top:8px;'><span style='color:{d_color}; font-size:1.3em; font-weight:700;'>综合评分 {d:+.2f}</span> <span style='color:{TEXT_DIM}; font-size:0.85em;'>（满分 +2.0，越高越适合买入）</span></div>", unsafe_allow_html=True)

    st.markdown("")

    # ═════════════════════════════════════════════
    # SECTION 3: 三个维度具体分析（通俗版）
    # ═════════════════════════════════════════════
    st.markdown("#### 🔍 三个维度的详细分析")

    col_m, col_s, col_c = st.columns(3)

    # ─── 维度1：全球经济 ───
    with col_m:
        m_c = _score_color(m_s)
        weight_pct = int(wm * 100)
        st.markdown(f"**🌍 全球经济环境** · 占比{weight_pct}%")
        st.markdown(f"<span style='font-size:1.8em; font-weight:700; color:{m_c};'>{m_e} {_score_cn_word(m_s)}</span>", unsafe_allow_html=True)

        m_factors = m_result.get("factors", {})
        for fname, fdata in m_factors.items():
            sc = fdata["score"]
            detail = fdata.get("detail", "")
            icon = fdata.get("icon", "")
            plain_name, plain_tip = _plain_factor_name(fname)
            fc = _score_color(sc)
            st.markdown(f"<div class='sv-list-item' style='padding:6px 10px; margin:3px 0; border-left:3px solid {fc}; background:rgba(255,255,255,0.02); border-radius:0 6px 6px 0;'><b style='color:{TEXT_PRIMARY};'>{icon} {plain_name}</b> <span style='color:{fc}; float:right;'>{_score_emoji(sc)} {_score_cn_word(sc)}</span><br/><span style='color:{TEXT_DIM}; font-size:0.78em;'>{plain_tip}</span><br/><span style='color:{TEXT_MUTED}; font-size:0.75em;'>当前：{detail}</span></div>", unsafe_allow_html=True)

        # 伊朗风险
        iran_info = factor.get("iran_info", {})
        if iran_info:
            st.markdown(f"<div style='padding:10px; margin-top:8px; border:1px solid rgba({int(DOWN[1:3],16)},{int(DOWN[3:5],16)},{int(DOWN[5:7],16)},0.3); border-radius:8px; background:rgba({int(DOWN[1:3],16)},{int(DOWN[3:5],16)},{int(DOWN[5:7],16)},0.04);'><b style='color:{DOWN};'>🇮🇷 伊朗战争风险</b><br/><span style='color:{TEXT_MUTED}; font-size:0.82em;'>战争可能推高油价、引发全球避险，预计对投资环境产生负面影响</span></div>", unsafe_allow_html=True)

    # ─── 维度2：行业状况 ───
    with col_s:
        s_c = _score_color(s_s)
        weight_pct_s = int(ws * 100)
        st.markdown(f"**🏭 {sector}板块** · 占比{weight_pct_s}%")
        st.markdown(f"<span style='font-size:1.8em; font-weight:700; color:{s_c};'>{s_e} {_score_cn_word(s_s)}</span>", unsafe_allow_html=True)

        s_components = s_result.get("components", {})
        for cname, cval in s_components.items():
            fc = _score_color(cval)
            plain_name, plain_tip = _plain_factor_name(cname)
            st.markdown(f"<div class='sv-list-item' style='padding:6px 10px; margin:3px 0; border-left:3px solid {fc}; background:rgba(255,255,255,0.02); border-radius:0 6px 6px 0;'><b style='color:{TEXT_PRIMARY};'>{plain_name}</b> <span style='color:{fc}; float:right;'>{_score_emoji(cval)} {_score_cn_word(cval)}</span><br/><span style='color:{TEXT_DIM}; font-size:0.78em;'>{plain_tip}</span></div>", unsafe_allow_html=True)

    # ─── 维度3：基金自身 ───
    with col_c:
        c_c = _score_color(c_s)
        weight_pct_c = int(wc * 100)
        st.markdown(f"**📈 这只基金本身** · 占比{weight_pct_c}%")
        st.markdown(f"<span style='font-size:1.8em; font-weight:700; color:{c_c};'>{c_e} {_score_cn_word(c_s)}</span>", unsafe_allow_html=True)

        c_components = c_result.get("components", {})
        for cname, cval in c_components.items():
            fc = _score_color(cval)
            plain_name, plain_tip = _plain_factor_name(cname)
            st.markdown(f"<div class='sv-list-item' style='padding:6px 10px; margin:3px 0; border-left:3px solid {fc}; background:rgba(255,255,255,0.02); border-radius:0 6px 6px 0;'><b style='color:{TEXT_PRIMARY};'>{plain_name}</b> <span style='color:{fc}; float:right;'>{_score_emoji(cval)} {_score_cn_word(cval)}</span><br/><span style='color:{TEXT_DIM}; font-size:0.78em;'>{plain_tip}</span></div>", unsafe_allow_html=True)

    # ─── 微观深度分析补充 ───
    with st.expander("🔬 持仓公司经营分析 & 基金经理评估（点击展开）", expanded=False):
        try:
            from engine.micro_analysis import full_micro_analysis
            with st.spinner("正在获取持仓公司基本面数据..."):
                micro = full_micro_analysis(fund_cfg["code"])

            micro_score = micro.get("composite_micro_score", 0)
            micro_rec = micro.get("recommendation", "")
            ms_clr = _score_color(micro_score)

            st.markdown(f"**微观综合评分：** <span style='color:{ms_clr}; font-size:1.2em; font-weight:700;'>{_score_emoji(micro_score)} {_score_cn_word(micro_score)} ({micro_score:+.1f})</span>", unsafe_allow_html=True)
            st.caption(micro_rec)

            # 持仓公司概况
            ha = micro.get("holdings_analysis", {})
            holdings_list = ha.get("holdings", [])
            if holdings_list:
                st.markdown("**前十大持仓公司：**")
                for h in holdings_list[:8]:
                    pe_str = f"PE {h['pe']:.0f}" if h.get("pe") else "PE —"
                    gw = h.get("growth_word", "—")
                    val = h.get("valuation", "")
                    gc = UP if h.get("growth_score", 0) > 0 else DOWN if h.get("growth_score", 0) < 0 else TEXT_MUTED
                    vc = UP if val in ("偏低","合理") else WARN if val == "适中偏高" else DOWN
                    st.markdown(
                        f'<div style="display:flex; gap:8px; padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.03); font-size:0.82em;">'
                        f'<span style="color:{TEXT_PRIMARY}; width:80px;">{h["stock_name"]}</span>'
                        f'<span style="color:{TEXT_DIM}; width:45px;">{h["hold_pct"]:.1f}%</span>'
                        f'<span style="color:{vc}; width:65px;">{pe_str}</span>'
                        f'<span style="color:{gc};">{gw}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                avg_pe = ha.get("avg_pe")
                if avg_pe:
                    st.caption(f"加权平均PE: {avg_pe:.0f}倍 | 集中度: {ha.get('concentration_risk','—')} | 前3大占比: {ha.get('top3_pct',0):.1f}%")

            # 持仓变动
            changes = micro.get("position_changes", {})
            if changes.get("changes"):
                st.markdown(f"**持仓变动：** {changes.get('summary', '')}")

            # 基金经理
            mgr = micro.get("manager_analysis", {})
            if mgr.get("manager") != "未知":
                st.markdown(f"**基金经理：** {mgr.get('summary', '')}")

            # 风险提示
            risks = micro.get("risks", [])
            if risks:
                for r in risks:
                    st.warning(r)

        except Exception as e:
            st.caption(f"微观分析模块加载中... ({e})")

    st.divider()

    # ═════════════════════════════════════════════
    # SECTION 4: 什么情况下会改变建议？（通俗版）
    # ═════════════════════════════════════════════
    st.markdown("#### 💡 什么情况下建议会改变？")

    if rec in ("WAIT", "BUY_SMALL"):
        st.markdown(
            '<div class="ft-explainer">'
            '<b>如果以下情况发生，会转为「积极加仓」：</b><br/>'
            '- 美联储宣布降息，全球资金变宽松，股市更有吸引力<br/>'
            '- 中国PMI持续回升到52以上，经济在复苏，企业利润改善<br/>'
            '- 伊朗局势缓和，油价回落，全球避险情绪降温'
            '</div>',
            unsafe_allow_html=True,
        )
    if rec in ("WAIT", "BUY_SMALL", "BUY"):
        st.markdown(
            f'<div class="ft-explainer" style="border-color:rgba({int(DOWN[1:3],16)},{int(DOWN[3:5],16)},{int(DOWN[5:7],16)},0.25); background:rgba({int(DOWN[1:3],16)},{int(DOWN[3:5],16)},{int(DOWN[5:7],16)},0.04);">'
            f'<b style="color:{DOWN};">如果以下情况发生，需要紧急减仓：</b><br/>'
            '- 伊朗战争全面升级、油价突破120美元，全球经济衰退风险大增<br/>'
            '- 中国PMI跌破47，经济深度收缩，企业利润大幅下降<br/>'
            '- 美联储意外大幅加息，全球资金急剧收紧'
            '</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ═════════════════════════════════════════════
    # SECTION 5: Checklist 辅助验证（折叠面板）
    # ═════════════════════════════════════════════
    with st.expander("📋 详细 Checklist 核查清单（高级 · 点击展开）", expanded=False):
        if checklist.get("veto_triggered"):
            st.error(f"🚨 一票否决触发！{checklist.get('veto_reason', '')}")

        score = checklist.get("score", 0)
        score_clr = UP if score >= 70 else WARN if score >= 40 else DOWN
        st.markdown(f"**综合得分：** <span style='color:{score_clr}; font-size:1.2em; font-weight:700;'>{score}/100</span>", unsafe_allow_html=True)
        st.progress(score / 100)

        dim_scores = checklist.get("dimension_scores", {})
        if dim_scores:
            dim_cols = st.columns(min(len(dim_scores), 5))
            for i, (dim, s) in enumerate(dim_scores.items()):
                pct = s.get("pct", 0)
                dim_cols[i % 5].metric(dim, f"{pct:.0f}%", f"{s['earned']}/{s['max']}分")

        items = checklist.get("items", [])
        for item in items:
            passed  = item["passed"]
            is_veto = item.get("is_veto", False)
            icon    = "🚨" if (is_veto and not passed) else "✅" if passed else "❌"
            veto_label = " [一票否决项]" if is_veto else ""
            with st.expander(f"{icon} [{item['dimension']}] {item['name']}{veto_label} — {item['score']}/{item['weight']}分", expanded=not passed):
                st.caption(item["detail"])

    # ═════════════════════════════════════════════
    # SECTION 6: 传导链路（折叠面板）
    # ═════════════════════════════════════════════
    transmission = chain.get("transmission", [])
    if transmission:
        with st.expander("🔗 详细推理链路（高级 · 点击展开）", expanded=False):
            for i, step in enumerate(transmission):
                st.markdown(f"**Step {i+1}：** {step}")

    st.divider()

    # ═════════════════════════════════════════════
    # SECTION 7: 风险提示
    # ═════════════════════════════════════════════
    st.markdown("#### ⚠️ 风险提示")
    warnings = chain.get("risk_warnings", [])
    has_warnings = False
    if warnings:
        for w in warnings:
            st.warning(w)
        has_warnings = True

    iran_adj = factor["iran_info"].get("expected_m_adjustment", 0)
    if iran_adj < -0.4:
        st.warning("🇮🇷 伊朗战争风险较高 — 如果战争升级、油价冲破120美元，所有基金可能面临较大回撤。建议此时先降低总仓位到目标的50%，等局势明朗再加回来。")
        has_warnings = True
    if m_s < -0.5:
        st.warning(f"📉 全球经济环境偏差 — 当前处于「{regime_name}」阶段，不建议大幅加仓，控制好总仓位，等待经济好转信号（如PMI回升到50以上）。")
        has_warnings = True
    if rec in ("WAIT", "VETO") and not has_warnings:
        st.info("💡 当前不适合操作。建议关注以下信号：PMI是否回升到50以上、美国国债利率是否回落、外资是否转为净流入。出现这些信号时可以重新分析。")


# ══════════════════════════════════════════════
# Tab 4: 决策记录
# ══════════════════════════════════════════════

def render_history_tab():
    st.markdown("### 📁 决策记录 — 可追溯、可复盘")
    st.caption("所有历史分析记录均保存在本地，你可以记录实际操作和结果用于复盘")

    decisions = get_decisions(limit=50)

    if not decisions:
        st.info("暂无决策记录。在「买卖建议」页面运行分析后，记录会自动保存到这里。")
        return

    # 汇总统计
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总记录数", len(decisions))
    buy_count = sum(1 for d in decisions if d["recommendation"] in ("BUY", "BUY_SMALL"))
    col2.metric("买入建议", buy_count)
    wait_count = sum(1 for d in decisions if d["recommendation"] == "WAIT")
    col3.metric("观望建议", wait_count)
    avg_score = sum(d.get("checklist_score", 0) or 0 for d in decisions) / len(decisions)
    col4.metric("平均评分", f"{avg_score:.1f}/100")

    st.divider()

    # 记录列表
    for d in decisions:
        rec = d.get("recommendation", "WAIT")
        rec_emoji = {"BUY": "✅", "BUY_SMALL": "⚠️", "WAIT": "⏸️",
                     "VETO": "🚨", "SELL": "🔴"}.get(rec, "❓")
        score = d.get("checklist_score", 0) or 0
        created = d.get("created_at", "")[:16].replace("T", " ")

        with st.expander(
            f"{rec_emoji} {created}  |  {d['fund_name']}  |  {rec}  |  {d.get('trigger_event','')[:30]}  |  评分:{score:.0f}",
            expanded=False
        ):
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f"**基金：** {d['fund_name']} ({d['fund_code']})")
                st.markdown(f"**触发：** [{d.get('trigger_type','')}] {d.get('trigger_event','')}")
                st.markdown(f"**建议：** {rec_emoji} {rec}  |  建议金额：¥{d.get('suggested_amount',0):,.0f}")
                conf = int(d.get('confidence') or 0)
                st.markdown(f"**置信度：** {'★' * conf}{'☆' * (5 - conf)}")

            with col2:
                # 用户实际操作填写
                st.markdown("**记录实际操作（用于复盘）**")
                action = st.selectbox("实际操作", ["未操作", "买入", "卖出", "观望"],
                                       key=f"action_{d['id']}")
                amount = st.number_input("操作金额(元)", min_value=0.0, value=0.0,
                                          key=f"amount_{d['id']}")
                if st.button("保存操作记录", key=f"save_{d['id']}"):
                    from data.db import update_user_action
                    update_user_action(d["id"], action, amount, datetime.date.today().isoformat())
                    st.success("已保存！")

            # 决策链路回顾
            chain_steps = d.get("decision_chain", [])
            if chain_steps:
                st.markdown("**决策链路回顾：**")
                for step in chain_steps:
                    st.caption(f"  → {step}")

            # Checklist摘要
            st.markdown(f"**Checklist评分：** {score:.0f}/100")
            reasoning = d.get("reasoning", "")
            if reasoning:
                st.caption(reasoning[:300] + ("..." if len(reasoning) > 300 else ""))


# ══════════════════════════════════════════════
# 主程序入口
# ══════════════════════════════════════════════

# ══════════════════════════════════════════════
# 统一分析缓存
# ══════════════════════════════════════════════

@st.cache_data(ttl=900)
def _run_unified_analysis(run_fundamental: bool = True):
    """运行统一决策引擎，返回 (reports, summary, market_data, regime_name, regime_cfg)

    yfinance 全球市场数据 (~2s) + 基本面缓存兜底 → 总体 <15s
    """
    # 加载市场数据
    market_data = load_market_snapshot()

    # 构建技术指标 map（并行获取）
    from concurrent.futures import ThreadPoolExecutor
    tech_map = {}
    def _load_tech(f):
        return f["code"], load_technical(f["code"])
    with ThreadPoolExecutor(max_workers=8) as ex:
        for code, data in ex.map(lambda f: _load_tech(f), FUNDS):
            tech_map[code] = data

    # 构建 portfolio 上下文
    current_total = sum(f["current_value"] for f in FUNDS)
    total_cost = current_total - sum(f["total_return"] for f in FUNDS)
    portfolio = {
        "total_value": current_total,
        "total_cost": total_cost,
        "total_target": PORTFOLIO_CONFIG["total_target"],
        "funds": FUNDS,
    }

    fmt_data = market_data

    reports = analyze_all_funds(
        funds_config=FUNDS,
        market_data=fmt_data,
        tech_data_map=tech_map,
        portfolio=portfolio,
        run_fundamental=run_fundamental,
    )

    summary = summarize_portfolio_status(reports)

    regime_name = reports[0].regime_name if reports else "放缓期"
    from engine.factor_model import REGIMES
    regime_cfg = REGIMES.get(regime_name, REGIMES["放缓期"])

    return reports, summary, fmt_data, regime_name, regime_cfg


# ══════════════════════════════════════════════
# 侧边栏导航 (SPA-style)
# ══════════════════════════════════════════════

_NAV_PAGES = [
    {"key": "overview",  "icon": "📊", "label": "总揽"},
    {"key": "assets",    "icon": "💰", "label": "资产"},
    {"key": "decision",  "icon": "🎯", "label": "决策"},
    {"key": "insight",   "icon": "🔍", "label": "透视"},
    {"key": "action",    "icon": "💡", "label": "操作"},
    {"key": "strategy",  "icon": "🧪", "label": "策略"},
    {"key": "review",    "icon": "📋", "label": "复盘"},
]


def _render_nav_sidebar(regime_name="放缓期", regime_cfg=None):
    """StableVault 品牌侧边栏 — SPA 导航 + 投资状态摘要"""
    from ui.design_tokens import (
        BG_CARD, BG_ELEVATED, BRAND, BRAND_DIM, UP, UP_DIM, DOWN, DOWN_DIM,
        WARN, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BORDER,
        RADIUS_MD, RADIUS_SM, SP_2, SP_3, SP_4,
        FONT_SIZE_XS, FONT_SIZE_SM, FONT_SIZE_LG, FONT_SIZE_MD,
    )

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "overview"

    with st.sidebar:
        # ═════ Brand Header ═════
        st.markdown(
            f'<div style="font-size:18px; font-weight:700; color:{TEXT_PRIMARY}; '
            f'letter-spacing:0.05em; margin-bottom:4px;">'
            f'Stable<span style="color:{BRAND};">Vault</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="color:{TEXT_MUTED}; font-size:{FONT_SIZE_XS}; margin-bottom:16px;">'
            f'四维决策引擎 · {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</div>',
            unsafe_allow_html=True,
        )

        # ═════ Navigation ═════
        for page in _NAV_PAGES:
            is_active = st.session_state["nav_page"] == page["key"]
            if st.button(
                f'{page["icon"]}  {page["label"]}',
                key=f'nav_{page["key"]}',
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["nav_page"] = page["key"]
                st.rerun()

        st.divider()

        # ═════ 投资部署摘要 ═════
        total_target = PORTFOLIO_CONFIG["total_target"]
        current_total = sum(f["current_value"] for f in FUNDS)
        remaining = total_target - current_total
        progress = min(current_total / total_target, 1.0) if total_target > 0 else 0

        st.progress(progress, text=f"部署 {progress*100:.0f}%")

        col1, col2 = st.columns(2)
        col1.metric("已部署", f"¥{current_total:,.0f}")
        col2.metric("目标", f"¥{total_target:,.0f}")

        # ═════ 持仓收益 ═════
        total_return = sum(f["total_return"] for f in FUNDS)
        total_cost = current_total - total_return
        return_pct = total_return / total_cost * 100 if total_cost > 0 else 0
        return_color = UP if total_return >= 0 else DOWN
        return_bg = UP_DIM if total_return >= 0 else DOWN_DIM
        sign = "+¥" if total_return >= 0 else "−¥"

        st.markdown(
            f'<div style="padding:{SP_3}; background:{return_bg}; border:1px solid {BORDER}; '
            f'border-radius:{RADIUS_SM}; text-align:center; margin:8px 0;">'
            f'<div style="color:{TEXT_MUTED}; font-size:{FONT_SIZE_XS}; text-transform:uppercase; '
            f'letter-spacing:0.08em;">累计盈亏</div>'
            f'<div style="color:{return_color}; font-family:var(--font-mono); font-size:{FONT_SIZE_LG}; '
            f'font-weight:700; margin-top:4px;">{sign}{abs(total_return):,.0f}</div>'
            f'<div style="color:{return_color}; font-size:{FONT_SIZE_SM}; margin-top:2px;">'
            f'{return_pct:+.2f}%</div></div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # ═════ Regime Badge ═════
        r_icon = regime_cfg.get("icon", "🔄") if regime_cfg else "🔄"
        st.markdown(
            f'<div style="background:{BRAND_DIM}; border:1px solid {BRAND}; '
            f'border-radius:{RADIUS_SM}; padding:8px 12px; font-size:12px; '
            f'text-align:center; color:{BRAND};">{r_icon} {regime_name}</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # ═════ Quick Actions ═════
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔄 刷新", use_container_width=True, help="清除缓存并刷新"):
                st.cache_data.clear()
                st.session_state.pop("_full_analysis", None)
                if "all_fund_analysis" in st.session_state:
                    del st.session_state["all_fund_analysis"]
                st.rerun()
        with col_b:
            is_full = st.session_state.get("_full_analysis", False)
            btn_label = "✅ 已加载" if is_full else "🧬 基本面"
            if st.button(btn_label, use_container_width=True,
                         help="加载基本面数据（含持仓/经理/风格分析）",
                         disabled=is_full):
                st.cache_data.clear()
                st.session_state["_full_analysis"] = True
                st.rerun()

        st.caption("⚠️ 仅供参考，非投资建议。")

        # ═════ 用户 & 登出 ═════
        user = st.session_state.get("user", "")
        if user:
            st.markdown(
                f'<div style="color:{TEXT_MUTED}; font-size:11px; text-align:center; '
                f'margin-top:8px;">👤 {user}</div>',
                unsafe_allow_html=True,
            )
            if st.button("🚪 退出登录", use_container_width=True):
                for k in ["authenticated", "user", "nav_page"]:
                    st.session_state.pop(k, None)
                st.rerun()


# ══════════════════════════════════════════════
# 登录认证
# ══════════════════════════════════════════════

import hashlib

# 用户凭证 — 密码以 SHA-256 哈希存储
_USERS = {
    "admin": hashlib.sha256("19950620".encode()).hexdigest(),
}


def _check_login():
    """显示登录页面，验证后写入 session_state。返回 True 表示已认证。"""
    if st.session_state.get("authenticated"):
        return True

    # ── 居中登录卡片 ──
    st.markdown(
        f'<div style="display:flex; justify-content:center; align-items:center; '
        f'min-height:70vh;">'
        f'<div style="background:{BG_CARD}; border:1px solid {BORDER}; '
        f'border-radius:16px; padding:48px 40px; width:380px; text-align:center;">'
        f'<div style="font-size:28px; font-weight:700; color:{TEXT_PRIMARY}; '
        f'letter-spacing:0.05em; margin-bottom:8px;">'
        f'Stable<span style="color:{BRAND};">Vault</span></div>'
        f'<div style="color:{TEXT_MUTED}; font-size:13px; margin-bottom:32px;">'
        f'四维决策引擎 · 基金智能监控</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        username = st.text_input("用户名", key="login_user", placeholder="请输入用户名")
        password = st.text_input("密码", type="password", key="login_pass", placeholder="请输入密码")
        if st.button("登 录", use_container_width=True, type="primary"):
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            if username in _USERS and _USERS[username] == pwd_hash:
                st.session_state["authenticated"] = True
                st.session_state["user"] = username
                st.rerun()
            else:
                st.error("用户名或密码错误")
    return False


# ══════════════════════════════════════════════
# 主程序入口 — SPA 架构
# ══════════════════════════════════════════════

def main():
    # ── 默认包含基本面（有缓存兜底，不会卡）──
    with st.spinner("正在加载四维决策分析..."):
        reports, summary, market_data, regime_name, regime_cfg = _run_unified_analysis(run_fundamental=True)

    # ── 渲染侧边栏导航 ──
    _render_nav_sidebar(regime_name=regime_name, regime_cfg=regime_cfg)

    # ── 构建通用上下文 ──
    current_total = sum(f["current_value"] for f in FUNDS)
    total_cost = current_total - sum(f["total_return"] for f in FUNDS)
    portfolio = {
        "total_value": current_total,
        "total_cost": total_cost,
        "total_target": PORTFOLIO_CONFIG["total_target"],
        "funds": FUNDS,
    }

    # ── 页面路由 ──
    page = st.session_state.get("nav_page", "overview")

    if page == "overview":
        # 总揽 = 决策总控 + 仪表盘合并
        from ui.decision_cockpit import render_decision_cockpit
        render_decision_cockpit(
            reports=reports, summary=summary, market_data=market_data,
            regime_name=regime_name, regime_cfg=regime_cfg,
            funds_config=FUNDS, portfolio=portfolio,
        )

    elif page == "assets":
        # 资产 = 原持仓总览 + 仪表盘
        from ui.dashboard_tab import render_dashboard_tab
        render_dashboard_tab(
            reports=reports, summary=summary, market_data=market_data,
            regime_name=regime_name, regime_cfg=regime_cfg,
        )

    elif page == "decision":
        # 决策 = 宏观监控 + 买卖建议合并
        render_macro_tab()
        st.divider()
        render_recommendation_tab()

    elif page == "insight":
        # 透视 = 基金洞察
        from ui.fund_insight_tab import render_fund_insight_tab
        render_fund_insight_tab(reports=reports, funds_config=FUNDS)

    elif page == "action":
        # 操作 = 操作中心
        from ui.action_center_tab import render_action_center_tab
        render_action_center_tab(
            reports=reports, funds_config=FUNDS, market_data=market_data,
            portfolio=portfolio, load_fund_history_fn=load_fund_history,
        )

    elif page == "strategy":
        # 策略 = 策略实验室
        from ui.strategy_lab_tab import render_strategy_lab_tab
        render_strategy_lab_tab(
            funds_config=FUNDS, load_fund_history_fn=load_fund_history,
            portfolio_config=PORTFOLIO_CONFIG,
            load_market_snapshot_fn=load_market_snapshot,
            load_fund_realtime_fn=load_fund_realtime,
            compute_technical_fn=load_technical,
        )

    elif page == "review":
        # 复盘 = 决策复盘
        from ui.decision_review_tab import render_decision_review_tab
        render_decision_review_tab(reports=reports)

    # ── count-up JS: st.markdown 不执行 <script>，
    #    data-countup 属性已预埋，待迁移到 components.html 整页模式后启用 ──


if __name__ == "__main__":
    if _check_login():
        main()
