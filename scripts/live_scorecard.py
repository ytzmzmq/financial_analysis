# -*- coding: utf-8 -*-
"""Live scorecard —— 两个监控系统实盘表现的唯一记录与裁决数据源。

背景(DECISION_MEMO_2027-04.md):两模型的历史回测已因 HP 前视/重叠 bootstrap 作废,
实盘记录(is_live=1)是唯一干净的测试段。本脚本每月 1 号(CI 或手动)重算并落盘:

  data/processed/live_scorecard.md    人读的月度快照 + 备忘录判据对照
  data/processed/live_scorecard.csv   每实盘交易日一行的基础证据表(确定性重生成)

设计约束:只用 SQLite(标准库),不联网、不装依赖;任何时候重跑结果一致。
用法: python scripts/live_scorecard.py
"""
from __future__ import annotations

import csv
import io
import sqlite3
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MED_DB = REPO / "data" / "processed" / "signals.db"
AGRI_DB = REPO / "agriculture" / "data" / "processed" / "signals.db"
OUT_MD = REPO / "data" / "processed" / "live_scorecard.md"
OUT_CSV = REPO / "data" / "processed" / "live_scorecard.csv"


def rows(db: Path, sql: str) -> list[tuple]:
    con = sqlite3.connect(str(db))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def main() -> int:
    today = date.today().isoformat()

    # ── 农业:实盘行 + 全库价格序列(算 T+1 收益与信号后最大浮亏) ──
    agri_all = rows(AGRI_DB, "SELECT date, price, holding FROM signals ORDER BY date")
    price_by_date = {d: p for d, p, _ in agri_all}
    agri_live = rows(AGRI_DB,
        "SELECT date, price, holding, alert_level, action, buy_date, panic_score, streak_days "
        "FROM signals WHERE is_live=1 ORDER BY date")
    dates_live = [r[0] for r in agri_live]

    n_live = len(agri_live)
    strat_cum = idx_cum = 1.0
    csv_rows = []
    for i in range(1, n_live):  # T+1:t-1 收盘持仓,吃 t-1→t 收益
        p_prev, p_now = agri_live[i - 1][1], agri_live[i][1]
        hold_prev = agri_live[i - 1][2] or 0
        r = p_now / p_prev - 1.0
        strat_cum *= 1 + hold_prev * r
        idx_cum *= 1 + r
        csv_rows.append([dates_live[i], hold_prev, round(r, 6), round(hold_prev * r, 6)])

    # 当前持仓的"信号后最大浮亏"(备忘录二-b:开仓后浮亏不超过 -15%)
    mae = None
    buy_date = agri_live[-1][5] if agri_live else None
    if buy_date and (agri_live[-1][2] or 0) == 1 and buy_date in price_by_date:
        entry = price_by_date[buy_date]
        lows = [p for d, p in sorted(price_by_date.items()) if d >= buy_date]
        mae = min(lows) / entry - 1.0 if lows else None

    # 滚动 126 日窗口(样本不足时如实标注)
    roll_win_ok = None
    if n_live >= 127:
        best = None
        for s in range(n_live - 126):
            w = 1.0
            wi = 1.0
            for i in range(s + 1, s + 127):
                r = agri_live[i][1] / agri_live[i - 1][1] - 1.0
                w *= 1 + (agri_live[i - 1][2] or 0) * r
                wi *= 1 + r
            best = (w - wi) if best is None else max(best, w - wi)
        roll_win_ok = best > 0

    # ── 医药:实盘事实(因子触发/ARMED/估值与 RSI 区间) ──
    med_live = rows(MED_DB,
        "SELECT date, armed, alert_level, rsi, val_pct_5y, price, n_factors "
        "FROM signals ORDER BY date")
    med_n = len(med_live)
    med_armed = [r for r in med_live if r[1]]
    med_val = [r[4] for r in med_live if r[4] is not None]
    med_rsi = [r[3] for r in med_live if r[3] is not None]
    med_factors = sum(r[6] or 0 for r in med_live)
    # ARMED 后 13 周(约 65 交易日)前瞻收益——样本出现后自动补算
    armed_notes = []
    price_seq = [(r[0], r[5]) for r in med_live]
    for a in med_armed:
        idxs = [i for i, (d, _) in enumerate(price_seq) if d == a[0]]
        if idxs and idxs[0] + 65 < len(price_seq):
            fwd = price_seq[idxs[0] + 65][1] / a[5] - 1.0
            armed_notes.append(f"{a[0]} ARMED → 13周收益 {fwd:+.1%}")
        else:
            armed_notes.append(f"{a[0]} ARMED → 13周期未满,待补算")

    # ── 数据健康 ──
    med_errs = rows(MED_DB,
        "SELECT substr(timestamp,1,7) m, count(*) FROM system_log "
        "WHERE level='error' GROUP BY m ORDER BY m")

    # ── 备忘录判据对照 ──
    lines = []
    lines.append(f"# Live Scorecard(生成 {today})\n")
    lines.append("> 裁决依据见 `DECISION_MEMO_2027-04.md`;判据不满足就是不满则。\n")
    lines.append("## 农业实盘(自 %s,样本 %d 个交易日%s)\n" % (
        dates_live[0] if dates_live else "-", n_live,
        ",备忘录要求 ≥100" if n_live < 100 else ",已满足备忘录样本要求"))
    lines.append(f"- 区间累计:策略口径 **{strat_cum - 1:+.1%}** vs 指数 {idx_cum - 1:+.1%}"
                 f"(超额 {(strat_cum - 1) - (idx_cum - 1):+.1%})")
    if mae is not None:
        verdict_b = "满足" if mae > -0.15 else "**违反**"
        lines.append(f"- 当前持仓(买于 {buy_date})后最大浮亏 {mae:+.1%}"
                     f"(备忘录二-b 红线 −15%:{verdict_b})")
    if roll_win_ok is None:
        lines.append("- 滚动 126 日超额窗口:样本不足(需 ≥127 日),复审前自动补算")
    else:
        lines.append(f"- 滚动 126 日超额窗口最佳值 {'>' if roll_win_ok else '≤'} 0"
                     f"(备忘录二-a:{'满足' if roll_win_ok else '未满足'})")
    lines.append("")
    lines.append("## 医药实盘(自 %s,样本 %d 个交易日)\n" % (
        med_live[0][0] if med_live else "-", med_n))
    lines.append(f"- 因子触发合计 {med_factors} 次;ARMED {len(med_armed)} 次")
    if armed_notes:
        lines.extend("- " + n for n in armed_notes)
    if med_val:
        lines.append(f"- 估值分位区间 {min(med_val):.1f}% ~ {max(med_val):.1f}%"
                     f";RSI 区间 {min(med_rsi):.1f} ~ {max(med_rsi):.1f}")
    lines.append("")
    lines.append("## 数据健康(医药 system_log 错误)\n")
    lines.append("- " + ("; ".join(f"{m}×{c}" for m, c in med_errs) if med_errs else "无错误记录"))
    lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "holding_prev", "index_ret_1d", "strat_ret_1d"])
        w.writerows(csv_rows)

    print("\n".join(lines))
    print(f"[saved] {OUT_MD.name} / {OUT_CSV.name} ({len(csv_rows)} 交易日)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
