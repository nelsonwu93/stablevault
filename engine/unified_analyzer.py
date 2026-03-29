"""
统一决策分析引擎 — Unified Analyzer
将三层因子模型、微观基本面、Checklist验证、LLM点评合并为单一分析流水线。

设计理念：
  一只基金 → 一次调用 → 一份完整报告（FundAnalysisReport）

四维评分体系：
  M_score  宏观层  ∈ [-2, +2]  利率/PMI/汇率/风险偏好
  S_score  行业层  ∈ [-2, +2]  板块景气/北向资金/政策
  T_score  技术面  ∈ [-2, +2]  RSI/MACD/均线/仓位（原 score_fund_micro）
  F_score  基本面  ∈ [-2, +2]  PE/成长性/集中度/经理（原 full_micro_analysis）

  D = wm*M + ws*S + wt*T + wf*F    （权重随 Regime 动态调整）

与旧系统的区别：
  - 旧系统有两个"micro"概念（技术面 vs 公司基本面），容易混淆
  - 旧系统 factor_model.composite_score 只有 M/S/C 三层
  - 本引擎拆分为明确的 T(Technical) + F(Fundamental) 四维
  - 集成 Checklist 验证 + LLM 点评，一次输出全部信息
"""

import logging
import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.factor_model import (
    REGIMES,
    detect_regime,
    score_macro,
    score_sector,
    score_fund_micro,
    _score_label,
    _score_to_pct,
    _score_color,
)
from engine.checklist import ChecklistAgent
from config import CHECKLIST_DIMENSIONS, PORTFOLIO_CONFIG, FUNDS
from data.fetcher import assess_fed_stance

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 四维权重表（按 Regime）
# ══════════════════════════════════════════════

REGIME_WEIGHTS_4D = {
    # v2.0 修正：提升 F(基本面) 权重（回测唯一正相关因子），降低 M(宏观) 权重（回测负相关）
    "外部冲击": {
        "macro": 0.35, "sector": 0.25, "technical": 0.15, "fundamental": 0.25,
        "desc": "宏观主导但基本面提供安全垫，避免过度恐慌",
    },
    "放缓期": {
        "macro": 0.20, "sector": 0.25, "technical": 0.20, "fundamental": 0.35,
        "desc": "基本面为锚，行业轮动辅助，降低宏观噪声",
    },
    "扩张期": {
        "macro": 0.10, "sector": 0.15, "technical": 0.25, "fundamental": 0.50,
        "desc": "基本面α主导，大胆布局优质基金",
    },
    "衰退修复": {
        "macro": 0.25, "sector": 0.20, "technical": 0.25, "fundamental": 0.30,
        "desc": "基本面+技术面共振把握反弹节奏",
    },
    "流动性危机": {
        "macro": 0.45, "sector": 0.20, "technical": 0.15, "fundamental": 0.20,
        "desc": "宏观防守为主，但优质基本面基金可逢低布局",
    },
}


# ══════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════

@dataclass
class ScoreDetail:
    """单维度评分详情"""
    score: float = 0.0
    weight: float = 0.0
    contribution: float = 0.0
    label: str = ""
    components: Dict = field(default_factory=dict)
    bar_pct: float = 50.0
    color: str = "#FFA500"


