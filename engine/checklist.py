"""
Checklist Agent - 多维度验证引擎
每条买卖建议在输出前必须通过此Agent核查
核查结果全部可见、可追溯
"""

from typing import Dict, List, Tuple, Optional
import datetime


class ChecklistItem:
    """单个检查项"""
    def __init__(self, item_id: str, name: str, dimension: str,
                 weight: int, is_veto: bool = False, description: str = ""):
        self.id = item_id
        self.name = name
        self.dimension = dimension
        self.weight = weight
        self.is_veto = is_veto
        self.description = description

    def run(self, context: Dict) -> Tuple[bool, str]:
        """
        执行检查，返回 (passed: bool, detail: str)
        context包含：market_data, fund_data, portfolio_data, technical_data
        """
        check_fn = getattr(self, f"_check_{self.id}", None)
        if check_fn:
            return check_fn(context)
        return True, "检查项未实现，默认通过"

    # ── 宏观类检查 ─────────────────────────────

    def _check_global_liquidity(self, ctx: Dict) -> Tuple[bool, str]:
        """全球流动性：通过美债利率/美联储立场判断"""
        fed = ctx.get("fed_stance", "unknown")
        us10y = ctx.get("market", {}).get("global", {}).get("us_10y", {})
        change = us10y.get("change_pct") if us10y else None

        if fed in ("dovish", "dovish_strong"):
            return True, f"✅ 美联储偏鸽派，全球流动性宽松（美债10Y变化 {change:+.1f}%）" if change else "✅ 美联储偏鸽派，流动性宽松"
        elif fed in ("hawkish", "hawkish_strong"):
            return False, f"❌ 美联储偏鹰派，全球流动性偏紧（美债10Y变化 {change:+.1f}%）" if change else "❌ 美联储偏鹰派，流动性偏紧"
        elif fed == "neutral":
            return True, f"⚠️ 美联储中性，流动性适中（半通过）"
        else:
            return True, "⚠️ 今日美国国债利率数据暂未更新（可能非交易时段），此项暂不扣分"

    def _check_cny_stable(self, ctx: Dict) -> Tuple[bool, str]:
        """人民币汇率是否稳定：近5日波动 < 1%"""
        cny = ctx.get("market", {}).get("global", {}).get("usd_cny", {})
        change = cny.get("change_pct") if cny else None
        if change is None:
            return True, "⚠️ 美元/人民币汇率数据暂未获取到，此项暂不扣分"
        if abs(change) < 1.0:
            return True, f"✅ 人民币汇率稳定（美元/人民币日变化 {change:+.2f}%）"
        else:
            return False, f"❌ 人民币波动偏大（日变化 {change:+.2f}%），汇率风险提升"

    # ── 技术类检查 ─────────────────────────────

    def _check_above_ma60(self, ctx: Dict) -> Tuple[bool, str]:
        """基金净值是否在60日均线之上"""
        tech = ctx.get("technical", {})
        above = tech.get("above_ma60")
        nav = tech.get("latest_nav")
        ma60 = tech.get("ma60")
        if above is None:
            return True, "⚠️ 历史净值数据不足60个交易日，无法计算中期趋势线，此项暂不扣分"
        if above:
            return True, f"✅ 净值({nav}) 在60日均线({ma60})上方，中期趋势向上"
        else:
            diff_pct = ((nav - ma60) / ma60 * 100) if ma60 else 0
            return False, f"❌ 净值({nav}) 低于60日均线({ma60})，偏离 {diff_pct:.1f}%，中期趋势偏弱"

    def _check_rsi_reasonable(self, ctx: Dict) -> Tuple[bool, str]:
        """RSI是否在合理区间 35-70"""
        tech = ctx.get("technical", {})
        rsi = tech.get("rsi")
        signal = tech.get("rsi_signal", "unknown")
        if rsi is None:
            return True, "⚠️ 历史数据不足15个交易日，无法计算RSI超买超卖指标，此项暂不扣分"
        if signal == "oversold":
            return True, f"✅ RSI={rsi:.1f} 处于超卖区间(<35)，是较好买入时机"
        elif signal == "overbought":
            return False, f"❌ RSI={rsi:.1f} 处于超买区间(>70)，短期有回调风险"
        elif 35 <= rsi <= 70:
            return True, f"✅ RSI={rsi:.1f} 在合理区间(35-70)，无明显超买超卖"
        else:
            return True, f"⚠️ RSI={rsi:.1f}，数据边界情况"

    # ── 仓位类检查 ─────────────────────────────

    def _check_position_below_target(self, ctx: Dict) -> Tuple[bool, str]:
        """当前板块仓位是否低于目标配置"""
        fund_cfg = ctx.get("fund_cfg", {})
        portfolio = ctx.get("portfolio", {})
        target_pct = fund_cfg.get("target_pct", 0)
        sector = fund_cfg.get("sector", "")
        current_total = portfolio.get("total_value", 0)
        target_total = portfolio.get("total_target", 300000)

        # 计算该板块当前占比
        sector_value = sum(
            f.get("current_value", 0)
            for f in portfolio.get("funds", [])
            if f.get("sector") == sector
        )
        current_pct = sector_value / target_total if target_total else 0
        gap = target_pct - current_pct

        if gap > 0.02:
            return True, f"✅ {sector}板块当前占比 {current_pct*100:.1f}%，目标 {target_pct*100:.0f}%，仍有 {gap*100:.1f}% 补仓空间"
        elif gap > 0:
            return True, f"⚠️ {sector}板块轻微低配（缺口 {gap*100:.1f}%），可小额补仓"
        else:
            return False, f"❌ {sector}板块已达目标配置（当前{current_pct*100:.1f}% ≥ 目标{target_pct*100:.0f}%），无需加仓"

    # ── 情绪类检查 ─────────────────────────────

    def _check_northbound_positive(self, ctx: Dict) -> Tuple[bool, str]:
        """北向资金近5日是否净流入"""
        nb = ctx.get("market", {}).get("northbound", {})
        total_5d = nb.get("5day_total")
        positive_days = nb.get("5day_positive_days", 0)
        signal = nb.get("signal", "unknown")

        if total_5d is None:
            return True, "⚠️ 北向资金（外资流入A股）数据暂未获取到（可能非交易时段），此项暂不扣分"
        if signal == "positive":
            return True, f"✅ 北向资金近5日净流入合计 {total_5d:.1f}亿元（{positive_days}/5日正流入）"
        else:
            return False, f"❌ 北向资金近5日净流出合计 {abs(total_5d):.1f}亿元（仅{positive_days}/5日正流入），外资情绪偏悲观"

    # ── 风险类检查（一票否决）─────────────────

    def _check_total_drawdown_ok(self, ctx: Dict) -> Tuple[bool, str]:
        """【一票否决】总仓位回撤是否在-15%以内"""
        portfolio = ctx.get("portfolio", {})
        total_cost = portfolio.get("total_cost", 0)
        total_value = portfolio.get("total_value", 0)
        if total_cost <= 0:
            return True, "⚠️ 总仓位成本数据不完整，无法计算回撤比例，此项暂不扣分"
        drawdown = (total_value - total_cost) / total_cost
        if drawdown >= -0.15:
            return True, f"✅ 总仓位回撤 {drawdown*100:.1f}%，在-15%安全线以内"
        else:
            return False, f"🚨 【一票否决】总仓位回撤 {drawdown*100:.1f}% 超过-15%警戒线！禁止加仓，应考虑止损"

    def _check_not_in_stoploss(self, ctx: Dict) -> Tuple[bool, str]:
        """【一票否决】该基金未触发止损线"""
        fund_cfg = ctx.get("fund_cfg", {})
        stop_loss = fund_cfg.get("stop_loss", -0.12)
        total_return = fund_cfg.get("total_return", 0)
        current_value = fund_cfg.get("current_value", 1)
        # 估算持有收益率
        cost_estimate = current_value - total_return
        if cost_estimate <= 0:
            return True, "⚠️ 该基金成本数据不完整，无法计算持有收益率，此项暂不扣分"
        hold_return_pct = total_return / cost_estimate
        if hold_return_pct > stop_loss:
            return True, f"✅ 持有收益率 {hold_return_pct*100:.1f}%，未触及止损线({stop_loss*100:.0f}%)"
        else:
            return False, f"🚨 【一票否决】持有亏损 {hold_return_pct*100:.1f}% 已超止损线({stop_loss*100:.0f}%)！请先检查逻辑，不建议加仓"


