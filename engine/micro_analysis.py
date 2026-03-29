"""
微观深度分析引擎 — Micro Analysis Engine
分析基金持仓公司经营情况、持仓变化、风格漂移、基金经理能力等
"""

import requests
import re
import json
import time
import logging
import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
}


# ══════════════════════════════════════════════
# 1. 持仓公司基本面分析
# ══════════════════════════════════════════════

def analyze_holdings_fundamentals(fund_code: str) -> Dict:
    """
    分析基金前十大重仓股的基本面
    返回每只股票的PE、市值、行业、盈利增长等
    """
    holdings = _get_fund_holdings_detail(fund_code)
    if not holdings:
        return {"holdings": [], "summary": "持仓数据暂不可用", "score": 0}

    analyzed = []
    total_pe = 0
    pe_count = 0
    growth_scores = []
    risk_flags = []

    for h in holdings:
        stock_code = h.get("stock_code", "")
        stock_name = h.get("stock_name", "")
        hold_pct = h.get("hold_pct", 0)

        # 获取股票基本面
        fundamentals = _get_stock_fundamentals(stock_code)

        pe = fundamentals.get("pe")
        pb = fundamentals.get("pb")
        market_cap = fundamentals.get("market_cap")  # 亿元
        industry = fundamentals.get("industry", "")
        revenue_growth = fundamentals.get("revenue_growth")
        profit_growth = fundamentals.get("profit_growth")
        roe = fundamentals.get("roe")

        # 估值评估
        valuation = "合理"
        if pe is not None:
            total_pe += pe * hold_pct
            pe_count += hold_pct
            if pe > 80:
                valuation = "偏高"
                risk_flags.append(f"{stock_name}市盈率{pe:.0f}倍偏高")
            elif pe > 40:
                valuation = "适中偏高"
            elif pe < 0:
                valuation = "亏损"
                risk_flags.append(f"{stock_name}当前亏损（PE为负）")
            elif pe < 15:
                valuation = "偏低"

        # 成长性评估
        growth_word = "未知"
        growth_score = 0
        if profit_growth is not None:
            if profit_growth > 30:
                growth_word = "高速增长"
                growth_score = 2
            elif profit_growth > 10:
                growth_word = "稳健增长"
                growth_score = 1
            elif profit_growth > 0:
                growth_word = "低速增长"
                growth_score = 0.5
            elif profit_growth > -20:
                growth_word = "利润下滑"
                growth_score = -1
            else:
                growth_word = "大幅下滑"
                growth_score = -2
                risk_flags.append(f"{stock_name}利润同比下滑{abs(profit_growth):.0f}%")
            growth_scores.append(growth_score * hold_pct)

        # 市值分类
        cap_class = "未知"
        if market_cap is not None:
            if market_cap > 1000:
                cap_class = "大盘股"
            elif market_cap > 200:
                cap_class = "中盘股"
            else:
                cap_class = "小盘股"

        analyzed.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "hold_pct": hold_pct,
            "industry": industry,
            "market_cap": market_cap,
            "cap_class": cap_class,
            "pe": pe,
            "pb": pb,
            "roe": roe,
            "revenue_growth": revenue_growth,
            "profit_growth": profit_growth,
            "valuation": valuation,
            "growth_word": growth_word,
            "growth_score": growth_score,
        })

    # 综合评估
    avg_pe = (total_pe / pe_count) if pe_count > 0 else None
    avg_growth_score = (sum(growth_scores) / sum(h["hold_pct"] for h in analyzed)) if analyzed else 0

    # 集中度分析
    top3_pct = sum(h["hold_pct"] for h in analyzed[:3])
    concentration_risk = "高" if top3_pct > 30 else "中" if top3_pct > 20 else "低"

    # 行业分布
    industry_dist = {}
    for h in analyzed:
        ind = h.get("industry", "其他")
        industry_dist[ind] = industry_dist.get(ind, 0) + h["hold_pct"]

    # 生成投资评分 [-2, +2]
    micro_score = 0
    if avg_pe is not None:
        if avg_pe < 20:
            micro_score += 0.5
        elif avg_pe > 60:
            micro_score -= 0.5
    if avg_growth_score > 0.5:
        micro_score += 1.0
    elif avg_growth_score < -0.5:
        micro_score -= 1.0
    if top3_pct > 35:
        micro_score -= 0.3  # 集中度过高扣分
    micro_score = max(-2, min(2, micro_score))

    # 生成通俗总结
    summary_parts = []
    if avg_pe is not None:
        pe_word = "估值偏低（便宜）" if avg_pe < 20 else "估值适中" if avg_pe < 40 else "估值偏高（贵）"
        summary_parts.append(f"加权平均市盈率{avg_pe:.0f}倍，{pe_word}")
    if growth_scores:
        gw = "整体盈利增长良好" if avg_growth_score > 0.5 else "盈利增长一般" if avg_growth_score > -0.5 else "部分公司利润下滑"
        summary_parts.append(gw)
    summary_parts.append(f"前3大重仓占比{top3_pct:.1f}%，集中度{concentration_risk}")
    if risk_flags:
        summary_parts.append(f"风险提示：{'; '.join(risk_flags[:3])}")

    return {
        "holdings": analyzed,
        "avg_pe": avg_pe,
        "avg_growth_score": avg_growth_score,
        "top3_pct": top3_pct,
        "concentration_risk": concentration_risk,
        "industry_distribution": industry_dist,
        "risk_flags": risk_flags,
        "micro_score": round(micro_score, 2),
        "summary": "；".join(summary_parts),
    }


