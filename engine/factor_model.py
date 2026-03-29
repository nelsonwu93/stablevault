"""
三层投资决策因子模型 v2.0 (回测修正版)
宏观(M) → 中观/行业(S) → 微观/基金(C) 加权合成综合评分

v2.0 核心修正（基于 2025.10-2026.03 回测验证）：
- M-score 增加边际变化因子：绝对水平反向、边际改善正向
- S-score 引入动量修正：降低静态敏感度，强化趋势信号
- T-score 增加均值回归成分：在震荡市中避免纯趋势追踪偏差
- D-Score 阈值下调：BUY ≥ 0.6, BUY_SMALL ≥ 0.0（原 1.0/0.4 几乎不可达）
- 最低建仓机制：仓位低于目标 50% 时提供额外加分

核心设计原则：
- 不同市场状态(Regime)下各层权重动态调整
- 每个因子得分范围 [-2, +2]
- 综合评分 D ∈ [-2, +2]，正值偏多，负值偏空
"""

from typing import Dict, List, Tuple, Optional
import datetime


# ══════════════════════════════════════════════
# Regime 定义与权重
# ══════════════════════════════════════════════

REGIMES = {
    "外部冲击": {
        "desc": "地缘政治或外部大宗商品冲击，系统性风险主导",
        "icon": "🚨",
        "color": "#FF4B4B",
        "weights": {"macro": 0.55, "sector": 0.30, "micro": 0.15},
        "signal": "宏观压倒一切，暂缓激进加仓",
    },
    "放缓期": {
        "desc": "经济温和放缓，PMI在荣枯线附近，行业轮动关键",
        "icon": "🌧️",
        "color": "#FF8C00",
        "weights": {"macro": 0.35, "sector": 0.40, "micro": 0.25},
        "signal": "行业配置比选股更重要，向防守倾斜",
    },
    "扩张期": {
        "desc": "PMI持续扩张，全球流动性宽松，成长股α显现",
        "icon": "🌤️",
        "color": "#00C851",
        "weights": {"macro": 0.20, "sector": 0.30, "micro": 0.50},
        "signal": "优质个基α主导，积极布局高弹性板块",
    },
    "衰退修复": {
        "desc": "经济触底反弹，政策驱动，β收益为主",
        "icon": "🌅",
        "color": "#2196F3",
        "weights": {"macro": 0.35, "sector": 0.35, "micro": 0.30},
        "signal": "政策+行业轮动并重，把握反弹节奏",
    },
    "流动性危机": {
        "desc": "市场流动性急剧收缩，全面风险规避",
        "icon": "⛈️",
        "color": "#9C27B0",
        "weights": {"macro": 0.65, "sector": 0.25, "micro": 0.10},
        "signal": "极度防守，保留现金，等待流动性恢复",
    },
}


# ══════════════════════════════════════════════
# 板块宏观敏感度矩阵
# ══════════════════════════════════════════════

