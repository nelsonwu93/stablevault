"""
基金智能监控系统 - 核心配置
Fund Monitor - Core Configuration

请在此文件中确认基金代码是否正确（可在天天基金网搜索确认）
"""

# ═══════════════════════════════════════════════════════════
# 投资组合总目标
# ═══════════════════════════════════════════════════════════
PORTFOLIO_CONFIG = {
    "total_target": 300_000,        # 总目标投资额（元）
    "risk_profile": "balanced",     # 风险偏好：conservative / balanced / aggressive
    "max_drawdown_alert": -0.15,    # 总仓位最大回撤预警线 -15%
    "entry_batches": 6,             # 分批入场计划批次数
    "remaining_to_invest": 222_200, # 剩余待入场资金（元）
}

# ═══════════════════════════════════════════════════════════
# 持仓基金配置
# code: 天天基金代码（如有误请在 https://fund.eastmoney.com 搜索更新）
# sector: 所属板块
# target_pct: 满仓时目标占比（平衡型配置）
# stop_profit: 止盈线（持有收益率）
# stop_loss:   止损线（持有收益率）
# ═══════════════════════════════════════════════════════════
FUNDS = [
    {
        "code": "290008",
        "name": "泰信发展主题混合",
        "short": "泰信主题",
        "sector": "主动混合",
        "sector_icon": "🎯",
        "current_value": 5415.68,
        "yesterday_return": 412.98,
        "total_return": 0.00,
        "target_pct": 0.04,
        "stop_profit": 0.20,
        "stop_loss": -0.12,
        "macro_drivers": ["china_pmi", "policy_stimulus"],
        "note": "主动管理型，关注基金经理操作"
    },
    {
        "code": "025778",
        "name": "东方阿尔法瑞享混合C",
        "short": "东方瑞享",
        "sector": "主动混合",
        "sector_icon": "🎯",
        "current_value": 9063.57,
        "yesterday_return": 643.48,
        "total_return": 531.78,
        "target_pct": 0.05,
        "stop_profit": 0.20,
        "stop_loss": -0.12,
        "macro_drivers": ["china_pmi", "northbound_flow"],
        "note": "主动管理型混合基金"
    },
    {
        "code": "017057",
        "name": "嘉实国证绿色电力ETF联接C",
        "short": "绿色电力",
        "sector": "绿色能源",
        "sector_icon": "⚡",
        "current_value": 9358.59,
        "yesterday_return": -83.82,
        "total_return": 358.59,
        "target_pct": 0.10,
        "stop_profit": 0.25,
        "stop_loss": -0.12,
        "macro_drivers": ["carbon_price", "china_energy_policy", "renewables_capacity"],
        "note": "绑定国内绿色电力建设，受电价政策影响大"
    },
    {
        "code": "021279",
        "name": "永赢上证科创板100指数增强C",
        "short": "科创100增强",
        "sector": "科创板",
        "sector_icon": "🚀",
        "current_value": 12069.46,
        "yesterday_return": 206.19,
        "total_return": 69.46,
        "target_pct": 0.12,
        "stop_profit": 0.25,
        "stop_loss": -0.12,
        "macro_drivers": ["fed_rate", "northbound_flow", "china_tech_policy", "nasdaq"],
        "note": "科创100含更多中小成长股，弹性大于科创50"
    },
    {
        "code": "008021",
        "name": "华富中证人工智能产业ETF联接C",
        "short": "AI产业",
        "sector": "AI & 科技",
        "sector_icon": "🤖",
        "current_value": 7956.64,
        "yesterday_return": -15.90,
        "total_return": -43.36,
        "target_pct": 0.10,
        "stop_profit": 0.30,
        "stop_loss": -0.12,
        "macro_drivers": ["nvidia_stock", "fed_rate", "china_ai_policy", "nasdaq"],
        "note": "高弹性AI主题，紧跟英伟达/半导体行情"
    },
    {
        "code": "020973",
        "name": "易方达机器人ETF联接C",
        "short": "机器人",
        "sector": "AI & 科技",
        "sector_icon": "🤖",
        "current_value": 7685.95,
        "yesterday_return": 37.32,
        "total_return": -314.05,
        "target_pct": 0.10,
        "stop_profit": 0.30,
        "stop_loss": -0.12,
        "macro_drivers": ["china_manufacturing_policy", "nvidia_stock", "industrial_automation"],
        "note": "人形机器人/工业自动化主题，政策敏感度高"
    },
    {
        "code": "013308",
        "name": "申万菱信中证1000指数增强C",
        "short": "中证1000增强",
        "sector": "宽基指数",
        "sector_icon": "📊",
        "current_value": 4202.67,
        "yesterday_return": 30.13,
        "total_return": 702.67,
        "target_pct": 0.10,
        "stop_profit": 0.25,
        "stop_loss": -0.10,
        "macro_drivers": ["china_pmi", "social_financing", "northbound_flow"],
        "note": "中小盘宽基，经济复苏时弹性强"
    },
    {
        "code": "011609",
        "name": "华泰柏瑞科创50联接C",
        "short": "科创50",
        "sector": "科创板",
        "sector_icon": "🚀",
        "current_value": 18998.63,
        "yesterday_return": 163.89,
        "total_return": 2498.63,
        "target_pct": 0.18,
        "stop_profit": 0.35,
        "stop_loss": -0.12,
        "macro_drivers": ["fed_rate", "northbound_flow", "china_tech_policy", "nasdaq"],
        "note": "科创板龙头，已盈利较多，关注止盈时机"
    },
    {
        "code": "007467",
        "name": "华泰柏瑞中证红利低波动ETF联接C",
        "short": "红利低波",
        "sector": "红利防守",
        "sector_icon": "💰",
        "current_value": 948.41,
        "yesterday_return": -3.28,
        "total_return": -39.87,
        "target_pct": 0.15,
        "stop_profit": 0.15,
        "stop_loss": -0.08,
        "macro_drivers": ["cn_bond_yield", "fed_rate", "dividend_season"],
        "note": "防守型底仓，利率下行时受益，仓位偏低需补充"
    },
    {
        "code": "017458",
        "name": "长城创新驱动混合C",
        "short": "创新驱动",
        "sector": "主动混合",
        "sector_icon": "🎯",
        "current_value": 895.78,
        "yesterday_return": 7.47,
        "total_return": -104.22,
        "target_pct": 0.04,
        "stop_profit": 0.20,
        "stop_loss": -0.12,
        "macro_drivers": ["china_tech_policy", "china_pmi"],
        "note": "主动管理，持仓较小，可考虑合并或清仓"
    },
    {
        "code": "018036",
        "name": "长城全球新能源汽车股票(QDII-LOF)C",
        "short": "全球新能源车",
        "sector": "绿色能源",
        "sector_icon": "⚡",
        "current_value": 1204.29,
        "yesterday_return": -47.25,
        "total_return": 104.29,
        "target_pct": 0.07,
        "stop_profit": 0.25,
        "stop_loss": -0.12,
        "macro_drivers": ["tesla_stock", "lithium_price", "usd_cny", "global_ev_sales"],
        "note": "QDII基金，人民币升值时净值承压"
    },
]

