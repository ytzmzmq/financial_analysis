# -*- coding: utf-8 -*-
"""个人规则看门狗——把每日推送从"模型信号"改造成"事实 + 你的规则状态"。

定位(DECISION_MEMO_2027-04.md §四):规则由本人执行,系统只盯事实、提醒触发,
不负责择时判断。规则定义在 config/personal_rules.json,改数字不用改代码。

数据源:两个 signals.db 的最新行 + 农业价格序列(算持仓期高点/浮盈)。
只用标准库;任何失败都降级为提示文本,绝不抛异常阻断推送。
用法(被 notify_combined 调用):
    from app.rules_engine import render_rules_section
    section = render_rules_section(repo_root)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _q(db: Path, sql: str):
    con = sqlite3.connect(str(db))
    try:
        con.row_factory = sqlite3.Row
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _facts(root: Path) -> dict:
    """从两个 DB 收集规则所需事实(缺失的记 None,规则按未触发处理)。"""
    agri_db = root / "agriculture" / "data" / "processed" / "signals.db"
    med_db = root / "data" / "processed" / "signals.db"
    f: dict = {"agri": None, "agri_entry": None, "agri_peak": None, "med": None}
    if agri_db.exists():
        last = _q(agri_db, "SELECT * FROM signals WHERE is_live=1 ORDER BY date DESC LIMIT 1")
        f["agri"] = dict(last[0]) if last else None
        if f["agri"] and (f["agri"].get("holding") or 0) == 1 and f["agri"].get("buy_date"):
            con = sqlite3.connect(str(agri_db))
            rows_ = con.execute("SELECT date, price FROM signals WHERE date >= ? ORDER BY date",
                                (f["agri"]["buy_date"],)).fetchall()
            con.close()
            if rows_:
                f["agri_entry"] = rows_[0][1]
                f["agri_peak"] = max(r[1] for r in rows_)
    if med_db.exists():
        last = _q(med_db, "SELECT date, price, rsi, val_pct_5y, armed FROM signals ORDER BY date DESC LIMIT 1")
        f["med"] = dict(last[0]) if last else None
    return f


def render_rules_section(root: Path | None = None) -> str:
    root = root or Path(__file__).resolve().parent.parent
    try:
        cfg = json.loads((root / "config" / "personal_rules.json").read_text(encoding="utf-8"))
        f = _facts(root)
    except Exception as e:  # noqa: BLE001 — 规则区失败不阻断推送
        return f"\n## 📋 个人规则\n\n(规则引擎不可用:{e})\n"

    ag, entry, peak = f["agri"], f["agri_entry"], f["agri_peak"]
    med = f["med"]
    px = (ag or {}).get("price")
    lines = ["## 📋 你的规则(与模型独立,只认事实)"]
    triggered = []

    for r in cfg.get("rules", []):
        rid, name, p = r["id"], r["name"], r.get("params", {})
        mark, txt = "·", ""
        if r["type"] == "take_profit" and px and entry:
            gain = px / entry - 1
            if gain >= p["gain_pct"] / 100:
                mark, txt = "✅", f"触发:浮盈 {gain:+.1%} ≥ {p['gain_pct']}% → 次日赎回 {p['sell_frac']}"
                triggered.append(rid)
            else:
                txt = f"未触发(浮盈 {gain:+.1%},线 +{p['gain_pct']}%)"
        elif r["type"] == "trailing_stop" and px and peak:
            dd = px / peak - 1
            if dd <= -p["drawdown_pct"] / 100:
                mark, txt = "✅", f"触发:距持仓高点 {dd:+.1%} ≤ -{p['drawdown_pct']}% → 次日赎回 {p['sell_frac']}"
                triggered.append(rid)
            else:
                txt = f"未触发(距高点 {dd:+.1%},线 -{p['drawdown_pct']}%)"
        elif r["type"] == "panic_add" and ag:
            panic = ag.get("panic_score") or 0
            streak = ag.get("streak_days") or 0
            if panic >= p["panic_min"] and streak >= p["streak_min"]:
                mark, txt = "✅", f"触发:恐慌 {panic:.0f} ≥{p['panic_min']} 且连跌 {streak} 天 ≥{p['streak_min']} → 可加一份(≤{p['max_per_quarter']}份/季)"
                triggered.append(rid)
            else:
                txt = f"未触发(恐慌 {panic:.0f}/{p['panic_min']},连跌 {streak}/{p['streak_min']}天)"
        elif r["type"] == "val_dca" and med and med.get("val_pct_5y") is not None:
            val = med["val_pct_5y"]
            if val < p["val_below"]:
                mark, txt = "✅", f"建仓窗口:分位 {val:.1f}% < {p['val_below']}% → 本月申购一份(累计≤{p['max_shares']}份)"
                triggered.append(rid)
            elif val > p["val_pause"]:
                mark, txt = "⏸", f"暂停新增:分位 {val:.1f}% > {p['val_pause']}%"
            else:
                txt = f"未触发(分位 {val:.1f}%,窗口 <{p['val_below']}%)"
        elif r["type"] == "panic_boost" and med and med.get("rsi") is not None:
            armed = bool(med.get("armed"))
            rsi = med["rsi"]
            if rsi < p["rsi_below"] or armed:
                mark, txt = "✅", f"触发:RSI {rsi:.1f} <{p['rsi_below']}" + ("或模型 ARMED" if armed else "") + f" → 允许提前加一份(≤{p['max_shares']}份)"
                triggered.append(rid)
            else:
                txt = f"未触发(RSI {rsi:.1f},线 <{p['rsi_below']})"
        elif r["type"] == "default_noop":
            if not triggered:
                knife = (ag or {}).get("streak_days") or 0
                extra = f";连跌 {knife} 天,不接飞刀" if knife >= p.get("no_catch_days", 5) else ""
                mark, txt = "☑", f"今日无操作{extra}"
            else:
                mark, txt = "·", f"今日有 {len(triggered)} 条规则触发,按上方 ✅ 执行"
        lines.append(f"- {mark} {rid} {name}:{txt}")

    lines.append("\n(规则参数在 `config/personal_rules.json`;系统只提醒,不择时)")
    return "\n".join(lines)


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print(render_rules_section())