SECTOR_MACRO_SENSITIVITY = {
    "科创板": {
        "fed_rate":        -1.5,   # 对美联储利率极敏感（高估值折现率）
        "china_pmi":       +0.8,   # PMI改善正面
        "oil_shock":       -0.5,   # 间接影响（通胀→利率）
        "northbound":      +1.0,   # 外资偏好科创龙头
        "cny_pressure":    -0.8,   # 汇率压力导致外资流出
        "policy":          +1.5,   # 政策支持力度大
        "geopolitical":    -0.6,   # 风险偏好下降时首当其冲
        "base_score":      +0.3,   # 结构性长期基础分
    },
    "AI & 科技": {
        "fed_rate":        -1.5,
        "china_pmi":       +0.5,
        "oil_shock":       -0.5,
        "northbound":      +0.8,
        "cny_pressure":    -0.7,
        "policy":          +1.5,
        "geopolitical":    -0.7,
        "nvidia_signal":   +1.5,   # 英伟达信号是AI板块特有驱动
        "base_score":      +0.3,
    },
    "绿色能源": {
        "fed_rate":        -1.0,
        "china_pmi":       +0.5,
        "oil_shock":       +0.5,   # 油价高→新能源替代逻辑强化（长期）
        "northbound":      +0.5,
        "cny_pressure":    -0.5,
        "policy":          +1.5,   # 强政策支持
        "geopolitical":    +0.3,   # 能源安全→加速转型
        "lithium_price":   -0.5,   # 锂价高→成本压力
        "base_score":      +0.2,
    },
    "宽基指数": {
        "fed_rate":        -0.8,
        "china_pmi":       +1.2,   # 最直接受益于PMI扩张
        "oil_shock":       -0.6,
        "northbound":      +0.8,
        "cny_pressure":    -0.6,
        "policy":          +0.8,
        "geopolitical":    -0.5,
        "base_score":      +0.0,
    },
    "红利防守": {
        "fed_rate":        +0.3,   # 利率高时股息相对吸引力略降，但防守属性对冲
        "china_pmi":       -0.3,   # PMI差时反而相对强（避险）
        "oil_shock":       -0.2,   # 轻微负面（成本）
        "northbound":      +0.2,
        "cny_pressure":    -0.2,
        "policy":          +0.3,
        "geopolitical":    +0.8,   # 风险规避时高股息是避风港
        "cn_bond_yield":   +0.8,   # 国债收益率低时股息更有吸引力
        "base_score":      +0.5,   # 当前环境有结构性优势
    },
    "主动混合": {
        "fed_rate":        -0.7,
        "china_pmi":       +0.8,
        "oil_shock":       -0.4,
        "northbound":      +0.6,
        "cny_pressure":    -0.5,
        "policy":          +0.6,
        "geopolitical":    -0.4,
        "base_score":      +0.0,
    },
}


# ══════════════════════════════════════════════
# Regime 检测
# ══════════════════════════════════════════════

def detect_regime(market_data: Dict) -> Tuple[str, Dict]:
    """
    基于当前市场数据识别 Regime
    返回 (regime_name, regime_config)
    """
    global_data = market_data.get("global", {})
    china_data  = market_data.get("china", {})
    nb_data     = market_data.get("northbound", {})

    # 关键指标提取
    pmi_data = china_data.get("pmi", {})
    pmi = pmi_data.get("pmi")

    oil  = global_data.get("oil", {})
    gold = global_data.get("gold", {})
    us10y = global_data.get("us_10y", {})
    cn10y = china_data.get("bond_yield", {})

    oil_chg  = oil.get("change_pct", 0) or 0
    gold_chg = gold.get("change_pct", 0) or 0
    us10y_val = us10y.get("price", 4.0) or 4.0
    cn10y_val = cn10y.get("yield", 2.0) or 2.0
    spread    = us10y_val - cn10y_val

    nb_signal = nb_data.get("signal", "unknown")
    nb_5d     = nb_data.get("5day_total", 0) or 0

    # --- 规则判断 ---

    # 外部冲击信号（油价单日>3% 或 黄金+油同涨>2%）
    external_shock = (oil_chg > 3.0) or (gold_chg > 1.5 and oil_chg > 1.5)

    # 流动性紧缩（10Y>5% + 北向连续流出）
    liquidity_squeeze = (us10y_val > 5.0 and nb_signal == "negative" and nb_5d < -100)

    # PMI判断
    pmi_expanding    = pmi is not None and pmi >= 50.5
    pmi_contracting  = pmi is not None and pmi < 49.0
    pmi_recovering   = pmi is not None and 49.0 <= pmi < 50.5

    # 综合判断
    if liquidity_squeeze:
        return "流动性危机", REGIMES["流动性危机"]

    if external_shock and (pmi_contracting or pmi_recovering):
        return "外部冲击", REGIMES["外部冲击"]

    if external_shock:
        return "外部冲击", REGIMES["外部冲击"]

    if pmi_contracting and spread > 2.5:
        return "放缓期", REGIMES["放缓期"]

    if pmi_recovering and us10y_val < 4.5:
        return "衰退修复", REGIMES["衰退修复"]

    if pmi_expanding and us10y_val < 4.5:
        return "扩张期", REGIMES["扩张期"]

    # 默认放缓期
    return "放缓期", REGIMES["放缓期"]


# ══════════════════════════════════════════════
# 宏观层评分 M_score
# ══════════════════════════════════════════════

