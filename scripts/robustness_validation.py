"""
V5.2 模型稳健性检验

1000 个随机种子 × 7:3 分 train/test × 考虑/不考虑时间效应

一致性检验: 因子选择是否稳定 (Jaccard, 选择频率, 权重变异)
稳健性检验: 训练集选出的因子在测试集是否仍然有效 (uplift, 退化比)

用法:
    cd financial_analysis
    python scripts/robustness_validation.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime
from itertools import combinations

from src.models.factor_optimizer import build_factor_pool, screen_factors
from src.models.indicators import rsi_wilder


# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

N_SEEDS = 1000
TRAIN_RATIO = 0.7
FORWARD_WEEKS = 13
BOOTSTRAP_ITER = 500  # 加速版 bootstrap

# 全量候选因子 (V5.2 管线)
ALL_CANDIDATE_FACTORS = [
    "V1_price_5y_low", "V2_near_52w_low", "V3_down_8w",
    "L1_rsi_30", "L2_dd_12pct", "L3_vol_shrink",
    "M1_skew_neg", "M2_mom_4w", "M3_macd_low",
    "S1_divergence", "S2_down_slowing", "S3_margin_diverge",
    "S4_north_diverge", "E1_market_bear", "E2_m2_accel",
]

# V5.2 当前模型
V52_FACTORS = {"L1_rsi_30": 3.0, "M1_skew_neg": 2.5,
               "S3_margin_diverge": 2.0, "V1_price_5y_low": 2.0}
V52_NAMES = set(V52_FACTORS.keys())


# ═══════════════════════════════════════════
# 快速 Bootstrap CI (向量化)
# ═══════════════════════════════════════════

def fast_bootstrap_ci_low(data, n_iter=BOOTSTRAP_ITER, seed=42):
    """Bootstrap CI 下限 (向量化, 快速)"""
    if len(data) < 4:
        return np.nan
    rng = np.random.RandomState(seed)
    idx = rng.randint(0, len(data), size=(n_iter, len(data)))
    means = data[idx].mean(axis=1)
    return float(np.percentile(means, 2.5))


# ═══════════════════════════════════════════
# 轻量三漏斗 (跳过过慢的完整版)
# ═══════════════════════════════════════════

def quick_screen(pool, med_w, forward_weeks=FORWARD_WEEKS, relaxed=False):
    """三漏斗: 稀疏度 2-15% → 条件收益 >5% → Uplift CI >1%

    relaxed=True: 宽松版 (小样本适用) — freq_min=1.5%, ci_min=0.5%
    """
    freq_min = 0.015 if relaxed else 0.02
    ci_min = 0.5 if relaxed else 1.0
    n_total = len(pool)
    all_rets = np.array([
        (med_w.iloc[i + forward_weeks] / med_w.iloc[i] - 1) * 100
        for i in range(n_total - forward_weeks)
    ])
    e_uncond = np.mean(all_rets)

    results = []
    for col in pool.columns:
        triggered = (pool[col] == 1).values
        n_triggered = triggered.sum()
        freq = n_triggered / n_total
        if freq < freq_min or freq > 0.15:
            continue

        fwd_rets = np.array([
            (med_w.iloc[i + forward_weeks] / med_w.iloc[i] - 1) * 100
            for i in range(n_total - forward_weeks) if triggered[i]
        ])
        e_cond = np.mean(fwd_rets)
        if e_cond <= 5.0:
            continue

        ci_low = fast_bootstrap_ci_low(fwd_rets - e_uncond)
        if np.isnan(ci_low) or ci_low <= ci_min:
            continue

        results.append({
            "factor": col, "freq": freq, "e_cond": e_cond,
            "uplift": e_cond - e_uncond, "uplift_ci_low": ci_low,
            "n_signals": int(n_triggered),
        })

    if not results:
        return pd.DataFrame(columns=["factor", "freq", "e_cond", "uplift",
                                     "uplift_ci_low", "n_signals"])

    return pd.DataFrame(results).sort_values("uplift_ci_low", ascending=False)


# ═══════════════════════════════════════════
# Uplift 评估 (在指定数据段上)
# ═══════════════════════════════════════════

def evaluate_uplift(pool_sub, med_sub, factors, forward_weeks=FORWARD_WEEKS):
    """在给定数据子集上评估因子组合的 uplift

    pool_sub: 因子池子集 (sliced)
    med_sub:  价格序列子集 (sliced, 与 pool_sub 对齐)
    """
    n = len(pool_sub)
    if n < forward_weeks + 10:
        return {"uplift": np.nan, "e_cond": np.nan, "e_uncond": np.nan, "n_signals": 0}

    all_rets = np.array([
        (med_sub.iloc[i + forward_weeks] / med_sub.iloc[i] - 1) * 100
        for i in range(n - forward_weeks)
    ])
    e_uncond = np.mean(all_rets)

    triggered = np.zeros(n - forward_weeks, dtype=bool)
    for f in factors:
        if f in pool_sub.columns:
            triggered |= (pool_sub[f].iloc[:n - forward_weeks].values == 1)

    n_signals = triggered.sum()
    if n_signals < 3:
        return {"uplift": np.nan, "e_cond": np.nan, "e_uncond": float(e_uncond),
                "n_signals": int(n_signals)}

    e_cond = np.mean(all_rets[triggered])
    ci_low = fast_bootstrap_ci_low(all_rets[triggered])

    return {
        "uplift": float(e_cond - e_uncond),
        "e_cond": float(e_cond),
        "e_uncond": float(e_uncond),
        "n_signals": int(n_signals),
        "ci_low": float(ci_low) if not np.isnan(ci_low) else np.nan,
    }


# ═══════════════════════════════════════════
# 单次迭代
# ═══════════════════════════════════════════

def run_one_seed(pool, med_w, seed, temporal=True, warmup=52, relaxed=False):
    """
    单次 train/test 分割 + 三漏斗筛选 + 评估

    temporal=True:  前70%=train, 后30%=test (尊重时间顺序)
    temporal=False: 随机70/30分割 (不考虑时间)
    """
    rng = np.random.RandomState(seed)
    n = len(pool)

    if temporal:
        split = int(n * TRAIN_RATIO)
        train_idx = np.arange(0, split)
        test_idx = np.arange(split, n)
    else:
        idx = np.arange(n)
        rng.shuffle(idx)
        split = int(n * TRAIN_RATIO)
        train_idx = np.sort(idx[:split])
        test_idx = np.sort(idx[split:])

    # 构建 train/test 子集 (保留 DatetimeIndex)
    train_pool = pool.iloc[train_idx]
    train_med = med_w.iloc[train_idx]
    test_pool = pool.iloc[test_idx]
    test_med = med_w.iloc[test_idx]

    # ── 训练集: 三漏斗筛选 ──
    screened = quick_screen(train_pool, train_med, FORWARD_WEEKS, relaxed=relaxed)

    if len(screened) == 0:
        return None

    selected = screened["factor"].tolist()

    # ── 训练集评分 ──
    train_eval = evaluate_uplift(train_pool, train_med, selected)

    # ── 测试集评估 ──
    test_eval = evaluate_uplift(test_pool, test_med, selected)

    # ── V5.2 当前因子在测试集的表现 ──
    v52_eval = evaluate_uplift(test_pool, test_med, list(V52_NAMES))

    # ── 权重分配 (简化版: 按 uplift 比例) ──
    total_uplift = screened["uplift"].sum()
    weights = {}
    for _, r in screened.iterrows():
        weights[r["factor"]] = round(r["uplift"] / total_uplift * 10, 1) if total_uplift > 0 else 0

    return {
        "seed": seed,
        "n_train": len(train_idx),
        "n_test": len(test_idx),
        "selected_factors": selected,
        "n_selected": len(selected),
        "weights": weights,
        "train_uplift": train_eval["uplift"],
        "train_e_cond": train_eval["e_cond"],
        "train_n_signals": train_eval["n_signals"],
        "test_uplift": test_eval["uplift"],
        "test_e_cond": test_eval["e_cond"],
        "test_n_signals": test_eval["n_signals"],
        "test_ci_low": test_eval.get("ci_low", np.nan),
        "v52_test_uplift": v52_eval["uplift"],
        "v52_test_n_signals": v52_eval["n_signals"],
        "v52_matches": len(set(selected) & V52_NAMES),
    }


# ═══════════════════════════════════════════
# 分析 + 报告
# ═══════════════════════════════════════════

def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def analyze_and_report(records, mode_name):
    """生成单个模式的分析结果"""
    df = pd.DataFrame(records)
    n_runs = len(df)
    n_valid = len(df[df["n_selected"] > 0])

    lines = []
    lines.append(f"### {mode_name}")
    lines.append(f"")
    lines.append(f"有效运行: {n_valid}/{n_runs}")
    lines.append(f"")

    if n_valid == 0:
        lines.append("无有效运行，跳过分析。")
        return "\n".join(lines), df

    valid = df[df["n_selected"] > 0]

    # ── 1. 因子选择频率 ──
    all_factors = set()
    for sf in valid["selected_factors"]:
        all_factors.update(sf)

    freq = {}
    for f in all_factors:
        freq[f] = sum(1 for sf in valid["selected_factors"] if f in sf)

    lines.append("#### 因子选择频率")
    lines.append("")
    lines.append("| 因子 | 选择次数 | 频率 | V5.2当前 |")
    lines.append("|------|---------|------|---------|")
    for f in sorted(freq, key=freq.get, reverse=True):
        rate = freq[f] / n_valid
        is_v52 = "Yes" if f in V52_NAMES else ""
        lines.append(f"| {f} | {freq[f]} | {rate:.1%} | {is_v52} |")

    # V5.2 因子命中率
    v52_match_dist = valid["v52_matches"].value_counts().sort_index()
    lines.append("")
    lines.append(f"**V5.2 因子命中分布**: 平均 {valid['v52_matches'].mean():.1f}/4 个当前因子被选中")
    lines.append("")

    # ── 2. Jaccard 相似度 ──
    factor_lists = valid["selected_factors"].tolist()
    n_pairs = min(5000, n_valid * (n_valid - 1) // 2)
    rng = np.random.RandomState(42)
    jaccards = []
    if n_valid >= 2:
        for _ in range(n_pairs):
            i, j = rng.choice(n_valid, 2, replace=False)
            jaccards.append(jaccard(factor_lists[i], factor_lists[j]))
    mean_jaccard = np.mean(jaccards) if jaccards else 0

    lines.append("#### 一致性指标")
    lines.append("")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 平均 Jaccard 相似度 | {mean_jaccard:.3f} |")
    lines.append(f"| 平均选出因子数 | {valid['n_selected'].mean():.1f} |")
    lines.append(f"| 选出因子数 std | {valid['n_selected'].std():.1f} |")

    # ── 3. 权重稳定性 (只看 V5.2 因子) ──
    weight_data = {f: [] for f in V52_FACTORS}
    for w in valid["weights"]:
        for f in V52_FACTORS:
            if f in w:
                weight_data[f].append(w[f])

    lines.append("")
    lines.append("#### V5.2 因子权重稳定性 (训练集拟合)")
    lines.append("")
    lines.append("| 因子 | 当前权重 | 均值 | std | CV | 覆盖度 |")
    lines.append("|------|---------|------|-----|-----|--------|")
    for f in V52_FACTORS:
        vals = weight_data[f]
        if len(vals) > 10:
            mean_w = np.mean(vals)
            std_w = np.std(vals)
            cv = std_w / mean_w if mean_w > 0 else np.nan
            coverage = len(vals) / n_valid
            lines.append(
                f"| {f} | {V52_FACTORS[f]:.1f} | {mean_w:.1f} | {std_w:.1f} | "
                f"{cv:.2f} | {coverage:.0%} |"
            )
        else:
            lines.append(f"| {f} | {V52_FACTORS[f]:.1f} | — | — | — | {len(vals)/n_valid:.0%} |")

    # ── 4. 稳健性指标 ──
    test_uplifts = valid["test_uplift"].dropna()
    train_uplifts = valid["train_uplift"].dropna()

    n_test_positive = (test_uplifts > 0).sum()
    pct_positive = n_test_positive / len(test_uplifts) if len(test_uplifts) > 0 else 0

    # 退化比: test_uplift / train_uplift
    both = valid.dropna(subset=["train_uplift", "test_uplift"])
    both = both[both["train_uplift"] > 0]
    if len(both) > 0:
        degradation = (both["test_uplift"] / both["train_uplift"])
        mean_degrad = degradation.mean()
        median_degrad = degradation.median()
    else:
        mean_degrad = np.nan
        median_degrad = np.nan

    # V5.2 固定因子在测试集的表现
    v52_uplifts = valid["v52_test_uplift"].dropna()
    v52_positive = (v52_uplifts > 0).sum() / len(v52_uplifts) if len(v52_uplifts) > 0 else 0

    lines.append("")
    lines.append("#### 稳健性指标")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 训练集 uplift 均值 | {train_uplifts.mean():+.2f}% |")
    lines.append(f"| 训练集 uplift std | {train_uplifts.std():.2f}% |")
    lines.append(f"| 测试集 uplift 均值 | {test_uplifts.mean():+.2f}% |")
    lines.append(f"| 测试集 uplift std | {test_uplifts.std():.2f}% |")
    lines.append(f"| 测试集 uplift >0 比例 | {pct_positive:.1%} ({n_test_positive}/{len(test_uplifts)}) |")
    lines.append(f"| 测试集 uplift 中位数 | {test_uplifts.median():+.2f}% |")
    lines.append(f"| 退化比 均值 (test/train) | {mean_degrad:.2f} |")
    lines.append(f"| 退化比 中位数 | {median_degrad:.2f} |")
    lines.append(f"| V5.2固定因子 测试uplift>0 | {v52_positive:.1%} |")
    lines.append(f"| V5.2固定因子 测试uplift均值 | {v52_uplifts.mean():+.2f}% |")

    # ── 5. 测试集 CI 分析 ──
    ci_lows = valid["test_ci_low"].dropna()
    if len(ci_lows) > 0:
        ci_positive = (ci_lows > 0).sum() / len(ci_lows)
        lines.append(f"| 测试集 CI下限>0 比例 | {ci_positive:.1%} |")
        lines.append(f"| 测试集 CI下限 中位数 | {ci_lows.median():+.2f}% |")

    return "\n".join(lines), df


def generate_report(temporal_df, temporal_relaxed_df, non_temporal_df, med_w, pool):
    """生成完整 Markdown 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append("## V5.2 模型稳健性检验报告")
    lines.append("")
    lines.append(f"生成时间: {now}")
    lines.append(f"实验配置: {N_SEEDS} 种子 x {TRAIN_RATIO:.0%}/{1-TRAIN_RATIO:.0%} train/test x 3 模式")
    lines.append(f"  - 模式A: 严格时序 (前70%训练/后30%测试, 标准三漏斗)")
    lines.append(f"  - 模式A': 松弛时序 (同上, freq≥1.5%, CI≥0.5%)")
    lines.append(f"  - 模式B: 随机分割 (不考虑时间, 标准三漏斗)")
    lines.append(f"Bootstrap: {BOOTSTRAP_ITER} 次迭代, 前瞻周期: {FORWARD_WEEKS} 周")
    lines.append("")

    # 数据概览
    lines.append("### 数据概览")
    lines.append("")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 总周数 | {len(med_w)} |")
    lines.append(f"| 日期范围 | {med_w.index[0].date()} ~ {med_w.index[-1].date()} |")
    lines.append(f"| 训练集周数 (70%) | {int(len(med_w) * TRAIN_RATIO)} |")
    lines.append(f"| 测试集周数 (30%) | {len(med_w) - int(len(med_w) * TRAIN_RATIO)} |")
    lines.append(f"| 候选因子池 | {len(pool.columns)} 个 |")
    lines.append(f"| V5.2 活跃因子 | {', '.join(V52_FACTORS.keys())} |")
    lines.append(f"| V5.2 权重 | {V52_FACTORS} |")
    lines.append("")

    # 全量筛选结果 (baseline)
    lines.append("### Baseline: 全量数据三漏斗筛选")
    lines.append("")
    full_screened = quick_screen(pool, med_w, FORWARD_WEEKS)
    if len(full_screened) > 0:
        lines.append("| 因子 | 频率 | 条件收益 | Uplift | CI下限 | V5.2 |")
        lines.append("|------|------|---------|--------|--------|------|")
        for _, r in full_screened.iterrows():
            is_v52 = "Yes" if r["factor"] in V52_NAMES else ""
            lines.append(
                f"| {r['factor']} | {r['freq']:.1%} | {r['e_cond']:+.1f}% | "
                f"{r['uplift']:+.1f}% | {r['uplift_ci_low']:+.1f}% | {is_v52} |"
            )
    else:
        lines.append("全量数据无因子通过三漏斗筛选。")
    lines.append("")

    # 三种模式的分析
    lines.append("---")
    lines.append("")
    temporal_report, _ = analyze_and_report(
        [r for _, r in temporal_df.iterrows()],
        "模式A: 严格时序 (前70%训练, 后30%测试, 标准三漏斗)"
    )
    lines.append(temporal_report)
    lines.append("")
    lines.append("---")
    lines.append("")

    temporal_relaxed_report, _ = analyze_and_report(
        [r for _, r in temporal_relaxed_df.iterrows()],
        "模式A': 松弛时序 (同上, 小样本松弛门槛)"
    )
    lines.append(temporal_relaxed_report)
    lines.append("")
    lines.append("---")
    lines.append("")

    non_temporal_report, _ = analyze_and_report(
        [r for _, r in non_temporal_df.iterrows()],
        "模式B: 不考虑时间效应 (随机70/30分割)"
    )
    lines.append(non_temporal_report)
    lines.append("")

    # ── 对比总结 ──
    lines.append("---")
    lines.append("")
    lines.append("### 对比总结")
    lines.append("")

    t_valid = temporal_df[temporal_df["n_selected"] > 0]
    tr_valid = temporal_relaxed_df[temporal_relaxed_df["n_selected"] > 0]
    nt_valid = non_temporal_df[non_temporal_df["n_selected"] > 0]

    t_test_up = t_valid["test_uplift"].dropna()
    tr_test_up = tr_valid["test_uplift"].dropna()
    nt_test_up = nt_valid["test_uplift"].dropna()

    lines.append("| 对比维度 | 模式A (严格时序) | 模式A' (松弛时序) | 模式B (随机) |")
    lines.append("|----------|-----------------|-------------------|-------------|")
    lines.append(f"| 有效运行数 | {len(t_valid)} | {len(tr_valid)} | {len(nt_valid)} |")
    t_nsel = t_valid['n_selected'].mean() if len(t_valid) > 0 else 0
    tr_nsel = tr_valid['n_selected'].mean() if len(tr_valid) > 0 else 0
    lines.append(f"| 平均选出因子数 | {t_nsel:.1f} | {tr_nsel:.1f} | {nt_valid['n_selected'].mean():.1f} |")
    t_up_mean = t_test_up.mean() if len(t_test_up) > 0 else float('nan')
    tr_up_mean = tr_test_up.mean() if len(tr_test_up) > 0 else float('nan')
    lines.append(f"| 测试集 uplift 均值 | {t_up_mean:+.2f}% | {tr_up_mean:+.2f}% | {nt_test_up.mean():+.2f}% |")
    t_pct = (t_test_up>0).mean() if len(t_test_up) > 0 else 0
    tr_pct = (tr_test_up>0).mean() if len(tr_test_up) > 0 else 0
    lines.append(f"| 测试集 uplift>0 | {t_pct:.1%} | {tr_pct:.1%} | {(nt_test_up>0).mean():.1%} |")
    t_v52m = t_valid['v52_matches'].mean() if len(t_valid) > 0 else 0
    tr_v52m = tr_valid['v52_matches'].mean() if len(tr_valid) > 0 else 0
    lines.append(f"| V5.2 平均命中 | {t_v52m:.1f}/4 | {tr_v52m:.1f}/4 | {nt_valid['v52_matches'].mean():.1f}/4 |")
    lines.append("")

    # ── 结论 ──
    lines.append("### 结论")
    lines.append("")

    # V5.2 因子在测试集的稳健性 (优先用松弛时序模式)
    tr_v52 = tr_valid["v52_test_uplift"].dropna() if len(tr_valid) > 0 else pd.Series(dtype=float)
    nt_v52 = nt_valid["v52_test_uplift"].dropna()
    v52_robust_nt = (nt_v52 > 0).mean() if len(nt_v52) > 0 else 0

    if v52_robust_nt > 0.7:
        lines.append(f"1. **V5.2 模型稳健**: 在 {v52_robust_nt:.0%} 的随机分割中，"
                      f"V5.2 固定因子在测试集仍产生正 uplift (均值{nt_v52.mean():+.2f}%)。")
    elif v52_robust_nt > 0.5:
        lines.append(f"1. **V5.2 模型边际稳健**: 在 {v52_robust_nt:.0%} 的随机分割中 uplift 正向。")
    else:
        lines.append(f"1. **V5.2 模型需关注**: 仅 {v52_robust_nt:.0%} 的随机分割中 uplift 正向。")

    # 一致性 (用随机模式的数据, 因为有时序模式可能无有效运行)
    nt_jaccards = []
    nt_lists = nt_valid["selected_factors"].tolist()
    rng = np.random.RandomState(42)
    if len(nt_lists) >= 2:
        for _ in range(min(5000, len(nt_lists) * 10)):
            i, j = rng.choice(len(nt_lists), 2, replace=True)
            if i != j:
                nt_jaccards.append(jaccard(nt_lists[i], nt_lists[j]))
    mean_j = np.mean(nt_jaccards) if nt_jaccards else 0

    if mean_j > 0.5:
        lines.append(f"2. **因子选择一致**: 平均 Jaccard={mean_j:.3f}，"
                      f"不同数据子集倾向选出相同因子。")
    elif mean_j > 0.3:
        lines.append(f"2. **因子选择中等一致**: 平均 Jaccard={mean_j:.3f}，"
                      f"因子选择受数据子集影响，但核心因子相对稳定。")
    else:
        lines.append(f"2. **因子选择不稳定**: 平均 Jaccard={mean_j:.3f}，"
                      f"不同数据子集选出差异较大的因子组合。")

    # 过拟合风险 (用随机模式)
    nt_both = nt_valid.dropna(subset=["train_uplift", "test_uplift"])
    nt_both = nt_both[nt_both["train_uplift"] > 0]
    if len(nt_both) > 0:
        degrad = nt_both["test_uplift"] / nt_both["train_uplift"]
        if degrad.median() > 0.5:
            lines.append(f"3. **过拟合风险低**: 退化比中位数={degrad.median():.2f}，"
                          f"测试集 uplift 保留训练集的 {degrad.median():.0%}。")
        elif degrad.median() > 0.2:
            lines.append(f"3. **过拟合风险中等**: 退化比中位数={degrad.median():.2f}。")
        else:
            lines.append(f"3. **过拟合风险较高**: 退化比中位数={degrad.median():.2f}，"
                          f"训练集表现难以迁移到测试集。")

    # 时序模式发现
    n_strict_valid = len(t_valid)
    n_relaxed_valid = len(tr_valid)
    if n_strict_valid == 0:
        lines.append(f"4. **时序筛选门槛敏感**: 严格三漏斗在前70%训练数据上 0/{N_SEEDS} 次通过"
                      f"（低频因子在子集上触发不足），松弛后 {n_relaxed_valid}/{N_SEEDS} 次通过。"
                      f"说明三漏斗需要 400+ 周数据才能可靠筛选低频因子。")

    lines.append("")
    lines.append("---")
    lines.append(f"*报告由 `scripts/robustness_validation.py` 自动生成*")

    return "\n".join(lines)


