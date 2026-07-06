"""V5.2 补充验证脚本 — 运行审核意见要求的四项分析"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np

from src.data_fetcher.akshare_source import AKShareSource
from src.models.factor_optimizer import build_factor_pool, bootstrap_ci

# ── 加载数据 ──
ak = AKShareSource()
med_df = ak.fetch_sw_medical('20180101')
margin_df = ak.fetch_margin_data('20180101')

med = med_df.set_index('date')['close'].sort_index()
med_w = med.resample('W-FRI').last().dropna()

margin_w = None
if margin_df is not None and not margin_df.empty:
    mdf = margin_df.set_index('date')['value'].sort_index()
    margin_w = mdf.resample('W-FRI').last().dropna().shift(1)

vol_w = None
if 'volume' in med_df.columns:
    vdf = med_df.set_index('date')['volume'].sort_index()
    vol_w = vdf.resample('W-FRI').sum().dropna()

pool = build_factor_pool(med_w, vol_w=vol_w, margin_w=margin_w)
n = len(med_w) - 13
fwd_ret = np.array([(med_w.iloc[i+13]/med_w.iloc[i]-1)*100 for i in range(n)])
e_uncond = np.mean(fwd_ret)

FACTORS = ['L1_rsi_30', 'M1_skew_neg', 'S3_margin_diverge', 'V1_price_5y_low']

# ═══════════════════════════════════════
# 验证1: 因子组合表现表
# ═══════════════════════════════════════
print('=' * 60)
print('  验证1: 因子组合表现表')
print('=' * 60)

combo_results = {}
for i in range(n):
    triggered = tuple(sorted([f for f in FACTORS if pool[f].iloc[i] == 1]))
    if len(triggered) == 0:
        continue
    key = '+'.join(triggered)
    if key not in combo_results:
        combo_results[key] = []
    combo_results[key].append(fwd_ret[i])

print()
print(f'| 组合 | 样本数 | 平均收益 | 中位数 | 胜率 | Uplift | 95% CI |')
print(f'|------|:------:|:-------:|:-----:|:----:|:------:|:------:|')

for combo in sorted(combo_results.keys(), key=lambda x: -len(combo_results[x])):
    rets = np.array(combo_results[combo])
    n_sig = len(rets)
    avg = np.mean(rets)
    median = np.median(rets)
    win_rate = np.mean(rets > 0) * 100
    uplift = avg - e_uncond
    ci_low, ci_high = bootstrap_ci(rets - e_uncond)
    ci_str = f'[{ci_low:+.1f}%, {ci_high:+.1f}%]' if not np.isnan(ci_low) else '样本不足'
    print(f'| {combo} | {n_sig} | {avg:+.1f}% | {median:+.1f}% | {win_rate:.0f}% | {uplift:+.1f}% | {ci_str} |')

# ═══════════════════════════════════════
# 验证2: 权重映射公式
# ═══════════════════════════════════════
print()
print('=' * 60)
print('  验证2: 权重映射推导')
print('=' * 60)

factor_stats = {}
for f in FACTORS:
    triggered = pool[f].iloc[:n].values == 1
    rets = fwd_ret[triggered]
    ci_low, ci_high = bootstrap_ci(rets - e_uncond)
    factor_stats[f] = {
        'uplift': np.mean(rets) - e_uncond,
        'ci_low': ci_low,
        'ci_high': ci_high,
        'n': int(triggered.sum()),
    }

# 方案B: CI下限分档
print()
print('方案B: 按 CI 下限分档')
print('  CI下限 >= 3.5%  -> 3.0')
print('  CI下限 2.0~3.5% -> 2.5')
print('  CI下限 1.0~2.0% -> 2.0')
print()
print('| 因子 | Uplift | CI下限 | CI上限 | 方案B权重 |')
print('|------|:------:|:------:|:------:|:---------:|')
for f in FACTORS:
    s = factor_stats[f]
    ci = s['ci_low']
    if ci >= 3.5:
        w = 3.0
    elif ci >= 2.0:
        w = 2.5
    elif ci >= 1.0:
        w = 2.0
    else:
        w = 0
    ci_s = f"{ci:.1f}%" if not np.isnan(ci) else 'N/A'
    ci_h = f"{s['ci_high']:.1f}%" if not np.isnan(s['ci_high']) else 'N/A'
    print(f"| {f} | {s['uplift']:+.1f}% | {ci_s} | {ci_h} | {w} |")

# 方案C: CI下限正比映射
print()
print('方案C: 按 CI 下限正比映射, 归一到总分10, round到0.5步长')
ci_lows = {f: max(0, factor_stats[f]['ci_low']) for f in FACTORS}
total_ci = sum(ci_lows.values())
print('| 因子 | CI下限 | 原始比例 | x10 | round到0.5 |')
print('|------|:------:|:-------:|:---:|:----------:|')
for f in FACTORS:
    ratio = ci_lows[f] / total_ci if total_ci > 0 else 0
    raw = ratio * 10
    discrete = round(raw * 2) / 2
    print(f'| {f} | {ci_lows[f]:.1f}% | {ratio:.3f} | {raw:.2f} | {discrete} |')

# ═══════════════════════════════════════
# 验证3: L1 边际增益
# ═══════════════════════════════════════
print()
print('=' * 60)
print('  验证3: L1 边际增益检验')
print('=' * 60)

# 3A: 新增覆盖
both_armed = []
new_only = []

for i in range(n):
    m1 = pool['M1_skew_neg'].iloc[i]
    s3 = pool['S3_margin_diverge'].iloc[i]
    v1 = pool['V1_price_5y_low'].iloc[i]
    l1 = pool['L1_rsi_30'].iloc[i]

    old_score = m1 * 4.5 + s3 * 3.0 + v1 * 2.5
    old_arm = old_score >= 3.5

    n_factors = int(m1 + s3 + v1 + l1)
    new_arm = n_factors >= 2

    if old_arm and new_arm:
        both_armed.append(fwd_ret[i])
    elif not old_arm and new_arm:
        new_only.append(fwd_ret[i])

print(f'\n  V5.1 和 V5.2 都 Armed: {len(both_armed)} 周')
if both_armed:
    r = np.array(both_armed)
    print(f'    平均收益: {np.mean(r):+.1f}%, 中位数: {np.median(r):+.1f}%, 胜率: {np.mean(r>0)*100:.0f}%')

print(f'  V5.2 新增 (V5.1 未 Armed): {len(new_only)} 周')
if new_only:
    r = np.array(new_only)
    print(f'    平均收益: {np.mean(r):+.1f}%, 中位数: {np.median(r):+.1f}%, 胜率: {np.mean(r>0)*100:.0f}%')

# 3B: 条件 uplift
print('\n  条件 uplift (其他因子触发时, L1=1 vs L1=0):')
for f in ['M1_skew_neg', 'S3_margin_diverge', 'V1_price_5y_low']:
    f_mask = pool[f].iloc[:n].values == 1
    if f_mask.sum() < 3:
        print(f'    {f}: 样本不足 ({f_mask.sum()}周)')
        continue
    l1_on = (pool['L1_rsi_30'].iloc[:n].values == 1) & f_mask
    l1_off = (pool['L1_rsi_30'].iloc[:n].values == 0) & f_mask
    ret_on = fwd_ret[l1_on] if l1_on.sum() > 0 else np.array([])
    ret_off = fwd_ret[l1_off] if l1_off.sum() > 0 else np.array([])
    avg_on = np.mean(ret_on) if len(ret_on) > 0 else float('nan')
    avg_off = np.mean(ret_off) if len(ret_off) > 0 else float('nan')
    delta = avg_on - avg_off if not (np.isnan(avg_on) or np.isnan(avg_off)) else float('nan')
    print(f'    {f}: L1=1({len(ret_on)}周) avg={avg_on:+.1f}%  vs  L1=0({len(ret_off)}周) avg={avg_off:+.1f}%  增量={delta:+.1f}%')

# ═══════════════════════════════════════
# 验证4: 回溯对比 (被取消 vs 保留)
# ═══════════════════════════════════════
print()
print('=' * 60)
print('  验证4: 回溯对比 (被取消 vs 保留)')
print('=' * 60)

cancelled = []
retained = []

for i in range(n):
    m1 = pool['M1_skew_neg'].iloc[i]
    s3 = pool['S3_margin_diverge'].iloc[i]
    v1 = pool['V1_price_5y_low'].iloc[i]
    l1 = pool['L1_rsi_30'].iloc[i]

    old_score = m1 * 4.5 + s3 * 3.0 + v1 * 2.5
    old_arm = old_score >= 3.5

    n_factors = int(m1 + s3 + v1 + l1)
    new_arm = n_factors >= 2

    if old_arm and not new_arm:
        cancelled.append(fwd_ret[i])
    if new_arm:
        retained.append(fwd_ret[i])

print()
print(f'| 分组 | 样本数 | 平均13W收益 | 中位数 | 胜率 | Uplift | 95% CI |')
print(f'|------|:------:|:---------:|:-----:|:----:|:------:|:------:|')

for label, rets in [('被V5.2取消(单因子M1)', cancelled), ('被V5.2保留(>=2因子)', retained)]:
    r = np.array(rets)
    if len(r) == 0:
        print(f'| {label} | 0 | - | - | - | - | - |')
        continue
    avg = np.mean(r)
    med = np.median(r)
    wr = np.mean(r > 0) * 100
    up = avg - e_uncond
    ci_l, ci_h = bootstrap_ci(r - e_uncond)
    ci_str = f'[{ci_l:+.1f}%, {ci_h:+.1f}%]' if not np.isnan(ci_l) else '样本不足'
    print(f'| {label} | {len(r)} | {avg:+.1f}% | {med:+.1f}% | {wr:.0f}% | {up:+.1f}% | {ci_str} |')

print()
print('验证完成。')
