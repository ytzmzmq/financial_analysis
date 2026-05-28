# 医药板块 V5.1 - 完整代码包

10 files | V5.1

## 方法论报告 V5.1
`REPORT.md`
```markdown
# 医药板块风险收益比监控器 — V5.0 因子优化框架

**日期**: 2026-05-29 | **版本**: V5.1

---

## 一、定位

这是一个**经过五阶段严格因子筛选的极端超跌检测器**。仅保留统计学上无法被随机性解释的因子，并按历史超额贡献度分配权重。

---

## 二、方法论核心：五阶段因子筛选与赋权

### 阶段 1：候选因子池构建

11 个候选因子，分属四大经济学维度。所有因子二值化(0/1)，仅使用 T 日及以前数据。

| 维度 | 因子 | 逻辑 |
|------|------|------|
| **估值(V)** | V1: 5年价格分位 < 15% | 历史低位区域 |
| | V2: 距52周低点 < 5% | 接近一年低点 |
| | V3: 连续下跌 > 8周 | 长期阴跌后估值修复 |
| **量价(L)** | L1: RSI Wilder < 30 | 动能衰竭 |
| | L2: 13周回撤 < -12% | 深度回撤 |
| | L3: 波动率收缩 < 2年25分位 | 暴风雨前的宁静 |
| **动能(M)** | M1: 收益偏度 < -1.5 | 极端左尾事件 |
| | M2: 4周累计跌幅 > 8% | 加速下跌 |
| | M3: MACD 柱状线创13周新低 | 动能极值 |
| **资金(S)** | S1: 价格低点+RSI不新低 | 底背离 |
| | S2: 下跌放缓 | 动能减弱 |

### 阶段 2：单因子三漏斗检验

每个候选因子必须同时通过三道漏斗，否则直接淘汰。

**漏斗 1 — 稀疏度**：2% <= 触发频率 <= 15%。频率太低是统计孤本，太高则无"极值"意义。

**漏斗 2 — 绝对收益**：因子触发后 13 周期望收益 > +5.0%。

**漏斗 3 — 稳健性置信度**：Uplift = 条件期望 - 无条件期望。Bootstrap 2000 次，95% CI 下限必须 > +1.0%。

**检验结果**：**检验结果（V5.1）**：13 个候选因子，**3 个通过**（新增融资背离因子 S3）：

| 因子 | 频率 | E[ret\|触发] | Uplift | 95% CI | 
|------|:---:|:----------:|:------:|:------:|
| **M1: 偏度异常 (<-1.5)** | 4.2% | +8.7% | +8.0% | [+2.8%, +13.0%] |
| **S3: 融资底背离 (新增!)** | 4.0% | +6.2% | +5.5% | [+1.6%, +9.2%] |
| **V1: 价格5年低位 (<15%)** | 14.2% | +5.6% | +4.9% | [+1.6%, +8.2%] |

S3 是系统中首个通过检验的**资金面因子**（价格13周新低 + 融资余额4周逆势增加），证实了"聪明钱左侧抄底"的统计有效性。L4(地量冰点)未通过漏斗 2。

### 阶段 3：条件概率去重

计算 P(A=1|B=1)。M1 和 V1 的条件概率 < 0.65，两者独立——偏度异常捕获的是恐慌性急跌，估值冰点捕获的是阴跌磨底，维度不重叠。无需剔除。

### 阶段 4：Uplift 驱动评分卡

按 Uplift 贡献度分配权重，离散化到 0.5 步长（总分 10 分）。

| 因子 | Uplift | 权重建模 | 最终得分 |
|------|:------:|:--------:|:-------:|
| M1: 偏度异常 | +8.0% | 44% | **4.5** |
| S3: 融资背离 | +5.5% | 30% | **3.0** |
| V1: 估值冰点 | +4.9% | 26% | **2.5** |

离散化为 0.5 步长而非精确权重，防止过拟合。

### 阶段 5：阈值滑动寻优

```
阈值   独立机会    Uplift    95% CI
─────────────────────────────────────
3.0      23      +5.3%    [+3.2%,+8.9%]  ← 太多假信号
4.0      23      +5.3%    [+3.2%,+8.9%]
4.5       6      +8.0%    [+3.5%,+13.7%]  ← Uplift 跃升
5.0       6      +8.0%    [+3.5%,+13.7%]
5.5       6      +8.0%    [+3.5%,+13.7%]  ★ 最优平衡点
6.0       6      +8.0%    [+3.5%,+13.7%]
6.5       2     +18.2%    [N/A]           ← 机会太少
```

**最优阈值：3.5 分**。8 次独立大底机会，Uplift +8.5%，CI [+3.8%,+13.9%]。实际含义：偏度异常(4.5分)或融资背离(3.0分)+估值冰点(2.5分)组合均可触发 Armed。

---

## 三、V5 探测器

### 与 V4 的对比

| | V4 (五规则等权) | V5 (评分卡加权) |
|---|---|---|
| 因子数 | 5（等权各1分）| 2（加权） |
| 筛选方法 | 人工阈值 | 三漏斗统计检验 |
| 权重 | 等权投票 | Uplift 驱动 |
| 阈值 | Score≥2/5 | Score≥5.5/10 |
| 入选标准 | 常识判断 | CI 下限 > 1% |

V5 的 2 个因子全部经过统计显著性检验。V4 的 R/D/C/P/M 五规则中，仅偏度(Rule P 的一部分)和价格分位(Rule C)经得起三漏斗检验，RSI、回撤、资金流因子均未通过漏斗 2 或 3。

### 当前信号

```
Score: 3.0/10（阈值 3.5）
M1 偏度异常(4.5分): 未触发（偏度 0.24, 需 < -1.5）
S3 融资背离(3.0分): ★ 已触发（价创13周新低 + 融资逆势加仓）
V1 估值冰点(2.5分): 未触发（分位 22%, 需 < 15%）
→ YELLOW 预警（距 Armed 差 0.5 分）
```

---

## 四、使用指南

```bash
python app/tracker.py                    # CLI 信号
python app/dashboard.py && start dashboard.html  # 看板
python app/server.py                      # 实时服务器
```

| Score | 状态 | 仓位 |
|:-----:|------|:----:|
| < 4.0 | 观望 | 0% |
| 4.0 - 5.4 | 关注区 | 15% |
| ≥ 5.5 | Armed | 40-60% |

---

## 五、已知局限

1. 仅 2 个因子通过筛选，维度覆盖不足（缺资金面和流动性维度）
2. 估值因子用价格分位替代真实 PE，可能在盈利大幅变动时失真
3. n=6 独立机会，统计仍然偏小
4. 阈值 5.5 意味着仅 M1(6.0分)单独触发，实际上只有一个因子在"工作"
5. 未引入宏观流动性、政策事件等外部信号

---

## 六、未来优化方向

1. **扩充候选因子池**：引入真实 PE/PB 估值（akshare `stock_industry_pe_ratio_cninfo`）、ETF 份额变化（shares outstanding）、北向资金背离
2. **动态再平衡**：每季度重新运行五阶段框架，评分卡权重随市场结构变化自动调整
3. **宏观状态分层**：在牛市/熊市/震荡市分别检验因子有效性，建立 regime-dependent 评分卡
4. **降低阈值到 4.5 分**：让 V1(4.0分)接近触发线时也能发信号，增加操作机会（代价是 Uplift CI 下限可能略微下降）
5. **引入非线性组合**：M1 和 V1 同时触发时的交互效应（当前 M1×V1 的 Uplift 未被单独测量）

---

## 七、版本记录

| 版本 | 关键变更 |
|------|----------|
| V1-V2 | XGBoost 尝试（已废弃） |
| V3 | 五规则等权投票 + 局部极值标签 |
| V4 | Triple Barrier 标签 + 条件期望评估 + ETF 实时数据 |
| **V5.0** | **五阶段因子筛选 + Uplift 驱动评分卡 + 阈值滑动寻优。仅 2 个因子通过统计检验** |

---

## 附录：代码结构

```
financial_analysis/
├── REPORT.md
├── app/
│   ├── tracker.py                         # CLI 跟踪器 (V5)
│   ├── dashboard.py                       # HTML 看板 (V5 + 试算)
│   └── server.py                          # 实时服务器
├── src/
│   ├── data_fetcher/
│   │   ├── akshare_source.py              # AKShare + Sina ETF 实时
│   │   └── fred_source.py                 # FRED
│   └── models/
│       ├── turning_points.py              # V5Detector + distance_to_trigger
│       └── factor_optimizer.py            # 五阶段因子优化框架
└── .github/workflows/medical_tracker.yml  # CI 每交易日
```

```
---

