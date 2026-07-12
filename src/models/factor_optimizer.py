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

from src.models.indicators import rsi_wilder, macd_histogram


# ═══════════════════════════════════════════
# 阶段1: 候选因子池
# ═══════════════════════════════════════════

def build_factor_pool(med_w: pd.Series, vol_w: pd.Series = None,
                      pe_w: pd.Series = None, margin_w: pd.Series = None,
                      north_w: pd.Series = None, hs300_w: pd.Series = None,
                      m2_w: pd.Series = None) -> pd.DataFrame:
    """
    构建候选因子池。所有因子二值化(1/0)，仅用T日及以前数据。

    新增外部因子参数:
        north_w: 北向资金周频净流入(亿元), 日频求和得到
        hs300_w: 沪深300周频收盘价
        m2_w:    M2同比增速(%), 月频前向填充到周频
    """
    pool = pd.DataFrame(index=med_w.index)

    # ── 维度1: 估值 (Valuation) ──
    pool["V1_price_5y_low"] = (
        med_w.rolling(260, min_periods=52).rank(pct=True) < 0.15
    ).astype(int)

    ll_52w = med_w.rolling(52).min()
    pool["V2_near_52w_low"] = ((med_w / ll_52w - 1) < 0.05).astype(int)

    down_streak = (med_w.pct_change() < 0).astype(int)
    pool["V3_down_8w"] = (down_streak.rolling(8).sum() >= 7).astype(int)

    # V4: PE估值冰点 (真实PE < 5年15%分位, 无PE数据则退化为价格分位)
    if pe_w is not None and len(pe_w.dropna()) > 52:
        pe_aligned = pe_w.reindex(med_w.index).ffill()
        pool["V4_true_pe_low"] = (
            pe_aligned.rolling(260, min_periods=52).rank(pct=True) < 0.15
        ).astype(int)

    # ── 维度2: 量价冰点 (Liquidity) ──
    pool["L1_rsi_30"] = (rsi_wilder(med_w, 14) < 30).astype(int)
    pool["L2_dd_12pct"] = ((med_w / med_w.rolling(13).max() - 1) * 100 < -12).astype(int)

    vol = med_w.pct_change().rolling(13).std() * np.sqrt(52) * 100
    pool["L3_vol_shrink"] = (
        vol < vol.rolling(104, min_periods=52).quantile(0.25)
    ).astype(int)

    # L4: 地量冰点 (成交量<2年10%分位, 无人问津)
    if vol_w is not None and len(vol_w.dropna()) > 52:
        vol_aligned = vol_w.reindex(med_w.index).ffill()
        pool["L4_vol_freezing"] = (
            vol_aligned.rolling(104, min_periods=52).rank(pct=True) < 0.10
        ).astype(int)

    # ── 维度3: 动能衰竭 (Momentum) ──
    skew = med_w.pct_change().rolling(13).skew()
    pool["M1_skew_neg"] = (skew < -1.5).astype(int)
    pool["M2_mom_4w"] = (med_w.pct_change(4) * 100 < -8).astype(int)

    macd_hist = macd_histogram(med_w)
    pool["M3_macd_low"] = (macd_hist < macd_hist.rolling(13).min()).astype(int)

    # ── 维度4: 资金背离 (Smart Money) ──
    ll_rsi = rsi_wilder(med_w, 14).rolling(52).min()
    pool["S1_divergence"] = (
        (pool["V2_near_52w_low"] == 1) &
        (rsi_wilder(med_w, 14) > ll_rsi + 5)
    ).astype(int)

    weekly_ret = med_w.pct_change() * 100
    pool["S2_down_slowing"] = (
        (weekly_ret < 0) & (weekly_ret > weekly_ret.rolling(4).mean())
    ).astype(int)

    # S3: 融资底背离 (价格13周新低 + 融资4周逆势加仓)
    if margin_w is not None and len(margin_w.dropna()) > 20:
        margin_aligned = margin_w.reindex(med_w.index).ffill()
        price_13w_low = (med_w == med_w.rolling(13).min()).astype(int)
        margin_chg_4w = margin_aligned.pct_change(4)
        pool["S3_margin_diverge"] = (
            (price_13w_low == 1) & (margin_chg_4w > 0)
        ).astype(int)

    # ── 维度5: 外部环境 (External) ──

    # S4: 北向资金背离 (价格13周新低 + 北向4周净流入>0)
    if north_w is not None and len(north_w.dropna()) > 20:
        north_aligned = north_w.reindex(med_w.index).ffill()
        price_13w_low = (med_w == med_w.rolling(13).min()).astype(int)
        north_net_4w = north_aligned.rolling(4).sum()
        pool["S4_north_diverge"] = (
            (price_13w_low == 1) & (north_net_4w > 0)
        ).astype(int)

    # E1: 大盘熊市 (HS300 < 200日均线, 系统性恐慌放大底部信号)
    if hs300_w is not None and len(hs300_w.dropna()) > 200:
        hs300_aligned = hs300_w.reindex(med_w.index).ffill()
        hs300_ma200 = hs300_aligned.rolling(200, min_periods=100).mean()
        pool["E1_market_bear"] = (hs300_aligned < hs300_ma200).astype(int)

    # E2: M2加速 (当前M2增速 > 近13周均值, 货币宽松环境)
    if m2_w is not None and len(m2_w.dropna()) > 20:
        m2_aligned = m2_w.reindex(med_w.index).ffill()
        m2_ma13 = m2_aligned.rolling(13, min_periods=4).mean()
        pool["E2_m2_accel"] = (m2_aligned > m2_ma13).astype(int)

    return pool.fillna(0).astype(int)


# _rsi_wilder 和 _macd_histogram 已移至 src/models/indicators.py
# 本文件通过顶部 import 和向后兼容别名使用它们


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

def run_full_pipeline(med_w: pd.Series, vol_w: pd.Series = None,
                       pe_w: pd.Series = None, margin_w: pd.Series = None,
                       north_w: pd.Series = None, hs300_w: pd.Series = None,
                       m2_w: pd.Series = None) -> dict:
    """执行完整五阶段优化, 返回所有结果"""
    print("=" * 60)
    print("  V5.0 因子自动筛选与赋权框架")
    print("=" * 60)

    # 阶段1
    print("\n[阶段1] 构建候选因子池...")
    pool = build_factor_pool(med_w, vol_w=vol_w, pe_w=pe_w, margin_w=margin_w,
                             north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)
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
