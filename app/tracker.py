"""
医药生物板块底部探测器 — 每周跟踪器

用法:
    python app/tracker.py              # 命令行
    streamlit run app/tracker.py       # Web界面
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

try:
    import streamlit as st
    IN_STREAMLIT = True
except ImportError:
    IN_STREAMLIT = False


def _load_data() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.data_fetcher.akshare_source import AKShareSource
    return AKShareSource().fetch_all("2018-01-01")


def _compute(data: dict, custom_price: float = None) -> dict:
    """计算信号。custom_price: 可选, 用指定价格覆盖最新周数据（用于试算）"""
    from src.models.turning_points import TurningPointDetector

    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    # 用 custom_price 覆盖最新一周的收盘价（"跌到XX会触发"的试算功能）
    if custom_price is not None and len(med_w) > 0:
        med_w.iloc[-1] = custom_price

    det = TurningPointDetector()
    df = det.compute(med_w)
    latest = df.iloc[-1]

    # 规则状态直接从 df 读取（与 Score 计算完全一致）
    rule_defs = [
        ("rule_rsi",   "R:RSI超卖",     f"{latest['rsi']:.1f}",               "< 30",          "短期动能衰竭"),
        ("rule_dd",    "D:深度回撤",     f"{latest['drawdown_13w']:.1f}%",     "< -10%",        "跌幅充分"),
        ("rule_cheap", "C:极度便宜",     f"{latest['val_pct_5y']:.0f}%",       "< 15%分位",     "历史底部区域"),
        ("rule_panic", "P:恐慌指数",     f"偏度{latest['skew_13w']:.2f}/波动率{latest['vol_annual']:.1f}%",
                                         "偏度<-1 或 波动>80分位",               "极端左尾或恐慌"),
        ("rule_micro", "M:聪明钱流入",   "ETF份额",                             "价跌+份额增",    "机构越跌越买"),
    ]

    rules_status = []
    for col, name, val, thresh, desc in rule_defs:
        rules_status.append({
            "name": name, "triggered": bool(latest[col]),
            "value": val, "threshold": thresh, "description": desc,
        })

    from src.models.turning_points import distance_to_trigger, alert_level
    dist = distance_to_trigger(df, med_w)

    # 读取历史 + 保存今天 (合并为一次IO，避免竞态)
    hist_path = Path("data/processed/signal_history.csv")
    today_str = str(latest.name.date())
    prev_score = None
    if not hist_path.parent.exists():
        hist_path.parent.mkdir(parents=True, exist_ok=True)
    if hist_path.exists():
        hist = pd.read_csv(hist_path)
        if len(hist) > 0:
            prev_score = int(hist.iloc[-1].get("score", 0))
        hist = hist[hist["date"] != today_str]
    else:
        hist = pd.DataFrame(columns=["date", "score"])
    hist = pd.concat([hist, pd.DataFrame([{"date": today_str, "score": int(latest["score"])}])], ignore_index=True)
    hist.to_csv(hist_path, index=False)

    alert = alert_level(df, prev_score)

    return {
        "date": latest.name.date(),
        "price": latest["price"],
        "rsi": latest["rsi"],
        "drawdown_13w": latest["drawdown_13w"],
        "val_pct_5y": latest["val_pct_5y"],
        "skew": latest["skew_13w"],
        "vol": latest["vol_annual"],
        "score": int(latest["score"]),
        "armed": bool(latest["armed"]),
        "buy": bool(latest["buy_signal"]),
        "macd_ok": bool(latest["macd_stable"]),
        "ma2_ok": bool(latest["above_ma2"]),
        "rules_status": rules_status,
        "distance_to_trigger": dist,
        "alert": alert,
        "df": df,
    }


# ═══════════════════════════════════════
# CLI
# ═══════════════════════════════════════

def run_cli():
    print("=" * 60)
    print("  医药生物板块(801150) — 底部探测器")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n[1/2] 拉取数据...")
    data = _load_data()
    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()
    print(f"  指数: {len(med_w)}周 ({med_w.index[0].date()} ~ {med_w.index[-1].date()})")

    print("\n[2/2] 计算信号...")
    sig = _compute(data)

    status = "BUY ZONE" if sig["buy"] else "ARMED" if sig["armed"] else "HOLD"
    print(f"\n{'='*60}")
    print(f"  {status}")
    print(f"{'='*60}")
    print(f"  日期:       {sig['date']}")
    print(f"  收盘价:     {sig['price']:.2f}")
    print(f"  Score:      {sig['score']}/5")
    print()

    for r in sig["rules_status"]:
        mark = "[ON]" if r["triggered"] else "[  ]"
        print(f"  {mark} {r['name']}: {r['value']} (阈值: {r['threshold']})")

    if sig["armed"]:
        print(f"\n  右侧确认: MACD={'ON' if sig['macd_ok'] else 'OFF'}  MA2={'ON' if sig['ma2_ok'] else 'OFF'}")

    # Distance to trigger
    print(f"\n  距离触发:")
    dist = sig["distance_to_trigger"]
    for key in ["D", "C"]:
        d = dist[key]
        if d["triggered"]:
            print(f"    {d['name']}: 已触发")
        elif d.get("trigger_price"):
            gap = d["trigger_price"] - d["current"]
            print(f"    {d['name']}: 未触发. 触发价={d['trigger_price']:.0f} (需跌至{d['trigger_price']:.0f}, 再跌{abs(d['pct_away']):.1f}%)")

    # Alert
    print(f"\n  警报: [{sig['alert']['level'].upper()}] {sig['alert']['message']}")

    df = sig["df"]
    recent = df[(df.index >= "2024-01-01") & (df["armed"] == 1)]
    if len(recent) > 0:
        print(f"\n  近期Armed信号 ({len(recent)}次):")
        for d, row in recent.tail(8).iterrows():
            print(f"    {d.date()}  sc={int(row.score)}  RSI={row.rsi:.0f}  DD={row.drawdown_13w:.0f}%  price={row.price:.0f}")

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
    c1.metric("状态", status, delta=f"Score {sig['score']}/5")
    c2.metric("RSI(14)", f"{sig['rsi']:.1f}", delta=f"{sig['rsi']-30:.1f} vs 30")
    c3.metric("13周回撤", f"{sig['drawdown_13w']:.1f}%", delta=f"{sig['drawdown_13w']+10:.1f}% vs -10%")

    st.markdown("---")
    st.subheader("五规则状态")
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
