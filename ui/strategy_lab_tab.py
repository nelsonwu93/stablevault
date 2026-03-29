"""
Tab4 策略实验室 — 定投回测 + AI虚拟盘
"""

import streamlit as st
from typing import List, Dict, Callable, Optional
import pandas as pd

from ui.design_tokens import (
    BG_BASE, BG_CARD, BG_ELEVATED, BRAND, BRAND_DIM,
    UP, UP_DIM, DOWN, DOWN_DIM, WARN, WARN_DIM,
    INFO, INFO_DIM, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    BORDER, RADIUS_SM, RADIUS_MD, RADIUS_LG,
    FONT_MONO, SHADOW_SM, SHADOW_MD,
    score_color,
)


def render_strategy_lab_tab(
    funds_config: List[Dict],
    load_fund_history_fn: Callable,
    portfolio_config: Dict = None,
    load_market_snapshot_fn: Callable = None,
    load_fund_realtime_fn: Callable = None,
    compute_technical_fn: Callable = None,
) -> None:

    st.markdown(f'<div style="font-size:1.3em; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:4px;">🧪 策略实验室</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:{TEXT_DIM}; font-size:0.85em; margin-bottom:16px;">回测定投策略 · AI虚拟盘模拟 · 验证投资思路</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📈 定投回测", "🤖 AI虚拟盘"])

    with tab1:
        try:
            from ui.dca_backtest_tab import render_dca_backtest_tab
            render_dca_backtest_tab(funds_config, load_fund_history_fn)
        except ImportError as e:
            st.error(f"无法加载定投回测模块: {e}")

    with tab2:
        try:
            from ui.virtual_portfolio_tab import render_virtual_portfolio_tab
            render_virtual_portfolio_tab(
                funds_config=funds_config,
                portfolio_config=portfolio_config or {},
                load_market_snapshot_fn=load_market_snapshot_fn,
                load_fund_realtime_fn=load_fund_realtime_fn,
                load_fund_history_fn=load_fund_history_fn,
                compute_technical_fn=compute_technical_fn,
            )
        except ImportError as e:
            st.warning(f"AI虚拟盘模块未可用: {e}")
        except Exception as e:
            st.error(f"AI虚拟盘运行异常: {str(e)[:200]}")