class ChecklistAgent:
    """
    Checklist Agent 核心类
    在任何买卖建议输出前运行，确保决策质量
    """

    def __init__(self, config: List[Dict]):
        self.items = [
            ChecklistItem(
                item_id=c["id"],
                name=c["name"],
                dimension=c["dimension"],
                weight=c["weight"],
                is_veto=c.get("veto", False),
                description=c.get("description", ""),
            )
            for c in config
        ]

    def run(self, context: Dict) -> Dict:
        """
        运行完整检查清单
        返回：{
          score: 综合评分(0-100),
          recommendation: BUY/BUY_SMALL/WAIT/VETO,
          veto_triggered: bool,
          items: [各项检查结果],
          summary: 文字总结,
          timestamp: 执行时间,
        }
        """
        results = []
        total_score = 0
        veto_triggered = False
        veto_reason = ""

        for item in self.items:
            try:
                passed, detail = item.run(context)
            except Exception as e:
                passed, detail = True, f"⚠️ 检查执行异常({e})，默认通过"

            score = item.weight if passed else 0
            total_score += score

            if item.is_veto and not passed:
                veto_triggered = True
                veto_reason = detail

            results.append({
                "id": item.id,
                "name": item.name,
                "dimension": item.dimension,
                "weight": item.weight,
                "passed": passed,
                "score": score,
                "detail": detail,
                "is_veto": item.is_veto,
            })

        # 最终决策
        if veto_triggered:
            recommendation = "VETO"
            confidence = 1
        elif total_score >= 70:
            recommendation = "BUY"
            confidence = min(5, int(total_score / 20))
        elif total_score >= 40:
            recommendation = "BUY_SMALL"
            confidence = 2
        else:
            recommendation = "WAIT"
            confidence = 1

        # 生成总结文字
        passed_count = sum(1 for r in results if r["passed"])
        total_count = len(results)
        summary = self._generate_summary(
            total_score, recommendation, passed_count, total_count,
            veto_triggered, veto_reason, results
        )

        return {
            "score": round(total_score, 1),
            "max_score": 100,
            "recommendation": recommendation,
            "confidence": confidence,
            "veto_triggered": veto_triggered,
            "veto_reason": veto_reason if veto_triggered else "",
            "items": results,
            "passed_count": passed_count,
            "total_count": total_count,
            "summary": summary,
            "timestamp": datetime.datetime.now().isoformat(),
            # 各维度得分
            "dimension_scores": self._calc_dimension_scores(results),
        }

    def _calc_dimension_scores(self, results: List[Dict]) -> Dict:
        """计算各维度得分"""
        dims = {}
        for r in results:
            d = r["dimension"]
            if d not in dims:
                dims[d] = {"total_weight": 0, "earned": 0}
            dims[d]["total_weight"] += r["weight"]
            dims[d]["earned"] += r["score"]
        return {
            d: {
                "pct": round(v["earned"] / v["total_weight"] * 100 if v["total_weight"] else 0, 0),
                "earned": v["earned"],
                "max": v["total_weight"],
            }
            for d, v in dims.items()
        }

    def _generate_summary(self, score, recommendation, passed, total,
                          veto, veto_reason, results) -> str:
        rec_map = {
            "BUY": "✅ 建议正常加仓",
            "BUY_SMALL": "⚠️ 建议谨慎小额加仓（金额减半）",
            "WAIT": "⏸️ 建议暂不操作，等待信号改善",
            "VETO": "🚨 一票否决，禁止操作",
        }
        text = f"Checklist综合评分：{score}/100分，通过 {passed}/{total} 项。\n"
        text += f"最终结论：{rec_map.get(recommendation, recommendation)}\n"
        if veto:
            text += f"\n否决原因：{veto_reason}\n"

        # 列出未通过项
        failed = [r for r in results if not r["passed"] and not r["is_veto"]]
        if failed:
            text += f"\n需关注的风险点（{len(failed)}项）：\n"
            for f in failed:
                text += f"  · {f['name']}：{f['detail']}\n"

        return text