# ══════════════════════════════════════════════
# 2. 持仓变动追踪
# ══════════════════════════════════════════════

def analyze_position_changes(fund_code: str) -> Dict:
    """
    分析基金最近一期持仓相比上一期的变动
    包括：新进、增持、减持、退出的股票
    """
    changes = _get_position_changes(fund_code)
    if not changes:
        return {
            "changes": [],
            "summary": "持仓变动数据暂不可用（通常季报/半年报公布后更新）",
            "new_entries": [],
            "increased": [],
            "decreased": [],
            "exited": [],
            "turnover_signal": "unknown",
        }

    new_entries = [c for c in changes if c.get("change_type") == "新进"]
    increased = [c for c in changes if c.get("change_type") == "增持"]
    decreased = [c for c in changes if c.get("change_type") == "减持"]
    exited = [c for c in changes if c.get("change_type") == "退出"]

    # 换手率信号
    total_changes = len(new_entries) + len(exited)
    if total_changes >= 5:
        turnover_signal = "high"
        turnover_word = "大幅调仓（基金经理策略可能有重大变化）"
    elif total_changes >= 2:
        turnover_signal = "moderate"
        turnover_word = "适度调仓（正常的持仓优化）"
    else:
        turnover_signal = "low"
        turnover_word = "持仓稳定（基金经理对当前配置较有信心）"

    summary_parts = [turnover_word]
    if new_entries:
        names = "、".join(c["stock_name"] for c in new_entries[:3])
        summary_parts.append(f"新买入：{names}")
    if exited:
        names = "、".join(c["stock_name"] for c in exited[:3])
        summary_parts.append(f"已卖出：{names}")

    return {
        "changes": changes,
        "new_entries": new_entries,
        "increased": increased,
        "decreased": decreased,
        "exited": exited,
        "turnover_signal": turnover_signal,
        "summary": "；".join(summary_parts),
    }


# ══════════════════════════════════════════════
# 3. 基金风格分析
# ══════════════════════════════════════════════

