"""
月度因子审计 — 稳健性检验 + 新因子发现

用法:
    python app/monthly_audit.py              # 生成审计报告
    python app/monthly_audit.py --output /path/to/report.md  # 指定输出路径

审计内容:
  Part A — 当前模型因子稳健性检验
    A1. 滚动窗口稳定性: 近3年 vs 全历史, 比较因子条件收益和触发频率
    A2. 触发频率漂移: 近半年触发率 vs 全历史, 偏差>50%告警
    A3a. 真实信号复盘: 从 SQLite 取 is_live_signal=1 的历史信号
    A3b. 模型回算: 用当前模型对全历史做 retrospective replay
    A4. 因子间相关性 / 多重共线性检查
    A5. 组合表现表: 按 signal_tier 分组的条件收益

  Part B — 新因子发现
    1. 运行五阶段因子优化全流程
    2. 对比当前模型配置, 标注新通过 / 不再通过的因子
    3. 给出候选评分卡建议

输出: data/processed/audit_report.md + system_log
"""
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.models.rule_registry import (
    MODEL_CONFIGS, ACTIVE_MODEL_VERSION, RULE_DEFS,
    evaluate_signal_history,
)
from app.db import get_live_signals


def _load_data():
    """拉取所有可用数据（价格 + 融资 + 成交量 + 外部因子）"""
    from src.data_fetcher.akshare_source import AKShareSource
    ak = AKShareSource()
    med_df = ak.fetch_sw_medical("20180101")
    margin_df = ak.fetch_margin_data("20180101")
    north_df = ak.fetch_north_flow("20180101")
    hs300_df = ak.fetch_market_index("hs300", "20180101")
    m2_df = ak.fetch_m2("20180101")

    med = med_df.set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    margin_w = None
    if margin_df is not None and not margin_df.empty:
        mdf = margin_df.set_index("date")["value"].sort_index()
        margin_w = mdf.resample("W-FRI").last().dropna().shift(1)

    # 成交量（L4 地量冰点因子需要）
    vol_w = None
    if "volume" in med_df.columns:
        vdf = med_df.set_index("date")["volume"].sort_index()
        vol_w = vdf.resample("W-FRI").sum().dropna()

    # 外部因子数据
    north_w = None
    if north_df is not None and not north_df.empty:
        ndf = north_df.set_index("date")["value"].sort_index()
        north_w = ndf.resample("W-FRI").sum().dropna()

    hs300_w = None
    if hs300_df is not None and not hs300_df.empty:
        hdf = hs300_df.set_index("date")["close"].sort_index()
        hs300_w = hdf.resample("W-FRI").last().dropna()

    m2_w = None
    if m2_df is not None and not m2_df.empty:
        mdf2 = m2_df.set_index("date")["value"].sort_index()
        m2_w = mdf2.resample("W-FRI").last().ffill().dropna()

    return med_w, margin_w, vol_w, north_w, hs300_w, m2_w


# ═══════════════════════════════════════════
# Part A: 稳健性检验
# ═══════════════════════════════════════════

def _check_rolling_stability(med_w, margin_w, vol_w=None,
                             north_w=None, hs300_w=None, m2_w=None):
    """对比近3年 vs 全历史的因子条件收益"""
    from src.models.factor_optimizer import build_factor_pool

    config = MODEL_CONFIGS[ACTIVE_MODEL_VERSION]
    factor_names = list(config["factors"].keys())

    pool_full = build_factor_pool(med_w, vol_w=vol_w, margin_w=margin_w,
                                  north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)
    fwd_ret = med_w.pct_change(13).shift(-13) * 100

    cutoff = med_w.index[-1] - pd.DateOffset(years=3)
    mask_recent = med_w.index >= cutoff

    pool_recent = pool_full.loc[mask_recent]
    fwd_recent = fwd_ret.loc[mask_recent]

    rows = []
    for factor in factor_names:
        if factor not in pool_full.columns:
            rows.append({"因子": factor, "全历史触发数": 0, "全历史条件收益": "N/A",
                         "近3年触发数": 0, "近3年条件收益": "N/A", "稳定性": "无数据"})
            continue

        n_full = int(pool_full[factor].sum())
        cond_full = fwd_ret[pool_full[factor] == 1].mean() if n_full > 0 else float("nan")

        n_recent = int(pool_recent[factor].sum())
        cond_recent = fwd_recent[pool_recent[factor] == 1].mean() if n_recent > 0 else float("nan")

        if np.isnan(cond_full) or np.isnan(cond_recent):
            stability = "数据不足"
        elif abs(cond_recent - cond_full) / max(abs(cond_full), 1) > 0.5:
            stability = "漂移 >50%"
        else:
            stability = "稳定"

        rows.append({
            "因子": factor,
            "全历史触发数": n_full,
            "全历史条件收益": f"{cond_full:.1f}%" if not np.isnan(cond_full) else "N/A",
            "近3年触发数": n_recent,
            "近3年条件收益": f"{cond_recent:.1f}%" if not np.isnan(cond_recent) else "N/A",
            "稳定性": stability,
        })

    return pd.DataFrame(rows)


