"""
买卖建议引擎 + 决策链路生成器
核心逻辑：触发信号 → 传导分析 → Checklist验证 → 输出可读建议
"""

from typing import Dict, List, Optional, Tuple
import datetime
from engine.checklist import ChecklistAgent
from data.fetcher import assess_fed_stance
from config import MACRO_TRANSMISSION, CHECKLIST_DIMENSIONS, PORTFOLIO_CONFIG


# ══════════════════════════════════════════════
# 决策链路生成器
# ══════════════════════════════════════════════

class DecisionChain:
    """
    为每条建议生成完整的推理链路
    让用户清楚看到：为什么、怎么影响、可信度多少
    """

    def build(
        self,
        fund_cfg: Dict,
        trigger_type: str,
        trigger_event: str,
        market_data: Dict,
        technical_data: Dict,
        checklist_result: Dict,
    ) -> Dict:
        """
        构建完整决策链路
        返回结构化的链路数据，供UI渲染
        """
        chain = {
            "fund_code": fund_cfg["code"],
            "fund_name": fund_cfg["name"],
            "sector": fund_cfg["sector"],
            "trigger": {
                "type": trigger_type,
                "event": trigger_event,
                "timestamp": datetime.datetime.now().isoformat(),
            },
            "transmission": [],      # 传导逻辑步骤
            "evidence": [],          # 数据佐证
            "checklist": checklist_result,
            "final_decision": {},    # 最终决策
            "risk_warnings": [],     # 风险提示
        }

        # Step 1: 找到对应的传导逻辑
        transmission_key = self._map_trigger_to_transmission(trigger_type, trigger_event, market_data)
        if transmission_key and transmission_key in MACRO_TRANSMISSION:
            macro_info = MACRO_TRANSMISSION[transmission_key]
            chain["transmission"] = macro_info["chain"]
            chain["macro_impact"] = macro_info["impact"]
            chain["macro_strength"] = macro_info["strength"]
        elif trigger_type == "technical":
            chain["transmission"] = self._build_technical_chain(technical_data)
            chain["macro_impact"] = "neutral"
        elif trigger_type == "stoploss":
            chain["transmission"] = self._build_stoploss_chain(fund_cfg)
            chain["macro_impact"] = "negative"

        # Step 2: 数据佐证
        chain["evidence"] = self._build_evidence(market_data, technical_data, fund_cfg)

        # Step 3: 最终决策
        rec = checklist_result.get("recommendation", "WAIT")
        score = checklist_result.get("score", 0)
        confidence = checklist_result.get("confidence", 1)
        suggested_amount = self._calc_suggested_amount(fund_cfg, rec, score)

        chain["final_decision"] = {
            "recommendation": rec,
            "recommendation_label": self._rec_label(rec),
            "recommendation_emoji": self._rec_emoji(rec),
            "score": score,
            "confidence": confidence,
            "confidence_stars": "★" * confidence + "☆" * (5 - confidence),
            "suggested_amount": suggested_amount,
            "reasoning": checklist_result.get("summary", ""),
            "next_check_date": self._next_check_date(rec),
        }

        # Step 4: 风险提示
        chain["risk_warnings"] = self._build_risk_warnings(fund_cfg, market_data, technical_data)

        return chain

    def _map_trigger_to_transmission(self, trigger_type: str, trigger_event: str, market_data: Dict) -> Optional[str]:
        """将触发事件映射到传导逻辑key"""
        if trigger_type == "macro":
            # 通过事件描述匹配
            event_lower = trigger_event.lower()
            global_data = market_data.get("global", {})

            # 美联储立场
            fed_stance = market_data.get("fed_stance", "neutral")
            if fed_stance in ("dovish", "dovish_strong"):
                return "fed_rate_cut"
            elif fed_stance in ("hawkish", "hawkish_strong"):
                return "fed_rate_hike"

            # 北向资金
            nb = market_data.get("northbound", {})
            if nb.get("signal") == "positive":
                return "northbound_inflow"
            elif nb.get("signal") == "negative":
                return "northbound_outflow"

            # 汇率
            cny = global_data.get("usd_cny", {})
            if cny.get("change_pct") and cny["change_pct"] > 1.0:
                return "cny_depreciation"

            # 英伟达
            nvda = global_data.get("nvidia", {})
            if nvda.get("change_pct") and nvda["change_pct"] > 5.0:
                return "nvidia_up"

        return None

    def _build_technical_chain(self, tech: Dict) -> List[str]:
        """基于技术指标构建传导链路"""
        chain = []
        rsi = tech.get("rsi")
        rsi_signal = tech.get("rsi_signal", "")
        ma60 = tech.get("ma60")
        nav = tech.get("latest_nav")
        trend = tech.get("trend", "unknown")
        macd_cross = tech.get("macd_cross", "neutral")

        if rsi_signal == "oversold":
            chain.append(f"RSI={rsi:.1f} 进入超卖区间(<35) → 短期抛售过度")
            chain.append("历史规律：RSI超卖后10个交易日平均反弹概率 ~67%")
            chain.append("超卖通常意味着短期资金已过度撤出，反弹动力积累")
        elif rsi_signal == "overbought":
            chain.append(f"RSI={rsi:.1f} 进入超买区间(>70) → 短期涨幅过大")
            chain.append("短期获利盘较重，有回调压力")
            chain.append("建议等待RSI回落至60以下再考虑加仓")

        if ma60 and nav:
            if nav > ma60:
                diff = (nav - ma60) / ma60 * 100
                chain.append(f"净值({nav}) 站稳60日均线({ma60})上方 +{diff:.1f}% → 中期趋势偏多")
            else:
                diff = (nav - ma60) / ma60 * 100
                chain.append(f"净值({nav}) 跌破60日均线({ma60}) {diff:.1f}% → 中期趋势偏弱")

        if macd_cross == "bullish":
            chain.append("MACD出现金叉信号（MACD线上穿信号线）→ 短期动能转正")
        elif macd_cross == "bearish":
            chain.append("MACD出现死叉信号（MACD线下穿信号线）→ 短期动能转负")

        if trend == "uptrend":
            chain.append("📊 综合判断：中期上涨趋势确立，技术面支持买入")
        elif trend == "downtrend":
            chain.append("📊 综合判断：中期下跌趋势，技术面建议观望")

        return chain if chain else ["技术指标触发，具体数据见佐证部分"]

    def _build_stoploss_chain(self, fund_cfg: Dict) -> List[str]:
        """止盈止损链路"""
        total_return = fund_cfg.get("total_return", 0)
        current_value = fund_cfg.get("current_value", 1)
        cost = current_value - total_return
        return_pct = (total_return / cost * 100) if cost > 0 else 0
        stop_profit = fund_cfg.get("stop_profit", 0.20) * 100
        stop_loss = fund_cfg.get("stop_loss", -0.12) * 100

        chain = []
        if return_pct >= stop_profit * 0.8:
            chain.append(f"持有收益率 {return_pct:.1f}% 接近止盈线 {stop_profit:.0f}%")
            chain.append("止盈逻辑：落袋为安，锁定盈利，避免高位套牢")
            chain.append("建议策略：可分批止盈（先卖50%，剩余设移动止损）")
            chain.append(f"📊 若继续持有至{stop_profit*1.2:.0f}%再卖，历史上约35%概率会先回调至{stop_profit*0.8:.0f}%")
        elif return_pct <= stop_loss * 0.8:
            chain.append(f"持有亏损 {return_pct:.1f}% 接近止损线 {stop_loss:.0f}%")
            chain.append("止损逻辑：控制风险，避免亏损继续扩大")
            chain.append("建议先分析亏损原因：是整体市场下跌还是该基金特有问题？")
            chain.append("若是市场系统性下跌，可考虑暂停止损等待反弹")

        return chain if chain else ["触发止盈/止损机制，请查看具体数值"]

    def _build_evidence(self, market_data: Dict, tech: Dict, fund_cfg: Dict) -> List[Dict]:
        """构建数据佐证列表"""
        evidence = []
        global_data = market_data.get("global", {})

        # 全球指标
        for key, label in [("nasdaq", "纳斯达克"), ("nvidia", "英伟达"), ("usd_cny", "美元/人民币")]:
            d = global_data.get(key, {})
            if d.get("price"):
                change = d.get("change_pct", 0)
                arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
                evidence.append({
                    "label": label,
                    "value": f"{d['price']} {arrow}{abs(change):.1f}%",
                    "sentiment": "positive" if change > 0 else "negative" if change < 0 else "neutral",
                })

        # 北向资金
        nb = market_data.get("northbound", {})
        if nb.get("5day_total") is not None:
            total = nb["5day_total"]
            evidence.append({
                "label": "北向资金(5日)",
                "value": f"{'+' if total > 0 else ''}{total:.1f}亿",
                "sentiment": "positive" if total > 0 else "negative",
            })

        # 技术指标
        if tech.get("rsi"):
            evidence.append({
                "label": "RSI-14",
                "value": f"{tech['rsi']:.1f}",
                "sentiment": "positive" if tech["rsi"] < 40 else "negative" if tech["rsi"] > 70 else "neutral",
            })

        if tech.get("ma60"):
            above = tech.get("above_ma60", False)
            evidence.append({
                "label": "60日均线",
                "value": f"{'上方✅' if above else '下方⚠️'}({tech['ma60']:.4f})",
                "sentiment": "positive" if above else "negative",
            })

        # PMI
        pmi_data = market_data.get("china", {}).get("pmi", {})
        if pmi_data.get("pmi"):
            pmi = pmi_data["pmi"]
            evidence.append({
                "label": f"中国PMI({pmi_data.get('date', '')})",
                "value": f"{pmi} ({'扩张↑' if pmi >= 50 else '收缩↓'})",
                "sentiment": "positive" if pmi >= 50 else "negative",
            })

        return evidence

    def _calc_suggested_amount(self, fund_cfg: Dict, recommendation: str, score: float) -> float:
        """计算建议操作金额"""
        if recommendation in ("WAIT", "VETO"):
            return 0.0

        # 基础金额：剩余可投 / 批次数 / 基金数量
        remaining = PORTFOLIO_CONFIG.get("remaining_to_invest", 222200)
        batches = PORTFOLIO_CONFIG.get("entry_batches", 6)
        fund_target_pct = fund_cfg.get("target_pct", 0.05)
        base_amount = remaining / batches * fund_target_pct * 10  # 粗略估算

        # 根据评分调整
        if recommendation == "BUY":
            multiplier = min(1.5, score / 80)
        elif recommendation == "BUY_SMALL":
            multiplier = 0.5
        else:
            multiplier = 0

        amount = base_amount * multiplier
        # 取整到1000
        return round(amount / 1000) * 1000

    def _rec_label(self, rec: str) -> str:
        labels = {
            "BUY": "建议买入",
            "BUY_SMALL": "谨慎小额买入",
            "WAIT": "暂不操作",
            "VETO": "禁止操作",
            "SELL": "建议卖出",
            "SELL_PARTIAL": "建议部分卖出",
        }
        return labels.get(rec, rec)

    def _rec_emoji(self, rec: str) -> str:
        emojis = {
            "BUY": "✅",
            "BUY_SMALL": "⚠️",
            "WAIT": "⏸️",
            "VETO": "🚨",
            "SELL": "🔴",
            "SELL_PARTIAL": "🟡",
        }
        return emojis.get(rec, "❓")

    def _next_check_date(self, rec: str) -> str:
        """建议下次复查时间"""
        days = {"BUY": 7, "BUY_SMALL": 3, "WAIT": 5, "VETO": 1}.get(rec, 7)
        next_date = datetime.date.today() + datetime.timedelta(days=days)
        return next_date.strftime("%Y-%m-%d")

    def _build_risk_warnings(self, fund_cfg: Dict, market_data: Dict, tech: Dict) -> List[str]:
        """生成风险提示列表"""
        warnings = []
        total_return = fund_cfg.get("total_return", 0)
        current_value = fund_cfg.get("current_value", 1)
        cost = current_value - total_return
        return_pct = (total_return / cost) if cost > 0 else 0
        stop_profit = fund_cfg.get("stop_profit", 0.20)

        # 接近止盈线
        if return_pct >= stop_profit * 0.8:
            remaining = (stop_profit - return_pct) * 100
            warnings.append(f"⚠️ 持有收益已达 {return_pct*100:.1f}%，距止盈线({stop_profit*100:.0f}%)仅剩 {remaining:.1f}%，注意止盈时机")

        # 科创/AI板块高波动
        if fund_cfg.get("sector") in ("科创板", "AI & 科技"):
            warnings.append("⚡ 该基金所属高弹性板块，单日波动可能达±3-5%，请做好心理准备")

        # 技术指标警示
        rsi = tech.get("rsi")
        if rsi and rsi > 65:
            warnings.append(f"📊 RSI={rsi:.1f} 偏高，短期可能有震荡回调，建议分批买入而非一次性投入")

        # QDII汇率风险
        if "QDII" in fund_cfg.get("name", "") or "全球" in fund_cfg.get("name", ""):
            cny = market_data.get("global", {}).get("usd_cny", {})
            if cny.get("change_pct") and cny["change_pct"] < -0.5:
                warnings.append("💱 人民币升值中，QDII基金净值可能因汇率原因承压")

        if not warnings:
            warnings.append("当前无特别风险提示，正常关注即可")

        return warnings


