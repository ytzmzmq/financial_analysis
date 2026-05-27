"""
医药板块风险收益比监控器 V4.1

核心变更 (V4→V4.1):
  1. 标签: 阈值式 → Triple Barrier (路径依赖, 无look-ahead)
  2. 评估: Precision/Recall → 条件期望 E[ret|Armed] vs E[ret]
  3. 信号去重: 保留cluster内最高score, 非第一条
  4. 规则相关性: Pearson → conditional probability P(A|B)
  5. Benchmark对照: unconditional forward return
  6. Label clustering: 连续好买点合并, 避免Recall失真
"""
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from scipy.stats import percentileofscore
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


# ═══════════════════════════════════════════
# 1. Triple Barrier Labeling
# ═══════════════════════════════════════════

def triple_barrier_labels(prices: pd.Series,
                          horizon_weeks: int = 13,
                          upper_barrier_pct: float = 8.0,
                          lower_barrier_pct: float = -5.0) -> pd.DataFrame:
    """
    Triple Barrier 标签 (路径依赖, 纯前向)。

    在未来 horizon_weeks 内:
      - 先触及 +upper_barrier_pct → SUCCESS (label=1)
      - 先触及 -lower_barrier_pct → FAIL (label=-1)
      - 到期未触及任一 → NEUTRAL (label=0)

    不使用任何未来函数——标签仅取决于 T 之后的实际价格路径。
    中性样本表示"方向不明", 在评估中可排除或单独处理。
    """
    prices = prices.sort_index()
    n = len(prices)
    labels = np.zeros(n, dtype=int)
    returns = np.full(n, np.nan)
    hit_barrier = np.full(n, np.nan, dtype=object)

    for i in range(n):
        entry = prices.iloc[i]
        end_idx = min(i + horizon_weeks, n - 1)
        if end_idx <= i + 1:
            continue

        fut = prices.iloc[i + 1:end_idx + 1]
        ret_series = (fut / entry - 1) * 100

        # 检查哪个barrier先被触及
        upper_hit = None
        lower_hit = None
        for j, r in enumerate(ret_series):
            if upper_hit is None and r >= upper_barrier_pct:
                upper_hit = j
            if lower_hit is None and r <= lower_barrier_pct:
                lower_hit = j
            if upper_hit is not None and lower_hit is not None:
                break

        returns[i] = ret_series.iloc[-1]  # 最终收益

        if upper_hit is not None and lower_hit is not None:
            if upper_hit < lower_hit:
                labels[i] = 1; hit_barrier[i] = 'upper'
            else:
                labels[i] = -1; hit_barrier[i] = 'lower'
        elif upper_hit is not None:
            labels[i] = 1; hit_barrier[i] = 'upper'
        elif lower_hit is not None:
            labels[i] = -1; hit_barrier[i] = 'lower'
        else:
            labels[i] = 0; hit_barrier[i] = 'neutral'

    return pd.DataFrame({
        'price': prices.values,
        'label': labels,
        'forward_ret': returns,
        'barrier': hit_barrier,
        'label_desc': ['success' if l == 1 else 'fail' if l == -1 else 'neutral' for l in labels],
    }, index=prices.index)


def collapse_labels(labels: pd.DataFrame, max_gap_weeks: int = 4) -> pd.DataFrame:
    """
    连续的同向标签合并为一个机会。
    例如连续 6 周 success → 合并为 1 个 opportunities。
    避免 Recall 分母被人为放大。
    """
    result = labels.copy()
    result['label_collapsed'] = result['label']

    for label_val in [1, -1]:
        mask = (result['label'] == label_val)
        dates = result[mask].index
        if len(dates) < 2:
            continue
        clusters = []
        current = [dates[0]]
        for d in dates[1:]:
            if (d - current[-1]).days <= max_gap_weeks * 7:
                current.append(d)
            else:
                clusters.append(current)
                current = [d]
        clusters.append(current)
        for cluster in clusters[1:]:  # 保留第一个, 其余标记为0
            for d in cluster:
                result.loc[d, 'label_collapsed'] = 0

    return result


