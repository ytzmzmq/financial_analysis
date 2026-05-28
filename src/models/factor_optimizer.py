"""
V5.0 因子自动筛选与赋权框架

五阶段:
  1. 候选因子池 (Valuation/Liquidity/Momentum/SmartMoney, 二值化, 无look-ahead)
  2. 单因子三漏斗检验 (稀疏度2-15% + 收益>5% + Uplift CI下限>1%)
  3. 条件概率去重 (P(A|B)>0.65则保留Uplift下限更高的)
  4. Uplift驱动离散评分卡 (0.5步长, 满分10)
  5. 阈值滑动寻优 (平衡Uplift与独立机会数)
"""
import pandas as pd
import numpy as np
from scipy.stats import percentileofscore


# ═══════════════════════════════════════════
# 阶段1: 候选因子池
# ═══════════════════════════════════════════

def build_factor_pool(med_w: pd.Series) -> pd.DataFrame:
    """
    构建四维度候选因子池。所有因子二值化(1/0)，仅用T日及以前数据。

    Returns: DataFrame(index=med_w.index, columns=因子名, values=0/1)
    """
    pool = pd.DataFrame(index=med_w.index)

    # ── 维度1: 估值 (Valuation) ──
    # V1: 5年价格分位 < 15% (极度便宜)
    pool["V1_price_5y_low"] = (
        med_w.rolling(260, min_periods=52).rank(pct=True) < 0.15
    ).astype(int)

    # V2: 价格距52周低点 < 5% (接近一年低点)
    ll_52w = med_w.rolling(52).min()
    pool["V2_near_52w_low"] = ((med_w / ll_52w - 1) < 0.05).astype(int)

    # V3: 连续下跌 > 8周 (长期阴跌后的估值修复概率高)
    down_streak = (med_w.pct_change() < 0).astype(int)
    pool["V3_down_8w"] = (down_streak.rolling(8).sum() >= 7).astype(int)

    # ── 维度2: 量价冰点 (Liquidity) ──
    # L1: 周线RSI Wilder < 30
    pool["L1_rsi_30"] = (_rsi_wilder(med_w, 14) < 30).astype(int)

    # L2: 13周最大回撤 < -12% (加深阈值, 比V3的-10%更严)
    pool["L2_dd_12pct"] = ((med_w / med_w.rolling(13).max() - 1) * 100 < -12).astype(int)

    # L3: 波动率收缩 < 过去2年25分位 (暴风雨前的宁静)
    vol = med_w.pct_change().rolling(13).std() * np.sqrt(52) * 100
    pool["L3_vol_shrink"] = (
        vol < vol.rolling(104, min_periods=52).quantile(0.25)
    ).astype(int)

    # ── 维度3: 动能衰竭 (Momentum) ──
    # M1: 收益偏度 < -1.5 (极端左尾, 比之前-1更严)
    skew = med_w.pct_change().rolling(13).skew()
    pool["M1_skew_neg"] = (skew < -1.5).astype(int)

    # M2: 4周累计跌幅 > 8% (加速下跌)
    pool["M2_mom_4w"] = (med_w.pct_change(4) * 100 < -8).astype(int)

    # M3: MACD 柱状线创13周新低
    macd_hist = _macd_histogram(med_w)
    pool["M3_macd_low"] = (
        macd_hist < macd_hist.rolling(13).min()
    ).astype(int)

    # ── 维度4: 资金背离 (Smart Money) ──
    # S1: 价格跌但RSI不创新低 (底背离)
    ll_rsi = _rsi_wilder(med_w, 14).rolling(52).min()
    pool["S1_divergence"] = (
        (pool["V2_near_52w_low"] == 1) &
        (_rsi_wilder(med_w, 14) > ll_rsi + 5)
    ).astype(int)

    # S2: 下跌放缓 (本周跌幅 < 前4周平均跌幅)
    weekly_ret = med_w.pct_change() * 100
    avg_down_4w = weekly_ret.rolling(4).mean()
    pool["S2_down_slowing"] = (
        (weekly_ret < 0) & (weekly_ret > avg_down_4w)
    ).astype(int)

    return pool.fillna(0).astype(int)


