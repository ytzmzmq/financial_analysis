# -*- coding: utf-8 -*-
"""医药+农业合并微信推送（Server酱 / PushDeer）——每天只消耗一条推送额度。

读取两板块的 CI 产物：
- 医药：alert_result.txt（alert/score）+ output.txt（信号全文）
- 农业：alert_result_agri.txt（alert/score/summary）+ output_agri.txt（信号全文）
拼成一条消息发送；医药侧已在 workflow 中移除其独立推送的 PUSH_KEY，本脚本是
唯一的推送出口。未配置密钥或发送失败均不阻断流水线（exit 0）。

用法: python agriculture/app/notify_combined.py   （CI 中在两个 ci_parse 之后）
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ALERT_TEXT = {"red": "🔴 行动日", "yellow": "🟡 关注", "silent": "⚪ 常态"}
BASE_URL = "https://ytzmzmq.github.io/financial_analysis"


def push_serverchan(title: str, content: str, key: str) -> bool:
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = json.dumps({"title": title, "desp": content}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [ServerChan] Failed: {e}")
        return False


def push_pushdeer(title: str, content: str, key: str) -> bool:
    try:
        url = ("https://api2.pushdeer.com/message/push?pushkey=" + urllib.parse.quote(key)
               + "&text=" + urllib.parse.quote(title)
               + "&desp=" + urllib.parse.quote(content))
        urllib.request.urlopen(url, timeout=10)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [PushDeer] Failed: {e}")
        return False


def read_fields(path: str) -> dict:
    p = Path.cwd() / path
    if not p.exists():
        return {}
    return dict(
        line.split("=", 1) for line in
        p.read_text(encoding="utf-8", errors="replace").splitlines() if "=" in line
    )


def read_text(path: str, limit: int = 2200) -> str:
    p = Path.cwd() / path
    if not p.exists():
        return "（无输出）"
    return p.read_text(encoding="utf-8", errors="replace")[:limit]


def main() -> int:
    med = read_fields("alert_result.txt")
    agri = read_fields("alert_result_agri.txt")
    med_alert = med.get("alert", "silent")
    agri_alert = agri.get("alert", "silent")
    agri_summary = agri.get("summary", "")

    title = f"医药:{med_alert} 农业:{agri_alert}｜{agri_summary[:24]}"
    desp = (
        f"# 每日板块信号（合并推送）\n\n"
        f"## 💊 医药生物 {ALERT_TEXT.get(med_alert, med_alert)}（Score {med.get('score', '0')}）\n\n"
        f"```\n{read_text('output.txt')}\n```\n\n"
        f"## 🌾 农业 {ALERT_TEXT.get(agri_alert, agri_alert)}（恐慌分 {agri.get('score', '0')}）\n\n"
        f"{agri_summary}\n\n"
        f"```\n{read_text('output_agri.txt')}\n```\n\n"
        f"[🌾 农业看板]({BASE_URL}/dashboard_agri.html)｜"
        f"[💊 医药看板]({BASE_URL}/dashboard.html)｜"
        f"[📖 农业报告](https://github.com/ytzmzmq/financial_analysis/blob/main/agriculture/REPORT.md)"
    )

    sent = False
    key = os.environ.get("PUSH_KEY", "")
    if key:
        sent = push_serverchan(title, desp, key) or sent
        print(f"[notify-combined] ServerChan: {'sent' if sent else 'failed'}")
    deer = os.environ.get("PUSHDEER_KEY", "")
    if deer:
        sent = push_pushdeer(title, desp, deer) or sent
        print(f"[notify-combined] PushDeer: {'sent' if sent else 'failed'}")
    if not key and not deer:
        print("[notify-combined] 未配置 PUSH_KEY/PUSHDEER_KEY，跳过推送")
    # 推送失败不阻断流水线（Server酱免费额度 5 条/天）
    return 0


if __name__ == "__main__":
    sys.exit(main())
