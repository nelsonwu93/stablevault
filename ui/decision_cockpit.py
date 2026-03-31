"""
决策总揽 v4（Decision Cockpit）— 7层深度钻取

层级架构：
  L0 — 裁决总栏（加仓/减持/观望汇总）
  L1 — 基金列表（每行：结论 + 迷你 M→S→T→F→D 流）
  L2 — 展开决策链（SVG粒子流 + 权重环）  ← 点击基金
  L3 — 子因子卡片（如 M1利率周期, M2经济周期...） ← 点击维度
  L4 — 细分指标面板 ← 点击子因子
  L5 — 指标详情（统计 + 评分规则） ← 点击指标
  L6 — 原始数据时间序列 + 方法论 ← 继续展开

v4.0 — 在 v3 基础上每个维度至少再深3层
"""

import streamlit as st
from typing import List, Dict, Optional
from datetime import datetime
import json


# ═══════════════════════════════════════
#  Factor metadata — 评分规则描述
# ═══════════════════════════════════════
# 为每个因子提供人类可读的评分规则，供 L5/L6 展示

MACRO_FACTOR_META = {
    "M1_利率周期": {
        "label": "利率周期",
        "icon": "🏦",
        "desc": "美债10年期收益率对权益市场估值的影响",
        "scoring": [
            {"cond": "< 3.5%", "result": "+1.5 利率友好"},
            {"cond": "3.5% ~ 4.0%", "result": "+0.5 中性"},
            {"cond": "4.0% ~ 4.5%", "result": "0 高位压力"},
            {"cond": "4.5% ~ 5.0%", "result": "-1.0 紧缩"},
            {"cond": "> 5.0%", "result": "-2.0 危机"},
        ],
        "method": "score_macro() → M1: market_data['us_10y'] 分段映射。权重=0.15",
    },
    "M2_经济周期": {
        "label": "经济周期",
        "icon": "🏭",
        "desc": "中国PMI数据反映的经济周期状态",
        "scoring": [
            {"cond": "> 52", "result": "+1.5 强扩张"},
            {"cond": "51 ~ 52", "result": "+1.0"},
            {"cond": "50 ~ 51", "result": "+0.5 弱扩张"},
            {"cond": "49 ~ 50", "result": "-0.5 收缩"},
            {"cond": "< 49", "result": "-1.5 深度收缩"},
        ],
        "method": "score_macro() → M2: market_data['pmi'] 分段映射。权重=0.20",
    },
    "M3_大宗冲击": {
        "label": "油价冲击",
        "icon": "🛢️",
        "desc": "国际原油4周涨跌幅对市场的冲击影响",
        "scoring": [
            {"cond": "4周涨 > 15%", "result": "-2.0 冲击"},
            {"cond": "5% ~ 15%", "result": "-0.5"},
            {"cond": "±5%", "result": "0 中性"},
            {"cond": "跌 > 5%", "result": "+0.5 利好"},
        ],
        "method": "score_macro() → M3: 油价4周变化。权重=0.10",
    },
    "M4_利差汇率": {
        "label": "利差与汇率",
        "icon": "💱",
        "desc": "中美利差和人民币汇率对资本流动的影响",
        "scoring": [
            {"cond": "利差 > 0", "result": "+1.0 资金流入"},
            {"cond": "-1% ~ 0%", "result": "+0.3"},
            {"cond": "-2% ~ -1%", "result": "0"},
            {"cond": "< -2%", "result": "-0.5 资金外流"},
        ],
        "method": "score_macro() → M4: CN10Y-US10Y利差 + CNY变化。权重=0.15",
    },
    "M5_风险偏好": {
        "label": "全球风险偏好",
        "icon": "🌡️",
        "desc": "黄金/原油/纳指等资产反映的全球风险情绪",
        "scoring": [
            {"cond": "避险信号强", "result": "-1.0"},
            {"cond": "中性", "result": "0"},
            {"cond": "风险偏好升温", "result": "+1.0"},
        ],
        "method": "score_macro() → M5: 黄金/油/纳指综合判断。权重=0.15",
    },
    "M6_边际变化": {
        "label": "边际变化(v2.0新增)",
        "icon": "📈",
        "desc": "关键指标的周环比变化方向——利率Δ、PMI Δ、北向资金动量、油价趋势",
        "scoring": [
            {"cond": "多指标改善", "result": "+0.5 ~ +1.0"},
            {"cond": "混合信号", "result": "0"},
            {"cond": "多指标恶化", "result": "-0.5 ~ -1.0"},
        ],
        "method": "score_macro() → M6: delta子项加权。v2.0新增，权重=0.25",
    },
}

SECTOR_FACTOR_META = {
    "利率敏感": {"icon": "📊", "desc": "该板块对利率变化的敏感程度", "method": "score_sector → S1"},
    "PMI景气": {"icon": "🏭", "desc": "PMI变化对该板块的景气传导弹性", "method": "score_sector → S2"},
    "油价影响": {"icon": "🛢️", "desc": "油价变化对该板块的成本/替代效应", "method": "score_sector → S3"},
    "北向资金": {"icon": "💰", "desc": "北向资金对该板块的净流入偏好", "method": "score_sector → S4"},
    "地缘风险": {"icon": "🌐", "desc": "地缘政治事件对该板块的特异性影响", "method": "score_sector → S5"},
    "英伟达信号": {"icon": "🤖", "desc": "NVDA走势对AI/科技板块的风向标效应", "method": "score_sector → S6（仅AI）"},
    "债券替代": {"icon": "💵", "desc": "低利率环境下红利股作为债券替代品的吸引力", "method": "score_sector → S7（仅红利）"},
}

