"""
LLM 行情解读引擎 — Market Commentary Engine
参考 GoFundBot 思路，生成：
  1. 每日市场综述 (Daily Market Summary)
  2. 基金操作点评 (Fund Action Commentary)
  3. 风险预警报告 (Risk Alert Report)
  4. 投资策略建议 (Investment Strategy Advice)

注：本模块使用规则模板 + 动态数据生成专业评论，
    不依赖外部LLM API，所有分析逻辑内置
"""

import datetime
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 1. 每日市场综述
# ══════════════════════════════════════════════

def generate_market_summary(
    snapshot: Dict,
    regime_name: str,
    regime_cfg: Dict,
    all_fund_results: List[Dict] = None,
) -> Dict:
    """
    生成每日市场综述报告
    snapshot: 宏观数据快照
    regime_name: 当前经济体制
    all_fund_results: 所有基金分析结果
    """
    now = datetime.datetime.now()

    # ── 解读宏观环境 ──
    macro_parts = []
    risk_alerts = []

    # 美股行情
    sp500 = snapshot.get("^GSPC", {})
    nasdaq = snapshot.get("^IXIC", {})
    if sp500.get("change_pct") is not None:
        sp_pct = sp500["change_pct"]
        if sp_pct > 1.5:
            macro_parts.append(f"美股强势上涨，标普500涨{sp_pct:.1f}%，市场风险偏好提升")
        elif sp_pct > 0:
            macro_parts.append(f"美股温和上涨，标普500涨{sp_pct:.1f}%，整体气氛偏暖")
        elif sp_pct > -1.5:
            macro_parts.append(f"美股小幅回调，标普500跌{abs(sp_pct):.1f}%，短期压力不大")
        else:
            macro_parts.append(f"美股大幅下跌，标普500跌{abs(sp_pct):.1f}%，市场情绪偏谨慎")
            risk_alerts.append(f"美股单日大跌{abs(sp_pct):.1f}%，关注是否为趋势性下行")

    # 美债收益率
    tnx = snapshot.get("^TNX", {})
    if tnx.get("price"):
        yield_val = tnx["price"]
        if yield_val > 4.8:
            macro_parts.append(f"美债收益率高达{yield_val:.2f}%，高利率环境压制成长股估值")
            risk_alerts.append(f"美债十年期收益率{yield_val:.2f}%处于高位，对科技/成长板块不利")
        elif yield_val > 4.0:
            macro_parts.append(f"美债收益率{yield_val:.2f}%处于中高位，市场等待降息信号")
        elif yield_val > 3.0:
            macro_parts.append(f"美债收益率{yield_val:.2f}%温和回落，有利于权益资产估值修复")
        else:
            macro_parts.append(f"美债收益率降至{yield_val:.2f}%，宽松预期利好成长股")

    # 汇率
    usdcny = snapshot.get("USDCNY=X", {})
    if usdcny.get("price"):
        rate = usdcny["price"]
        if rate > 7.3:
            macro_parts.append(f"人民币兑美元{rate:.2f}，偏弱走势不利于QDII基金净值")
            risk_alerts.append(f"人民币汇率偏弱（{rate:.2f}），QDII基金面临汇率损失风险")
        elif rate > 7.1:
            macro_parts.append(f"人民币兑美元{rate:.2f}，汇率基本稳定")
        else:
            macro_parts.append(f"人民币走强至{rate:.2f}，有利于QDII基金换算净值")

    # 黄金/原油
    gold = snapshot.get("GC=F", {})
    oil = snapshot.get("CL=F", {})
    if gold.get("price"):
        macro_parts.append(f"黄金{gold['price']:.0f}美元{'，避险需求强劲' if gold.get('change_pct', 0) > 1 else ''}")
    if oil.get("price") and oil["price"] > 85:
        risk_alerts.append(f"原油价格{oil['price']:.0f}美元处于高位，通胀压力增大")

    # ── 解读经济体制 ──
    regime_text = {
        "外部冲击": "当前市场受外部事件（地缘冲突/政策冲击）主导，建议以防守为主，控制仓位。外部冲击通常是暂时的，但短期波动可能加剧。",
        "放缓期": "经济增速有所放缓，盈利预期下修。建议精选确定性高的行业，避免过度押注单一赛道。红利和价值风格可能优于成长。",
        "扩张期": "经济处于扩张阶段，企业盈利改善。大部分基金都有表现机会，可以适度提高仓位。成长型和科技板块弹性最大。",
        "衰退修复": "经济可能已经触底，正在修复中。是逐步布局的窗口期，但仍需保持耐心。可以关注超跌反弹和政策受益方向。",
        "流动性危机": "市场流动性紧张，系统性风险升高。建议大幅降低仓位，持有现金或防御性资产。等待流动性改善信号。",
    }
    regime_commentary = regime_text.get(regime_name, "经济环境不明朗，建议保持适度仓位。")

    # ── 组合总评 ──
    portfolio_commentary = ""
    if all_fund_results:
        buy_funds = [r for r in all_fund_results if r.get("comp", {}).get("recommendation") in ("BUY", "BUY_SMALL")]
        sell_funds = [r for r in all_fund_results if r.get("comp", {}).get("recommendation") in ("VETO", "SELL")]
        avg_d = sum(r.get("comp", {}).get("d_score", 0) for r in all_fund_results) / len(all_fund_results) if all_fund_results else 0

        if avg_d > 0.5:
            portfolio_commentary = f"组合整体偏乐观（平均D分{avg_d:+.2f}），{len(buy_funds)}只基金有加仓信号。建议按照优化权重逐步加仓，优先操作D分最高的基金。"
        elif avg_d > -0.3:
            portfolio_commentary = f"组合信号中性（平均D分{avg_d:+.2f}），{len(buy_funds)}只可加仓、{len(sell_funds)}只建议减仓。当前环境适合小幅调仓，不宜大进大出。"
        else:
            portfolio_commentary = f"组合整体偏谨慎（平均D分{avg_d:+.2f}），{len(sell_funds)}只基金有减仓信号。建议优先执行减仓操作，等待市场企稳后再考虑加仓。"

    return {
        "date": now.strftime("%Y-%m-%d %H:%M"),
        "regime": regime_name,
        "regime_commentary": regime_commentary,
        "macro_summary": "；".join(macro_parts) if macro_parts else "市场数据获取中...",
        "portfolio_commentary": portfolio_commentary,
        "risk_alerts": risk_alerts,
        "sentiment": "乐观" if len(risk_alerts) == 0 else "谨慎" if len(risk_alerts) <= 2 else "警惕",
    }


