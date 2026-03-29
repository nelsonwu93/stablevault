"""
数据获取层 v5 - 全球可用版本（yfinance 优先）
======================================================
市场行情：yfinance（全球CDN，美国服务器 <2 秒）
基金净值：东方财富 API（5s超时 + 合成回退）
中国宏观：静态近期值 + 可选在线刷新

设计原则：
  1. 全球市场数据 100% 走 yfinance，零中国 API 依赖
  2. 基金净值保留东方财富（无替代），但超时后立即回退到合成数据
  3. 中国宏观（PMI/国债/北向）使用近期静态值，月度更新即可
  4. 所有函数保证返回有效数据结构，绝不抛异常导致页面崩溃
"""

import requests
import pandas as pd
import numpy as np
import json
import time
import datetime
import re
import logging
from typing import Optional, Dict, List, Tuple

# yfinance：全球市场数据唯一来源
try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    yf = None
    _YF_AVAILABLE = False

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════

def _safe_float(val) -> Optional[float]:
    """安全转换为 float，失败返回 None"""
    if val is None:
        return None
    try:
        f = float(str(val).replace(",", "").strip())
        return f if not (f != f) else None  # NaN check
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════
# HTTP Headers（仅基金净值接口使用）
# ══════════════════════════════════════════════

_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://data.eastmoney.com/",
}


# ══════════════════════════════════════════════
# 全球市场数据 — 100% yfinance
# ══════════════════════════════════════════════

# yfinance 符号 → 合理值范围 (min, max)，用于数据校验
_YF_VALIDATORS = {
    "^IXIC":    (5000, 30000),   # 纳斯达克
    "^GSPC":    (2000, 10000),   # 标普500
    "NVDA":     (10, 5000),      # 英伟达
    "USDCNY=X": (5, 10),         # 美元/人民币
    "^TNX":     (0.1, 20),       # 美国10年国债收益率
    "GC=F":     (500, 5000),     # 黄金期货
    "CL=F":     (10, 200),       # 原油期货
    "LIT":      (10, 200),       # 锂矿ETF
}

# 静态回退值（当 yfinance 也不可用时的兜底）
_STATIC_FALLBACK = {
    "nasdaq":      {"price": 17800, "change_pct": 0.0, "label": "纳斯达克指数",  "unit": "点"},
    "sp500":       {"price": 5600,  "change_pct": 0.0, "label": "标普500",       "unit": "点"},
    "nvidia":      {"price": 110,   "change_pct": 0.0, "label": "英伟达股价",     "unit": "USD"},
    "usd_cny":     {"price": 7.25,  "change_pct": 0.0, "label": "美元/人民币",    "unit": ""},
    "us_10y":      {"price": 4.25,  "change_pct": 0.0, "label": "美国10年期国债", "unit": "%"},
    "gold":        {"price": 2650,  "change_pct": 0.0, "label": "黄金期货",       "unit": "USD/oz"},
    "oil":         {"price": 70,    "change_pct": 0.0, "label": "原油期货(WTI)",  "unit": "USD/桶"},
    "lithium_etf": {"price": 42,    "change_pct": 0.0, "label": "锂矿ETF",        "unit": "USD"},
}


def _yf_quote(symbol: str) -> Dict:
    """通过 yfinance 获取单个标的实时行情"""
    if not _YF_AVAILABLE:
        return {}
    try:
        t = yf.Ticker(symbol)
        info = t.fast_info
        price = getattr(info, 'last_price', None)
        prev = getattr(info, 'previous_close', None)
        if price and price > 0:
            vmin, vmax = _YF_VALIDATORS.get(symbol, (0, 1e9))
            if not (vmin <= price <= vmax):
                logger.warning(f"yfinance {symbol} 价格 {price} 超出合理范围 [{vmin}, {vmax}]")
                return {}
            change_pct = ((price - prev) / prev * 100) if prev and prev > 0 else 0.0
            return {
                "price": round(price, 4),
                "prev_close": round(prev, 4) if prev else None,
                "change_pct": round(change_pct, 2),
                "source": "yfinance",
            }
    except Exception as e:
        logger.warning(f"yfinance {symbol}: {e}")
    return {}


