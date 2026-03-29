"""
基金详情数据获取 — Fund Detail Fetcher
获取基金基本信息、持仓明细、基金经理等详细数据
数据源：东方财富/天天基金
"""

import requests
import re
import json
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
}


def get_fund_basic_info(fund_code: str) -> Dict:
    """
    获取基金基本信息（规模、经理、类型、费率等）
    数据源：天天基金详情页
    """
    result = {
        "code": fund_code,
        "name": "",
        "type": "",           # 基金类型（混合型、指数型等）
        "manager": "",        # 基金经理
        "company": "",        # 基金公司
        "inception_date": "", # 成立日期
        "scale": "",          # 基金规模（亿元）
        "fee_rate": "",       # 管理费率
        "benchmark": "",      # 业绩基准
        "risk_level": "",     # 风险等级
        "source": "",
    }

    # 方法1：东方财富基金档案API
    info = _fund_info_em_api(fund_code)
    if info.get("name"):
        result.update(info)
        result["source"] = "eastmoney_api"
        return result

    # 方法2：天天基金JS接口
    info = _fund_info_ttjj(fund_code)
    if info.get("name"):
        result.update(info)
        result["source"] = "ttjj"
        return result

    # 方法3：AKShare
    info = _fund_info_akshare(fund_code)
    if info.get("name"):
        result.update(info)
        result["source"] = "akshare"
        return result

    # 方法4：本地静态缓存（离线回退）
    from data.fund_static_data import get_static_basic_info
    info = get_static_basic_info(fund_code)
    if info.get("name"):
        result.update(info)
        result["source"] = "static_cache"
        return result

    return result


def _fund_info_akshare(fund_code: str) -> Dict:
    """AKShare基金信息（最终备用）"""
    try:
        import akshare as ak
        df = ak.fund_individual_basic_info_xq(symbol=fund_code)
        if df is not None and not df.empty:
            info = {}
            for _, row in df.iterrows():
                key = str(row.iloc[0]).strip()
                val = str(row.iloc[1]).strip() if len(row) > 1 else ""
                if "名称" in key or "基金简称" in key:
                    info["name"] = val
                elif "类型" in key:
                    info["type"] = val
                elif "经理" in key:
                    info["manager"] = val
                elif "公司" in key or "管理人" in key:
                    info["company"] = val
                elif "成立" in key:
                    info["inception_date"] = val
                elif "规模" in key:
                    info["scale"] = val.replace("亿元", "").strip()
                elif "管理费" in key:
                    info["fee_rate"] = val.replace("%", "").strip()
                elif "风险" in key:
                    info["risk_level"] = val
            return info
    except Exception as e:
        logger.debug(f"AKShare基金信息 {fund_code}: {e}")
    # 再试一个AKShare接口
    try:
        import akshare as ak
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="基金概况")
        if df is not None and not df.empty:
            info = {}
            for _, row in df.iterrows():
                key = str(row.iloc[0]).strip()
                val = str(row.iloc[1]).strip() if len(row) > 1 else ""
                if "名称" in key:
                    info["name"] = val
                elif "类型" in key:
                    info["type"] = val
                elif "经理" in key:
                    info["manager"] = val
                elif "公司" in key:
                    info["company"] = val
                elif "成立" in key:
                    info["inception_date"] = val
                elif "规模" in key:
                    info["scale"] = val
                elif "费率" in key or "管理费" in key:
                    info["fee_rate"] = val
            return info
    except Exception as e:
        logger.debug(f"AKShare基金概况 {fund_code}: {e}")
    return {}


def _fund_info_em_api(fund_code: str) -> Dict:
    """东方财富基金档案API"""
    try:
        url = f"https://fundmobapi.eastmoney.com/FundMNewApi/FundMNInformation"
        params = {
            "plat": "Android", "appType": "ttjj",
            "product": "EFund", "version": "6.4.8",
            "fundCode": fund_code,
        }
        r = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        data = r.json()
        datas = data.get("Datas", {})
        if not datas:
            return {}

        return {
            "name": datas.get("SHORTNAME", ""),
            "type": datas.get("FTYPE", ""),
            "manager": datas.get("JJJL", ""),
            "company": datas.get("JJGS", ""),
            "inception_date": datas.get("ESTABDATE", ""),
            "scale": datas.get("ENDNAV", ""),
            "fee_rate": datas.get("MGRFEE", ""),
            "benchmark": datas.get("BENCH", ""),
            "risk_level": _map_risk_level(datas.get("RISKLEVEL", "")),
        }
    except Exception as e:
        logger.warning(f"基金信息(EM API) {fund_code}: {e}")
    return {}