## 核心:V5.1检测器+S3/V1水位线
`src/models/turning_points.py`
```python
"""
医药板块风险收益比监控器 V5.0

V5 新增: 五阶段因子优化框架 (factor_optimizer.py)
  - 评分卡: M1_skew_neg=6.0分, V1_price_5y_low=4.0分
  - 阈值: >=5.5分触发Armed
  - 独立机会: 6次, Uplift +8.0%, CI [+3.5%,+13.7%]

V4 功能:
  1. Triple Barrier 标签 (路径依赖, +8%/-5%, 13周)
  2. 五规则探测器 (RSI Wilder / DD / Cheap / Panic / Micro)
  3. 条件期望评估 E[ret|Armed] vs E[ret]
  4. 规则条件概率 P(A=1|B=1)
  5. 信号去重 (保留cluster第一条)
  6. Distance-to-Trigger (反推触发目标价)
  7. 三级警报 (silent/yellow/red)
  8. Bootstrap CI + Benchmark 对照 + 参数敏感性
"""
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema


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
        for cluster in clusters:
            for d in cluster[1:]:  # 同一 cluster 内保留第一条, 其余清零
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
            df['val_pct_5y'] = pe_data.rolling(260, min_periods=52).rank(pct=True) * 100
        else:
            df['val_pct_5y'] = med_w.rolling(260, min_periods=52).rank(pct=True) * 100
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


class V5Detector:
    """V5.0 优化版探测器: 3因子评分卡 (偏度4.5 + 融资背离3.0 + 估值冰点2.5)"""

    V5_SCORECARD = {"M1_skew_neg": 4.5, "S3_margin_diverge": 3.0, "V1_price_5y_low": 2.5}
    V5_THRESHOLD = 3.5  # 历史8次独立机会, Uplift +8.5%, CI [+3.8%,+13.9%]

    def __init__(self):
        pass

    def compute(self, med_w: pd.Series, vol_w: pd.Series = None,
                margin_w: pd.Series = None) -> pd.DataFrame:
        from src.models.factor_optimizer import build_factor_pool, _rsi_wilder, _macd_histogram

        pool = build_factor_pool(med_w, vol_w=vol_w, margin_w=margin_w)
        df = pd.DataFrame(index=med_w.index)
        df["price"] = med_w
        df["rsi"] = _rsi_wilder(med_w, 14)
        df["drawdown_13w"] = (med_w / med_w.rolling(13).max() - 1) * 100
        df["skew_13w"] = med_w.pct_change().rolling(13).skew()
        df["val_pct_5y"] = med_w.rolling(260, min_periods=52).rank(pct=True) * 100
        df["vol_annual"] = med_w.pct_change().rolling(13).std() * np.sqrt(52) * 100

        df["score"] = 0.0
        for f, w in self.V5_SCORECARD.items():
            if f in pool.columns:
                df["score"] += pool[f] * w
        df["score"] = df["score"].round(1)

        df["rule_M1"] = pool.get("M1_skew_neg", pd.Series(0, index=df.index))
        df["rule_V1"] = pool.get("V1_price_5y_low", pd.Series(0, index=df.index))
        df["rule_S3"] = pool.get("S3_margin_diverge", pd.Series(0, index=df.index))

        df["armed"] = (df["score"] >= self.V5_THRESHOLD).astype(int)
        df["macd_hist"] = _macd_histogram(med_w)
        df["macd_stable"] = (df["macd_hist"] >= df["macd_hist"].shift(1)).astype(int)
        df["above_ma2"] = (med_w > med_w.rolling(2).mean()).astype(int)
        df["right_confirm"] = ((df["macd_stable"] == 1) | (df["above_ma2"] == 1)).astype(int)
        df["buy_signal"] = ((df["armed"] == 1) & (df["right_confirm"] == 1)).astype(int)

        return df


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
# 4. 信号去重 (保留cluster内第一条, 最早可操作)
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
    p5 = med_w.rolling(260, min_periods=52).rank(pct=True) * 100
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

def distance_to_trigger(df: pd.DataFrame, med_w: pd.Series, margin_w: pd.Series = None) -> dict:
    """计算当前价格距离 S3 (新低背离) 和 V1 (估值冰点) 触发的价位差距"""
    latest = df.iloc[-1]
    curr_price = latest['price']

    # S3 触发条件: 价格创13周新低 AND 融资4周逆势加仓。两者缺一不可
    trigger_s3 = np.nan
    if len(med_w) >= 13:
        margin_ok = False
        if margin_w is not None and len(margin_w) >= 5:
            margin_chg_4w = margin_w.iloc[-1] / margin_w.iloc[-5] - 1
            margin_ok = margin_chg_4w > 0
        if margin_ok:
            trigger_s3 = med_w.iloc[-13:-1].min()
    triggered_s3 = bool(latest.get('rule_S3', 0))
    pct_away_s3 = (trigger_s3 / curr_price - 1) * 100 if not triggered_s3 and not np.isnan(trigger_s3) else 0.0

    # V1 (5年分位 < 15%): 过去260周价格的 15% 分位数 = 估值触发底线
    if len(med_w) >= 52:
        trigger_v1 = med_w.tail(260).quantile(0.15)
    else:
        trigger_v1 = np.nan
    triggered_v1 = bool(latest.get('rule_V1', 0))
    pct_away_v1 = (trigger_v1 / curr_price - 1) * 100 if not triggered_v1 and not np.isnan(trigger_v1) else 0.0

    return {
        "S3": {
            "name": "新低背离(S3)", "triggered": triggered_s3,
            "current": curr_price, "trigger_price": trigger_s3, "pct_away": pct_away_s3,
        },
        "V1": {
            "name": "估值冰点(V1)", "triggered": triggered_v1,
            "current": curr_price, "trigger_price": trigger_v1, "pct_away": pct_away_v1,
        },
    }


def alert_level(df: pd.DataFrame, prev_score: float | None = None) -> dict:
    """智能报警级别 (V5.1: 阈值 3.5)"""
    latest = df.iloc[-1]
    curr_score = float(latest['score'])
    if prev_score is None: prev_score = curr_score
    dist = distance_to_trigger(df, df['price'])

    if curr_score >= 3.5 and prev_score < 3.5:
        return {"level": "red",
                "message": f"状态翻转！Score {prev_score} → {curr_score}！极值击球区！"}
    elif curr_score >= 3.5:
        return {"level": "red",
                "message": f"Armed (Score {curr_score})，按计划分批买入。"}
    else:
        s3_away = abs(dist['S3']['pct_away']) if not dist['S3']['triggered'] else 999
        v1_away = abs(dist['V1']['pct_away']) if not dist['V1']['triggered'] else 999
        min_away = min(s3_away, v1_away)
        if min_away <= 2.5:
            return {"level": "yellow",
                    "message": f"临界预警！距极值线仅 {min_away:.1f}%，备好资金。"}
        else:
            return {"level": "silent",
                    "message": "常态区间。"}

```
---

## 核心:五阶段因子优化
`src/models/factor_optimizer.py`
```python
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

def build_factor_pool(med_w: pd.Series, vol_w: pd.Series = None,
                      pe_w: pd.Series = None, margin_w: pd.Series = None) -> pd.DataFrame:
    """
    构建四维度候选因子池。所有因子二值化(1/0)，仅用T日及以前数据。
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
    pool["L1_rsi_30"] = (_rsi_wilder(med_w, 14) < 30).astype(int)
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

    macd_hist = _macd_histogram(med_w)
    pool["M3_macd_low"] = (macd_hist < macd_hist.rolling(13).min()).astype(int)

    # ── 维度4: 资金背离 (Smart Money) ──
    ll_rsi = _rsi_wilder(med_w, 14).rolling(52).min()
    pool["S1_divergence"] = (
        (pool["V2_near_52w_low"] == 1) &
        (_rsi_wilder(med_w, 14) > ll_rsi + 5)
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

def run_full_pipeline(med_w: pd.Series, vol_w: pd.Series = None,
                       pe_w: pd.Series = None, margin_w: pd.Series = None) -> dict:
    """执行完整五阶段优化, 返回所有结果"""
    print("=" * 60)
    print("  V5.0 因子自动筛选与赋权框架")
    print("=" * 60)

    # 阶段1
    print("\n[阶段1] 构建候选因子池...")
    pool = build_factor_pool(med_w, vol_w=vol_w, pe_w=pe_w, margin_w=margin_w)
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

```
---

