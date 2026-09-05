# -*- coding: utf-8 -*-
"""因子三漏斗筛选（校准流水线与周期性筛查共用）。

漏斗 1 可投资性：训练段内有效样本 ≥ min_obs（≈10 年）、top 分位样本 ≥ min_top；
漏斗 2 统计性：top/bottom 三分位的 20 日前瞻收益差 t≥3（Welch）、训练段前后半方向
        一致、最大单年触发占比 ≤ 0.40；
漏斗 3 增益性：与已入选因子 Spearman |ρ|≤0.7（贪心，按 |t| 降序）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def screen_factors(factors: pd.DataFrame, fwd20: pd.Series,
                   train: tuple[pd.Timestamp, pd.Timestamp],
                   log=print, min_obs: int = 2500, min_top: int = 300,
                   max_year_share: float = 0.40, t_threshold: float = 3.0,
                   rho_threshold: float = 0.7) -> list[str]:
    """对 FACTOR_DEFS 中全部因子跑三漏斗，返回入选因子列表（按 |t| 降序）。"""
    from src.models.factor_library import FACTOR_DEFS

    tr = factors.loc[(factors.index >= train[0]) & (factors.index <= train[1])]
    f20 = fwd20.reindex(tr.index)
    half = tr.index[len(tr) // 2]
    years = tr.index.year
    selected: list[str] = []
    log("\n## 因子三漏斗筛选\n")
    log(f"窗口：{train[0].date()} → {train[1].date()}｜门槛：t≥{t_threshold}、前后半同向、"
        f"单年占比≤{max_year_share:.0%}、|ρ|≤{rho_threshold}\n")
    log("| 因子 | 方向 | t值 | n_top | 前后半一致 | 最大单年占比 | 结果 |")
    log("|---|---|---|---|---|---|---|")
    rows = []
    for name, (direction, desc) in FACTOR_DEFS.items():
        if name not in tr.columns:
            continue
        s = tr[name]
        valid = s.notna() & f20.notna()
        if valid.sum() < min_obs:
            log(f"| {name} | {direction:+d} | — | — | — | — | SKIP(样本{int(valid.sum())}<{min_obs}) |")
            continue
        q_hi = s.rolling(1250, min_periods=500).rank(pct=True)
        top, bot = valid & (q_hi >= 2 / 3), valid & (q_hi <= 1 / 3)
        n_top = int(top.sum())
        if n_top < min_top:
            log(f"| {name} | {direction:+d} | — | {n_top} | — | — | SKIP(top<{min_top}) |")
            continue
        t_stat, _ = stats.ttest_ind(f20[top], f20[bot], equal_var=False)
        spread = float(f20[top].mean() - f20[bot].mean())
        h1 = f20[top & (tr.index <= half)].mean() - f20[bot & (tr.index <= half)].mean()
        h2 = f20[top & (tr.index > half)].mean() - f20[bot & (tr.index > half)].mean()
        consistent = bool(np.sign(h1) == np.sign(h2) == np.sign(spread)) if np.isfinite(h1) and np.isfinite(h2) else False
        yearly_share = (top.groupby(years).sum() / max(n_top, 1))
        max_share = float(yearly_share.max())
        passed = bool(t_stat >= t_threshold and consistent and max_share <= max_year_share and spread > 0)
        rows.append((name, direction, t_stat, n_top, consistent, max_share, passed, s))
        log(f"| {name} | {direction:+d} | {t_stat:.2f} | {n_top} | {consistent} | {max_share:.2f} | "
            f"{'PASS' if passed else 'FAIL'} |")
    rows.sort(key=lambda r: -r[2])
    for name, direction, t_stat, n_top, consistent, max_share, passed, s in rows:
        if not passed:
            continue
        ok = True
        for sel_name in selected:
            a, b = s.align(tr[sel_name], join="inner")
            rho = a.corr(b, method="spearman")
            if pd.notna(rho) and abs(rho) > rho_threshold:
                ok = False
                log(f"\n> 剔除 `{name}`：与 `{sel_name}` Spearman ρ={rho:.2f} > {rho_threshold}")
                break
        if ok:
            selected.append(name)
    log(f"\n**入选因子（{len(selected)}）**：{selected}\n")
    return selected
