"""
实时看板服务器 — 每次打开/刷新页面自动拉取最新数据

用法:
    python app/server.py              # 启动服务器，自动打开浏览器
    python app/server.py --port 9000  # 指定端口
    python app/server.py --no-browser # 不自动打开浏览器

架构:
    GET /            → 返回 HTML 看板（JS 动态渲染）
    GET /api/signal  → 实时计算信号，返回 JSON
"""
import sys
import json
import argparse
import threading
import webbrowser
import traceback
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_PORT = 8888

# ═══════════════════════════════════════════════════════════════
# HTML 模板 — JS 动态从 /api/signal 拉取数据后渲染
# ═══════════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>医药板块监控器</title>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script>window.lightweightCharts||document.write('<script src=\"https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js\"><\/script>')</script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#222636;--border:#2a2d3e;
  --text:#e2e8f0;--muted:#64748b;--accent:#38bdf8;
  --green:#34d399;--yellow:#fbbf24;--red:#f87171;--silent:#64748b;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

/* Loading */
#loading{display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;gap:16px;color:var(--muted)}
.spinner{width:36px;height:36px;border:3px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
#error{display:none;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;gap:12px;color:var(--red)}

/* Layout */
#app{display:none;max-width:960px;margin:0 auto;padding:24px 16px}
.header{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:28px;padding-bottom:16px;border-bottom:1px solid var(--border)}
.header-title{font-size:15px;font-weight:700;letter-spacing:.5px;color:var(--muted);
  text-transform:uppercase}
.header-meta{font-size:12px;color:var(--muted);text-align:right;line-height:1.6}
.header-meta b{color:var(--accent)}

/* Cards */
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:20px;margin-bottom:16px}
.card-title{font-size:11px;font-weight:700;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted);margin-bottom:16px}

/* Status badge */
.status-row{display:flex;align-items:center;gap:16px;margin-bottom:20px}
.badge{display:inline-flex;align-items:center;gap:8px;padding:8px 18px;
  border-radius:8px;font-family:'DM Mono',monospace;font-weight:500;font-size:14px}