TECH_FACTOR_META = {
    "持仓状态": {"icon": "📦", "desc": "当前持仓盈亏状态与止损线距离", "method": "score_fund_micro → C1"},
    "RSI": {"icon": "📉", "desc": "14日RSI技术指标，v2.0增强超卖信号", "method": "score_fund_micro → C2 v2.0 rescoring"},
    "均线位置": {"icon": "📏", "desc": "价格相对MA60的偏离度，v2.0均值回归逻辑", "method": "score_fund_micro → C3 distance-based"},
    "MACD": {"icon": "📊", "desc": "MACD金叉/死叉信号", "method": "score_fund_micro → C4"},
    "仓位空间": {"icon": "🏗️", "desc": "当前仓位vs目标仓位的建仓空间", "method": "score_fund_micro → C5 v2.0 position building"},
    "动量回归": {"icon": "🔄", "desc": "4周累计涨跌幅评估均值回归概率", "method": "score_fund_micro → C6 v2.0新增"},
}

FUND_FACTOR_META = {
    "持仓估值": {"icon": "💰", "desc": "组合加权PE/PB估值水平", "method": "unified_analyzer → F1"},
    "盈利成长": {"icon": "📈", "desc": "组合加权归母净利增速", "method": "unified_analyzer → F2"},
    "集中度": {"icon": "🎯", "desc": "Top3持仓占比，衡量集中度风险", "method": "unified_analyzer → F3"},
    "经理能力": {"icon": "👤", "desc": "基金经理综合能力评分/跟踪误差", "method": "unified_analyzer → F4"},
    "持仓稳定": {"icon": "🔒", "desc": "持仓换手率评估稳定性", "method": "unified_analyzer → F5"},
}


def render_decision_cockpit(
    reports: List,
    summary: Dict,
    market_data: Dict,
    regime_name: str,
    regime_cfg: Dict,
    funds_config: List[Dict],
    portfolio: Dict,
) -> None:
    """渲染 v4 决策总揽 — 7层深度钻取。"""
    if not reports:
        st.info("暂无分析数据，请等待数据加载完成。")
        return

    # 准备数据
    data = _prepare_cockpit_data(reports, summary, market_data, regime_name, regime_cfg, funds_config, portfolio)

    # 渲染整页 HTML
    html = _build_cockpit_html(data)
    n_funds = len(data["funds"])
    height = 220 + n_funds * 62 + 80  # base + rows + summary; expands via scrolling
    st.components.v1.html(html, height=max(height, 600), scrolling=True)


def _prepare_cockpit_data(reports, summary, market_data, regime_name, regime_cfg, funds_config, portfolio) -> Dict:
    """从分析报告提取渲染所需的完整深度数据。"""

    # 取 regime 权重
    r0 = reports[0]
    wm, ws, wt, wf = r0.macro.weight, r0.sector_score.weight, r0.technical.weight, r0.fundamental.weight

    funds = []
    for r in reports:
        fund_cfg = next((f for f in funds_config if f["code"] == r.fund_code), {})
        total_return = fund_cfg.get("total_return", 0)
        current_value = fund_cfg.get("current_value", 1)
        cost = max(current_value - total_return, 0.01)
        return_pct = total_return / cost if cost > 0 else 0
        target_pct = fund_cfg.get("target_pct", 0.05)
        total_target = portfolio.get("total_target", 300000)
        target_alloc = target_pct * total_target
        position_pct = current_value / target_alloc if target_alloc > 0 else 0

        # 基金类型
        if r.recommendation in ("BUY", "BUY_SMALL"):
            ftype = "buy"
        elif r.recommendation in ("VETO", "SELL", "SELL_PARTIAL"):
            ftype = "sell"
        else:
            ftype = "wait"

        # 构建四维深度数据
        dims = {}

        # --- M 宏观 ---
        m_comps = r.macro.components or {}
        m_factors = []
        for key, meta in MACRO_FACTOR_META.items():
            val_data = m_comps.get(key, {})
            if isinstance(val_data, dict):
                score = round(val_data.get("score", 0), 2)
                detail = val_data.get("detail", "")
                fweight = val_data.get("weight", 0)
            elif isinstance(val_data, (int, float)):
                score = round(val_data, 2)
                detail = ""
                fweight = 0
            else:
                continue
            m_factors.append({
                "name": key.replace("_", " "),
                "val": score,
                "summary": meta.get("desc", ""),
                "icon": meta.get("icon", ""),
                "detail": detail,
                "weight": fweight,
                "scoring": meta.get("scoring", []),
                "method": meta.get("method", ""),
            })
        dims["M"] = {
            "score": round(r.macro.score, 2),
            "weight": wm,
            "icon": "🏦",
            "label": "宏观",
            "factors": m_factors,
        }

        # --- S 行业 ---
        s_comps = r.sector_score.components or {}
        s_factors = []
        for key, val in s_comps.items():
            meta = SECTOR_FACTOR_META.get(key, {})
            score = round(val, 2) if isinstance(val, (int, float)) else round(val.get("score", 0), 2) if isinstance(val, dict) else 0
            s_factors.append({
                "name": f"S {key}",
                "val": score,
                "summary": meta.get("desc", key),
                "icon": meta.get("icon", "🏭"),
                "detail": "",
                "scoring": [],
                "method": meta.get("method", ""),
            })
        dims["S"] = {
            "score": round(r.sector_score.score, 2),
            "weight": ws,
            "icon": "🏭",
            "label": "行业",
            "factors": s_factors,
        }

        # --- T 技术面 ---
        t_comps = r.technical.components or {}
        t_factors = []
        for key, val in t_comps.items():
            meta = TECH_FACTOR_META.get(key, {})
            score = round(val, 2) if isinstance(val, (int, float)) else round(val.get("score", 0), 2) if isinstance(val, dict) else 0
            t_factors.append({
                "name": f"T {key}",
                "val": score,
                "summary": meta.get("desc", key),
                "icon": meta.get("icon", "📊"),
                "detail": "",
                "scoring": [],
                "method": meta.get("method", ""),
            })
        dims["T"] = {
            "score": round(r.technical.score, 2),
            "weight": wt,
            "icon": "📊",
            "label": "技术面",
            "factors": t_factors,
        }

        # --- F 基本面 ---
        f_comps = r.fundamental.components or {}
        f_factors = []
        for key, val in f_comps.items():
            meta = FUND_FACTOR_META.get(key, {})
            score = round(val, 2) if isinstance(val, (int, float)) else round(val.get("score", 0), 2) if isinstance(val, dict) else 0
            f_factors.append({
                "name": f"F {key}",
                "val": score,
                "summary": meta.get("desc", key),
                "icon": meta.get("icon", "💎"),
                "detail": "",
                "scoring": [],
                "method": meta.get("method", ""),
            })
        dims["F"] = {
            "score": round(r.fundamental.score, 2),
            "weight": wf,
            "icon": "💎",
            "label": "基本面",
            "factors": f_factors,
        }

        funds.append({
            "name": r.fund_short or r.fund_name,
            "code": r.fund_code,
            "sector": r.sector,
            "type": ftype,
            "amount": r.suggested_amount,
            "reason": _build_reason(r, fund_cfg, position_pct, return_pct),
            "d": round(r.d_score, 2),
            "dims": dims,
        })

    # 排序：买入 > 卖出 > 观望，组内按 |d_score| 排
    type_order = {"buy": 0, "sell": 1, "wait": 2}
    funds.sort(key=lambda f: (type_order.get(f["type"], 2), -abs(f["d"])))

    # 汇总
    buy_count = sum(1 for f in funds if f["type"] == "buy")
    sell_count = sum(1 for f in funds if f["type"] == "sell")
    wait_count = sum(1 for f in funds if f["type"] == "wait")
    total_buy = sum(f["amount"] for f in funds if f["type"] == "buy")
    total_sell = sum(f["amount"] for f in funds if f["type"] == "sell")
    avg_d = summary.get("avg_d_score", 0) if summary else sum(r.d_score for r in reports) / len(reports)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "regime_name": regime_name,
        "regime_icon": regime_cfg.get("icon", "🌧️"),
        "regime_color": regime_cfg.get("color", "#FF8C00"),
        "regime_weights": f"M={wm*100:.0f}% S={ws*100:.0f}% T={wt*100:.0f}% F={wf*100:.0f}%",
        "buy_count": buy_count,
        "sell_count": sell_count,
        "wait_count": wait_count,
        "total_buy": total_buy,
        "total_sell": total_sell,
        "avg_d": round(avg_d, 3),
        "funds": funds,
        "commentary": _build_commentary(reports, regime_name, funds, total_buy),
    }


