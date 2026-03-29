import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from ui.design_tokens import (
    BG_BASE, BG_CARD, BG_ELEVATED, BRAND, BRAND_DIM,
    UP, UP_DIM, DOWN, DOWN_DIM, WARN, WARN_DIM,
    INFO, INFO_DIM, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    BORDER, RADIUS_SM, RADIUS_MD, RADIUS_LG,
    SCORE_MACRO, SCORE_SECTOR, SCORE_TECH, SCORE_FUND,
    FONT_MONO, SHADOW_SM, SHADOW_MD,
    score_color, verdict_style, dim_color,
)


def render_decision_review_tab(reports=None):
    """
    Render Tab 5: Decision Review (决策复盘)
    Tracks decision history and accuracy metrics.

    Args:
        reports: Optional List[FundAnalysisReport] for current recommendations
    """

    st.markdown(f'<div style="font-size:1.3em; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:4px;">📋 决策复盘</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:{TEXT_DIM}; font-size:0.85em; margin-bottom:16px;">跟踪投资决策质量与迭代效果</div>', unsafe_allow_html=True)

    # Section A: Today's Decision Snapshot
    st.markdown("#### 📊 当日决策快照")

    if reports and len(reports) > 0:
        try:
            # Build today's recommendations table
            today_data = []
            for report in reports:
                today_data.append({
                    "基金": report.fund_code if hasattr(report, 'fund_code') else "N/A",
                    "D-score": f"{report.d_score:.2f}" if hasattr(report, 'd_score') else "N/A",
                    "建议": report.recommendation if hasattr(report, 'recommendation') else "持观",
                    "金额": f"¥{report.suggested_amount:,.0f}" if hasattr(report, 'suggested_amount') else "N/A",
                    "置信度": f"{report.confidence*100:.0f}%" if hasattr(report, 'confidence') else "N/A",
                })

            if today_data:
                df_today = pd.DataFrame(today_data)
                st.dataframe(df_today, use_container_width=True, hide_index=True)
            else:
                st.info("暂无今日决策数据")
        except Exception as e:
            st.warning(f"读取决策数据失败: {str(e)}")
    else:
        st.info("暂无今日决策数据")

    st.divider()

    # Section B: Historical Decisions
    st.markdown("#### 📈 历史决策记录")

    try:
        db_path = Path(__file__).parent.parent / "data" / "virtual_portfolio.db"

        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Check if vp_trades table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='vp_trades'"
            )

            if cursor.fetchone():
                # Load last 50 trades
                query = """
                    SELECT
                        trade_date,
                        fund_code,
                        action,
                        amount,
                        d_score,
                        price,
                        shares
                    FROM vp_trades
                    ORDER BY trade_date DESC
                    LIMIT 50
                """

                df_trades = pd.read_sql_query(query, conn)

                if not df_trades.empty:
                    # Format the dataframe for display
                    df_display = df_trades.copy()

                    # Rename columns for Chinese display
                    df_display.columns = ["交易日期", "基金代码", "操作", "金额", "D-score", "价格", "份额"]

                    # Format numeric columns
                    if "金额" in df_display.columns:
                        df_display["金额"] = df_display["金额"].apply(
                            lambda x: f"¥{x:,.0f}" if pd.notna(x) else "N/A"
                        )
                    if "D-score" in df_display.columns:
                        df_display["D-score"] = df_display["D-score"].apply(
                            lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
                        )
                    if "价格" in df_display.columns:
                        df_display["价格"] = df_display["价格"].apply(
                            lambda x: f"¥{x:.2f}" if pd.notna(x) else "N/A"
                        )
                    if "份额" in df_display.columns:
                        df_display["份额"] = df_display["份额"].apply(
                            lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
                        )

                    st.dataframe(df_display, use_container_width=True, hide_index=True)

                    # Summary statistics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        buy_count = (df_trades["action"] == "buy").sum()
                        st.metric("买入次数", buy_count)
                    with col2:
                        sell_count = (df_trades["action"] == "sell").sum()
                        st.metric("卖出次数", sell_count)
                    with col3:
                        total_amount = df_trades["amount"].sum()
                        st.metric("总交易额", f"¥{total_amount:,.0f}")
                else:
                    st.info("暂无历史决策记录")
            else:
                st.info("暂无历史决策记录（vp_trades表不存在）")

            conn.close()
        else:
            st.info("暂无历史决策记录（数据库不存在）")

    except Exception as e:
        st.warning(f"读取历史决策失败: {str(e)}")

    st.divider()

    # Section C: Decision Accuracy Tracking
    st.markdown("#### 🎯 决策准确率追踪")

    try:
        db_path = Path(__file__).parent.parent / "data" / "virtual_portfolio.db"

        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Check if vp_iteration_log table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='vp_iteration_log'"
            )

            if cursor.fetchone():
                # Load iteration metrics
                query = """
                    SELECT
                        iteration_id,
                        timestamp,
                        total_trades,
                        successful_trades,
                        win_rate,
                        total_return,
                        sharpe_ratio,
                        max_drawdown
                    FROM vp_iteration_log
                    ORDER BY timestamp DESC
                    LIMIT 20
                """

                try:
                    df_metrics = pd.read_sql_query(query, conn)

                    if not df_metrics.empty:
                        # Display latest metrics in cards
                        latest = df_metrics.iloc[0]

                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            win_rate = latest["win_rate"] if pd.notna(latest["win_rate"]) else 0
                            st.metric(
                                "胜率",
                                f"{win_rate*100:.1f}%",
                                delta=None
                            )

                        with col2:
                            sharpe = latest["sharpe_ratio"] if pd.notna(latest["sharpe_ratio"]) else 0
                            st.metric(
                                "夏普比率",
                                f"{sharpe:.2f}",
                                delta=None
                            )

                        with col3:
                            returns = latest["total_return"] if pd.notna(latest["total_return"]) else 0
                            st.metric(
                                "累计收益率",
                                f"{returns*100:.2f}%",
                                delta=None
                            )

                        with col4:
                            drawdown = latest["max_drawdown"] if pd.notna(latest["max_drawdown"]) else 0
                            st.metric(
                                "最大回撤",
                                f"{drawdown*100:.2f}%",
                                delta=None
                            )

                        st.markdown("**历史准确率趋势**")

                        # Format for display
                        df_display = df_metrics.copy()
                        df_display.columns = [
                            "迭代号", "时间戳", "总交易数", "成功交易数",
                            "胜率", "累计收益", "夏普比率", "最大回撤"
                        ]

                        # Format numeric columns
                        df_display["胜率"] = df_display["胜率"].apply(
                            lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
                        )
                        df_display["累计收益"] = df_display["累计收益"].apply(
                            lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
                        )
                        df_display["夏普比率"] = df_display["夏普比率"].apply(
                            lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
                        )
                        df_display["最大回撤"] = df_display["最大回撤"].apply(
                            lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
                        )

                        st.dataframe(df_display, use_container_width=True, hide_index=True)
                    else:
                        st.info("暂无准确率数据")

                except Exception as inner_e:
                    st.info("准确率数据将在系统运行过程中逐步累积")
            else:
                st.info("准确率数据将在系统运行过程中逐步累积（vp_iteration_log表尚未创建）")

            conn.close()
        else:
            st.info("准确率数据将在系统运行过程中逐步累积")

    except Exception as e:
        st.warning(f"读取准确率数据失败: {str(e)}")

    st.divider()

    # Section D: Self-Iteration Log
    st.markdown("#### 🔄 自迭代记录")

    try:
        db_path = Path(__file__).parent.parent / "data" / "virtual_portfolio.db"

        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Check if vp_iteration_log table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='vp_iteration_log'"
            )

            if cursor.fetchone():
                # Load iteration details
                query = """
                    SELECT
                        iteration_id,
                        timestamp,
                        factor_adjustments,
                        weight_changes
                    FROM vp_iteration_log
                    ORDER BY timestamp DESC
                    LIMIT 10
                """

                try:
                    df_iterations = pd.read_sql_query(query, conn)

                    if not df_iterations.empty:
                        st.markdown("**最近的因子权重调整**")

                        # Display iteration history
                        for idx, row in df_iterations.iterrows():
                            with st.expander(
                                f"迭代 #{row['iteration_id']} - {row['timestamp']}"
                            ):
                                if pd.notna(row["factor_adjustments"]):
                                    st.write("**因子调整:**")
                                    st.code(row["factor_adjustments"])

                                if pd.notna(row["weight_changes"]):
                                    st.write("**权重变化:**")
                                    st.code(row["weight_changes"])

                                if not row["factor_adjustments"] and not row["weight_changes"]:
                                    st.write("无详细调整信息")
                    else:
                        st.info("暂无自迭代记录")

                except Exception as inner_e:
                    st.info("自迭代记录将在系统自学习过程中逐步记录")
            else:
                st.info("自迭代记录将在系统自学习过程中逐步记录")

            conn.close()
        else:
            st.info("自迭代记录将在系统自学习过程中逐步记录")

    except Exception as e:
        st.warning(f"读取自迭代记录失败: {str(e)}")

    # Footer note
    st.divider()
    st.caption(
        "💡 决策复盘帮助您追踪投资决策的质量和系统的自学习进展。"
        "数据将随系统运行而逐步积累。"
    )
