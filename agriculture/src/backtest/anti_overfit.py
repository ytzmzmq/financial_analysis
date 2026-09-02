# -*- coding: utf-8 -*-
"""反过拟合检验（docs/strategy_proposal.md §3 协议的代码实现）。

- reality_check：White (2000) stationary bootstrap，检验"48 个配置中最优者"
  是否显著优于买入持有（数据窥探校正后的 p 值）。
- deflated_sharpe：Bailey & López de Prado (2014)，按试验次数与非正态性修正。
- pbo_cscv：Bailey et al. (2017) 组合清洗交叉验证，估计回测过拟合概率。
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def stationary_bootstrap_indices(n: int, n_boot: int, avg_block: int = 10,
                                 seed: int = 42) -> np.ndarray:
    """stationary bootstrap（Politis-Romano）索引矩阵，形状 (n_boot, n)。"""
    rng = np.random.default_rng(seed)
    p = 1.0 / avg_block
    idx = np.empty((n_boot, n), dtype=np.int64)
    for b in range(n_boot):
        cur = rng.integers(0, n)
        row = np.empty(n, dtype=np.int64)
        for t in range(n):
            row[t] = cur
            if rng.random() < p:
                cur = rng.integers(0, n)
            else:
                cur = (cur + 1) % n
        idx[b] = row
    return idx


def reality_check(strat_returns: np.ndarray, index_returns: np.ndarray,
                  n_boot: int = 1000, avg_block: int = 10, seed: int = 42) -> dict:
    """strat_returns: (T, N) 各配置日收益；index_returns: (T,) 基准。

    RC 统计量 = max_i mean(d_i)；d_i = r_i - r_bench。
    p 值 = bootstrap 分布中 max 统计量 ≥ 观测值的比例。
    """
    d = strat_returns - index_returns[:, None]
    obs = d.mean(axis=0)
    obs_max = float(obs.max())
    idx = stationary_bootstrap_indices(len(d), n_boot, avg_block, seed)
    boot_max = np.empty(n_boot)
    for b in range(n_boot):
        boot_max[b] = d[idx[b]].mean(axis=0).max()
    p = float((boot_max >= obs_max).mean())
    return {"obs_best_mean_daily": round(obs_max, 6),
            "rc_p_value": round(p, 4),
            "significant_5pct": bool(p < 0.05)}


def deflated_sharpe(strat_returns: np.ndarray, freq: int = 244) -> dict:
    """strat_returns: (T, N) 全部试验配置的日收益矩阵。

    按 Bailey & López de Prado (2014)：SR0 = sqrt(V[SR]) * ((1-γ)Z(1-1/N) + γZ(1-1/(N·e)))，
    DSR = Φ( (SR̂ - SR0)·sqrt(T-1) / sqrt(1 - γ3·SR̂ + (γ4-1)/4·SR̂²) )，SR̂ 为期间 Sharpe。
    返回最优配置的 DSR（>0.9 视为通过）。
    """
    t = strat_returns.shape[0]
    n_trials = strat_returns.shape[1]
    srs = []
    for i in range(n_trials):
        col = strat_returns[:, i][np.isfinite(strat_returns[:, i])]
        std = col.std(ddof=1)
        srs.append(col.mean() / std if std > 0 else 0.0)  # 零交易配置按 SR=0 计
    srs = np.asarray(srs)
    best = int(np.nanargmax(srs))
    r = strat_returns[:, best][np.isfinite(strat_returns[:, best])]
    sr = float(srs[best])
    gamma = 0.5772156649
    v_sr = float(np.nanvar(srs, ddof=1))
    sr0 = np.sqrt(max(v_sr, 1e-12)) * (
        (1 - gamma) * stats.norm.ppf(1 - 1.0 / n_trials)
        + gamma * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
    )
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))
    denom = np.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr**2))
    dsr = float(stats.norm.cdf((sr - sr0) * np.sqrt(t - 1) / denom))
    return {"sr_best_period": round(sr, 5),
            "sr_annualized": round(sr * np.sqrt(freq), 3),
            "v_sr_across_trials": round(v_sr, 6),
            "sr0": round(float(sr0), 5),
            "dsr": round(dsr, 4),
            "n_trials": n_trials,
            "pass_090": bool(dsr > 0.9)}


def pbo_cscv(returns_matrix: np.ndarray, n_blocks: int = 12, seed: int = 42) -> float:
    """returns_matrix: (T, N) 验证段各配置日收益。PBO ∈ [0,1]，<0.5 视为通过。

    CSCV：把 T 期分成 n_blocks 块，穷举一半训练/一半测试的组合；
    训练块内选最优配置，看它在测试块内是否跑输中位数 → 计过拟合一次。
    """
    from itertools import combinations

    t, n = returns_matrix.shape
    idx = np.array_split(np.arange(t), n_blocks)
    rng = np.random.default_rng(seed)
    if n_blocks > 14:  # 控制组合爆炸
        combos = list(combinations(range(n_blocks), n_blocks // 2))
        if len(combos) > 3000:
            sel = rng.choice(len(combos), 3000, replace=False)
            combos = [combos[i] for i in sel]
    else:
        combos = list(combinations(range(n_blocks), n_blocks // 2))

    overfit = total = 0
    for train_blocks in combos:
        test_blocks = [b for b in range(n_blocks) if b not in train_blocks]
        tr = np.concatenate([idx[b] for b in train_blocks])
        te = np.concatenate([idx[b] for b in test_blocks])
        tr_means = returns_matrix[tr].mean(axis=0)
        te_means = returns_matrix[te].mean(axis=0)
        best = int(np.argmax(tr_means))
        med_test = float(np.median(te_means))
        total += 1
        if te_means[best] < med_test:
            overfit += 1
    return overfit / total if total else 1.0
