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
<script src="/lw.js"></script>
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
#chart{width:100%;max-width:100%;height:320px;overflow:hidden}

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

/* Tabs */
.tabs{display:flex;gap:2px;margin-bottom:20px;background:var(--surface);
  border-radius:10px;padding:4px;border:1px solid var(--border)}
.tab-btn{flex:1;padding:10px 0;border:none;border-radius:8px;background:transparent;
  color:var(--muted);font-family:'DM Sans',sans-serif;font-size:13px;font-weight:500;
  cursor:pointer;transition:.2s}
.tab-btn:hover{color:var(--text)}
.tab-btn.active{background:var(--surface2);color:var(--accent)}
.tab-content{display:none}
.tab-content.active{display:block}

/* Error banner */
.error-banner{display:none;margin-bottom:16px;padding:12px 16px;
  border-radius:8px;background:#450a0a;border:1px solid #991b1b;color:var(--red);font-size:13px;line-height:1.6}
.error-banner .err-item{margin-bottom:4px}
.error-banner .err-time{font-family:'DM Mono',monospace;font-size:11px;color:#fca5a5;margin-right:8px}
.error-banner.warning{background:#451a03;border-color:#92400e;color:var(--yellow)}
.error-banner.warning .err-time{color:#fde68a}
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
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('realtime')">实时监控</button>
    <button class="tab-btn" onclick="switchTab('history')">历史信号</button>
  </div>

  <div id="tab-realtime" class="tab-content active">
  <div class="error-banner" id="error-banner"></div>
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
        <div style="display:flex;align-items:center;gap:8px">
          <div style="flex:1;height:6px;border-radius:3px;background:var(--border);overflow:hidden">
            <div id="score-fill" style="height:100%;border-radius:3px;background:var(--accent);transition:.3s;width:0%"></div>
          </div>
          <span class="score-label" id="score-lbl">0.0</span>
        </div>
        <div id="tier-lbl" style="font-size:11px;color:var(--muted);margin-top:4px;font-family:'DM Mono',monospace"></div>
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
    <div class="card-title">因子状态</div>
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
        <th>日期</th><th>Score</th><th>价格</th><th>RSI</th><th>回撤</th><th>Tier</th>
      </tr></thead>
      <tbody id="sig-tbody"></tbody>
    </table>
  </div>

  </div><!-- /tab-realtime -->

  <div id="tab-history" class="tab-content">
    <div class="card">
      <div class="card-title">历史信号记录（来源: SQLite）</div>
      <div id="history-loading" style="text-align:center;color:var(--muted);padding:20px">加载中...</div>
      <table class="sig-table" id="history-table" style="display:none">
        <thead><tr>
          <th>日期</th><th>Score</th><th>价格</th><th>警报</th>
          <th>L1</th><th>M1</th><th>S3</th><th>V1</th>
          <th>Tier</th>
          <th>S3触发价</th><th>V1触发价</th>
        </tr></thead>
        <tbody id="history-tbody"></tbody>
      </table>
      <div id="history-empty" style="display:none;text-align:center;color:var(--muted);padding:20px">
        暂无历史记录，运行 tracker.py 后自动积累
      </div>
    </div>
    <div class="card">
      <div class="card-title">Score 历史趋势</div>
      <div id="score-history-chart" style="width:100%;height:240px"></div>
    </div>
  </div><!-- /tab-history -->

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
    window.__scoreThreshold = d.score_threshold;
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

  // Score bar (dynamic progress bar)
  const score = d.score;
  const maxScore = d.max_score || 10.0;
  const pctFill = Math.min(score / maxScore * 100, 100);
  const fillColor = score >= maxScore * 0.4 ? (score >= maxScore * 0.7 ? 'var(--red)' : 'var(--yellow)') : 'var(--accent)';
  document.getElementById('score-fill').style.width = pctFill + '%';
  document.getElementById('score-fill').style.background = fillColor;
  document.getElementById('score-lbl').textContent = score.toFixed(1);

  // Tier display
  const tierMap = {
    'hold': 'HOLD', 'weak_armed': 'WEAK ARMED',
    'standard_armed': 'STANDARD ARMED', 'strong_armed': 'STRONG ARMED',
    'armed': 'ARMED'
  };
  const tierColor = {
    'hold': 'var(--muted)', 'weak_armed': 'var(--yellow)',
    'standard_armed': 'var(--red)', 'strong_armed': 'var(--red)',
    'armed': 'var(--red)'
  };
  const tierLbl = document.getElementById('tier-lbl');
  const tierKey = d.signal_tier || 'hold';
  tierLbl.textContent = (tierMap[tierKey] || tierKey) + (d.n_factors ? ' (' + d.n_factors + ' factors)' : '');
  tierLbl.style.color = tierColor[tierKey] || 'var(--muted)';

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

  // Chart (try-catch, 错误可见)
  try {
  if (chart) { chart.remove(); chart = null; }
  const el = document.getElementById('chart');
  chart = LightweightCharts.createChart(el, {
    layout: {background:{color:'transparent'}, textColor:'#94a3b8'},
    grid: {vertLines:{color:'#1e293b'}, horzLines:{color:'#1e293b'}},
    rightPriceScale: {borderColor:'#2a2d3e'},
    timeScale: {borderColor:'#2a2d3e', timeVisible:true},
    width: el.clientWidth || window.innerWidth - 80 || 900, height: 320,
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
    chart.applyOptions({width: el.clientWidth || window.innerWidth - 80 || 900});
  });
  } catch(e) {
    document.getElementById('chart').innerHTML =
      '<div style="padding:40px;text-align:center;color:#ef4444"><b>图表加载失败</b><br><small>'+e.message+'</small></div>';
  }

  // Armed signal table
  document.getElementById('sig-tbody').innerHTML = d.armed_history.slice(-20).reverse().map(s =>
    `<tr class="${s.first?'first':''}">
       <td>${s.date}</td><td>${s.score.toFixed(1)}</td><td>${s.price}</td>
       <td>${s.rsi}</td><td>${s.dd}%</td>
       <td style="font-size:10px">${s.tier || ''}</td>
     </tr>`
  ).join('');

  // Footer note
  document.getElementById('footer-note').textContent =
    `行情来源: AKShare | 计算耗时: ${d.elapsed_s}s`;
}

function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  const labels = {realtime: '实时监控', history: '历史信号'};
  document.querySelectorAll('.tab-btn').forEach(btn => {
    if (btn.textContent.trim() === labels[name]) btn.classList.add('active');
  });
  if (name === 'history') loadHistory();
}

let _historyLoaded = false;
async function loadHistory() {
  if (_historyLoaded) return;
  _historyLoaded = true;
  try {
    const r = await fetch('/api/history');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const rows = await r.json();
    const tbody = document.getElementById('history-tbody');
    if (rows.length === 0) {
      document.getElementById('history-loading').style.display = 'none';
      document.getElementById('history-empty').style.display = 'block';
      return;
    }
    document.getElementById('history-loading').style.display = 'none';
    document.getElementById('history-table').style.display = 'table';
    tbody.innerHTML = rows.map(r => {
      const ac = {silent:'var(--muted)', yellow:'var(--yellow)', red:'var(--red)'}[r.alert_level] || 'var(--muted)';
      const al = {silent:'静默', yellow:'YELLOW', red:'RED'}[r.alert_level] || r.alert_level;
      const dot = c => c ? '<span style="color:var(--green)">✓</span>' : '<span style="color:var(--border)">—</span>';
      const tierDisp = r.signal_tier || '';
      return '<tr>' +
        '<td>' + r.date + '</td>' +
        '<td>' + (r.score ? r.score.toFixed(1) : '-') + '</td>' +
        '<td>' + (r.price ? r.price.toFixed(0) : '-') + '</td>' +
        '<td style="color:' + ac + '">' + al + '</td>' +
        '<td>' + dot(r.l1_triggered) + '</td>' +
        '<td>' + dot(r.m1_triggered) + '</td>' +
        '<td>' + dot(r.s3_triggered) + '</td>' +
        '<td>' + dot(r.v1_triggered) + '</td>' +
        '<td style="font-size:10px">' + tierDisp + '</td>' +
        '<td>' + (r.s3_trigger_price ? r.s3_trigger_price.toFixed(0) : '-') + '</td>' +
        '<td>' + (r.v1_trigger_price ? r.v1_trigger_price.toFixed(0) : '-') + '</td>' +
      '</tr>';
    }).join('');
    renderScoreChart(rows);
  } catch(e) {
    document.getElementById('history-loading').textContent = '加载失败: ' + e.message;
  }
}

function renderScoreChart(rows) {
  try {
    const el = document.getElementById('score-history-chart');
    const c = LightweightCharts.createChart(el, {
      layout: {background:{color:'transparent'}, textColor:'#94a3b8'},
      grid: {vertLines:{color:'#1e293b'}, horzLines:{color:'#1e293b'}},
      rightPriceScale: {borderColor:'#2a2d3e'},
      timeScale: {borderColor:'#2a2d3e'},
      width: el.clientWidth || 900, height: 240,
    });
    const series = c.addLineSeries({color:'#38bdf8', lineWidth:2});
    const data = rows.slice().reverse().map(r => ({time: r.date, value: r.score}));
    series.setData(data);
    // Armed threshold line (only show for V5.1 score_threshold mode)
    if (window.__scoreThreshold != null) {
    const th = c.addLineSeries({
      color:'#fbbf24', lineWidth:1, lineStyle:2,
      priceLineVisible:false, lastValueVisible:false,
    });
    th.setData(data.map(d => ({time: d.time, value: window.__scoreThreshold})));
    }
    c.timeScale().fitContent();
    window.addEventListener('resize', () => {
      c.applyOptions({width: el.clientWidth || 900});
    });
  } catch(e) {
    document.getElementById('score-history-chart').innerHTML =
      '<div style="padding:20px;text-align:center;color:#ef4444">图表加载失败: '+e.message+'</div>';
  }
}

async function loadErrors() {
  try {
    const r = await fetch('/api/errors');
    if (!r.ok) return;
    const errors = await r.json();
    const banner = document.getElementById('error-banner');
    if (errors.length === 0) { banner.style.display = 'none'; return; }
    const hasError = errors.some(e => e.level === 'error');
    banner.className = 'error-banner' + (hasError ? '' : ' warning');
    banner.style.display = 'block';
    banner.innerHTML = errors.slice(0, 5).map(e =>
      '<div class="err-item"><span class="err-time">' + e.timestamp +
      '</span>[' + e.source + '] ' + e.message + '</div>'
    ).join('');
  } catch(e) {}
}

loadErrors();
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
    from app.db import log_error

    # 极速模式: 拉取医药指数+融资数据 (S3因子需要资金面)
    try:
        ak_src = AKShareSource()
        med_df = ak_src.fetch_sw_medical("20180101")
        margin_df = ak_src.fetch_margin_data("20180101")
        fast_data = {"sw_medical": med_df, "total_margin": margin_df}
    except Exception as e:
        log_error("data_fetch", f"Web端数据拉取失败: {e}", "error")
        raise

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
                "score": round(float(r["score"]), 1),
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
                "score": round(float(r["score"]), 1),
                "price": round(float(r["price"])),
                "rsi": round(float(r["rsi"]), 1),
                "dd": round(float(r["drawdown_13w"]), 1),
                "first": bool(collapsed.iloc[i]),
                "tier": r.get("signal_tier", ""),
            })

    elapsed = round(time.time() - t0, 1)

    # score_threshold: V5.1 才有（用于图表阈值线），V5.2 返回 null
    from src.models.rule_registry import MODEL_CONFIGS
    cfg = MODEL_CONFIGS.get(sig.get("model_version", "V5.1"), {})
    score_threshold = cfg.get("score_threshold")  # V5.1=3.5, V5.2=None

    return {
        "date": str(sig["date"]),
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": elapsed,
        "price": float(sig["price"]),
        "score": float(sig["score"]),
        "max_score": float(sig.get("max_score", 10.0)),
        "signal_tier": sig.get("signal_tier", "hold"),
        "n_factors": int(sig.get("n_factors", 0)),
        "model_version": sig.get("model_version", "V5.1"),
        "score_threshold": score_threshold,
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
        elif self.path.startswith("/api/history"):
            self._serve_history()
        elif self.path.startswith("/api/errors"):
            self._serve_errors()
        elif self.path == "/lw.js":
            self._serve_lw()
        elif self.path.startswith("/static/"):
            self._serve_static()
        else:
            self._serve_dash()

    def _serve_dash(self):
        import subprocess, sys
        # 每次请求重新生成看板，保证数据最新
        subprocess.run([sys.executable, "app/dashboard.py"], capture_output=True)
        body = Path("dashboard.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_history(self):
        """从 SQLite 读取历史信号记录"""
        try:
            from app.db import get_history
            rows = get_history()
            body = json.dumps(rows, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = json.dumps({"error": str(e)}, ensure_ascii=False).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def _serve_errors(self):
        """返回最近 24 小时内的系统错误/警告日志"""
        try:
            from app.db import get_recent_errors
            errors = get_recent_errors(hours=24)
            body = json.dumps(errors, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = json.dumps({"error": str(e)}, ensure_ascii=False).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def _serve_lw(self):
        js_path = Path("data/lightweight-charts.min.js")
        if not js_path.exists():
            self.send_response(404); self.end_headers(); return
        body = js_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript")
        self.send_header("Cache-Control", "max-age=86400")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self):
        fname = self.path.split("/")[-1]
        fpath = Path(__file__).resolve().parent / "static" / fname
        if fpath.exists():
            body = fpath.read_bytes()
            ct = "application/javascript" if fname.endswith(".js") else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

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
            print(f"  [{datetime.now():%H:%M:%S}] 完成 ({payload['elapsed_s']}s) — Score={payload['score']:.1f} [{payload['signal_tier']}] ({payload['model_version']}) [{payload['alert']['level'].upper()}]")
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
