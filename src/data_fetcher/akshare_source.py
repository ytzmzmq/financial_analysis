"""A股数据源：行情、板块指数、资金流向 —— 通过 AKShare"""
import pandas as pd
import numpy as np

try:
    import akshare as ak
except ImportError:
    ak = None


class AKShareSource:
    """封装 AKShare 数据获取，统一返回标准化 DataFrame"""

    def __init__(self):
        pass

    # ── 申万医药生物指数 ──
    def fetch_sw_medical(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取申万医药生物指数(801150)日线，用 ETF 代理映射盘中实时价格"""
        if ak is None:
            raise ImportError("akshare not installed")

        # 1. 获取历史日线
        df = ak.index_hist_sw(symbol="801150", period="day")
        df = df.rename(columns={
            "日期": "date", "收盘": "close", "开盘": "open",
            "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()

        # 2. 用 512290(生物医药ETF) 盘中涨跌幅推算指数实时点位
        try:
            today = pd.Timestamp.today().normalize()
            if today.weekday() < 5:
                spot_df = ak.fund_etf_spot_em()
                etf = spot_df[spot_df["代码"] == "512290"]
                if not etf.empty:
                    pct_change = float(etf["涨跌幅"].iloc[0]) / 100.0
                    # 只在日线还未更新今天数据时(盘中)，才用昨天收盘价推算
                    if df.iloc[-1]["date"] < today:
                        last_close = df.iloc[-1]["close"]
                        realtime_price = last_close * (1 + pct_change)
                        new_row = {"date": today, "close": realtime_price, "open": realtime_price,
                                   "high": realtime_price, "low": realtime_price,
                                   "volume": 0, "amount": 0}
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        print(f"[AKShare] ETF代理: 512290盘中涨跌{pct_change*100:+.2f}% → 指数盘中估算 {realtime_price:.2f}")
                    # 如果df里已有今天数据(收盘后)，保持原样不动
        except Exception:
            pass  # 网络不佳则静默退回历史数据

        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = "sw_medical"
        cols = ["date", "ticker", "close", "open", "high", "low", "volume", "amount"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 中证医疗指数（备选/补充） ──
    def fetch_csi_medical(self, start_date: str = "20180101",
                          end_date: str | None = None) -> pd.DataFrame:
        """获取中证医疗指数(000933)日线"""
        if ak is None:
            raise ImportError("akshare not installed")
        df = ak.stock_zh_index_daily(symbol="sh000933")
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = "csi_medical"
        cols = ["date", "ticker", "close", "open", "high", "low", "volume"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 大盘指数 ──
    def fetch_market_index(self, symbol: str = "hs300",
                           start_date: str = "20180101",
                           end_date: str | None = None) -> pd.DataFrame:
        """获取大盘指数日线: hs300 / cyb / sz50 / sh000001"""
        if ak is None:
            raise ImportError("akshare not installed")
        symbol_map = {
            "hs300": "sh000300", "cyb": "sz399006",
            "sz50": "sh000016", "sh000001": "sh000001",
        }
        code = symbol_map.get(symbol, symbol)
        df = ak.stock_zh_index_daily(symbol=code)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = symbol
        cols = ["date", "ticker", "close", "open", "high", "low", "volume"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 北向资金 ──
    def fetch_north_flow(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取沪股通北向资金日净流入"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.stock_hsgt_hist_em(symbol="沪股通")
            df = df.rename(columns={
                "日期": "date", "当日成交净买额": "net_flow",
                "买入成交额": "buy_amount", "卖出成交额": "sell_amount",
            })
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "north_flow",
                "value": pd.to_numeric(df["net_flow"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── COMEX 黄金期货（真实国际金价） ──
    def fetch_comex_gold(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取 COMEX 黄金期货(GC)日线 —— 真实国际金价"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.futures_foreign_hist(symbol="GC")
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "gold_futures",
                "close": df["close"],
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "volume": df.get("volume", np.nan),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── USD/CNY 汇率（DXY 的国内替代） ──
    def fetch_usd_cny(self, start_date: str = "20180101",
                      end_date: str | None = None) -> pd.DataFrame:
        """获取美元兑人民币汇率（替代 DXY）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.currency_boc_sina(symbol="美元")
            df["date"] = pd.to_datetime(df["日期"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "usdcny",
                "value": pd.to_numeric(df["央行中间价"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 上海金交所基准价 ──
    def fetch_sge_gold(self, start_date: str = "20180101",
                       end_date: str | None = None) -> pd.DataFrame:
        """获取上海黄金交易所基准金价"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.spot_golden_benchmark_sge()
            df["date"] = pd.to_datetime(df["交易时间"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "sge_gold",
                "close": pd.to_numeric(df["早盘价"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── 黄金概念板块 ──
    def fetch_gold_concept(self, start_date: str = "20180101",
                           end_date: str | None = None) -> pd.DataFrame:
        """获取同花顺黄金概念板块指数"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.stock_board_concept_index_ths(
                symbol="黄金概念", start_date=start_date, end_date=end_date or "20260101"
            )
            df = df.rename(columns={
                "date": "date", "收盘价": "close", "开盘价": "open",
                "最高价": "high", "最低价": "low", "成交量": "volume",
            })
            if "date" not in df.columns:
                for c in df.columns:
                    if "日期" in str(c):
                        df = df.rename(columns={c: "date"})
                        break
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "gold_concept_cn",
                "close": df.get("close", np.nan),
                "open": df.get("open", np.nan),
                "high": df.get("high", np.nan),
                "low": df.get("low", np.nan),
                "volume": df.get("volume", np.nan),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── 融资融券（沪深合计） ──
    def fetch_margin_data(self, start_date: str = "20180101",
                          end_date: str | None = None) -> pd.DataFrame:
        """获取沪深两市融资融券日数据（合并）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            sh = ak.macro_china_market_margin_sh()
            sz = ak.macro_china_market_margin_sz()
            sh["date"] = pd.to_datetime(sh["日期"]).dt.normalize()
            sz["date"] = pd.to_datetime(sz["日期"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            sh = sh[(sh["date"] >= pd.Timestamp(start_date)) & (sh["date"] <= pd.Timestamp(end_date))]
            sz = sz[(sz["date"] >= pd.Timestamp(start_date)) & (sz["date"] <= pd.Timestamp(end_date))]

            # merge on date（杜绝 index 错位）
            merged = sh[["date", "融资融券余额"]].merge(
                sz[["date", "融资融券余额"]], on="date",
                suffixes=("_sh", "_sz"), how="outer"
            )
            result = pd.DataFrame({
                "date": merged["date"],
                "ticker": "total_margin",
                "value": (pd.to_numeric(merged["融资融券余额_sh"], errors="coerce").fillna(0) +
                          pd.to_numeric(merged["融资融券余额_sz"], errors="coerce").fillna(0)),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── M2 货币供应量 ──
    def fetch_m2(self, start_date: str = "20180101",
                 end_date: str | None = None) -> pd.DataFrame:
        """获取中国 M2 月度同比增速"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_money_supply()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_m2",
                "value": pd.to_numeric(df["货币和准货币(M2)-同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 中国 PMI ──
    def fetch_cn_pmi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国官方制造业 PMI + 非制造业 PMI（月频）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_pmi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            records = []
            for _, row in df.iterrows():
                d = row["date"]
                records.append({"date": d, "ticker": "cn_mfg_pmi",
                               "value": pd.to_numeric(row["制造业-指数"], errors="coerce")})
                records.append({"date": d, "ticker": "cn_nonmfg_pmi",
                               "value": pd.to_numeric(row["非制造业-指数"], errors="coerce")})
            return pd.DataFrame(records).sort_values("date").reset_index(drop=True) if records else pd.DataFrame(columns=["date", "ticker", "value"])
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 中国 CPI / PPI ──
    def fetch_cn_cpi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国 CPI 月度同比"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_cpi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_cpi",
                "value": pd.to_numeric(df["全国-同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    def fetch_cn_ppi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国 PPI 月度同比"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_ppi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_ppi",
                "value": pd.to_numeric(df["当月同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 批量拉取 ──
    def fetch_all(self, start_date: str = "20180101",
                  end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """一次性拉取所有 AKShare 数据"""
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        results = {}
        fetchers = [
            ("sw_medical", lambda: self.fetch_sw_medical(start_date, end_date)),
            ("csi_medical", lambda: self.fetch_csi_medical(start_date, end_date)),
            ("hs300", lambda: self.fetch_market_index("hs300", start_date, end_date)),
            ("cyb", lambda: self.fetch_market_index("cyb", start_date, end_date)),
            ("sh000001", lambda: self.fetch_market_index("sh000001", start_date, end_date)),
            ("north_flow", lambda: self.fetch_north_flow(start_date, end_date)),
            ("gold_futures", lambda: self.fetch_comex_gold(start_date, end_date)),
            ("gold_concept_cn", lambda: self.fetch_gold_concept(start_date, end_date)),
            ("usdcny", lambda: self.fetch_usd_cny(start_date, end_date)),
            ("sge_gold", lambda: self.fetch_sge_gold(start_date, end_date)),
            ("cn_pmi", lambda: self.fetch_cn_pmi(start_date, end_date)),
            ("cn_cpi", lambda: self.fetch_cn_cpi(start_date, end_date)),
            ("cn_ppi", lambda: self.fetch_cn_ppi(start_date, end_date)),
            ("total_margin", lambda: self.fetch_margin_data(start_date, end_date)),
            ("cn_m2", lambda: self.fetch_m2(start_date, end_date)),
        ]
        for name, fetcher in fetchers:
            try:
                results[name] = fetcher()
                print(f"[AKShare] {name}: {len(results[name])} rows")
            except Exception as e:
                print(f"[AKShare] Failed {name}: {e}")
                results[name] = pd.DataFrame()
        return results