def get_all_global_macro(macro_indicators: Dict) -> Dict:
    """
    批量获取全球宏观指标（yfinance 唯一来源）。
    通常 2-3 秒完成全部 8 个指标。
    """
    results = {}

    for key, cfg in macro_indicators.items():
        sym = cfg["symbol"]
        data = _yf_quote(sym)
        if data.get("price"):
            data["symbol"] = sym
            data["label"] = cfg["label"]
            data["unit"] = cfg["unit"]
            data["name"] = cfg["label"]
            results[key] = data
        else:
            # 使用静态回退
            fb = _STATIC_FALLBACK.get(key, {}).copy()
            fb["symbol"] = sym
            fb["source"] = "static_fallback"
            fb["name"] = fb.get("label", key)
            results[key] = fb
            logger.info(f"使用静态回退: {key}")

    return results


# ══════════════════════════════════════════════
# 中国宏观数据 — 静态近期值（月度更新即可）
# ══════════════════════════════════════════════

def get_china_pmi() -> Dict:
    """
    中国制造业 PMI（月度数据，变化缓慢）。
    使用近期实际值作为默认，无需实时 API。
    手动更新频率：每月 1 日
    """
    return {
        "pmi": 50.5,
        "date": "2025-12",
        "label": "中国制造业PMI",
        "source": "static_recent",
        "note": "月度数据，自动使用近期值",
    }


def get_cn_bond_yield() -> Dict:
    """
    中国10年期国债收益率（变化缓慢）。
    使用近期实际值作为默认。
    """
    return {
        "yield": 1.72,
        "change": None,
        "label": "中国10Y国债收益率",
        "source": "static_recent",
    }


def get_northbound_history(days: int = 10) -> List[Dict]:
    """
    北向资金流入数据（使用中性默认值）。
    因北向数据只能从中国 API 获取，海外部署时使用静态中性值。
    """
    # 返回中性默认值，不影响评分
    today = datetime.date.today()
    return [
        {"date": (today - datetime.timedelta(days=i)).isoformat(),
         "net_flow": 0.0}
        for i in range(days)
    ]


# ══════════════════════════════════════════════
# 综合市场快照
# ══════════════════════════════════════════════

def fetch_market_snapshot(macro_indicators: Dict) -> Dict:
    """
    拉取完整市场快照。
    全球数据：yfinance（1-3秒）
    中国宏观：静态近期值（0秒）
    """
    snapshot = {
        "timestamp": datetime.datetime.now().isoformat(),
        "global": {},
        "china": {},
        "northbound": {},
        "errors": [],
        "data_sources": "yfinance + static_defaults",
    }

    # 全球指标 — yfinance
    snapshot["global"] = get_all_global_macro(macro_indicators)
    for key, d in snapshot["global"].items():
        if d.get("source") == "static_fallback":
            snapshot["errors"].append(f"{d.get('label', key)} 使用静态回退值")

    # 中国宏观 — 静态值
    snapshot["china"]["pmi"] = get_china_pmi()
    snapshot["china"]["bond_yield"] = get_cn_bond_yield()

    # 北向资金 — 中性默认值
    nb_history = get_northbound_history(5)
    recent = [r["net_flow"] for r in nb_history[-5:]]
    snapshot["northbound"] = {
        "history": nb_history,
        "5day_total": round(sum(recent), 2),
        "5day_positive_days": sum(1 for f in recent if f > 0),
        "signal": "neutral",  # 海外部署无法获取真实北向数据，中性处理
    }

    return snapshot


# ══════════════════════════════════════════════
# 基金净值数据（东方财富 — 唯一数据源，无美国替代）
# 超时后立即回退到合成数据，保证页面不卡
# ══════════════════════════════════════════════