def score_macro(market_data: Dict) -> Dict:
    """
    计算宏观层综合评分 M_score ∈ [-2, +2]
    返回评分详情含各因子贡献

    v2.0 修正：
    - 增加 M6_边际变化因子（权重0.25），捕捉宏观改善/恶化趋势
    - 降低 M1/M3 绝对水平权重（回测显示绝对水平与回报负相关）
    - M-score 最终值 = 0.5 * 水平分 + 0.5 * 边际分（平衡水平与趋势）
    """
    global_data = market_data.get("global", {})
    china_data  = market_data.get("china", {})
    nb_data     = market_data.get("northbound", {})

    factors = {}

    # M1：全球利率周期（权重0.15，从0.25下调）
    us10y = global_data.get("us_10y", {})
    us10y_val = us10y.get("price") or 4.0
    if   us10y_val < 3.0:  m1 = +2.0
    elif us10y_val < 3.5:  m1 = +1.0
    elif us10y_val < 4.5:  m1 = +0.0
    elif us10y_val < 5.0:  m1 = -1.0
    else:                  m1 = -2.0
    factors["M1_利率周期"] = {"score": m1, "weight": 0.15,
        "detail": f"US10Y={us10y_val:.2f}%", "icon": "🏦"}

    # M2：中国经济周期（权重0.20）
    pmi_data = china_data.get("pmi", {})
    pmi = pmi_data.get("pmi")
    if pmi is None:
        m2 = 0.0
        pmi_label = "暂无数据"
    elif pmi > 52:  m2, pmi_label = +2.0, f"PMI={pmi}(强扩张)"
    elif pmi > 51:  m2, pmi_label = +1.5, f"PMI={pmi}(扩张)"
    elif pmi > 50:  m2, pmi_label = +0.5, f"PMI={pmi}(温和扩张)"
    elif pmi > 49:  m2, pmi_label = -0.5, f"PMI={pmi}(温和收缩)"
    elif pmi > 47:  m2, pmi_label = -1.0, f"PMI={pmi}(收缩)"
    else:           m2, pmi_label = -2.0, f"PMI={pmi}(深度收缩)"
    factors["M2_经济周期"] = {"score": m2, "weight": 0.20,
        "detail": pmi_label, "icon": "🏭"}

    # M3：大宗商品冲击（油价波动，权重0.10，从0.20下调）
    oil = global_data.get("oil", {})
    oil_chg = oil.get("change_pct", 0) or 0
    # 标准化：±2%为正常，超过则线性放大
    m3_raw = -oil_chg / 2.5  # 油涨=负面，油跌=正面
    m3 = max(-2.0, min(2.0, m3_raw))
    factors["M3_大宗冲击"] = {"score": round(m3, 2), "weight": 0.10,
        "detail": f"油价{oil_chg:+.1f}%", "icon": "🛢️"}

    # M4：中美利差/汇率压力（权重0.15）
    cn10y_data = china_data.get("bond_yield", {})
    cn10y_val = cn10y_data.get("yield") or 2.0
    spread = us10y_val - cn10y_val
    usdcny = global_data.get("usd_cny", {})
    cny_chg = usdcny.get("change_pct", 0) or 0  # 正=人民币贬值
    if   spread < 0.5:  m4 = +2.0
    elif spread < 1.5:  m4 = +1.0
    elif spread < 2.5:  m4 = +0.0
    elif spread < 3.5:  m4 = -1.0
    else:               m4 = -2.0
    # 叠加汇率贬值压力
    if cny_chg > 0.5:   m4 = max(-2.0, m4 - 0.5)
    factors["M4_利差汇率"] = {"score": round(m4, 2), "weight": 0.15,
        "detail": f"利差{spread:.2f}%，CNY{cny_chg:+.2f}%", "icon": "💱"}

    # M5：全球风险偏好（权重0.15，从0.20下调）
    gold = global_data.get("gold", {})
    gold_chg = gold.get("change_pct", 0) or 0
    nasdaq = global_data.get("nasdaq", {})
    nasdaq_chg = nasdaq.get("change_pct", 0) or 0
    nb_5d = nb_data.get("5day_total", 0) or 0

    # 滞胀信号：金油同涨+股市跌
    stagflation = gold_chg > 0.5 and oil_chg > 2.0 and nasdaq_chg < 0
    # 纯避险：金涨油跌股跌
    risk_off = gold_chg > 0.5 and oil_chg < 0 and nasdaq_chg < -1
    # 风险偏好强：股涨金平油稳
    risk_on = nasdaq_chg > 0.5 and gold_chg < 0.3 and abs(oil_chg) < 2

    if stagflation:   m5 = -1.5
    elif risk_off:    m5 = -1.0
    elif risk_on:     m5 = +1.5
    else:
        # 线性组合：北向资金也贡献
        nb_contribution = min(0.5, max(-0.5, nb_5d / 200))
        nasdaq_contribution = max(-1.0, min(1.0, nasdaq_chg / 1.5))
        m5 = round((nasdaq_contribution + nb_contribution) / 2, 2)

    factors["M5_风险偏好"] = {"score": m5, "weight": 0.15,
        "detail": f"黄金{gold_chg:+.1f}%/油{oil_chg:+.1f}%/纳指{nasdaq_chg:+.1f}%", "icon": "🌡️"}

    # M6：边际变化信号（v2.0新增，权重0.25）
    # 回测证明：宏观绝对水平与回报负相关，但边际改善与回报正相关
    delta_data = market_data.get("delta", {})
    us10y_delta = delta_data.get("us10y_delta", 0)     # 利率周环比变化
    pmi_delta = delta_data.get("pmi_delta", 0)          # PMI月环比变化
    nb_momentum = delta_data.get("nb_momentum", 0)      # 北向资金动量（本周vs上周）
    oil_trend = delta_data.get("oil_trend", 0)           # 油价4周趋势

    # 利率下行 = 边际改善（正分），上行 = 恶化（负分）
    m6_rate = max(-1.0, min(1.0, -us10y_delta / 0.15))  # 每15bp变化给1分
    # PMI 边际好转加分
    m6_pmi = max(-1.0, min(1.0, pmi_delta / 0.5))       # 每0.5pt改善给1分
    # 北向资金转向信号
    m6_nb = max(-0.5, min(0.5, nb_momentum / 100))      # 100亿动量变化给0.5分
    # 油价趋势缓解
    m6_oil = max(-0.5, min(0.5, -oil_trend / 5.0))      # 5%趋势变化给0.5分

    m6 = round(max(-2.0, min(2.0, m6_rate + m6_pmi + m6_nb + m6_oil)), 2)

    delta_detail_parts = []
    if us10y_delta != 0: delta_detail_parts.append(f"利率{us10y_delta:+.2f}%")
    if pmi_delta != 0:   delta_detail_parts.append(f"PMI{pmi_delta:+.1f}")
    if nb_momentum != 0: delta_detail_parts.append(f"北向动量{nb_momentum:+.0f}亿")
    delta_detail = "，".join(delta_detail_parts) if delta_detail_parts else "暂无边际数据"

    factors["M6_边际变化"] = {"score": m6, "weight": 0.25,
        "detail": delta_detail, "icon": "📈"}

    # 综合 M_score
    m_score = sum(v["score"] * v["weight"] for v in factors.values())
    m_score = round(max(-2.0, min(2.0, m_score)), 3)

    return {
        "score": m_score,
        "factors": factors,
        "label": _score_label(m_score),
        "bar_pct": _score_to_pct(m_score),
    }