@dataclass
class FundAnalysisReport:
    """一只基金的完整分析报告"""
    # 基金基本信息
    fund_code: str = ""
    fund_name: str = ""
    fund_short: str = ""
    sector: str = ""
    sector_icon: str = ""

    # 当前 Regime
    regime_name: str = ""
    regime_icon: str = ""
    regime_signal: str = ""

    # 四维评分
    macro: ScoreDetail = field(default_factory=ScoreDetail)
    sector_score: ScoreDetail = field(default_factory=ScoreDetail)
    technical: ScoreDetail = field(default_factory=ScoreDetail)
    fundamental: ScoreDetail = field(default_factory=ScoreDetail)

    # 综合评分
    d_score: float = 0.0
    d_label: str = ""
    d_bar_pct: float = 50.0
    d_color: str = "#FFA500"

    # 操作建议
    recommendation: str = "WAIT"       # BUY / BUY_SMALL / WAIT / VETO / SELL
    rec_label: str = "暂缓观望"
    rec_emoji: str = "⏸️"
    suggested_amount: float = 0.0
    confidence: int = 1
    confidence_stars: str = "★☆☆☆☆"

    # Checklist 验证
    checklist_score: float = 0.0
    checklist_passed: int = 0
    checklist_total: int = 0
    checklist_veto: bool = False
    checklist_items: List[Dict] = field(default_factory=list)
    checklist_summary: str = ""

    # 基本面详情（来自 micro_analysis）
    holdings_summary: str = ""
    style_summary: str = ""
    manager_summary: str = ""
    fundamental_raw: Dict = field(default_factory=dict)

    # AI 点评
    commentary: str = ""
    risk_alerts: List[str] = field(default_factory=list)

    # 触发信息
    trigger_type: str = "macro"
    trigger_event: str = "定期分析"

    # 时间戳
    generated_at: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @property
    def is_actionable(self) -> bool:
        return self.recommendation in ("BUY", "BUY_SMALL", "SELL", "SELL_PARTIAL")


# ══════════════════════════════════════════════
# 基本面评分（F_score）
# ══════════════════════════════════════════════

def score_fundamental(fund_code: str) -> Dict:
    """
    计算基金基本面评分 F_score ∈ [-2, +2]
    整合 micro_analysis 的持仓分析 + 经理分析 + 风格分析
    """
    try:
        from engine.micro_analysis import (
            analyze_holdings_fundamentals,
            analyze_position_changes,
            analyze_fund_style,
            analyze_fund_manager,
        )
    except ImportError:
        logger.warning("micro_analysis 模块不可用，基本面评分设为 0")
        return {
            "score": 0.0,
            "components": {},
            "label": _score_label(0),
            "bar_pct": _score_to_pct(0),
            "holdings_summary": "基本面数据不可用",
            "style_summary": "",
            "manager_summary": "",
            "raw": {},
        }

    # 运行子分析
    holdings_result = analyze_holdings_fundamentals(fund_code)
    changes_result = analyze_position_changes(fund_code)
    style_result = analyze_fund_style(fund_code, holdings_result)
    manager_result = analyze_fund_manager(fund_code)

    components = {}

    # F1: 持仓估值 (加权平均PE)
    avg_pe = holdings_result.get("avg_pe")
    if avg_pe is not None:
        if avg_pe < 15:
            f1 = 1.0
        elif avg_pe < 25:
            f1 = 0.5
        elif avg_pe < 40:
            f1 = 0.0
        elif avg_pe < 60:
            f1 = -0.5
        else:
            f1 = -1.0
        components["持仓估值"] = round(f1, 2)

    # F2: 盈利成长性
    avg_growth = holdings_result.get("avg_growth_score", 0)
    f2 = round(max(-2, min(2, avg_growth * 1.0)), 2)
    components["盈利成长"] = f2

    # F3: 持仓集中度 (top3占比)
    top3_pct = holdings_result.get("top3_pct", 0)
    if top3_pct > 40:
        f3 = -0.5
    elif top3_pct > 30:
        f3 = -0.2
    elif top3_pct > 15:
        f3 = 0.2
    else:
        f3 = 0.0  # 过于分散也不一定好
    components["集中度"] = round(f3, 2)

    # F4: 基金经理能力
    mgr_score = manager_result.get("score", 0)
    f4 = round(max(-2, min(2, mgr_score)), 2)
    components["经理能力"] = f4

    # F5: 持仓变动稳定性
    turnover = changes_result.get("turnover_signal", "unknown")
    if turnover == "high":
        f5 = -0.3
    elif turnover == "low":
        f5 = 0.3
    else:
        f5 = 0.0
    components["持仓稳定"] = round(f5, 2)

    # 等权平均
    if components:
        f_raw = sum(components.values()) / len(components)
    else:
        f_raw = 0.0

    f_score = round(max(-2.0, min(2.0, f_raw)), 3)

    return {
        "score": f_score,
        "components": components,
        "label": _score_label(f_score),
        "bar_pct": _score_to_pct(f_score),
        "holdings_summary": holdings_result.get("summary", ""),
        "style_summary": style_result.get("summary", ""),
        "manager_summary": manager_result.get("summary", ""),
        "raw": {
            "holdings": holdings_result,
            "changes": changes_result,
            "style": style_result,
            "manager": manager_result,
        },
    }


