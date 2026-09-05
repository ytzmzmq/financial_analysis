# -*- coding: utf-8 -*-
"""农业信号微信推送（Server酱 / PushDeer，独立实现，不引用医药项目代码）。

读取 output_agri.txt + alert_result_agri.txt（CI 中由 tracker/ci_parse 生成），
向 PUSH_KEY / PUSHDEER_KEY 对应渠道推送当日信号。所有警报级别均推送
（与医药项目行为一致）；未配置密钥时静默跳过。

用法: python agriculture/app/notify_agri.py   （CI 中在 ci_parse_agri 之后）
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


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    alert_file = Path.cwd() / "alert_result_agri.txt"
    out_file = Path.cwd() / "output_agri.txt"
    if not alert_file.exists():
        print("[notify-agri] alert_result_agri.txt 不存在，跳过")
        return 0
    fields = dict(
        line.split("=", 1) for line in
        alert_file.read_text(encoding="utf-8").splitlines() if "=" in line
    )
    alert = fields.get("alert", "silent")
    summary = fields.get("summary", "")
    out = out_file.read_text(encoding="utf-8", errors="replace")[:3000] if out_file.exists() else ""

    date_line = out.splitlines()[0] if out else ""
    title = f"农业{ALERT_TEXT.get(alert, alert)}｜{summary[:40]}"
    desp = f"{date_line}\n\n```\n{out}\n```\n\n[看板](https://ytzmzmq.github.io/financial_analysis/dashboard_agri.html)"

    sent = False
    key = os.environ.get("PUSH_KEY", "")
    if key:
        sent = push_serverchan(f"农业板块 {title}", desp, key) or sent
        print(f"[notify-agri] ServerChan: {'sent' if sent else 'failed'}")
    deer = os.environ.get("PUSHDEER_KEY", "")
    if deer:
        sent = push_pushdeer(f"农业板块 {title}", desp, deer) or sent
        print(f"[notify-agri] PushDeer: {'sent' if sent else 'failed'}")
    if not key and not deer:
        print("[notify-agri] 未配置 PUSH_KEY/PUSHDEER_KEY，跳过推送")
    # 推送失败不阻断流水线（Server酱免费额度 5 条/天可能耗尽，次日自动恢复）
    return 0


if __name__ == "__main__":
    sys.exit(main())