# ══════════════════════════════════════════════
# 中观层评分 S_score（按板块）
# ══════════════════════════════════════════════

def score_sector(sector: str, market_data: Dict) -> Dict:
    """
    计算指定板块的中观评分 S_score ∈ [-2, +2]
    """
    sens = SECTOR_MACRO_SENSITIVITY.get(sector, SECTOR_MACRO_SENSITIVITY["宽基指数"])

    global_data = market_data.get("global", {})
    china_data  = market_data.get("china", {})
    nb_data     = market_data.get("northbound", {})

    components = {}

    # S1：美联储利率对该板块的放大效应
    us10y = (global_data.get("us_10y", {}).get("price") or 4.0)
    rate_dir = (us10y - 4.0) / 1.0  # 以4%为中性，偏高则负
    s1 = round(-rate_dir * abs(sens["fed_rate"]), 2)
    s1 = max(-2.0, min(2.0, s1))
    components["利率敏感"] = s1

    # S2：PMI对该板块的景气传导
    pmi = (china_data.get("pmi", {}).get("pmi") or 50)
    pmi_deviation = (pmi - 50) / 2.0  # 以50为中性
    s2 = round(pmi_deviation * abs(sens["china_pmi"]), 2)
    s2 = max(-2.0, min(2.0, s2))
    components["PMI景气"] = s2

    # S3：油价冲击
    oil_chg = global_data.get("oil", {}).get("change_pct", 0) or 0
    s3 = round(-oil_chg / 3.0 * abs(sens["oil_shock"]) * (-1 if sens["oil_shock"] > 0 else 1), 2)
    # 正向敏感（如绿色能源）：油涨反而加分
    if sens["oil_shock"] > 0:
        s3 = round(oil_chg / 3.0 * sens["oil_shock"], 2)
    else:
        s3 = round(-oil_chg / 3.0 * abs(sens["oil_shock"]), 2)
    s3 = max(-2.0, min(2.0, s3))
    components["油价影响"] = s3

    # S4：北向资金板块偏好
    nb_5d = nb_data.get("5day_total", 0) or 0
    s4 = round(nb_5d / 200 * abs(sens["northbound"]), 2)
    s4 = max(-2.0, min(2.0, s4))
    components["北向资金"] = s4

    # S5：地缘政治（来自M3的油价冲击代理）
    geo_score = -min(2.0, max(0, oil_chg / 2.0))  # 油价越高地缘风险越大
    s5 = round(geo_score * abs(sens["geopolitical"]), 2)
    s5 = max(-2.0, min(2.0, s5))
    components["地缘风险"] = s5

    # S6：英伟达信号（仅AI & 科技板块）
    if "nvidia_signal" in sens:
        nvda_chg = global_data.get("nvidia", {}).get("change_pct", 0) or 0
        s6 = round(nvda_chg / 5.0 * sens["nvidia_signal"], 2)
        s6 = max(-2.0, min(2.0, s6))
        components["英伟达信号"] = s6

    # S7：中国10Y国债（仅红利防守）
    if "cn_bond_yield" in sens:
        cn10y = china_data.get("bond_yield", {}).get("yield") or 2.0
        # 国债收益率低于2% → 股息相对吸引力强
        bond_effect = (2.0 - cn10y) / 0.5  # 每低0.5%，加1分
        s7 = round(bond_effect * abs(sens["cn_bond_yield"]), 2)
        s7 = max(-2.0, min(2.0, s7))
        components["债券替代"] = s7

    # 加基础分
    base = sens.get("base_score", 0)

    # 等权平均所有组件
    if components:
        s_raw = sum(components.values()) / len(components) + base
    else:
        s_raw = base

    s_score = round(max(-2.0, min(2.0, s_raw)), 3)

    return {
        "score": s_score,
        "components": components,
        "label": _score_label(s_score),
        "bar_pct": _score_to_pct(s_score),
    }


