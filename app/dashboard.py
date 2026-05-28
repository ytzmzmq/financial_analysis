"""生成自包含 HTML 看板 — 浏览器直接打开"""
import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CSS = """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f3f4f6;color:#1f2937;padding:20px}
.container{max-width:900px;margin:0 auto}
.header{text-align:center;margin-bottom:24px}
.header h1{font-size:24px;font-weight:700}
.header p{color:#6b7280;font-size:14px}
.card{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.card-title{font-size:14px;font-weight:600;color:#6b7280;text-transform:uppercase;margin-bottom:12px;letter-spacing:.5px}
.signal-badge{display:inline-block;padding:6px 16px;border-radius:20px;font-weight:700;font-size:16px;color:#fff}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}
.metric{text-align:center;padding:12px;background:#f9fafb;border-radius:8px}
.metric .val{font-size:22px;font-weight:700}
.metric .lbl{font-size:11px;color:#6b7280;margin-top:4px}
.rule-row{display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #f3f4f6;font-size:13px}
.rule-icon{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;margin-right:10px;font-size:14px;flex-shrink:0}
.rule-icon.on{background:#d1fae5;color:#065f46}
.rule-icon.off{background:#f3f4f6;color:#9ca3af}
.rule-desc{color:#6b7280;margin-left:auto;font-size:12px}
.rec-table{width:100%;font-size:12px;border-collapse:collapse}
.rec-table th,.rec-table td{text-align:center;padding:6px 8px;border-bottom:1px solid #f3f4f6}
.rec-table th{color:#6b7280;font-weight:600}
.first-signal{font-weight:600}
#chart{width:100%;height:350px}
.footer{text-align:center;color:#9ca3af;font-size:12px;margin-top:20px}
.position-card{text-align:center;padding:24px}
.position-card .pct{font-size:48px;font-weight:800}
.position-card .label{font-size:16px;color:#6b7280;margin-top:4px}"""