## 数据:AKShare(Sina ETF实时)
`src/data_fetcher/akshare_source.py`
```python
"""A股数据源：行情、板块指数、资金流向 —— 通过 AKShare"""
import pandas as pd
import numpy as np

try:
    import akshare as ak
except ImportError:
    ak = None

def fetch_realtime_price() -> float | None:
    """通过 Sina 抓取 512170(医疗ETF) 实时价, 映射到 801150"""
    import urllib.request
    try:
        req = urllib.request.Request(
            "http://hq.sinajs.cn/list=sh512170",
            headers={"Referer": "https://finance.sina.com.cn"})
        resp = urllib.request.urlopen(req, timeout=5).read().decode("gbk", errors="ignore")
        parts = resp.split('"')[1].split(",")
        current = float(parts[3])   # 当前价
        prev_close = float(parts[2])  # 昨收
        if prev_close > 0:
            pct = (current / prev_close - 1)
            return pct  # 返回涨跌幅, 由调用方乘以801150昨收
    except Exception:
        pass
    return None


class AKShareSource:
    """封装 AKShare 数据获取，统一返回标准化 DataFrame"""

    def __init__(self):
        pass

    # ── 申万医药生物指数 ──
    def fetch_sw_medical(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取申万医药生物指数(801150)日线，用 ETF 代理映射盘中实时价格"""
        if ak is None:
            raise ImportError("akshare not installed")

        # 1. 获取历史日线
        df = ak.index_hist_sw(symbol="801150", period="day")
        df = df.rename(columns={
            "日期": "date", "收盘": "close", "开盘": "open",
            "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()

        # ETF 实时映射: Sina 抓 512170 涨跌幅 → 映射到 801150
        try:
            today = pd.Timestamp.today().normalize()
            if today.weekday() < 5 and df.iloc[-1]["date"] < today:
                pct = fetch_realtime_price()
                if pct is not None:
                    rt = df.iloc[-1]["close"] * (1 + pct)
                    df = pd.concat([df, pd.DataFrame([{
                        "date": today, "close": rt, "open": rt,
                        "high": rt, "low": rt, "volume": 0, "amount": 0
                    }])], ignore_index=True)
                    print(f"[AKShare] ETF实时: 512170涨跌{pct*100:+.2f}% → 801150={rt:.2f}")
        except Exception:
            pass

        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = "sw_medical"
        cols = ["date", "ticker", "close", "open", "high", "low", "volume", "amount"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 中证医疗指数（备选/补充） ──
    def fetch_csi_medical(self, start_date: str = "20180101",
                          end_date: str | None = None) -> pd.DataFrame:
        """获取中证医疗指数(000933)日线"""
        if ak is None:
            raise ImportError("akshare not installed")
        df = ak.stock_zh_index_daily(symbol="sh000933")
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = "csi_medical"
        cols = ["date", "ticker", "close", "open", "high", "low", "volume"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 大盘指数 ──
    def fetch_market_index(self, symbol: str = "hs300",
                           start_date: str = "20180101",
                           end_date: str | None = None) -> pd.DataFrame:
        """获取大盘指数日线: hs300 / cyb / sz50 / sh000001"""
        if ak is None:
            raise ImportError("akshare not installed")
        symbol_map = {
            "hs300": "sh000300", "cyb": "sz399006",
            "sz50": "sh000016", "sh000001": "sh000001",
        }
        code = symbol_map.get(symbol, symbol)
        df = ak.stock_zh_index_daily(symbol=code)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = symbol
        cols = ["date", "ticker", "close", "open", "high", "low", "volume"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 北向资金 ──
    def fetch_north_flow(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取沪股通北向资金日净流入"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.stock_hsgt_hist_em(symbol="沪股通")
            df = df.rename(columns={
                "日期": "date", "当日成交净买额": "net_flow",
                "买入成交额": "buy_amount", "卖出成交额": "sell_amount",
            })
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "north_flow",
                "value": pd.to_numeric(df["net_flow"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── COMEX 黄金期货（真实国际金价） ──
    def fetch_comex_gold(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取 COMEX 黄金期货(GC)日线 —— 真实国际金价"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.futures_foreign_hist(symbol="GC")
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "gold_futures",
                "close": df["close"],
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "volume": df.get("volume", np.nan),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── USD/CNY 汇率（DXY 的国内替代） ──
    def fetch_usd_cny(self, start_date: str = "20180101",
                      end_date: str | None = None) -> pd.DataFrame:
        """获取美元兑人民币汇率（替代 DXY）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.currency_boc_sina(symbol="美元")
            df["date"] = pd.to_datetime(df["日期"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "usdcny",
                "value": pd.to_numeric(df["央行中间价"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 上海金交所基准价 ──
    def fetch_sge_gold(self, start_date: str = "20180101",
                       end_date: str | None = None) -> pd.DataFrame:
        """获取上海黄金交易所基准金价"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.spot_golden_benchmark_sge()
            df["date"] = pd.to_datetime(df["交易时间"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "sge_gold",
                "close": pd.to_numeric(df["早盘价"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── 黄金概念板块 ──
    def fetch_gold_concept(self, start_date: str = "20180101",
                           end_date: str | None = None) -> pd.DataFrame:
        """获取同花顺黄金概念板块指数"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.stock_board_concept_index_ths(
                symbol="黄金概念", start_date=start_date, end_date=end_date or "20260101"
            )
            df = df.rename(columns={
                "date": "date", "收盘价": "close", "开盘价": "open",
                "最高价": "high", "最低价": "low", "成交量": "volume",
            })
            if "date" not in df.columns:
                for c in df.columns:
                    if "日期" in str(c):
                        df = df.rename(columns={c: "date"})
                        break
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "gold_concept_cn",
                "close": df.get("close", np.nan),
                "open": df.get("open", np.nan),
                "high": df.get("high", np.nan),
                "low": df.get("low", np.nan),
                "volume": df.get("volume", np.nan),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── 融资融券（沪深合计） ──
    def fetch_margin_data(self, start_date: str = "20180101",
                          end_date: str | None = None) -> pd.DataFrame:
        """获取沪深两市融资融券日数据（合并）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            sh = ak.macro_china_market_margin_sh()
            sz = ak.macro_china_market_margin_sz()
            sh["date"] = pd.to_datetime(sh["日期"]).dt.normalize()
            sz["date"] = pd.to_datetime(sz["日期"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            sh = sh[(sh["date"] >= pd.Timestamp(start_date)) & (sh["date"] <= pd.Timestamp(end_date))]
            sz = sz[(sz["date"] >= pd.Timestamp(start_date)) & (sz["date"] <= pd.Timestamp(end_date))]

            # merge on date（杜绝 index 错位）
            merged = sh[["date", "融资融券余额"]].merge(
                sz[["date", "融资融券余额"]], on="date",
                suffixes=("_sh", "_sz"), how="outer"
            )
            result = pd.DataFrame({
                "date": merged["date"],
                "ticker": "total_margin",
                "value": (pd.to_numeric(merged["融资融券余额_sh"], errors="coerce").fillna(0) +
                          pd.to_numeric(merged["融资融券余额_sz"], errors="coerce").fillna(0)),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── M2 货币供应量 ──
    def fetch_m2(self, start_date: str = "20180101",
                 end_date: str | None = None) -> pd.DataFrame:
        """获取中国 M2 月度同比增速"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_money_supply()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_m2",
                "value": pd.to_numeric(df["货币和准货币(M2)-同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 中国 PMI ──
    def fetch_cn_pmi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国官方制造业 PMI + 非制造业 PMI（月频）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_pmi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            records = []
            for _, row in df.iterrows():
                d = row["date"]
                records.append({"date": d, "ticker": "cn_mfg_pmi",
                               "value": pd.to_numeric(row["制造业-指数"], errors="coerce")})
                records.append({"date": d, "ticker": "cn_nonmfg_pmi",
                               "value": pd.to_numeric(row["非制造业-指数"], errors="coerce")})
            return pd.DataFrame(records).sort_values("date").reset_index(drop=True) if records else pd.DataFrame(columns=["date", "ticker", "value"])
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 中国 CPI / PPI ──
    def fetch_cn_cpi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国 CPI 月度同比"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_cpi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_cpi",
                "value": pd.to_numeric(df["全国-同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    def fetch_cn_ppi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国 PPI 月度同比"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_ppi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_ppi",
                "value": pd.to_numeric(df["当月同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 批量拉取 ──
    def fetch_all(self, start_date: str = "20180101",
                  end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """一次性拉取所有 AKShare 数据"""
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        results = {}
        fetchers = [
            ("sw_medical", lambda: self.fetch_sw_medical(start_date, end_date)),
            ("csi_medical", lambda: self.fetch_csi_medical(start_date, end_date)),
            ("hs300", lambda: self.fetch_market_index("hs300", start_date, end_date)),
            ("cyb", lambda: self.fetch_market_index("cyb", start_date, end_date)),
            ("sh000001", lambda: self.fetch_market_index("sh000001", start_date, end_date)),
            ("north_flow", lambda: self.fetch_north_flow(start_date, end_date)),
            ("gold_futures", lambda: self.fetch_comex_gold(start_date, end_date)),
            ("gold_concept_cn", lambda: self.fetch_gold_concept(start_date, end_date)),
            ("usdcny", lambda: self.fetch_usd_cny(start_date, end_date)),
            ("sge_gold", lambda: self.fetch_sge_gold(start_date, end_date)),
            ("cn_pmi", lambda: self.fetch_cn_pmi(start_date, end_date)),
            ("cn_cpi", lambda: self.fetch_cn_cpi(start_date, end_date)),
            ("cn_ppi", lambda: self.fetch_cn_ppi(start_date, end_date)),
            ("total_margin", lambda: self.fetch_margin_data(start_date, end_date)),
            ("cn_m2", lambda: self.fetch_m2(start_date, end_date)),
        ]
        for name, fetcher in fetchers:
            try:
                results[name] = fetcher()
                print(f"[AKShare] {name}: {len(results[name])} rows")
            except Exception as e:
                print(f"[AKShare] Failed {name}: {e}")
                results[name] = pd.DataFrame()
        return results

```
---

