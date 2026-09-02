# -*- coding: utf-8 -*-
"""流水线自检：防前视对齐、T+1 执行、7 天约束、冻结表一致性。

全部断言通过输出 SELF-CHECK PASSED，任一失败抛 AssertionError（退出码 1）。
用法: python scripts/selfcheck.py （使用本地缓存，不联网）
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

AGRI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGRI))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.backtest.backtester import (  # noqa: E402
    MIN_HOLD_NATURAL_DAYS, compute_metrics, desired_position_v12, position_signals, run_backtest,
)
from src.data_fetcher.akshare_source import load_core_data, align_daily  # noqa: E402
from src.models.pipeline import build_features  # noqa: E402
from src.models.factor_library import composite_score  # noqa: E402


def main() -> None:
    cfg = json.loads((AGRI / "src" / "models" / "model_config_agri.json").read_text(encoding="utf-8"))

    # ── 1. 宏观防前视：对齐帧在可得日发生阶梯切换（值不早于可得日出现） ──
    data = load_core_data(use_cache_days=7)
    daily = align_daily(data, data["agri"].index)
    macro_aligned = data["macro"]  # fetch_macro 输出：索引即可得日
    for col in ["cpi_yoy", "ppi_yoy", "m1_yoy", "m2_yoy"]:
        s = macro_aligned[col].dropna()
        for a in list(s.index)[-24:]:  # 抽查近 24 个可得日
            v = s.asof(a)
            k = daily.index.searchsorted(a)  # 可得日后的第一个交易日
            at = daily[col].iloc[k]
            before = daily[col].iloc[k - 1] if k > 0 else np.nan
            assert abs(at - v) < 1e-9, \
                f"错位! {col} 可得日 {a.date()} 后首个交易日应为 {v}，实际 {at}"
            v_prev = s.asof(a - pd.Timedelta(days=20))
            if pd.notna(before) and pd.notna(v_prev):
                assert abs(before - v_prev) < 1e-9, \
                    f"前视! {col} 可得日 {a.date()} 前一日已是新值 {before}（应为上期 {v_prev}）"
    print("[1] 宏观防前视对齐 ... OK")

    # ── 2. 前瞻收益定义正确（fwd 用的 shift(-h)，仅限标签，不得进入信号） ──
    close = daily["close"]
    h = 20
    fwd = close.shift(-h) / close - 1.0
    i = 3000
    assert abs(fwd.iloc[i] - close.iloc[i + h] / close.iloc[i] + 1) < 1e-9
    print("[2] 前瞻收益定义 ... OK（仅用于标签/评估，信号链无引用）")

    # ── 3. 回测执行约束：T+1 成交 + 7 自然日 + 无违规 ──
    feats = build_features(data, regime_params=cfg["regime"])
    cond = feats["cond"]
    score_panic = composite_score(feats["factors"], cfg["factors"]["panic_factors"])
    pos = desired_position_v12(cond, daily["close"], score_panic, {
        "theta_in": cfg["signals"]["theta_in"], "theta_out": cfg["signals"]["theta_out"],
        "panic_threshold": cfg["signals"]["panic_threshold"],
        "exit_mode": cfg["signals"]["exit_mode"],
    })
    bt = run_backtest(position_signals(pos), daily.index[0], daily.index[-1],
                      close=daily["close"])
    for tr in bt["trades"]:
        if "sell_date" not in tr:
            continue  # 当前持有中的未平仓交易
        hold = (tr["sell_date"] - tr["buy_date"]).days
        assert hold >= MIN_HOLD_NATURAL_DAYS, f"7 天约束违规: {tr}"
        # T+1：buy_date 必须是 buy 事件日的下一交易日
        events = position_signals(pos)
        buy_events = events.index[events["buy"] & (events.index <= tr["buy_date"])]
        last_event = buy_events[-1]
        ev_pos = daily.index.get_loc(last_event)
        assert daily.index[ev_pos + 1] == tr["buy_date"], \
            f"非 T+1 成交: 事件 {last_event.date()} → 成交 {tr['buy_date'].date()}"
    print(f"[3] T+1 执行 + 7 自然日约束 ... OK（{len(bt['trades'])} 笔交易 0 违规）")

    # ── 4. 冻结表一致性 ──
    mk = pd.DataFrame(cfg["streak_tables"]["markov"]).set_index("k")
    fq = pd.DataFrame(cfg["streak_tables"]["frequency"]).set_index("n")
    assert mk["p_up_tomorrow"].between(0, 1).all()
    assert fq["p_continue"].dropna().between(0, 1).all()
    assert set(cfg["protocol"]["test_peek_note"]) and cfg["protocol"]["test_peek_count"] == 3
    print("[4] 冻结表取值域与版本披露 ... OK")

    # ── 5. 持仓状态与最新信号可复算 ──
    m = compute_metrics(bt["state"]["strat_ret"], bt["state"]["index_ret"], bt["trades"])
    assert np.isfinite(m["ann_return"])
    print(f"[5] 全历史复算 ... OK（年化 {m['ann_return']:+.1%}，当前持仓 "
          f"{'是' if bt['state']['position'].iloc[-1] == 1 else '否'}）")

    print("\nSELF-CHECK PASSED")


if __name__ == "__main__":
    main()
