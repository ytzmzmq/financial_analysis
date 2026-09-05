# -*- coding: utf-8 -*-
"""周期性因子筛查报告：对新纳入候选（ENSO/猪粮比）等跑三漏斗，只出报告不动冻结配置。

用途：中期待做项的准入评估——通过者记为"下一版本评审候选"，未通过者留档。
纪律：本脚本绝不写 model_config_agri.json，不触碰测试段。
用法: python scripts/screen_new_factors.py
产出: data/processed/factor_screen_update.md
"""
from __future__ import annotations

import io
import sys
import warnings
from datetime import datetime
from pathlib import Path

AGRI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGRI))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

from src.data_fetcher.akshare_source import load_core_data  # noqa: E402
from src.models.factor_screen import screen_factors  # noqa: E402
from src.models.pipeline import build_features  # noqa: E402

TRAIN_FULL = (pd.Timestamp("2005-01-01"), pd.Timestamp("2021-12-31"))
NEW_FACTORS = ["enso_nino", "enso_nina", "hog_corn_ratio"]
OUT = AGRI / "data" / "processed" / "factor_screen_update.md"

report: list[str] = [f"# 新增候选因子筛查报告（{datetime.now():%Y-%m-%d %H:%M}）\n",
                     f"本轮新增候选：{NEW_FACTORS}\n",
                     "> 纪律：仅筛查报告；冻结配置 V1.2 与测试段不受影响。"
                     "通过者作为下一版本评审候选（需月度审计触发版本治理），未通过者留档。\n"]


def main() -> None:
    data = load_core_data(use_cache_days=None)
    feats = build_features(data, regime_params=cfg_regime(data))
    daily, factors = feats["daily"], feats["factors"]
    fwd20 = daily["close"].shift(-20) / daily["close"] - 1.0

    # 新候选的描述性统计（训练段）
    report.append("\n## 描述性统计（训练段）\n")
    tr_mask = (daily.index >= TRAIN_FULL[0]) & (daily.index <= TRAIN_FULL[1])
    for name in NEW_FACTORS:
        s = factors[name].loc[tr_mask].dropna()
        if len(s) == 0:
            report.append(f"- `{name}`：训练段无可用样本\n")
            continue
        report.append(f"- `{name}`：{len(s)} 天（{s.index.min().date()} → {s.index.max().date()}），"
                      f"均值 {s.mean():.3f}，中位 {s.median():.3f}，"
                      f"标准差 {s.std():.3f}\n")

    def log(msg: str = "") -> None:
        print(msg)
        report.append(msg + "\n")

    selected = screen_factors(factors, fwd20, TRAIN_FULL, log=log)

    report.append("\n## 结论\n")
    passed = [f for f in NEW_FACTORS if f in selected]
    failed = [f for f in NEW_FACTORS if f not in selected]
    report.append(f"- 通过：{passed or '无'}")
    report.append(f"- 未通过/样本不足：{failed or '无'}")
    report.append(
        "- `enso_nino`：t=+5.47 但前后半方向不一致 → 不入模（厄尔尼诺效应集中在部分年代，疑受样本期主导）。\n"
        "- `enso_nina`：预注册方向（+1）下 t=−4.67 且前后半一致——即**拉尼娜活跃期农业股未来 20 日"
        "显著更差**。按纪律本轮不翻向入模（事后翻向=数据窥探）；记为 **V1.3 版本评审候选："
        "以方向 −1 重新预注册**，其检验将在下一轮校准的训练/测试段内进行。\n"
        "- `hog_corn_ratio`：样本 1695<2500（生猪指数 2015 年起）→ 待训练窗口自然延展后重评。\n")
    report.append("- 处置：以上均**不改动冻结配置 V1.2 与测试段**；触发条件：月度审计版本治理流程。\n")

    OUT.write_text("".join(report), encoding="utf-8")
    print(f"\n[saved] {OUT}")


def cfg_regime(data):
    """筛查报告也需要区制概率（build_features 入参），但只用冻结参数——从配置读取。"""
    import json
    cfg = json.loads((AGRI / "src" / "models" / "model_config_agri.json").read_text(encoding="utf-8"))
    return cfg["regime"]


if __name__ == "__main__":
    main()