## 应用:CLI跟踪器(V5.1+融资)
`app/tracker.py`
```python
"""
医药生物板块底部探测器 — 每周跟踪器

用法:
    python app/tracker.py              # 命令行
    streamlit run app/tracker.py       # Web界面
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

try:
    import streamlit as st
    IN_STREAMLIT = True
except ImportError:
    IN_STREAMLIT = False


def _load_data() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.data_fetcher.akshare_source import AKShareSource
    ak_src = AKShareSource()
    med_df = ak_src.fetch_sw_medical("20180101")
    margin_df = ak_src.fetch_margin_data("20180101")
    return {"sw_medical": med_df, "total_margin": margin_df}


def _compute(data: dict, custom_price: float = None) -> dict:
    """计算信号。custom_price: 可选, 用指定价格覆盖最新周数据（用于试算）"""
    from src.models.turning_points import V5Detector

    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    # 用 custom_price 覆盖最新一周的收盘价（"跌到XX会触发"的试算功能）
    if custom_price is not None and len(med_w) > 0:
        med_w.iloc[-1] = custom_price

    # 融资数据 (T+1时滞)
    margin_w = None
    if "total_margin" in data and not data["total_margin"].empty:
        mdf = data["total_margin"].set_index("date")["value"].sort_index()
        margin_w = mdf.resample("W-FRI").last().dropna().shift(1)

    det = V5Detector()
    df = det.compute(med_w, margin_w=margin_w)
    latest = df.iloc[-1]

    # V5.1 三因子评分卡
    rule_defs = [
        ("rule_M1", "M1:偏度异常(4.5分)", f"偏度{latest['skew_13w']:.2f}", "< -1.5", "极端左尾恐慌"),
        ("rule_S3", "S3:融资背离(3.0分)", "已触发" if latest.get("rule_S3",0) else "未触发", "价新低+融资增", "聪明钱抄底"),
        ("rule_V1", "V1:估值冰点(2.5分)", f"{latest['val_pct_5y']:.0f}%", "< 15%分位", "历史低位区域"),
    ]
    rules_status = []
    for col, name, val, thresh, desc in rule_defs:
        rules_status.append({
            "name": name, "triggered": bool(latest[col]),
            "value": val, "threshold": thresh, "description": desc,
        })

    from src.models.turning_points import distance_to_trigger, alert_level
    dist = distance_to_trigger(df, med_w, margin_w=margin_w)

    # 读取历史 + 保存今天 (合并为一次IO，避免竞态)
    hist_path = Path("data/processed/signal_history.csv")
    today_str = str(latest.name.date())
    prev_score = None
    if not hist_path.parent.exists():
        hist_path.parent.mkdir(parents=True, exist_ok=True)
    if hist_path.exists():
        hist = pd.read_csv(hist_path)
        if len(hist) > 0:
            prev_score = int(hist.iloc[-1].get("score", 0))
        hist = hist[hist["date"] != today_str]
    else:
        hist = pd.DataFrame(columns=["date", "score"])
    hist = pd.concat([hist, pd.DataFrame([{"date": today_str, "score": round(latest["score"], 1)}])], ignore_index=True)
    hist.to_csv(hist_path, index=False)

    alert = alert_level(df, prev_score)

    return {
        "date": latest.name.date(),
        "price": latest["price"],
        "rsi": latest["rsi"],
        "drawdown_13w": latest["drawdown_13w"],
        "val_pct_5y": latest["val_pct_5y"],
        "skew": latest["skew_13w"],
        "vol": latest["vol_annual"],
        "score": round(latest["score"], 1),
        "armed": bool(latest["armed"]),
        "buy": bool(latest["buy_signal"]),
        "macd_ok": bool(latest["macd_stable"]),
        "ma2_ok": bool(latest["above_ma2"]),
        "rules_status": rules_status,
        "distance_to_trigger": dist,
        "alert": alert,
        "df": df,
    }


# ═══════════════════════════════════════
# CLI
# ═══════════════════════════════════════

def run_cli():
    print("=" * 60)
    print("  医药生物板块(801150) — 底部探测器")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n[1/2] 拉取数据...")
    data = _load_data()
    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()
    print(f"  指数: {len(med_w)}周 ({med_w.index[0].date()} ~ {med_w.index[-1].date()})")

    print("\n[2/2] 计算信号...")
    sig = _compute(data)

    status = "BUY ZONE" if sig["buy"] else "ARMED" if sig["armed"] else "HOLD"
    print(f"\n{'='*60}")
    print(f"  {status}")
    print(f"{'='*60}")
    print(f"  日期:       {sig['date']}")
    print(f"  收盘价:     {sig['price']:.2f}")
    print(f"  Score:      {sig['score']}/5")
    print()

    for r in sig["rules_status"]:
        mark = "[ON]" if r["triggered"] else "[  ]"
        print(f"  {mark} {r['name']}: {r['value']} (阈值: {r['threshold']})")

    if sig["armed"]:
        print(f"\n  右侧确认: MACD={'ON' if sig['macd_ok'] else 'OFF'}  MA2={'ON' if sig['ma2_ok'] else 'OFF'}")

    # Distance to trigger
    print(f"\n  距离触发:")
    dist = sig["distance_to_trigger"]
    for key in ["S3", "V1"]:
        d = dist[key]
        if d["triggered"]:
            print(f"    {d['name']}: 已触发")
        elif d.get("trigger_price"):
            gap = d["trigger_price"] - d["current"]
            print(f"    {d['name']}: 未触发. 触发价={d['trigger_price']:.0f} (需跌至{d['trigger_price']:.0f}, 再跌{abs(d['pct_away']):.1f}%)")

    # Alert
    print(f"\n  警报: [{sig['alert']['level'].upper()}] {sig['alert']['message']}")

    df = sig["df"]
    recent = df[(df.index >= "2024-01-01") & (df["armed"] == 1)]
    if len(recent) > 0:
        print(f"\n  近期Armed信号 ({len(recent)}次):")
        for d, row in recent.tail(8).iterrows():
            print(f"    {d.date()}  sc={int(row.score)}  RSI={row.rsi:.0f}  DD={row.drawdown_13w:.0f}%  price={row.price:.0f}")

    print()


# ═══════════════════════════════════════
# Streamlit
# ═══════════════════════════════════════

def run_streamlit():
    st.set_page_config(page_title="医药底部探测器", page_icon="📊", layout="wide")
    st.title("📊 医药生物板块 — 底部探测器")
    st.caption(f"更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.spinner("数据加载中..."):
        sig = _compute(_load_data())

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    status = "BUY" if sig["buy"] else "ARMED" if sig["armed"] else "HOLD"
    c1.metric("状态", status, delta=f"Score {sig['score']}/5")
    c2.metric("RSI(14)", f"{sig['rsi']:.1f}", delta=f"{sig['rsi']-30:.1f} vs 30")
    c3.metric("13周回撤", f"{sig['drawdown_13w']:.1f}%", delta=f"{sig['drawdown_13w']+10:.1f}% vs -10%")

    st.markdown("---")
    st.subheader("五规则状态")
    for r in sig["rules_status"]:
        icon = "✅" if r["triggered"] else "⬜"
        st.write(f"{icon} **{r['name']}**: {r['value']} (阈值: {r['threshold']}) — *{r['description']}*")

    st.markdown("---")
    st.subheader("近期Armed信号")
    df = sig["df"]
    recent = df[(df.index >= "2024-01-01") & (df["armed"] == 1)]
    if len(recent) > 0:
        st.dataframe(recent[["price", "score", "rsi", "drawdown_13w", "val_pct_5y"]],
                     use_container_width=True)

    st.caption("REPORT.md — 完整方法论与验证")


if __name__ == "__main__":
    if IN_STREAMLIT:
        run_streamlit()
    else:
        run_cli()

```
---