def get_fund_realtime(fund_code: str) -> Dict:
    """获取基金实时估算净值"""
    for fn in [_fund_gz, _fund_em_mobile]:
        result = fn(fund_code)
        if result.get("nav"):
            return result
    # 合成回退
    try:
        df = _fund_history_synthetic(fund_code, 5)
        if not df.empty and "nav" in df.columns:
            latest = df.iloc[-1]
            nav = float(latest["nav"])
            ret = float(latest.get("daily_return_pct", 0) or 0)
            return {
                "code": fund_code, "name": "", "nav": nav,
                "est_nav": nav, "est_change_pct": ret,
                "source": "synthetic_fallback",
            }
    except Exception:
        pass
    return {"code": fund_code, "nav": None, "est_nav": None,
            "est_change_pct": None, "source": "all_failed"}


def _fund_gz(fund_code: str) -> Dict:
    """天天基金实时估算"""
    try:
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        r = requests.get(
            url,
            headers={**_EM_HEADERS, "Referer": "https://fund.eastmoney.com/"},
            timeout=5,
        )
        text = r.text.strip()
        match = re.search(r'jsonpgz\((\{.*?\})\)', text)
        if not match:
            return {"code": fund_code, "nav": None}
        data = json.loads(match.group(1))
        nav = _safe_float(data.get("dwjz"))
        est = _safe_float(data.get("gsz")) or nav
        return {
            "code": fund_code,
            "name": data.get("name", ""),
            "nav_date": data.get("jzrq", ""),
            "nav": nav, "est_nav": est,
            "est_change_pct": _safe_float(data.get("gszzl")) or 0.0,
            "update_time": data.get("gztime", ""),
            "source": "fundgz",
        }
    except Exception as e:
        logger.warning(f"天天基金实时失败 {fund_code}: {e}")
    return {"code": fund_code, "nav": None}


def _fund_em_mobile(fund_code: str) -> Dict:
    """东方财富移动端基金接口（备用）"""
    try:
        url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
        params = {
            "plat": "Android", "appType": "ttjj",
            "product": "EFund", "version": "6.4.8",
            "deviceid": "550e8400e29b41d4a716446655440000",
            "pageIndex": 1, "pageSize": 1, "fundCode": fund_code,
        }
        r = requests.get(url, params=params, headers=_EM_HEADERS, timeout=5)
        data = r.json()
        items = data.get("Datas", [])
        if not items:
            return {"code": fund_code, "nav": None}
        item = items[0]
        nav = _safe_float(item.get("NAV"))
        return {
            "code": fund_code,
            "name": item.get("SHORTNAME", ""),
            "nav_date": item.get("PDATE", ""),
            "nav": nav, "est_nav": nav,
            "est_change_pct": _safe_float(item.get("NAVCHGRT")) or 0.0,
            "source": "em_mobile",
        }
    except Exception as e:
        logger.warning(f"东方财富移动端失败 {fund_code}: {e}")
    return {"code": fund_code, "nav": None}


# ══════════════════════════════════════════════
# 基金历史净值
# ══════════════════════════════════════════════

def get_fund_history(fund_code: str, page_size: int = 180) -> pd.DataFrame:
    """获取基金历史净值（东方财富 → 合成回退）"""
    df = _fund_history_main(fund_code, page_size)
    if not df.empty:
        return df
    df = _fund_history_mobile(fund_code, page_size)
    if not df.empty:
        return df
    # 最终回退：基于配置数据生成模拟历史（保证技术指标计算不空）
    logger.info(f"基金 {fund_code} 使用合成历史数据")
    return _fund_history_synthetic(fund_code, page_size)


def _fund_history_main(fund_code: str, page_size: int) -> pd.DataFrame:
    """东方财富基金历史净值主接口"""
    try:
        url = "https://api.fund.eastmoney.com/f10/lsjz"
        params = {
            "fundCode": fund_code, "page": 1, "pageSize": page_size,
            "startDate": "", "endDate": "",
            "_": int(time.time() * 1000),
        }
        headers = {
            **_EM_HEADERS,
            "Referer": f"https://fundf10.eastmoney.com/jjjz_{fund_code}.html",
            "Host": "api.fund.eastmoney.com",
        }
        r = requests.get(url, params=params, headers=headers, timeout=5)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        records = (data.get("Data") or {}).get("LSJZList", [])
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df = df.rename(columns={
            "FSRQ": "date", "DWJZ": "nav",
            "LJJZ": "cumulative_nav", "JZZZL": "daily_return_pct",
        })
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
        df["daily_return_pct"] = pd.to_numeric(df["daily_return_pct"], errors="coerce")
        df = df.dropna(subset=["nav"]).sort_values("date").reset_index(drop=True)
        return df[["date", "nav", "cumulative_nav", "daily_return_pct"]]
    except Exception as e:
        logger.warning(f"基金历史(主) {fund_code}: {e}")
    return pd.DataFrame()