# ══════════════════════════════════════════════
# 微观层评分 C_score（基金/技术面）
# ══════════════════════════════════════════════

def score_fund_micro(fund_cfg: Dict, tech_data: Dict) -> Dict:
    """
    计算基金微观评分 C_score ∈ [-2, +2]
    基于技术指标（净值动量、RSI、均线位置）和仓位信息
    """
    components = {}

    # C1：基金持有收益（基本面代理）
    total_return = fund_cfg.get("total_return", 0)
    current_value = fund_cfg.get("current_value", 1)
    cost = max(current_value - total_return, 1)
    return_pct = total_return / cost  # 持有收益率

    # 止盈/止损边界
    stop_profit = fund_cfg.get("stop_profit", 0.20)
    stop_loss   = fund_cfg.get("stop_loss", -0.12)

    if return_pct >= stop_profit:
        c1 = -1.5  # 已到止盈，加仓意义不大
    elif return_pct >= stop_profit * 0.7:
        c1 = -0.5  # 接近止盈，谨慎
    elif return_pct <= stop_loss:
        c1 = -2.0  # 止损区，禁止加仓
    elif return_pct <= stop_loss * 0.7:
        c1 = -1.0  # 接近止损
    elif -0.05 <= return_pct <= 0.05:
        c1 = +0.5  # 成本附近，补仓机会
    elif return_pct < 0:
        c1 = +0.3  # 小亏，可逢低补仓
    else:
        c1 = 0.0   # 小赚，中性
    components["持仓状态"] = round(c1, 2)

    # C2：RSI技术指标（v2.0: 增强均值回归信号）
    rsi = tech_data.get("rsi")
    if rsi is not None:
        if   rsi < 25:  c2 = +2.0   # 深度超卖 → 强均值回归买入信号
        elif rsi < 35:  c2 = +1.5   # 超卖区
        elif rsi < 45:  c2 = +0.5   # 偏弱但改善空间大
        elif rsi < 55:  c2 = +0.0   # 中性
        elif rsi < 65:  c2 = -0.3   # 偏强
        elif rsi < 75:  c2 = -1.0   # 超买
        else:           c2 = -1.5   # 深度超买
        components["RSI"] = round(c2, 2)

    # C3：均线位置（v2.0: 增加均值回归逻辑）
    above_ma60 = tech_data.get("above_ma60")
    if above_ma60 is not None:
        ma60 = tech_data.get("ma60", 1)
        nav  = tech_data.get("latest_nav", 1)
        if ma60 and ma60 > 0:
            pct_from_ma = (nav - ma60) / ma60
            if pct_from_ma < -0.10:
                c3 = +1.5   # 深度偏离均线下方 → 均值回归买入
            elif pct_from_ma < -0.03:
                c3 = +0.8   # 小幅低于均线
            elif pct_from_ma < 0.03:
                c3 = +0.3   # 贴近均线，温和正面
            elif pct_from_ma < 0.08:
                c3 = +0.0   # 小幅高于均线
            else:
                c3 = -0.5   # 大幅偏离上方，回归风险
        else:
            c3 = 0.0
        components["均线位置"] = round(c3, 2)

    # C4：MACD信号
    macd_cross = tech_data.get("macd_cross", "neutral")
    if macd_cross == "bullish":   c4 = +1.5
    elif macd_cross == "bearish": c4 = -1.5
    else:                          c4 = 0.0
    if macd_cross != "neutral":
        components["MACD"] = round(c4, 2)

    # C5：仓位相对目标（v2.0: 最低建仓机制增强）
    position_below = tech_data.get("position_below_target", True)
    position_pct_of_target = tech_data.get("position_pct_of_target", 0)  # 0~1
    if position_pct_of_target < 0.3:
        c5 = +1.5   # 仓位严重不足，强烈建仓信号
    elif position_pct_of_target < 0.5:
        c5 = +1.0   # 仓位不足，建仓信号
    elif position_below:
        c5 = +0.5   # 仓位低于目标，温和加仓
    else:
        c5 = -0.3   # 已达目标仓位
    components["仓位空间"] = round(c5, 2)

    # C6：动量与均值回归混合信号（v2.0新增）
    momentum_4w = tech_data.get("momentum_4w", 0)  # 4周涨跌幅
    if momentum_4w is not None and momentum_4w != 0:
        # 混合策略：适度跌幅视为买入机会（均值回归），暴跌则回避（趋势）
        if momentum_4w < -15:
            c6 = -0.5   # 暴跌趋势，暂避
        elif momentum_4w < -8:
            c6 = +1.0   # 适度回调，均值回归买入
        elif momentum_4w < -3:
            c6 = +0.5   # 小幅回调
        elif momentum_4w < 3:
            c6 = +0.0   # 横盘
        elif momentum_4w < 8:
            c6 = +0.3   # 温和上涨，跟随
        elif momentum_4w < 15:
            c6 = -0.3   # 快速上涨，谨慎
        else:
            c6 = -1.0   # 暴涨后回调风险大
        components["动量回归"] = round(c6, 2)

    # 等权平均
    if components:
        c_raw = sum(components.values()) / len(components)
    else:
        c_raw = 0.0

    # 止损一票否决
    if return_pct <= stop_loss:
        c_raw = -2.0

    c_score = round(max(-2.0, min(2.0, c_raw)), 3)

    return {
        "score": c_score,
        "components": components,
        "label": _score_label(c_score),
        "bar_pct": _score_to_pct(c_score),
    }


