"""
AI 虚拟盘页面 — Virtual Portfolio Tab
展示虚拟投资组合的持仓、交易历史、收益曲线、迭代日志
"""

import streamlit as st
import pandas as pd
import datetime
from typing import Dict, List

from ui.design_tokens import (
    BG_BASE, BG_CARD, BG_ELEVATED, BRAND, BRAND_DIM,
    UP, UP_DIM, DOWN, DOWN_DIM, WARN, WARN_DIM,
    INFO, INFO_DIM, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    BORDER, RADIUS_SM, RADIUS_MD, RADIUS_LG,
    FONT_MONO, SHADOW_SM, SHADOW_MD,
    score_color,
)


def render_virtual_portfolio_tab(
    funds_config: List[Dict],
    portfolio_config: Dict,
    load_market_snapshot_fn,
    load_fund_realtime_fn,
    load_fund_history_fn,
    compute_technical_fn,
):
    """渲染AI虚拟盘Tab"""
    from engine.virtual_portfolio import (
        init_virtual_tables, get_or_create_account, get_account_summary,
        execute_virtual_buy, execute_virtual_sell, update_holdings_nav,
        take_daily_snapshot, get_performance_history, get_trade_history,
        calculate_performance_metrics, ai_daily_analysis,
    )
    from engine.iteration_engine import run_weekly_iteration, _get_conn
    from engine.virtual_portfolio import get_iteration_logs, save_iteration_log
    from engine.factor_model import (
        detect_regime, score_macro, score_sector, score_fund_micro,
        composite_score, REGIMES,
    )
    from data.fetcher import get_fund_realtime, get_fund_history, compute_technical_indicators

    # 初始化表
    init_virtual_tables()
    account = get_or_create_account(initial_cash=portfolio_config.get("total_target", 300000))
    account_id = account["id"]

    st.markdown(f"### 🤖 AI 虚拟盘")
    st.caption("AI使用三层因子模型自主做投资决策，用虚拟资金模拟实战，自动记录和迭代优化")

    # ═════════════════════════════════════════
    # AUTO-RUN: 每次页面加载自动运行AI分析+交易+快照
    # ═════════════════════════════════════════
    _auto_run_key = "vp_auto_run_done"
    if _auto_run_key not in st.session_state:
        st.session_state[_auto_run_key] = False

    if not st.session_state[_auto_run_key]:
        with st.spinner("🤖 AI正在自动分析市场并执行虚拟交易..."):
            try:
                snapshot = load_market_snapshot_fn()
                if snapshot:
                    # 1) AI分析并执行交易
                    actions = ai_daily_analysis(
                        account_id=account_id,
                        funds_config=funds_config,
                        snapshot=snapshot,
                        score_macro_fn=score_macro,
                        score_sector_fn=score_sector,
                        score_fund_micro_fn=score_fund_micro,
                        composite_score_fn=composite_score,
                        detect_regime_fn=detect_regime,
                        get_fund_realtime_fn=get_fund_realtime,
                        compute_technical_fn=compute_technical_indicators,
                        get_fund_history_fn=get_fund_history,
                    )

                    # 2) 更新所有持仓净值
                    nav_map = {}
                    for f in funds_config:
                        rt = get_fund_realtime(f["code"])
                        n = rt.get("nav") or rt.get("est_nav")
                        if n:
                            nav_map[f["code"]] = n
                    update_holdings_nav(account_id, nav_map)

                    # 3) 拍摄每日快照
                    take_daily_snapshot(account_id)

                    # 4) 检查是否该运行迭代优化（每7天一次）
                    from engine.iteration_engine import run_weekly_iteration
                    from engine.virtual_portfolio import get_iteration_logs as _get_iter_logs
                    recent_logs = _get_iter_logs(limit=1)
                    should_iterate = True
                    if recent_logs:
                        last_iter_date = recent_logs[0].get("iteration_date", "")
                        if last_iter_date:
                            try:
                                last_dt = datetime.datetime.strptime(last_iter_date, "%Y-%m-%d").date()
                                if (datetime.date.today() - last_dt).days < 7:
                                    should_iterate = False
                            except Exception:
                                pass
                    if should_iterate:
                        try:
                            regime_name, regime_cfg = detect_regime(snapshot)
                            current_weights = regime_cfg.get("weights", {"macro": 0.35, "sector": 0.35, "micro": 0.30})
                            log = run_weekly_iteration(account_id, current_weights, REGIMES)
                            save_iteration_log(log)
                        except Exception:
                            pass

                    st.session_state[_auto_run_key] = True
                    st.session_state["vp_auto_actions"] = actions
                else:
                    st.session_state[_auto_run_key] = True
                    st.session_state["vp_auto_actions"] = []
            except Exception as e:
                st.session_state[_auto_run_key] = True
                st.session_state["vp_auto_actions"] = []
                st.warning(f"自动分析时遇到问题：{e}")

    # 显示自动交易结果
    auto_actions = st.session_state.get("vp_auto_actions", [])
    if auto_actions:
        st.success(f"✅ AI今日自动执行了 {len(auto_actions)} 笔交易")
        for a in auto_actions:
            emoji = "🟢" if a.get("direction") == "BUY" else "🔴"
            direction_color = UP if a.get("direction") == "BUY" else DOWN
            st.caption(f"{emoji} {a.get('direction','')} {a.get('fund_name','')} ¥{a.get('amount',0):,.0f} (D={a.get('d_score',0):+.2f})")

    # ═════════════════════════════════════════
    # SECTION 1: 账户概览
    # ═════════════════════════════════════════
    summary = get_account_summary(account_id)
    total_assets = summary["total_assets"]
    total_return = summary["total_return"]
    total_return_pct = summary["total_return_pct"]
    cash = summary["cash"]
    holdings = summary["holdings"]
    initial = account["initial_cash"]

    ret_color = UP if total_return >= 0 else DOWN
    hero_html = f'<div class="glass-card"><div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:20px;"><div><div class="label-dim">虚拟盘总资产</div><div class="num-xl" style="background:linear-gradient(135deg, {BRAND}, {UP}); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">¥{total_assets:,.0f}</div></div><div><div class="label-dim">累计盈亏</div><div class="num-lg" style="color:{ret_color};">{"+" if total_return>=0 else ""}¥{total_return:,.0f}</div><div style="color:{ret_color}; font-weight:700; margin-top:4px;">{total_return_pct:+.2f}%</div></div><div><div class="label-dim">可用现金</div><div class="num-md" style="color:{BRAND};">¥{cash:,.0f}</div></div><div><div class="label-dim">持仓基金</div><div class="num-md" style="color:{UP};">{len(holdings)}</div></div><div><div class="label-dim">总交易次数</div><div class="num-md" style="color:{WARN};">{summary["trade_count"]}</div></div></div></div>'
    st.markdown(hero_html, unsafe_allow_html=True)

    st.markdown("")

    # ═════════════════════════════════════════
    # SECTION 2: AI操作按钮
    # ═════════════════════════════════════════
    col_btn1, col_btn2, col_btn3 = st.columns(3)

    with col_btn1:
        if st.button("🤖 手动重新分析", use_container_width=True):
            with st.spinner("AI正在分析所有基金并执行虚拟交易..."):
                snapshot = load_market_snapshot_fn()
                if snapshot:
                    actions = ai_daily_analysis(
                        account_id=account_id,
                        funds_config=funds_config,
                        snapshot=snapshot,
                        score_macro_fn=score_macro,
                        score_sector_fn=score_sector,
                        score_fund_micro_fn=score_fund_micro,
                        composite_score_fn=composite_score,
                        detect_regime_fn=detect_regime,
                        get_fund_realtime_fn=get_fund_realtime,
                        compute_technical_fn=compute_technical_indicators,
                        get_fund_history_fn=get_fund_history,
                    )

                    # 更新净值并拍快照
                    nav_map = {}
                    for f in funds_config:
                        rt = get_fund_realtime(f["code"])
                        n = rt.get("nav") or rt.get("est_nav")
                        if n:
                            nav_map[f["code"]] = n
                    update_holdings_nav(account_id, nav_map)
                    take_daily_snapshot(account_id)

                    if actions:
                        st.success(f"✅ AI今日执行了 {len(actions)} 笔交易")
                        for a in actions:
                            emoji = "🟢" if a["direction"] == "BUY" else "🔴"
                            direction_color = UP if a["direction"] == "BUY" else DOWN
                            st.caption(f"{emoji} {a['direction']} {a.get('fund_name','')} ¥{a['amount']:,.0f} (D={a.get('d_score',0):+.2f})")
                    else:
                        st.info("📊 分析完成，今日无符合条件的交易信号")
                else:
                    st.error("市场数据获取失败，请重试")
                st.rerun()

    with col_btn2:
        if st.button("📸 拍摄今日快照", use_container_width=True):
            with st.spinner("更新净值并保存快照..."):
                nav_map = {}
                for f in funds_config:
                    rt = load_fund_realtime_fn(f["code"])
                    n = rt.get("nav") or rt.get("est_nav")
                    if n:
                        nav_map[f["code"]] = n
                update_holdings_nav(account_id, nav_map)
                snap = take_daily_snapshot(account_id)
                st.success(f"✅ 快照已保存 | 总资产 ¥{snap['total_assets']:,.0f} | 日收益 {snap['daily_return_pct']:+.2f}%")
                st.rerun()

    with col_btn3:
        if st.button("🔄 运行迭代优化", use_container_width=True):
            with st.spinner("AI正在分析交易表现并优化策略..."):
                snapshot = load_market_snapshot_fn()
                if snapshot:
                    regime_name, regime_cfg = detect_regime(snapshot)
                    current_weights = regime_cfg.get("weights", {"macro": 0.35, "sector": 0.35, "micro": 0.30})
                    log = run_weekly_iteration(account_id, current_weights, REGIMES)
                    save_iteration_log(log)
                    st.success(f"✅ 第 {log['iteration_num']} 轮迭代完成")
                    st.caption(log.get("lessons_learned", ""))
                    if log.get("weight_changes"):
                        for change in log["weight_changes"]:
                            st.caption(f"  📝 {change}")
                st.rerun()

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 3: 收益曲线
    # ═════════════════════════════════════════
    st.markdown("#### 📈 虚拟盘收益曲线")
    perf_history = get_performance_history(account_id, days=180)
    if perf_history and len(perf_history) > 1:
        perf_df = pd.DataFrame(perf_history)
        perf_df["日期"] = pd.to_datetime(perf_df["snapshot_date"])
        chart_data = perf_df.set_index("日期")[["cumulative_return_pct"]].rename(
            columns={"cumulative_return_pct": "虚拟盘收益率(%)"}
        )
        if "benchmark_return_pct" in perf_df.columns:
            chart_data["基准收益率(%)"] = perf_df.set_index("日期")["benchmark_return_pct"]
        st.line_chart(chart_data, use_container_width=True)
    else:
        st.info("暂无收益历史。点击上方「AI一键分析并交易」或「拍摄今日快照」开始积累数据。")

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 4: 当前持仓
    # ═════════════════════════════════════════
    st.markdown("#### 💼 当前持仓")
    if holdings:
        for h in holdings:
            nav_now = h.get("last_nav") or h.get("avg_cost_nav", 0)
            market_val = h["shares"] * nav_now
            cost = h["total_cost"]
            pnl = market_val - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0
            pnl_color = UP if pnl >= 0 else DOWN

            card_html = f'<div class="signal-bar" style="border-left-color:{pnl_color};"><div><span style="color:{TEXT_PRIMARY}; font-weight:600;">{h["fund_name"]}</span><span style="color:{TEXT_MUTED}; font-size:0.75em; margin-left:8px;">{h["fund_code"]}</span><div style="color:{TEXT_MUTED}; font-size:0.75em; margin-top:4px;">持有 {h["shares"]:.2f} 份 | 成本 ¥{h["avg_cost_nav"]:.4f} → 现价 ¥{nav_now:.4f}</div></div><div style="text-align:right;"><div style="color:{TEXT_PRIMARY}; font-weight:700; font-family:monospace;">¥{market_val:,.0f}</div><div style="color:{pnl_color}; font-weight:700; margin-top:4px;">{"+" if pnl>=0 else ""}¥{pnl:,.0f}</div><div style="color:{pnl_color}; font-size:0.8em;">{pnl_pct:+.1f}%</div></div></div>'
            st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.caption("暂无持仓。点击「AI一键分析并交易」让AI开始虚拟投资。")

    st.divider()

    # ═════════════════════════════════════════
    # SECTION 5: 交易历史
    # ═════════════════════════════════════════
    with st.expander("📜 交易历史", expanded=False):
        trades = get_trade_history(account_id, limit=30)
        if trades:
            for t in trades:
                d_emoji = "🟢" if t["direction"] == "BUY" else "🔴"
                d_word = "买入" if t["direction"] == "BUY" else "卖出"
                d_score = t.get("d_score") or 0
                trade_color = UP if t["direction"] == "BUY" else DOWN
                st.markdown(f'<div style="padding:8px 12px; margin:4px 0; background:rgba(255,255,255,0.02); border-radius:8px; border-left:3px solid {trade_color}; font-size:0.85em; display:flex; justify-content:space-between; align-items:center;"><div><span style="color:{trade_color}; font-weight:700;">{d_emoji} {d_word}</span> <span style="color:{TEXT_SECONDARY}; font-weight:600;">{t["fund_name"]}</span><span style="color:{TEXT_MUTED}; margin-left:8px;font-size:0.8em;">@{t.get("nav",0):.4f}</span></div><div style="text-align:right;"><span style="color:{BRAND}; font-weight:600;">¥{t["amount"]:,.0f}</span><span style="color:{TEXT_MUTED}; margin-left:8px; font-size:0.8em;">D={d_score:+.2f}</span></div></div>', unsafe_allow_html=True)
        else:
            st.caption("暂无交易记录")

    # ═════════════════════════════════════════
    # SECTION 6: 性能指标
    # ═════════════════════════════════════════
    with st.expander("📊 性能指标仪表盘", expanded=False):
        metrics = calculate_performance_metrics(account_id)
        m_cols = st.columns(4)
        m_cols[0].metric("累计收益率", f"{metrics['total_return_pct']:+.2f}%")
        m_cols[1].metric("年化收益率", f"{metrics['annual_return_pct']:+.2f}%")
        m_cols[2].metric("最大回撤", f"{metrics['max_drawdown_pct']:.2f}%")
        m_cols[3].metric("夏普比率", f"{metrics['sharpe_ratio']:.2f}")

        m_cols2 = st.columns(4)
        m_cols2[0].metric("正收益天数占比", f"{metrics['win_rate']:.1f}%")
        m_cols2[1].metric("总交易笔数", f"{metrics['total_trades']}")
        m_cols2[2].metric("运行天数", f"{metrics['trading_days']}")
        m_cols2[3].metric("初始资金", f"¥{initial:,.0f}")

    # ═════════════════════════════════════════
    # SECTION 7: 迭代优化日志
    # ═════════════════════════════════════════
    with st.expander("🔄 AI迭代优化日志", expanded=False):
        logs = get_iteration_logs(limit=10)
        if logs:
            for log in logs:
                iter_num = log.get("iteration_num", 0)
                ret = log.get("total_return_pct", 0)
                alpha = log.get("alpha", 0)
                ret_color = UP if ret >= 0 else DOWN
                alpha_color = UP if alpha >= 0 else DOWN

                st.markdown(f'<div class="glass-card"><div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;"><div><div class="label-bright">迭代轮次 #{iter_num}</div><div class="label-dim" style="font-size:0.8em;">{log.get("iteration_date", "")}</div></div><div style="text-align:right; color:{ret_color}; font-weight:700; font-size:1.2em;">{ret:+.2f}%</div></div></div>', unsafe_allow_html=True)

                iter_cols = st.columns(4)
                iter_cols[0].metric("期间收益", f"{ret:+.2f}%")
                iter_cols[1].metric("超额α", f"{alpha:+.2f}%")
                iter_cols[2].metric("最大回撤", f"{log.get('max_drawdown', 0):.2f}%")
                iter_cols[3].metric("夏普", f"{log.get('sharpe_ratio', 0):.2f}")

                # 权重变更
                changes = log.get("weight_changes", [])
                if isinstance(changes, list) and changes:
                    st.markdown("**权重调整:**")
                    for ch in changes:
                        st.caption(f"📝 {ch}")

                # 经验总结
                lessons = log.get("lessons_learned", "")
                if lessons:
                    st.markdown(f'<div class="ft-explainer">{lessons}</div>', unsafe_allow_html=True)
                st.divider()
        else:
            st.caption("暂无迭代日志。运行一段时间交易后，点击「运行迭代优化」让AI自动调整策略。")