def analyze_fund_style(fund_code: str, holdings_analysis: Dict = None) -> Dict:
    """
    分析基金投资风格：成长/价值、大盘/小盘
    """
    if not holdings_analysis:
        holdings_analysis = analyze_holdings_fundamentals(fund_code)

    holdings = holdings_analysis.get("holdings", [])
    if not holdings:
        return {"style": "未知", "style_detail": {}, "summary": "数据不足无法分析风格"}

    # 市值风格
    large_cap_pct = sum(h["hold_pct"] for h in holdings if h.get("cap_class") == "大盘股")
    mid_cap_pct = sum(h["hold_pct"] for h in holdings if h.get("cap_class") == "中盘股")
    small_cap_pct = sum(h["hold_pct"] for h in holdings if h.get("cap_class") == "小盘股")
    total_pct = large_cap_pct + mid_cap_pct + small_cap_pct

    if total_pct > 0:
        if large_cap_pct / total_pct > 0.6:
            cap_style = "大盘"
        elif small_cap_pct / total_pct > 0.4:
            cap_style = "小盘"
        else:
            cap_style = "中盘"
    else:
        cap_style = "未知"

    # 成长/价值风格
    avg_pe = holdings_analysis.get("avg_pe")
    avg_growth = holdings_analysis.get("avg_growth_score", 0)
    if avg_pe is not None:
        if avg_pe > 40 and avg_growth > 0.5:
            value_style = "成长"
        elif avg_pe < 20:
            value_style = "价值"
        else:
            value_style = "均衡"
    else:
        value_style = "未知"

    style = f"{cap_style}{value_style}"

    # 行业集中度
    ind_dist = holdings_analysis.get("industry_distribution", {})
    top_industry = max(ind_dist.items(), key=lambda x: x[1]) if ind_dist else ("未知", 0)

    summary = f"风格：{style}型 | 主要行业：{top_industry[0]}（占{top_industry[1]:.1f}%）"
    if cap_style == "小盘":
        summary += " | 小盘股比例高，波动可能较大"

    return {
        "style": style,
        "cap_style": cap_style,
        "value_style": value_style,
        "large_cap_pct": large_cap_pct,
        "mid_cap_pct": mid_cap_pct,
        "small_cap_pct": small_cap_pct,
        "top_industry": top_industry,
        "industry_distribution": ind_dist,
        "summary": summary,
    }


# ══════════════════════════════════════════════
# 4. 基金经理评估
# ══════════════════════════════════════════════

def analyze_fund_manager(fund_code: str) -> Dict:
    """
    评估基金经理的能力和风格
    """
    info = _get_manager_info(fund_code)
    if not info:
        return {"manager": "未知", "summary": "基金经理信息暂不可用", "score": 0}

    manager_name = info.get("name", "未知")
    experience_years = info.get("experience_years", 0)
    total_return = info.get("best_return")
    current_funds_count = info.get("funds_count", 0)

    # 评估
    score = 0
    summary_parts = [f"基金经理：{manager_name}"]

    if experience_years:
        if experience_years >= 7:
            score += 1.0
            summary_parts.append(f"从业{experience_years}年（经验丰富）")
        elif experience_years >= 3:
            score += 0.5
            summary_parts.append(f"从业{experience_years}年（经验适中）")
        else:
            score -= 0.5
            summary_parts.append(f"从业{experience_years}年（经验尚浅）")

    if current_funds_count:
        if current_funds_count > 8:
            score -= 0.3
            summary_parts.append(f"同时管理{current_funds_count}只基金（管理精力可能分散）")
        else:
            summary_parts.append(f"管理{current_funds_count}只基金")

    return {
        "manager": manager_name,
        "experience_years": experience_years,
        "funds_count": current_funds_count,
        "total_return": total_return,
        "score": round(max(-2, min(2, score)), 2),
        "summary": "；".join(summary_parts),
    }


# ══════════════════════════════════════════════
# 5. 综合微观分析报告
# ══════════════════════════════════════════════