# ══════════════════════════════════════════════
# 2. 单只基金操作点评
# ══════════════════════════════════════════════

def generate_fund_commentary(
    fund_cfg: Dict,
    comp: Dict,
    m_result: Dict,
    s_result: Dict,
    c_result: Dict,
    regime_name: str,
) -> str:
    """
    为单只基金生成自然语言操作点评
    """
    name = fund_cfg.get("name", "")
    sector = fund_cfg.get("sector", "")
    d_score = comp.get("d_score", 0)
    rec = comp.get("recommendation", "WAIT")
    current = fund_cfg.get("current_value", 0)
    total_ret = fund_cfg.get("total_return", 0)
    ret_pct = (total_ret / current * 100) if current > 0 else 0

    m_s = m_result.get("score", 0)
    s_s = s_result.get("score", 0)
    c_s = c_result.get("score", 0)

    parts = []

    # 开头：基金当前状态
    if ret_pct > 15:
        parts.append(f"{name}已累计盈利{ret_pct:.1f}%，属于盈利较好的持仓")
    elif ret_pct > 0:
        parts.append(f"{name}目前小幅盈利{ret_pct:.1f}%，表现尚可")
    elif ret_pct > -10:
        parts.append(f"{name}目前小幅亏损{ret_pct:.1f}%，尚在可控范围")
    else:
        parts.append(f"{name}目前亏损{ret_pct:.1f}%，需要关注是否触及止损线")

    # 中段：三层因子解读
    if m_s > 0.5:
        parts.append("宏观环境对其有利")
    elif m_s < -0.5:
        parts.append("宏观环境给其带来压力")

    if s_s > 0.5:
        parts.append(f"{sector}板块处于上升期")
    elif s_s < -0.5:
        parts.append(f"{sector}板块承压")

    if c_s > 0.5:
        parts.append("基金自身指标表现良好")
    elif c_s < -0.5:
        parts.append("基金自身指标偏弱")

    # 结尾：操作建议
    if rec == "BUY":
        parts.append(f"综合评分{d_score:+.2f}，三个维度都偏正面，建议积极加仓")
    elif rec == "BUY_SMALL":
        parts.append(f"综合评分{d_score:+.2f}，方向偏正面但有不确定性，建议小额试探")
    elif rec == "VETO":
        parts.append(f"综合评分{d_score:+.2f}，风险信号较多，建议适当减仓控制风险")
    else:
        parts.append(f"综合评分{d_score:+.2f}，利好利空交织，建议持有观望等待信号明朗")

    return "。".join(parts) + "。"


