# -*- coding: utf-8 -*-
"""农业板块每日信号追踪器（CLI / GitHub Actions 共用）。

用法: python agriculture/app/tracker_agri.py
输出: 人类可读信号摘要（首行含 [SILENT|YELLOW|RED] 供 ci_parse_agri 解析）
存储: agriculture/data/processed/signals.db（signals + system_log）

模型：加载冻结配置 src/models/model_config_agri.json（V1.2 周期主导），
在线拉取数据（失败回退本地缓存），重放持仓状态并生成今日建议。
"""
from __future__ import annotations

import io
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

AGRI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGRI))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd  # noqa: E402

from src.backtest.backtester import desired_position_v12, position_signals, run_backtest  # noqa: E402
from src.data_fetcher.akshare_source import load_core_data  # noqa: E402
from src.models.factor_library import composite_score  # noqa: E402
from src.models.pipeline import build_features  # noqa: E402
from src.models.streak_stats import current_streak_card  # noqa: E402

CONFIG_PATH = AGRI / "src" / "models" / "model_config_agri.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def tables_from_records(tables_json: dict) -> dict[str, pd.DataFrame]:
    """配置 JSON 里的冻结表 → DataFrame（恢复索引）。"""
    out = {}
    for name, records in tables_json.items():
        df = pd.DataFrame(records)
        idx_cols = [c for c in ("n", "k", "cond_val") if c in df.columns]
        if idx_cols:
            df = df.set_index(idx_cols)
            if df.index.nlevels == 1:
                df.index.name = idx_cols[0]
        out[name] = df
    return out