def full_micro_analysis(fund_code: str) -> Dict:
    """
    一次性运行所有微观分析，返回综合报告
    """
    holdings_result = analyze_holdings_fundamentals(fund_code)
    changes_result = analyze_position_changes(fund_code)
    style_result = analyze_fund_style(fund_code, holdings_result)
    manager_result = analyze_fund_manager(fund_code)

    # 综合微观评分
    h_score = holdings_result.get("micro_score", 0)
    m_score = manager_result.get("score", 0)

    # 持仓变动对评分的影响
    change_adj = 0
    if changes_result.get("turnover_signal") == "high":
        change_adj = -0.3  # 大幅调仓增加不确定性
    elif changes_result.get("turnover_signal") == "low":
        change_adj = 0.2   # 持仓稳定加分

    composite_micro = round(max(-2, min(2, h_score * 0.5 + m_score * 0.3 + change_adj)), 2)

    # 生成投资建议
    if composite_micro > 0.8:
        recommendation = "微观面支持买入：持仓公司基本面良好，基金经理稳健"
    elif composite_micro > 0:
        recommendation = "微观面中性偏正：整体还行，但有一些需要关注的点"
    elif composite_micro > -0.5:
        recommendation = "微观面中性偏弱：部分持仓公司状况一般，观望为主"
    else:
        recommendation = "微观面偏弱：持仓公司基本面有压力或估值偏高，谨慎"

    # 风险提示
    risks = holdings_result.get("risk_flags", [])
    if changes_result.get("turnover_signal") == "high":
        risks.append("基金经理近期大幅调仓，策略方向可能发生变化")
    if style_result.get("cap_style") == "小盘":
        risks.append("持仓以小盘股为主，流动性风险偏高")

    return {
        "holdings_analysis": holdings_result,
        "position_changes": changes_result,
        "style_analysis": style_result,
        "manager_analysis": manager_result,
        "composite_micro_score": composite_micro,
        "recommendation": recommendation,
        "risks": risks,
    }


# ══════════════════════════════════════════════
# 数据获取层（内部函数）
# ══════════════════════════════════════════════

def _get_fund_holdings_detail(fund_code: str) -> List[Dict]:
    """获取基金持仓明细（含股票代码）"""
    # 方法1：天天基金pingzhongdata
    try:
        url = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
        headers = {**_HEADERS, "Referer": f"https://fund.eastmoney.com/{fund_code}.html"}
        r = requests.get(url, headers=headers, timeout=2)
        text = r.text

        match = re.search(r'var\s+stockCodesNew\s*=\s*"([^"]*)"', text)
        if match and match.group(1):
            codes_str = match.group(1)
            stocks = []
            for item in codes_str.split(","):
                parts = item.split("~")
                if len(parts) >= 4:
                    market = parts[0]  # 1=SZ, 0=SH
                    code = parts[1]
                    name = parts[2]
                    pct = float(parts[3]) if parts[3] else 0
                    stocks.append({
                        "stock_code": code,
                        "stock_name": name,
                        "hold_pct": pct,
                        "market": "SZ" if market == "1" else "SH",
                    })
            return stocks
    except Exception as e:
        logger.warning(f"持仓明细获取失败 {fund_code}: {e}")

    # 本地静态缓存回退
    try:
        from data.fund_static_data import get_static_holdings
        holdings = get_static_holdings(fund_code)
        if holdings:
            # 补充 market 字段
            for h in holdings:
                code = h.get("stock_code", "")
                if code.startswith("6"):
                    h["market"] = "SH"
                else:
                    h["market"] = "SZ"
            return holdings
    except Exception:
        pass
    return []