# ══════════════════════════════════════════════
# 四维综合评分
# ══════════════════════════════════════════════

def composite_score_4d(
    m_score: float,
    s_score: float,
    t_score: float,
    f_score: float,
    regime: str,
) -> Dict:
    """
    四维加权综合评分 D ∈ [-2, +2]
    """
    w = REGIME_WEIGHTS_4D.get(regime, REGIME_WEIGHTS_4D["放缓期"])
    wm = w["macro"]
    ws = w["sector"]
    wt = w["technical"]
    wf = w["fundamental"]

    d = wm * m_score + ws * s_score + wt * t_score + wf * f_score
    d = round(max(-2.0, min(2.0, d)), 3)

    # 操作建议映射（v2.0：阈值下调，原 1.0/0.4 几乎不可达）
    if d >= 0.6:
        rec, label, emoji = "BUY", "积极加仓", "✅"
    elif d >= 0.0:
        rec, label, emoji = "BUY_SMALL", "温和加仓", "🟢"
    elif d >= -0.4:
        rec, label, emoji = "WAIT", "暂缓观望", "⏸️"
    elif d >= -0.8:
        rec, label, emoji = "WAIT", "谨慎控仓", "🟠"
    else:
        rec, label, emoji = "VETO", "防守减仓", "🔴"

    return {
        "d_score": d,
        "recommendation": rec,
        "rec_label": label,
        "rec_emoji": emoji,
        "weights": {"macro": wm, "sector": ws, "technical": wt, "fundamental": wf},
        "contributions": {
            "macro": round(wm * m_score, 3),
            "sector": round(ws * s_score, 3),
            "technical": round(wt * t_score, 3),
            "fundamental": round(wf * f_score, 3),
        },
        "bar_pct": _score_to_pct(d),
        "label": _score_label(d),
        "color": _score_color(d),
        "regime_desc": w["desc"],
    }


# ══════════════════════════════════════════════
# 操作金额计算
# ══════════════════════════════════════════════

def compute_action_amount(
    fund_cfg: Dict,
    recommendation: str,
    d_score: float,
    confidence: int,
    current_position_pct: float = 0.0,
) -> float:
    """
    根据综合评分和置信度计算建议操作金额

    v2.0 修正：
    - 渐进式建仓：单只基金每次加仓不超过总资本的2%
    - 最低建仓机制：WAIT + 仓位不足30% + D > -0.6 → 小额建仓
    - 柔性止损：分级减仓代替全量清仓
    """
    remaining = PORTFOLIO_CONFIG.get("remaining_to_invest", 222200)
    total_capital = PORTFOLIO_CONFIG.get("total_capital", 300000)
    batches = PORTFOLIO_CONFIG.get("entry_batches", 6)
    target_pct = fund_cfg.get("target_pct", 0.05)

    # 单只基金单次最大投入 = 总资本的2%
    max_per_action = total_capital * 0.02

    if recommendation in ("WAIT",):
        # v2.0: 最低建仓机制 — 仓位<30%目标且D不太差时小额建仓
        if current_position_pct < 0.30 and d_score > -0.6:
            target_alloc = target_pct * total_capital
            room = target_alloc * (1 - current_position_pct)
            amount = min(room * 0.10, 1500)
            return round(amount / 500) * 500 if amount >= 500 else 0.0
        return 0.0

    if recommendation == "VETO":
        return 0.0

    # 单批次该基金的基础金额
    base = remaining / batches * target_pct * 10

    # D-score 调节：D 越高买越多
    score_mult = max(0.3, min(2.0, 0.5 + d_score * 0.8))

    # 置信度调节
    conf_mult = max(0.5, confidence / 5.0)

    if recommendation == "BUY":
        # 积极加仓：目标仓位空间的 1/4
        amount = min(base * score_mult * conf_mult, max_per_action)
    elif recommendation == "BUY_SMALL":
        # 温和加仓：目标仓位空间的 1/6
        amount = min(base * 0.5 * conf_mult, max_per_action * 0.6)
    elif recommendation in ("SELL", "SELL_PARTIAL"):
        amount = base * 0.5  # 卖出金额参考
    else:
        amount = 0

    return round(amount / 500) * 500  # 取整到500


