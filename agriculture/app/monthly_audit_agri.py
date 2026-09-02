# -*- coding: utf-8 -*-
"""月度因子审计（轻量版，复用医药项目 monthly_audit 思想）。

每月 1 号手动/计划任务运行：
  python agriculture/app/monthly_audit_agri.py
产出: agriculture/data/processed/audit_report_agri.md

只做监测与报告，不自动改配置（版本治理由人工决策）：
A. 恐慌因子（skew_13w / vol_pctile_20d）条件收益漂移：近 3 年 vs 训练段
B. 周期门触发频率漂移：近 6 个月持仓占比 vs 训练段
C. SQLite 实盘信号复盘：信号数、警报分布、当前持仓状态一致性
D. 数据健康：各源最新日期与缺失检查
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

AGRI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGRI))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from src.data_fetcher.akshare_source import load_core_data, align_daily  # noqa: E402
from src.models.cycle_regime import TRAIN_END  # noqa: E402
from src.models.factor_library import composite_score  # noqa: E402
from src.models.pipeline import build_features  # noqa: E402

DB_PATH = AGRI / "data" / "processed" / "signals.db"
OUT = AGRI / "data" / "processed" / "audit_report_agri.md"
report: list[str] = [f"# 农业板块月度审计（{datetime.now():%Y-%m-%d %H:%M}）\n"]


def log(msg: str = "") -> None:
    print(msg)
    report.append(msg + "\n")


def main() -> None:
    cfg = json.loads((AGRI / "src" / "models" / "model_config_agri.json").read_text(encoding="utf-8"))
    data = load_core_data(use_cache_days=7)
    daily = align_daily(data, data["agri"].index)
    feats = build_features(data, regime_params=cfg["regime"])
    cond = feats["cond"]
    factors = feats["factors"]

    # ── A. 恐慌因子漂移 ──
    log("\n## A. 恐慌因子条件收益漂移（近 3 年 vs 训练段）\n")
    fwd20 = daily["close"].shift(-20) / daily["close"] - 1.0
    recent_start = daily.index[-1] - pd.DateOffset(years=3)
    for name in cfg["factors"]["panic_factors"]:
        s = factors[name]
        for label, mask in [("训练段", s.index <= TRAIN_END),
                            ("近3年", s.index >= recent_start)]:
            sv, fv = s[mask], fwd20[mask]
            valid = sv.notna() & fv.notna()
            q = sv.rolling(1250, min_periods=500).rank(pct=True)
            top, bot = valid & (q >= 2 / 3), valid & (q <= 1 / 3)
            if top.sum() > 30 and bot.sum() > 30:
                spread = fv[top].mean() - fv[bot].mean()
                t, _ = stats.ttest_ind(fv[top], fv[bot], equal_var=False)
                log(f"- `{name}` {label}：top-bottom 20 日收益差 {spread:+.2%}（t={t:.2f}，"
                    f"top 样本 {int(top.sum())}）")
        log("")

    # ── B. 周期门触发频率漂移 ──
    log("\n## B. 周期门持仓占比\n")
    cs = cond["cycle_score"]
    pos = (cs > cfg["signals"]["theta_in"]).astype(float)
    pos[(cs < cfg["signals"]["theta_out"])] = 0.0
    pos = pos.ffill().fillna(0.0)
    train_share = float(pos[cs.index <= TRAIN_END].mean())
    recent6 = float(pos[cs.index >= cs.index[-1] - pd.DateOffset(months=6)].mean())
    drift = (recent6 - train_share) / max(train_share, 1e-9)
    log(f"- 训练段持仓占比 {train_share:.0%}，近 6 个月 {recent6:.0%}（漂移 {drift:+.0%}，"
        f"{'⚠️ 超过 ±50% 需人工复核' if abs(drift) > 0.5 else '正常区间'}）")

    # ── C. SQLite 实盘信号复盘 ──
    log("\n## C. 实盘信号复盘（SQLite）\n")
    if DB_PATH.exists():
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute("SELECT * FROM signals ORDER BY date")]
        if rows:
            df = pd.DataFrame(rows)
            log(f"- 累计信号 {len(df)} 条（{df['date'].iloc[0]} → {df['date'].iloc[-1]}）")
            log(f"- 警报分布：{df['alert_level'].value_counts().to_dict()}")
            log(f"- 当前持仓标记：{'是' if df['holding'].iloc[-1] else '否'}，"
                f"最近建议：{df['action'].iloc[-1]}")
        else:
            log("- 无历史信号")
    else:
        log("- SQLite 不存在（tracker 尚未运行）")

    # ── D. 数据健康 ──
    log("\n## D. 数据健康\n")
    for name, src in [("申万农林牧渔", data["agri"]), ("沪深300", data["hs300"]),
                      ("猪价周频", data["hog_week"]), ("玉米期货", data["corn"]),
                      ("豆粕期货", data["meal"]), ("宏观对齐帧", data["macro"])]:
        lag = (pd.Timestamp.now().normalize() - src.index.max()).days
        flag = "⚠️" if lag > 7 else "✓"
        log(f"- {flag} {name}：最新 {src.index.max().date()}（滞后 {lag} 天）")

    log("\n---\n")
    log("治理规则（复用医药项目）：连续 2 次审计同一指标 Declining 或任一次 Unstable，"
        "方启动版本评审；本报告只生成不自动执行。")

    OUT.write_text("".join(report), encoding="utf-8")
    print(f"\n[saved] {OUT}")


if __name__ == "__main__":
    main()
