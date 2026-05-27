"""美国宏观经济数据源 —— 通过 FRED (pandas_datareader)"""
import pandas as pd
import numpy as np

try:
    import pandas_datareader.data as web
except ImportError:
    web = None


class FREDSource:
    """封装 FRED 数据获取，统一返回 (date, ticker, value) 长表"""

    # FRED 序列 ID → 内部名称
    SERIES_MAP = {
        "DGS10": "us10y",          # 10年期美债收益率
        "DGS2": "us2y",            # 2年期美债收益率
        "DFII10": "us_tips10y",    # 10年期 TIPS 收益率（实际利率）
        "FEDFUNDS": "fed_funds",   # 联邦基金利率
        "CPIAUCSL": "us_cpi",      # CPI (需要手动转为同比)
        "CPILFESL": "us_core_cpi", # 核心 CPI
        "UNRATE": "us_unemployment",  # 失业率
        "T10Y2Y": "us_10y2y_spread",  # 10Y-2Y 利差（直接可用）
        "DTWEXBGS": "usd_index_tw",   # 贸易加权美元指数
    }

    def fetch_series(self, fred_code: str, name: str,
                     start_date: str = "2018-01-01",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取单个 FRED 序列"""
        if web is None:
            raise ImportError("pandas_datareader not installed")
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        try:
            data = web.DataReader(fred_code, "fred", start=start_date, end=end_date)
            data = data.reset_index()
            data.columns = ["date", "value"]
            data["ticker"] = name
            data["date"] = pd.to_datetime(data["date"]).dt.normalize()
            # 前向填充日期间隔（FRED 只在发布日有值）
            data = data.set_index("date").resample("D").ffill().reset_index()
            return data[["date", "ticker", "value"]].dropna(subset=["value"])
        except Exception as e:
            print(f"[FRED] Failed to fetch {name} ({fred_code}): {e}")
            return pd.DataFrame(columns=["date", "ticker", "value"])

    def _cpi_to_yoy(self, df: pd.DataFrame) -> pd.DataFrame:
        """将 CPI 水平值转为同比变化率"""
        df = df.copy()
        # 同比: 使用 DateOffset 精确对齐 (处理闰年)
        df = df.set_index("date")
        df["value"] = (df["value"] / df["value"].shift(freq=pd.DateOffset(years=1)) - 1) * 100
        df = df.reset_index()
        return df.dropna(subset=["value"])

    def fetch_all(self, start_date: str = "2018-01-01",
                  end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """批量拉取所有 FRED 数据"""
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")

        results = {}
        for fred_code, name in self.SERIES_MAP.items():
            try:
                df = self.fetch_series(fred_code, name, start_date, end_date)
                # CPI 需要转为同比
                if fred_code in ("CPIAUCSL", "CPILFESL"):
                    df = self._cpi_to_yoy(df)
                results[name] = df
            except Exception as e:
                print(f"[FRED] Failed to fetch {name}: {e}")
                results[name] = pd.DataFrame(columns=["date", "ticker", "value"])
        return results
