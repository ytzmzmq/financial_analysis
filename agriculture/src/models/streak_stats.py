# -*- coding: utf-8 -*-
"""L-B 游程概率层 + L-B2 基本面条件化连跌概率表。

预注册设计（docs/strategy_proposal.md §4 L-B / L-B2）：
- 频率表：连跌 ≥n 天（n=1..7）的年均发生次数、历史最长纪录、P(≥n+1|≥n)。
- 马尔可夫链：P(明日跌|已连跌 k)、P(明日涨|已连跌 k)（一阶）；
  条件收益：连跌 k 天后 5/20/60 日收益（均值/中位数/胜率）。
- L-B2 条件分层（单变量，样本 <30 自动合并标注"样本不足"）：
  vol 高/低、amount(量能) 高/低、residual 独跌/跟跌、market MA200 上/下、
  hog_phase 谷/扩张/峰/收缩、sentiment(margin) 低/高、val(价格5年分位) 低/高。
  二维交叉仅两组：vol×amount、hog_phase×val（此处仅存一维表，二维表由
  tracker 按需查询原始样本计算，避免表格爆炸）。
- 估计窗口：仅训练段（TRAIN_END 前）；全历史表仅供看板展示（明确标注）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRAIN_END = pd.Timestamp("2021-12-31")
FORWARD_HORIZONS = (5, 20, 60)
MIN_CELL = 30


def streak_length(down: pd.Series) -> pd.Series:
    """连跌天数（截至当日，当日下跌时 ≥1，上涨日为 0）。"""
    grp = (down != down.shift()).cumsum()
    return down.groupby(grp).cumsum() * down


def forward_returns(close: pd.Series, horizons=FORWARD_HORIZONS) -> pd.DataFrame:
    """forward h 日收益（以 T 收盘买入、T+h 收盘计价，不含费用）。"""
    out = {}
    for h in horizons:
        out[f"fwd{h}"] = close.shift(-h) / close - 1.0
    return pd.DataFrame(out, index=close.index)


def streak_frequency_table(streak: pd.Series, train_end: pd.Timestamp = TRAIN_END,
                           max_k: int = 7) -> pd.DataFrame:
    s = streak[streak.index <= train_end].dropna()
    years = max((s.index[-1] - s.index[0]).days / 365.25, 1.0)
    rows = []
    for n in range(1, max_k + 1):
        reach = s >= n
        events = int((reach & ~reach.shift(1, fill_value=False)).sum())
        # ≥n+1|≥n
        base = int((s >= n).sum())
        cont = int((s >= n + 1).sum()) if n < max_k else 0
        rows.append({
            "n": n,
            "days_ge_n": base,
            "episodes_per_year": round(events / years, 2),
            "p_continue": round(cont / base, 3) if base else np.nan,
        })
    return pd.DataFrame(rows).set_index("n")


def markov_p_up(streak: pd.Series, train_end: pd.Timestamp = TRAIN_END, max_k: int = 7) -> pd.DataFrame:
    """P(明日涨 | 已连跌 k)。"""
    s = streak[streak.index <= train_end].dropna()
    nxt_up = (s.shift(-1) == 0)  # 明日上涨（streak 归零）
    rows = []
    for k in range(1, max_k + 1):
        mask = (s == k)
        n = int((mask & nxt_up.shift(0).fillna(False)).sum())
        tot = int(mask.sum())
        rows.append({"k": k, "n_obs": tot, "p_up_tomorrow": round(n / tot, 3) if tot else np.nan})
    return pd.DataFrame(rows).set_index("k")


def _median_split(x: pd.Series, train_end: pd.Timestamp) -> pd.Series:
    """按训练段中位数二分（冻结阈值，防前视）。"""
    thr = x[x.index <= train_end].median()
    return (x > thr).astype(float).where(x.notna())


def build_conditions(daily: pd.DataFrame, regime_prob: pd.Series,
                     phase_daily: pd.DataFrame, hog_phase_daily: pd.DataFrame) -> pd.DataFrame:
    """构造 L-B2 条件变量（全部只用截至当日的可得信息）。"""
    c = pd.DataFrame(index=daily.index)
    ret = daily["close"].pct_change()
    c["down"] = (ret < 0).astype(float).where(ret.notna())
    c["streak"] = streak_length(c["down"] == 1)

    # 波动率状态（20 日已实现波动，500 日滚动分位）
    vol20 = ret.rolling(20).std()
    c["vol_high"] = _median_split(vol20.rolling(500, min_periods=250).rank(pct=True), TRAIN_END)

    # 量能（成交额 250 日分位）
    c["amount_high"] = _median_split(
        daily["amount"].rolling(250, min_periods=125).rank(pct=True), TRAIN_END
    )

    # 情绪代理：融资余额 20 日变化分位（2010 起）
    mg = daily["margin_balance"]
    margin_chg = mg.pct_change(20)
    c["sentiment_high"] = _median_split(
        margin_chg.rolling(500, min_periods=250).rank(pct=True), TRAIN_END
    )

    # 估值代理：价格 5 年分位
    px = daily["close"]
    val = px.rolling(1250, min_periods=500).rank(pct=True)
    c["val_low"] = 1.0 - _median_split(val, TRAIN_END)  # 分位低于中位 → val_low=1

    # 大盘状态
    hs = daily["hs300_close"]
    c["market_bull"] = (hs > hs.rolling(200).mean()).astype(float).where(hs.notna())

    # 残差方向：板块收益 − β×大盘收益（β 用过去 250 日周收益回归的滚动代理）
    ra = daily["close"].pct_change()
    rm = daily["hs300_close"].pct_change()
    cov = ra.rolling(250, min_periods=125).cov(rm)
    var = rm.rolling(250, min_periods=125).var()
    beta = (cov / var).clip(0.3, 2.0)
    resid = ra - beta * rm
    cum_resid = resid.groupby((c["down"] != c["down"].shift()).cumsum()).cumsum()
    c["resid_solo"] = (cum_resid < 0).astype(float).where(c["down"] == 1)

    # 周期与猪相位
    c["cycle_phase"] = phase_daily["cycle_phase"].reindex(daily.index).ffill()
    c["hog_phase"] = hog_phase_daily["cycle_phase"].reindex(daily.index).ffill()
    c["cycle_score"] = phase_daily["cycle_score"].reindex(daily.index).ffill()
    c["recession_prob"] = regime_prob.reindex(daily.index).ffill()
    return c


def conditional_streak_table(streak: pd.Series, fwd: pd.DataFrame,
                             cond: pd.Series, train_end: pd.Timestamp = TRAIN_END,
                             horizons=FORWARD_HORIZONS, min_cell: int = MIN_CELL) -> pd.DataFrame:
    """连跌 k 天 × 条件分层的条件收益表（仅训练段；k∈{1..5}）。

    返回 MultiIndex (k, 条件值) → {n, p_up_tomorrow, fwd5_med, fwd20_med, fwd60_med, fwd20_win}
    样本 < min_cell 的单元格合并为该条件下 k 的全样本值，并标 merged=True。
    """
    mask_train = streak.index <= train_end
    s = streak[mask_train].dropna()
    rows = []
    for k in range(1, 6):
        base = (s == k)
        for val in sorted(cond.reindex(s.index).dropna().unique()):
            m = base & (cond.reindex(s.index) == val)
            n = int(m.sum())
            if n < min_cell:
                m = base  # 合并：退化为全样本（无该条件）
                n = int(base.sum())
                merged = True
            else:
                merged = False
            row = {"k": k, "cond_val": float(val), "n_obs": n, "merged": merged}
            nxt_up = (s.shift(-1) == 0)
            row["p_up_tomorrow"] = round(float((m & nxt_up.fillna(False)).sum()) / n, 3) if n else np.nan
            for h in horizons:
                r = fwd.loc[s.index, f"fwd{h}"]
                row[f"fwd{h}_med"] = round(float(r[m].median()), 4) if n else np.nan
            if n:
                r20 = fwd.loc[s.index, "fwd20"]
                row["fwd20_win"] = round(float((r20[m] > 0).mean()), 3)
            rows.append(row)
    return pd.DataFrame(rows).set_index(["k", "cond_val"])


def build_all_tables(daily: pd.DataFrame, cond: pd.DataFrame,
                     train_end: pd.Timestamp = TRAIN_END) -> dict:
    """一次构建 L-B/L-B2 全部冻结表（训练段）。"""
    fwd = forward_returns(daily["close"])
    streak = cond["streak"]
    specs = {
        "overall": pd.Series(0.0, index=streak.index),
        "vol_high": cond["vol_high"],
        "amount_high": cond["amount_high"],
        "resid_solo": cond["resid_solo"],
        "market_bull": cond["market_bull"],
        "sentiment_high": cond["sentiment_high"],
        "val_low": cond["val_low"],
    }
    tables = {
        "frequency": streak_frequency_table(streak, train_end),
        "markov": markov_p_up(streak, train_end),
    }
    for name, col in specs.items():
        tables[f"cond_{name}"] = conditional_streak_table(streak, fwd, col, train_end)
    # 猪相位（多值条件）
    tables["cond_hog_phase"] = _multi_cond_table(streak, fwd, cond["hog_phase"], train_end)
    tables["cond_cycle_phase"] = _multi_cond_table(streak, fwd, cond["cycle_phase"], train_end)
    return tables


def _multi_cond_table(streak: pd.Series, fwd: pd.DataFrame, cond: pd.Series,
                      train_end: pd.Timestamp, min_cell: int = MIN_CELL) -> pd.DataFrame:
    mask_train = streak.index <= train_end
    s = streak[mask_train].dropna()
    c = cond.reindex(s.index)
    rows = []
    for k in range(1, 6):
        base = (s == k)
        for val in c.dropna().unique():
            m = base & (c == val)
            n = int(m.sum())
            merged = False
            if n < min_cell:
                m, n, merged = base, int(base.sum()), True
            nxt_up = (s.shift(-1) == 0)
            row = {"k": k, "cond_val": str(val), "n_obs": n, "merged": merged,
                   "p_up_tomorrow": round(float((m & nxt_up.fillna(False)).sum()) / n, 3) if n else np.nan}
            for h in FORWARD_HORIZONS:
                row[f"fwd{h}_med"] = round(float(fwd.loc[s.index, f"fwd{h}"][m].median()), 4) if n else np.nan
            if n:
                row["fwd20_win"] = round(float((fwd.loc[s.index, "fwd20"][m] > 0).mean()), 3)
            rows.append(row)
    return pd.DataFrame(rows).set_index(["k", "cond_val"])


def current_streak_card(streak_today: int, cond_today: pd.Series,
                        tables: dict) -> dict:
    """生成"连跌买入参考卡"（tracker 每日输出）。"""
    card: dict = {"streak_days": int(streak_today), "conditions": {}}
    mk = tables["markov"]
    if streak_today in mk.index:
        card["p_up_tomorrow"] = float(mk.loc[streak_today, "p_up_tomorrow"])
        card["n_obs"] = int(mk.loc[streak_today, "n_obs"])
    mapping = {
        "vol_high": "cond_vol_high",
        "amount_high": "cond_amount_high",
        "resid_solo": "cond_resid_solo",
        "market_bull": "cond_market_bull",
        "sentiment_high": "cond_sentiment_high",
        "val_low": "cond_val_low",
    }
    for cond_name, table_key in mapping.items():
        if cond_name not in cond_today.index or pd.isna(cond_today[cond_name]):
            continue
        val = float(cond_today[cond_name])
        tbl = tables[table_key]
        if (streak_today, val) in tbl.index:
            rec = tbl.loc[(streak_today, val)]
            merged = bool(rec["merged"]) if hasattr(rec, "get") else bool(rec["merged"])
            card["conditions"][cond_name] = {
                "state": "高" if val == 1 else "低",
                "p_up": float(rec["p_up_tomorrow"]),
                "fwd20_med": float(rec["fwd20_med"]),
                "fwd20_win": float(rec["fwd20_win"]),
                "n_obs": int(rec["n_obs"]),
                "merged": merged,
            }
    for multi, table_key in [("hog_phase", "cond_hog_phase"), ("cycle_phase", "cond_cycle_phase")]:
        if multi in cond_today.index and pd.notna(cond_today[multi]):
            tbl = tables[table_key]
            val = str(cond_today[multi])
            if (streak_today, val) in tbl.index:
                rec = tbl.loc[(streak_today, val)]
                card["conditions"][multi] = {
                    "state": val,
                    "p_up": float(rec["p_up_tomorrow"]),
                    "fwd20_med": float(rec["fwd20_med"]),
                    "fwd20_win": float(rec["fwd20_win"]),
                    "n_obs": int(rec["n_obs"]),
                    "merged": bool(rec["merged"]),
                }
    return card