def _check_frequency_drift(pool):
    """检查因子触发频率是否漂移"""
    config = MODEL_CONFIGS[ACTIVE_MODEL_VERSION]
    factor_names = list(config["factors"].keys())
    cutoff_6m = pool.index[-1] - pd.DateOffset(weeks=26)

    rows = []
    for factor in factor_names:
        if factor not in pool.columns:
            continue
        freq_all = pool[factor].mean() * 100
        freq_6m = pool.loc[pool.index >= cutoff_6m, factor].mean() * 100

        if freq_all < 0.5:
            drift = "基频过低"
        elif abs(freq_6m - freq_all) / max(freq_all, 0.1) > 0.5:
            drift = f"偏离 {((freq_6m - freq_all) / freq_all * 100):.0f}%"
        else:
            drift = "正常"

        rows.append({
            "因子": factor,
            "全历史触发率": f"{freq_all:.1f}%",
            "近半年触发率": f"{freq_6m:.1f}%",
            "判断": drift,
        })

    return pd.DataFrame(rows)


def _signal_quality_live(med_w):
    """A3a: 从 SQLite 取真实 live 信号，计算13周前瞻收益

    这些是 tracker.py 实际运行时写入的信号，非回算。
    """
    live_rows = get_live_signals(limit=200)
    if not live_rows:
        return pd.DataFrame(columns=["日期", "Score", "价格", "Tier", "13周后收益", "结果"])

    records = []
    for r in live_rows:
        date_str = r["date"]
        try:
            dt = pd.Timestamp(date_str)
        except Exception:
            continue
        # 在 med_w 中找到最近的周五
        if dt not in med_w.index:
            dt = med_w.index[med_w.index.searchsorted(dt)]
        if dt > med_w.index[-1]:
            continue
        fwd_idx = med_w.index.searchsorted(dt)
        if fwd_idx + 13 >= len(med_w):
            fwd_ret = float("nan")  # 尾部未验证
        else:
            price_now = med_w.iloc[fwd_idx]
            price_fwd = med_w.iloc[fwd_idx + 13]
            fwd_ret = (price_fwd / price_now - 1) * 100

        records.append({
            "日期": date_str,
            "Score": round(float(r["score"] or 0), 1),
            "价格": round(float(r["price"] or 0), 0),
            "Tier": r.get("signal_tier") or "",
            "13周后收益": round(fwd_ret, 1) if not np.isnan(fwd_ret) else None,
            "结果": "盈利" if not np.isnan(fwd_ret) and fwd_ret > 0
                    else ("亏损" if not np.isnan(fwd_ret) else "待验证"),
            "model_version": r.get("model_version") or "",
        })

    return pd.DataFrame(records)