def build_dashboard(output_path: str = "dashboard.html"):
    from src.data_fetcher.akshare_source import AKShareSource
    from src.models.turning_points import TurningPointDetector, collapse_signals

    data = AKShareSource().fetch_all("2018-01-01")
    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    det = TurningPointDetector()
    df = det.compute(med_w)
    latest = df.iloc[-1]

    # ── 仓位 ──
    score = int(latest["score"])
    if score <= 1:
        pct, label, color = 0, "观望 (0%)", "#9CA3AF"
    elif score == 2:
        if bool(latest["right_confirm"]):
            pct, label, color = 30, "轻仓 30% — Armed + 右侧确认", "#F59E0B"
        else:
            pct, label, color = 15, "试探仓 15% — Armed, 等右侧确认", "#F59E0B"
    elif score == 3:
        pct, label, color = 50, "半仓 50% — 强信号", "#F97316"
    else:
        pct, label, color = 70, f"重仓 {pct}% — 极强信号", "#EF4444"

    # ── Distance-to-Trigger ──
    from src.models.turning_points import distance_to_trigger
    dist = distance_to_trigger(df, med_w)

    # ── 走势图数据 (周线 + 近日线末尾) ──
    weekly_data = []
    for i in range(max(0, len(df) - 104), len(df)):
        r = df.iloc[i]
        weekly_data.append({
            "time": r.name.strftime("%Y-%m-%d"),
            "value": round(float(r["price"]), 2),
            "armed": bool(r["armed"]),
            "score": int(r["score"]),
        })

    # 补近日线数据到 latest_date，使图表显示到"今天"
    daily_recent = med[med.index > df.index[-1]]
    for d, p in daily_recent.items():
        weekly_data.append({
            "time": d.strftime("%Y-%m-%d"),
            "value": round(float(p), 2),
            "armed": False,
            "score": 0,
        })

    # 数据源日期
    data_date_str = df.index[-1].strftime("%Y-%m-%d")
    daily_latest_str = med.index[-1].strftime("%Y-%m-%d") if len(med) > 0 else data_date_str

    # ── 规则 HTML ──
    rule_defs = [
        ("R: RSI超卖", bool(latest["rule_rsi"]), f'{latest["rsi"]:.1f}', "< 30", "短期动能衰竭"),
        ("D: 深度回撤", bool(latest["rule_dd"]), f'{latest["drawdown_13w"]:.1f}%', "< -10%", "跌幅充分"),
        ("C: 极度便宜", bool(latest["rule_cheap"]), f'{latest["val_pct_5y"]:.0f}%', "< 15%", "历史低位区域"),
        ("P: 恐慌指数", bool(latest["rule_panic"]), f'偏度{latest["skew_13w"]:.2f}', "偏度<-1 或 波动飙升", "极端左尾事件"),
        ("M: 聪明钱", bool(latest["rule_micro"]), "待数据", "ETF份额逆势增", "机构越跌越买"),
    ]
    rules_html = ""
    for name, ok, val, thresh, desc in rule_defs:
        rules_html += f"""<div class="rule-row">
    <div class="rule-icon {'on' if ok else 'off'}">{'Y' if ok else '-'}</div>
    <div><strong>{name}</strong><br><span style="font-size:11px;color:#6b7280">{val} (阈值: {thresh})</span></div>
    <div class="rule-desc">{desc}</div>
</div>"""

    # ── 历史信号 HTML ──
    collapsed = collapse_signals(df["armed"])
    armed_html = ""
    for i in range(max(0, len(df) - 156), len(df)):
        r = df.iloc[i]
        if not bool(r["armed"]):
            continue
        d = r.name
        first = bool(collapsed.iloc[i])
        armed_html += f"""<tr class="{'first-signal' if first else ''}">
    <td>{d.strftime('%Y-%m-%d')}</td><td>{int(r['score'])}/5</td><td>{r['price']:.0f}</td>
    <td>{r['rsi']:.1f}</td><td>{r['drawdown_13w']:.1f}%</td>
    <td>{'*' if first else ''}</td>
</tr>"""

    # ── 水位线 HTML ──
    waterline_html = ""
    for key, emoji in [("D", "🔴"), ("C", "🟢")]:
        d = dist[key]
        if d["triggered"]:
            waterline_html += f'<div style="padding:6px 12px;background:#f0fdf4;border-radius:6px;font-size:13px">{emoji} <b>{d["name"]}</b>: 已触发 ✓</div>'
        elif d.get("trigger_price"):
            waterline_html += f'<div style="padding:6px 12px;background:#fefce8;border-radius:6px;font-size:13px">{emoji} <b>{d["name"]}</b>: 触发价 <b>{d["trigger_price"]:.0f}</b> (距当前 {d["pct_away"]:+.1f}%)</div>'

    # ── 水位线 JSON ──
    waterline_prices = {}
    for key in ["D", "C"]:
        if not dist[key]["triggered"] and dist[key].get("trigger_price"):
            waterline_prices[key] = dist[key]["trigger_price"]

    # ── JSON ──
    chart_data = json.dumps(weekly_data, ensure_ascii=False)
    waterline_json = json.dumps(waterline_prices, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>医药板块风险收益比监控器</title>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>医药板块 风险收益比监控器</h1>
  <p>申万医药生物(801150) | 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')} | 指标数据至 {data_date_str} | 日线至 {daily_latest_str} | 数据源: AKShare</p>
</div>

<div class="card">
  <div class="position-card">
    <div class="pct" style="color:{color}">{pct}%</div>
    <div class="label">{label}</div>
    <div style="margin-top:12px">
      <span class="signal-badge" style="background:{color}">Score {score}/5</span>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-title">关键指标</div>
  <div class="metrics">
    <div class="metric">
      <div class="val">{latest["price"]:.0f}</div>
      <div class="lbl">收盘价 ({daily_latest_str})</div>
    </div>
    <div class="metric">
      <div class="val" style="color:{'#ef4444' if latest['rsi']<30 else '#1f2937'}">{latest["rsi"]:.1f}</div>
      <div class="lbl">RSI(14) Wilder ({data_date_str})</div>
    </div>
    <div class="metric">
      <div class="val" style="color:{'#ef4444' if latest['drawdown_13w']<-10 else '#1f2937'}">{latest["drawdown_13w"]:.1f}%</div>
      <div class="lbl">13周最大回撤 ({data_date_str})</div>
    </div>
    <div class="metric">
      <div class="val" style="color:{'#ef4444' if latest['val_pct_5y']<15 else '#1f2937'}">{latest["val_pct_5y"]:.0f}%</div>
      <div class="lbl">5年价格分位 ({data_date_str})</div>
    </div>
    <div class="metric">
      <div class="val">{latest["vol_annual"]:.1f}%</div>
      <div class="lbl">年化波动率 ({data_date_str})</div>
    </div>
    <div class="metric">
      <div class="val" style="color:{'#10b981' if latest['right_confirm'] else '#9ca3af'}">{'已触发' if latest['right_confirm'] else '未触发'}</div>
      <div class="lbl">右侧确认 MACD/MA2 ({data_date_str})</div>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-title">触发水位线 (今天跌到哪会触发?)</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">{waterline_html if waterline_html else '<span style="color:#9ca3af">无法计算触发价格</span>'}</div>
</div>

<div class="card">
  <div class="card-title">五规则状态</div>
  {rules_html}
</div>

<div class="card">
  <div class="card-title">走势图 (近2年周线+近日线 | 黄箭头=Armed | 虚线=触发水位线 | 数据至 {daily_latest_str})</div>
  <div id="chart"></div>
</div>

<div class="card">
  <div class="card-title">近期 Armed 信号记录 (* = 入场信号)</div>
  <table class="rec-table">
    <tr><th>日期</th><th>Score</th><th>价格</th><th>RSI</th><th>回撤</th><th>入场</th></tr>
    {armed_html}
  </table>
</div>

<div class="footer">
  数据源: AKShare | 申万医药生物指数(801150) | 仅供研究参考, 不构成投资建议<br>
  方法论: Triple Barrier + 五规则探测器 | 定位: 风险收益比监控器 | V4.2
</div>

</div>
<script>
var d = {chart_data};
var chart = LightweightCharts.createChart(document.getElementById('chart'), {{
    layout: {{ background: {{ color: '#ffffff' }}, textColor: '#1f2937' }},
    grid: {{ vertLines: {{ color: '#f3f4f6' }}, horzLines: {{ color: '#f3f4f6' }} }},
    rightPriceScale: {{ borderColor: '#d1d5db' }},
    timeScale: {{ borderColor: '#d1d5db', timeVisible: true }},
    width: document.getElementById('chart').clientWidth,
    height: 350,
}});
var line = chart.addLineSeries({{ color: '#3B82F6', lineWidth: 2 }});
var prices = d.map(function(w) {{ return {{ time: w.time, value: w.value }}; }});
var markers = d.filter(function(w) {{ return w.armed; }}).map(function(w) {{
    return {{ time: w.time, position: 'belowBar', color: '#F59E0B', shape: 'arrowUp', text: String(w.score) }};
}});
line.setData(prices);
line.setMarkers(markers);

// 水位线
var waterlines = {waterline_json};
var colors = {{ 'D': '#EF4444', 'C': '#10B981' }};
var labels = {{ 'D': '回撤触发', 'C': '估值触发' }};
Object.keys(waterlines).forEach(function(key) {{
    var price = waterlines[key];
    var wl = chart.addLineSeries({{
        color: colors[key], lineWidth: 1, lineStyle: 2, priceLineVisible: false,
        lastValueVisible: false,
    }});
    var data = [];
    for (var i = 0; i < prices.length; i++) {{
        data.push({{ time: prices[i].time, value: price }});
    }}
    wl.setData(data);
    // 右侧标签
    var marker = {{
        time: prices[prices.length-1].time, position: 'inLine', color: colors[key],
        shape: 'circle', text: labels[key] + ' ' + price.toFixed(0),
    }};
    wl.setMarkers([marker]);
}});

chart.timeScale().fitContent();
window.addEventListener('resize', function() {{
    chart.applyOptions({{ width: document.getElementById('chart').clientWidth }});
}});
</script>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Dashboard saved to {output_path}")
    return output_path


if __name__ == "__main__":
    build_dashboard()