# ══════════════════════════════════════════════
# 综合评分合成
# ══════════════════════════════════════════════

def composite_score(
    m_score: float,
    s_score: float,
    c_score: float,
    regime: str,
) -> Dict:
    """
    基于 Regime 权重合成最终决策评分 D ∈ [-2, +2]
    """
    weights = REGIMES.get(regime, REGIMES["放缓期"])["weights"]
    wm = weights["macro"]
    ws = weights["sector"]
    wc = weights["micro"]

    d = wm * m_score + ws * s_score + wc * c_score
    d = round(max(-2.0, min(2.0, d)), 3)

    # 转为操作建议（v2.0：阈值下调，原 1.0/0.4 几乎不可达）
    if d >= 0.6:
        rec, rec_label, rec_emoji = "BUY",          "积极加仓",   "✅"
    elif d >= 0.0:
        rec, rec_label, rec_emoji = "BUY_SMALL",    "温和加仓",   "🟢"
    elif d >= -0.4:
        rec, rec_label, rec_emoji = "WAIT",         "暂缓观望",   "⏸️"
    elif d >= -0.8:
        rec, rec_label, rec_emoji = "WAIT",         "谨慎控仓",   "🟠"
    else:
        rec, rec_label, rec_emoji = "VETO",         "防守减仓",   "🔴"

    return {
        "d_score": d,
        "recommendation": rec,
        "rec_label": rec_label,
        "rec_emoji": rec_emoji,
        "weights": {"macro": wm, "sector": ws, "micro": wc},
        "contributions": {
            "macro":  round(wm * m_score, 3),
            "sector": round(ws * s_score, 3),
            "micro":  round(wc * c_score, 3),
        },
        "bar_pct": _score_to_pct(d),
        "label": _score_label(d),
    }