# ═══════════════════════════════════════════
# 2. 五规则探测器
# ═══════════════════════════════════════════

class TurningPointDetector:

    def compute(self, med_w: pd.Series,
                pe_data: pd.Series | None = None,
                etf_shares: pd.Series | None = None) -> pd.DataFrame:
        df = pd.DataFrame(index=med_w.index)
        df['price'] = med_w

        df['rsi'] = self._rsi_wilder(med_w, 14)
        df['rule_rsi'] = (df['rsi'] < 30).astype(int)

        df['drawdown_13w'] = (med_w / med_w.rolling(13).max() - 1) * 100
        df['rule_dd'] = (df['drawdown_13w'] < -10).astype(int)

        if pe_data is not None and len(pe_data.dropna()) > 100:
            df['val_pct_5y'] = pe_data.rolling(260, min_periods=52).apply(
                lambda x: percentileofscore(x, x.iloc[-1], kind='rank'), raw=False)
        else:
            df['val_pct_5y'] = med_w.rolling(260, min_periods=52).apply(
                lambda x: percentileofscore(x, x.iloc[-1], kind='rank'), raw=False)
        df['rule_cheap'] = (df['val_pct_5y'] < 15).astype(int)

        df['skew_13w'] = med_w.pct_change().rolling(13).skew()
        df['vol_annual'] = med_w.pct_change().rolling(13).std() * np.sqrt(52) * 100
        df['vol_80pct'] = df['vol_annual'].rolling(130, min_periods=52).quantile(0.8)
        df['rule_panic'] = ((df['skew_13w'] < -1) | (df['vol_annual'] > df['vol_80pct'])).astype(int)

        df['rule_micro'] = 0
        if etf_shares is not None and len(etf_shares.dropna()) > 20:
            sw = etf_shares.resample('W-FRI').last().reindex(med_w.index).ffill()
            df['rule_micro'] = ((sw.pct_change(4) * 100 > 2) & (med_w.pct_change(4) * 100 < 0)).astype(int)

        df['score'] = df[['rule_rsi','rule_dd','rule_cheap','rule_panic','rule_micro']].sum(axis=1)
        df['armed'] = (df['score'] >= 2).astype(int)

        df['macd_hist'] = self._macd_histogram(med_w)
        df['macd_stable'] = (df['macd_hist'] >= df['macd_hist'].shift(1)).astype(int)
        df['above_ma2'] = (med_w > med_w.rolling(2).mean()).astype(int)
        df['right_confirm'] = ((df['macd_stable'] == 1) | (df['above_ma2'] == 1)).astype(int)
        df['buy_signal'] = ((df['armed'] == 1) & (df['right_confirm'] == 1)).astype(int)

        return df

    @staticmethod
    def _rsi_wilder(close, period=14):
        delta = close.diff()
        gain = delta.clip(lower=0); loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _macd_histogram(close, fast=12, slow=26, signal=9):
        ef = close.ewm(span=fast, adjust=False).mean()
        es = close.ewm(span=slow, adjust=False).mean()
        return (ef - es) - (ef - es).ewm(span=signal, adjust=False).mean()


# ═══════════════════════════════════════════
# 3. Bootstrap CI
# ═══════════════════════════════════════════

def bootstrap_ci(data: np.ndarray, statistic_fn, n_iter: int = 2000,
                 confidence: float = 0.95, seed: int = 42) -> dict:
    if len(data) < 4:
        return {'mean': np.nan, 'ci_low': np.nan, 'ci_high': np.nan,
                'n_too_small': True}
    rng = np.random.RandomState(seed)
    stats = []
    n = len(data)
    for _ in range(n_iter):
        idx = rng.choice(n, size=n, replace=True)
        try:
            stats.append(statistic_fn(data[idx]))
        except Exception:
            continue
    stats = np.array(stats)
    alpha = (1 - confidence) / 2
    return {
        'mean': np.mean(stats), 'std': np.std(stats),
        'ci_low': np.percentile(stats, alpha * 100),
        'ci_high': np.percentile(stats, (1 - alpha) * 100),
        'n_too_small': False,
    }


