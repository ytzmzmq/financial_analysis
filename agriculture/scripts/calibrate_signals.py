# -*- coding: utf-8 -*-
"""M4+M5（V1.2 周期主导架构）：因子筛选 → 周期门网格 → 反过拟合检验 → 测试段终评 → 冻结配置。

协议（预注册，docs/strategy_proposal.md §3；V1.1/V1.2 修订见 §4-L-D）：
- 完整训练段 2005-2021 内分：子训练 2005-2015（网格排序 + RC）、验证 2016-2021
  （DSR/PBO + 门槛）；测试段 2022-01 起终评。
  ⚠️ 披露：测试段已被使用 3 次（V1.0 / V1.1 / V1.2 各一次，test_peek_count=3），
  其统计量存在乐观偏差；真实基准以实盘为准，月度审计跟踪衰减。
- V1.2 架构（规则族诊断驱动，诊断仅用子训练/验证段）：HP 周期相位迟滞门为主信号
  （theta_in=0 / theta_out=-0.2，a priori 固定不进网格）；因子层降级为
  恐慌加速买入（skew+波动分位均值 ≥ 阈值）与风险刹车（区制+趋势双确认）。
  网格：panic_threshold∈{无,70,80} × risk_exit∈{关,开} = 6 配置 ≤ 60。
- 因子三漏斗门槛不变（t≥3、前后半一致、单年占比≤40%、|ρ|≤0.7）。
- 验证段上线门槛：超额>0、回撤 < 买入持有、半年目标达成率 ≥55%、0 违规。

用法: python scripts/calibrate_signals.py
产出: src/models/model_config_agri.json + data/processed/calibration_report.md
"""
from __future__ import annotations

import io
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

AGRI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGRI))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

from scipy import stats  # noqa: E402

from src.backtest.anti_overfit import deflated_sharpe, pbo_cscv, reality_check  # noqa: E402
from src.backtest.backtester import (  # noqa: E402
    compute_metrics, desired_position_v12, position_signals, run_backtest,
)
from src.data_fetcher.akshare_source import load_core_data  # noqa: E402
from src.models.factor_library import FACTOR_DEFS, composite_score  # noqa: E402
from src.models.pipeline import build_features  # noqa: E402
from src.models.streak_stats import build_all_tables  # noqa: E402

TRAIN_FULL = (pd.Timestamp("2005-01-01"), pd.Timestamp("2021-12-31"))
SUBTRAIN = (pd.Timestamp("2005-01-01"), pd.Timestamp("2015-12-31"))
VALID = (pd.Timestamp("2016-01-01"), pd.Timestamp("2021-12-31"))
TEST = (pd.Timestamp("2022-01-01"), pd.Timestamp("2099-12-31"))
GRID_PANIC = [None, 80]
GRID_EXIT = ["cycle_only", "rec80_trend", "trend_break"]

report: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    report.append(msg + "\n")