def _fund_history_mobile(fund_code: str, page_size: int) -> pd.DataFrame:
    """东方财富移动端历史净值（备用）"""
    try:
        url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList"
        params = {
            "plat": "Android", "appType": "ttjj",
            "product": "EFund", "version": "6.4.8",
            "deviceid": "550e8400e29b41d4a716446655440000",
            "pageIndex": 1, "pageSize": page_size, "fundCode": fund_code,
        }
        r = requests.get(url, params=params, headers=_EM_HEADERS, timeout=5)
        data = r.json()
        items = data.get("Datas", [])
        if not items:
            return pd.DataFrame()
        rows = [
            {
                "date": pd.to_datetime(item.get("PDATE", ""), errors="coerce"),
                "nav": _safe_float(item.get("NAV")) or 0,
                "cumulative_nav": _safe_float(item.get("ACCNAV")) or 0,
                "daily_return_pct": _safe_float(item.get("NAVCHGRT")) or 0,
            }
            for item in items
        ]
        df = pd.DataFrame(rows).dropna(subset=["nav"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        logger.warning(f"基金历史(移动端) {fund_code}: {e}")
    return pd.DataFrame()


def _fund_history_synthetic(fund_code: str, page_size: int) -> pd.DataFrame:
    """
    当所有网络源不可用时，基于配置数据生成模拟历史净值。
    保证 UI 展示不空白，技术指标可计算。
    """
    try:
        from config import FUNDS
        fund = next((f for f in FUNDS if f["code"] == fund_code), None)
        if not fund:
            return pd.DataFrame()

        current_value = fund.get("current_value", 10000)
        np.random.seed(hash(fund_code) % (2**31))
        days = min(page_size, 180)
        end_date = datetime.date.today()
        dates = [end_date - datetime.timedelta(days=i) for i in range(days)]
        dates.reverse()

        base_nav = 1.0 + (current_value % 1000) / 10000
        daily_vol = 0.012
        daily_drift = 0.0003
        returns = np.random.normal(daily_drift, daily_vol, days)

        navs = [base_nav]
        for r in returns[1:]:
            navs.append(navs[-1] * (1 + r))

        daily_return_pcts = [0.0] + [
            (navs[i] - navs[i-1]) / navs[i-1] * 100 for i in range(1, len(navs))
        ]

        df = pd.DataFrame({
            "date": pd.to_datetime(dates),
            "nav": [round(n, 4) for n in navs],
            "cumulative_nav": [round(n, 4) for n in navs],
            "daily_return_pct": [round(r, 2) for r in daily_return_pcts],
        })
        return df
    except Exception as e:
        logger.warning(f"合成历史数据失败 {fund_code}: {e}")
    return pd.DataFrame()


# ══════════════════════════════════════════════
# 技术指标计算（纯本地计算，无 API 调用）
# ══════════════════════════════════════════════

def compute_technical_indicators(df: pd.DataFrame) -> Dict:
    """计算 MA20/MA60/RSI14/MACD，数据不足时优雅降级"""
    base = {
        "ma20": None, "ma60": None, "rsi": None, "trend": "unknown",
        "latest_nav": None, "above_ma20": None, "above_ma60": None,
        "rsi_signal": "unknown", "macd_cross": "unknown",
        "macd": None, "macd_signal": None, "macd_hist": None,
    }
    if df.empty:
        return base
    nav = df["nav"].dropna().values
    if len(nav) < 5:
        return {**base, "latest_nav": float(nav[-1]) if len(nav) > 0 else None}

    latest = float(nav[-1])
    ma20 = float(np.mean(nav[-20:])) if len(nav) >= 20 else None
    ma60 = float(np.mean(nav[-60:])) if len(nav) >= 60 else None
    rsi = _compute_rsi(nav) if len(nav) >= 15 else None
    macd_line, signal_line, histogram = _compute_macd(nav)

    if ma20 and ma60:
        trend = "uptrend" if (latest > ma60 and ma20 > ma60) else \
                "downtrend" if (latest < ma60 and ma20 < ma60) else "sideways"
    elif ma20:
        trend = "uptrend" if latest > ma20 else "downtrend"
    else:
        trend = "unknown"

    return {
        "latest_nav":   round(latest, 4),
        "ma20":         round(ma20, 4) if ma20 else None,
        "ma60":         round(ma60, 4) if ma60 else None,
        "above_ma20":   latest > ma20 if ma20 else None,
        "above_ma60":   latest > ma60 if ma60 else None,
        "rsi":          round(rsi, 1) if rsi else None,
        "rsi_signal":   _rsi_signal(rsi),
        "macd":         round(macd_line, 4) if macd_line else None,
        "macd_signal":  round(signal_line, 4) if signal_line else None,
        "macd_hist":    round(histogram, 4) if histogram else None,
        "macd_cross":   _macd_cross_signal(macd_line, signal_line, histogram),
        "trend":        trend,
    }


def _compute_rsi(prices: np.ndarray, period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices.astype(float))
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    return float(100 - 100 / (1 + avg_gain / avg_loss))


def _compute_macd(prices: np.ndarray, fast=12, slow=26, signal=9) -> Tuple:
    if len(prices) < slow + signal:
        return None, None, None
    prices = prices.astype(float)
    kf, ks = 2 / (fast + 1), 2 / (slow + 1)
    ef, es = prices[0], prices[0]
    macd_arr = []
    for p in prices:
        ef = p * kf + ef * (1 - kf)
        es = p * ks + es * (1 - ks)
        macd_arr.append(ef - es)
    if len(macd_arr) < signal:
        return None, None, None
    ks2 = 2 / (signal + 1)
    sig = macd_arr[0]
    for m in macd_arr[1:]:
        sig = m * ks2 + sig * (1 - ks2)
    ml = macd_arr[-1]
    return float(ml), float(sig), float(ml - sig)


def _rsi_signal(rsi) -> str:
    if rsi is None: return "unknown"
    if rsi < 35:    return "oversold"
    if rsi > 70:    return "overbought"
    if rsi < 50:    return "mild_weak"
    return "mild_strong"


def _macd_cross_signal(macd, signal, hist) -> str:
    if macd is None or signal is None: return "unknown"
    if macd > signal and hist and hist > 0: return "bullish"
    if macd < signal and hist and hist < 0: return "bearish"
    return "neutral"


# ══════════════════════════════════════════════
# 美联储立场评估（纯逻辑，无 API）
# ══════════════════════════════════════════════

def assess_fed_stance(us10y_change_pct: Optional[float]) -> str:
    if us10y_change_pct is None: return "unknown"
    if us10y_change_pct < -2.0:  return "dovish_strong"
    if us10y_change_pct < -0.5:  return "dovish"
    if us10y_change_pct > 2.0:   return "hawkish_strong"
    if us10y_change_pct > 0.5:   return "hawkish"
    return "neutral"


# ══════════════════════════════════════════════
# 兼容性别名（保留旧代码引用）
# ══════════════════════════════════════════════

def get_global_quote(symbol: str) -> Dict:
    """兼容旧接口：现在统一走 yfinance"""
    data = _yf_quote(symbol)
    if data.get("price"):
        data["symbol"] = symbol
        return data
    return {"symbol": symbol, "price": None, "change_pct": None, "source": "failed"}


def get_northbound_flow() -> Dict:
    """兼容旧接口"""
    history = get_northbound_history(5)
    recent = [r["net_flow"] for r in history[-5:]]
    return {
        "5day_total": round(sum(recent), 2),
        "signal": "neutral",
    }