# ══════════════════════════════════════════════
# AI 点评生成
# ══════════════════════════════════════════════

def generate_commentary(report: FundAnalysisReport) -> str:
    """为单只基金生成一段自然语言分析点评"""
    parts = []

    # 开头：整体判断（v2.0：阈值适配新评分体系）
    if report.d_score >= 0.6:
        parts.append(f"{report.fund_short}当前综合评分较高（D={report.d_score:+.2f}），多维度信号偏积极，可积极加仓。")
    elif report.d_score >= 0.0:
        parts.append(f"{report.fund_short}综合评分温和偏正（D={report.d_score:+.2f}），可小幅建仓或加仓。")
    elif report.d_score >= -0.4:
        parts.append(f"{report.fund_short}综合评分中性偏弱（D={report.d_score:+.2f}），建议观望为主。")
    else:
        parts.append(f"{report.fund_short}综合评分偏低（D={report.d_score:+.2f}），多维度信号偏谨慎。")

    # 宏观环境
    regime_word = {
        "扩张期": "经济扩张有利于风险资产",
        "放缓期": "经济放缓需注重行业选择",
        "外部冲击": "外部冲击环境下宏观权重提升",
        "衰退修复": "经济触底反弹阶段把握节奏",
        "流动性危机": "流动性收紧建议极度防守",
    }
    parts.append(f"当前处于{report.regime_name}（{regime_word.get(report.regime_name, '')}）。")

    # 最强/最弱维度
    dims = [
        ("宏观", report.macro.score),
        ("行业", report.sector_score.score),
        ("技术面", report.technical.score),
        ("基本面", report.fundamental.score),
    ]
    strongest = max(dims, key=lambda x: x[1])
    weakest = min(dims, key=lambda x: x[1])
    if strongest[1] > 0.3:
        parts.append(f"主要支撑来自{strongest[0]}（{strongest[1]:+.2f}）。")
    if weakest[1] < -0.3:
        parts.append(f"主要拖累来自{weakest[0]}（{weakest[1]:+.2f}），需关注。")

    # 基本面亮点
    if report.holdings_summary:
        parts.append(f"持仓概况：{report.holdings_summary[:80]}。")

    # Checklist 提示
    if report.checklist_veto:
        parts.append(f"⚠️ Checklist触发一票否决，当前禁止操作。")
    elif report.checklist_score < 50:
        parts.append(f"Checklist评分偏低（{report.checklist_score:.0f}/100），建议谨慎。")

    return "".join(parts)


# ══════════════════════════════════════════════
# 风险提示生成
# ══════════════════════════════════════════════