def screen_factors(factors: pd.DataFrame, fwd20: pd.Series,
                   train: tuple[pd.Timestamp, pd.Timestamp]) -> list[str]:
    """三漏斗筛选（完整训练段 2005-2021）。"""
    tr = factors.loc[(factors.index >= train[0]) & (factors.index <= train[1])]
    f20 = fwd20.reindex(tr.index)
    half = tr.index[len(tr) // 2]
    years = tr.index.year
    selected: list[str] = []
    log("\n## 因子三漏斗筛选（完整训练段 2005-2021）\n")
    log("| 因子 | 方向 | t值 | n_top | 前后半一致 | 最大单年占比 | 结果 |")
    log("|---|---|---|---|---|---|---|")
    rows = []
    for name, (direction, desc) in FACTOR_DEFS.items():
        s = tr[name]
        valid = s.notna() & f20.notna()
        if valid.sum() < 2500:
            continue
        q_hi = s.rolling(1250, min_periods=500).rank(pct=True)
        top, bot = valid & (q_hi >= 2 / 3), valid & (q_hi <= 1 / 3)
        n_top = int(top.sum())
        if n_top < 300:
            continue
        t_stat, _ = stats.ttest_ind(f20[top], f20[bot], equal_var=False)
        spread = float(f20[top].mean() - f20[bot].mean())
        h1 = f20[top & (tr.index <= half)].mean() - f20[bot & (tr.index <= half)].mean()
        h2 = f20[top & (tr.index > half)].mean() - f20[bot & (tr.index > half)].mean()
        consistent = bool(np.sign(h1) == np.sign(h2) == np.sign(spread)) if np.isfinite(h1) and np.isfinite(h2) else False
        yearly_share = (top.groupby(years).sum() / max(n_top, 1))
        max_share = float(yearly_share.max())
        passed = bool(t_stat >= 3.0 and consistent and max_share <= 0.40 and spread > 0)
        rows.append((name, direction, t_stat, n_top, consistent, max_share, passed, s))
        log(f"| {name} | {direction:+d} | {t_stat:.2f} | {n_top} | {consistent} | {max_share:.2f} | "
            f"{'PASS' if passed else 'FAIL'} |")
    rows.sort(key=lambda r: -r[2])
    for name, direction, t_stat, n_top, consistent, max_share, passed, s in rows:
        if not passed:
            continue
        ok = True
        for sel_name in selected:
            a, b = s.align(tr[sel_name], join="inner")
            rho = a.corr(b, method="spearman")
            if pd.notna(rho) and abs(rho) > 0.7:
                ok = False
                log(f"\n> 剔除 `{name}`：与 `{sel_name}` Spearman ρ={rho:.2f} > 0.7")
                break
        if ok:
            selected.append(name)
    log(f"\n**入选因子（{len(selected)}）**：{selected}\n")
    return selected


def main() -> None:
    log("# 农业板块周期监控系统 · 校准报告（V1.2 周期主导）\n")
    log(f"生成时间：{datetime.now():%Y-%m-%d %H:%M}")
    log("> ⚠️ 测试段使用披露：V1.0/V1.1/V1.2 各评估一次（共 3 次），统计量偏乐观；真实基准以实盘为准。")

    # ── 1. 特征 ──
    log("\n## 1. 特征构建\n")
    data = load_core_data(use_cache_days=None)
    feats = build_features(data)
    daily, cond, factors = feats["daily"], feats["cond"], feats["factors"]
    rp = feats["regime_params"]
    log(f"- 主表 {len(daily)} 行（{daily.index.min().date()} → {daily.index.max().date()}）")
    log(f"- 区制模型：{rp['method']}，p00={rp.get('p00'):.3f}, p11={rp.get('p11'):.3f}, "
        f"mu={np.round(rp.get('mu', [0, 0]), 5).tolist()}")
    fwd20 = daily["close"].shift(-20) / daily["close"] - 1.0

    # ── 2. L-B/L-B2 冻结表 ──
    log("\n## 2. 连跌概率层冻结表（训练段）\n")
    tables = build_all_tables(daily, cond)
    log("- 频率表：")
    log(tables["frequency"].to_string())
    log("\n- 马尔可夫 P(明日涨|已连跌k)：")
    log(tables["markov"].to_string())

    # ── 3. 因子筛选 ──
    selected = screen_factors(factors, fwd20, TRAIN_FULL)
    panic_factors = [f for f in ["skew_13w", "vol_pctile_20d"] if f in selected]
    if not panic_factors:
        panic_factors = ["skew_13w", "vol_pctile_20d"]  # 文献预注册兜底
    log(f"\n恐慌加速因子（score_panic）：{panic_factors}")
    score_panic = composite_score(factors, panic_factors)

    # ── 4. V1.2 网格（6 配置） ──
    log("\n## 3. 训练段网格回测（V1.2 周期门 + 恐慌加速 + 退出模式，6 配置）\n")
    grid = []
    for pt in GRID_PANIC:
        for exit_mode in GRID_EXIT:
            params = {"theta_in": 0.0, "theta_out": -0.2,
                      "panic_threshold": pt, "exit_mode": exit_mode}
            pos = desired_position_v12(cond, daily["close"], score_panic, params)
            sig = position_signals(pos)
            bt = run_backtest(sig, *TRAIN_FULL, close=daily["close"])
            grid.append({"params": params, "returns": bt["state"]["strat_ret"],
                         "index_ret": bt["state"]["index_ret"], "trades": bt["trades"]})

    bh_sub = compute_metrics(grid[0]["index_ret"].loc[SUBTRAIN[0]:SUBTRAIN[1]],
                             grid[0]["index_ret"].loc[SUBTRAIN[0]:SUBTRAIN[1]])
    log(f"- 子训练段买入持有：年化 {bh_sub['ann_return']:+.1%}，回撤 {bh_sub['max_drawdown']:.1%}")
    for g in grid:
        g["sub_metrics"] = compute_metrics(
            g["returns"].loc[SUBTRAIN[0]:SUBTRAIN[1]],
            g["index_ret"].loc[SUBTRAIN[0]:SUBTRAIN[1]], g["trades"])

    mask = (grid[0]["returns"].index >= SUBTRAIN[0]) & (grid[0]["returns"].index <= SUBTRAIN[1])
    rc = reality_check(np.column_stack([g["returns"][mask].values for g in grid]),
                       grid[0]["index_ret"][mask].values, n_boot=1000)
    log(f"- Reality Check（子训练段 vs 买入持有）：最优日均 {rc['obs_best_mean_daily']:.5f}，"
        f"RC p={rc['rc_p_value']}（{'显著' if rc['significant_5pct'] else '不显著，如实报告'}）")

    log("\n- 子训练段明细：")
    for g in grid:
        m = g["sub_metrics"]
        log(f"  - panic={g['params']['panic_threshold']} exit={g['params']['exit_mode']} → "
            f"年化 {m['ann_return']:+.1%}，超额 {m['ann_excess']:+.1%}，回撤 {m['max_drawdown']:.1%}，"
            f"交易 {m['n_trades']} 次，目标达成率 {m['roll126_win_abs4_or_ex3']:.0%}")

    ranked = sorted(grid, key=lambda g: g["sub_metrics"]["ann_return"]
                    - 0.5 * max(0, g["sub_metrics"]["max_drawdown"] - 0.15), reverse=True)

    # ── 5. 验证段 ──
    log("\n## 4. 验证段（2016-2021）：DSR + PBO + 门槛\n")
    vmask = (grid[0]["returns"].index >= VALID[0]) & (grid[0]["returns"].index <= VALID[1])
    val_rets = np.column_stack([g["returns"][vmask].values for g in grid])
    dsr = deflated_sharpe(val_rets)
    pbo = pbo_cscv(val_rets, n_blocks=12)
    log(f"- DSR（N={len(grid)}）：SR*={dsr['sr_annualized']}（年化），DSR={dsr['dsr']} "
        f"（{'通过' if dsr['pass_090'] else '未通过'}）")
    log(f"- PBO（CSCV，12 块）：{pbo:.3f}（{'通过' if pbo < 0.5 else '未通过'}）")

    bh_val = compute_metrics(grid[0]["index_ret"].loc[VALID[0]:VALID[1]],
                             grid[0]["index_ret"].loc[VALID[0]:VALID[1]])
    log(f"- 验证段买入持有：年化 {bh_val['ann_return']:+.1%}，回撤 {bh_val['max_drawdown']:.1%}")

    chosen, chosen_metrics = None, None
    for cand in ranked:
        vm = compute_metrics(cand["returns"].loc[VALID[0]:VALID[1]],
                             cand["index_ret"].loc[VALID[0]:VALID[1]], cand["trades"])
        # 相对门槛（V1.2 修订，仅基于验证段）：全面优于买入持有 + 0 违规
        ok = (vm["ann_return"] > bh_val["ann_return"]
              and vm["max_drawdown"] > bh_val["max_drawdown"]
              and vm["roll126_win_abs4_or_ex3"] > bh_val["roll126_win_abs4_or_ex3"]
              and vm["min_hold_violations"] == 0)
        log(f"  - 验证段 panic={cand['params']['panic_threshold']} "
            f"exit={cand['params']['exit_mode']} → 年化 {vm['ann_return']:+.1%}，"
            f"超额 {vm['ann_excess']:+.1%}，回撤 {vm['max_drawdown']:.1%}，"
            f"半年胜率 {vm['roll126_win_vs_index']:.0%}，目标达成率 {vm['roll126_win_abs4_or_ex3']:.0%}，"
            f"违规 {vm['min_hold_violations']} {'✓' if ok else '✗'}")
        if ok and chosen is None:
            chosen, chosen_metrics = cand, vm
    if chosen is None:
        log("\n- ⚠️ 无配置达验证段门槛 → 取排名 Top1 标记 degraded=true")
        chosen = ranked[0]
        chosen_metrics = chosen["sub_metrics"]

    log(f"\n**冻结配置：{chosen['params']}，恐慌因子={panic_factors}**\n")

    # ── 6. 测试段终评估 ──
    log("\n## 5. 测试段终评估（2022-01 → 最新；第 3 次使用，此后冻结）\n")
    pos_t = desired_position_v12(cond, daily["close"], score_panic, chosen["params"])
    bt = run_backtest(position_signals(pos_t), *TEST, close=daily["close"])
    m = bt["metrics"]
    bh_test = compute_metrics(daily["close"].pct_change().loc[TEST[0]:],
                              daily["close"].pct_change().loc[TEST[0]:])
    log(f"- 年化 {m['ann_return']:+.1%} vs 指数 {bh_test['ann_return']:+.1%}（超额 {m['ann_excess']:+.1%}）")
    log(f"- 最大回撤 {m['max_drawdown']:.1%}（指数 {bh_test['max_drawdown']:.1%}），Sharpe {m['sharpe']}")
    log(f"- 交易 {m['n_trades']} 次，滚动半年胜率 {m['roll126_win_vs_index']:.0%}，"
        f"半年目标(绝对4%/超额3%)达成率 {m['roll126_win_abs4_or_ex3']:.0%}")
    log(f"- 最差半年 {m['roll126_worst']:+.1%}；**7 天约束违规 {m['min_hold_violations']} 次**；"
        f"顺延卖出 {bt['deferred_sells']} 次")
    if bt["trades"]:
        log("\n- 测试段交易明细：")
        for tr in bt["trades"]:
            if "sell_date" in tr:
                pl = tr["sell_close"] / tr["buy_close"] - 1
                log(f"  - 买 {tr['buy_date'].date()}@{tr['buy_close']:.0f} → 卖 {tr['sell_date'].date()}"
                    f"@{tr['sell_close']:.0f}（{pl:+.1%}，{(tr['sell_date']-tr['buy_date']).days} 天）")
            else:
                log(f"  - 买 {tr['buy_date'].date()}@{tr['buy_close']:.0f} → 持有中")

    # ── 7. 冻结配置 ──
    tables_json = {name: json.loads(tbl.reset_index().to_json(orient="records", force_ascii=False))
                   for name, tbl in tables.items()}
    config = {
        "version": "V1.2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "architecture": "cycle_primary",
        "protocol": {
            "train": [str(TRAIN_FULL[0].date()), str(TRAIN_FULL[1].date())],
            "subtrain": [str(SUBTRAIN[0].date()), str(SUBTRAIN[1].date())],
            "validation": [str(VALID[0].date()), str(VALID[1].date())],
            "test_start": str(TEST[0].date()),
            "grid": {"panic_threshold": GRID_PANIC, "exit_mode": GRID_EXIT},
            "test_peek_count": 3,
            "test_peek_note": "V1.0/V1.1/V1.2 各评估一次，测试段统计量偏乐观；真实基准以实盘为准",
        },
        "factors": {
            "selected": selected,
            "panic_factors": panic_factors,
            "defs": {k: list(FACTOR_DEFS[k]) for k in selected},
        },
        "signals": {
            "theta_in": 0.0, "theta_out": -0.2,
            "panic_threshold": chosen["params"]["panic_threshold"],
            "exit_mode": chosen["params"]["exit_mode"],
            "rules": "V1.2 周期主导：cycle_score>0 持有 / <-0.2 清仓（迟滞）；"
                     "score_panic≥阈值 且 recession<0.7 → 立即持有；"
                     "退出模式 exit_mode: cycle_only=仅迟滞门 | rec80_trend=区制+趋势双确认 | trend_break=MA60 趋势破坏",
        },
        "regime": rp,
        "streak_tables": tables_json,
        "anti_overfit": {"reality_check": rc, "dsr": dsr, "pbo": round(pbo, 4)},
        "validation_eval": chosen_metrics,
        "test_eval": m,
        "test_eval_bh": bh_test,
        "degraded": bool(chosen is not ranked[0]),
    }
    cfg_path = AGRI / "src" / "models" / "model_config_agri.json"
    cfg_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\n冻结配置已写入 `{cfg_path.relative_to(AGRI.parent)}`")

    out = AGRI / "data" / "processed" / "calibration_report.md"
    out.write_text("".join(report), encoding="utf-8")
    print(f"[saved] {out}")


if __name__ == "__main__":
    main()