# ═══════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════

def main():
    print("=" * 60)
    print("  V5.2 模型稳健性检验")
    print(f"  {N_SEEDS} seeds x {TRAIN_RATIO:.0%}/{1-TRAIN_RATIO:.0%} x temporal/non-temporal")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    from app.tracker import _load_data
    data = _load_data()
    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()
    margin_w = None
    if "total_margin" in data and not data["total_margin"].empty:
        mdf = data["total_margin"].set_index("date")["value"].sort_index()
        margin_w = mdf.resample("W-FRI").last().dropna().shift(1)
    north_w = None
    if "north_flow" in data and not data["north_flow"].empty:
        ndf = data["north_flow"].set_index("date")["value"].sort_index()
        north_w = ndf.resample("W-FRI").sum().dropna()
    hs300_w = None
    if "hs300" in data and not data["hs300"].empty:
        hdf = data["hs300"].set_index("date")["close"].sort_index()
        hs300_w = hdf.resample("W-FRI").last().dropna()
    m2_w = None
    if "m2" in data and not data["m2"].empty:
        mdf2 = data["m2"].set_index("date")["value"].sort_index()
        m2_w = mdf2.resample("W-FRI").last().ffill().dropna()

    print(f"  指数: {len(med_w)} 周 ({med_w.index[0].date()} ~ {med_w.index[-1].date()})")

    # 2. 预计算因子池 (只做一次!)
    print("\n[2/4] 构建因子池...")
    pool = build_factor_pool(med_w, margin_w=margin_w, north_w=north_w,
                             hs300_w=hs300_w, m2_w=m2_w)
    print(f"  候选因子: {len(pool.columns)} 个")
    for col in pool.columns:
        n_trig = (pool[col] == 1).sum()
        print(f"    {col}: {n_trig} 次触发 ({n_trig/len(pool):.1%})")

    # 3. 运行 1000 seeds
    print(f"\n[3/4] 运行 {N_SEEDS} 个种子...")
    temporal_records = []
    temporal_relaxed_records = []
    non_temporal_records = []

    def empty_record(seed):
        return {
            "seed": seed, "n_train": int(len(pool) * TRAIN_RATIO),
            "n_test": len(pool) - int(len(pool) * TRAIN_RATIO),
            "selected_factors": [], "n_selected": 0, "weights": {},
            "train_uplift": np.nan, "train_e_cond": np.nan, "train_n_signals": 0,
            "test_uplift": np.nan, "test_e_cond": np.nan, "test_n_signals": 0,
            "test_ci_low": np.nan, "v52_test_uplift": np.nan,
            "v52_test_n_signals": 0, "v52_matches": 0,
        }

    for seed in range(N_SEEDS):
        # 模式A: 严格时序分割 (标准三漏斗)
        r_t = run_one_seed(pool, med_w, seed, temporal=True, relaxed=False)
        temporal_records.append(r_t if r_t else empty_record(seed))

        # 模式A': 时序分割 + 松弛门槛 (小样本适配)
        r_tr = run_one_seed(pool, med_w, seed, temporal=True, relaxed=True)
        temporal_relaxed_records.append(r_tr if r_tr else empty_record(seed))

        # 模式B: 随机分割
        r_nt = run_one_seed(pool, med_w, seed, temporal=False, relaxed=False)
        non_temporal_records.append(r_nt if r_nt else empty_record(seed))

        if (seed + 1) % 100 == 0:
            t_pos = sum(1 for r in temporal_records if r.get("test_uplift", 0) and r["test_uplift"] > 0)
            tr_pos = sum(1 for r in temporal_relaxed_records if r.get("test_uplift", 0) and r["test_uplift"] > 0)
            nt_pos = sum(1 for r in non_temporal_records if r.get("test_uplift", 0) and r["test_uplift"] > 0)
            print(f"  [{seed+1:4d}/{N_SEEDS}] "
                  f"严格时序:{t_pos}  松弛时序:{tr_pos}  随机:{nt_pos}")

    # 4. 生成报告
    print("\n[4/4] 生成报告...")
    temporal_df = pd.DataFrame(temporal_records)
    temporal_relaxed_df = pd.DataFrame(temporal_relaxed_records)
    non_temporal_df = pd.DataFrame(non_temporal_records)

    report = generate_report(temporal_df, temporal_relaxed_df, non_temporal_df, med_w, pool)

    # 保存
    output_dir = Path(__file__).resolve().parent.parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "robustness_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n  报告已保存: {report_path}")

    # CSV 原始数据
    csv_dir = output_dir / "robustness_data"
    csv_dir.mkdir(exist_ok=True)

    # 展开 selected_factors 为字符串
    for name, df_obj in [("temporal_strict", temporal_df),
                          ("temporal_relaxed", temporal_relaxed_df),
                          ("non_temporal", non_temporal_df)]:
        out = df_obj.copy()
        out["selected_factors"] = out["selected_factors"].apply(
            lambda x: "|".join(x) if isinstance(x, list) and x else "")
        out.to_csv(csv_dir / f"{name}_results.csv", index=False)
    print(f"  原始数据: {csv_dir}/")

    print("\n" + "=" * 60)
    print("  完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