def _get_stock_fundamentals(stock_code: str) -> Dict:
    """获取单只股票基本面数据"""
    result = {
        "pe": None, "pb": None, "market_cap": None,
        "industry": "", "revenue_growth": None,
        "profit_growth": None, "roe": None,
    }
    try:
        # 新浪财经实时数据获取PE/PB/市值
        # 判断沪深
        if stock_code.startswith("6"):
            sina_code = f"sh{stock_code}"
        else:
            sina_code = f"sz{stock_code}"

        url = f"https://hq.sinajs.cn/list={sina_code}"
        headers = {**_HEADERS, "Referer": "https://finance.sina.com.cn"}
        r = requests.get(url, headers=headers, timeout=2)
        text = r.text
        match = re.search(r'"(.*)"', text)
        if match:
            parts = match.group(1).split(",")
            if len(parts) > 3:
                price = float(parts[3]) if parts[3] else None
                # 新浪不直接给PE，我们用东方财富
    except Exception:
        pass

    # 东方财富个股基本面
    try:
        # F10数据接口
        if stock_code.startswith("6"):
            secid = f"1.{stock_code}"
        else:
            secid = f"0.{stock_code}"

        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "secid": secid,
            "fields": "f2,f3,f9,f20,f23,f37,f100,f116,f117",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }
        r = requests.get(url, params=params, headers=_HEADERS, timeout=2)
        data = r.json().get("data") or {}
        if data:
            pe_raw = data.get("f9")
            pb_raw = data.get("f23")
            market_cap_raw = data.get("f20")  # 总市值(元)
            roe_raw = data.get("f37")
            industry = data.get("f100", "")

            result["pe"] = float(pe_raw) if pe_raw and pe_raw != "-" else None
            result["pb"] = float(pb_raw) if pb_raw and pb_raw != "-" else None
            result["roe"] = float(roe_raw) if roe_raw and roe_raw != "-" else None
            result["industry"] = industry or ""

            if market_cap_raw and market_cap_raw != "-":
                result["market_cap"] = round(float(market_cap_raw) / 1e8, 1)  # 转亿元
    except Exception as e:
        logger.debug(f"股票基本面 {stock_code}: {e}")

    # 如果东方财富也获取失败，使用静态数据
    if result["pe"] is None and result["market_cap"] is None:
        static = _get_static_stock_fundamentals(stock_code)
        if static:
            result.update(static)
            return result

    # 财务增长数据（东方财富datacenter）
    try:
        if stock_code.startswith("6"):
            secid = f"1.{stock_code}"
        else:
            secid = f"0.{stock_code}"

        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            "reportName": "RPT_F10_FINANCE_MAINFINADATA",
            "columns": "SECURITY_CODE,REPORT_DATE,TOTAL_OPERATE_INCOME_YOY,NETPROFIT_YOY",
            "filter": f"(SECURITY_CODE=\"{stock_code}\")",
            "pageNumber": 1, "pageSize": 1,
            "sortColumns": "REPORT_DATE", "sortTypes": "-1",
            "source": "WEB", "client": "WEB",
        }
        r = requests.get(url, params=params, headers=_HEADERS, timeout=2)
        records = (r.json().get("result") or {}).get("data", [])
        if records:
            rec = records[0]
            rev_yoy = rec.get("TOTAL_OPERATE_INCOME_YOY")
            profit_yoy = rec.get("NETPROFIT_YOY")
            if rev_yoy is not None:
                result["revenue_growth"] = round(float(rev_yoy), 1)
            if profit_yoy is not None:
                result["profit_growth"] = round(float(profit_yoy), 1)
    except Exception as e:
        logger.debug(f"财务增长 {stock_code}: {e}")

    return result