def generate_risk_alerts(
    fund_cfg: Dict,
    report: FundAnalysisReport,
    market_data: Dict,
    tech_data: Dict,
) -> List[str]:
    """为单只基金生成风险提示列表"""
    alerts = []

    # 止盈提醒
    total_return = fund_cfg.get("total_return", 0)
    current_value = fund_cfg.get("current_value", 1)
    cost = max(current_value - total_return, 1)
    return_pct = total_return / cost
    stop_profit = fund_cfg.get("stop_profit", 0.20)
    stop_loss = fund_cfg.get("stop_loss", -0.12)

    if return_pct >= stop_profit * 0.8:
        alerts.append(f"持有收益{return_pct*100:.1f}%接近止盈线{stop_profit*100:.0f}%，注意止盈时机")
    if return_pct <= stop_loss * 0.7:
        alerts.append(f"持有亏损{return_pct*100:.1f}%接近止损线{stop_loss*100:.0f}%，请关注风险")

    # 高波动板块
    if fund_cfg.get("sector") in ("科创板", "AI & 科技"):
        alerts.append("高弹性板块，日波动可能达±3-5%，建议分批操作")

    # 技术面超买
    rsi = tech_data.get("rsi")
    if rsi and rsi > 70:
        alerts.append(f"RSI={rsi:.1f}超买，短期有回调压力")
    elif rsi and rsi < 30:
        alerts.append(f"RSI={rsi:.1f}超卖，可能是逢低布局机会")

    # QDII汇率
    if "QDII" in fund_cfg.get("name", "") or "全球" in fund_cfg.get("name", ""):
        alerts.append("QDII基金受汇率波动影响，关注人民币走势")

    # 宏观风险
    if report.regime_name in ("外部冲击", "流动性危机"):
        alerts.append(f"当前处于{report.regime_name}状态，系统性风险较高")

    # D-score 极端值
    if report.d_score < -1.0:
        alerts.append("综合评分深度负值，强烈建议回避加仓")

    return alerts if alerts else ["当前无特别风险提示"]


# ══════════════════════════════════════════════
# 触发类型自动检测
# ══════════════════════════════════════════════

def detect_trigger(
    fund_cfg: Dict,
    market_data: Dict,
    tech_data: Dict,
) -> Tuple[str, str]:
    """自动检测当前最相关的触发信号"""
    total_return = fund_cfg.get("total_return", 0)
    current_value = fund_cfg.get("current_value", 1)
    cost = max(current_value - total_return, 1)
    return_pct = total_return / cost

    # 止盈/止损优先
    if return_pct >= fund_cfg.get("stop_profit", 0.20) * 0.9:
        return "stoploss", f"持有收益率{return_pct*100:.1f}%接近止盈线"
    if return_pct <= fund_cfg.get("stop_loss", -0.12) * 0.8:
        return "stoploss", f"持有亏损{return_pct*100:.1f}%接近止损线"

    # 技术信号
    rsi_signal = tech_data.get("rsi_signal", "")
    if rsi_signal == "oversold":
        return "technical", f"RSI={tech_data.get('rsi', 0):.1f}超卖信号"
    if rsi_signal == "overbought":
        return "technical", f"RSI={tech_data.get('rsi', 0):.1f}超买信号"
    macd = tech_data.get("macd_cross", "neutral")
    if macd == "bullish":
        return "technical", "MACD金叉信号"
    if macd == "bearish":
        return "technical", "MACD死叉信号"

    # 宏观信号
    us10y_chg = market_data.get("global", {}).get("us_10y", {}).get("change_pct")
    fed_stance = assess_fed_stance(us10y_chg)
    if fed_stance in ("dovish", "dovish_strong"):
        return "macro", "美联储偏鸽派信号"
    if fed_stance in ("hawkish", "hawkish_strong"):
        return "macro", "美联储偏鹰派信号"

    return "macro", "定期宏观环境评估"


# ══════════════════════════════════════════════
# 核心入口：完整分析单只基金
# ══════════════════════════════════════════════

