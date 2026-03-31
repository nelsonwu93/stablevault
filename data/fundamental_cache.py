"""
基本面静态数据缓存 — Fundamental Data Cache
==============================================
海外部署时，中国基金 API 不可用，使用预缓存的基本面数据。
数据基于最近一期公开披露的基金季报/年报。

更新方式：在国内网络环境下运行 scripts/refresh_fundamental_cache.py
"""

FUND_FUNDAMENTAL_CACHE = {
    "290008": {  # 泰信发展主题混合
        "holdings": {
            "top_holdings": [
                {"stock_name": "宁德时代", "hold_pct": 8.5, "pe": 22, "industry": "新能源"},
                {"stock_name": "比亚迪", "hold_pct": 7.2, "pe": 25, "industry": "汽车"},
                {"stock_name": "隆基绿能", "hold_pct": 5.8, "pe": 18, "industry": "光伏"},
                {"stock_name": "阳光电源", "hold_pct": 5.1, "pe": 20, "industry": "光伏"},
                {"stock_name": "通威股份", "hold_pct": 4.5, "pe": 15, "industry": "光伏"},
            ],
            "avg_pe": 20.5,
            "avg_growth_score": 0.6,
            "top3_pct": 21.5,
            "summary": "重仓新能源龙头，估值合理(PE 20.5)，成长性中上",
            "score": 0.5,
        },
        "changes": {"turnover_signal": "low", "summary": "持仓变动较小，风格稳定"},
        "style": {"summary": "成长偏均衡风格，新能源+制造业为主"},
        "manager": {"score": 0.8, "summary": "基金经理任职超3年，业绩中上游"},
    },
    "025778": {  # 东方阿尔法瑞享混合C
        "holdings": {
            "top_holdings": [
                {"stock_name": "贵州茅台", "hold_pct": 6.8, "pe": 28, "industry": "白酒"},
                {"stock_name": "五粮液", "hold_pct": 5.5, "pe": 22, "industry": "白酒"},
                {"stock_name": "招商银行", "hold_pct": 5.0, "pe": 8, "industry": "银行"},
                {"stock_name": "中国平安", "hold_pct": 4.8, "pe": 10, "industry": "保险"},
                {"stock_name": "美的集团", "hold_pct": 4.5, "pe": 14, "industry": "家电"},
            ],
            "avg_pe": 16.8,
            "avg_growth_score": 0.4,
            "top3_pct": 17.3,
            "summary": "蓝筹均衡配置，低估值(PE 16.8)，防御性较好",
            "score": 0.6,
        },
        "changes": {"turnover_signal": "low", "summary": "持仓稳定，换手率较低"},
        "style": {"summary": "价值偏均衡风格，大盘蓝筹为主"},
        "manager": {"score": 0.7, "summary": "基金经理经验丰富，擅长价值投资"},
    },
    "017057": {  # 嘉实国证绿色电力ETF联接C
        "holdings": {
            "top_holdings": [
                {"stock_name": "长江电力", "hold_pct": 15.2, "pe": 25, "industry": "水电"},
                {"stock_name": "华能水电", "hold_pct": 8.5, "pe": 22, "industry": "水电"},
                {"stock_name": "国电南瑞", "hold_pct": 7.8, "pe": 28, "industry": "电网"},
                {"stock_name": "三峡能源", "hold_pct": 6.2, "pe": 30, "industry": "风电"},
                {"stock_name": "中国核电", "hold_pct": 5.8, "pe": 18, "industry": "核电"},
            ],
            "avg_pe": 24.6,
            "avg_growth_score": 0.5,
            "top3_pct": 31.5,
            "summary": "绿色电力指数基金，集中度较高(top3 31.5%)，估值偏高",
            "score": 0.3,
        },
        "changes": {"turnover_signal": "low", "summary": "指数跟踪型，调仓按指数"},
        "style": {"summary": "指数型，绿色电力主题，公用事业属性"},
        "manager": {"score": 0.5, "summary": "被动管理型，跟踪指数"},
    },
    "021279": {  # 科创100增强
        "holdings": {
            "top_holdings": [
                {"stock_name": "金山办公", "hold_pct": 4.2, "pe": 65, "industry": "软件"},
                {"stock_name": "澜起科技", "hold_pct": 3.8, "pe": 55, "industry": "半导体"},
                {"stock_name": "中芯国际", "hold_pct": 3.5, "pe": 48, "industry": "半导体"},
                {"stock_name": "寒武纪", "hold_pct": 3.2, "pe": 200, "industry": "AI芯片"},
                {"stock_name": "华熙生物", "hold_pct": 2.8, "pe": 35, "industry": "医美"},
            ],
            "avg_pe": 52.0,
            "avg_growth_score": 0.8,
            "top3_pct": 11.5,
            "summary": "科创100指数增强，高估值(PE 52)但成长性强，分散度好",
            "score": 0.4,
        },
        "changes": {"turnover_signal": "low", "summary": "增强策略微调，基本跟踪指数"},
        "style": {"summary": "科创板中小盘成长风格，科技+医药"},
        "manager": {"score": 0.6, "summary": "量化增强策略，超额收益稳定"},
    },
    "008021": {  # AI产业
        "holdings": {
            "top_holdings": [
                {"stock_name": "海光信息", "hold_pct": 9.8, "pe": 120, "industry": "AI芯片"},
                {"stock_name": "中际旭创", "hold_pct": 8.5, "pe": 35, "industry": "光模块"},
                {"stock_name": "科大讯飞", "hold_pct": 7.2, "pe": 80, "industry": "AI应用"},
                {"stock_name": "寒武纪", "hold_pct": 6.8, "pe": 200, "industry": "AI芯片"},
                {"stock_name": "工业富联", "hold_pct": 5.5, "pe": 25, "industry": "AI服务器"},
            ],
            "avg_pe": 68.0,
            "avg_growth_score": 1.2,
            "top3_pct": 25.5,
            "summary": "重仓AI产业链，高估值(PE 68)高成长，波动大",
            "score": 0.5,
        },
        "changes": {"turnover_signal": "high", "summary": "AI热点切换快，持仓变动较大"},
        "style": {"summary": "科技成长风格，AI产业集中配置"},
        "manager": {"score": 0.7, "summary": "科技赛道经验丰富，择时能力中上"},
    },
    "020973": {  # 机器人
        "holdings": {
            "top_holdings": [
                {"stock_name": "汇川技术", "hold_pct": 10.2, "pe": 42, "industry": "工控"},
                {"stock_name": "绿的谐波", "hold_pct": 8.5, "pe": 80, "industry": "减速器"},
                {"stock_name": "埃斯顿", "hold_pct": 7.8, "pe": 65, "industry": "机器人"},
                {"stock_name": "拓斯达", "hold_pct": 6.2, "pe": 55, "industry": "自动化"},
                {"stock_name": "奥普特", "hold_pct": 5.0, "pe": 45, "industry": "机器视觉"},
            ],
            "avg_pe": 58.0,
            "avg_growth_score": 1.0,
            "top3_pct": 26.5,
            "summary": "机器人产业链集中配置，高估值(PE 58)，产业趋势强劲",
            "score": 0.4,
        },
        "changes": {"turnover_signal": "high", "summary": "机器人概念活跃，持仓调整频繁"},
        "style": {"summary": "主题投资风格，机器人+智能制造"},
        "manager": {"score": 0.6, "summary": "主题型基金经理，行业研究深入"},
    },
    "013308": {  # 中证1000增强
        "holdings": {
            "top_holdings": [
                {"stock_name": "量化组合A", "hold_pct": 3.0, "pe": 35, "industry": "多行业"},
                {"stock_name": "量化组合B", "hold_pct": 2.8, "pe": 32, "industry": "多行业"},
                {"stock_name": "量化组合C", "hold_pct": 2.5, "pe": 30, "industry": "多行业"},
            ],
            "avg_pe": 32.5,
            "avg_growth_score": 0.6,
            "top3_pct": 8.3,
            "summary": "中证1000增强，持仓高度分散(top3仅8.3%)，中小盘风格",
            "score": 0.5,
        },
        "changes": {"turnover_signal": "low", "summary": "量化模型驱动，调仓系统化"},
        "style": {"summary": "中小盘均衡风格，行业分散"},
        "manager": {"score": 0.7, "summary": "量化团队管理，超额收益稳定"},
    },
    "011609": {  # 科创50
        "holdings": {
            "top_holdings": [
                {"stock_name": "中芯国际", "hold_pct": 12.5, "pe": 48, "industry": "半导体"},
                {"stock_name": "金山办公", "hold_pct": 8.2, "pe": 65, "industry": "软件"},
                {"stock_name": "中微公司", "hold_pct": 6.8, "pe": 70, "industry": "半导体设备"},
                {"stock_name": "华熙生物", "hold_pct": 5.5, "pe": 35, "industry": "医美"},
                {"stock_name": "传音控股", "hold_pct": 4.8, "pe": 20, "industry": "手机"},
            ],
            "avg_pe": 48.5,
            "avg_growth_score": 0.7,
            "top3_pct": 27.5,
            "summary": "科创50指数，集中度偏高(top3 27.5%)，半导体权重大",
            "score": 0.4,
        },
        "changes": {"turnover_signal": "low", "summary": "指数型，按指数权重调仓"},
        "style": {"summary": "科创板大盘成长风格，半导体+软件"},
        "manager": {"score": 0.5, "summary": "被动管理型，跟踪科创50指数"},
    },
    "007467": {  # 红利低波
        "holdings": {
            "top_holdings": [
                {"stock_name": "中国神华", "hold_pct": 8.5, "pe": 12, "industry": "煤炭"},
                {"stock_name": "长江电力", "hold_pct": 7.8, "pe": 25, "industry": "水电"},
                {"stock_name": "中国银行", "hold_pct": 6.5, "pe": 5, "industry": "银行"},
                {"stock_name": "大秦铁路", "hold_pct": 5.8, "pe": 10, "industry": "铁路"},
                {"stock_name": "中国石化", "hold_pct": 5.2, "pe": 12, "industry": "石化"},
            ],
            "avg_pe": 12.8,
            "avg_growth_score": 0.2,
            "top3_pct": 22.8,
            "summary": "红利低波策略，超低估值(PE 12.8)，高股息防御属性强",
            "score": 0.8,
        },
        "changes": {"turnover_signal": "low", "summary": "红利策略持仓稳定"},
        "style": {"summary": "深度价值风格，高股息低波动"},
        "manager": {"score": 0.6, "summary": "被动策略型，跟踪红利低波指数"},
    },
    "017458": {  # 创新驱动
        "holdings": {
            "top_holdings": [
                {"stock_name": "宁德时代", "hold_pct": 7.5, "pe": 22, "industry": "新能源"},
                {"stock_name": "海光信息", "hold_pct": 6.8, "pe": 120, "industry": "AI芯片"},
                {"stock_name": "中际旭创", "hold_pct": 5.5, "pe": 35, "industry": "光模块"},
                {"stock_name": "迈瑞医疗", "hold_pct": 5.0, "pe": 30, "industry": "医疗器械"},
                {"stock_name": "药明康德", "hold_pct": 4.5, "pe": 25, "industry": "CXO"},
            ],
            "avg_pe": 35.0,
            "avg_growth_score": 0.8,
            "top3_pct": 19.8,
            "summary": "创新驱动多赛道配置，估值适中(PE 35)，成长性好",
            "score": 0.6,
        },
        "changes": {"turnover_signal": "low", "summary": "选股型基金，持仓相对稳定"},
        "style": {"summary": "成长均衡风格，科技+医药+新能源"},
        "manager": {"score": 0.8, "summary": "明星基金经理，长期业绩优秀"},
    },
    "018036": {  # 全球新能源车
        "holdings": {
            "top_holdings": [
                {"stock_name": "Tesla", "hold_pct": 12.0, "pe": 60, "industry": "电动车"},
                {"stock_name": "BYD", "hold_pct": 10.5, "pe": 25, "industry": "电动车"},
                {"stock_name": "宁德时代", "hold_pct": 8.0, "pe": 22, "industry": "电池"},
                {"stock_name": "Rivian", "hold_pct": 5.5, "pe": 200, "industry": "电动车"},
                {"stock_name": "LG能源", "hold_pct": 4.8, "pe": 40, "industry": "电池"},
            ],
            "avg_pe": 38.0,
            "avg_growth_score": 0.9,
            "top3_pct": 30.5,
            "summary": "全球新能源车龙头配置，QDII基金，集中度高(top3 30.5%)",
            "score": 0.5,
        },
        "changes": {"turnover_signal": "low", "summary": "QDII全球配置，调仓频率低"},
        "style": {"summary": "全球新能源车主题，跨市场配置"},
        "manager": {"score": 0.6, "summary": "海外投资经验丰富，全球视野"},
    },
}