def _build_reason(r, fund_cfg, position_pct, return_pct):
    """为每只基金生成一句话原因。"""
    parts = []
    if r.recommendation in ("BUY", "BUY_SMALL"):
        dims = [("基本面", r.fundamental.score), ("技术面", r.technical.score),
                ("行业", r.sector_score.score), ("宏观", r.macro.score)]
        best = max(dims, key=lambda x: x[1])
        if best[1] > 0.2:
            parts.append(f"{best[0]}支撑({best[1]:+.1f})")
        if position_pct < 0.3:
            parts.append(f"仓位仅{position_pct*100:.0f}%")
        if hasattr(r, 'technical') and r.technical.components:
            comps = r.technical.components
            rsi_data = comps.get("RSI", {})
            rsi_val = rsi_data.get("score", 0) if isinstance(rsi_data, dict) else rsi_data
            if isinstance(rsi_val, (int, float)) and rsi_val > 1.0:
                parts.append("RSI超卖反弹")
    elif r.recommendation in ("VETO", "SELL", "SELL_PARTIAL"):
        if r.checklist_veto:
            parts.append("Checklist否决")
        if return_pct < -0.08:
            parts.append(f"亏损{return_pct*100:.1f}%接近止损")
        dims = [("宏观", r.macro.score), ("行业", r.sector_score.score)]
        worst = min(dims, key=lambda x: x[1])
        if worst[1] < -0.3:
            parts.append(f"{worst[0]}拖累({worst[1]:+.1f})")
    else:
        if abs(r.d_score) < 0.1:
            parts.append("D接近阈值，信号不明确")
        elif r.d_score < -0.2:
            dims = [("宏观", r.macro.score), ("行业", r.sector_score.score),
                    ("技术面", r.technical.score)]
            worst = min(dims, key=lambda x: x[1])
            parts.append(f"{worst[0]}压制({worst[1]:+.1f})")
        if position_pct > 0.6:
            parts.append("仓位已充足")

    return "，".join(parts) if parts else "综合信号中性"


def _build_commentary(reports, regime_name, funds, total_buy):
    """生成 AI 策略摘要。"""
    regime_desc = {
        "扩张期": "扩张期下基本面α主导",
        "放缓期": "放缓期下基本面为锚、行业轮动辅助",
        "外部冲击": "外部冲击环境下宏观防守优先",
        "衰退修复": "衰退修复阶段把握反弹节奏",
        "流动性危机": "流动性危机下极度防守",
    }
    parts = [f"本周策略：{regime_desc.get(regime_name, regime_name)}。"]

    buy_funds = [f for f in funds if f["type"] == "buy"]
    sell_funds = [f for f in funds if f["type"] == "sell"]

    if buy_funds:
        names = "、".join(f["name"] for f in buy_funds[:3])
        parts.append(f"{names}是本周最优加仓标的，合计建议投入¥{total_buy:,.0f}。")
    else:
        parts.append("本周无明确买入信号，建议维持现有仓位。")

    if sell_funds:
        names = "、".join(f["name"] for f in sell_funds[:2])
        parts.append(f"{names}建议减仓控制风险。")

    avg_scores = {}
    for r in reports:
        for dim_name, dim_obj in [("宏观", r.macro), ("行业", r.sector_score),
                                    ("技术面", r.technical), ("基本面", r.fundamental)]:
            avg_scores.setdefault(dim_name, []).append(dim_obj.score)
    dim_avgs = {k: sum(v) / len(v) for k, v in avg_scores.items()}
    best_dim = max(dim_avgs, key=dim_avgs.get)
    worst_dim = min(dim_avgs, key=dim_avgs.get)
    if dim_avgs[best_dim] > 0.1:
        parts.append(f"{best_dim}是最大正贡献。")
    if dim_avgs[worst_dim] < -0.1:
        parts.append(f"注意{worst_dim}压制。")

    return "".join(parts)