# ══════════════════════════════════════════════
# 3. 风险预警报告
# ══════════════════════════════════════════════

def generate_risk_report(
    snapshot: Dict,
    all_fund_results: List[Dict],
    regime_name: str,
) -> Dict:
    """
    生成风险预警报告
    """
    alerts = []
    level = "normal"  # normal / caution / warning / danger

    # 体制性风险
    if regime_name in ("外部冲击", "流动性危机"):
        alerts.append({
            "level": "high",
            "category": "系统性风险",
            "title": f"当前处于{regime_name}阶段",
            "detail": "市场整体风险偏高，建议降低仓位至50%以下",
        })
        level = "danger"

    # 集中度风险
    if all_fund_results:
        total_value = sum(r["fund"].get("current_value", 0) for r in all_fund_results)
        if total_value > 0:
            for r in all_fund_results:
                fund = r["fund"]
                pct = fund.get("current_value", 0) / total_value * 100
                if pct > 30:
                    alerts.append({
                        "level": "medium",
                        "category": "集中度风险",
                        "title": f"{fund['name']}占比过高（{pct:.0f}%）",
                        "detail": "单一基金占比超过30%，建议分散到其他基金",
                    })
                    level = max(level, "caution", key=lambda x: ["normal", "caution", "warning", "danger"].index(x))

    # 止损风险
    if all_fund_results:
        for r in all_fund_results:
            fund = r["fund"]
            ret = fund.get("total_return", 0)
            val = fund.get("current_value", 0)
            stop_loss = fund.get("stop_loss", -0.12)
            if val > 0:
                ret_pct = ret / val
                if ret_pct < stop_loss * 0.8:
                    alerts.append({
                        "level": "high",
                        "category": "止损预警",
                        "title": f"{fund['name']}接近止损线",
                        "detail": f"当前亏损{ret_pct*100:.1f}%，止损线{stop_loss*100:.0f}%，建议重点关注",
                    })
                    level = "warning"

    # D分数极端值
    if all_fund_results:
        for r in all_fund_results:
            d = r.get("comp", {}).get("d_score", 0)
            if d < -1.2:
                alerts.append({
                    "level": "high",
                    "category": "因子预警",
                    "title": f"{r['fund']['name']}D分极低（{d:+.2f}）",
                    "detail": "三层因子模型给出强烈减仓信号",
                })

    # 汇率风险（QDII）
    usdcny = snapshot.get("USDCNY=X", {})
    if usdcny.get("price") and usdcny["price"] > 7.3:
        alerts.append({
            "level": "medium",
            "category": "汇率风险",
            "title": "人民币偏弱影响QDII",
            "detail": f"当前汇率{usdcny['price']:.2f}，持有QDII基金（全球新能源车）需注意汇率波动",
        })

    if not alerts:
        alerts.append({
            "level": "low",
            "category": "系统检查",
            "title": "暂无重大风险预警",
            "detail": "当前各项指标正常，继续执行既定投资策略即可",
        })

    # 确定整体风险等级
    high_count = sum(1 for a in alerts if a["level"] == "high")
    if high_count >= 3:
        level = "danger"
    elif high_count >= 1:
        level = "warning"

    return {
        "level": level,
        "level_cn": {"normal": "正常", "caution": "关注", "warning": "预警", "danger": "危险"}.get(level, "未知"),
        "alerts": alerts,
        "total_alerts": len(alerts),
        "high_alerts": high_count,
    }


