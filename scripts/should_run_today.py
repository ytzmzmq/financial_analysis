"""CI 预检：判断「当日信号是否已经生成」，用于避免一天重复运行。

背景
----
GitHub 对公共仓库的 schedule 触发是 best-effort 排队，本仓库实测被延迟
5.5~8.5 小时（cron 写 06:45 UTC = 北京 14:45，实际落在北京 20:00~23:20）。
因此本仓库同时保留两条触发路径：

  1. 外部准点调度（cron-job.org / 本机计划任务）在 14:45 调 workflow_dispatch；
  2. 原有的 schedule 作为兜底（延迟到晚上，但保证当天一定有结果）。

两条路径会让同一天跑两次，因此用本预检把「一天只干一次活」约束住：
  - 14:45 那次成功 → 当日晚些的 schedule 那次看到信号已存在 → 直接跳过
    （既不会重复微信推送，也不会用收盘数据覆盖 14:45 的尾盘信号）；
  - 14:45 那次取数失败（未落库）→ 晚些的 schedule 那次发现当日仍无信号
    → 自动重试，实现「自愈」。

用法
----
    python scripts/should_run_today.py

输出
----
    run=true   今日尚无信号 → 需要运行
    run=false  今日已有信号 → 跳过

在 GitHub Actions 中会把 run 写入 $GITHUB_OUTPUT；本地运行时只打印到标准输出。
注意：runner 时区为 UTC，判定日期需换算北京时间（UTC+8）。
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BEIJING = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
DBS = (
    ROOT / "data" / "processed" / "signals.db",
    ROOT / "agriculture" / "data" / "processed" / "signals.db",
)


def _has_today(db: Path, today: str) -> bool:
    """读取 signals 表，判断是否存在 date == today 的行。读失败按「无信号」处理。"""
    if not db.exists():
        print("  [INFO] 数据源不存在（视为无信号）: %s" % db)
        return False
    try:
        uri = "file:%s?mode=ro" % db.as_posix()
        con = sqlite3.connect(uri, uri=True)
        try:
            row = con.execute(
                "SELECT COUNT(*) FROM signals WHERE date = ?", (today,)
            ).fetchone()
        finally:
            con.close()
        return bool(row and row[0])
    except Exception as exc:  # 表缺失 / 文件损坏等
        print("  [WARN] 预检读取失败（视为无信号）: %s -> %s" % (db, exc))
        return False


def main() -> int:
    today = datetime.now(BEIJING).strftime("%Y-%m-%d")
    hit = [str(p.relative_to(ROOT).as_posix()) for p in DBS if _has_today(p, today)]
    run = "false" if hit else "true"
    print("预检：北京日期=%s 已有当日信号的数据源=%s → run=%s" % (today, hit or "无", run))

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write("run=%s\n" % run)
        print("已写入 $GITHUB_OUTPUT: run=%s" % run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