def analyze_fund_complete(
    fund_cfg: Dict,
    market_data: Dict,
    tech_data: Dict,
    portfolio: Dict,
    regime_name: str = None,
    regime_cfg: Dict = None,
    run_fundamental: bool = True,
) -> FundAnalysisReport:
    """
    单只基金完整分析的唯一入口。

    参数：
        fund_cfg:       基金配置 (来自 config.FUNDS)
        market_data:    宏观数据快照
        tech_data:      技术指标数据 (来自 fetcher 计算)
        portfolio:      当前持仓状态
        regime_name:    经济状态 (可选，不传则自动检测)
        regime_cfg:     Regime配置 (可选)
        run_fundamental: 是否运行基本面分析 (耗时较长，可关闭)

    返回：
        FundAnalysisReport - 包含所有评分、建议、点评的完整报告
    """
    report = FundAnalysisReport()
    report.generated_at = datetime.datetime.now().isoformat()

    # ── 基本信息 ──
    report.fund_code = fund_cfg["code"]
    report.fund_name = fund_cfg["name"]
    report.fund_short = fund_cfg.get("short", fund_cfg["name"])
    report.sector = fund_cfg.get("sector", "")
    report.sector_icon = fund_cfg.get("sector_icon", "📊")

    # ── Regime 检测 ──
    if regime_name is None:
        regime_name, regime_cfg = detect_regime(market_data)
    elif regime_cfg is None:
        regime_cfg = REGIMES.get(regime_name, REGIMES["放缓期"])

    report.regime_name = regime_name
    report.regime_icon = regime_cfg.get("icon", "🌧️")
    report.regime_signal = regime_cfg.get("signal", "")

    # ── 触发检测 ──
    report.trigger_type, report.trigger_event = detect_trigger(
        fund_cfg, market_data, tech_data
    )

    # ── 维度1: 宏观评分 M ──
    macro_result = score_macro(market_data)
    m = macro_result["score"]
    w4d = REGIME_WEIGHTS_4D.get(regime_name, REGIME_WEIGHTS_4D["放缓期"])

    report.macro = ScoreDetail(
        score=m,
        weight=w4d["macro"],
        contribution=round(w4d["macro"] * m, 3),
        label=macro_result["label"],
        components=macro_result.get("factors", {}),
        bar_pct=macro_result["bar_pct"],
        color=_score_color(m),
    )

    # ── 维度2: 行业评分 S ──
    sector_result = score_sector(fund_cfg.get("sector", "宽基指数"), market_data)
    s = sector_result["score"]

    report.sector_score = ScoreDetail(
        score=s,
        weight=w4d["sector"],
        contribution=round(w4d["sector"] * s, 3),
        label=sector_result["label"],
        components=sector_result.get("components", {}),
        bar_pct=sector_result["bar_pct"],
        color=_score_color(s),
    )

    # ── 维度3: 技术面评分 T ──
    tech_result = score_fund_micro(fund_cfg, tech_data)
    t = tech_result["score"]

    report.technical = ScoreDetail(
        score=t,
        weight=w4d["technical"],
        contribution=round(w4d["technical"] * t, 3),
        label=tech_result["label"],
        components=tech_result.get("components", {}),
        bar_pct=tech_result["bar_pct"],
        color=_score_color(t),
    )

    # ── 维度4: 基本面评分 F ──
    if run_fundamental:
        fund_result = score_fundamental(fund_cfg["code"])
    else:
        fund_result = {
            "score": 0.0, "components": {}, "label": "未分析",
            "bar_pct": 50.0, "holdings_summary": "", "style_summary": "",
            "manager_summary": "", "raw": {},
        }

    f = fund_result["score"]

    report.fundamental = ScoreDetail(
        score=f,
        weight=w4d["fundamental"],
        contribution=round(w4d["fundamental"] * f, 3),
        label=fund_result["label"],
        components=fund_result.get("components", {}),
        bar_pct=fund_result["bar_pct"],
        color=_score_color(f),
    )
    report.holdings_summary = fund_result.get("holdings_summary", "")
    report.style_summary = fund_result.get("style_summary", "")
    report.manager_summary = fund_result.get("manager_summary", "")
    report.fundamental_raw = fund_result.get("raw", {})

    # ── 四维综合评分 D ──
    comp = composite_score_4d(m, s, t, f, regime_name)
    report.d_score = comp["d_score"]
    report.d_label = comp["label"]
    report.d_bar_pct = comp["bar_pct"]
    report.d_color = comp["color"]

    # 初步建议来自 D-score
    d_rec = comp["recommendation"]
    d_label = comp["rec_label"]
    d_emoji = comp["rec_emoji"]

    # ── Checklist 验证 ──
    fed_stance = assess_fed_stance(
        market_data.get("global", {}).get("us_10y", {}).get("change_pct")
    )
    checklist_agent = ChecklistAgent(CHECKLIST_DIMENSIONS)
    cl_context = {
        "fund_cfg": fund_cfg,
        "market": {**market_data, "fed_stance": fed_stance},
        "technical": tech_data,
        "portfolio": portfolio,
        "fed_stance": fed_stance,
    }
    cl_result = checklist_agent.run(cl_context)

    report.checklist_score = cl_result["score"]
    report.checklist_passed = cl_result["passed_count"]
    report.checklist_total = cl_result["total_count"]
    report.checklist_veto = cl_result["veto_triggered"]
    report.checklist_items = cl_result["items"]
    report.checklist_summary = cl_result["summary"]

    # ── 最终建议 = D-score建议 ∩ Checklist验证 ──
    if cl_result["veto_triggered"]:
        # Checklist 一票否决覆盖 D-score 建议
        report.recommendation = "VETO"
        report.rec_label = "一票否决"
        report.rec_emoji = "🚨"
        report.confidence = 1
    elif d_rec in ("BUY", "BUY_SMALL") and cl_result["recommendation"] == "WAIT":
        # D想买但 Checklist 分数不够 → 降级
        report.recommendation = "WAIT"
        report.rec_label = "信号不一致，观望"
        report.rec_emoji = "⏸️"
        report.confidence = 2
    elif d_rec == "BUY" and cl_result["recommendation"] == "BUY_SMALL":
        # D想大买 Checklist 只同意小买 → 取保守
        report.recommendation = "BUY_SMALL"
        report.rec_label = "温和加仓"
        report.rec_emoji = "🟢"
        report.confidence = cl_result["confidence"]
    else:
        # 一致或 D 本身就是 WAIT/VETO
        report.recommendation = d_rec
        report.rec_label = d_label
        report.rec_emoji = d_emoji
        report.confidence = cl_result["confidence"]

    report.confidence_stars = "★" * report.confidence + "☆" * (5 - report.confidence)

    # ── 操作金额 ──
    report.suggested_amount = compute_action_amount(
        fund_cfg, report.recommendation, report.d_score, report.confidence
    )

    # ── 风险提示 ──
    report.risk_alerts = generate_risk_alerts(fund_cfg, report, market_data, tech_data)

    # ── AI 点评 ──
    report.commentary = generate_commentary(report)

    return report