def _signal_quality_replay(med_w, margin_w, vol_w=None,
                           north_w=None, hs300_w=None, m2_w=None):
    """A3b: 用当前模型对全历史做 retrospective replay

    回答: "如果从头到尾用当前模型，历史上 Armed 信号表现如何？"
    """
    df = evaluate_signal_history(ACTIVE_MODEL_VERSION, med_w,
                                  margin_w=margin_w, vol_w=vol_w,
                                  north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)
    fwd = med_w.pct_change(13).shift(-13) * 100

    armed_df = df[df["armed"] == 1].copy()
    if len(armed_df) == 0:
        return pd.DataFrame(columns=["日期", "Score", "价格", "Tier", "13周后收益", "结果"])

    # 去重: 连续 Armed 只保留第一周（避免统计放大）
    armed_df["prev_armed"] = armed_df["armed"].shift(1)
    first_signals = armed_df[armed_df["prev_armed"] != 1].copy()

    first_signals["fwd_13w"] = fwd.reindex(first_signals.index)
    first_signals["result"] = first_signals["fwd_13w"].apply(
        lambda x: "盈利" if pd.notna(x) and x > 0
        else ("亏损" if pd.notna(x) else "待验证"))

    out = first_signals[["price", "score", "signal_tier", "fwd_13w"]].reset_index()
    out = out.rename(columns={
        "date": "日期", "price": "价格", "score": "Score",
        "signal_tier": "Tier", "fwd_13w": "13周后收益",
    })
    out["Score"] = out["Score"].round(1)
    out["价格"] = out["价格"].round(0)
    out["13周后收益"] = out["13周后收益"].round(1)
    out["结果"] = first_signals["result"].values

    # 统计摘要
    verified = first_signals["fwd_13w"].dropna()
    n_verified = len(verified)
    n_total = len(first_signals)
    win_rate = (verified > 0).mean() * 100 if n_verified > 0 else 0
    avg_ret = verified.mean() if n_verified > 0 else float("nan")

    summary = {
        "n_total": n_total,
        "n_verified": n_verified,
        "n_pending": n_total - n_verified,
        "win_rate": f"{win_rate:.0f}%",
        "avg_return": f"{avg_ret:.1f}%" if not np.isnan(avg_ret) else "N/A",
    }

    return out, summary


def _check_correlation(med_w, margin_w, vol_w=None,
                       north_w=None, hs300_w=None, m2_w=None):
    """因子间相关性分析 — 检查多重共线性风险

    两个层面:
    1. 全因子池的条件概率矩阵（P(A|B)），>0.5 的对标红
    2. 当前三因子(M1/S3/V1)的连续变量相关性
       （偏度值、融资变化、价格分位，而非二值触发）
    """
    from src.models.factor_optimizer import build_factor_pool

    pool = build_factor_pool(med_w, vol_w=vol_w, margin_w=margin_w,
                             north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)
    factors = pool.columns.tolist()

    # ── 1. 条件概率矩阵 ──
    n = len(factors)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = factors[i], factors[j]
            na = int((pool[a] == 1).sum())
            nb = int((pool[b] == 1).sum())
            if na == 0 or nb == 0:
                continue
            p_a_given_b = pool.loc[pool[b] == 1, a].mean()
            p_b_given_a = pool.loc[pool[a] == 1, b].mean()
            max_p = max(p_a_given_b, p_b_given_a)
            if max_p >= 0.30:  # 只展示 >=30% 的对
                pairs.append({
                    "因子A": a, "因子B": b,
                    "P(A|B)": f"{p_a_given_b:.1%}",
                    "P(B|A)": f"{p_b_given_a:.1%}",
                    "max": f"{max_p:.1%}",
                    "风险": "高" if max_p >= 0.5 else ("中" if max_p >= 0.35 else "低"),
                })

    pairs_df = pd.DataFrame(pairs).sort_values("max", ascending=False) if pairs else pd.DataFrame()

    # ── 2. 当前三因子的连续变量相关性 ──
    skew = med_w.pct_change().rolling(13).skew()
    val_pct = med_w.rolling(260, min_periods=52).rank(pct=True) * 100

    margin_chg = pd.Series(np.nan, index=med_w.index)
    if margin_w is not None:
        margin_aligned = margin_w.reindex(med_w.index).ffill()
        margin_chg = margin_aligned.pct_change(4) * 100

    cont_df = pd.DataFrame({
        "M1_偏度": skew,
        "V1_价格分位": val_pct,
        "S3_融资变化%": margin_chg,
    }).dropna()

    cont_corr = cont_df.corr() if len(cont_df) > 10 else pd.DataFrame()

    return pairs_df, cont_corr


# ═══════════════════════════════════════════
# Part B: 新因子发现
# ═══════════════════════════════════════════