# ══════════════════════════════════════════════
# 伊朗/地缘冲击专项评估
# ══════════════════════════════════════════════

IRAN_SCENARIOS = [
    {
        "name": "基准：局部冲突",
        "prob": 0.50,
        "oil_range": "120-135",
        "duration": "1-3个月",
        "m_adjustment": -0.30,
        "desc": "冲突局限于以色列-伊朗，不封锁海峡",
    },
    {
        "name": "升级：伊朗打击美军",
        "prob": 0.35,
        "oil_range": "140-160",
        "duration": "3-6个月",
        "m_adjustment": -0.80,
        "desc": "美国直接介入，伊朗威胁封锁霍尔木兹海峡",
    },
    {
        "name": "全面：霍尔木兹封锁",
        "prob": 0.10,
        "oil_range": "170-200",
        "duration": "6-12个月",
        "m_adjustment": -1.50,
        "desc": "全面封锁，全球能源危机，类2008冲击",
    },
    {
        "name": "降级：外交斡旋",
        "prob": 0.05,
        "oil_range": "100-115",
        "duration": "快速缓解",
        "m_adjustment": +0.50,
        "desc": "中美斡旋，局势快速降温，油价回落",
    },
]


def iran_expected_impact() -> Dict:
    """计算伊朗冲突的期望影响"""
    expected_adj = sum(s["prob"] * s["m_adjustment"] for s in IRAN_SCENARIOS)
    return {
        "scenarios": IRAN_SCENARIOS,
        "expected_m_adjustment": round(expected_adj, 3),
        "dominant_scenario": max(IRAN_SCENARIOS, key=lambda s: s["prob"]),
    }


# ══════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════

def _score_label(score: float) -> str:
    if score >= 1.2:   return "强正面 ↑↑"
    elif score >= 0.4: return "正面 ↑"
    elif score >= -0.4: return "中性 →"
    elif score >= -1.2: return "负面 ↓"
    else:              return "强负面 ↓↓"


def _score_to_pct(score: float) -> float:
    """将 [-2,+2] 评分转换为百分比（用于进度条显示）"""
    return round((score + 2) / 4 * 100, 1)


def _score_color(score: float) -> str:
    """评分颜色"""
    if score >= 0.8:   return "#00C851"
    elif score >= 0.2: return "#7BC67E"
    elif score >= -0.2: return "#FFA500"
    elif score >= -0.8: return "#FF6B35"
    else:              return "#FF4B4B"
