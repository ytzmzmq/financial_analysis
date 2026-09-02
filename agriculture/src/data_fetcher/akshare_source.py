# -*- coding: utf-8 -*-
"""农业板块数据源（AKShare 单一来源）+ 本地 CSV 缓存 + 防前视对齐。

设计约定（详见 docs/strategy_proposal.md §2）：
- 所有返回的 DataFrame 均以 ``date``（datetime64）为索引、列名小写英文。
- 月度宏观数据按"可得日"对齐（当月值在次月 15 日后才可用），杜绝前视。
- 周频生猪价格按报告日对齐（asof），同样不前视。
- 缓存位于 agriculture/data/raw/cache/*.csv（不入库）；CI 无缓存时直接在线拉取。
"""
from __future__ import annotations

from pathlib import Path
import re
import time

import pandas as pd

AGRI_ROOT = Path(__file__).resolve().parents[2]  # agriculture/
CACHE_DIR = AGRI_ROOT / "data" / "raw" / "cache"

# 申万行业指数
SW_AGRI = "801010"          # 申万农林牧渔（主建模序列）
SW_MED = "801150"           # 申万医药生物（对照，不再使用仅留验证）
# 指数代码（新浪源）
IDX_AGRI_CS = "sh000122"    # 上证农业主题（基金对应，对照展示）
IDX_HS300 = "sh000300"      # 沪深300（大盘环境 / 残差因子）
# 期货主力（新浪源）
FUT_HOG = "LH0"             # 生猪期货主力（2021-01 上市）
FUT_CORN = "C0"             # 玉米
FUT_MEAL = "M0"             # 豆粕

# 月度宏观数据的保守可得滞后：次月 15 日（CPI/PPI 约 9-10 日发布，货币供应 10-15 日）
MACRO_AVAIL_DAY = 15


