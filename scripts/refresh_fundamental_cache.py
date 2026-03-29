#!/usr/bin/env python3
"""
基本面数据缓存刷新脚本
========================
在国内网络环境下运行，抓取最新基金持仓/经理数据，写入 fundamental_cache.py。
然后 git push 更新线上部署。

使用方式：
  cd ~/Desktop/fund_monitor
  python3 scripts/refresh_fundamental_cache.py
  git add -A && git commit -m "data: 刷新基本面缓存" && git push

建议频率：每季度基金季报发布后运行一次（1月/4月/7月/10月）
"""

import requests
import json
import re
import time
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FUNDS

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://fund.eastmoney.com/",
}

EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://data.eastmoney.com/",
}


def safe_float(val):
    if val is None:
        return None
    try:
        f = float(str(val).replace(",", "").strip())
        return f if f == f else None
    except (ValueError, TypeError):
        return None


def get_fund_holdings(fund_code: str) -> list:
    """获取基金前十大持仓"""
    try:
        url = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
        r = requests.get(url, headers=HEADERS, timeout=10)
        text = r.text

        # 提取持仓股票代码
        m = re.search(r'var stockCodesNew="([^"]*)"', text)
        if not m or not m.group(1).strip():
            return []

        codes_str = m.group(1).strip().rstrip(",")
        stock_codes = [c.strip() for c in codes_str.split(",") if c.strip()]

        # 提取持仓比例
        m2 = re.search(r'var stockPercent="([^"]*)"', text)
        percents = []
        if m2 and m2.group(1).strip():
            percents = [safe_float(p) for p in m2.group(1).strip().rstrip(",").split(",")]

        holdings = []
        for i, code in enumerate(stock_codes[:10]):
            pct = percents[i] if i < len(percents) else 0
            holdings.append({
                "stock_code": code,
                "hold_pct": pct or 0,
            })
        return holdings
    except Exception as e:
        print(f"  [WARN] 持仓获取失败 {fund_code}: {e}")
        return []


def get_stock_info(stock_code: str) -> dict:
    """获取单只股票的 PE/PB/名称/行业"""
    # 东方财富 secid: 沪市 1.xxx, 深市 0.xxx
    if stock_code.startswith("6"):
        secid = f"1.{stock_code}"
    else:
        secid = f"0.{stock_code}"

    try:
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "secid": secid,
            "fields": "f43,f57,f58,f9,f23,f100,f167",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }
        r = requests.get(url, params=params, headers=EM_HEADERS, timeout=8)
        d = (r.json().get("data") or {})
        pe = safe_float(d.get("f9"))  # 动态PE
        pb = safe_float(d.get("f23"))  # PB
        name = d.get("f58", stock_code)
        industry = d.get("f100", "未知")

        # PE 可能是万分比
        if pe and pe > 10000:
            pe = pe / 100

        return {
            "name": name,
            "pe": round(pe, 1) if pe and 0 < pe < 5000 else None,
            "pb": round(pb, 2) if pb and pb > 0 else None,
            "industry": industry,
        }
    except Exception as e:
        print(f"  [WARN] 股票信息失败 {stock_code}: {e}")
        return {"name": stock_code, "pe": None, "pb": None, "industry": "未知"}


def get_manager_info(fund_code: str) -> dict:
    """获取基金经理信息"""
    try:
        url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
        params = {
            "plat": "Android", "appType": "ttjj",
            "product": "EFund", "version": "6.4.8",
            "deviceid": "test123", "pageIndex": 1,
            "pageSize": 1, "fundCode": fund_code,
        }
        r = requests.get(url, params=params, headers=EM_HEADERS, timeout=8)
        data = r.json()
        items = (data.get("Datas") or [])
        if not items:
            return {"name": "未知", "years": 0, "score": 0.5}

        item = items[0]
        mgr_name = item.get("JJJL", "未知")

        # 简单评分：有名字得基础分
        score = 0.5
        return {
            "name": mgr_name,
            "score": score,
            "summary": f"基金经理: {mgr_name}",
        }
    except Exception as e:
        print(f"  [WARN] 经理信息失败 {fund_code}: {e}")
        return {"name": "未知", "score": 0.5, "summary": "经理信息获取失败"}