def _run_factor_discovery(med_w, margin_w, vol_w=None,
                          north_w=None, hs300_w=None, m2_w=None):
    """运行全因子优化流水线，对比当前模型"""
    from src.models.factor_optimizer import run_full_pipeline

    config = MODEL_CONFIGS[ACTIVE_MODEL_VERSION]
    current_factors = list(config["factors"].keys())

    results = run_full_pipeline(med_w, vol_w=vol_w, margin_w=margin_w,
                                north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)

    if not results:
        return {"status": "无因子通过筛选", "screened": None, "scoring": None, "final_factors": []}

    screened = results.get("screened", pd.DataFrame())
    final_factors = results.get("final_factors", [])
    scoring = results.get("scoring", pd.DataFrame())
    threshold_df = results.get("threshold_analysis", pd.DataFrame())

    new_factors = [f for f in final_factors if f not in current_factors]
    dropped = [f for f in current_factors if f not in final_factors]

    return {
        "status": "完成",
        "screened": screened,
        "scoring": scoring,
        "final_factors": final_factors,
        "new_factors": new_factors,
        "dropped_factors": dropped,
        "threshold_analysis": threshold_df,
    }


def _combination_performance(med_w, margin_w, vol_w=None,
                             north_w=None, hs300_w=None, m2_w=None):
    """A5: 按 signal_tier 分组的组合表现表

    对全历史做 evaluate_signal_history，按 tier 统计：
    - 触发周数（去重后机会数）
    - 13周前瞻收益均值/中位数
    - 胜率
    """
    df = evaluate_signal_history(ACTIVE_MODEL_VERSION, med_w,
                                  margin_w=margin_w, vol_w=vol_w,
                                  north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)
    fwd = med_w.pct_change(13).shift(-13) * 100

    # 去重: 同一 tier 连续触发只保留第一周
    df["_prev_tier"] = df["signal_tier"].shift(1)
    first_occ = df[df["signal_tier"] != df["_prev_tier"]].copy()

    # 排除 hold（无信号）
    armed_occ = first_occ[first_occ["signal_tier"] != "hold"].copy()
    armed_occ["fwd_13w"] = fwd.reindex(armed_occ.index)

    if len(armed_occ) == 0:
        return pd.DataFrame()

    tiers = ["strong_armed", "standard_armed", "weak_armed"]
    rows = []
    for tier in tiers:
        subset = armed_occ[armed_occ["signal_tier"] == tier]
        if len(subset) == 0:
            rows.append({"Tier": tier, "机会数": 0, "已验证": 0,
                         "胜率": "N/A", "平均收益": "N/A", "中位收益": "N/A"})
            continue
        verified = subset["fwd_13w"].dropna()
        n_v = len(verified)
        win = (verified > 0).sum()
        rows.append({
            "Tier": tier,
            "机会数": len(subset),
            "已验证": n_v,
            "胜率": f"{win/n_v*100:.0f}%" if n_v > 0 else "N/A",
            "平均收益": f"{verified.mean():.1f}%" if n_v > 0 else "N/A",
            "中位收益": f"{verified.median():.1f}%" if n_v > 0 else "N/A",
        })

    # 基线: 全市场无条件持有13周
    all_fwd = fwd.dropna()
    rows.append({
        "Tier": "基线(全市场)",
        "机会数": len(all_fwd),
        "已验证": len(all_fwd),
        "胜率": f"{(all_fwd > 0).mean()*100:.0f}%",
        "平均收益": f"{all_fwd.mean():.1f}%",
        "中位收益": f"{all_fwd.median():.1f}%",
    })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════

def _df_to_md(df, max_rows=20):
    """DataFrame 转 markdown 表格"""
    if df is None or len(df) == 0:
        return "（无数据）\n"
    return df.head(max_rows).to_markdown(index=False) + "\n"