def _build_cockpit_html(data: Dict) -> str:
    """生成 v4 七层深度钻取 HTML。"""

    funds_json = json.dumps(data["funds"], ensure_ascii=False, default=str)
    commentary = data["commentary"].replace("'", "\\'").replace("\n", " ")

    # 裁决文案
    bc, wc, slc = data["buy_count"], data["wait_count"], data["sell_count"]
    tb, ts_ = data["total_buy"], data["total_sell"]
    if bc > 0 and slc > 0:
        verdict_icon, verdict_text = "🟡", f"加仓 {bc} 只，减持 {slc} 只，观望 {wc} 只"
    elif bc > 0:
        verdict_icon, verdict_text = "🟢", f"温和加仓 {bc} 只，观望 {wc} 只"
    elif slc > 0:
        verdict_icon, verdict_text = "🔴", f"减持 {slc} 只，观望 {wc} 只"
    else:
        verdict_icon, verdict_text = "⏸️", f"全部观望（{wc} 只）"

    sub_parts = [f"组合 D-Score = {data['avg_d']:+.3f}"]
    if tb > 0:
        sub_parts.append(f"建议投入 ¥{tb:,.0f}")
    if ts_ > 0:
        sub_parts.append(f"减仓 ¥{ts_:,.0f}")
    verdict_sub = " · ".join(sub_parts)

    rc = data["regime_color"]

    html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
:root{{--bg:transparent;--bg-base:#0D0E12;--bg-card:#1C1D22;--bg-elevated:#22242A;--border:#2C2D35;--brand:#A8E6CF;--up:#FF6B6B;--down:#4CAF50;--warn:#F59E0B;--info:#60A5FA;--text-primary:#FFFFFF;--text-secondary:#A0A0A0;--text-muted:#6B7280;--text-dim:#4B5563;--score-m:#60A5FA;--score-s:#A78BFA;--score-t:#F472B6;--score-f:#34D399;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);font-family:'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--text-primary);overflow-x:hidden;}}

/* L0 */
.L0{{display:flex;align-items:center;justify-content:space-between;background:linear-gradient(135deg,var(--bg-base),var(--bg-card));border:1px solid rgba(168,230,207,.15);border-radius:14px;padding:16px 24px;margin-bottom:14px;position:relative;overflow:hidden;animation:slideIn .5s ease-out;}}
.L0::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 20% 50%,rgba(168,230,207,.06),transparent 70%);pointer-events:none;}}
@keyframes slideIn{{from{{opacity:0;transform:translateY(-10px)}}to{{opacity:1;transform:none}}}}
.L0-icon{{font-size:38px;filter:drop-shadow(0 0 10px rgba(168,230,207,.25));animation:pulse 2.5s ease-in-out infinite;margin-right:14px;}}
@keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.06)}}}}
.L0-title{{font-size:19px;font-weight:700;color:var(--brand);text-shadow:0 0 16px rgba(168,230,207,.25);}}
.L0-sub{{font-size:12px;color:var(--text-muted);margin-top:2px;}}
.L0-right{{text-align:right;z-index:1;}}
.L0-date{{font-size:11px;color:var(--text-dim);}}
.regime-tag{{display:inline-block;padding:3px 10px;border-radius:16px;font-size:11px;font-weight:600;background:rgba(255,255,255,.03);margin-top:4px;border:1px solid {rc}55;color:{rc};}}