# ══════════════════════════════════════════════
# 批量分析：扫描全部基金
# ══════════════════════════════════════════════

def analyze_all_funds(
    funds_config: List[Dict],
    market_data: Dict,
    tech_data_map: Dict,
    portfolio: Dict,
    run_fundamental: bool = True,
) -> List[FundAnalysisReport]:
    """
    一次性分析全部基金，共享 Regime 检测结果。

    参数：
        funds_config:   基金配置列表 (config.FUNDS)
        market_data:    宏观数据快照
        tech_data_map:  {fund_code: tech_data} 技术指标映射
        portfolio:      当前持仓状态
        run_fundamental: 是否运行基本面分析

    返回：
        按操作优先级排序的 FundAnalysisReport 列表
    """
    # 共享 Regime 检测
    regime_name, regime_cfg = detect_regime(market_data)

    def _analyze_one(fund):
        code = fund["code"]
        tech = tech_data_map.get(code, {})
        try:
            return analyze_fund_complete(
                fund_cfg=fund,
                market_data=market_data,
                tech_data=tech,
                portfolio=portfolio,
                regime_name=regime_name,
                regime_cfg=regime_cfg,
                run_fundamental=run_fundamental,
            )
        except Exception as e:
            logger.error(f"分析基金 {code} 失败: {e}")
            fallback = FundAnalysisReport()
            fallback.fund_code = code
            fallback.fund_name = fund["name"]
            fallback.fund_short = fund.get("short", fund["name"])
            fallback.sector = fund.get("sector", "")
            fallback.regime_name = regime_name
            fallback.regime_icon = regime_cfg.get("icon", "🌧️")
            fallback.d_score = 0.0
            fallback.recommendation = "WAIT"
            fallback.rec_label = "数据异常，观望"
            fallback.rec_emoji = "⏸️"
            fallback.confidence = 1
            fallback.confidence_stars = "★☆☆☆☆"
            fallback.commentary = f"{fund.get('short', fund['name'])}数据获取异常，建议观望。"
            fallback.risk_alerts = ["数据获取异常，建议人工确认"]
            return fallback

    # 使用线程池并行分析所有基金（IO密集型，线程数=基金数）
    reports = []
    with ThreadPoolExecutor(max_workers=min(len(funds_config), 8)) as executor:
        futures = {executor.submit(_analyze_one, f): f for f in funds_config}
        for future in as_completed(futures):
            reports.append(future.result())

    # 排序：可操作的优先，D-score 高的靠前
    priority = {
        "BUY": 0, "SELL": 0, "BUY_SMALL": 1,
        "SELL_PARTIAL": 1, "WAIT": 2, "VETO": 3,
    }
    reports.sort(key=lambda r: (priority.get(r.recommendation, 4), -r.d_score))

    return reports


