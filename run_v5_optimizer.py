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
