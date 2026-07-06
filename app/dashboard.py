"""生成自包含 HTML 看板 — 图表库首次下载缓存，之后离线可用"""
import sys, json, urllib.request, time
from pathlib import Path
from datetime import datetime
import pandas as pd, numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LW_CACHE = Path("data/lightweight-charts.min.js")
LW_CDN = "https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"

def _get_lw_js() -> str:
    """优先读本地缓存，没有则下载一次并缓存"""
    if LW_CACHE.exists() and LW_CACHE.stat().st_size > 100_000:
        return LW_CACHE.read_text(encoding="utf-8")
    print("下载图表库 (仅首次)...")
    js = urllib.request.urlopen(LW_CDN, timeout=20).read().decode("utf-8")
    LW_CACHE.parent.mkdir(parents=True, exist_ok=True)
    LW_CACHE.write_text(js, encoding="utf-8")
    print(f"已缓存 {LW_CACHE} (后续离线)")
    return js

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
#chart{width:100%;max-width:100%;height:350px;overflow:hidden}
.footer{text-align:center;color:#9ca3af;font-size:12px;margin-top:20px}
.position-card{text-align:center;padding:24px}
.position-card .pct{font-size:48px;font-weight:800}
.position-card .label{font-size:16px;color:#6b7280;margin-top:4px}"""


def build_dashboard(output_path: str = "dashboard.html"):
    from src.data_fetcher.akshare_source import AKShareSource
    from src.models.rule_registry import (
        evaluate_signal, evaluate_signal_history,
        MODEL_CONFIGS, ACTIVE_MODEL_VERSION,
    )
    from src.models.turning_points import distance_to_trigger, collapse_signals

    t0 = time.time()
    print("生成看板...")

    med_df = AKShareSource().fetch_sw_medical("20180101")
    med = med_df.set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    from src.data_fetcher.akshare_source import AKShareSource as _AKS
    margin_df = _AKS().fetch_margin_data("20180101")
    margin_w = None
    if not margin_df.empty:
        m = margin_df.set_index("date")["value"].sort_index()
        margin_w = m.resample("W-FRI").last().dropna().shift(1)

    config = MODEL_CONFIGS[ACTIVE_MODEL_VERSION]
    max_score = config.get("max_score", 10.0)

    # 核心判定
    result = evaluate_signal(ACTIVE_MODEL_VERSION, med_w, margin_w=margin_w)
    df = evaluate_signal_history(ACTIVE_MODEL_VERSION, med_w, margin_w=margin_w)
    latest = df.iloc[-1]

    score = result.score
    tier = result.signal_tier

    # 仓位建议（基于 tier）
    tier_map = {
        "hold": (0, "观望 (0%)", "#9CA3AF"),
        "weak_armed": (15, "关注区 15%", "#F59E0B"),
        "standard_armed": (40, "轻仓 40% — Armed", "#F97316"),
        "strong_armed": (60, "重仓 60% — 多因子触发", "#EF4444"),
        "armed": (40, "Armed", "#F97316"),  # V5.1 fallback
    }
    pct, label, color = tier_map.get(tier, (0, "观望", "#9CA3AF"))
    # V5.1 兼容: 如果 armed_rule 是 score_threshold, 按 score 判断
    if config.get("armed_rule") == "score_threshold":
        if score < 2.5:      pct, label, color = 0, "观望 (0%)", "#9CA3AF"
        elif score < 3.5:    pct, label, color = 15, "关注区 15%", "#F59E0B"
        elif score < 5.5:    pct, label, color = 40, "轻仓 40% — Armed", "#F97316"
        else:                pct, label, color = 60, "重仓 60% — 多因子触发", "#EF4444"

    dist = distance_to_trigger(df, med_w, margin_w=margin_w, config=config)

    weekly_data = []
    for i in range(max(0, len(df) - 104), len(df)):
        r = df.iloc[i]
        weekly_data.append({"time": r.name.strftime("%Y-%m-%d"), "value": round(float(r["price"]), 2),
                            "armed": bool(r["armed"]), "score": round(float(r["score"]), 1)})

    data_date_str = df.index[-1].strftime("%Y-%m-%d")

    # 因子状态（从 evaluate_signal 的 rules_status 动态生成）
    rules_html = ""
    for r in result.rules_status:
        rules_html += f"""<div class="rule-row">
    <div class="rule-icon {'on' if r['triggered'] else 'off'}">{'Y' if r['triggered'] else '-'}</div>
    <div><strong>{r['name']}</strong><br><span style="font-size:11px;color:#6b7280">{r['value']} (阈值: {r['threshold']})</span></div>
</div>"""

    collapsed = collapse_signals(df["armed"])
    armed_html = ""
    for i in range(max(0, len(df) - 156), len(df)):
        r = df.iloc[i]
        if not bool(r["armed"]): continue
        d = r.name; first = bool(collapsed.iloc[i])
        armed_html += f"""<tr class="{'first-signal' if first else ''}">
    <td>{d.strftime('%Y-%m-%d')}</td><td>{float(r['score']):.1f}</td><td>{r['price']:.0f}</td>
    <td>{r['rsi']:.1f}</td><td>{r['drawdown_13w']:.1f}%</td><td>{'*' if first else ''}</td></tr>"""

    waterline_html = ""
    for key, emoji in [("S3",""),("V1","")]:
        dv = dist[key]
        if dv["triggered"]:
            waterline_html += f'<div style="padding:6px 12px;background:#f0fdf4;border-radius:6px;font-size:13px">{emoji}<b>{dv["name"]}</b>: 已触发</div>'
        elif dv.get("trigger_price") and not np.isnan(dv["trigger_price"]):
            waterline_html += f'<div style="padding:6px 12px;background:#fefce8;border-radius:6px;font-size:13px">{emoji}<b>{dv["name"]}</b>: 触发价 <b>{dv["trigger_price"]:.0f}</b> (距当前 {dv["pct_away"]:+.1f}%)</div>'

    waterline_prices = {}
    for key in ["S3", "V1"]:
        if not dist[key]["triggered"] and dist[key].get("trigger_price") and not np.isnan(dist[key]["trigger_price"]):
            waterline_prices[key] = dist[key]["trigger_price"]

    # ── 图表库：内联（首次下载缓存） ──
    try:
        lw_js = _get_lw_js()
        lw_tag = f"<script>{lw_js}</script>"
    except Exception as e:
        print(f"图表库加载失败: {e}")
        lw_tag = f'<script src="{LW_CDN}"></script>'

    chart_data = json.dumps(weekly_data, ensure_ascii=False)
    waterline_json = json.dumps(waterline_prices, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>医药板块风险收益比监控器</title>
{lw_tag}
<style>{CSS}</style>
</head>
<body><div class="container">
<div class="header">
  <h1>医药板块 风险收益比监控器</h1>
  <p>申万医药生物(801150) | 数据至 {data_date_str} | {"实时 (via 512170 ETF)" if med.index[-1].date() == pd.Timestamp.today().date() else "EOD"} | 耗时 {time.time()-t0:.1f}s</p>
</div>
<div class="card"><div class="position-card">
  <div class="pct" style="color:{color}">{pct}%</div>
  <div class="label">{label}</div>
  <div style="margin-top:12px"><span class="signal-badge" style="background:{color}">Score {score:.1f} [{tier}]</span></div>
  <div style="margin-top:10px;display:flex;justify-content:center;gap:8px">
    <input type="number" id="trial-price" placeholder="试算点位(如7400)" style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;width:150px;font-size:13px">
    <button onclick="trialCalc()" style="padding:6px 14px;background:#3B82F6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px">试算</button>
    <span id="trial-result" style="font-size:13px;color:#6b7280;align-self:center"></span>
  </div>
</div></div>
<div class="card"><div class="card-title">关键指标 ({data_date_str})</div><div class="metrics">
  <div class="metric"><div class="val">{latest["price"]:.0f}</div><div class="lbl">收盘价</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['rsi']<30 else '#1f2937'}">{latest["rsi"]:.1f}</div><div class="lbl">RSI(14) Wilder</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['drawdown_13w']<-10 else '#1f2937'}">{latest["drawdown_13w"]:.1f}%</div><div class="lbl">13周最大回撤</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['val_pct_5y']<15 else '#1f2937'}">{latest["val_pct_5y"]:.0f}%</div><div class="lbl">5年价格分位</div></div>
  <div class="metric"><div class="val">{latest["vol_annual"]:.1f}%</div><div class="lbl">年化波动率</div></div>
  <div class="metric"><div class="val" style="color:{'#10b981' if latest['right_confirm'] else '#9ca3af'}">{'已触发' if latest['right_confirm'] else '未触发'}</div><div class="lbl">右侧确认 MACD/MA2</div></div>
</div></div>
<div class="card"><div class="card-title">触发水位线</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">{waterline_html if waterline_html else '<span style="color:#9ca3af">无法计算</span>'}</div>
</div>
<div class="card"><div class="card-title">因子状态</div>{rules_html}</div>
<div class="card"><div class="card-title">走势图 (黄箭头=Armed | 虚线=水位线)</div><div id="chart"></div></div>
<div class="card"><div class="card-title">近期 Armed 信号 (* = 入场)</div>
  <table class="rec-table"><tr><th>日期</th><th>Score</th><th>价格</th><th>RSI</th><th>回撤</th><th>入场</th></tr>{armed_html}</table>
</div>
<div class="footer">AKShare | {ACTIVE_MODEL_VERSION} | 仅供参考</div>
</div>
<script>
try {{
    var d = {chart_data};
    var el = document.getElementById('chart');
    var chart = LightweightCharts.createChart(el, {{
        layout: {{ background: {{ color: '#ffffff' }}, textColor: '#1f2937' }},
        grid: {{ vertLines: {{ color: '#f3f4f6' }}, horzLines: {{ color: '#f3f4f6' }} }},
        rightPriceScale: {{ borderColor: '#d1d5db' }},
        timeScale: {{ borderColor: '#d1d5db', timeVisible: true }},
        width: Math.min(el.clientWidth || 900, window.innerWidth - 60 || 900), height: 350,
    }});
    var line = chart.addLineSeries({{ color: '#3B82F6', lineWidth: 2 }});
    var uniqueData = [], seen = new Set();
    d.forEach(function(w) {{
        if (!seen.has(w.time) && w.value != null && !isNaN(w.value)) {{ seen.add(w.time); uniqueData.push(w); }}
    }});
    uniqueData.sort(function(a,b) {{ return a.time.localeCompare(b.time); }});
    var prices = uniqueData.map(function(w) {{ return {{ time: w.time, value: w.value }}; }});
    var markers = uniqueData.filter(function(w) {{ return w.armed; }}).map(function(w) {{
        return {{ time: w.time, position: 'belowBar', color: '#F59E0B', shape: 'arrowUp', text: String(w.score) }};
    }});
    line.setData(prices); line.setMarkers(markers);
    var waterlines = {waterline_json};
    var colors = {{ 'S3': '#EF4444', 'V1': '#10B981' }};
    var labels = {{ 'S3': '新低触发', 'V1': '估值触发' }};
    Object.keys(waterlines).forEach(function(key) {{
        var price = waterlines[key];
        var wl = chart.addLineSeries({{ color: colors[key], lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }});
        var data = [];
        for (var i = 0; i < prices.length; i++) {{ data.push({{ time: prices[i].time, value: price }}); }}
        wl.setData(data);
        wl.setMarkers([{{ time: prices[prices.length-1].time, position: 'inLine', color: colors[key], shape: 'circle', text: labels[key] + ' ' + price.toFixed(0) }}]);
    }});
    chart.timeScale().fitContent();
    window.addEventListener('resize', function() {{ chart.applyOptions({{ width: Math.min(el.clientWidth || 900, window.innerWidth - 60 || 900) }}); }});
}} catch(e) {{
    document.getElementById('chart').innerHTML =
        '<div style="padding:40px;text-align:center;color:#ef4444"><b>图表加载失败</b><br><small>'+e.message+'</small></div>';
}}
async function trialCalc() {{
  var price = document.getElementById('trial-price').value;
  var res = document.getElementById('trial-result');
  if (!price) {{ res.textContent = '请输入点位'; return; }}
  res.textContent = '计算中...';
  try {{
    var r = await fetch('/api/signal?price=' + price);
    var d = await r.json();
    res.innerHTML = 'Score <b>' + d.score + '</b> [' + (d.signal_tier||'') + '] | ' + (d.alert && d.alert.level || '');
    res.style.color = d.score >= 2 ? '#ef4444' : '#10b981';
  }} catch(e) {{ res.textContent = '计算失败'; }}
}}
</script>
</body></html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Dashboard saved ({time.time()-t0:.1f}s)")
    return output_path


if __name__ == "__main__":
    build_dashboard()