# ══════════════════════════════════════════════
# 便捷函数：生成摘要统计
# ══════════════════════════════════════════════

def summarize_portfolio_status(reports: List[FundAnalysisReport]) -> Dict:
    """
    从全部基金分析报告中提取组合级别的摘要统计。
    用于仪表盘顶部展示。
    """
    if not reports:
        return {"total": 0, "avg_d": 0, "actions": {}, "regime": ""}

    total = len(reports)
    avg_d = round(sum(r.d_score for r in reports) / total, 3)

    # 操作分布
    actions = {}
    for r in reports:
        actions[r.recommendation] = actions.get(r.recommendation, 0) + 1

    # 板块平均 D-score
    sector_scores = {}
    for r in reports:
        if r.sector not in sector_scores:
            sector_scores[r.sector] = []
        sector_scores[r.sector].append(r.d_score)
    sector_avg = {k: round(sum(v)/len(v), 3) for k, v in sector_scores.items()}

    # 最强 / 最弱基金
    best = max(reports, key=lambda r: r.d_score)
    worst = min(reports, key=lambda r: r.d_score)

    return {
        "total": total,
        "avg_d_score": avg_d,
        "avg_d_label": _score_label(avg_d),
        "avg_d_color": _score_color(avg_d),
        "action_distribution": actions,
        "buy_count": actions.get("BUY", 0) + actions.get("BUY_SMALL", 0),
        "wait_count": actions.get("WAIT", 0),
        "veto_count": actions.get("VETO", 0),
        "sector_avg_d": sector_avg,
        "best_fund": {"code": best.fund_code, "name": best.fund_short, "d": best.d_score},
        "worst_fund": {"code": worst.fund_code, "name": worst.fund_short, "d": worst.d_score},
        "regime_name": reports[0].regime_name if reports else "",
        "regime_icon": reports[0].regime_icon if reports else "",
    }