.badge.silent{background:#1e293b;color:var(--silent);border:1px solid var(--border)}
.badge.yellow{background:#451a03;color:var(--yellow);border:1px solid #92400e}
.badge.red{background:#450a0a;color:var(--red);border:1px solid #991b1b}
.badge .dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.badge.red .dot{animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* Score bar */
.score-bar{display:flex;gap:6px;align-items:center}
.score-seg{height:6px;border-radius:3px;flex:1;background:var(--border);transition:.3s}
.score-seg.active{background:var(--accent)}
.score-seg.active.warn{background:var(--yellow)}
.score-seg.active.alert{background:var(--red)}
.score-label{font-family:'DM Mono',monospace;font-size:12px;color:var(--muted);
  min-width:32px;text-align:right}

/* Metrics grid */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:0}
.metric{background:var(--surface2);border-radius:8px;padding:12px 10px;text-align:center}
.metric .val{font-family:'DM Mono',monospace;font-size:18px;font-weight:500}
.metric .lbl{font-size:10px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.metric.triggered .val{color:var(--red)}

/* Rules */
.rule{display:flex;align-items:center;gap:12px;padding:10px 0;
  border-bottom:1px solid var(--border)}
.rule:last-child{border-bottom:none}
.rule-icon{width:26px;height:26px;border-radius:6px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:12px}
.rule-icon.on{background:#052e16;color:var(--green)}
.rule-icon.off{background:var(--surface2);color:var(--muted)}
.rule-name{font-weight:500;font-size:13px;min-width:100px}
.rule-val{font-family:'DM Mono',monospace;font-size:12px;color:var(--muted);flex:1}
.rule-thresh{font-size:11px;color:var(--border);margin-left:auto}

/* Distance */
.dist-row{display:flex;justify-content:space-between;align-items:center;
  padding:10px 0;border-bottom:1px solid var(--border)}
.dist-row:last-child{border-bottom:none}
.dist-name{font-size:13px;font-weight:500}
.dist-price{font-family:'DM Mono',monospace;font-size:13px}
.dist-pct{font-family:'DM Mono',monospace;font-size:12px;padding:2px 8px;
  border-radius:4px;background:var(--surface2)}
.dist-pct.triggered{color:var(--green)}
.dist-pct.far{color:var(--muted)}
.dist-pct.close{color:var(--yellow)}

/* Chart */
#chart{width:100%;height:320px}

/* Table */
.sig-table{width:100%;border-collapse:collapse;font-size:12px}
.sig-table th{text-align:center;padding:6px 8px;color:var(--muted);
  font-weight:500;border-bottom:1px solid var(--border);font-family:'DM Mono',monospace}
.sig-table td{text-align:center;padding:6px 8px;border-bottom:1px solid var(--border);
  font-family:'DM Mono',monospace;color:var(--muted)}
.sig-table tr.first td{color:var(--text)}
.sig-table tr.first td:first-child::before{content:'▶ ';color:var(--accent)}

/* Alert message */
.alert-msg{font-size:13px;color:var(--muted);padding:10px 14px;
  background:var(--surface2);border-radius:6px;border-left:3px solid var(--border);line-height:1.5}
.alert-msg.yellow{border-color:var(--yellow);color:var(--yellow)}
.alert-msg.red{border-color:var(--red);color:var(--red)}

/* Footer */
.footer{text-align:center;color:var(--muted);font-size:11px;
  margin-top:24px;padding-top:16px;border-top:1px solid var(--border);line-height:2}
</style>
</head>
<body>

<div id="loading">
  <div class="spinner"></div>
  <span>正在拉取最新行情数据…</span>
</div>
<div id="error">
  <span style="font-size:32px">⚠️</span>
  <b id="err-msg">数据加载失败</b>
  <small id="err-detail" style="color:var(--muted)"></small>
  <button onclick="load()" style="margin-top:12px;padding:8px 20px;background:var(--accent);
    color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600">重试</button>
</div>

<div id="app">
  <div class="header">
    <div>
      <div class="header-title">申万医药生物(801150) · 风险收益比监控器</div>
    </div>
    <div class="header-meta">
      数据截止 <b id="h-date">—</b><br>
      更新时间 <b id="h-updated">—</b>
      <div style="margin-top:10px; display:flex; align-items:center; gap:8px; justify-content:flex-end">
        <input type="number" id="custom-price" placeholder="试算点位(如 7430)"
               style="padding:6px; border-radius:6px; border:1px solid #374151; background:#1f2937; color:#e2e8f0; width:160px; font-size:12px;">
        <button onclick="load()" style="padding:6px 12px; background:#38bdf8; color:#000; border:none; border-radius:6px; cursor:pointer; font-size:12px; font-weight:bold;">刷新试算</button>
      </div>
    </div>
  </div>

  <!-- 状态 + Score -->
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px">
      <div>
        <div class="card-title">当前状态</div>
        <div class="status-row">
          <span class="badge" id="badge"><span class="dot"></span><span id="badge-text">—</span></span>
        </div>
        <div class="alert-msg" id="alert-msg"></div>
      </div>
      <div style="min-width:180px">
        <div class="card-title">Score</div>
        <div class="score-bar" id="score-bar">
          <div class="score-seg" id="s0"></div>
          <div class="score-seg" id="s1"></div>
          <div class="score-seg" id="s2"></div>
          <div class="score-seg" id="s3"></div>
          <div class="score-seg" id="s4"></div>
          <span class="score-label" id="score-lbl">0/5</span>
        </div>
      </div>
    </div>
  </div>

  <!-- 关键指标 -->
  <div class="card">
    <div class="card-title">关键指标</div>
    <div class="metrics" id="metrics"></div>
  </div>

  <!-- 五规则 -->
  <div class="card">
    <div class="card-title">五规则状态</div>
    <div id="rules"></div>
  </div>

  <!-- 距离触发 -->
  <div class="card">
    <div class="card-title">距离触发水位线</div>
    <div id="dist"></div>
  </div>

  <!-- 走势图 -->
  <div class="card">
    <div class="card-title">近两年周线 · 黄箭头=Armed · 虚线=触发水位线</div>
    <div id="chart"></div>
  </div>

  <!-- 历史信号 -->
  <div class="card">
    <div class="card-title">近期 Armed 信号 (▶ = 入场信号)</div>
    <table class="sig-table">
      <thead><tr>
        <th>日期</th><th>Score</th><th>价格</th><th>RSI</th><th>回撤</th>
      </tr></thead>
      <tbody id="sig-tbody"></tbody>
    </table>
  </div>

  <div class="footer">
    仅供研究参考，不构成投资建议 &nbsp;|&nbsp;
    方法论: Triple Barrier + 五规则探测器 &nbsp;|&nbsp; V4.3<br>
    <span id="footer-note"></span>
  </div>
</div>

<script>
let chart = null;

async function load() {
  document.getElementById('loading').style.display = 'flex';
  document.getElementById('error').style.display = 'none';
  document.getElementById('app').style.display = 'none';

  try {
    const cpEl = document.getElementById('custom-price');
    const cp = cpEl ? cpEl.value : '';
    const url = cp ? '/api/signal?price=' + cp : '/api/signal';
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
    const d = await r.json();
    render(d);
    document.getElementById('loading').style.display = 'none';
    document.getElementById('app').style.display = 'block';
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error').style.display = 'flex';
    document.getElementById('err-msg').textContent = '数据加载失败';
    document.getElementById('err-detail').textContent = e.message;
  }
}

function render(d) {
  // Header
  document.getElementById('h-date').textContent = d.date;
  document.getElementById('h-updated').textContent = d.computed_at;

  // Badge
  const level = d.alert.level;
  const badge = document.getElementById('badge');
  badge.className = 'badge ' + level;
  const labels = {silent:'HOLD', yellow:'YELLOW ⚠', red:'ARMED 🔴'};
  document.getElementById('badge-text').textContent = labels[level] || level.toUpperCase();

  // Alert message
  const msg = document.getElementById('alert-msg');
  msg.textContent = d.alert.message;
  msg.className = 'alert-msg ' + (level === 'silent' ? '' : level);

  // Score bar
  const score = d.score;
  const colorClass = score >= 4 ? 'alert' : score >= 2 ? 'warn' : '';
  for(let i = 0; i < 5; i++) {
    const seg = document.getElementById('s' + i);
    seg.className = 'score-seg' + (i < score ? ' active ' + colorClass : '');
  }
  document.getElementById('score-lbl').textContent = score + '/5';

  // Metrics
  const metrics = [
    {label: 'RSI(Wilder)', val: d.rsi.toFixed(1), trigger: d.rsi < 30},
    {label: '13周回撤', val: d.drawdown_13w.toFixed(1) + '%', trigger: d.drawdown_13w < -10},
    {label: '5年价格分位', val: d.val_pct_5y.toFixed(0) + '%', trigger: d.val_pct_5y < 15},
    {label: '收盘价', val: d.price.toFixed(0), trigger: false},
  ];
  document.getElementById('metrics').innerHTML = metrics.map(m =>
    `<div class="metric${m.trigger?' triggered':''}">
       <div class="val">${m.val}</div>
       <div class="lbl">${m.label}</div>
     </div>`
  ).join('');

  // Rules
  document.getElementById('rules').innerHTML = d.rules_status.map(r =>
    `<div class="rule">
       <div class="rule-icon ${r.triggered?'on':'off'}">${r.triggered?'✓':'—'}</div>
       <div class="rule-name">${r.name}</div>
       <div class="rule-val">${r.value}</div>
       <div class="rule-thresh">阈值: ${r.threshold}</div>
     </div>`
  ).join('');

  // Distance to trigger
  document.getElementById('dist').innerHTML = Object.values(d.distance_to_trigger).map(dt => {
    if (dt.triggered) {
      return `<div class="dist-row">
        <div class="dist-name">${dt.name}</div>
        <div class="dist-pct triggered">已触发 ✓</div>
      </div>`;
    }
    const pct = dt.pct_away;
    const cls = Math.abs(pct) < 2.5 ? 'close' : 'far';
    return `<div class="dist-row">
      <div class="dist-name">${dt.name}</div>
      <div class="dist-price">触发价 ${dt.trigger_price ? dt.trigger_price.toFixed(0) : '—'}</div>
      <div class="dist-pct ${cls}">${pct ? (pct > 0 ? '+' : '') + pct.toFixed(1) + '%' : '—'}</div>
    </div>`;
  }).join('');

  // Chart
  if (chart) { chart.remove(); chart = null; }
  const el = document.getElementById('chart');
  chart = LightweightCharts.createChart(el, {
    layout: {background:{color:'transparent'}, textColor:'#94a3b8'},
    grid: {vertLines:{color:'#1e293b'}, horzLines:{color:'#1e293b'}},
    rightPriceScale: {borderColor:'#2a2d3e'},
    timeScale: {borderColor:'#2a2d3e', timeVisible:true},
    width: el.clientWidth, height: 320,
  });

  const line = chart.addLineSeries({color:'#38bdf8', lineWidth:2});

  // 去重 + 排序 (防止重复时间轴导致图表崩溃)
  const uniqueData = [];
  const seen = new Set();
  d.chart.forEach(w => {
    if (!seen.has(w.time) && w.value != null && !isNaN(w.value)) {
      seen.add(w.time);
      uniqueData.push(w);
    }
  });
  uniqueData.sort((a,b) => a.time.localeCompare(b.time));

  const prices = uniqueData.map(w => ({time:w.time, value:w.value}));
  line.setData(prices);
  line.setMarkers(
    uniqueData.filter(w => w.armed).map(w => ({
      time:w.time, position:'belowBar', color:'#fbbf24',
      shape:'arrowUp', text: String(w.score)
    }))
  );

  // Waterlines
  const wl_colors = {D:'#f87171', C:'#34d399'};
  const wl_labels = {D:'回撤触发', C:'估值触发'};
  Object.entries(d.distance_to_trigger).forEach(([key, dt]) => {
    if (!dt.trigger_price || dt.triggered) return;
    const wl = chart.addLineSeries({
      color:wl_colors[key], lineWidth:1, lineStyle:2,
      priceLineVisible:false, lastValueVisible:false,
    });
    wl.setData(prices.map(p => ({time:p.time, value:dt.trigger_price})));
    wl.setMarkers([{
      time: prices[prices.length-1].time, position:'inLine',
      color:wl_colors[key], shape:'circle',
      text: wl_labels[key] + ' ' + dt.trigger_price.toFixed(0),
    }]);
  });
  chart.timeScale().fitContent();
  window.addEventListener('resize', () => {
    chart.applyOptions({width: el.clientWidth});
  });

  // Armed signal table
  document.getElementById('sig-tbody').innerHTML = d.armed_history.slice(-20).reverse().map(s =>
    `<tr class="${s.first?'first':''}">
       <td>${s.date}</td><td>${s.score}/5</td><td>${s.price}</td>
       <td>${s.rsi}</td><td>${s.dd}%</td>
     </tr>`
  ).join('');

  // Footer note
  document.getElementById('footer-note').textContent =
    `行情来源: AKShare | 计算耗时: ${d.elapsed_s}s`;
}

load();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# API: 实时计算信号并序列化为 JSON
# ═══════════════════════════════════════════════════════════════

def _compute_and_serialize(custom_price: float = None) -> dict:
    import time
    import numpy as np
    t0 = time.time()

    from app.tracker import _compute
    from src.data_fetcher.akshare_source import AKShareSource

    # 极速模式: 只拉取医药指数, 跳过宏观数据 (14s → <1s)
    med_df = AKShareSource().fetch_sw_medical("20180101")
    fast_data = {"sw_medical": med_df}

    sig = _compute(fast_data, custom_price=custom_price)

    df = sig.get("df")
    dist = sig.get("distance_to_trigger", {})

    # ── 水位线触发价（确保可序列化）──
    dist_out = {}
    for k, v in dist.items():
        dist_out[k] = {
            "name": v["name"],
            "triggered": bool(v["triggered"]),
            "trigger_price": float(v["trigger_price"]) if v.get("trigger_price") is not None and not (isinstance(v["trigger_price"], float) and np.isnan(v["trigger_price"])) else None,
            "pct_away": float(v["pct_away"]) if v.get("pct_away") is not None else 0.0,
        }

    # ── 近两年周线数据 ──
    chart_data = []
    if df is not None:
        for i in range(max(0, len(df) - 104), len(df)):
            r = df.iloc[i]
            chart_data.append({
                "time": r.name.strftime("%Y-%m-%d"),
                "value": round(float(r["price"]), 2),
                "armed": bool(r["armed"]),
                "score": int(r["score"]),
            })

    # ── 近期 Armed 信号 ──
    armed_history = []
    if df is not None:
        from src.models.turning_points import collapse_signals
        collapsed = collapse_signals(df["armed"])
        for i in range(max(0, len(df) - 156), len(df)):
            r = df.iloc[i]
            if not bool(r["armed"]):
                continue
            armed_history.append({
                "date": r.name.strftime("%Y-%m-%d"),
                "score": int(r["score"]),
                "price": round(float(r["price"])),
                "rsi": round(float(r["rsi"]), 1),
                "dd": round(float(r["drawdown_13w"]), 1),
                "first": bool(collapsed.iloc[i]),
            })

    elapsed = round(time.time() - t0, 1)

    return {
        "date": str(sig["date"]),
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": elapsed,
        "price": float(sig["price"]),
        "score": int(sig["score"]),
        "armed": bool(sig["armed"]),
        "rsi": float(sig["rsi"]),
        "drawdown_13w": float(sig["drawdown_13w"]),
        "val_pct_5y": float(sig["val_pct_5y"]),
        "rules_status": sig["rules_status"],
        "alert": sig["alert"],
        "distance_to_trigger": dist_out,
        "chart": chart_data,
        "armed_history": armed_history,
    }


# ═══════════════════════════════════════════════════════════════
# HTTP 服务器
# ═══════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith("/api/signal"):
            self._serve_api()
        else:
            self._serve_html()

    def _serve_html(self):
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_api(self):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        custom_price = float(qs["price"][0]) if "price" in qs else None
        print(f"  [{datetime.now():%H:%M:%S}] 拉取数据中...")
        try:
            payload = _compute_and_serialize(custom_price=custom_price)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            print(f"  [{datetime.now():%H:%M:%S}] 完成 ({payload['elapsed_s']}s) — Score={payload['score']}/5 [{payload['alert']['level'].upper()}]")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"  [ERROR] {e}\n{tb}")
            body = json.dumps({"error": str(e), "detail": tb}, ensure_ascii=False).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # 屏蔽默认 access log，用自定义日志


def main():
    parser = argparse.ArgumentParser(description="医药板块实时监控看板")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"

    print("=" * 50)
    print("  医药板块实时监控看板")
    print(f"  地址: {url}")
    print("  每次刷新页面 (F5) 自动拉取最新行情")
    print("  Ctrl+C 停止服务器")
    print("=" * 50)

    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    main()
