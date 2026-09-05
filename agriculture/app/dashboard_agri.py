# -*- coding: utf-8 -*-
"""生成自包含 HTML 看板 dashboard_agri.html（仓库根目录，离线可用）。

数据源：agriculture/data/processed/latest_state.json（tracker 生成）+
        agriculture/data/processed/signals.db（历史信号）+
        src/models/model_config_agri.json（冻结表/回测指标）。
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

AGRI = Path(__file__).resolve().parents[1]
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB_PATH = AGRI / "data" / "processed" / "signals.db"
STATE_PATH = AGRI / "data" / "processed" / "latest_state.json"
CONFIG_PATH = AGRI / "src" / "models" / "model_config_agri.json"
OUT_PATH = AGRI.parent / "dashboard_agri.html"

ALERT_COLOR = {"RED": "#c0392b", "YELLOW": "#d4a017", "SILENT": "#27ae60"}
ALERT_TEXT = {"RED": "行动日", "YELLOW": "关注", "SILENT": "常态"}


def esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_chart(history: list) -> str:
    """近 600 日收盘价 + 持仓区底的 SVG 折线图。"""
    if not history:
        return "<p>暂无历史数据</p>"
    closes = [h[1] for h in history]
    lo, hi = min(closes) * 0.98, max(closes) * 1.02
    w, hgt = 860, 220
    n = len(history)
    xs = [12 + i * (w - 24) / max(n - 1, 1) for i in range(n)]
    ys = [hgt - 18 - (c - lo) / max(hi - lo, 1e-9) * (hgt - 36) for c in closes]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    # 持仓区段（浅色底）
    bands, start = [], None
    for i, (_, _, p) in enumerate(history):
        if p == 1 and start is None:
            start = xs[i]
        elif p == 0 and start is not None:
            bands.append((start, xs[i]))
            start = None
    if start is not None:
        bands.append((start, xs[-1]))
    band_svg = "".join(
        f'<rect x="{a:.1f}" y="4" width="{max(b - a, 1):.1f}" height="{hgt - 22}" '
        f'fill="#27ae6018"/>' for a, b in bands)
    labels = f'{history[0][0]} → {history[-1][0]}'
    return (f'<svg viewBox="0 0 {w} {hgt}" style="width:100%;background:#fafafa;'
            f'border:1px solid #eee;border-radius:8px">'
            f'{band_svg}'
            f'<polyline points="{pts}" fill="none" stroke="#2c3e50" stroke-width="1.6"/>'
            f'<text x="14" y="16" font-size="11" fill="#888">{labels}（绿色底=持仓区间）</text></svg>')


def build_nav_chart(nav_history: list) -> str:
    """策略 vs 指数累计净值（近 600 个交易日，归一=1）。"""
    if not nav_history:
        return "<p>暂无净值数据</p>"
    strat = [h[1] for h in nav_history]
    idx = [h[2] for h in nav_history]
    lo = min(min(strat), min(idx)) * 0.97
    hi = max(max(strat), max(idx)) * 1.03
    w, hgt = 860, 220
    n = len(nav_history)
    xs = [12 + i * (w - 24) / max(n - 1, 1) for i in range(n)]

    def line(vals: list, color: str) -> str:
        ys = [hgt - 18 - (v - lo) / max(hi - lo, 1e-9) * (hgt - 36) for v in vals]
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.8"/>'

    end_s, end_i = strat[-1], idx[-1]
    labels = (f'{nav_history[0][0]} → {nav_history[-1][0]}｜'
              f'策略 {end_s:.3f}（{end_s - 1:+.1%}） vs 指数 {end_i:.3f}（{end_i - 1:+.1%}）')
    return (f'<svg viewBox="0 0 {w} {hgt}" style="width:100%;background:#fafafa;'
            f'border:1px solid #eee;border-radius:8px">'
            f'<line x1="12" y1="{hgt - 18 - (1 - lo) / max(hi - lo, 1e-9) * (hgt - 36):.1f}" '
            f'x2="{w - 12}" y2="{hgt - 18 - (1 - lo) / max(hi - lo, 1e-9) * (hgt - 36):.1f}" '
            f'stroke="#bbb" stroke-dasharray="4,3"/>'
            f'{line(idx, "#95a5a6")}{line(strat, "#c0392b")}'
            f'<text x="14" y="16" font-size="11" fill="#888">{labels}</text>'
            f'<text x="{w - 150}" y="16" font-size="11" fill="#c0392b">— 策略</text>'
            f'<text x="{w - 80}" y="16" font-size="11" fill="#95a5a6">— 指数</text></svg>')


def table_html(df_records: list, cols: list, headers: list) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for rec in df_records:
        body += "<tr>" + "".join(f"<td>{esc(rec.get(c, ''))}</td>" for c in cols) + "</tr>"
    return (f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    snap = state.get("snapshot", {})
    alert = state.get("alert", "SILENT")
    color = ALERT_COLOR.get(alert, "#888")

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        hist_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM signals ORDER BY date DESC LIMIT 30")]
    te = cfg.get("test_eval", {})
    bh = cfg.get("test_eval_bh", {})
    ao = cfg.get("anti_overfit", {})
    ve = cfg.get("validation_eval", {})
    freq = cfg["streak_tables"]["frequency"]
    markov = cfg["streak_tables"]["markov"]
    card = (snap.get("card") or {}).get("conditions", {})

    card_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{esc(v['state'])}</td><td>{v['p_up']:.0%}</td>"
        f"<td>{v['fwd20_med']:+.2%}</td><td>{v['fwd20_win']:.0%}</td><td>{v['n_obs']}</td>"
        f"{'<td>样本不足合并</td>' if v.get('merged') else '<td></td>'}</tr>"
        for k, v in card.items())

    cond_rows = ""
    for k, v in card.items():
        cond_rows += f"<li><b>{esc(k)}</b> 当前 {esc(v['state'])}：历史同状态连跌后，次日上涨概率 {v['p_up']:.0%}，20 日收益中位数 {v['fwd20_med']:+.2%}（样本 {v['n_obs']}）</li>"

    html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>农业板块周期监控 · {esc(state.get('date', ''))}</title>
<style>
body{{font-family:"Microsoft YaHei",system-ui,sans-serif;margin:0;background:#f4f6f8;color:#2c3e50}}
.wrap{{max-width:920px;margin:0 auto;padding:16px}}
.banner{{border-radius:10px;padding:14px 18px;color:#fff;margin-bottom:14px}}
.banner h1{{margin:0;font-size:20px}} .banner .sub{{opacity:.9;font-size:13px;margin-top:4px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:14px}}
.card{{background:#fff;border-radius:10px;padding:12px 14px;border:1px solid #eceff1}}
.card .k{{font-size:12px;color:#7f8c8d}} .card .v{{font-size:19px;font-weight:600;margin-top:2px}}
.card .s{{font-size:12px;color:#95a5a6;margin-top:2px}}
h2{{font-size:15px;margin:18px 0 8px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;font-size:13px}}
th,td{{padding:6px 10px;border-bottom:1px solid #f0f2f4;text-align:left}}
th{{background:#f8f9fa;color:#5a6a7a;font-weight:600}}
.note{{font-size:12px;color:#7f8c8d;line-height:1.7}}
ul{{font-size:13px;line-height:1.8}} .warn{{background:#fff8e1;border-left:4px solid #d4a017;padding:8px 12px;border-radius:6px;font-size:12.5px}}
</style></head><body><div class="wrap">

<div class="banner" style="background:{color}">
<h1>农业板块周期监控 · {ALERT_TEXT.get(alert, alert)}（{alert}）</h1>
<div class="sub">{esc(state.get('date', ''))} · 模型 {esc(state.get('model_version', ''))} · 申万农林牧渔指数 · 生成于 {esc(state.get('generated_at', ''))}</div>
</div>

<div class="grid">
<div class="card"><div class="k">收盘 / 今日建议</div><div class="v">{esc(snap.get('hold_days') is not None and '持仓中' or '空仓')}</div><div class="s">{esc(snap.get('event', ''))}{(' · 已持有 ' + str(snap.get('hold_days')) + ' 天') if snap.get('hold_days') is not None else ''}</div></div>
<div class="card"><div class="k">周期相位（CycleScore）</div><div class="v">{esc(snap.get('cycle_phase', '—'))}（{snap.get('cycle_score', 0):+.2f}）</div><div class="s">HP 月频周期分量，谷=+1 峰=-1</div></div>
<div class="card"><div class="k">猪周期相位</div><div class="v">{esc(snap.get('hog_phase', '—'))}</div><div class="s">生猪价格指数（2015 起周频）</div></div>
<div class="card"><div class="k">收缩区制概率</div><div class="v">{snap.get('recession_prob', 0):.0%}</div><div class="s">Markov 区制模型（Hamilton 1989）</div></div>
<div class="card"><div class="k">连跌天数 / 恐慌分</div><div class="v">{snap.get('streak_days', 0)} 天 / {snap.get('panic_score', 0):.0f}</div><div class="s">恐慌加速买入线 = {esc(cfg['signals']['panic_threshold'])}</div></div>
</div>

<h2>连跌买入参考卡（L-B2 · 基本面条件化）</h2>
{'<ul>' + cond_rows + '</ul>' if cond_rows else '<p class="note">当前无连续下跌（连跌 0 天），参考卡不适用。</p>'}
<p class="note">机制（文献综述 §10）：高量/跟跌/高波动/大盘强势下的连跌属流动性冲击，倾向反弹；独跌/缩量/猪价利空中途的基本面型连跌倾向惯性。短尺度看流动性条件，半年尺度看估值、情绪与猪周期相位。</p>

<h2>近 600 个交易日</h2>
{build_chart(state.get('history', []))}

<h2>策略 vs 指数 · 累计净值（近 600 个交易日，含费用与 7 天约束）</h2>
{build_nav_chart(state.get('nav_history', []))}
<p class="note">策略净值含申购 0.15%/赎回 0.5% 费用与 T+1 执行；虚线为归一基准 1.0。曲线展示的是历史回放（冻结模型对全历史的回溯），非实盘承诺。</p>

<h2>连跌频率（训练段 2005-2021 冻结）</h2>
{table_html(freq, ['n', 'episodes_per_year', 'p_continue'], ['连跌≥n 天', '年均发生次数', '继续下跌概率'])}
<p class="note">读法示例：连跌 5 天每年约出现 {freq[4]['episodes_per_year'] if len(freq) > 4 else '—'} 次；连跌 n 天后次日继续下跌概率见马尔可夫表。</p>

<h2>马尔可夫链 P(明日涨 | 已连跌 k)</h2>
{table_html(markov, ['k', 'n_obs', 'p_up_tomorrow'], ['k（已连跌天数）', '历史样本', 'P(明日涨)'])}

<h2>模型档案（V{esc(cfg['version'])} · {esc(cfg.get('architecture', ''))}）</h2>
<table>
<tr><th>验证段（2016-2021）</th><td>年化 {ve.get('ann_return', 0):+.1%}，超额 {ve.get('ann_excess', 0):+.1%}，回撤 {ve.get('max_drawdown', 0):.1%}</td></tr>
<tr><th>测试段（2022- 至今）</th><td>年化 {te.get('ann_return', 0):+.1%} vs 指数 {bh.get('ann_return', 0):+.1%}（超额 {te.get('ann_excess', 0):+.1%}），回撤 {te.get('max_drawdown', 0):.1%} vs 指数 {bh.get('max_drawdown', 0):.1%}</td></tr>
<tr><th>半年目标达成率</th><td>绝对≥4% 或 超额≥3%：测试段 {te.get('roll126_win_abs4_or_ex3', 0):.0%}（滚动半年窗口占比）</td></tr>
<tr><th>7 天最短持有</th><td>测试段违规 {te.get('min_hold_violations', 0)} 次（强制 ≥7 自然日，规避 1.5% 惩罚赎回费）</td></tr>
<tr><th>反过拟合检验</th><td>Reality Check p={ao.get('reality_check', {}).get('rc_p_value')}；DSR={ao.get('dsr', {}).get('dsr')}；PBO={ao.get('pbo')}</td></tr>
</table>
<div class="warn">⚠️ 诚实披露：测试段在 V1.0/V1.1/V1.2 三个版本各评估过一次（共 3 次），上表测试段统计量存在乐观偏差；Reality Check 与 DSR 未达显著，策略价值主张是「周期状态识别 + 赔率改善 + 回撤收缩」，<b>不承诺收益率</b>。真实基准以实盘与月度审计为准。</div>

<h2>近期信号（SQLite）</h2>
{table_html([{k: r[k] for k in ('date', 'alert_level', 'action', 'price', 'cycle_score', 'hog_phase', 'streak_days')} for r in hist_rows],
            ['date', 'alert_level', 'action', 'price', 'cycle_score', 'hog_phase', 'streak_days'],
            ['日期', '警报', '建议', '收盘', 'CycleScore', '猪相位', '连跌'])}

<p class="note">数据源 AKShare（申万指数 / 新浪指数与期货 / 搜猪网-生猪指数 / 宏观月度，宏观按次月 15 日可得对齐防前视）。
完整原理与使用手册见仓库 <a href="agriculture/REPORT.md">agriculture/REPORT.md</a>（GitHub 网页上直接点击）。
本看板仅为研究工具，不构成投资建议。</p>
</div></body></html>"""

    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"[dashboard] 已生成 {OUT_PATH}")


if __name__ == "__main__":
    main()