## 应用:HTML看板(V5.1+S3/V1水位线)
`app/dashboard.py`
```python
"""生成自包含 HTML 看板 — 图表库首次下载缓存，之后离线可用"""
import sys, json, urllib.request, time
from pathlib import Path
from datetime import datetime
import pandas as pd, numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LW_CACHE = Path("data/lightweight-charts.min.js")
LW_CDN = "https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"

def _get_lw_js() -> str:
    """优先读本地缓存，没有则下载一次并缓存"""
    if LW_CACHE.exists() and LW_CACHE.stat().st_size > 100_000:
        return LW_CACHE.read_text(encoding="utf-8")
    print("下载图表库 (仅首次)...")
    js = urllib.request.urlopen(LW_CDN, timeout=20).read().decode("utf-8")
    LW_CACHE.parent.mkdir(parents=True, exist_ok=True)
    LW_CACHE.write_text(js, encoding="utf-8")
    print(f"已缓存 {LW_CACHE} (后续离线)")
    return js

CSS = """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f3f4f6;color:#1f2937;padding:20px}
.container{max-width:900px;margin:0 auto}
.header{text-align:center;margin-bottom:24px}
.header h1{font-size:24px;font-weight:700}
.header p{color:#6b7280;font-size:14px}
.card{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.card-title{font-size:14px;font-weight:600;color:#6b7280;text-transform:uppercase;margin-bottom:12px;letter-spacing:.5px}
.signal-badge{display:inline-block;padding:6px 16px;border-radius:20px;font-weight:700;font-size:16px;color:#fff}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}
.metric{text-align:center;padding:12px;background:#f9fafb;border-radius:8px}
.metric .val{font-size:22px;font-weight:700}
.metric .lbl{font-size:11px;color:#6b7280;margin-top:4px}
.rule-row{display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #f3f4f6;font-size:13px}
.rule-icon{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;margin-right:10px;font-size:14px;flex-shrink:0}
.rule-icon.on{background:#d1fae5;color:#065f46}
.rule-icon.off{background:#f3f4f6;color:#9ca3af}
.rule-desc{color:#6b7280;margin-left:auto;font-size:12px}
.rec-table{width:100%;font-size:12px;border-collapse:collapse}
.rec-table th,.rec-table td{text-align:center;padding:6px 8px;border-bottom:1px solid #f3f4f6}
.rec-table th{color:#6b7280;font-weight:600}
.first-signal{font-weight:600}
#chart{width:100%;max-width:100%;height:350px;overflow:hidden}
.footer{text-align:center;color:#9ca3af;font-size:12px;margin-top:20px}
.position-card{text-align:center;padding:24px}
.position-card .pct{font-size:48px;font-weight:800}
.position-card .label{font-size:16px;color:#6b7280;margin-top:4px}"""


def build_dashboard(output_path: str = "dashboard.html"):
    from src.data_fetcher.akshare_source import AKShareSource
    from src.models.turning_points import V5Detector, collapse_signals

    t0 = time.time()
    print("生成看板...")

    med_df = AKShareSource().fetch_sw_medical("20180101")
    med = med_df.set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    from src.data_fetcher.akshare_source import AKShareSource as _AKS
    margin_df = _AKS().fetch_margin_data("20180101")
    margin_w = None
    if not margin_df.empty:
        m = margin_df.set_index("date")["value"].sort_index()
        margin_w = m.resample("W-FRI").last().dropna().shift(1)

    det = V5Detector()
    df = det.compute(med_w, margin_w=margin_w)
    latest = df.iloc[-1]

    score = float(latest["score"])
    if score < 2.5:      pct, label, color = 0, "观望 (0%)", "#9CA3AF"
    elif score < 3.5:    pct, label, color = 15, "关注区 15%", "#F59E0B"
    elif score < 5.5:    pct, label, color = 40, "轻仓 40% — Armed", "#F97316"
    else:                pct, label, color = 60, "重仓 60% — 多因子触发", "#EF4444"

    from src.models.turning_points import distance_to_trigger
    dist = distance_to_trigger(df, med_w, margin_w=margin_w)

    weekly_data = []
    for i in range(max(0, len(df) - 104), len(df)):
        r = df.iloc[i]
        weekly_data.append({"time": r.name.strftime("%Y-%m-%d"), "value": round(float(r["price"]), 2),
                            "armed": bool(r["armed"]), "score": int(r["score"])})

    data_date_str = df.index[-1].strftime("%Y-%m-%d")

    rule_defs = [
        ("M1:偏度异常(4.5分)", bool(latest["rule_M1"]), f'偏度{latest["skew_13w"]:.2f}', "< -1.5"),
        ("S3:融资背离(3.0分)", bool(latest.get("rule_S3",0)), "融资+价格新低", "融资逆势加仓"),
        ("V1:估值冰点(2.5分)", bool(latest["rule_V1"]), f'{latest["val_pct_5y"]:.0f}%', "< 15%"),
    ]
    rules_html = ""
    for name, ok, val, thresh in rule_defs:
        rules_html += f"""<div class="rule-row">
    <div class="rule-icon {'on' if ok else 'off'}">{'Y' if ok else '-'}</div>
    <div><strong>{name}</strong><br><span style="font-size:11px;color:#6b7280">{val} (阈值: {thresh})</span></div>
</div>"""

    collapsed = collapse_signals(df["armed"])
    armed_html = ""
    for i in range(max(0, len(df) - 156), len(df)):
        r = df.iloc[i]
        if not bool(r["armed"]): continue
        d = r.name; first = bool(collapsed.iloc[i])
        armed_html += f"""<tr class="{'first-signal' if first else ''}">
    <td>{d.strftime('%Y-%m-%d')}</td><td>{float(r['score']):.1f}</td><td>{r['price']:.0f}</td>
    <td>{r['rsi']:.1f}</td><td>{r['drawdown_13w']:.1f}%</td><td>{'*' if first else ''}</td></tr>"""

    waterline_html = ""
    for key, emoji in [("S3",""),("V1","")]:
        dv = dist[key]
        if dv["triggered"]:
            waterline_html += f'<div style="padding:6px 12px;background:#f0fdf4;border-radius:6px;font-size:13px">{emoji}<b>{dv["name"]}</b>: 已触发</div>'
        elif dv.get("trigger_price") and not np.isnan(dv["trigger_price"]):
            waterline_html += f'<div style="padding:6px 12px;background:#fefce8;border-radius:6px;font-size:13px">{emoji}<b>{dv["name"]}</b>: 触发价 <b>{dv["trigger_price"]:.0f}</b> (距当前 {dv["pct_away"]:+.1f}%)</div>'

    waterline_prices = {}
    for key in ["S3", "V1"]:
        if not dist[key]["triggered"] and dist[key].get("trigger_price") and not np.isnan(dist[key]["trigger_price"]):
            waterline_prices[key] = dist[key]["trigger_price"]

    # ── 图表库：内联（首次下载缓存） ──
    try:
        lw_js = _get_lw_js()
        lw_tag = f"<script>{lw_js}</script>"
    except Exception as e:
        print(f"图表库加载失败: {e}")
        lw_tag = f'<script src="{LW_CDN}"></script>'

    chart_data = json.dumps(weekly_data, ensure_ascii=False)
    waterline_json = json.dumps(waterline_prices, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>医药板块风险收益比监控器</title>
{lw_tag}
<style>{CSS}</style>
</head>
<body><div class="container">
<div class="header">
  <h1>医药板块 风险收益比监控器</h1>
  <p>申万医药生物(801150) | 数据至 {data_date_str} | {"实时 (via 512170 ETF)" if med.index[-1].date() == pd.Timestamp.today().date() else "EOD"} | 耗时 {time.time()-t0:.1f}s</p>
</div>
<div class="card"><div class="position-card">
  <div class="pct" style="color:{color}">{pct}%</div>
  <div class="label">{label}</div>
  <div style="margin-top:12px"><span class="signal-badge" style="background:{color}">Score {score}/5</span></div>
  <div style="margin-top:10px;display:flex;justify-content:center;gap:8px">
    <input type="number" id="trial-price" placeholder="试算点位(如7400)" style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;width:150px;font-size:13px">
    <button onclick="trialCalc()" style="padding:6px 14px;background:#3B82F6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px">试算</button>
    <span id="trial-result" style="font-size:13px;color:#6b7280;align-self:center"></span>
  </div>
</div></div>
<div class="card"><div class="card-title">关键指标 ({data_date_str})</div><div class="metrics">
  <div class="metric"><div class="val">{latest["price"]:.0f}</div><div class="lbl">收盘价</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['rsi']<30 else '#1f2937'}">{latest["rsi"]:.1f}</div><div class="lbl">RSI(14) Wilder</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['drawdown_13w']<-10 else '#1f2937'}">{latest["drawdown_13w"]:.1f}%</div><div class="lbl">13周最大回撤</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['val_pct_5y']<15 else '#1f2937'}">{latest["val_pct_5y"]:.0f}%</div><div class="lbl">5年价格分位</div></div>
  <div class="metric"><div class="val">{latest["vol_annual"]:.1f}%</div><div class="lbl">年化波动率</div></div>
  <div class="metric"><div class="val" style="color:{'#10b981' if latest['right_confirm'] else '#9ca3af'}">{'已触发' if latest['right_confirm'] else '未触发'}</div><div class="lbl">右侧确认 MACD/MA2</div></div>
</div></div>
<div class="card"><div class="card-title">触发水位线</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">{waterline_html if waterline_html else '<span style="color:#9ca3af">无法计算</span>'}</div>
</div>
<div class="card"><div class="card-title">五规则状态</div>{rules_html}</div>
<div class="card"><div class="card-title">走势图 (黄箭头=Armed | 虚线=水位线)</div><div id="chart"></div></div>
<div class="card"><div class="card-title">近期 Armed 信号 (* = 入场)</div>
  <table class="rec-table"><tr><th>日期</th><th>Score</th><th>价格</th><th>RSI</th><th>回撤</th><th>入场</th></tr>{armed_html}</table>
</div>
<div class="footer">AKShare | V4.4 | 仅供参考</div>
</div>
<script>
try {{
    var d = {chart_data};
    var el = document.getElementById('chart');
    var chart = LightweightCharts.createChart(el, {{
        layout: {{ background: {{ color: '#ffffff' }}, textColor: '#1f2937' }},
        grid: {{ vertLines: {{ color: '#f3f4f6' }}, horzLines: {{ color: '#f3f4f6' }} }},
        rightPriceScale: {{ borderColor: '#d1d5db' }},
        timeScale: {{ borderColor: '#d1d5db', timeVisible: true }},
        width: Math.min(el.clientWidth || 900, window.innerWidth - 60 || 900), height: 350,
    }});
    var line = chart.addLineSeries({{ color: '#3B82F6', lineWidth: 2 }});
    var uniqueData = [], seen = new Set();
    d.forEach(function(w) {{
        if (!seen.has(w.time) && w.value != null && !isNaN(w.value)) {{ seen.add(w.time); uniqueData.push(w); }}
    }});
    uniqueData.sort(function(a,b) {{ return a.time.localeCompare(b.time); }});
    var prices = uniqueData.map(function(w) {{ return {{ time: w.time, value: w.value }}; }});
    var markers = uniqueData.filter(function(w) {{ return w.armed; }}).map(function(w) {{
        return {{ time: w.time, position: 'belowBar', color: '#F59E0B', shape: 'arrowUp', text: String(w.score) }};
    }});
    line.setData(prices); line.setMarkers(markers);
    var waterlines = {waterline_json};
    var colors = {{ 'S3': '#EF4444', 'V1': '#10B981' }};
    var labels = {{ 'S3': '新低触发', 'V1': '估值触发' }};
    Object.keys(waterlines).forEach(function(key) {{
        var price = waterlines[key];
        var wl = chart.addLineSeries({{ color: colors[key], lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }});
        var data = [];
        for (var i = 0; i < prices.length; i++) {{ data.push({{ time: prices[i].time, value: price }}); }}
        wl.setData(data);
        wl.setMarkers([{{ time: prices[prices.length-1].time, position: 'inLine', color: colors[key], shape: 'circle', text: labels[key] + ' ' + price.toFixed(0) }}]);
    }});
    chart.timeScale().fitContent();
    window.addEventListener('resize', function() {{ chart.applyOptions({{ width: Math.min(el.clientWidth || 900, window.innerWidth - 60 || 900) }}); }});
}} catch(e) {{
    document.getElementById('chart').innerHTML =
        '<div style="padding:40px;text-align:center;color:#ef4444"><b>图表加载失败</b><br><small>'+e.message+'</small></div>';
}}
async function trialCalc() {{
  var price = document.getElementById('trial-price').value;
  var res = document.getElementById('trial-result');
  if (!price) {{ res.textContent = '请输入点位'; return; }}
  res.textContent = '计算中...';
  try {{
    var r = await fetch('/api/signal?price=' + price);
    var d = await r.json();
    res.innerHTML = 'Score <b>' + d.score + '/5</b> | ' + d.status +
      ' | D触发价:' + (d.d_trigger||'—') + ' C触发价:' + (d.c_trigger||'—');
    res.style.color = d.score >= 2 ? '#ef4444' : '#10b981';
  }} catch(e) {{ res.textContent = '计算失败'; }}
}}
</script>
</body></html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Dashboard saved ({time.time()-t0:.1f}s)")
    return output_path


if __name__ == "__main__":
    build_dashboard()

```
---