def _get_position_changes(fund_code: str) -> List[Dict]:
    """获取基金持仓变动（本期vs上期）"""
    try:
        url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNInverstPosition"
        params = {
            "plat": "Android", "appType": "ttjj",
            "product": "EFund", "version": "6.4.8",
            "fundCode": fund_code,
            "deviceid": "xxx", "Mession": "xxx",
        }
        r = requests.get(url, params=params, headers=_HEADERS, timeout=2)
        data = r.json()
        quarters = (data.get("Datas") or {}).get("InverstPositionDetail", [])

        if len(quarters) < 2:
            # 只有一期数据，无法对比
            if quarters:
                q = quarters[0]
                stocks = q.get("InverstDetail", [])
                return [
                    {
                        "stock_code": s.get("GPDM", ""),
                        "stock_name": s.get("GPJC", ""),
                        "hold_pct": float(s.get("JZBL", 0) or 0),
                        "change_type": "当期持仓",
                        "report_date": q.get("FSRQ", ""),
                    }
                    for s in stocks
                ]
            return []

        current_q = quarters[0]
        prev_q = quarters[1]

        current_stocks = {s.get("GPDM"): s for s in current_q.get("InverstDetail", [])}
        prev_stocks = {s.get("GPDM"): s for s in prev_q.get("InverstDetail", [])}

        changes = []
        for code, s in current_stocks.items():
            name = s.get("GPJC", "")
            cur_pct = float(s.get("JZBL", 0) or 0)
            if code in prev_stocks:
                prev_pct = float(prev_stocks[code].get("JZBL", 0) or 0)
                diff = cur_pct - prev_pct
                if diff > 0.5:
                    change_type = "增持"
                elif diff < -0.5:
                    change_type = "减持"
                else:
                    change_type = "不变"
                changes.append({
                    "stock_code": code,
                    "stock_name": name,
                    "hold_pct": cur_pct,
                    "prev_pct": prev_pct,
                    "change_pct": round(diff, 2),
                    "change_type": change_type,
                    "report_date": current_q.get("FSRQ", ""),
                })
            else:
                changes.append({
                    "stock_code": code,
                    "stock_name": name,
                    "hold_pct": cur_pct,
                    "prev_pct": 0,
                    "change_pct": cur_pct,
                    "change_type": "新进",
                    "report_date": current_q.get("FSRQ", ""),
                })

        for code, s in prev_stocks.items():
            if code not in current_stocks:
                changes.append({
                    "stock_code": code,
                    "stock_name": s.get("GPJC", ""),
                    "hold_pct": 0,
                    "prev_pct": float(s.get("JZBL", 0) or 0),
                    "change_pct": -float(s.get("JZBL", 0) or 0),
                    "change_type": "退出",
                    "report_date": current_q.get("FSRQ", ""),
                })

        return sorted(changes, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)

    except Exception as e:
        logger.warning(f"持仓变动获取失败 {fund_code}: {e}")
    return []


def _get_manager_info(fund_code: str) -> Dict:
    """获取基金经理信息"""
    try:
        url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNInformation"
        params = {
            "plat": "Android", "appType": "ttjj",
            "product": "EFund", "version": "6.4.8",
            "fundCode": fund_code,
        }
        r = requests.get(url, params=params, headers=_HEADERS, timeout=2)
        data = r.json()
        datas = data.get("Datas") or {}

        manager_name = datas.get("JJJL", "")
        # 从业年限
        start_date_str = datas.get("JJJLNX", "")
        exp_years = 0
        if start_date_str:
            try:
                parts = start_date_str.split("年")
                if parts:
                    exp_years = float(parts[0].strip())
            except Exception:
                pass

        return {
            "name": manager_name,
            "experience_years": exp_years,
            "funds_count": 0,  # 需要额外接口
            "best_return": None,
        }
    except Exception as e:
        logger.warning(f"基金经理信息 {fund_code}: {e}")

    # 本地静态缓存回退
    try:
        from data.fund_static_data import get_static_basic_info
        info = get_static_basic_info(fund_code)
        if info.get("manager"):
            return {
                "name": info["manager"],
                "experience_years": _MANAGER_EXPERIENCE.get(info["manager"], 5),
                "funds_count": 3,
                "best_return": None,
            }
    except Exception:
        pass
    return {}


# ══════════════════════════════════════════════
# 静态数据回退
# ══════════════════════════════════════════════

# 基金经理从业年限缓存
_MANAGER_EXPERIENCE = {
    "董山青": 8, "刘为": 4, "田光远": 6, "章赟": 9,
    "李孝华": 7, "庄智渊": 5, "俞诚": 8, "李茜": 10,
    "杨宇": 6, "鲁衡军": 7,
}