# ══════════════════════════════════════════════
# 4. 综合投资策略建议
# ══════════════════════════════════════════════

def generate_strategy_advice(
    regime_name: str,
    portfolio_opt: Dict = None,
    risk_report: Dict = None,
    all_fund_results: List[Dict] = None,
) -> str:
    """
    生成综合投资策略建议（自然语言段落）
    """
    parts = []
    now = datetime.datetime.now().strftime("%m月%d日")

    # 开头
    parts.append(f"【{now}投资策略建议】")

    # 经济环境
    env_map = {
        "扩张期": "当前经济处于扩张周期，企业盈利整体向好。建议维持较高仓位（70-90%），重点配置科技成长和顺周期板块。",
        "放缓期": "经济增速有所放缓，结构性机会为主。建议中等仓位（50-70%），均衡配置，增加红利低波防御比例。",
        "衰退修复": "经济正从低谷恢复，是中长期布局窗口。建议逐步加仓（40-60%），可以定投方式分批建仓。",
        "外部冲击": "外部事件冲击市场，短期波动加剧。建议降低仓位（30-50%），持有防御性资产，等待冲击消退。",
        "流动性危机": "市场流动性紧张，系统性风险升高。建议大幅减仓（<30%），以现金和低风险资产为主。",
    }
    parts.append(env_map.get(regime_name, "当前环境不明朗，建议保持中等仓位。"))

    # 组合优化建议
    if portfolio_opt and portfolio_opt.get("status") == "ok":
        rec_strategy = portfolio_opt.get("recommended_strategy", "")
        rebalance = portfolio_opt.get("rebalance", [])
        add_funds = [r for r in rebalance if r["action"] == "加仓"]
        cut_funds = [r for r in rebalance if r["action"] == "减仓"]
        if add_funds or cut_funds:
            rebal_parts = []
            if add_funds:
                names = "、".join(r["name"] for r in add_funds[:3])
                rebal_parts.append(f"建议加仓：{names}")
            if cut_funds:
                names = "、".join(r["name"] for r in cut_funds[:3])
                rebal_parts.append(f"建议减仓：{names}")
            parts.append(f"根据{rec_strategy}模型优化，" + "，".join(rebal_parts) + "。")

    # 风险提示
    if risk_report:
        high_alerts = [a for a in risk_report.get("alerts", []) if a["level"] == "high"]
        if high_alerts:
            alert_text = "、".join(a["title"] for a in high_alerts[:3])
            parts.append(f"重点风险提示：{alert_text}。请优先处理减仓操作。")

    # D分最高和最低的基金
    if all_fund_results:
        sorted_by_d = sorted(all_fund_results, key=lambda r: r.get("comp", {}).get("d_score", 0), reverse=True)
        best = sorted_by_d[0]
        worst = sorted_by_d[-1]
        best_d = best.get("comp", {}).get("d_score", 0)
        worst_d = worst.get("comp", {}).get("d_score", 0)
        parts.append(
            f"当前最看好{best['fund']['name']}（D分{best_d:+.2f}），"
            f"最需谨慎{worst['fund']['name']}（D分{worst_d:+.2f}）。"
        )

    return "\n\n".join(parts)