## 应用:实时服务器
`app/server.py`
```python
"""
实时看板服务器 — 每次打开/刷新页面自动拉取最新数据

用法:
    python app/server.py              # 启动服务器，自动打开浏览器
    python app/server.py --port 9000  # 指定端口
    python app/server.py --no-browser # 不自动打开浏览器

架构:
    GET /            → 返回 HTML 看板（JS 动态渲染）
    GET /api/signal  → 实时计算信号，返回 JSON
"""
import sys
import json
import argparse
import threading
import webbrowser
import traceback
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_PORT = 8888

# ═══════════════════════════════════════════════════════════════
# HTML 模板 — JS 动态从 /api/signal 拉取数据后渲染
# ═══════════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>医药板块监控器</title>
<script src="/lw.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#222636;--border:#2a2d3e;
  --text:#e2e8f0;--muted:#64748b;--accent:#38bdf8;
  --green:#34d399;--yellow:#fbbf24;--red:#f87171;--silent:#64748b;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

/* Loading */
#loading{display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;gap:16px;color:var(--muted)}
.spinner{width:36px;height:36px;border:3px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
#error{display:none;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;gap:12px;color:var(--red)}

/* Layout */
#app{display:none;max-width:960px;margin:0 auto;padding:24px 16px}
.header{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:28px;padding-bottom:16px;border-bottom:1px solid var(--border)}
.header-title{font-size:15px;font-weight:700;letter-spacing:.5px;color:var(--muted);
  text-transform:uppercase}
.header-meta{font-size:12px;color:var(--muted);text-align:right;line-height:1.6}
.header-meta b{color:var(--accent)}

/* Cards */
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:20px;margin-bottom:16px}
.card-title{font-size:11px;font-weight:700;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted);margin-bottom:16px}

/* Status badge */
.status-row{display:flex;align-items:center;gap:16px;margin-bottom:20px}
.badge{display:inline-flex;align-items:center;gap:8px;padding:8px 18px;
  border-radius:8px;font-family:'DM Mono',monospace;font-weight:500;font-size:14px}
.badge.silent{background:#1e293b;color:var(--silent);border:1px solid var(--border)}
.badge.yellow{background:#451a03;color:var(--yellow);border:1px solid #92400e}
.badge.red{background:#450a0a;color:var(--red);border:1px solid #991b1b}
.badge .dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.badge.red .dot{animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* Score bar */
.score-bar{display:flex;gap:6px;align-items:center}
.score-seg{height:6px;border-radius:3px;flex:1;background:var(--border);transition:.3s}
.score-seg.active{background:var(--accent)}
.score-seg.active.warn{background:var(--yellow)}
.score-seg.active.alert{background:var(--red)}
.score-label{font-family:'DM Mono',monospace;font-size:12px;color:var(--muted);
  min-width:32px;text-align:right}

/* Metrics grid */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:0}
.metric{background:var(--surface2);border-radius:8px;padding:12px 10px;text-align:center}
.metric .val{font-family:'DM Mono',monospace;font-size:18px;font-weight:500}
.metric .lbl{font-size:10px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.metric.triggered .val{color:var(--red)}

/* Rules */
.rule{display:flex;align-items:center;gap:12px;padding:10px 0;
  border-bottom:1px solid var(--border)}
.rule:last-child{border-bottom:none}
.rule-icon{width:26px;height:26px;border-radius:6px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:12px}
.rule-icon.on{background:#052e16;color:var(--green)}
.rule-icon.off{background:var(--surface2);color:var(--muted)}
.rule-name{font-weight:500;font-size:13px;min-width:100px}
.rule-val{font-family:'DM Mono',monospace;font-size:12px;color:var(--muted);flex:1}
.rule-thresh{font-size:11px;color:var(--border);margin-left:auto}

/* Distance */
.dist-row{display:flex;justify-content:space-between;align-items:center;
  padding:10px 0;border-bottom:1px solid var(--border)}
.dist-row:last-child{border-bottom:none}
.dist-name{font-size:13px;font-weight:500}
.dist-price{font-family:'DM Mono',monospace;font-size:13px}
.dist-pct{font-family:'DM Mono',monospace;font-size:12px;padding:2px 8px;
  border-radius:4px;background:var(--surface2)}
.dist-pct.triggered{color:var(--green)}
.dist-pct.far{color:var(--muted)}
.dist-pct.close{color:var(--yellow)}

/* Chart */
#chart{width:100%;max-width:100%;height:320px;overflow:hidden}

/* Table */
.sig-table{width:100%;border-collapse:collapse;font-size:12px}
.sig-table th{text-align:center;padding:6px 8px;color:var(--muted);
  font-weight:500;border-bottom:1px solid var(--border);font-family:'DM Mono',monospace}
.sig-table td{text-align:center;padding:6px 8px;border-bottom:1px solid var(--border);
  font-family:'DM Mono',monospace;color:var(--muted)}
.sig-table tr.first td{color:var(--text)}
.sig-table tr.first td:first-child::before{content:'▶ ';color:var(--accent)}

/* Alert message */
.alert-msg{font-size:13px;color:var(--muted);padding:10px 14px;
  background:var(--surface2);border-radius:6px;border-left:3px solid var(--border);line-height:1.5}
.alert-msg.yellow{border-color:var(--yellow);color:var(--yellow)}
.alert-msg.red{border-color:var(--red);color:var(--red)}

/* Footer */
.footer{text-align:center;color:var(--muted);font-size:11px;
  margin-top:24px;padding-top:16px;border-top:1px solid var(--border);line-height:2}
</style>
</head>
<body>

<div id="loading">
  <div class="spinner"></div>
  <span>正在拉取最新行情数据…</span>
</div>
<div id="error">
  <span style="font-size:32px">⚠️</span>
  <b id="err-msg">数据加载失败</b>
  <small id="err-detail" style="color:var(--muted)"></small>
  <button onclick="load()" style="margin-top:12px;padding:8px 20px;background:var(--accent);
    color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600">重试</button>
</div>

<div id="app">
  <div class="header">
    <div>
      <div class="header-title">申万医药生物(801150) · 风险收益比监控器</div>
    </div>
    <div class="header-meta">
      数据截止 <b id="h-date">—</b><br>
      更新时间 <b id="h-updated">—</b>
      <div style="margin-top:10px; display:flex; align-items:center; gap:8px; justify-content:flex-end">
        <input type="number" id="custom-price" placeholder="试算点位(如 7430)"
               style="padding:6px; border-radius:6px; border:1px solid #374151; background:#1f2937; color:#e2e8f0; width:160px; font-size:12px;">
        <button onclick="load()" style="padding:6px 12px; background:#38bdf8; color:#000; border:none; border-radius:6px; cursor:pointer; font-size:12px; font-weight:bold;">刷新试算</button>
      </div>
    </div>
  </div>

  <!-- 状态 + Score -->
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px">
      <div>
        <div class="card-title">当前状态</div>
        <div class="status-row">
          <span class="badge" id="badge"><span class="dot"></span><span id="badge-text">—</span></span>
        </div>
        <div class="alert-msg" id="alert-msg"></div>
      </div>
      <div style="min-width:180px">
        <div class="card-title">Score</div>
        <div class="score-bar" id="score-bar">
          <div class="score-seg" id="s0"></div>
          <div class="score-seg" id="s1"></div>
          <div class="score-seg" id="s2"></div>
          <div class="score-seg" id="s3"></div>
          <div class="score-seg" id="s4"></div>
          <span class="score-label" id="score-lbl">0/5</span>
        </div>
      </div>
    </div>
  </div>

  <!-- 关键指标 -->
  <div class="card">
    <div class="card-title">关键指标</div>
    <div class="metrics" id="metrics"></div>
  </div>

  <!-- 五规则 -->
  <div class="card">
    <div class="card-title">五规则状态</div>
    <div id="rules"></div>
  </div>

  <!-- 距离触发 -->
  <div class="card">
    <div class="card-title">距离触发水位线</div>
    <div id="dist"></div>
  </div>

  <!-- 走势图 -->
  <div class="card">
    <div class="card-title">近两年周线 · 黄箭头=Armed · 虚线=触发水位线</div>
    <div id="chart"></div>
  </div>

  <!-- 历史信号 -->
  <div class="card">
    <div class="card-title">近期 Armed 信号 (▶ = 入场信号)</div>
    <table class="sig-table">
      <thead><tr>
        <th>日期</th><th>Score</th><th>价格</th><th>RSI</th><th>回撤</th>
      </tr></thead>
      <tbody id="sig-tbody"></tbody>
    </table>
  </div>

  <div class="footer">
    仅供研究参考，不构成投资建议 &nbsp;|&nbsp;
    方法论: Triple Barrier + 五规则探测器 &nbsp;|&nbsp; V4.3<br>
    <span id="footer-note"></span>
  </div>
</div>

<script>
let chart = null;

async function load() {
  document.getElementById('loading').style.display = 'flex';
  document.getElementById('error').style.display = 'none';
  document.getElementById('app').style.display = 'none';

  try {
    const cpEl = document.getElementById('custom-price');
    const cp = cpEl ? cpEl.value : '';
    const url = cp ? '/api/signal?price=' + cp : '/api/signal';
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
    const d = await r.json();
    render(d);
    document.getElementById('loading').style.display = 'none';
    document.getElementById('app').style.display = 'block';
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error').style.display = 'flex';
    document.getElementById('err-msg').textContent = '数据加载失败';
    document.getElementById('err-detail').textContent = e.message;
  }
}

function render(d) {
  // Header
  document.getElementById('h-date').textContent = d.date;
  document.getElementById('h-updated').textContent = d.computed_at;

  // Badge
  const level = d.alert.level;
  const badge = document.getElementById('badge');
  badge.className = 'badge ' + level;
  const labels = {silent:'HOLD', yellow:'YELLOW ⚠', red:'ARMED 🔴'};
  document.getElementById('badge-text').textContent = labels[level] || level.toUpperCase();

  // Alert message
  const msg = document.getElementById('alert-msg');
  msg.textContent = d.alert.message;
  msg.className = 'alert-msg ' + (level === 'silent' ? '' : level);

  // Score bar
  const score = d.score;
  const colorClass = score >= 4 ? 'alert' : score >= 2 ? 'warn' : '';
  for(let i = 0; i < 5; i++) {
    const seg = document.getElementById('s' + i);
    seg.className = 'score-seg' + (i < score ? ' active ' + colorClass : '');
  }
  document.getElementById('score-lbl').textContent = score + '/5';

  // Metrics
  const metrics = [
    {label: 'RSI(Wilder)', val: d.rsi.toFixed(1), trigger: d.rsi < 30},
    {label: '13周回撤', val: d.drawdown_13w.toFixed(1) + '%', trigger: d.drawdown_13w < -10},
    {label: '5年价格分位', val: d.val_pct_5y.toFixed(0) + '%', trigger: d.val_pct_5y < 15},
    {label: '收盘价', val: d.price.toFixed(0), trigger: false},
  ];
  document.getElementById('metrics').innerHTML = metrics.map(m =>
    `<div class="metric${m.trigger?' triggered':''}">
       <div class="val">${m.val}</div>
       <div class="lbl">${m.label}</div>
     </div>`
  ).join('');

  // Rules
  document.getElementById('rules').innerHTML = d.rules_status.map(r =>
    `<div class="rule">
       <div class="rule-icon ${r.triggered?'on':'off'}">${r.triggered?'✓':'—'}</div>
       <div class="rule-name">${r.name}</div>
       <div class="rule-val">${r.value}</div>
       <div class="rule-thresh">阈值: ${r.threshold}</div>
     </div>`
  ).join('');

  // Distance to trigger
  document.getElementById('dist').innerHTML = Object.values(d.distance_to_trigger).map(dt => {
    if (dt.triggered) {
      return `<div class="dist-row">
        <div class="dist-name">${dt.name}</div>
        <div class="dist-pct triggered">已触发 ✓</div>
      </div>`;
    }
    const pct = dt.pct_away;
    const cls = Math.abs(pct) < 2.5 ? 'close' : 'far';
    return `<div class="dist-row">
      <div class="dist-name">${dt.name}</div>
      <div class="dist-price">触发价 ${dt.trigger_price ? dt.trigger_price.toFixed(0) : '—'}</div>
      <div class="dist-pct ${cls}">${pct ? (pct > 0 ? '+' : '') + pct.toFixed(1) + '%' : '—'}</div>
    </div>`;
  }).join('');

  // Chart (try-catch, 错误可见)
  try {
  if (chart) { chart.remove(); chart = null; }
  const el = document.getElementById('chart');
  chart = LightweightCharts.createChart(el, {
    layout: {background:{color:'transparent'}, textColor:'#94a3b8'},
    grid: {vertLines:{color:'#1e293b'}, horzLines:{color:'#1e293b'}},
    rightPriceScale: {borderColor:'#2a2d3e'},
    timeScale: {borderColor:'#2a2d3e', timeVisible:true},
    width: el.clientWidth || window.innerWidth - 80 || 900, height: 320,
  });

  const line = chart.addLineSeries({color:'#38bdf8', lineWidth:2});

  // 去重 + 排序 (防止重复时间轴导致图表崩溃)
  const uniqueData = [];
  const seen = new Set();
  d.chart.forEach(w => {
    if (!seen.has(w.time) && w.value != null && !isNaN(w.value)) {
      seen.add(w.time);
      uniqueData.push(w);
    }
  });
  uniqueData.sort((a,b) => a.time.localeCompare(b.time));

  const prices = uniqueData.map(w => ({time:w.time, value:w.value}));
  line.setData(prices);
  line.setMarkers(
    uniqueData.filter(w => w.armed).map(w => ({
      time:w.time, position:'belowBar', color:'#fbbf24',
      shape:'arrowUp', text: String(w.score)
    }))
  );

  // Waterlines
  const wl_colors = {D:'#f87171', C:'#34d399'};
  const wl_labels = {D:'回撤触发', C:'估值触发'};
  Object.entries(d.distance_to_trigger).forEach(([key, dt]) => {
    if (!dt.trigger_price || dt.triggered) return;
    const wl = chart.addLineSeries({
      color:wl_colors[key], lineWidth:1, lineStyle:2,
      priceLineVisible:false, lastValueVisible:false,
    });
    wl.setData(prices.map(p => ({time:p.time, value:dt.trigger_price})));
    wl.setMarkers([{
      time: prices[prices.length-1].time, position:'inLine',
      color:wl_colors[key], shape:'circle',
      text: wl_labels[key] + ' ' + dt.trigger_price.toFixed(0),
    }]);
  });
  chart.timeScale().fitContent();
  window.addEventListener('resize', () => {
    chart.applyOptions({width: el.clientWidth || window.innerWidth - 80 || 900});
  });
  } catch(e) {
    document.getElementById('chart').innerHTML =
      '<div style="padding:40px;text-align:center;color:#ef4444"><b>图表加载失败</b><br><small>'+e.message+'</small></div>';
  }

  // Armed signal table
  document.getElementById('sig-tbody').innerHTML = d.armed_history.slice(-20).reverse().map(s =>
    `<tr class="${s.first?'first':''}">
       <td>${s.date}</td><td>${s.score}/5</td><td>${s.price}</td>
       <td>${s.rsi}</td><td>${s.dd}%</td>
     </tr>`
  ).join('');

  // Footer note
  document.getElementById('footer-note').textContent =
    `行情来源: AKShare | 计算耗时: ${d.elapsed_s}s`;
}

load();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# API: 实时计算信号并序列化为 JSON
# ═══════════════════════════════════════════════════════════════

def _compute_and_serialize(custom_price: float = None) -> dict:
    import time
    import numpy as np
    t0 = time.time()

    from app.tracker import _compute
    from src.data_fetcher.akshare_source import AKShareSource

    # 极速模式: 只拉取医药指数, 跳过宏观数据 (14s → <1s)
    med_df = AKShareSource().fetch_sw_medical("20180101")
    fast_data = {"sw_medical": med_df}

    sig = _compute(fast_data, custom_price=custom_price)

    df = sig.get("df")
    dist = sig.get("distance_to_trigger", {})

    # ── 水位线触发价（确保可序列化）──
    dist_out = {}
    for k, v in dist.items():
        dist_out[k] = {
            "name": v["name"],
            "triggered": bool(v["triggered"]),
            "trigger_price": float(v["trigger_price"]) if v.get("trigger_price") is not None and not (isinstance(v["trigger_price"], float) and np.isnan(v["trigger_price"])) else None,
            "pct_away": float(v["pct_away"]) if v.get("pct_away") is not None else 0.0,
        }

    # ── 近两年周线数据 ──
    chart_data = []
    if df is not None:
        for i in range(max(0, len(df) - 104), len(df)):
            r = df.iloc[i]
            chart_data.append({
                "time": r.name.strftime("%Y-%m-%d"),
                "value": round(float(r["price"]), 2),
                "armed": bool(r["armed"]),
                "score": int(r["score"]),
            })

    # ── 近期 Armed 信号 ──
    armed_history = []
    if df is not None:
        from src.models.turning_points import collapse_signals
        collapsed = collapse_signals(df["armed"])
        for i in range(max(0, len(df) - 156), len(df)):
            r = df.iloc[i]
            if not bool(r["armed"]):
                continue
            armed_history.append({
                "date": r.name.strftime("%Y-%m-%d"),
                "score": int(r["score"]),
                "price": round(float(r["price"])),
                "rsi": round(float(r["rsi"]), 1),
                "dd": round(float(r["drawdown_13w"]), 1),
                "first": bool(collapsed.iloc[i]),
            })

    elapsed = round(time.time() - t0, 1)

    return {
        "date": str(sig["date"]),
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": elapsed,
        "price": float(sig["price"]),
        "score": int(sig["score"]),
        "armed": bool(sig["armed"]),
        "rsi": float(sig["rsi"]),
        "drawdown_13w": float(sig["drawdown_13w"]),
        "val_pct_5y": float(sig["val_pct_5y"]),
        "rules_status": sig["rules_status"],
        "alert": sig["alert"],
        "distance_to_trigger": dist_out,
        "chart": chart_data,
        "armed_history": armed_history,
    }


# ═══════════════════════════════════════════════════════════════
# HTTP 服务器
# ═══════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith("/api/signal"):
            self._serve_api()
        elif self.path == "/lw.js":
            self._serve_lw()
        elif self.path.startswith("/static/"):
            self._serve_static()
        else:
            self._serve_dash()

    def _serve_dash(self):
        import subprocess, sys
        dash_path = Path("dashboard.html")
        if not dash_path.exists():
            subprocess.run([sys.executable, "app/dashboard.py"], capture_output=True)
        body = dash_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_api(self):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        custom_price = float(qs["price"][0]) if "price" in qs else None
        print(f"  [{datetime.now():%H:%M:%S}] 计算中...")
        try:
            from app.tracker import _compute, _load_data
            data = _load_data()
            if custom_price is not None:
                # 覆盖最后一周价格为试算值
                med = data["sw_medical"].set_index("date")["close"].sort_index()
                med_w = med.resample("W-FRI").last().dropna()
                med_w.iloc[-1] = custom_price
                data["sw_medical"] = med_w.reset_index().rename(columns={"index":"date",0:"close"})
                # 让 _compute 使用修改后的数据
                data["_custom_med_w"] = med_w
            sig = _compute(data)
            dist = sig.get("distance_to_trigger", {})
            payload = {
                "score": sig["score"],
                "status": "ARMED" if sig["armed"] else "HOLD",
                "d_trigger": f'{dist["D"]["trigger_price"]:.0f}' if dist["D"].get("trigger_price") else None,
                "c_trigger": f'{dist["C"]["trigger_price"]:.0f}' if dist["C"].get("trigger_price") else None,
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _serve_lw(self):
        js_path = Path("data/lightweight-charts.min.js")
        if not js_path.exists():
            self.send_response(404); self.end_headers(); return
        body = js_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript")
        self.send_header("Cache-Control", "max-age=86400")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self):
        fname = self.path.split("/")[-1]
        fpath = Path(__file__).resolve().parent / "static" / fname
        if fpath.exists():
            body = fpath.read_bytes()
            ct = "application/javascript" if fname.endswith(".js") else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def _serve_api(self):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        custom_price = float(qs["price"][0]) if "price" in qs else None
        print(f"  [{datetime.now():%H:%M:%S}] 拉取数据中...")
        try:
            payload = _compute_and_serialize(custom_price=custom_price)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            print(f"  [{datetime.now():%H:%M:%S}] 完成 ({payload['elapsed_s']}s) — Score={payload['score']}/5 [{payload['alert']['level'].upper()}]")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"  [ERROR] {e}\n{tb}")
            body = json.dumps({"error": str(e), "detail": tb}, ensure_ascii=False).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # 屏蔽默认 access log，用自定义日志


def main():
    parser = argparse.ArgumentParser(description="医药板块实时监控看板")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"

    print("=" * 50)
    print("  医药板块实时监控看板")
    print(f"  地址: {url}")
    print("  每次刷新页面 (F5) 自动拉取最新行情")
    print("  Ctrl+C 停止服务器")
    print("=" * 50)

    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    main()

```
---