# ═══════════════════════════════════════════════════════════
# 板块目标占比（平衡型）
# ═══════════════════════════════════════════════════════════
SECTOR_TARGETS = {
    "科创板":    {"target_pct": 0.30, "color": "#00C9FF", "desc": "科创50 + 科创100"},
    "AI & 科技": {"target_pct": 0.20, "color": "#FF6B6B", "desc": "AI产业 + 机器人"},
    "绿色能源":  {"target_pct": 0.17, "color": "#51CF66", "desc": "绿色电力 + 新能源车"},
    "宽基指数":  {"target_pct": 0.10, "color": "#FFD43B", "desc": "中证1000增强"},
    "红利防守":  {"target_pct": 0.15, "color": "#CC5DE8", "desc": "红利低波动"},
    "主动混合":  {"target_pct": 0.08, "color": "#74C0FC", "desc": "主动管理混合基金"},
}

# ═══════════════════════════════════════════════════════════
# 宏观指标 → 基金传导逻辑知识库
# 这是"为什么建议买入/卖出"的核心推理依据
# ═══════════════════════════════════════════════════════════
MACRO_TRANSMISSION = {
    "fed_rate_cut": {
        "label": "美联储降息",
        "icon": "🏦",
        "affected_sectors": ["科创板", "AI & 科技"],
        "impact": "positive",
        "strength": "strong",
        "chain": [
            "美联储降息 → 美元走弱（历史相关性 -0.72）",
            "美元走弱 → 全球风险偏好上升",
            "风险偏好上升 → 新兴市场成长股受益",
            "A股科创板以成长股为主 → 科创50/科创100上涨概率提升",
            "📊 历史数据：美联储转鸽后30日，科创50平均涨幅 +6.8%（2019-2024）"
        ],
    },
    "fed_rate_hike": {
        "label": "美联储加息",
        "icon": "🏦",
        "affected_sectors": ["科创板", "AI & 科技"],
        "impact": "negative",
        "strength": "strong",
        "chain": [
            "美联储加息 → 美元走强 → 资金流向美国",
            "新兴市场资金外流压力加大",
            "高估值成长股折现率提升 → 估值压缩",
            "科创板/AI主题基金短期承压",
            "📊 建议：暂缓加仓科创/AI，等待利率见顶信号"
        ],
    },
    "china_pmi_above_50": {
        "label": "中国PMI > 50（扩张）",
        "icon": "🏭",
        "affected_sectors": ["宽基指数", "主动混合"],
        "impact": "positive",
        "strength": "moderate",
        "chain": [
            "PMI > 50 → 制造业扩张信号",
            "企业盈利预期改善 → A股整体估值提升",
            "中小市值企业受益更明显 → 中证1000增强受益",
            "主动混合基金仓位有望提升",
            "📊 建议：宽基指数可适量加仓"
        ],
    },
    "china_pmi_below_49": {
        "label": "中国PMI < 49（收缩）",
        "icon": "🏭",
        "affected_sectors": ["红利防守"],
        "impact": "positive",  # defensive up
        "strength": "moderate",
        "chain": [
            "PMI < 49 → 经济收缩信号",
            "市场避险情绪上升",
            "高股息/低波动资产吸引力增加",
            "红利低波ETF相对抗跌",
            "📊 建议：增加红利防守仓位，减少高弹性成长股"
        ],
    },
    "northbound_inflow": {
        "label": "北向资金持续净流入",
        "icon": "📈",
        "affected_sectors": ["科创板", "AI & 科技", "宽基指数"],
        "impact": "positive",
        "strength": "moderate",
        "chain": [
            "北向资金净流入 → 外资对A股信心增强",
            "外资偏好科创/消费/金融龙头",
            "科创50权重股受益（外资持仓约8%）",
            "市场整体流动性改善",
            "📊 连续5日净流入 > 50亿 → 短期积极信号"
        ],
    },
    "northbound_outflow": {
        "label": "北向资金持续净流出",
        "icon": "📉",
        "affected_sectors": ["科创板", "AI & 科技"],
        "impact": "negative",
        "strength": "moderate",
        "chain": [
            "北向资金净流出 → 外资撤离A股",
            "市场流动性收缩",
            "科创板/高估值成长股承压",
            "📊 连续3日净流出 > 30亿 → 谨慎加仓信号"
        ],
    },
    "cny_depreciation": {
        "label": "人民币大幅贬值（>1%）",
        "icon": "💱",
        "affected_sectors": ["绿色能源"],  # QDII benefits in RMB terms
        "impact": "mixed",
        "strength": "moderate",
        "chain": [
            "人民币贬值 → QDII基金（以美元计价资产）RMB净值上升",
            "长城全球新能源汽车QDII 短期受益",
            "但北向资金可能加速外流 → A股整体承压",
            "📊 QDII可适当持有，A股科创类需观望"
        ],
    },
    "nvidia_up": {
        "label": "英伟达/半导体大涨（>5%）",
        "icon": "🖥️",
        "affected_sectors": ["AI & 科技"],
        "impact": "positive",
        "strength": "strong",
        "chain": [
            "英伟达大涨 → AI算力需求旺盛信号",
            "全球AI产业链景气度上升",
            "国内AI/半导体公司联动上涨",
            "华富AI产业ETF、易方达机器人ETF受益",
            "📊 历史相关性：英伟达单日涨>5%，次日AI ETF平均+2.1%"
        ],
    },
    "cn_bond_yield_fall": {
        "label": "中国10年期国债收益率下降",
        "icon": "📉",
        "affected_sectors": ["红利防守"],
        "impact": "positive",
        "strength": "moderate",
        "chain": [
            "国债收益率下降 → 无风险利率降低",
            "高股息资产相对吸引力上升",
            "红利低波ETF估值提升（股息率相对更高）",
            "📊 收益率每降10bp，红利指数平均+1.2%（历史规律）"
        ],
    },
    "lithium_price_drop": {
        "label": "碳酸锂价格大跌（>5%）",
        "icon": "⚡",
        "affected_sectors": ["绿色能源"],
        "impact": "mixed",
        "strength": "weak",
        "chain": [
            "锂价下跌 → 电池成本下降 → 新能源汽车盈利改善",
            "长城全球新能源汽车QDII中下游车企受益",
            "但上游锂矿/能源公司受损 → 绿色电力ETF影响中性",
            "📊 综合判断：对新能源车QDII略正面，对绿色电力中性"
        ],
    },
}