/* L1 */
.fund-list{{display:flex;flex-direction:column;gap:6px;margin-bottom:14px;}}
.fund-row{{background:var(--bg-card);border:1px solid var(--border);border-radius:10px;cursor:pointer;transition:all .3s cubic-bezier(.4,0,.2,1);overflow:hidden;animation:cardUp .4s ease-out backwards;}}
@keyframes cardUp{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
.fund-row:hover{{border-color:rgba(168,230,207,.2);background:rgba(168,230,207,.02);}}
.fund-row.active{{border-color:rgba(168,230,207,.35);background:rgba(168,230,207,.04);box-shadow:0 4px 24px rgba(0,0,0,.25),0 0 20px rgba(168,230,207,.06);}}
.fund-header{{display:grid;grid-template-columns:30px 140px 1fr auto;align-items:center;gap:10px;padding:10px 16px;}}
.fh-emoji{{font-size:20px;}} .fh-name{{font-size:14px;font-weight:600;}} .fh-sector{{font-size:10px;color:var(--text-muted);margin-top:1px;}}
.mini-flow{{display:flex;align-items:center;gap:3px;}}
.mini-dim{{display:flex;flex-direction:column;align-items:center;width:42px;padding:2px 0;}}
.mini-label{{font-size:8px;color:var(--text-dim);letter-spacing:.5px;text-transform:uppercase;}}
.mini-score{{font-size:13px;font-weight:700;line-height:1.2;}}
.mini-bar{{width:100%;height:2px;border-radius:1px;background:rgba(255,255,255,.06);margin-top:2px;overflow:hidden;}}
.mini-bar-fill{{height:100%;border-radius:1px;}}
.mini-arrow{{color:rgba(168,230,207,.2);font-size:10px;}}
.fh-verdict{{text-align:right;white-space:nowrap;}}
.fh-amt{{font-size:15px;font-weight:700;}} .fh-amt.buy{{color:var(--up);}} .fh-amt.sell{{color:var(--down);}} .fh-amt.wait{{color:var(--text-dim);font-size:13px;}}
.fh-reason{{font-size:10px;color:var(--text-muted);margin-top:1px;}}

/* L2 */
.fund-detail{{max-height:0;overflow:hidden;transition:max-height .5s cubic-bezier(.4,0,.2,1);opacity:0;}}
.fund-row.active .fund-detail{{max-height:2400px;opacity:1;transition:max-height .5s cubic-bezier(.4,0,.2,1),opacity .3s .1s;}}
.chain-wrap{{position:relative;padding:12px 16px 16px;}}
.chain-flow{{display:flex;align-items:stretch;gap:0;position:relative;z-index:2;}}
.chain-svg{{position:absolute;top:0;left:0;width:100%;height:100%;z-index:1;pointer-events:none;}}
.dim-card{{flex:1;margin:0 3px;border-radius:10px;padding:10px 12px;cursor:pointer;border:1px solid var(--border);background:var(--bg-card);transition:all .3s;position:relative;}}
.dim-card:hover{{border-color:rgba(168,230,207,.2);transform:translateY(-2px);box-shadow:0 6px 18px rgba(0,0,0,.25);}}
.dim-card.dim-active{{border-color:rgba(168,230,207,.35);background:rgba(168,230,207,.04);box-shadow:0 2px 16px rgba(0,0,0,.2),0 0 24px rgba(168,230,207,.08);}}
.dim-card.d-final{{border-color:rgba(168,230,207,.3);background:linear-gradient(135deg,rgba(168,230,207,.05),rgba(96,165,250,.03));}}
.dc-top{{display:flex;align-items:center;gap:6px;}} .dc-icon{{font-size:18px;}} .dc-meta{{flex:1;}}
.dc-label{{font-size:9px;color:var(--text-muted);letter-spacing:.8px;text-transform:uppercase;}}
.dc-score{{font-size:20px;font-weight:800;line-height:1.1;}} .dc-ring{{flex-shrink:0;}}
.ring-arc{{transition:stroke-dasharray 1s cubic-bezier(.4,0,.2,1);}}
.dc-bar{{height:3px;border-radius:2px;background:rgba(255,255,255,.05);margin:6px 0 2px;overflow:hidden;}}
.dc-bar-fill{{height:100%;border-radius:2px;width:0;transition:width 1s cubic-bezier(.4,0,.2,1);position:relative;}}
.dc-hint{{font-size:8px;color:var(--text-dim);text-align:center;margin-top:3px;}}
.dim-card.dim-active .dc-hint{{display:none;}}
.chain-arrow{{display:flex;align-items:center;color:rgba(168,230,207,.2);font-size:12px;flex-shrink:0;}}

/* Breadcrumb */
.breadcrumb{{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--text-dim);margin:6px 16px 4px;flex-wrap:wrap;}}
.bc-item{{cursor:pointer;padding:2px 6px;border-radius:6px;transition:all .2s;}}
.bc-item:hover{{background:rgba(168,230,207,.06);color:var(--brand);}}
.bc-item.bc-current{{color:var(--brand);font-weight:600;}}
.bc-sep{{color:var(--text-muted);}}

/* L3 */
.L3-panel{{overflow:hidden;transition:max-height .45s cubic-bezier(.4,0,.2,1),opacity .3s;max-height:0;opacity:0;margin:0 16px 8px;}}
.L3-panel.open{{max-height:2000px;opacity:1;padding-top:8px;}}
.L3-head{{font-size:12px;color:var(--brand);font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px;}}
.L3-head span{{font-size:10px;color:var(--text-muted);font-weight:400;}}
.L3-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;}}
.L3-card{{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);border-radius:10px;padding:10px 12px;cursor:pointer;transition:all .28s;position:relative;overflow:hidden;animation:factorIn .3s ease-out backwards;}}
@keyframes factorIn{{from{{opacity:0;transform:translateX(-8px)}}to{{opacity:1;transform:none}}}}
.L3-card:hover{{background:rgba(168,230,207,.03);border-color:rgba(168,230,207,.15);transform:translateY(-1px);}}
.L3-card.l3-active{{background:rgba(168,230,207,.05);border-color:rgba(168,230,207,.3);box-shadow:0 0 16px rgba(168,230,207,.06);}}
.L3-card::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;background:var(--brand);transform:scaleX(0);transition:transform .3s;}}
.L3-card.l3-active::after{{transform:scaleX(1);}}
.l3-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;}}
.l3-name{{font-size:11px;color:var(--text-secondary);}} .l3-val{{font-size:15px;font-weight:700;}}
.l3-summary{{font-size:9px;color:var(--text-muted);line-height:1.4;margin-top:3px;}}
.l3-bar{{height:3px;border-radius:2px;background:rgba(255,255,255,.04);margin-top:6px;overflow:hidden;}}
.l3-bar-fill{{height:100%;border-radius:2px;transition:width .6s;}}
.l3-expand-hint{{font-size:8px;color:var(--text-dim);text-align:right;margin-top:4px;}}
.L3-card.l3-active .l3-expand-hint{{color:var(--brand);}}

/* L4 */
.L4-panel{{overflow:hidden;transition:max-height .4s cubic-bezier(.4,0,.2,1),opacity .3s;max-height:0;opacity:0;margin:0 16px 4px;}}
.L4-panel.open{{max-height:1600px;opacity:1;padding:8px 0;}}
.L4-head{{font-size:11px;color:var(--warn);font-weight:600;margin-bottom:6px;padding-left:4px;}}
.L4-detail-box{{background:rgba(255,255,255,.015);border:1px solid rgba(255,255,255,.04);border-radius:10px;padding:10px 12px;animation:factorIn .3s ease-out;}}
.l4-row{{display:flex;justify-content:space-between;align-items:center;padding:3px 0;}}
.l4-label{{font-size:10px;color:var(--text-muted);}} .l4-val{{font-size:11px;font-weight:600;color:var(--text-secondary);}}
.l4-desc{{font-size:9px;color:var(--text-muted);line-height:1.5;margin:6px 0;}}

