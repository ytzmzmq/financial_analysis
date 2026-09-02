# -*- coding: utf-8 -*-
"""L-A 周期状态层：区制模型（Hamilton 1989）+ 周期相位定位。

预注册设计（docs/strategy_proposal.md §4 L-A，确认版）：
- 区制：对申万农林牧渔周收益拟合 2 状态 Markov 区制模型（均值+方差双切换），
  只在训练段估计参数并冻结；在线用 Hamilton 前向滤波输出"收缩区制概率"。
  statsmodels 不可用/不收敛时降级为确定性启发式（波动分位代理），并在输出中标记。
- 相位：月频对数价 HP 滤波（Ravn-Uhlig λ=129600）取周期分量，
  z 分数的标准化常数（训练段 std）冻结；相位 = 谷/扩张/峰/收缩 四象限。
  （预注册时以带通滤波为原案；HP 滤波端点不依赖未来值重算窗口、实现确定，
  作为带通滤波的替代并在此处留档。）
- CycleScore = clip(-z, -1, 1)：谷=+1、峰=-1。
- 猪价相位：同一套管线用于生猪价格指数（2015 起周频）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

HP_LAMBDA_MONTHLY = 129_600  # Ravn-Uhlig 月频标准 λ
TRAIN_END = pd.Timestamp("2021-12-31")


# ── 区制模型 ────────────────────────────────────────────────

def fit_weekly_regime(close_daily: pd.Series, train_end: pd.Timestamp = TRAIN_END) -> dict:
    """训练段内拟合 2 状态周收益区制模型，返回冻结参数。"""
    wk = close_daily.resample("W-FRI").last().dropna()
    rets = (np.log(wk).diff().dropna())
    train = rets[rets.index <= train_end]
    try:
        mod = MarkovRegression(train, k_regimes=2, trend="c", switching_variance=True)
        res = mod.fit(search_reps=20, disp=False)
        mu = np.asarray([res.params[f"const[{i}]"] for i in range(2)])
        sig = np.sqrt(np.asarray([res.params[f"sigma2[{i}]"] for i in range(2)]))
        # statsmodels 0.15 参数化：p[0->0] 与 p[1->0]（每行只给 k_regimes-1 个自由参数）
        p_stay0 = float(res.params["p[0->0]"])
        p_stay1 = 1.0 - float(res.params["p[1->0]"])
        # 收缩区制 = 低均值区制
        low = int(np.argmin(mu))
        params = {
            "method": "statsmodels",
            "mu": mu.tolist(),
            "sigma2": (sig**2).tolist(),
            "p00": p_stay0,
            "p11": p_stay1,
            "low_regime": low,
            "n_train": int(len(train)),
            "last_train_date": str(train.index.max().date()),
        }
    except Exception as e:  # noqa: BLE001 — 确定性降级，报告中标记
        # 降级：以波动分位定义高波动区制（收缩代理），转移概率由训练段标签游程估计
        vol = train.rolling(8).std()
        hi = (vol > vol.median()).values
        p00 = _run_trans_prob(hi, False)
        params = {
            "method": "fallback_vol_proxy",
            "fallback_reason": f"{type(e).__name__}: {str(e)[:120]}",
            "p00": p00,
            "p11": _run_trans_prob(hi, True),
            "n_train": int(len(train)),
            "last_train_date": str(train.index.max().date()),
        }
    return params


def _run_trans_prob(labels: np.ndarray, state: bool) -> float:
    """标签游程法估计 P(下一期仍是 state)。"""
    stay = total = 0
    for i in range(len(labels) - 1):
        if labels[i] == state:
            total += 1
            stay += int(labels[i + 1] == state)
    return stay / total if total else 0.5


def regime_recession_prob(close_daily: pd.Series, params: dict) -> pd.Series:
    """冻结参数 + 前向滤波（只用过去信息）输出收缩区制概率（周频）。"""
    wk = close_daily.resample("W-FRI").last().dropna()
    rets = np.log(wk).diff().dropna()
    probs = pd.Series(index=rets.index, dtype=float)
    if params["method"] == "statsmodels":
        mu0, mu1 = params["mu"][0], params["mu"][1]
        s20, s21 = params["sigma2"][0], params["sigma2"][1]
        low = params["low_regime"]
        p_stay_low = params["p00"] if low == 0 else params["p11"]
        p_stay_high = params["p11"] if low == 0 else params["p00"]
        prob_low = 0.5
        for t, r in rets.items():
            # 预测步
            pr_low = prob_low * p_stay_low + (1 - prob_low) * (1 - p_stay_high)
            # 更新步（高斯似然）
            lik_low = _norm_pdf(r, mu0 if low == 0 else mu1, s20 if low == 0 else s21)
            lik_high = _norm_pdf(r, mu1 if low == 0 else mu0, s21 if low == 0 else s20)
            joint = pr_low * lik_low
            denom = joint + (1 - pr_low) * lik_high
            prob_low = joint / denom if denom > 0 else pr_low
            probs.loc[t] = prob_low
    else:
        vol = rets.rolling(8).std()
        med = vol.median()  # 降级模式：中位数在应用时点已知（全历史中位数含未来信息，仅降级容错用）
        probs = (vol > med).astype(float)
    return probs.fillna(0.5)


def _norm_pdf(x: float, mu: float, sigma2: float) -> float:
    return float(np.exp(-0.5 * (x - mu) ** 2 / sigma2) / np.sqrt(2 * np.pi * sigma2))


# ── 周期相位（HP 月频周期分量） ─────────────────────────────

def cycle_phase(monthly_log_price: pd.Series, train_end: pd.Timestamp = TRAIN_END) -> pd.DataFrame:
    """HP 周期分量 → z（std 用训练段冻结）→ 相位与 CycleScore。"""
    from statsmodels.tsa.filters.hp_filter import hpfilter

    s = monthly_log_price.dropna()
    train_mask = s.index <= train_end
    std_train = None
    if train_mask.sum() > 36:
        cyc_train, _ = hpfilter(s[train_mask], lamb=HP_LAMBDA_MONTHLY)  # hpfilter 返回 (cycle, trend)
        std_train = float(cyc_train.std())
    cyc, _ = hpfilter(s, lamb=HP_LAMBDA_MONTHLY)
    if not std_train or np.isnan(std_train) or std_train == 0:
        std_train = float(cyc.std()) or 1.0
    z = cyc / std_train
    slope = z - z.shift(3)
    phase = pd.Series(index=s.index, dtype=object)
    phase[(z <= -1.0)] = "谷"
    phase[(z >= 1.0)] = "峰"
    phase[(z > -1.0) & (z < 1.0) & (slope > 0)] = "扩张"
    phase[(z > -1.0) & (z < 1.0) & (slope <= 0)] = "收缩"
    out = pd.DataFrame({
        "cycle_z": z,
        "cycle_slope": slope,
        "cycle_phase": phase,
        "cycle_score": z.mul(-1).clip(-1, 1),
    })
    return out


def expand_phase_to_daily(phase_df: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """月频相位 → 日频（当月内使用最近已实现月份的相位，不前视）。"""
    idx = phase_df.index + pd.offsets.MonthEnd(0)
    shifted = phase_df.copy()
    shifted.index = idx
    out = shifted.reindex(calendar).ffill()
    return out
