# -*- coding: utf-8 -*-
"""L-D/L-E：融合买卖信号 + 基金执行约束回测器。

预注册规则（docs/strategy_proposal.md §4 L-D / L-E）：
- BUY（T 日收盘判定）：Score ≥ B* 且 cycle_score > -0.5（非深峰端）
  且 recession_prob < 0.7 且 连跌保护：streak ≥ 4 时 P(明日涨|k) ≥ 0.5。
- SELL：Score ≤ S*，或 趋势止损（close < MA60 且 Score < 50），
  或 区制止损（recession_prob > 0.7 且 Score < 60）。
- 执行：T 日收盘信号 → T+1 收盘价成交（未知价法）；费用 申购 0.15% / 赎回 0.5%。
- 7 自然日最短持有：持有 < 7 天出现 SELL 时，顺延至第 8 天起首个交易日执行。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEE_BUY = 0.0015
FEE_SELL = 0.005
MIN_HOLD_NATURAL_DAYS = 7


def desired_position_v12(cond: pd.DataFrame, close: pd.Series,
                         score_panic: pd.Series, params: dict) -> pd.Series:
    """V1.2 周期主导的目标仓位（0/1，无费用无约束；由 run_backtest 落地执行约束）。

    - 主信号：HP 周期相位迟滞门——cycle_score > theta_in(0) 持有，
      < theta_out(-0.2) 清仓（Schmitt 触发器防抖动）；
    - 恐慌加速：score_panic（偏度+波动分位均值）≥ panic_threshold 且非收缩区制 → 立即持有
      （Nagel 2012 高波动反转溢价）；
    - 风险刹车：recession_prob > 0.8 且 close < MA60 → 清仓（双重确认，避免单指标误杀）。
    迟滞阈值 a priori 固定，不进网格（防过拟合）。
    """
    cs = cond["cycle_score"]
    theta_in = params.get("theta_in", 0.0)
    theta_out = params.get("theta_out", -0.2)
    pos = pd.Series(np.nan, index=cs.index)
    pos[cs > theta_in] = 1.0
    pos[cs < theta_out] = 0.0
    pos = pos.ffill().fillna(0.0)

    pt = params.get("panic_threshold")
    if pt is not None:
        panic = (score_panic >= pt) & (cond["recession_prob"] < 0.7)
        pos = pos.where(~panic.fillna(False), 1.0)

    exit_mode = params.get("exit_mode", "cycle_only")
    ma60 = close.rolling(60).mean()
    if exit_mode == "rec80_trend":
        risk = (cond["recession_prob"] > 0.8) & (close < ma60)
        pos = pos.where(~risk.fillna(False), 0.0)
    elif exit_mode == "trend_break":
        risk = close < ma60
        pos = pos.where(~risk.fillna(False), 0.0)
    # "cycle_only"：仅由迟滞门控制退出
    return pos


def position_signals(pos: pd.Series) -> pd.DataFrame:
    """目标仓位 → buy/sell 事件（变化点），交由 run_backtest 执行 T+1/费用/最短持有。"""
    change = pos.diff()
    change.iloc[0] = pos.iloc[0]
    return pd.DataFrame({"buy": change > 0, "sell": change < 0}, index=pos.index)


def generate_signals(score: pd.Series, daily: pd.DataFrame, cond: pd.DataFrame,
                     b_star: float, s_star: float, trend_stop: bool = True,
                     markov_table: pd.DataFrame | None = None,
                     gates: dict | None = None) -> pd.DataFrame:
    """融合信号（V1.1）。

    买入双通道（文献依据见 strategy_proposal §4 L-D V1.1 修订）：
    - 趋势确认通道：Score ≥ B* 且 大盘牛市门（hs300 > MA200）→ 动量入场（MOP 2012）；
    - 恐慌超跌通道：Score ≥ B* + PANIC_MARGIN（默认 +15）→ 深度超跌买入（skew/波动因子，
      Nagel 2012），不设大盘门；
    - 季节修正：5-10 月买入阈值 +5 / 11-4 月 −5（Halloween，Bouman-Jacobsen 2002）。
    公共门：cycle_score > -0.5、recession_prob < 0.7、连跌保护（streak≥4 且 P(涨)<0.5 时不买）。
    卖出：Score ≤ S*，或 趋势止损（close<MA60 且 Score<50，可开关），
         或 区制止损（recession_prob>0.7 且 Score<60）。
    """
    gates = gates or {}
    panic_margin = gates.get("panic_margin", 15)
    season_shift = gates.get("season_shift", 5)

    sig = pd.DataFrame(index=score.index)
    sig["score"] = score
    sig["close"] = daily["close"]
    sig["cycle_score"] = cond["cycle_score"]
    sig["recession_prob"] = cond["recession_prob"]
    sig["streak"] = cond["streak"]
    sig["ma60"] = daily["close"].rolling(60).mean()
    sig["hs300_ma200"] = (daily["hs300_close"] > daily["hs300_close"].rolling(200).mean())

    month = score.index.month
    season_adj = pd.Series(np.where(np.isin(month, [11, 12, 1, 2, 3, 4]), -season_shift, season_shift),
                           index=score.index)

    common_ok = (
        (cond["cycle_score"] > -0.5)
        & (cond["recession_prob"] < 0.7)
    ).fillna(False)
    if markov_table is not None:
        p_up = cond["streak"].map(markov_table["p_up_tomorrow"].to_dict())
        streak_guard = ~((cond["streak"] >= 4) & (p_up < 0.5))
        common_ok &= streak_guard.fillna(True)

    thr = score * 0 + b_star + season_adj  # 阈值随季节平移
    buy_trend = (score >= thr) & sig["hs300_ma200"].astype(float).eq(1.0)
    buy_panic = (score >= thr + panic_margin)
    sig["buy"] = ((buy_trend | buy_panic) & common_ok).fillna(False)

    sell_trend = (sig["close"] < sig["ma60"]) & (score < 50)
    sell_regime = (cond["recession_prob"] > 0.7) & (score < 60)
    sell_core = score <= s_star
    sig["sell"] = (sell_core | (sell_trend & trend_stop) | sell_regime).fillna(False)
    return sig


def run_backtest(sig: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
                 close: pd.Series | None = None) -> dict:
    """含 T+1 执行、费用与 7 自然日最短持有的回测。

    sig 需含 buy/sell 列；价格取 sig["close"]，或 V1.2 仓位事件流时显式传 close。
    """
    sig = sig.loc[(sig.index >= start) & (sig.index <= end)].copy()
    if "close" in sig.columns:
        px = sig["close"]
    else:
        if close is None:
            raise ValueError("sig 不含 close 列时必须传入 close 序列")
        px = close.reindex(sig.index)
    ret = px.pct_change()

    position = 0
    buy_date: pd.Timestamp | None = None
    pending_buy = False
    pending_sell = False
    deferred_sells = 0
    rows = []
    trades: list[dict] = []

    for row in sig.itertuples():
        t = row.Index
        pos_before = position
        fee = 0.0

        # 1) 执行昨日收盘产生的 pending（T+1 收盘成交，未知价法）
        if pending_buy and position == 0:
            position = 1
            buy_date = t
            fee += FEE_BUY
            trades.append({"buy_date": t, "buy_close": float(px.loc[t])})
            pending_buy = False
        elif pending_sell and position == 1:
            if buy_date is not None and (t - buy_date).days >= MIN_HOLD_NATURAL_DAYS:
                position = 0
                fee += FEE_SELL
                trades[-1].update({"sell_date": t, "sell_close": float(px.loc[t])})
                buy_date = None
                pending_sell = False
            # 未满 7 天：保持 pending，到天数满足后的下一个交易日成交

        # 2) T 日收盘读信号 → 设 pending（明日执行）
        if position == 0 and bool(row.buy) and not pending_buy:
            pending_buy = True
        elif position == 1 and bool(row.sell) and not pending_sell:
            if buy_date is not None and (t - buy_date).days < MIN_HOLD_NATURAL_DAYS:
                deferred_sells += 1
            pending_sell = True

        # 3) 当日收益归属 pos_before（前日收盘持仓）；费用记在成交日
        r_t = ret.loc[t]
        eff = pos_before * (r_t if pd.notna(r_t) else 0.0) - fee
        rows.append({"position": position, "strat_ret": eff})

    state = pd.DataFrame(rows, index=sig.index)
    state["strat_ret"] = state["strat_ret"].fillna(0.0)
    state["index_ret"] = ret.fillna(0.0)

    open_trade = trades[-1] if trades and "sell_date" not in trades[-1] else None
    metrics = _metrics(state, trades, deferred_count=deferred_sells)
    return {"state": state, "trades": trades, "open_trade": open_trade,
            "deferred_sells": deferred_sells, "metrics": metrics}


def compute_metrics(strat_ret: pd.Series, index_ret: pd.Series,
                    trades: list[dict] | None = None) -> dict:
    """在任意窗口上计算绩效指标（校准脚本对子训练/验证/测试段复用）。"""
    r = strat_ret.fillna(0.0)
    idx = index_ret.fillna(0.0)
    cum = (1 + r).cumprod()
    years = max((r.index[-1] - r.index[0]).days / 365.25, 1e-9)
    ann = cum.iloc[-1] ** (1 / years) - 1 if cum.iloc[-1] > 0 else -1.0
    dd = (cum / cum.cummax() - 1).min()
    idx_cum = (1 + idx).cumprod()
    idx_ann = idx_cum.iloc[-1] ** (1 / years) - 1 if idx_cum.iloc[-1] > 0 else -1.0

    win = 126
    roll_strat = (1 + r).rolling(win).apply(np.prod, raw=True) - 1
    roll_idx = (1 + idx).rolling(win).apply(np.prod, raw=True) - 1
    excess = roll_strat - roll_idx

    violations = 0
    for tr in (trades or []):
        if "sell_date" in tr and (tr["sell_date"] - tr["buy_date"]).days < MIN_HOLD_NATURAL_DAYS:
            violations += 1

    target_ok = ((roll_strat >= 0.04) | (excess >= 0.03))
    return {
        "ann_return": round(float(ann), 4),
        "index_ann_return": round(float(idx_ann), 4),
        "ann_excess": round(float(ann - idx_ann), 4),
        "max_drawdown": round(float(dd), 4),
        "sharpe": round(float(r.mean() / r.std() * np.sqrt(244)) if r.std() > 0 else 0.0, 3),
        "n_trades": len(trades or []),
        "roll126_win_vs_index": round(float((excess > 0).mean()), 3),
        "roll126_win_abs4_or_ex3": round(float(target_ok.mean()), 3),
        "roll126_avg_excess": round(float(excess.mean()), 4),
        "roll126_worst": round(float(roll_strat.min()), 4),
        "min_hold_violations": violations,
    }


def _metrics(state: pd.DataFrame, trades: list[dict], deferred_count: int = 0) -> dict:
    m = compute_metrics(state["strat_ret"], state["index_ret"], trades)
    m["deferred_sells_total"] = deferred_count
    return m