/* L5 scoring */
.L5-scoring{{margin-top:8px;background:rgba(255,255,255,.01);border:1px solid rgba(255,255,255,.03);border-radius:6px;padding:8px 10px;cursor:pointer;transition:all .2s;}}
.L5-scoring:hover{{border-color:rgba(245,158,11,.15);}}
.L5-scoring.open{{border-color:rgba(245,158,11,.2);background:rgba(245,158,11,.03);}}
.l5s-title{{font-size:9px;color:var(--warn);font-weight:600;margin-bottom:4px;}}
.l5s-rule{{display:flex;justify-content:space-between;padding:2px 0;font-size:9px;}}
.l5s-cond{{color:var(--text-muted);}} .l5s-result{{color:var(--text-muted);font-weight:600;}}

/* L6 method */
.L6-method{{margin-top:6px;background:rgba(255,255,255,.01);border:1px solid rgba(255,255,255,.02);border-radius:6px;padding:6px 8px;}}
.L6-method-title{{font-size:8px;color:var(--info);font-weight:600;margin-bottom:3px;}}
.L6-method-text{{font-size:8px;color:var(--text-dim);line-height:1.5;}}
.L6-method-text code{{background:rgba(255,255,255,.04);padding:1px 4px;border-radius:6px;font-family:monospace;color:var(--text-muted);}}

/* depth indicator */
.depth-indicator{{position:fixed;right:8px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:5px;z-index:100;}}
.depth-dot{{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);transition:all .3s;}}
.depth-dot.da{{background:var(--brand);border-color:var(--brand);box-shadow:0 0 6px rgba(168,230,207,.3);}}

/* summary */
.summary{{background:linear-gradient(135deg,rgba(168,230,207,.04),rgba(96,165,250,.02));border:1px solid rgba(168,230,207,.1);border-radius:14px;padding:12px 18px;font-size:12px;color:var(--text-secondary);line-height:1.7;margin-top:10px;}}
.summary strong{{color:var(--brand);}}
</style></head><body>

<div class="depth-indicator" id="depth-ind"></div>

<!-- L0 -->
<div class="L0">
  <div style="display:flex;align-items:center;z-index:1;">
    <div class="L0-icon">{verdict_icon}</div>
    <div><div class="L0-title">{verdict_text}</div>
    <div class="L0-sub">{verdict_sub}</div></div>
  </div>
  <div class="L0-right">
    <div class="L0-date">{data["date"]}</div>
    <div class="regime-tag">{data["regime_icon"]} {data["regime_name"]} · {data["regime_weights"]}</div>
  </div>
</div>

<div class="fund-list" id="fund-list"></div>

<div class="summary"><strong>AI策略摘要：</strong>{commentary}</div>

<script>
const FUNDS = {funds_json};

function sc(v){{return v>=.3?'#FF6B6B':v>=0?'#60A5FA':v>=-.3?'#F59E0B':'#4CAF50';}}
function bp(v){{return Math.max(5,Math.min(95,(v+2)/4*100));}}

let activeIdx=-1, activeDim=null, activeFactor=-1, showScoring=false;

function resetBelow(lv){{
  if(lv<=1){{activeDim=null;activeFactor=-1;showScoring=false;}}
  if(lv<=2){{activeFactor=-1;showScoring=false;}}
  if(lv<=3){{showScoring=false;}}
}}
function calcDepth(){{
  if(activeIdx<0) return 0;
  if(!activeDim) return 2;
  if(activeFactor<0) return 3;
  if(!showScoring) return 4;
  return 6;
}}
function renderDepth(){{
  const labels=['L0裁决','L1列表','L2决策链','L3子因子','L4指标','L5评分','L6方法论'];
  const d=calcDepth();
  let h='';
  labels.forEach((l,i)=>{{h+='<div class="depth-dot'+(i<=d?' da':'')+'" title="'+l+'"></div>';}});
  document.getElementById('depth-ind').innerHTML=h;
}}

function buildBreadcrumb(f){{
  let items=['<span class="bc-item" onclick="event.stopPropagation();activeIdx=-1;resetBelow(0);render();">全部基金</span>'];
  items.push('<span class="bc-sep">›</span><span class="bc-item'+(activeDim?'':' bc-current')+'" onclick="event.stopPropagation();resetBelow(1);render();">'+f.name+'</span>');
  if(activeDim){{
    const dm=f.dims[activeDim];
    items.push('<span class="bc-sep">›</span><span class="bc-item'+(activeFactor<0?' bc-current':'')+'" onclick="event.stopPropagation();resetBelow(2);render();">'+activeDim+' '+dm.label+'</span>');
    if(activeFactor>=0 && dm.factors[activeFactor]){{
      items.push('<span class="bc-sep">›</span><span class="bc-item bc-current" onclick="event.stopPropagation();resetBelow(3);render();">'+dm.factors[activeFactor].name+'</span>');
    }}
  }}
  return '<div class="breadcrumb">'+items.join('')+'</div>';
}}

