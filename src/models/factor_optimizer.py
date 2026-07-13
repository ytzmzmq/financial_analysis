"""
V5.0 因子自动筛选与赋权框架

五阶段:
  1. 候选因子池 (Valuation/Liquidity/Momentum/SmartMoney/External, 二值化, 无look-ahead)
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
# 健康监测层 — 行动建议映射
# ═══════════════════════════════════════════

HEALTH_ACTIONS = {
    "Stable":             "保持当前权重",
    "Regime-dependent":   "继续观察，不调整权重",
    "Declining":          "重点监测，下次审计复查",
    "Unstable":           "进入 V5.3 候选淘汰列表",
    "Insufficient":       "数据不足，暂不评估",
}


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


def temporal_stability(factor: pd.Series, med_w: pd.Series,
                       forward_weeks: int = 13,
                       n_windows: int = 4,
                       overlap: float = 0.5,
                       min_signals_per_window: int = 3) -> dict:
    """滚动窗口 uplift 计算（纯计算，不含 Grade 判定）。

    将全历史切成 n_windows 个重叠窗口，每个窗口独立计算 uplift 和触发数。
    返回原始窗口数据，由 factor_health_analysis() 做 evidence-based 综合评估。

    Returns:
        dict with window_uplifts, n_pass, pass_ratio,
        total_triggers, trigger_cv, window_details
    """
    n_total = len(factor)
    total_triggers = int((factor == 1).sum())
    effective_cover = (n_windows - 1) * (1 - overlap) + 1
    window_size = max(int(n_total / effective_cover),
                      forward_weeks + min_signals_per_window + 10)
    stride = max(int(window_size * (1 - overlap)), 1)

    window_uplifts = []
    window_details = []

    for i in range(n_windows):
        start = i * stride
        end = min(start + window_size, n_total)
        if end - start < forward_weeks + min_signals_per_window:
            break

        w_rets = np.array([
            (med_w.iloc[j + forward_weeks] / med_w.iloc[j] - 1) * 100
            for j in range(start, end - forward_weeks)
        ])
        if len(w_rets) == 0:
            continue
        e_uncond_w = np.mean(w_rets)

        triggered_rets = []
        for j in range(start, end - forward_weeks):
            if factor.iloc[j] == 1:
                triggered_rets.append(
                    (med_w.iloc[j + forward_weeks] / med_w.iloc[j] - 1) * 100
                )

        n_trig = len(triggered_rets)
        if n_trig >= min_signals_per_window:
            e_cond_w = np.mean(triggered_rets)
            uplift_w = e_cond_w - e_uncond_w
        else:
            uplift_w = np.nan

        window_uplifts.append(uplift_w)
        window_details.append({
            "window": i,
            "start_idx": start,
            "end_idx": end,
            "n_signals": n_trig,
            "uplift": uplift_w,
        })

    valid_uplifts = [u for u in window_uplifts if not np.isnan(u)]
    n_pass = sum(1 for u in valid_uplifts if u > 0)
    pass_ratio = n_pass / len(valid_uplifts) if len(valid_uplifts) > 0 else 0

    trigger_counts = np.array([d["n_signals"] for d in window_details])
    if len(trigger_counts) > 1 and np.mean(trigger_counts) > 0:
        trigger_cv = float(np.std(trigger_counts) / np.mean(trigger_counts))
    else:
        trigger_cv = 0.0

    return {
        "window_uplifts": window_uplifts,
        "n_pass": n_pass,
        "n_total_windows": len(valid_uplifts),
        "pass_ratio": pass_ratio,
        "total_triggers": total_triggers,
        "trigger_cv": trigger_cv,
        "window_details": window_details,
    }


def factor_health_analysis(factor: pd.Series, med_w: pd.Series,
                            forward_weeks: int = 13,
                            cond_ret_full: float = None,
                            cond_ret_recent: float = None,
                            freq_all: float = None,
                            freq_recent: float = None) -> dict:
    """Evidence-based 因子健康评估。

    收集多维 evidence，综合给出 Grade + Confidence + Action。
    扩展时只需在 evidence 列表中添加新维度，Grade 合成逻辑统一处理。

    Evidence 来源:
        - rolling_window: 4窗口 uplift 通过率 (来自 temporal_stability)
        - trigger_cv:     触发集中度 (CV > 0.8 = 高集中)
        - a1_drift:       近3年 vs 全历史条件收益漂移
        - freq_drift:     近半年 vs 全历史触发频率漂移
        - uplift_decay:   窗口间 uplift 衰减趋势

    Returns:
        dict with grade, confidence, action, evidence(dict), reasons(list)
    """
    # ── 1. 基础窗口计算 ──
    stab = temporal_stability(factor, med_w, forward_weeks)
    total_triggers = stab["total_triggers"]
    low_freq = total_triggers <= 15
    trigger_cv = stab["trigger_cv"]
    n_valid = stab["n_total_windows"]
    pass_ratio = stab["pass_ratio"]
    valid_uplifts = [u for u in stab["window_uplifts"] if not np.isnan(u)]

    # ── 2. Evidence 收集 ──
    evidence = {
        "rolling_window": {
            "pass_ratio": pass_ratio,
            "n_valid": n_valid,
            "n_pass": stab["n_pass"],
            "window_uplifts": stab["window_uplifts"],
        },
        "trigger_cv": {
            "value": trigger_cv,
            "high": trigger_cv > 0.8,
        },
        "total_triggers": total_triggers,
        "low_freq": low_freq,
    }

    # A1 drift (if provided by caller)
    if cond_ret_full is not None and cond_ret_recent is not None:
        drift_pct = (abs(cond_ret_recent - cond_ret_full)
                     / max(abs(cond_ret_full), 1))
        evidence["a1_drift"] = {
            "full": cond_ret_full,
            "recent": cond_ret_recent,
            "drift_pct": drift_pct,
            "flagged": drift_pct > 0.5,
        }

    # Frequency drift (if provided)
    if freq_all is not None and freq_recent is not None:
        if freq_all > 0:
            freq_dev = abs(freq_recent - freq_all) / max(freq_all, 0.001)
        else:
            freq_dev = 0
        evidence["freq_drift"] = {
            "all": freq_all,
            "recent": freq_recent,
            "deviation": freq_dev,
            "flagged": freq_dev > 0.5,
        }

    # Uplift decay
    decay_ratio = None
    if len(valid_uplifts) >= 2:
        half = max(1, len(valid_uplifts) // 2)
        first_half = np.mean(valid_uplifts[:half])
        second_half = np.mean(valid_uplifts[half:]) if len(valid_uplifts) > half else valid_uplifts[-1]
        if first_half > 0:
            decay_ratio = second_half / first_half
    evidence["uplift_decay"] = {
        "ratio": decay_ratio,
        "flagged": decay_ratio is not None and decay_ratio < 0.4,
    }

    # ── 3. Grade 合成（从 evidence 推导，非硬编码阈值）──
    reasons = []

    if n_valid == 0:
        grade = "Insufficient"
        reasons.append("无有效窗口可评估")

    elif pass_ratio >= 0.75:
        grade = "Stable"

        # Regime-dependent: 高CV + 有效窗口少 + 非低频
        if (not low_freq and trigger_cv > 0.8
                and n_valid <= 2 and n_valid < 3):
            grade = "Regime-dependent"
            reasons.append(f"触发高度集中(CV={trigger_cv:.2f})，仅{n_valid}个窗口有足够触发")

        # Declining: uplift 衰减
        if grade == "Stable" and evidence["uplift_decay"]["flagged"]:
            grade = "Declining"
            reasons.append(f"uplift 跨窗口衰减(比率={decay_ratio:.2f})")

        # A1 drift 交叉验证
        if grade == "Stable" and evidence.get("a1_drift", {}).get("flagged"):
            if grade == "Stable":
                reasons.append("A1 近3年条件收益漂移>50%，交叉验证需关注")

        if not reasons:
            reasons.append(f"{stab['n_pass']}/{n_valid}窗口uplift正向，分布均匀")

    elif trigger_cv > 0.8 and stab["n_pass"] > 0:
        grade = "Regime-dependent"
        reasons.append(f"触发集中在特定市场阶段(CV={trigger_cv:.2f})，触发时uplift正向")

    elif stab["n_pass"] == 0:
        grade = "Unstable"
        reasons.append("所有有效窗口uplift均非正向")

    else:
        if n_valid >= 3:
            recent = valid_uplifts[-1]
            early = np.mean(valid_uplifts[:max(1, n_valid // 2)])
            if early > 1.0 and recent < 0:
                grade = "Declining"
                reasons.append("后期窗口uplift转负")
            else:
                grade = "Regime-dependent"
                reasons.append("部分窗口正向但不稳定")
        else:
            grade = "Unstable"
            reasons.append("有效窗口不足且uplift不一致")

    # 低频标注
    if low_freq:
        reasons.insert(0, f"低频因子({total_triggers}次触发)，统计效力有限")

    # ── 4. Confidence 评估 ──
    evidence_count = sum([
        n_valid >= 3,                          # 足够窗口
        total_triggers >= 15,                  # 足够触发
        evidence.get("a1_drift") is not None,  # 有A1数据
        evidence.get("freq_drift") is not None, # 有频率漂移数据
    ])

    if grade == "Stable":
        confidence = "High" if n_valid >= 3 and total_triggers >= 15 else "Medium"
    elif grade == "Declining":
        if n_valid >= 3 and decay_ratio is not None and decay_ratio < 0.2:
            confidence = "High"
        else:
            confidence = "Low"
    elif grade == "Regime-dependent":
        confidence = "Medium" if total_triggers >= 10 else "Low"
    elif grade == "Unstable":
        confidence = "High" if n_valid >= 3 and pass_ratio == 0 else "Medium"
    else:
        confidence = "Low"

    if low_freq and confidence != "Low":
        confidence = "Low"

    # 低频时 Stable 不加置信度降级（数据少但方向一致也是有效信息）
    if low_freq and grade.startswith("Stable"):
        confidence = "Medium"

    # ── 5. Action ──
    base_grade = grade.split("(")[0].strip()  # 去掉 "(低频)" 标注
    action = HEALTH_ACTIONS.get(base_grade, "待评估")

    return {
        "grade": grade,
        "confidence": confidence,
        "action": action,
        "evidence": evidence,
        "reasons": reasons,
        "total_triggers": total_triggers,
        "trigger_cv": trigger_cv,
        "window_uplifts": stab["window_uplifts"],
        "n_pass": stab["n_pass"],
        "n_total_windows": n_valid,
        "pass_ratio": pass_ratio,
        "low_freq": low_freq,
        "window_details": stab["window_details"],
    }


def version_recommendation(health_results: dict) -> dict:
    """模型版本决策 — 从因子监测到版本治理的闭环。

    Args:
        health_results: {factor_name: factor_health_analysis() result}

    Returns:
        dict with recommendation, reason, evidence, action
    """
    grades = [r["grade"].split("(")[0].strip() for r in health_results.values()]
    n_total = len(grades)
    n_stable = grades.count("Stable")
    n_regime = grades.count("Regime-dependent")
    n_declining = grades.count("Declining")
    n_unstable = grades.count("Unstable")
    n_insufficient = grades.count("Insufficient")

    declining_factors = [
        name for name, r in health_results.items()
        if "Declining" in r["grade"]
    ]
    unstable_factors = [
        name for name, r in health_results.items()
        if "Unstable" in r["grade"]
    ]

    # 决策逻辑
    if n_unstable > 0:
        recommendation = "Recommend V5.3 Review"
        reason = (f"{n_unstable} 个因子 Unstable "
                  f"({', '.join(unstable_factors)})")
        action = "启动 V5.3 评估：审查不稳定因子，考虑替换或淘汰"
    elif n_declining >= 2:
        recommendation = "Recommend V5.3 Review"
        reason = f"{n_declining} 个因子 Declining"
        action = "启动 V5.3 评估：多个因子同时衰减，需寻找替代因子"
    elif n_declining == 1:
        recommendation = "Keep Current — 重点观察"
        reason = (f"1 个因子 Declining ({declining_factors[0]})，"
                  f"证据尚不充分，需连续 2 次审计确认")
        action = f"下次审计重点复查 {declining_factors[0]}，若持续 Declining 则启动 V5.3"
    else:
        recommendation = "Keep Current"
        reason = f"{n_stable} Stable, {n_regime} Regime-dependent，整体健康"
        action = "维持当前模型配置，按计划季度审计"

    return {
        "recommendation": recommendation,
        "reason": reason,
        "action": action,
        "summary": {
            "total": n_total,
            "stable": n_stable,
            "regime_dependent": n_regime,
            "declining": n_declining,
            "unstable": n_unstable,
            "insufficient": n_insufficient,
        },
    }


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
                       m2_w: pd.Series = None,
                       forward_weeks: int = 13) -> dict:
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
    print("\n[阶段2] 单因子三漏斗检验 (稀疏度→收益→CI)...")
    screened = screen_factors(pool, med_w)
    print(f"  通过筛选: {len(screened)}/{len(pool.columns)}")
    if len(screened) == 0:
        print("  ⚠ 无因子通过筛选!")
        return {}
    for _, r in screened.iterrows():
        print(f"    {r['factor']:20s} | freq={r['freq']:.1%} | E={r['e_cond']:+.1f}% | Uplift={r['uplift']:+.1f}% | CI=[{r['uplift_ci_low']:+.1f}%,{r['uplift_ci_high']:+.1f}%]")

    # 健康监测层: evidence-based 因子健康评估
    print("\n[监测层] Evidence-based 因子健康评估...")
    health_results = {}
    for _, r in screened.iterrows():
        f = r["factor"]
        health = factor_health_analysis(pool[f], med_w, forward_weeks)
        health_results[f] = health
        conf_tag = f" [{health['confidence']}]" if health['confidence'] != "High" else ""
        print(f"    {f:20s} | Grade={health['grade']:20s} | Conf={health['confidence']:6s} | Action={health['action']}")

    # 版本决策
    ver_rec = version_recommendation(health_results)
    print(f"\n[版本决策] {ver_rec['recommendation']}: {ver_rec['reason']}")

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
        "health_results": health_results,
        "version_recommendation": ver_rec,
    }