# ═══════════════════════════════════════════════════════════
# Checklist Agent 配置
# ═══════════════════════════════════════════════════════════
CHECKLIST_CONFIG = {
    "pass_threshold": 70,       # 通过阈值（满分100）
    "cautious_threshold": 40,   # 谨慎建仓阈值
    "small_position_ratio": 0.5, # 谨慎建仓时，建议金额为正常的50%
    "veto_items": [             # 一票否决项（这些为False时直接否决）
        "total_drawdown_ok",
        "not_in_stoploss",
    ],
}

# Checklist 评分维度
CHECKLIST_DIMENSIONS = [
    {
        "id": "global_liquidity",
        "name": "全球流动性是否宽松",
        "dimension": "宏观",
        "weight": 25,
        "veto": False,
        "description": "判断美联储利率方向，宽松=降息/暂停加息周期"
    },
    {
        "id": "cny_stable",
        "name": "人民币汇率稳定",
        "dimension": "宏观",
        "weight": 10,
        "veto": False,
        "description": "USD/CNY近5日波动 < 1%，外汇环境稳定"
    },
    {
        "id": "above_ma60",
        "name": "基金净值在60日均线之上",
        "dimension": "技术",
        "weight": 20,
        "veto": False,
        "description": "中期趋势向上，60日均线是多空分界线"
    },
    {
        "id": "rsi_reasonable",
        "name": "RSI在合理区间（35-70）",
        "dimension": "技术",
        "weight": 15,
        "veto": False,
        "description": "RSI<35超卖可买，RSI>70超买应谨慎"
    },
    {
        "id": "position_below_target",
        "name": "该板块仓位低于目标配置",
        "dimension": "仓位",
        "weight": 15,
        "veto": False,
        "description": "当前板块占比低于目标，有补仓空间"
    },
    {
        "id": "northbound_positive",
        "name": "北向资金近5日净流入",
        "dimension": "市场情绪",
        "weight": 10,
        "veto": False,
        "description": "外资流向是短期市场情绪的重要参考"
    },
    {
        "id": "total_drawdown_ok",
        "name": "总仓位回撤在-15%以内",
        "dimension": "风险控制",
        "weight": 3,
        "veto": True,
        "description": "【一票否决】总仓位亏损超过15%时禁止加仓"
    },
    {
        "id": "not_in_stoploss",
        "name": "该基金未触发止损线",
        "dimension": "风险控制",
        "weight": 2,
        "veto": True,
        "description": "【一票否决】该基金持有亏损已超过止损线时禁止加仓"
    },
]

# ═══════════════════════════════════════════════════════════
# 全局宏观指标配置（数据源）
# ═══════════════════════════════════════════════════════════
MACRO_INDICATORS = {
    "nasdaq":       {"symbol": "^IXIC",   "label": "纳斯达克指数",    "unit": "点"},
    "sp500":        {"symbol": "^GSPC",   "label": "标普500",         "unit": "点"},
    "nvidia":       {"symbol": "NVDA",    "label": "英伟达股价",       "unit": "USD"},
    "usd_cny":      {"symbol": "USDCNY=X","label": "美元/人民币",      "unit": ""},
    "us_10y":       {"symbol": "^TNX",    "label": "美国10年期国债",   "unit": "%"},
    "gold":         {"symbol": "GC=F",    "label": "黄金期货",         "unit": "USD/oz"},
    "oil":          {"symbol": "CL=F",    "label": "原油期货(WTI)",    "unit": "USD/桶"},
    "lithium_etf":  {"symbol": "LIT",     "label": "锂矿ETF",          "unit": "USD"},
}