# ══════════════════════════════════════════════
# 主建议引擎
# ══════════════════════════════════════════════

class FundAdvisor:
    """
    基金买卖建议引擎
    整合 Checklist Agent + 决策链路生成器
    """

    def __init__(self, checklist_config: List[Dict]):
        self.checklist = ChecklistAgent(checklist_config)
        self.chain_builder = DecisionChain()

    def analyze_fund(
        self,
        fund_cfg: Dict,
        market_data: Dict,
        technical_data: Dict,
        portfolio: Dict,
        trigger_type: str = "macro",
        trigger_event: str = "定期分析",
    ) -> Dict:
        """
        对单只基金进行完整分析
        返回：包含决策链路、Checklist结果、最终建议的完整报告
        """
        # 准备Checklist上下文
        fed_stance = assess_fed_stance(
            market_data.get("global", {}).get("us_10y", {}).get("change_pct")
        )

        context = {
            "fund_cfg": fund_cfg,
            "market": {**market_data, "fed_stance": fed_stance},
            "technical": technical_data,
            "portfolio": portfolio,
            "fed_stance": fed_stance,
        }

        # 运行Checklist Agent
        checklist_result = self.checklist.run(context)

        # 构建决策链路
        chain = self.chain_builder.build(
            fund_cfg=fund_cfg,
            trigger_type=trigger_type,
            trigger_event=trigger_event,
            market_data={**market_data, "fed_stance": fed_stance},
            technical_data=technical_data,
            checklist_result=checklist_result,
        )

        return {
            "fund_code": fund_cfg["code"],
            "fund_name": fund_cfg["name"],
            "fund_short": fund_cfg.get("short", fund_cfg["name"]),
            "sector": fund_cfg["sector"],
            "sector_icon": fund_cfg.get("sector_icon", "📊"),
            "trigger_type": trigger_type,
            "trigger_event": trigger_event,
            "checklist": checklist_result,
            "chain": chain,
            "recommendation": checklist_result["recommendation"],
            "recommendation_label": chain["final_decision"]["recommendation_label"],
            "recommendation_emoji": chain["final_decision"]["recommendation_emoji"],
            "suggested_amount": chain["final_decision"]["suggested_amount"],
            "confidence": checklist_result["confidence"],
            "confidence_stars": chain["final_decision"]["confidence_stars"],
            "generated_at": datetime.datetime.now().isoformat(),
        }

    def scan_all_funds(
        self,
        funds: List[Dict],
        market_data: Dict,
        technical_data_map: Dict,  # fund_code -> technical_data
        portfolio: Dict,
    ) -> List[Dict]:
        """
        扫描全部基金，生成建议列表
        优先返回有操作建议的基金
        """
        results = []
        for fund in funds:
            code = fund["code"]
            tech = technical_data_map.get(code, {})

            # 判断触发类型
            trigger_type, trigger_event = self._detect_trigger(fund, market_data, tech)

            result = self.analyze_fund(
                fund_cfg=fund,
                market_data=market_data,
                technical_data=tech,
                portfolio=portfolio,
                trigger_type=trigger_type,
                trigger_event=trigger_event,
            )
            results.append(result)

        # 排序：有操作建议的排前面，按置信度排序
        priority = {"BUY": 0, "SELL": 0, "BUY_SMALL": 1, "SELL_PARTIAL": 1, "WAIT": 2, "VETO": 3}
        results.sort(key=lambda x: (priority.get(x["recommendation"], 4), -x["confidence"]))
        return results

    def _detect_trigger(self, fund_cfg: Dict, market_data: Dict, tech: Dict) -> Tuple[str, str]:
        """自动检测触发类型"""
        total_return = fund_cfg.get("total_return", 0)
        current_value = fund_cfg.get("current_value", 1)
        cost = current_value - total_return
        return_pct = (total_return / cost) if cost > 0 else 0

        # 止盈检查
        if return_pct >= fund_cfg.get("stop_profit", 0.20) * 0.9:
            return "stoploss", f"持有收益率 {return_pct*100:.1f}% 接近止盈线"

        # 止损检查
        if return_pct <= fund_cfg.get("stop_loss", -0.12) * 0.8:
            return "stoploss", f"持有亏损 {return_pct*100:.1f}% 接近止损线"

        # 技术信号
        rsi_signal = tech.get("rsi_signal", "")
        if rsi_signal == "oversold":
            return "technical", f"RSI={tech.get('rsi', 0):.1f} 超卖信号"
        if rsi_signal == "overbought":
            return "technical", f"RSI={tech.get('rsi', 0):.1f} 超买信号"

        macd = tech.get("macd_cross", "neutral")
        if macd == "bullish":
            return "technical", "MACD金叉信号"
        if macd == "bearish":
            return "technical", "MACD死叉信号"

        # 宏观信号
        fed_stance = assess_fed_stance(
            market_data.get("global", {}).get("us_10y", {}).get("change_pct")
        )
        if fed_stance in ("dovish", "dovish_strong"):
            return "macro", "美联储偏鸽派信号"
        if fed_stance in ("hawkish", "hawkish_strong"):
            return "macro", "美联储偏鹰派信号"

        nvda = market_data.get("global", {}).get("nvidia", {})
        if nvda.get("change_pct") and abs(nvda["change_pct"]) > 5:
            return "macro", f"英伟达大幅波动 {nvda['change_pct']:+.1f}%"

        return "macro", "定期宏观环境评估"