function render(){{
  const el=document.getElementById('fund-list');
  let html='';
  FUNDS.forEach((f,i)=>{{
    const isActive=i===activeIdx;
    const emoji=f.type==='buy'?'🟢':f.type==='sell'?'🔴':'⏸️';
    const amtCls=f.type;
    const amtTxt=f.type==='buy'?('+¥'+f.amount.toLocaleString()):f.type==='sell'?('-¥'+f.amount.toLocaleString()):'观望';
    let miniHtml='';
    ['M','S','T','F'].forEach((k,di)=>{{
      const d=f.dims[k],c=sc(d.score);
      miniHtml+='<div class="mini-dim"><div class="mini-label">'+k+'</div><div class="mini-score" style="color:'+c+'">'+(d.score>=0?'+':'')+d.score.toFixed(1)+'</div><div class="mini-bar"><div class="mini-bar-fill" style="width:'+bp(d.score)+'%;background:'+c+'"></div></div></div>';
      if(di<3) miniHtml+='<div class="mini-arrow">→</div>';
    }});
    miniHtml+='<div class="mini-arrow">=</div>';
    const dColor=sc(f.d);
    miniHtml+='<div class="mini-dim" style="min-width:50px"><div class="mini-label" style="color:var(--brand)">D</div><div class="mini-score" style="color:'+dColor+';font-size:15px;font-weight:800">'+(f.d>=0?'+':'')+f.d.toFixed(2)+'</div></div>';
    html+='<div class="fund-row'+(isActive?' active':'')+'" onclick="toggleFund('+i+')" style="animation-delay:'+(i*0.04)+'s">';
    html+='<div class="fund-header"><div class="fh-emoji">'+emoji+'</div>';
    html+='<div><div class="fh-name">'+f.name+'</div><div class="fh-sector">'+f.sector+' · '+f.code+'</div></div>';
    html+='<div class="mini-flow">'+miniHtml+'</div>';
    html+='<div class="fh-verdict"><div class="fh-amt '+amtCls+'">'+amtTxt+'</div><div class="fh-reason">'+f.reason+'</div></div></div>';
    html+='<div class="fund-detail">';
    if(isActive){{ html+=buildBreadcrumb(f); html+=buildChain(f,i); }}
    html+='</div>';
    html+='<div class="L3-panel'+(isActive&&activeDim?' open':'')+'">';
    if(isActive&&activeDim) html+=buildL3(f);
    html+='</div>';
    html+='<div class="L4-panel'+(isActive&&activeDim&&activeFactor>=0?' open':'')+'">';
    if(isActive&&activeDim&&activeFactor>=0) html+=buildL4(f);
    html+='</div>';
    html+='</div>';
  }});
  el.innerHTML=html;
  setTimeout(()=>{{
    el.querySelectorAll('.dc-bar-fill').forEach(b=>{{b.style.width=b.dataset.w+'%';}});
    el.querySelectorAll('.ring-arc').forEach(a=>{{a.setAttribute('stroke-dasharray',a.dataset.target+' '+a.dataset.circ);}});
  }},80);
  if(activeIdx>=0) setTimeout(()=>drawChainSvg(activeIdx),300);
  renderDepth();
}}

function toggleFund(i){{
  if(activeIdx===i){{activeIdx=-1;resetBelow(0);}} else {{activeIdx=i;resetBelow(1);}}
  render();
}}

function buildChain(f,fi){{
  const keys=['M','S','T','F','D'];
  let html='<div class="chain-wrap"><svg class="chain-svg" id="csv-'+fi+'"></svg><div class="chain-flow">';
  keys.forEach((k,i)=>{{
    const isD=k==='D';
    const d=isD?{{score:f.d,weight:1,icon:'🎯',label:'综合'}}:f.dims[k];
    const c=sc(d.score);
    const wPct=Math.round(d.weight*100);
    const circ=2*Math.PI*16; const filled=circ*d.weight;
    const isDimActive=activeDim===k;
    let ring='';
    if(!isD){{
      ring='<svg width="40" height="40" viewBox="0 0 40 40" class="dc-ring"><circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,.05)" stroke-width="3"/><circle cx="20" cy="20" r="16" fill="none" stroke="'+c+'" stroke-width="3" stroke-dasharray="0 '+circ.toFixed(1)+'" stroke-linecap="round" transform="rotate(-90 20 20)" class="ring-arc" data-target="'+filled.toFixed(1)+'" data-circ="'+circ.toFixed(1)+'"/><text x="20" y="24" text-anchor="middle" fill="#A0A0A0" font-size="10" font-weight="700">'+wPct+'%</text></svg>';
    }}
    html+='<div class="dim-card'+(isD?' d-final':'')+(isDimActive?' dim-active':'')+'" onclick="event.stopPropagation();clickDim(\\\''+k+'\\\')">';
    html+='<div class="dc-top"><div class="dc-icon">'+d.icon+'</div>';
    html+='<div class="dc-meta"><div class="dc-label">'+k+' '+d.label+'</div>';
    html+='<div class="dc-score" style="color:'+c+'">'+(d.score>=0?'+':'')+d.score.toFixed(2)+'</div></div>'+ring+'</div>';
    html+='<div class="dc-bar"><div class="dc-bar-fill" data-w="'+bp(d.score)+'" style="background:'+(isD?'linear-gradient(90deg,#F59E0B,'+c+')':c)+'"></div></div>';
    if(!isD) html+='<div class="dc-hint">点击展开 '+(d.factors?d.factors.length:0)+' 个子因子 ▾</div>';
    html+='</div>';
    if(i<keys.length-1) html+='<div class="chain-arrow">→</div>';
  }});
  html+='</div></div>';
  return html;
}}

function clickDim(dim){{
  if(dim==='D') return;
  if(activeDim===dim){{activeDim=null;}} else {{activeDim=dim;}}
  resetBelow(2);
  render();
}}