def analyze_fund(fund_cfg: dict) -> dict:
    """完整分析一只基金"""
    code = fund_cfg["code"]
    short = fund_cfg.get("short", fund_cfg["name"])
    print(f"\n📊 分析 {short} ({code})...")

    # 获取持仓
    raw_holdings = get_fund_holdings(code)
    print(f"  持仓: {len(raw_holdings)} 只股票")

    # 获取每只股票详情
    top_holdings = []
    total_pe = 0
    pe_count = 0
    for h in raw_holdings[:10]:
        info = get_stock_info(h["stock_code"])
        entry = {
            "stock_name": info["name"],
            "hold_pct": h["hold_pct"],
            "pe": info["pe"],
            "industry": info["industry"],
        }
        top_holdings.append(entry)
        if info["pe"] and info["pe"] > 0:
            total_pe += info["pe"]
            pe_count += 1
        time.sleep(0.2)

    avg_pe = round(total_pe / pe_count, 1) if pe_count > 0 else None

    # top3 集中度
    pcts = sorted([h["hold_pct"] for h in top_holdings if h["hold_pct"]], reverse=True)
    top3_pct = round(sum(pcts[:3]), 1) if len(pcts) >= 3 else round(sum(pcts), 1)

    # 成长性评分（简单启发式）
    if avg_pe:
        if avg_pe < 20:
            growth_score = 0.3  # 低PE通常低成长
        elif avg_pe < 35:
            growth_score = 0.6
        elif avg_pe < 60:
            growth_score = 0.8
        else:
            growth_score = 1.0  # 高PE暗示高成长预期
    else:
        growth_score = 0.5

    # 摘要
    top_names = [h["stock_name"] for h in top_holdings[:3]]
    pe_str = f"PE {avg_pe}" if avg_pe else "PE未知"
    summary = f"重仓{'、'.join(top_names)}等，{pe_str}，top3集中度{top3_pct}%"

    # 经理
    manager = get_manager_info(code)

    # 判断风格
    sector = fund_cfg.get("sector", "")
    if "指数" in fund_cfg["name"] or "ETF" in fund_cfg["name"]:
        style_desc = f"指数/被动型，{sector}赛道"
        changes_signal = "low"
        changes_desc = "指数跟踪型，调仓按指数"
    elif "增强" in fund_cfg["name"]:
        style_desc = f"指数增强型，{sector}赛道，量化选股"
        changes_signal = "low"
        changes_desc = "量化增强策略，系统化调仓"
    else:
        style_desc = f"主动管理型，{sector}赛道"
        changes_signal = "low"
        changes_desc = "主动选股型，持仓相对稳定"

    return {
        "holdings": {
            "top_holdings": top_holdings[:5],
            "avg_pe": avg_pe,
            "avg_growth_score": growth_score,
            "top3_pct": top3_pct,
            "summary": summary,
            "score": round(growth_score * 0.6, 1),
        },
        "changes": {"turnover_signal": changes_signal, "summary": changes_desc},
        "style": {"summary": style_desc},
        "manager": manager,
    }


def main():
    print("=" * 60)
    print("🔄 基本面数据缓存刷新工具")
    print("=" * 60)

    results = {}
    for fund in FUNDS:
        try:
            data = analyze_fund(fund)
            results[fund["code"]] = data
            print(f"  ✅ {fund.get('short', fund['name'])} 完成")
        except Exception as e:
            print(f"  ❌ {fund.get('short', fund['name'])} 失败: {e}")
        time.sleep(0.5)

    # 写入 Python 缓存文件
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "fundamental_cache.py"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write('"""\n')
        f.write("基本面静态数据缓存 — 自动生成\n")
        f.write(f"更新时间: {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write("数据来源: 东方财富 API\n")
        f.write('"""\n\n')
        f.write("FUND_FUNDAMENTAL_CACHE = ")
        # Pretty print the dict
        f.write(json.dumps(results, ensure_ascii=False, indent=4))
        f.write("\n")

    print(f"\n✅ 缓存已写入: {output_path}")
    print(f"共 {len(results)} 只基金")
    print("\n下一步:")
    print("  git add -A && git commit -m 'data: 刷新基本面缓存' && git push")


if __name__ == "__main__":
    main()
