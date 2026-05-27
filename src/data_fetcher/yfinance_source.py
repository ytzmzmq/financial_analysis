"""国际数据源：黄金、美元、VIX —— 通过 yfinance"""
import pandas as pd
import numpy as np
from pathlib import Path
DATA_RAW = Path(__file__).resolve().parent.parent.parent / "data" / "raw"

try:
    import yfinance as yf
except ImportError:
    yf = None


class YFinanceSource:
    """封装 yfinance 数据获取，统一返回 (date, ticker, value) 或 (date, ticker, ohlcv)"""

    # 常用 ticker 映射
    TICKER_MAP = {
        "GLD": "GLD",               # SPDR Gold Trust ETF
        "GC=F": "GC=F",             # 黄金期货
        "DXY": "DX-Y.NYB",          # 美元指数
        "VIX": "^VIX",             # CBOE 波动率
        "SPY": "SPY",              # 标普500 ETF
        "TLT": "TLT",              # 20Y+ 美债ETF（利率敏感）
        "USO": "USO",              # WTI 原油ETF（通胀传导）
    }

    def __init__(self):
        self.cache_dir = DATA_RAW / "yfinance"

    def fetch_ohlcv(self, raw_ticker: str, name: str,
                    start_date: str = "2018-01-01",
                    end_date: str | None = None) -> pd.DataFrame:
        """获取单个标的 OHLCV 日线数据"""
        if yf is None:
            raise ImportError("yfinance not installed")
        yf_ticker = self.TICKER_MAP.get(raw_ticker, raw_ticker)
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        data = yf.download(yf_ticker, start=start_date, end=end_date,
                           progress=False, auto_adjust=True)
        if data.empty:
            return pd.DataFrame(columns=["date", "ticker", "close", "open", "high", "low", "volume"])

        # yfinance 返回 MultiIndex 列
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        data = data.reset_index()
        data["ticker"] = name
        data.columns = [c.lower() for c in data.columns]
        if "adj close" in data.columns:
            data = data.drop(columns=["adj close"])
        rename_map = {k: k for k in data.columns}
        data = data.rename(columns=rename_map)
        return data.rename(columns={"date": "date"}).reset_index(drop=True)

    def fetch_all_gold(self, start_date: str = "2018-01-01",
                       end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """获取黄金相关所有数据"""
        tickers = {
            "GLD": "gold_etf",
            "GC=F": "gold_futures",
            "DXY": "dxy",
            "VIX": "vix",
        }
        results = {}
        for raw_ticker, name in tickers.items():
            try:
                results[name] = self.fetch_ohlcv(raw_ticker, name, start_date, end_date)
            except Exception as e:
                print(f"[YFinance] Failed to fetch {name}: {e}")
                results[name] = pd.DataFrame()
        return results

    def fetch_all(self, start_date: str = "2018-01-01",
                  end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """批量拉取所有 yfinance 数据"""
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")

        all_tickers = {
            "GLD": "gold_etf",
            "GC=F": "gold_futures",
            "DXY": "dxy",
            "VIX": "vix",
            "SPY": "sp500",
            "TLT": "us_20y_bond",
            "USO": "wti_oil",
        }
        results = {}
        for raw_ticker, name in all_tickers.items():
            try:
                results[name] = self.fetch_ohlcv(raw_ticker, name, start_date, end_date)
            except Exception as e:
                print(f"[YFinance] Failed to fetch {name}: {e}")
                results[name] = pd.DataFrame()
        return results