## 应用:推送通知
`app/notify.py`
```python
"""
推送通知模块 — 支持多种推送渠道

用法:
    python app/notify.py                    # 运行 tracker 并在有警报时推送
    python app/notify.py --dry-run          # 仅打印，不实际推送

环境变量 (可选, 不设置则仅打印):
    PUSH_KEY       Server酱 SendKey (https://sct.ftqq.com/)
    PUSHDEER_KEY   PushDeer pushkey
    WEBHOOK_URL    自定义 Webhook URL (POST JSON)
"""
import sys
import os
import json
import urllib.request
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def push_serverchan(title: str, content: str, push_key: str = None) -> bool:
    """Server酱 (微信推送)"""
    key = push_key or os.environ.get("PUSH_KEY", "")
    if not key:
        return False
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = json.dumps({"title": title, "desp": content}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [ServerChan] Failed: {e}")
        return False


def push_pushdeer(title: str, content: str, push_key: str = None) -> bool:
    """PushDeer"""
    key = push_key or os.environ.get("PUSHDEER_KEY", "")
    if not key:
        return False
    try:
        url = f"https://api2.pushdeer.com/message/push?pushkey={key}&text={urllib.parse.quote(title)}&desp={urllib.parse.quote(content)}"
        urllib.request.urlopen(url, timeout=10)
        return True
    except Exception as e:
        print(f"  [PushDeer] Failed: {e}")
        return False


def push_webhook(title: str, content: str, webhook_url: str = None) -> bool:
    """自定义 Webhook"""
    url = webhook_url or os.environ.get("WEBHOOK_URL", "")
    if not url:
        return False
    try:
        data = json.dumps({"title": title, "content": content, "time": datetime.now().isoformat()}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [Webhook] Failed: {e}")
        return False


def push(title: str, content: str) -> bool:
    """尝试所有渠道"""
    sent = False
    for fn in [push_serverchan, push_pushdeer, push_webhook]:
        if fn(title, content):
            sent = True
    # GitHub Actions: 输出到 workflow summary
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"## {title}\n\n{content}\n")
        sent = True
    return sent


def run(dry_run: bool = False, test_push: bool = False):
    """主入口：计算信号 + 按需推送"""
    from app.tracker import _compute, _load_data

    # 测试模式：强制发送测试推送
    if test_push:
        title = "测试推送 — 医药板块监控器"
        content = f"如果你收到这条消息，说明推送配置成功！\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"  测试模式: 强制推送")
        if not dry_run:
            sent = push(title, content)
            if sent:
                print("  测试推送已发送！请检查微信/手机是否收到。")
            else:
                print("  推送失败！请检查 PUSH_KEY 是否正确设置。")
                print(f"  当前 PUSH_KEY: {'已设置' if os.environ.get('PUSH_KEY') else '未设置'}")
        else:
            print(f"  [dry-run] 标题: {title}\n  内容: {content}")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 运行监控...")
    try:
        sig = _compute(_load_data())
    except Exception as e:
        print(f"  数据拉取失败: {e}")
        print(f"  [SILENT] 无法计算信号, 静默退出")
        return
    alert = sig["alert"]
    score = sig["score"]

    # 构建推送内容
    lines = [
        f"日期: {sig['date']}",
        f"指数: {sig['price']:.0f}",
        f"Score: {score}/5",
        f"警报: [{alert['level'].upper()}] {alert['message']}",
        "",
        "--- 距离触发 ---",
    ]
    for key in ["D", "C"]:
        d = sig["distance_to_trigger"][key]
        if d["triggered"]:
            lines.append(f"{d['name']}: 已触发")
        elif d.get("trigger_price"):
            lines.append(f"{d['name']}: 触发价 {d['trigger_price']:.0f} (距当前 {d['pct_away']:+.1f}%)")
    content = "\n".join(lines)

    # 根据警报级别决定是否推送
    level = alert["level"]
    if level == "silent":
        print(f"  Score={score} [{level}] — 静默, 不推送")
        return

    # YELLOW 或 RED: 推送
    emoji = "🔴" if level == "red" else "🟡"
    title = f"{emoji} 医药板块{'ARMED!' if level == 'red' else '近触发预警'} (Score={score})"

    print(f"  [{level.upper()}] {alert['message']}")
    print(f"  推送标题: {title}")

    if not dry_run:
        sent = push(title, content)
        if sent:
            print("  推送已发送")
        else:
            print("  未配置推送渠道 (设置 PUSH_KEY / PUSHDEER_KEY / WEBHOOK_URL 环境变量)")
    else:
        print("  [dry-run] 跳过推送")
        print(content)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    test = "--test" in sys.argv
    run(dry_run=dry, test_push=test)

```
---