def _to_date_index(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    df = df.copy()
    vals = df[col].astype(str)
    if vals.str.contains("年").any():
        # akshare 宏观接口的中文月份格式："2026年07月份" → 月末时间戳
        parsed = vals.str.extract(r"(\d{4})年(\d{2})月")
        df[col] = pd.to_datetime(
            dict(year=parsed[0], month=parsed[1], day=1), errors="coerce"
        ) + pd.offsets.MonthEnd(0)
    else:
        df[col] = pd.to_datetime(vals, errors="raise")
    df = df.set_index(col).sort_index()
    return df[~df.index.duplicated(keep="last")]


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{name}.csv"


def _read_cache(name: str, max_age_days: int | None = None) -> pd.DataFrame | None:
    p = _cache_path(name)
    if not p.exists():
        return None
    if max_age_days is not None:
        age = time.time() - p.stat().st_mtime
        if age > max_age_days * 86400:
            return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index = pd.DatetimeIndex(df.index)
    return df


def _write_cache(name: str, df: pd.DataFrame) -> pd.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(_cache_path(name))
    return df


def _fetch(name: str, fn, max_cache_age_days: int | None = None, **kwargs) -> pd.DataFrame:
    """在线拉取，失败时回退缓存（CI 网络抖动不应让每日信号中断）。"""
    if max_cache_age_days is not None:
        cached = _read_cache(name, max_cache_age_days)
        if cached is not None:
            return cached
    try:
        df = fn(**kwargs)
        return _write_cache(name, df)
    except Exception:  # noqa: BLE001 — 数据源失败时用任意旧缓存兜底
        cached = _read_cache(name)
        if cached is not None:
            return cached
        raise


# ── 指数日线 ────────────────────────────────────────────────

def fetch_index_sw(symbol: str = SW_AGRI) -> pd.DataFrame:
    """申万指数日线：date, open, high, low, close, volume, amount。"""
    import akshare as ak
    raw = ak.index_hist_sw(symbol=symbol, period="day")
    df = raw.rename(columns={
        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
        "收盘": "close", "成交量": "volume", "成交额": "amount",
    })
    return _to_date_index(df)[["open", "high", "low", "close", "volume", "amount"]]


def fetch_index_daily(symbol: str = IDX_HS300) -> pd.DataFrame:
    """新浪指数日线（沪深300 / 上证农业 000122 等）：date, open, high, low, close, volume。"""
    import akshare as ak
    raw = ak.stock_zh_index_daily(symbol=symbol)
    return _to_date_index(raw)[["open", "high", "low", "close", "volume"]]


# ── 期货与生猪 ──────────────────────────────────────────────

def fetch_futures_main(symbol: str = FUT_HOG,
                       start: str = "20050104", end: str = "20991231") -> pd.DataFrame:
    """期货主力连续日线：date, close。"""
    import akshare as ak
    raw = ak.futures_main_sina(symbol=symbol, start_date=start, end_date=end)
    df = raw.rename(columns={"日期": "date", "收盘价": "close"})
    return _to_date_index(df)[["close"]]


def fetch_hog_weekly() -> pd.DataFrame:
    """生猪价格指数（周频，2015-01 起）：date, value。含 4/6/12 月均线可另行计算。"""
    import akshare as ak
    raw = ak.index_hog_spot_price()
    df = raw.rename(columns={"日期": "date", "指数": "value"})
    return _to_date_index(df)[["value"]]


# ── 宏观（防前视：次月 15 日才可用） ─────────────────────────

def _macro_to_daily(monthly: pd.Series) -> pd.Series:
    """月度值 → 按可得日（次月 15 日）展开的日频序列，向后填充。

    monthly 的索引是月末日期；值在该月末对应的次月 15 日才对外可用。
    """
    avail = monthly.index + pd.offsets.MonthBegin(1) + pd.Timedelta(days=MACRO_AVAIL_DAY - 1)
    s = pd.Series(monthly.values, index=avail).sort_index()
    return s


def fetch_macro() -> pd.DataFrame:
    """CPI/PPI 同比 + M1/M2 同比（日频、防前视对齐）：cpi_yoy, ppi_yoy, m1_yoy, m2_yoy。"""
    import akshare as ak

    cpi = ak.macro_china_cpi()
    ppi = ak.macro_china_ppi()
    money = ak.macro_china_money_supply()

    cpi_m = _to_date_index(cpi, "月份")["全国-同比增长"].dropna()
    ppi_m = _to_date_index(ppi, "月份")["当月同比增长"].dropna()
    m1_m = _to_date_index(money, "月份")["货币(M1)-同比增长"].dropna()
    m2_m = _to_date_index(money, "月份")["货币和准货币(M2)-同比增长"].dropna()

    out = pd.concat(
        {
            "cpi_yoy": _macro_to_daily(cpi_m),
            "ppi_yoy": _macro_to_daily(ppi_m),
            "m1_yoy": _macro_to_daily(m1_m),
            "m2_yoy": _macro_to_daily(m2_m),
        },
        axis=1,
    )
    return out.sort_index()


def fetch_margin_sh() -> pd.DataFrame:
    """沪市融资余额（日频）：margin_balance。"""
    import akshare as ak
    raw = ak.macro_china_market_margin_sh()
    df = raw.rename(columns={"日期": "date", "融资余额": "margin_balance"})
    return _to_date_index(df)[["margin_balance"]]


def fetch_rate_10y() -> pd.DataFrame:
    """中国 10 年期国债收益率（日频）：rate_10y。"""
    import akshare as ak
    raw = ak.bond_zh_us_rate()
    df = raw.rename(columns={"日期": "date", "中国国债收益率10年": "rate_10y"})
    return _to_date_index(df)[["rate_10y"]].dropna()


# ── 汇总装配 ────────────────────────────────────────────────

def load_core_data(use_cache_days: int | None = None) -> dict[str, pd.DataFrame]:
    """拉取全部核心数据并统一到主日历（申万农林牧渔交易日）。

    返回 dict:
        agri       申万农林牧渔日线（主序列）
        hs300      沪深300 日线
        agri_cs    上证农业主题日线（对照）
        hog_week   生猪价格指数（周频，原始频率保留，不做 ffill）
        hog_fut    生猪期货主力日线
        corn       玉米期货主力日线
        meal       豆粕期货主力日线
        macro      月度宏观（已按可得日对齐成日频）
        margin     沪市融资余额日线
    """
    return {
        "agri": _fetch(f"sw_{SW_AGRI}", fetch_index_sw, use_cache_days),
        "hs300": _fetch("idx_hs300", fetch_index_daily, use_cache_days, symbol=IDX_HS300),
        "agri_cs": _fetch("idx_sh000122", fetch_index_daily, use_cache_days, symbol=IDX_AGRI_CS),
        "hog_week": _fetch("hog_weekly", fetch_hog_weekly, use_cache_days),
        "hog_fut": _fetch(f"fut_{FUT_HOG}", fetch_futures_main, use_cache_days, symbol=FUT_HOG),
        "corn": _fetch(f"fut_{FUT_CORN}", fetch_futures_main, use_cache_days, symbol=FUT_CORN),
        "meal": _fetch(f"fut_{FUT_MEAL}", fetch_futures_main, use_cache_days, symbol=FUT_MEAL),
        "macro": _fetch("macro_daily", fetch_macro, use_cache_days),
        "margin": _fetch("margin_sh", fetch_margin_sh, use_cache_days),
        "rate": _fetch("rate_10y", fetch_rate_10y, use_cache_days),
    }


def _ffill_to_calendar(src: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """把 src 的值传播到 calendar 中所有 ≥ 其时间戳的交易日。

    不能用 reindex(calendar).ffill()：源时间戳若落在周末/节假日（宏观可得日、
    周频猪价报告日常见），该行会被 reindex 直接丢弃，值延迟到下一个源时间戳。
    """
    union = src.index.union(calendar).sort_values()
    return src.reindex(union).ffill().reindex(calendar)


def align_daily(data: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """把全部数据对齐到主日历（仅含截至当日的可得信息）。

    防前视规则：
    - 价格类：asof（用最近一个 <= 当日的值）。
    - 宏观类：已在 fetch_macro 按可得日展开，直接 asof。
    - 周频生猪：asof（报告日之后才可见）。
    """
    out = pd.DataFrame(index=calendar)

    def ff(series: pd.Series) -> pd.Series:
        return _ffill_to_calendar(series.dropna(), calendar)

    out["close"] = ff(data["agri"]["close"])
    out["open"] = data["agri"]["open"].reindex(calendar)
    out["high"] = data["agri"]["high"].reindex(calendar)
    out["low"] = data["agri"]["low"].reindex(calendar)
    out["volume"] = data["agri"]["volume"].reindex(calendar)
    out["amount"] = data["agri"]["amount"].reindex(calendar)
    out["hs300_close"] = ff(data["hs300"]["close"])
    out["agri_cs_close"] = ff(data["agri_cs"]["close"])
    out["hog_week"] = ff(data["hog_week"]["value"])
    out["hog_fut_close"] = ff(data["hog_fut"]["close"])
    out["corn_close"] = ff(data["corn"]["close"])
    out["meal_close"] = ff(data["meal"]["close"])
    for col in ["cpi_yoy", "ppi_yoy", "m1_yoy", "m2_yoy"]:
        out[col] = ff(data["macro"][col])
    out["margin_balance"] = ff(data["margin"]["margin_balance"])
    out["rate_10y"] = ff(data["rate"]["rate_10y"])
    return out