def _rsi_wilder(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd_histogram(close, fast=12, slow=26, signal=9):
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    return (ef - es) - (ef - es).ewm(span=signal, adjust=False).mean()


# ═══════════════════════════════════════════
# 阶段2: 单因子三漏斗检验
# ═══════════════════════════════════════════

def bootstrap_ci(data: np.ndarray, n_iter: int = 2000, seed: int = 42) -> tuple:
    """Bootstrap 95% CI for mean"""
    if len(data) < 4:
        return (np.nan, np.nan)
    rng = np.random.RandomState(seed)
    means = []
    n = len(data)
    for _ in range(n_iter):
        idx = rng.choice(n, size=n, replace=True)
        means.append(np.mean(data[idx]))
    means = np.array(means)
    return (np.percentile(means, 2.5), np.percentile(means, 97.5))


def screen_factors(pool: pd.DataFrame, med_w: pd.Series,
                   forward_weeks: int = 13) -> pd.DataFrame:
    """
    三漏斗检验：稀疏度 → 收益 → 置信度
    """
    n_total = len(pool)
    # 无条件13周期望收益
    all_rets = np.array([
        (med_w.iloc[i + forward_weeks] / med_w.iloc[i] - 1) * 100
        for i in range(n_total - forward_weeks)
    ])
    e_uncond = np.mean(all_rets)

    results = []
    for col in pool.columns:
        triggered = pool[col] == 1
        n_triggered = triggered.sum()

        # 漏斗1: 稀疏度 2%-15%
        freq = n_triggered / n_total
        if freq < 0.02 or freq > 0.15:
            continue

        # 漏斗2: 条件期望收益 > 5%
        fwd_rets = []
        for i in range(n_total - forward_weeks):
            if triggered.iloc[i]:
                fwd_rets.append(
                    (med_w.iloc[i + forward_weeks] / med_w.iloc[i] - 1) * 100
                )
        fwd_rets = np.array(fwd_rets)
        e_cond = np.mean(fwd_rets)
        if e_cond <= 5.0:
            continue

        # 漏斗3: Uplift CI下限 > 1%
        uplift_vals = fwd_rets - e_uncond
        ci_low, ci_high = bootstrap_ci(uplift_vals)
        if np.isnan(ci_low) or ci_low <= 1.0:
            continue

        results.append({
            "factor": col,
            "dimension": col[:2],  # V/L/M/S
            "freq": freq,
            "e_cond": e_cond,
            "e_uncond": e_uncond,
            "uplift": e_cond - e_uncond,
            "uplift_ci_low": ci_low,
            "uplift_ci_high": ci_high,
            "n_signals": n_triggered,
        })

    return pd.DataFrame(results).sort_values("uplift_ci_low", ascending=False)


# ═══════════════════════════════════════════
# 阶段3: 条件概率去重
# ═══════════════════════════════════════════

def deduplicate_factors(pool: pd.DataFrame, screened: pd.DataFrame,
                         corr_threshold: float = 0.65) -> list:
    """条件概率去重：P(A|B)>0.65 则保留Uplift CI下限更高的"""
    survivors = screened["factor"].tolist()
    removed = []

    for i in range(len(survivors)):
        if survivors[i] in removed:
            continue
        for j in range(i + 1, len(survivors)):
            if survivors[j] in removed:
                continue
            a, b = survivors[i], survivors[j]
            # P(A=1 | B=1)
            b_true = pool[pool[b] == 1]
            p_a_given_b = b_true[a].mean() if len(b_true) > 0 else 0
            p_b_given_a = pool[pool[a] == 1][b].mean() if (pool[a]==1).sum() > 0 else 0

            if max(p_a_given_b, p_b_given_a) > corr_threshold:
                # 保留 Uplift CI 下限更高的
                ci_a = screened[screened["factor"] == a]["uplift_ci_low"].values[0]
                ci_b = screened[screened["factor"] == b]["uplift_ci_low"].values[0]
                if ci_a >= ci_b:
                    removed.append(b)
                else:
                    removed.append(a)

    return [f for f in survivors if f not in removed]


# ═══════════════════════════════════════════
# 阶段4: Uplift驱动评分卡
# ═══════════════════════════════════════════

def build_scoring_card(screened: pd.DataFrame, final_factors: list,
                        max_score: float = 10.0) -> pd.DataFrame:
    """
    按Uplift贡献度分配权重，离散化到0.5步长。
    """
    sub = screened[screened["factor"].isin(final_factors)].copy()
    total_uplift = sub["uplift"].sum()
    sub["raw_weight"] = sub["uplift"] / total_uplift
    sub["raw_score"] = sub["raw_weight"] * max_score
    sub["discrete_score"] = (sub["raw_score"] * 2).round() / 2  # 四舍五入到0.5
    # 确保不低于0.5
    sub["discrete_score"] = sub["discrete_score"].clip(lower=0.5)
    # 总分归一化到max_score
    scale = max_score / sub["discrete_score"].sum()
    sub["final_score"] = (sub["discrete_score"] * scale * 2).round() / 2
    return sub[["factor", "dimension", "uplift", "uplift_ci_low",
                "raw_weight", "final_score"]].sort_values("final_score", ascending=False)


# ═══════════════════════════════════════════
# 阶段5: 阈值滑动寻优
# ═══════════════════════════════════════════

def threshold_optimization(pool: pd.DataFrame, scoring: pd.DataFrame,
                           med_w: pd.Series, forward_weeks: int = 13) -> pd.DataFrame:
    """
    滑动阈值, 输出每个阈值下的Uplift和独立机会数。
    """
    # 计算加权总分
    total_score = pd.Series(0, index=pool.index, dtype=float)
    for _, row in scoring.iterrows():
        f = row["factor"]
        if f in pool.columns:
            total_score += pool[f] * row["final_score"]

    n_total = len(pool)
    all_rets = np.array([
        (med_w.iloc[i + forward_weeks] / med_w.iloc[i] - 1) * 100
        for i in range(n_total - forward_weeks)
    ])
    e_uncond = np.mean(all_rets)

    # 去重叠信号
    def count_independent(triggered: np.ndarray, min_gap: int = 4) -> int:
        dates = np.where(triggered)[0]
        if len(dates) == 0:
            return 0
        count = 1
        last = dates[0]
        for d in dates[1:]:
            if d - last >= min_gap:
                count += 1
                last = d
        return count

    results = []
    thresholds = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]
    for thresh in thresholds:
        triggered = (total_score >= thresh).values
        n_independent = count_independent(triggered)

        fwd_rets = []
        for i in range(n_total - forward_weeks):
            if triggered[i]:
                fwd_rets.append(
                    (med_w.iloc[i + forward_weeks] / med_w.iloc[i] - 1) * 100
                )
        fwd_rets = np.array(fwd_rets)
        e_cond = np.mean(fwd_rets) if len(fwd_rets) > 0 else np.nan
        uplift = e_cond - e_uncond if not np.isnan(e_cond) else np.nan
        ci_low, ci_high = bootstrap_ci(fwd_rets) if len(fwd_rets) >= 4 else (np.nan, np.nan)

        results.append({
            "threshold": thresh,
            "n_independent": n_independent,
            "n_raw": int(triggered.sum()),
            "e_cond": e_cond,
            "uplift": uplift,
            "uplift_ci_low": ci_low,
            "uplift_ci_high": ci_high,
        })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════