def generate_report(med_w, margin_w, vol_w=None,
                    north_w=None, hs300_w=None, m2_w=None):
    """执行全部审计项目，返回 markdown 报告"""
    config = MODEL_CONFIGS[ACTIVE_MODEL_VERSION]
    factor_names = list(config["factors"].keys())
    factors_str = ", ".join(f"{k}={v}" for k, v in config["factors"].items())
    armed_rule = config.get("armed_rule", "")
    max_score = config.get("max_score", "")

    vol_note = "含成交量(L4)" if vol_w is not None else "无成交量数据(L4不可用)"
    lines = [
        f"# 月度因子审计报告",
        f"",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"数据范围: {med_w.index[0].date()} ~ {med_w.index[-1].date()} ({len(med_w)} 周), {vol_note}  ",
        f"当前模型: **{ACTIVE_MODEL_VERSION}** | 因子: {factors_str} | 满分: {max_score} | Armed规则: {armed_rule}",
        f"",
        f"---",
        f"",
        f"## Part A: 当前因子稳健性检验",
        f"",
    ]

    # A1: 滚动窗口稳定性
    print("  [A1] 滚动窗口稳定性检验...")
    try:
        stability_df = _check_rolling_stability(med_w, margin_w, vol_w,
                                                 north_w, hs300_w, m2_w)
        lines.append("### A1. 滚动窗口稳定性 (近3年 vs 全历史)\n")
        lines.append(_df_to_md(stability_df))
    except Exception as e:
        lines.append(f"### A1. 滚动窗口稳定性\n\n**执行失败**: {e}\n")

    # A2: 触发频率漂移
    print("  [A2] 触发频率漂移检验...")
    try:
        from src.models.factor_optimizer import build_factor_pool
        pool = build_factor_pool(med_w, vol_w=vol_w, margin_w=margin_w,
                                   north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)
        freq_df = _check_frequency_drift(pool)
        lines.append("### A2. 触发频率漂移\n")
        lines.append(_df_to_md(freq_df))
    except Exception as e:
        lines.append(f"### A2. 触发频率漂移\n\n**执行失败**: {e}\n")

    # A3a: 真实信号复盘（live from SQLite）
    print("  [A3a] 真实信号复盘...")
    try:
        live_df = _signal_quality_live(med_w)
        lines.append("### A3a. 真实信号复盘 (SQLite live signals)\n")
        if len(live_df) == 0:
            lines.append("暂无 live 信号记录（tracker.py 尚未运行或数据库为空）。\n")
        else:
            lines.append(f"共 {len(live_df)} 条 live 信号:\n")
            lines.append(_df_to_md(live_df))
    except Exception as e:
        lines.append(f"### A3a. 真实信号复盘\n\n**执行失败**: {e}\n")

    # A3b: 模型回算（retrospective replay）
    print("  [A3b] 模型回算 (retrospective replay)...")
    try:
        replay_result = _signal_quality_replay(med_w, margin_w, vol_w,
                                                north_w, hs300_w, m2_w)
        if isinstance(replay_result, tuple):
            replay_df, replay_summary = replay_result
            lines.append(f"### A3b. 模型回算 ({ACTIVE_MODEL_VERSION} retrospective)\n")
            lines.append(f"去重后机会数: {replay_summary['n_total']} | "
                         f"已验证: {replay_summary['n_verified']} | "
                         f"待验证: {replay_summary['n_pending']} | "
                         f"胜率: {replay_summary['win_rate']} | "
                         f"平均收益: {replay_summary['avg_return']}\n")
            lines.append(_df_to_md(replay_df))
        else:
            lines.append("### A3b. 模型回算\n")
            lines.append(_df_to_md(replay_df))
    except Exception as e:
        lines.append(f"### A3b. 模型回算\n\n**执行失败**: {e}\n")

    # A4: 因子相关性 / 多重共线性
    print("  [A4] 因子相关性分析...")
    try:
        pairs_df, cont_corr = _check_correlation(med_w, margin_w, vol_w,
                                                   north_w, hs300_w, m2_w)
        lines.append("### A4. 因子间相关性 (多重共线性检查)\n")
        lines.append("去重机制: 条件概率 P(A|B) > 0.65 时淘汰 Uplift 更低的因子 (阶段3)。\n")
        if len(pairs_df) > 0:
            lines.append("**条件概率 >=30% 的因子对:**\n")
            lines.append(_df_to_md(pairs_df))
            high_risk = pairs_df[pairs_df["风险"] == "高"]
            if len(high_risk) > 0:
                lines.append(f"**注意**: 有 {len(high_risk)} 对因子共触发率 >=50%，"
                             f"虽已通过去重阈值(65%)，但需关注是否实质冗余。\n")
        else:
            lines.append("所有因子对的条件概率均 <30%，无共线性风险。\n")

        if len(cont_corr) > 0:
            lines.append("**当前因子连续变量相关系数:**\n")
            lines.append("```\n")
            lines.append(cont_corr.round(3).to_string() + "\n")
            lines.append("```\n")
            off_diag = cont_corr.where(~np.eye(len(cont_corr), dtype=bool))
            high_corr = off_diag.abs().max().max()
            if high_corr > 0.5:
                lines.append(f"**注意**: 连续变量最大相关系数 {high_corr:.2f}，存在中等以上线性相关。\n")
            else:
                lines.append(f"连续变量最大相关系数 {high_corr:.2f}，因子独立性良好。\n")
    except Exception as e:
        lines.append(f"### A4. 因子相关性\n\n**执行失败**: {e}\n")

    # A5: 组合表现表
    print("  [A5] 组合表现表...")
    try:
        combo_df = _combination_performance(med_w, margin_w, vol_w,
                                             north_w, hs300_w, m2_w)
        lines.append("### A5. 组合表现 (按 signal_tier 分组, 去重机会级)\n")
        if len(combo_df) > 0:
            lines.append(_df_to_md(combo_df))
        else:
            lines.append("无 armed 信号，组合表现表为空。\n")
    except Exception as e:
        lines.append(f"### A5. 组合表现\n\n**执行失败**: {e}\n")

    # Part B: 新因子发现
    lines.append(f"---\n")
    lines.append(f"## Part B: 新因子发现\n")

    print("  [B] 运行全因子优化流水线...")
    try:
        discovery = _run_factor_discovery(med_w, margin_w, vol_w,
                                           north_w, hs300_w, m2_w)

        if discovery["status"] != "完成":
            lines.append(f"**{discovery['status']}**\n")
        else:
            new = discovery["new_factors"]
            dropped = discovery["dropped_factors"]

            if new:
                lines.append(f"**新通过筛选的因子**: {', '.join(new)}\n")
            else:
                lines.append("无新因子通过筛选。\n")

            if dropped:
                lines.append(f"**当前因子未通过重新筛选**: {', '.join(dropped)}\n")

            if discovery["scoring"] is not None and len(discovery["scoring"]) > 0:
                lines.append("### 候选评分卡\n")
                lines.append(_df_to_md(discovery["scoring"]))

            if discovery["threshold_analysis"] is not None and len(discovery["threshold_analysis"]) > 0:
                lines.append("### 阈值分析\n")
                lines.append(_df_to_md(discovery["threshold_analysis"]))

            # 给出建议
            lines.append("### 审计建议\n")
            if new or dropped:
                lines.append(f"**建议更新模型**: 因子组成发生变化，"
                             f"请审核候选评分卡后更新 `rule_registry.py` 中的 `MODEL_CONFIGS`。\n")
            else:
                lines.append("**当前模型无需调整**: 因子组成未变化。\n")
    except Exception as e:
        lines.append(f"**执行失败**: {e}\n")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="月度因子审计")
    parser.add_argument("--output", default=None, help="报告输出路径")
    args = parser.parse_args()

    output_path = args.output or str(_PROJECT_ROOT / "data" / "processed" / "audit_report.md")

    print("=" * 60)
    print("  月度因子审计")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    from app.db import log_error

    print("\n[1/3] 拉取数据...")
    try:
        med_w, margin_w, vol_w, north_w, hs300_w, m2_w = _load_data()
        print(f"  指数: {len(med_w)} 周" + (f", 成交量: {len(vol_w)} 周" if vol_w is not None else ""))
    except Exception as e:
        err_msg = f"月度审计: 数据拉取失败 — {e}"
        print(f"  [ERROR] {err_msg}")
        log_error("monthly_audit", err_msg, "error")
        return

    print("\n[2/3] 执行审计...")
    report = generate_report(med_w, margin_w, vol_w, north_w, hs300_w, m2_w)

    print(f"\n[3/3] 写入报告...")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(report, encoding="utf-8")
    print(f"  报告已保存: {output_path}")

    log_error("monthly_audit", f"审计完成，报告: {output_path}", "info")
    print("\n  审计完成。")


if __name__ == "__main__":
    main()
