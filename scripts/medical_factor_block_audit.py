# -*- coding: utf-8 -*-
"""医药 V5.2 因子置信度复核：iid bootstrap vs 移动块 bootstrap。

2026-10-24 模型审查善后（根目录 MODEL_AUDIT_2026-10-24.md）：三漏斗的 uplift CI
原用 iid bootstrap，而 13 周前瞻收益按周采样重叠 12/13，方差被低估最多
~sqrt(13)≈3.6 倍。本脚本并排输出两套 CI（screen_factors 已同时计算），供
REPORT 披露与 V5.3 评审参考。不修改 MODEL_CONFIGS（版本治理走月度审计）。

用法（需 akshare 环境）: python scripts/medical_factor_block_audit.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd  # noqa: E402

from app.tracker import _load_data  # noqa: E402
from src.models.factor_optimizer import build_factor_pool, screen_factors  # noqa: E402


def main() -> None:
    data = _load_data()
    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()
    margin_w = None
    if not data.get("total_margin", pd.DataFrame()).empty:
        mdf = data["total_margin"].set_index("date")["value"].sort_index()
        margin_w = mdf.resample("W-FRI").last().dropna().shift(1)

    print(f"周线样本: {med_w.index[0].date()} ~ {med_w.index[-1].date()} (n={len(med_w)})")
    pool = build_factor_pool(med_w, margin_w=margin_w)
    screened = screen_factors(pool, med_w, forward_weeks=13)

    cols = ["factor", "freq", "n_signals", "e_cond", "e_uncond", "uplift",
            "uplift_ci_low", "uplift_ci_high",
            "uplift_block_ci_low", "uplift_block_ci_high", "block_ci_ok"]
    print("\n通过 iid 三漏斗的因子（并排披露两套 CI）：")
    print(screened[cols].round(2).to_string(index=False))
    n_block_ok = int(screened["block_ci_ok"].sum())
    print(f"\n结论：iid 口径入选 {len(screened)} 个；移动块口径 CI 下限仍 >1% 的仅 "
          f"{n_block_ok} 个；其余因子的'统计显著'在诚实方差下不成立。")


if __name__ == "__main__":
    main()