function buildL3(f){{
  if(!activeDim||activeDim==='D') return '';
  const d=f.dims[activeDim];
  if(!d.factors||d.factors.length===0) return '<div style="padding:8px;font-size:11px;color:#4B5563;">暂无该维度详细因子数据</div>';
  let html='<div class="L3-head">'+d.icon+' '+activeDim+' '+d.label+' — '+d.factors.length+'个子因子 <span>权重'+Math.round(d.weight*100)+'% · 得分'+(d.score>=0?'+':'')+d.score.toFixed(2)+'</span></div>';
  html+='<div class="L3-grid">';
  d.factors.forEach((fac,fi)=>{{
    const c=sc(fac.val);
    const isActive=activeFactor===fi;
    html+='<div class="L3-card'+(isActive?' l3-active':'')+'" onclick="event.stopPropagation();clickL3('+fi+')" style="animation-delay:'+(fi*0.06)+'s">';
    html+='<div class="l3-top"><span class="l3-name">'+(fac.icon||'')+' '+fac.name+'</span><span class="l3-val" style="color:'+c+'">'+(fac.val>=0?'+':'')+fac.val.toFixed(2)+'</span></div>';
    if(fac.summary) html+='<div class="l3-summary">'+fac.summary+'</div>';
    if(fac.detail) html+='<div class="l3-summary" style="color:#A0A0A0;margin-top:2px;">'+fac.detail+'</div>';
    html+='<div class="l3-bar"><div class="l3-bar-fill" style="width:'+bp(fac.val)+'%;background:'+c+'"></div></div>';
    html+='<div class="l3-expand-hint">'+(isActive?'▾ 已展开':'▸ 点击查看详情')+'</div>';
    html+='</div>';
  }});
  html+='</div>';
  return html;
}}

function clickL3(fi){{
  if(activeFactor===fi){{activeFactor=-1;}} else {{activeFactor=fi;}}
  showScoring=false;
  render();
}}

function buildL4(f){{
  if(!activeDim||activeFactor<0) return '';
  const d=f.dims[activeDim];
  const fac=d.factors[activeFactor];
  if(!fac) return '';
  const c=sc(fac.val);

  let html='<div class="L4-head">📐 '+fac.name+' 详细分析</div>';
  html+='<div class="L4-detail-box">';

  // 基本信息
  html+='<div class="l4-row"><span class="l4-label">因子评分</span><span class="l4-val" style="color:'+c+'">'+(fac.val>=0?'+':'')+fac.val.toFixed(2)+'</span></div>';
  if(fac.weight) html+='<div class="l4-row"><span class="l4-label">因子权重</span><span class="l4-val">'+(fac.weight*100).toFixed(0)+'%</span></div>';
  if(fac.detail) html+='<div class="l4-row"><span class="l4-label">当前数据</span><span class="l4-val">'+fac.detail+'</span></div>';
  if(fac.summary) html+='<div class="l4-desc">'+fac.summary+'</div>';

  // L5: Scoring rules
  if(fac.scoring && fac.scoring.length>0){{
    html+='<div class="L5-scoring'+(showScoring?' open':'')+'" onclick="event.stopPropagation();showScoring=!showScoring;render();">';
    html+='<div class="l5s-title">📏 评分规则 '+(showScoring?'▾':'▸ 点击查看')+'</div>';
    if(showScoring){{
      fac.scoring.forEach(r=>{{
        html+='<div class="l5s-rule"><span class="l5s-cond">'+r.cond+'</span><span class="l5s-result">→ '+r.result+'</span></div>';
      }});
      // L6: Method
      if(fac.method){{
        html+='<div class="L6-method"><div class="L6-method-title">🔧 方法论 (factor_model.py)</div><div class="L6-method-text"><code>'+fac.method+'</code></div></div>';
      }}
    }}
    html+='</div>';
  }} else if(fac.method) {{
    // No scoring rules but has method
    html+='<div class="L5-scoring'+(showScoring?' open':'')+'" onclick="event.stopPropagation();showScoring=!showScoring;render();">';
    html+='<div class="l5s-title">🔧 方法论 '+(showScoring?'▾':'▸ 点击查看')+'</div>';
    if(showScoring){{
      html+='<div class="L6-method"><div class="L6-method-text"><code>'+fac.method+'</code></div></div>';
    }}
    html+='</div>';
  }}

  html+='</div>';
  return html;
}}

function drawChainSvg(fi){{
  const svg=document.getElementById('csv-'+fi);
  if(!svg) return;
  const wrap=svg.parentElement;
  const cards=wrap.querySelectorAll('.dim-card');
  if(cards.length<2) return;
  const wr=wrap.getBoundingClientRect();
  svg.setAttribute('viewBox','0 0 '+wr.width+' '+wr.height);
  let paths='<defs><filter id="g2"><feGaussianBlur stdDeviation="2.5" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>';
  for(let i=0;i<cards.length-1;i++){{
    const a=cards[i].getBoundingClientRect(),b=cards[i+1].getBoundingClientRect();
    const x1=a.right-wr.left,y1=a.top+a.height/2-wr.top;
    const x2=b.left-wr.left,y2=b.top+b.height/2-wr.top;
    const cx1=x1+(x2-x1)*.4,cx2=x2-(x2-x1)*.4;
    const f=FUNDS[fi];
    const dk=['M','S','T','F'][i];
    const w=dk?f.dims[dk].weight:.25;
    const thick=Math.max(1.5,w*9);
    const c=dk?sc(f.dims[dk].score):sc(f.d);
    const pid='p'+fi+'_'+i;
    paths+='<path id="'+pid+'" d="M'+x1+','+y1+' C'+cx1+','+y1+' '+cx2+','+y2+' '+x2+','+y2+'" fill="none" stroke="'+c+'" stroke-width="'+thick.toFixed(1)+'" opacity=".18" filter="url(#g2)" stroke-linecap="round"/>';
    for(let p=0;p<2;p++){{
      const delay=(p*1.3+i*0.35).toFixed(1),dur=(2+Math.random()*.6).toFixed(1),r=(thick*.3+.8).toFixed(1);
      paths+='<circle r="'+r+'" fill="'+c+'" opacity="0"><animateMotion dur="'+dur+'s" begin="'+delay+'s" repeatCount="indefinite"><mpath href="#'+pid+'"/></animateMotion><animate attributeName="opacity" values="0;.85;.85;0" dur="'+dur+'s" begin="'+delay+'s" repeatCount="indefinite"/></circle>';
    }}
  }}
  svg.innerHTML=paths;
}}

render();
</script></body></html>'''

    return html