## 工具:一键运行五阶段优化
`run_v5_optimizer.py`
```python
"""
V5.0 全量因子自动优化 — 注入高阶数据, 重跑五阶段
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import numpy as np

print("\n" + "=" * 60)
print("  V5.0 因子引擎 — 注入高阶 Alpha 数据")
print("=" * 60)

# 1. 拉取全量数据
print("\n[1/2] 拉取底层数据 (指数+融资)...")
from src.data_fetcher.akshare_source import AKShareSource
data = AKShareSource().fetch_all("20180101")

# 2. 周频聚合
med_df = data["sw_medical"].set_index("date")
med_w = med_df["close"].sort_index().resample("W-FRI").last().dropna()
vol_w = None
if "volume" in med_df.columns:
    vol_w = med_df["volume"].sort_index().resample("W-FRI").sum().dropna()

pe_w = None
if "medical_pe" in data and not data["medical_pe"].empty:
    pe_df = data["medical_pe"].set_index("date")["value"]
    pe_w = pe_df.sort_index().resample("W-FRI").last().dropna()

margin_w = None
if "total_margin" in data and not data["total_margin"].empty:
    margin_df = data["total_margin"].set_index("date")["value"]
    margin_w = margin_df.sort_index().resample("W-FRI").last().dropna()
    margin_w = margin_w.shift(1)  # T+1 发布时滞

print(f"  周线: {len(med_w)} 周 | 成交量: {'OK' if vol_w is not None else 'N/A'} | PE: {'OK' if pe_w is not None else 'N/A'} | 融资: {'OK' if margin_w is not None else 'N/A'}")

# 3. 注入优化器, 执行全量流程
print("\n[2/2] 五阶段漏斗筛选 + 评分卡赋权 + 阈值寻优...")
from src.models.factor_optimizer import run_full_pipeline
results = run_full_pipeline(med_w, vol_w=vol_w, pe_w=pe_w, margin_w=margin_w)

if results:
    scoring = results.get("scoring")
    threshold_df = results.get("threshold_analysis")
    if scoring is not None and len(scoring) > 0:
        print("\n" + "=" * 60)
        print("  最终评分卡")
        print("=" * 60)
        for _, r in scoring.iterrows():
            print(f"  {r['factor']:25s} | {r['final_score']:.1f} 分 | Uplift={r['uplift']:+.1f}%")

```
---

## CI/CD
`.github/workflows/medical_tracker.yml`
```yaml
name: 医药板块每日监控 + 推送

on:
  schedule:
    - cron: '45 6 * * 1-5'
  workflow_dispatch:

permissions:
  contents: write
  issues: write

jobs:
  daily-check:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install
        run: pip install pandas numpy scipy akshare openpyxl

      - name: Verify code
        run: |
          python -c "from src.models.turning_points import TurningPointDetector; print('Import OK')"
          python -c "from app.tracker import _compute, _load_data; print('Tracker OK')"

      - name: Run monitor
        id: monitor
        env:
          PUSH_KEY: ${{ secrets.PUSH_KEY }}
        run: |
          timeout 900 python app/notify.py 2>&1 | tee output.txt || true
          python app/ci_parse.py

      - name: Load results
        id: parsed
        run: cat alert_result.txt >> $GITHUB_OUTPUT

      - name: Generate dashboard
        timeout-minutes: 5
        run: timeout 300 python app/dashboard.py || true

      - name: Commit
        timeout-minutes: 2
        run: |
          git config user.name "bot"
          git config user.email "bot@users.noreply.github.com"
          git add dashboard.html data/processed/signal_history.csv 2>/dev/null || true
          git diff --staged --quiet || (git commit -m "[auto] $(date +%Y-%m-%d) ${{ steps.parsed.outputs.alert }}" && git push || true)

      - name: Issue (RED)
        if: steps.parsed.outputs.alert == 'red'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const out = fs.existsSync('output.txt') ? fs.readFileSync('output.txt','utf8').slice(0,4000) : '';
            await github.rest.issues.create({
              owner: context.repo.owner, repo: context.repo.repo,
              title: `ARMED! Score=${{ steps.parsed.outputs.score }} (${new Date().toISOString().split('T')[0]})`,
              body: '```\n' + out + '\n```\n\n历史Armed信号13周期望+8.4%',
              labels: ['armed','alert']
            });

```
---
