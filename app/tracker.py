"""
医药生物板块底部探测器 — 每周跟踪器

用法:
    python app/tracker.py              # 命令行
    streamlit run app/tracker.py       # Web界面

V5.2: 消费 evaluate_signal() 结果，不再自己理解模型。
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

from app.db import save_signal, get_latest_score

try:
    import streamlit as st
    IN_STREAMLIT = True
except ImportError:
    IN_STREAMLIT = False


def _load_data() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.data_fetcher.akshare_source import AKShareSource
    ak_src = AKShareSource()
    med_df = ak_src.fetch_sw_medical("20180101")
    margin_df = ak_src.fetch_margin_data("20180101")
    return {"sw_medical": med_df, "total_margin": margin_df}


def _compute(data: dict, custom_price: float = None) -> dict:
    """
    计算信号。

    custom_price: 可选, 用指定价格覆盖最新周数据（用于试算）
    """
    from src.models.rule_registry import (
        evaluate_signal, evaluate_signal_history,
        MODEL_CONFIGS, ACTIVE_MODEL_VERSION
    )
    from src.models.turning_points import distance_to_trigger, alert_level

    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    # 用 custom_price 覆盖最新一周的收盘价（"跌到XX会触发"的试算功能）
    if custom_price is not None and len(med_w) > 0:
        med_w.iloc[-1] = custom_price

    # 融资数据 (T+1时滞)
    margin_w = None
    if "total_margin" in data and not data["total_margin"].empty:
        mdf = data["total_margin"].set_index("date")["value"].sort_index()
        margin_w = mdf.resample("W-FRI").last().dropna().shift(1)

    config = MODEL_CONFIGS[ACTIVE_MODEL_VERSION]

    # ── 核心判定：调用 evaluate_signal() ──
    result = evaluate_signal(ACTIVE_MODEL_VERSION, med_w, margin_w=margin_w)

    # 构建 df 用于图表 / 历史信号显示
    df = evaluate_signal_history(ACTIVE_MODEL_VERSION, med_w, margin_w=margin_w)

    # Distance to trigger（传入 config，V5.2 会额外计算 L1/M1）
    dist = distance_to_trigger(df, med_w, margin_w=margin_w, config=config)

    # 获取上一次 score（用于 alert_level 计算）
    prev_score = get_latest_score()

    # Alert level（传入 config，V5.2 按 tier 判定）
    alert = alert_level(df, prev_score, config=config)

    today_str = str(med_w.index[-1].date())

    # 持久化到 SQLite（试算模式不写入）
    if custom_price is None:
        save_signal(
            date=today_str,
            score=result.score,
            armed=result.is_armed,
            alert_level=alert["level"],
            price=result.price,
            rsi=result.rsi,
            drawdown_13w=result.drawdown_13w,
            val_pct_5y=result.val_pct_5y,
            rules_status=result.rules_status,
            distance_to_trigger=dist,
            # V5.2 新增字段
            model_version=result.model_version,
            signal_tier=result.signal_tier,
            n_factors=result.n_factors_triggered,
            is_live_signal=True,
            factor_snapshot=result.factor_snapshot,
            l1_triggered=result.l1_triggered,
        )

    return {
        "date": result.date,
        "price": result.price,
        "rsi": result.rsi,
        "drawdown_13w": result.drawdown_13w,
        "val_pct_5y": result.val_pct_5y,
        "skew": result.skew_13w,
        "vol": result.vol_annual,
        "score": result.score,
        "max_score": result.max_score,
        "signal_tier": result.signal_tier,
        "n_factors": result.n_factors_triggered,
        "armed": result.is_armed,
        "buy": bool(df.iloc[-1]["buy_signal"]),
        "macd_ok": bool(df.iloc[-1]["macd_stable"]),
        "ma2_ok": bool(df.iloc[-1]["above_ma2"]),
        "rules_status": result.rules_status,
        "distance_to_trigger": dist,
        "alert": alert,
        "df": df,
        "model_version": result.model_version,
    }


# ═══════════════════════════════════════
# CLI
# ═══════════════════════════════════════

def run_cli():
    import traceback as tb_mod
    from app.db import log_error

    print("=" * 60)
    print("  医药生物板块(801150) — 底部探测器")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 拉取数据
    print("\n[1/2] 拉取数据...")
    try:
        data = _load_data()
    except Exception as e:
        err_msg = f"数据拉取失败: {e}"
        print(f"\n  [ERROR] {err_msg}")
        log_error("data_fetch", err_msg, "error")
        return

    # 数据新鲜度校验
    try:
        med = data["sw_medical"].set_index("date")["close"].sort_index()
        med_w = med.resample("W-FRI").last().dropna()
        latest_date = med_w.index[-1]
        days_stale = (pd.Timestamp.now() - latest_date).days
        if days_stale > 7:
            warn_msg = f"数据可能过旧: 最新数据 {latest_date.date()}，距今 {days_stale} 天"
            print(f"  [WARNING] {warn_msg}")
            log_error("data_freshness", warn_msg, "warning")
        if len(med_w) < 52:
            warn_msg = f"数据量不足: 仅 {len(med_w)} 周（建议至少 52 周）"
            print(f"  [WARNING] {warn_msg}")
            log_error("data_quality", warn_msg, "warning")
        print(f"  指数: {len(med_w)}周 ({med_w.index[0].date()} ~ {med_w.index[-1].date()})")
    except Exception as e:
        err_msg = f"数据解析失败: {e}"
        print(f"\n  [ERROR] {err_msg}")
        log_error("data_parse", err_msg, "error")
        return

    # 计算信号
    print("\n[2/2] 计算信号...")
    try:
        sig = _compute(data)
    except Exception as e:
        err_msg = f"信号计算失败: {e}"
        print(f"\n  [ERROR] {err_msg}")
        log_error("compute", err_msg, "error")
        return

    # ── 输出 ──
    status = "BUY ZONE" if sig["buy"] else "ARMED" if sig["armed"] else "HOLD"
    print(f"\n{'='*60}")
    print(f"  {status}  [{sig['signal_tier']}]  ({sig['model_version']})")
    print(f"{'='*60}")
    print(f"  日期:       {sig['date']}")
    print(f"  收盘价:     {sig['price']:.2f}")
    print(f"  Score:      {sig['score']}")
    print(f"  Factors:    {sig['n_factors']} triggered")
    print()

    for r in sig["rules_status"]:
        mark = "[ON]" if r["triggered"] else "[  ]"
        print(f"  {mark} {r['name']}: {r['value']} (阈值: {r['threshold']})")

    if sig["armed"]:
        print(f"\n  右侧确认: MACD={'ON' if sig['macd_ok'] else 'OFF'}  MA2={'ON' if sig['ma2_ok'] else 'OFF'}")

    # Distance to trigger (只显示有明确触发价格的因子: S3, V1)
    print(f"\n  距离触发:")
    dist = sig["distance_to_trigger"]
    for key in ["S3", "V1"]:
        if key not in dist:
            continue
        d = dist[key]
        if d["triggered"]:
            print(f"    {d['name']}: 已触发")
        elif d.get("trigger_price") is not None:
            gap = d["trigger_price"] - d["current"]
            print(f"    {d['name']}: 未触发. 触发价={d['trigger_price']:.0f} (需跌至{d['trigger_price']:.0f}, 再跌{abs(d['pct_away']):.1f}%)")

    # Alert
    print(f"\n  警报: [{sig['alert']['level'].upper()}] {sig['alert']['message']}")

    df = sig["df"]
    recent = df[(df.index >= "2024-01-01") & (df["armed"] == 1)]
    if len(recent) > 0:
        print(f"\n  近期Armed信号 ({len(recent)}次):")
        for d, row in recent.tail(8).iterrows():
            tier_str = f"tier={row.get('signal_tier', '')}" if 'signal_tier' in row.index else ""
            print(f"    {d.date()}  sc={row.score}  RSI={row.rsi:.0f}  DD={row.drawdown_13w:.0f}%  price={row.price:.0f}  {tier_str}")

    print()


# ═══════════════════════════════════════
# Streamlit
# ═══════════════════════════════════════

def run_streamlit():
    st.set_page_config(page_title="医药底部探测器", page_icon="📊", layout="wide")
    st.title("📊 医药生物板块 — 底部探测器")
    st.caption(f"更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.spinner("数据加载中..."):
        sig = _compute(_load_data())

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    status = "BUY" if sig["buy"] else "ARMED" if sig["armed"] else "HOLD"
    c1.metric("状态", f"{status} [{sig['signal_tier']}]", delta=f"Score {sig['score']}")
    c2.metric("RSI(14)", f"{sig['rsi']:.1f}", delta=f"{sig['rsi']-30:.1f} vs 30")
    c3.metric("13周回撤", f"{sig['drawdown_13w']:.1f}%", delta=f"{sig['drawdown_13w']+10:.1f}% vs -10%")

    st.markdown("---")
    st.subheader("因子状态")
    for r in sig["rules_status"]:
        icon = "✅" if r["triggered"] else "⬜"
        st.write(f"{icon} **{r['name']}**: {r['value']} (阈值: {r['threshold']}) — *{r['description']}*")

    st.markdown("---")
    st.subheader("近期Armed信号")
    df = sig["df"]
    recent = df[(df.index >= "2024-01-01") & (df["armed"] == 1)]
    if len(recent) > 0:
        st.dataframe(recent[["price", "score", "rsi", "drawdown_13w", "val_pct_5y"]],
                     use_container_width=True)

    st.caption("REPORT.md — 完整方法论与验证")


if __name__ == "__main__":
    if IN_STREAMLIT:
        run_streamlit()
    else:
        run_cli()