# 一键运行
# ═══════════════════════════════════════════

def run_full_pipeline(med_w: pd.Series) -> dict:
    """执行完整五阶段优化, 返回所有结果"""
    print("=" * 60)
    print("  V5.0 因子自动筛选与赋权框架")
    print("=" * 60)

    # 阶段1
    print("\n[阶段1] 构建候选因子池...")
    pool = build_factor_pool(med_w)
    print(f"  候选因子: {len(pool.columns)} 个")

    # 阶段2
    print("\n[阶段2] 单因子三漏斗检验...")
    screened = screen_factors(pool, med_w)
    print(f"  通过筛选: {len(screened)}/{len(pool.columns)}")
    if len(screened) == 0:
        print("  ⚠ 无因子通过筛选!")
        return {}
    for _, r in screened.iterrows():
        print(f"    {r['factor']:20s} | freq={r['freq']:.1%} | E={r['e_cond']:+.1f}% | Uplift={r['uplift']:+.1f}% | CI=[{r['uplift_ci_low']:+.1f}%,{r['uplift_ci_high']:+.1f}%]")

    # 阶段3
    print("\n[阶段3] 条件概率去重...")
    final = deduplicate_factors(pool, screened)
    print(f"  去重后: {len(final)}/{len(screened)}")
    print(f"  入选: {final}")

    # 阶段4
    print("\n[阶段4] 评分卡赋权...")
    scoring = build_scoring_card(screened, final)
    for _, r in scoring.iterrows():
        print(f"    {r['factor']:20s} | Uplift={r['uplift']:+.1f}% | 得分={r['final_score']:.1f}")

    # 阶段5
    print("\n[阶段5] 阈值滑动寻优...")
    threshold_df = threshold_optimization(pool, scoring, med_w)
    # 找最优: 独立机会 >=5 且 uplift CI下限最高的
    candidates = threshold_df[(threshold_df["n_independent"] >= 5)]
    if len(candidates) > 0:
        best = candidates.sort_values("uplift_ci_low", ascending=False).iloc[0]
        print(f"  最优阈值: {best['threshold']} (机会={int(best['n_independent'])}, Uplift={best['uplift']:+.1f}%)")
    print("\n" + threshold_df.to_string(index=False))

    return {
        "pool": pool,
        "screened": screened,
        "final_factors": final,
        "scoring": scoring,
        "threshold_analysis": threshold_df,
    }