# 常见A股基本面数据缓存
_STATIC_STOCK_FUNDAMENTALS = {
    "300750": {"pe": 28, "pb": 5.2, "market_cap": 9500, "industry": "电力设备", "revenue_growth": 12.5, "profit_growth": 15.8, "roe": 22.0},
    "600519": {"pe": 30, "pb": 9.5, "market_cap": 22000, "industry": "食品饮料", "revenue_growth": 16.0, "profit_growth": 18.5, "roe": 33.0},
    "002594": {"pe": 22, "pb": 4.8, "market_cap": 8500, "industry": "汽车", "revenue_growth": 25.0, "profit_growth": 30.2, "roe": 18.5},
    "600036": {"pe": 7, "pb": 1.1, "market_cap": 8800, "industry": "银行", "revenue_growth": 5.0, "profit_growth": 8.2, "roe": 16.5},
    "601012": {"pe": 15, "pb": 1.5, "market_cap": 2200, "industry": "电力设备", "revenue_growth": -10.5, "profit_growth": -25.0, "roe": 8.0},
    "601318": {"pe": 10, "pb": 1.3, "market_cap": 9200, "industry": "保险", "revenue_growth": 8.0, "profit_growth": 12.0, "roe": 15.0},
    "300760": {"pe": 45, "pb": 12.0, "market_cap": 4500, "industry": "医疗器械", "revenue_growth": 20.0, "profit_growth": 22.0, "roe": 28.0},
    "600276": {"pe": 55, "pb": 8.5, "market_cap": 3200, "industry": "医药", "revenue_growth": 15.0, "profit_growth": 18.0, "roe": 16.0},
    "601899": {"pe": 12, "pb": 3.8, "market_cap": 4800, "industry": "有色金属", "revenue_growth": 18.0, "profit_growth": 25.0, "roe": 20.0},
    "000858": {"pe": 25, "pb": 7.0, "market_cap": 7500, "industry": "食品饮料", "revenue_growth": 12.0, "profit_growth": 14.0, "roe": 25.0},
    "002230": {"pe": 60, "pb": 5.5, "market_cap": 1500, "industry": "计算机", "revenue_growth": 22.0, "profit_growth": 28.0, "roe": 12.0},
    "688111": {"pe": 80, "pb": 15.0, "market_cap": 1200, "industry": "计算机", "revenue_growth": 18.0, "profit_growth": 20.0, "roe": 22.0},
    "688041": {"pe": 120, "pb": 18.0, "market_cap": 2500, "industry": "半导体", "revenue_growth": 50.0, "profit_growth": 65.0, "roe": 15.0},
    "688981": {"pe": 35, "pb": 3.0, "market_cap": 4500, "industry": "半导体", "revenue_growth": 20.0, "profit_growth": 25.0, "roe": 10.0},
    "300782": {"pe": 55, "pb": 8.0, "market_cap": 500, "industry": "半导体", "revenue_growth": 15.0, "profit_growth": 22.0, "roe": 18.0},
    "603259": {"pe": 32, "pb": 5.0, "market_cap": 2800, "industry": "医药", "revenue_growth": 10.0, "profit_growth": 8.0, "roe": 16.0},
    "002050": {"pe": 30, "pb": 5.5, "market_cap": 1100, "industry": "家用电器", "revenue_growth": 20.0, "profit_growth": 25.0, "roe": 20.0},
    "300124": {"pe": 42, "pb": 8.0, "market_cap": 2200, "industry": "电气设备", "revenue_growth": 25.0, "profit_growth": 30.0, "roe": 22.0},
    "600900": {"pe": 18, "pb": 3.5, "market_cap": 5500, "industry": "电力", "revenue_growth": 8.0, "profit_growth": 12.0, "roe": 15.0},
    "600011": {"pe": 10, "pb": 1.2, "market_cap": 1800, "industry": "电力", "revenue_growth": 5.0, "profit_growth": 15.0, "roe": 12.0},
    "600795": {"pe": 12, "pb": 1.5, "market_cap": 1500, "industry": "电力", "revenue_growth": 6.0, "profit_growth": 10.0, "roe": 10.0},
    "601985": {"pe": 15, "pb": 2.0, "market_cap": 1800, "industry": "电力", "revenue_growth": 10.0, "profit_growth": 18.0, "roe": 12.0},
    "600905": {"pe": 20, "pb": 2.5, "market_cap": 900, "industry": "电力", "revenue_growth": 15.0, "profit_growth": 20.0, "roe": 10.0},
    "002415": {"pe": 22, "pb": 4.5, "market_cap": 4200, "industry": "计算机", "revenue_growth": 12.0, "profit_growth": 15.0, "roe": 22.0},
    "688256": {"pe": 300, "pb": 25.0, "market_cap": 2800, "industry": "半导体", "revenue_growth": 80.0, "profit_growth": 120.0, "roe": 8.0},
    "688008": {"pe": 50, "pb": 6.0, "market_cap": 800, "industry": "半导体", "revenue_growth": 18.0, "profit_growth": 22.0, "roe": 15.0},
    "688012": {"pe": 65, "pb": 8.0, "market_cap": 1200, "industry": "半导体", "revenue_growth": 30.0, "profit_growth": 35.0, "roe": 12.0},
    "688036": {"pe": 18, "pb": 3.5, "market_cap": 1500, "industry": "通信设备", "revenue_growth": 25.0, "profit_growth": 30.0, "roe": 20.0},
    "688017": {"pe": 95, "pb": 10.0, "market_cap": 350, "industry": "机械设备", "revenue_growth": 30.0, "profit_growth": 35.0, "roe": 12.0},
    "300607": {"pe": 50, "pb": 4.0, "market_cap": 200, "industry": "机械设备", "revenue_growth": 20.0, "profit_growth": 25.0, "roe": 10.0},
    "002747": {"pe": 80, "pb": 5.0, "market_cap": 250, "industry": "机械设备", "revenue_growth": 22.0, "profit_growth": 28.0, "roe": 8.0},
    "300024": {"pe": 90, "pb": 6.0, "market_cap": 400, "industry": "机械设备", "revenue_growth": 18.0, "profit_growth": 20.0, "roe": 7.0},
    "601088": {"pe": 10, "pb": 2.0, "market_cap": 7500, "industry": "煤炭", "revenue_growth": 2.0, "profit_growth": -5.0, "roe": 18.0},
    "600028": {"pe": 12, "pb": 1.0, "market_cap": 6500, "industry": "石油石化", "revenue_growth": 3.0, "profit_growth": -8.0, "roe": 10.0},
    "601006": {"pe": 8, "pb": 0.9, "market_cap": 1200, "industry": "交通运输", "revenue_growth": -2.0, "profit_growth": -5.0, "roe": 12.0},
    "601988": {"pe": 5, "pb": 0.5, "market_cap": 10000, "industry": "银行", "revenue_growth": 3.0, "profit_growth": 5.0, "roe": 10.0},
    "601288": {"pe": 5, "pb": 0.6, "market_cap": 12000, "industry": "银行", "revenue_growth": 4.0, "profit_growth": 6.0, "roe": 11.0},
    "000651": {"pe": 9, "pb": 2.5, "market_cap": 2200, "industry": "家用电器", "revenue_growth": 8.0, "profit_growth": 10.0, "roe": 25.0},
    "601127": {"pe": 35, "pb": 6.0, "market_cap": 1800, "industry": "汽车", "revenue_growth": 40.0, "profit_growth": 50.0, "roe": 15.0},
    "300308": {"pe": 40, "pb": 12.0, "market_cap": 1500, "industry": "通信设备", "revenue_growth": 45.0, "profit_growth": 55.0, "roe": 25.0},
    "300274": {"pe": 25, "pb": 5.0, "market_cap": 1800, "industry": "电力设备", "revenue_growth": 20.0, "profit_growth": 22.0, "roe": 18.0},
}


def _get_static_stock_fundamentals(stock_code: str) -> Optional[Dict]:
    """静态股票基本面数据（离线回退）"""
    return _STATIC_STOCK_FUNDAMENTALS.get(stock_code)