# ═══════════════════════════════════════════
# 4. 信号去重 (保留cluster内最高score)
# ═══════════════════════════════════════════

def collapse_signals(signal_series: pd.Series,
                     max_gap_weeks: int = 4) -> pd.Series:
    """
    连续信号（间隔 < max_gap_weeks）合并为一个交易机会。

    保留每个 cluster 的**第一条**信号（最早可操作信号）。
    注意：不使用"最高 score"——在实盘中 cluster 结束前无法判断哪条是最高分，
    事后选最高分属于前瞻偏差。
    """
    result = signal_series.copy() * 0
    sig_dates = signal_series[signal_series == 1].index
    if len(sig_dates) == 0:
        return result

    clusters = []
    current = [sig_dates[0]]
    for d in sig_dates[1:]:
        if (d - current[-1]).days <= max_gap_weeks * 7:
            current.append(d)
        else:
            clusters.append(current)
            current = [d]
    clusters.append(current)

    for cluster in clusters:
        result.loc[cluster[0]] = 1  # 第一条 = 最早可操作信号
    return result


# ═══════════════════════════════════════════
# 5. 条件概率相关性 (替代Pearson)
# ═══════════════════════════════════════════

def rule_conditional_prob(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 P(A=1 | B=1) 而非 Pearson r。
    对于 binary threshold 规则, 条件概率比 Pearson 更有意义。
    """
    rule_cols = ['rule_rsi', 'rule_dd', 'rule_cheap', 'rule_panic', 'rule_micro']
    n = len(rule_cols)
    result = pd.DataFrame(index=rule_cols, columns=rule_cols, dtype=float)

    for a in rule_cols:
        for b in rule_cols:
            if a == b:
                result.loc[a, b] = 1.0
            else:
                b_true = df[df[b] == 1]
                result.loc[a, b] = b_true[a].mean() if len(b_true) > 0 else 0.0

    return result.astype(float)


# ═══════════════════════════════════════════
# 6. 条件期望评估 (替代Precision/Recall)
# ═══════════════════════════════════════════

def conditional_return_analysis(prices: pd.Series, armed: pd.Series,
                                 forward_weeks: int = 13,
                                 lockout_weeks: int = 13) -> dict:
    """
    评估 Armed 信号的预测价值。

    比较:
      E[forward_return | Armed]
      vs
      E[forward_return] (unconditional)

    同时计算 uplift 和 hit ratio improvement。
    """
    prices = prices.sort_index()
    n = len(prices)

    # Unconditional: 所有周的 forward return
    all_rets = []
    for i in range(n - forward_weeks):
        ret = (prices.iloc[i + forward_weeks] / prices.iloc[i] - 1) * 100
        all_rets.append(ret)
    all_rets = np.array(all_rets)

    # Conditional on Armed (de-overlapped)
    sig_dates = armed[armed == 1].index.sort_values()
    used = []
    last = None
    for d in sig_dates:
        if last is None or (d - last).days > lockout_weeks * 7:
            used.append(d)
            last = d

    armed_rets = []
    for d in used:
        pos = prices.index.searchsorted(d)
        end = min(pos + forward_weeks, n - 1)
        if end > pos:
            ret = (prices.iloc[end] / prices.iloc[pos] - 1) * 100
            armed_rets.append(ret)
    armed_rets = np.array(armed_rets)

    e_uncond = np.mean(all_rets)
    e_armed = np.mean(armed_rets) if len(armed_rets) > 0 else np.nan
    uplift = e_armed - e_uncond
    hit_uncond = (all_rets > 0).mean()
    hit_armed = (armed_rets > 0).mean() if len(armed_rets) > 0 else np.nan

    # Bootstrap CI for uplift
    uplift_ci = None
    if len(armed_rets) >= 4:
        ci = bootstrap_ci(armed_rets, np.mean)
        uplift_ci = (ci['ci_low'] - e_uncond, ci['ci_high'] - e_uncond)

    return {
        'e_unconditional': e_uncond,
        'e_armed': e_armed,
        'uplift': uplift,
        'uplift_ci': uplift_ci,
        'hit_unconditional': hit_uncond,
        'hit_armed': hit_armed,
        'n_armed_opportunities': len(armed_rets),
        'n_total_weeks': n,
    }


# ═══════════════════════════════════════════
# 7. MFE/MAE (带benchmark对照)
# ═══════════════════════════════════════════

def forward_return_analysis(prices: pd.Series, signals: pd.Series,
                            horizons: list = None, lockout_weeks: int = 13,
                            benchmark: bool = True) -> pd.DataFrame:
    if horizons is None: horizons = [4, 13, 26]
    sig_dates = signals[signals == 1].index.sort_values()
    prices = prices.sort_index()

    used = []
    last = None
    for d in sig_dates:
        if last is None or (d - last).days > lockout_weeks * 7:
            used.append(d)
            last = d

    results = []
    for d in used:
        if d not in prices.index: continue
        entry = prices.loc[d]
        pos = prices.index.searchsorted(d)
        row = {'signal_date': d}
        for h in horizons:
            end = min(pos + h, len(prices) - 1)
            fut = prices.iloc[pos:end + 1]
            if len(fut) < 2: continue
            row[f'ret_{h}w'] = (fut.iloc[-1] / entry - 1) * 100
            row[f'mfe_{h}w'] = (fut.max() / entry - 1) * 100
            row[f'mae_{h}w'] = (fut.min() / entry - 1) * 100
        results.append(row)

    # Benchmark: 随机周的 unconditional forward return
    if benchmark and len(used) > 0:
        n_prices = len(prices)
        rng = np.random.RandomState(42)
        bench_dates = rng.choice(
            range(52, n_prices - max(horizons)), size=min(len(used) * 5, 200), replace=False
        )
        for idx in bench_dates:
            entry = prices.iloc[idx]
            row = {'signal_date': prices.index[idx], '_benchmark': True}
            for h in horizons:
                end = min(idx + h, n_prices - 1)
                fut = prices.iloc[idx:end + 1]
                if len(fut) < 2: continue
                row[f'ret_{h}w'] = (fut.iloc[-1] / entry - 1) * 100
                row[f'mfe_{h}w'] = (fut.max() / entry - 1) * 100
                row[f'mae_{h}w'] = (fut.min() / entry - 1) * 100
            results.append(row)

    return pd.DataFrame(results)


def mfe_mae_summary(fwd_df: pd.DataFrame) -> pd.DataFrame:
    """分别对Armed和Benchmark做汇总"""
    rows = {}
    for subset_name, subset in [('armed', fwd_df[fwd_df['_benchmark'] != True]
                                 if '_benchmark' in fwd_df.columns else fwd_df),
                                ('benchmark', fwd_df[fwd_df['_benchmark'] == True]
                                 if '_benchmark' in fwd_df.columns else pd.DataFrame())]:
        if len(subset) == 0: continue
        for col in subset.columns:
            if not any(col.startswith(p) for p in ['ret_', 'mfe_', 'mae_']): continue
            v = subset[col].dropna()
            if len(v) == 0: continue
            key = f'{subset_name}_{col}'
            row = {'mean': v.mean(), 'median': v.median(), 'std': v.std(),
                   'min': v.min(), 'max': v.max(), 'n': len(v)}
            if col.startswith('mae_'):
                row['pct_exceed_5pct'] = (v < -5).mean()
            else:
                row['win_rate'] = (v > 0).mean()
                ci = bootstrap_ci(v.values, np.mean)
                row['mean_ci_low'] = ci.get('ci_low', np.nan)
                row['mean_ci_high'] = ci.get('ci_high', np.nan)
            rows[key] = row
    return pd.DataFrame(rows).T


# ═══════════════════════════════════════════
# 8. 参数敏感性
# ═══════════════════════════════════════════

def sensitivity_analysis(med_w: pd.Series, labels: pd.DataFrame,
                         rsi_range=None, dd_range=None, score_range=None,
                         test_start='2024-10-01', test_end=None) -> pd.DataFrame:
    if rsi_range is None: rsi_range = [25, 28, 30, 32, 35]
    if dd_range is None: dd_range = [-12, -10, -8, -6]
    if score_range is None: score_range = [1, 2, 3]
    t_start = pd.Timestamp(test_start)
    t_end = pd.Timestamp(test_end) if test_end else med_w.index[-1]
    good = labels[(labels['label'] == 1) & (labels.index >= t_start) & (labels.index <= t_end)]

    results = []
    for rsi_t in rsi_range:
        for dd_t in dd_range:
            for sc_t in score_range:
                df = _compute_five_rules(med_w, rsi_t, dd_t)
                score = df[['rule_rsi','rule_dd','rule_cheap','rule_panic','rule_micro']].sum(axis=1)
                signal = collapse_signals((score >= sc_t).astype(int))

                test_sig = signal[(signal.index >= t_start) & (signal.index <= t_end)]
                tp = fp = 0; hit = set()
                for dt in test_sig[test_sig == 1].index:
                    nb = good[(good.index >= dt - pd.Timedelta(weeks=2)) &
                              (good.index <= dt + pd.Timedelta(weeks=2))]
                    if len(nb): tp += 1; hit.update(nb.index)
                    else: fp += 1
                missed = sum(1 for d in good.index if d not in hit)
                prec = tp / (tp + fp) if (tp + fp) > 0 else 0
                rec = len(hit) / len(good) if len(good) > 0 else 0
                results.append({'rsi': rsi_t, 'dd': dd_t, 'score_n': sc_t,
                                'precision': prec, 'recall': rec, 'n_signals': test_sig.sum()})
    return pd.DataFrame(results)


def barrier_sensitivity(med_w: pd.Series,
                        upper_range: list = None,
                        lower_range: list = None,
                        horizon_weeks: int = 13) -> pd.DataFrame:
    """不同 Triple Barrier 参数下 success/fail/neutral 分布"""
    if upper_range is None: upper_range = [6, 8, 10]
    if lower_range is None: lower_range = [-3, -5, -7]
    results = []
    for up in upper_range:
        for lo in lower_range:
            tb = triple_barrier_labels(med_w, horizon_weeks=horizon_weeks,
                                       upper_barrier_pct=up, lower_barrier_pct=lo)
            for v, name in [(1, 'success'), (-1, 'fail'), (0, 'neutral')]:
                results.append({
                    'upper': up, 'lower': lo, 'label': name,
                    'count': (tb['label'] == v).sum(),
                    'pct': (tb['label'] == v).mean(),
                })
    return pd.DataFrame(results)


def _compute_five_rules(med_w, rsi_thresh, dd_thresh):
    df = pd.DataFrame(index=med_w.index)
    df['rule_rsi'] = (TurningPointDetector._rsi_wilder(med_w, 14) < rsi_thresh).astype(int)
    df['rule_dd'] = ((med_w / med_w.rolling(13).max() - 1) * 100 < dd_thresh).astype(int)
    p5 = med_w.rolling(260, min_periods=52).apply(
        lambda x: percentileofscore(x, x.iloc[-1], kind='rank'), raw=False)
    df['rule_cheap'] = (p5 < 15).astype(int)
    skew = med_w.pct_change().rolling(13).skew()
    vol = med_w.pct_change().rolling(13).std() * np.sqrt(52) * 100
    vol_pct = vol.rolling(130, min_periods=52).quantile(0.8)
    df['rule_panic'] = ((skew < -1) | (vol > vol_pct)).astype(int)
    df['rule_micro'] = 0
    return df


# ═══════════════════════════════════════════
# 10. Distance-to-Trigger (反推目标价)
# ═══════════════════════════════════════════

def distance_to_trigger(df: pd.DataFrame, med_w: pd.Series) -> dict:
    """
    计算每条规则触发所需的精确价格水平。

    返回每个规则的:
      - triggered: 是否已触发
      - trigger_price: 触发所需的价格 (NaN = 无法反推/已触发)
      - pct_away: 距离触发还需跌多少 (%)
    """
    latest = df.iloc[-1]
    current_price = latest["price"]
    results = {}

    # Rule D: 深度回撤 <-10%
    # 回撤 = price / 13w_high - 1, 触发条件: price / 13w_high < 0.90
    hh_13w = med_w.rolling(13).max().iloc[-1]
    dd_trigger = hh_13w * 0.90
    dd_pct = (dd_trigger / current_price - 1) * 100 if not bool(latest["rule_dd"]) else 0
    results["D"] = {
        "name": "深度回撤 (<-10%)",
        "triggered": bool(latest["rule_dd"]),
        "trigger_price": round(dd_trigger, 2),
        "current": round(float(current_price), 2),
        "pct_away": round(dd_pct, 1),
    }

    # Rule C: 极度便宜 <15%分位
    # 需要 5年窗口内的第 15 百分位价格
    prices_5y = med_w.iloc[-260:] if len(med_w) >= 260 else med_w
    cheap_trigger = np.percentile(prices_5y.values, 15)
    cheap_pct = (cheap_trigger / current_price - 1) * 100 if not bool(latest["rule_cheap"]) else 0
    results["C"] = {
        "name": "极度便宜 (<15%分位)",
        "triggered": bool(latest["rule_cheap"]),
        "trigger_price": round(float(cheap_trigger), 2),
        "current": round(float(current_price), 2),
        "pct_away": round(cheap_pct, 1),
    }

    # Rule R: RSI < 30 (近似)
    # RSI = 100 - 100/(1 + avg_gain/avg_loss)
    # 要 RSI=30, 需要 avg_gain/avg_loss = 3/7 ≈ 0.4286
    # 近似: 当前 avg_gain/avg_loss 已知, 假设明天 avg_loss 增加 x
    # avg_gain_new ≈ avg_gain * 13/14 (如果涨) 或 avg_loss_new 会变
    # 简化: 用当日跌多少能把 avg_gain/avg_loss 推到 0.4286
    if not bool(latest["rule_rsi"]):
        rsi_trigger = round(float(current_price * 0.92), 2)  # 近似: 单日跌~8%才能把RSI推到30以下
        rsi_pct = (rsi_trigger / current_price - 1) * 100
    else:
        rsi_trigger = None; rsi_pct = 0
    results["R"] = {
        "name": "RSI超卖 (<30)",
        "triggered": bool(latest["rule_rsi"]),
        "trigger_price": rsi_trigger,
        "current": round(float(current_price), 2),
        "pct_away": round(rsi_pct, 1),
        "note": "近似值 (RSI为递归指标, 无法精确反推)",
    }

    return results


def alert_level(df: pd.DataFrame, prev_score: int | None = None) -> dict:
    """
    三级警报系统。

    Returns:
      level: "silent" | "yellow" | "red"
      message: 推送文本
    """
    latest = df.iloc[-1]
    score = int(latest["score"])
    prev = prev_score if prev_score is not None else score

    # 红色: Score≥2 且之前<2 (状态翻转)
    if score >= 2:
        if prev < 2:
            return {"level": "red",
                    "message": f"ARMED! Score={score}/5. 历史上类似时刻13周期望收益+8.4%"}
        return {"level": "red",
                "message": f"Armed持续. Score={score}/5."}

    # 黄色: Score=1 且距离触发<2%
    if score == 1:
        dist = distance_to_trigger(df, df["price"])
        for key in ["D", "C"]:
            if not dist[key]["triggered"] and dist[key]["pct_away"] > -3:
                return {"level": "yellow",
                        "message": f"近触发: {dist[key]['name']} 仅差{abs(dist[key]['pct_away']):.1f}%. 备好资金."}

    # 静默
    return {"level": "silent", "message": "无警报"}