def main() -> int:
    cfg = load_config()
    sig_cfg = cfg["signals"]
    tables = tables_from_records(cfg["streak_tables"])

    import db_agri  # noqa: PLC0415 — 延迟导入便于脚本独立运行

    try:
        data = load_core_data(use_cache_days=None)
        feats = build_features(data, regime_params=cfg["regime"])
    except Exception as e:  # noqa: BLE001 — 数据源全挂：记录并降级退出
        msg = f"data fetch failed: {type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
        try:
            db_agri.log_error("tracker", msg)
        except Exception:  # noqa: BLE001
            print(msg, file=sys.stderr)
        print(f"[SILENT] Score: 0 | 数据获取失败，今日无信号（{type(e).__name__}）")
        return 1

    daily, cond, factors = feats["daily"], feats["cond"], feats["factors"]
    score_panic = composite_score(factors, cfg["factors"]["panic_factors"])

    today = daily.index[-1]
    close_today = float(daily["close"].iloc[-1])
    cycle_score = float(cond["cycle_score"].iloc[-1])
    cycle_phase = str(cond["cycle_phase"].iloc[-1])
    hog_phase = str(cond["hog_phase"].iloc[-1])
    recession = float(cond["recession_prob"].iloc[-1])
    streak_today = int(cond["streak"].iloc[-1]) if pd.notna(cond["streak"].iloc[-1]) else 0
    panic_today = float(score_panic.iloc[-1])

    # 重放全历史目标仓位 → 持仓状态 + 今日事件
    pos = desired_position_v12(cond, daily["close"], score_panic, {
        "theta_in": sig_cfg["theta_in"], "theta_out": sig_cfg["theta_out"],
        "panic_threshold": sig_cfg["panic_threshold"], "exit_mode": sig_cfg["exit_mode"],
    })
    sig_all = position_signals(pos)
    bt = run_backtest(sig_all, daily.index[0], today, close=daily["close"])
    holding = bt["state"]["position"].iloc[-1] == 1
    buy_date = None
    if holding and bt["open_trade"]:
        buy_date = str(bt["open_trade"]["buy_date"].date())
        hold_days = (today - bt["open_trade"]["buy_date"]).days
    else:
        hold_days = None

    # 今日事件（T 日收盘产生、T+1 执行）
    event = "持有" if holding else "空仓"
    if bool(sig_all["buy"].iloc[-1]):
        event = "买入（明日执行）"
    elif bool(sig_all["sell"].iloc[-1]):
        if holding and buy_date and (today - pd.Timestamp(buy_date)).days < 7:
            event = "卖出预警（未满 7 天，第 8 天起执行）"
        else:
            event = "卖出（明日执行）"

    # 连跌参考卡
    cond_today = cond.iloc[-1]
    card = current_streak_card(streak_today, cond_today, tables) if streak_today >= 1 else None

    # 警报分级：RED=今日有可执行动作；YELLOW=接近触发或持有中的风险提示；SILENT=常态
    near_buy = (panic_today >= 70) or (cycle_score > sig_cfg["theta_out"] and cycle_score <= 0.15)
    near_sell = holding and (recession > 0.6 or cycle_score < 0.15)
    if "买入" in event or ("卖出" in event and "预警" not in event):
        alert = "RED"
    elif "预警" in event or near_buy or near_sell:
        alert = "YELLOW"
    else:
        alert = "SILENT"

    mk = tables["markov"]
    p_up = float(mk.loc[streak_today, "p_up_tomorrow"]) if streak_today in mk.index else None

    snapshot = {
        "cycle_score": round(cycle_score, 3),
        "cycle_phase": cycle_phase,
        "hog_phase": hog_phase,
        "recession_prob": round(recession, 3),
        "panic_score": round(panic_today, 1),
        "streak_days": streak_today,
        "hold_days": hold_days,
        "event": event,
        "card": card,
    }

    print(f"[{alert}] Score: {int(round(panic_today))} | 农业 {cfg['version']} {today.date()}")
    print(f"价格 {close_today:.0f} | 周期 {cycle_phase}({cycle_score:+.2f}) | 猪周期 {hog_phase} | "
          f"收缩概率 {recession:.0%}")
    print(f"持仓 {'是（已 ' + str(hold_days) + ' 天）' if holding else '否'} | 今日建议: {event}")
    print(f"连跌 {streak_today} 天 | P(明日涨|k)={p_up if p_up is not None else '—'} | "
          f"恐慌分 {panic_today:.0f}（买入加速线 {sig_cfg['panic_threshold']}）")
    if card:
        parts = [f"{k}:{v['state']}(P涨{v['p_up']:.0%},20日中位{v['fwd20_med']:+.1%})"
                 for k, v in card["conditions"].items()]
        print("L-B2 参考卡: " + " | ".join(parts) if parts else "L-B2 参考卡: 当前无连跌")
    print(f"警报级别: {alert.upper()}")

    try:
        db_agri.save_signal(
            date=str(today.date()), score=panic_today, action=event, alert_level=alert,
            price=close_today, holding=holding, cycle_score=cycle_score,
            cycle_phase=cycle_phase, hog_phase=hog_phase, recession_prob=recession,
            streak_days=streak_today, p_up_tomorrow=p_up, panic_score=panic_today,
            buy_date=buy_date, model_version=cfg["version"],
            factor_snapshot=snapshot, is_live=True,
        )
    except Exception as e:  # noqa: BLE001
        db_agri.log_error("tracker", f"save_signal failed: {e}")

    # 供 dashboard 使用的最新状态
    hist = bt["state"][["position"]].join(daily["close"]).iloc[-600:]
    history = [[str(d.date()), round(float(c), 1), int(p)]
               for d, c, p in hist.itertuples(index=True, name=None)]
    # 策略 vs 指数累计净值（近 600 个交易日，按窗口起点归一=1，含费用与 7 天约束）
    nav = pd.DataFrame({
        "strat": (1 + bt["state"]["strat_ret"].fillna(0)).cumprod(),
        "index": (1 + bt["state"]["index_ret"].fillna(0)).cumprod(),
    }).iloc[-600:]
    nav = nav / nav.iloc[0]
    nav_history = [[str(d.date()), round(float(a), 4), round(float(b), 4)]
                   for d, a, b in nav.itertuples(index=True, name=None)]
    state_path = AGRI / "data" / "processed" / "latest_state.json"
    state_path.write_text(json.dumps(
        {"date": str(today.date()), "alert": alert, "snapshot": snapshot,
         "model_version": cfg["version"], "history": history,
         "nav_history": nav_history,
         "generated_at": datetime.now().isoformat(timespec="seconds")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