def _fund_info_ttjj(fund_code: str) -> Dict:
    """天天基金JS数据接口"""
    try:
        url = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
        headers = {**_HEADERS, "Referer": f"https://fund.eastmoney.com/{fund_code}.html"}
        r = requests.get(url, headers=headers, timeout=10)
        text = r.text

        def extract_var(name: str) -> str:
            match = re.search(rf'var\s+{name}\s*=\s*"([^"]*)"', text)
            return match.group(1) if match else ""

        def extract_json_var(name: str):
            match = re.search(rf'var\s+{name}\s*=\s*(\[.*?\]);', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            return None

        return {
            "name": extract_var("fS_name"),
            "type": extract_var("fS_code"),  # 这里其实返回的是code, 需要别处获取type
            "manager": "",
            "company": "",
            "inception_date": "",
            "scale": "",
        }
    except Exception as e:
        logger.warning(f"基金信息(TTJJ) {fund_code}: {e}")
    return {}


def get_fund_top_holdings(fund_code: str) -> List[Dict]:
    """
    获取基金前十大重仓股
    """
    # 方法1：东方财富移动端API
    holdings = _holdings_em_mobile(fund_code)
    if holdings:
        return holdings

    # 方法2：天天基金JS
    holdings = _holdings_ttjj_js(fund_code)
    if holdings:
        return holdings

    # 方法3：本地静态缓存
    from data.fund_static_data import get_static_holdings
    holdings = get_static_holdings(fund_code)
    if holdings:
        return holdings

    return []


def _holdings_em_mobile(fund_code: str) -> List[Dict]:
    """东方财富移动端持仓接口"""
    try:
        url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNAssetAllocationNew"
        params = {
            "plat": "Android", "appType": "ttjj",
            "product": "EFund", "version": "6.4.8",
            "fundCode": fund_code,
        }
        r = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        data = r.json()
        # 尝试从返回数据提取持仓
        stocks = data.get("Datas", {}).get("fundStocks", [])
        result = []
        for s in stocks[:10]:
            result.append({
                "stock_name": s.get("GPJC", ""),
                "stock_code": s.get("GPDM", ""),
                "hold_pct": float(s.get("JZBL", 0) or 0),
            })
        return result
    except Exception as e:
        logger.debug(f"持仓(EM mobile) {fund_code}: {e}")
    return []


def _holdings_ttjj_js(fund_code: str) -> List[Dict]:
    """天天基金JS数据 - 前十大重仓"""
    try:
        url = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
        headers = {**_HEADERS, "Referer": f"https://fund.eastmoney.com/{fund_code}.html"}
        r = requests.get(url, headers=headers, timeout=10)
        text = r.text

        # 尝试提取 stockCodesNew 变量
        match = re.search(r'var\s+stockCodesNew\s*=\s*"([^"]*)"', text)
        if match:
            codes_str = match.group(1)
            # 格式：1~000001~平安银行~8.50,0~600036~招商银行~5.20,...
            stocks = []
            for item in codes_str.split(","):
                parts = item.split("~")
                if len(parts) >= 4:
                    stocks.append({
                        "stock_name": parts[2],
                        "stock_code": parts[1],
                        "hold_pct": float(parts[3]) if parts[3] else 0,
                    })
            return stocks[:10]
    except Exception as e:
        logger.debug(f"持仓(TTJJ JS) {fund_code}: {e}")
    return []


def get_fund_performance(fund_code: str) -> Dict:
    """
    获取基金历史业绩（近1月/3月/6月/1年/3年/成立以来）
    """
    try:
        url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNPeriodIncrease"
        params = {
            "plat": "Android", "appType": "ttjj",
            "product": "EFund", "version": "6.4.8",
            "fundCode": fund_code,
        }
        r = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        data = r.json()
        datas = data.get("Datas", [])
        result = {}
        period_map = {
            "Z": "近1周", "Y": "近1月", "3Y": "近3月",
            "6Y": "近6月", "1N": "近1年", "2N": "近2年",
            "3N": "近3年", "LN": "成立以来",
        }
        for item in datas:
            title = item.get("title", "")
            for code, label in period_map.items():
                if title == code:
                    val = item.get("syl")
                    result[label] = float(val) if val else None
                    break
        return result
    except Exception as e:
        logger.warning(f"基金业绩 {fund_code}: {e}")

    # 本地静态缓存回退
    from data.fund_static_data import get_static_performance
    perf = get_static_performance(fund_code)
    if perf:
        return perf

    return {}


def _map_risk_level(level_str: str) -> str:
    """映射风险等级"""
    mapping = {
        "1": "低风险",
        "2": "中低风险",
        "3": "中风险",
        "4": "中高风险",
        "5": "高风险",
        "R1": "低风险",
        "R2": "中低风险",
        "R3": "中风险",
        "R4": "中高风险",
        "R5": "高风险",
    }
    return mapping.get(str(level_str), level_str or "未知")


def get_fund_full_detail(fund_code: str) -> Dict:
    """
    一次性获取基金完整详情（汇总所有信息）
    """
    basic = get_fund_basic_info(fund_code)
    holdings = get_fund_top_holdings(fund_code)
    performance = get_fund_performance(fund_code)

    return {
        "basic": basic,
        "holdings": holdings,
        "performance": performance,
    }
