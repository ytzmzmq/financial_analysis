# -*- coding: utf-8 -*-
"""把冻结模型（V1.2）回放到全部历史，回填信号库（is_live=0）。

目的：为看板"近期信号"表与月度审计提供完整基线，便于"实盘 vs 回溯"对照。
规则：INSERT OR IGNORE——不覆盖任何 tracker 写入的实盘行（is_live=1）。
用法: python scripts/backfill_signals.py
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

AGRI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGRI))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.backtest.backtester import desired_position_v12, run_backtest  # noqa: E402
from src.data_fetcher.akshare_source import load_core_data  # noqa: E402
from src.models.factor_library import composite_score  # noqa: E402
from src.models.pipeline import build_features  # noqa: E402
from src.models.streak_stats import tables_from_records  # noqa: E402

DB_PATH = AGRI / "data" / "processed" / "signals.db"


def main() -> None:
    cfg = json.loads((AGRI / "src" / "models" / "model_config_agri.json").read_text(encoding="utf-8"))
    sig_cfg = cfg["signals"]
    tables = tables_from_records(cfg["streak_tables"])

    data = load_core_data(use_cache_days=7)
    feats = build_features(data, regime_params=cfg["regime"])
    daily, cond = feats["daily"], feats["cond"]
    score_panic = composite_score(feats["factors"], cfg["factors"]["panic_factors"])

    pos = desired_position_v12(cond, daily["close"], score_panic, {
        "theta_in": sig_cfg["theta_in"], "theta_out": sig_cfg["theta_out"],
        "panic_threshold": sig_cfg["panic_threshold"], "exit_mode": sig_cfg["exit_mode"],
    })
    change = pos.diff()
    change.iloc[0] = pos.iloc[0]
    bt = run_backtest(pd.DataFrame({"buy": change > 0, "sell": change < 0}, index=pos.index),
                      daily.index[0], daily.index[-1], close=daily["close"])
    state = bt["state"]

    # 交易对：date → 动作文案 + 持有天数
    events: dict = {}
    for tr in bt["trades"]:
        events[tr["buy_date"]] = ("买入（次日执行）", tr)
        if "sell_date" in tr:
            events[tr["sell_date"]] = ("卖出（次日执行）", tr)
    # pending 卖出被 7 天规则顺延的日期没有事件行，alert 逻辑按状态推导
    mk = tables["markov"]
    conn = sqlite3.connect(str(DB_PATH))
    n_ins = n_skip = 0
    for t, row in state.iterrows():
        date_str = str(t.date())
        if conn.execute("SELECT 1 FROM signals WHERE date=?", (date_str,)).fetchone():
            n_skip += 1  # 已有实盘行，不覆盖
            continue
        holding = bool(row["position"])
        cyc = float(cond["cycle_score"].loc[t])
        rec = float(cond["recession_prob"].loc[t])
        panic = float(score_panic.loc[t])
        streak = int(cond["streak"].loc[t]) if pd.notna(cond["streak"].loc[t]) else 0
        p_up = float(mk.loc[streak, "p_up_tomorrow"]) if streak in mk.index else None

        if t in events:
            action = events[t][0]
            alert = "RED"
        elif holding and (rec > 0.6 or cyc < 0.15):
            action, alert = "持有", "YELLOW"
        elif (not holding) and (panic >= 70 or (-0.2 < cyc <= 0.15)):
            action, alert = "空仓", "YELLOW"
        else:
            action, alert = ("持有" if holding else "空仓"), "SILENT"

        buy_date = None
        if holding:
            for tr in reversed(bt["trades"]):
                if tr["buy_date"] <= t and ("sell_date" not in tr or tr["sell_date"] > t):
                    buy_date = str(tr["buy_date"].date())
                    break

        snapshot = {"cycle_score": round(cyc, 3), "cycle_phase": str(cond["cycle_phase"].loc[t]),
                    "hog_phase": str(cond["hog_phase"].loc[t]), "recession_prob": round(rec, 3),
                    "panic_score": round(panic, 1), "streak_days": streak,
                    "backfilled": True}
        conn.execute("""
            INSERT OR IGNORE INTO signals
            (date, score, action, alert_level, price, holding, cycle_score, cycle_phase,
             hog_phase, recession_prob, streak_days, p_up_tomorrow, panic_score,
             buy_date, model_version, factor_snapshot, is_live)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (date_str, round(panic, 1), action, alert, round(float(daily["close"].loc[t]), 2),
              int(holding), round(cyc, 3), str(cond["cycle_phase"].loc[t]),
              str(cond["hog_phase"].loc[t]), round(rec, 3), streak,
              round(p_up, 3) if p_up is not None else None, round(panic, 1),
              buy_date, cfg["version"], json.dumps(snapshot, ensure_ascii=False)))
        n_ins += 1
    conn.commit()
    total = conn.execute("SELECT COUNT(*), SUM(is_live) FROM signals").fetchone()
    conn.close()
    print(f"回填完成：新增 {n_ins} 行，跳过已有 {n_skip} 行；"
          f"库内共 {total[0]} 行（实盘 {total[1] or 0} / 回溯 {total[0] - (total[1] or 0)}）")


if __name__ == "__main__":
    main()
