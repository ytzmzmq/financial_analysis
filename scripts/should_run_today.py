"""CI 预检：判断「最近一个 A 股交易日」的信号是否已生成，用于一天只干一次活。

背景
----
GitHub 对公共仓库的 schedule 触发是 best-effort 排队，本仓库实测被延迟
5.5~8.5 小时（cron 写 06:45 UTC = 北京 14:45，实际落在北京 20:00~23:20）。
因此本仓库同时保留两条触发路径：

  1. 外部准点调度（cron-job.org / 本机计划任务）在 14:45 调 workflow_dispatch；
  2. 原有的 schedule 作为兜底（延迟到晚上，但保证当天一定有结果）。

两条路径会让同一天跑两次，因此用本预检把「一天只干一次活」约束住：
  - 14:45 那次成功 → 晚些的 schedule 那次看到信号已存在 → 直接跳过
    （既不会重复微信推送，也不会用收盘数据覆盖 14:45 的尾盘信号）；
  - 14:45 那次取数失败（未落库）→ 晚些的 schedule 那次发现当日仍无信号
    → 自动重试，实现「自愈」。

为什么按「最近交易日」而不是「北京今天」（2026-10-24 重构）
-------------------------------------------------------------
旧逻辑问「北京今天有没有信号行」。当 schedule 被延迟到**跨过北京午夜**
（实测 2026-10-12：06:45 UTC 的 cron 落在北京 10-13 00:11），“今天”
已经翻到次日 → 闸门误放行 → 午夜重复运行、重复微信推送、收盘数据
覆盖尾盘信号（当日出现两条 [auto] 提交，c4f782a / 1557624）。

新逻辑把「运行时刻」映射到「应已产出信号的最近 A 股交易日」：

    北京时刻 >= 14:00 → 目标日 = 当天（尾盘窗口；周末回退到上周五）
    北京时刻 <  14:00 → 目标日 = 上一个交易日（凌晨补跑窗口，
                        覆盖 schedule 跨过北京午夜的情景）

任一数据源已有目标日信号 → run=false（跳过）；否则 run=true。
附带收益：若某次运行的 git push 失败导致信号行缺失，次日凌晨的
schedule 兜底会以「上一交易日无信号」再次放行，自动回补。

已知局限：不识别法定节假日。节假日运行的取数仍返回上一交易日收盘，
可能落一行重复数据——与重构前行为一致，未变化。

用法
----
    python scripts/should_run_today.py

输出
----
    run=true   目标交易日尚无信号 → 需要运行
    run=false  目标交易日已有信号 → 跳过

在 GitHub Actions 中会把 run 写入 $GITHUB_OUTPUT；本地运行时只打印到标准输出。
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BEIJING = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
DBS = (
    ROOT / "data" / "processed" / "signals.db",
    ROOT / "agriculture" / "data" / "processed" / "signals.db",
)

# 尾盘目标时刻是 14:45，14:00 之前不可能有「当日」信号，以此为分界：
# 14:00 前视为上一交易日的补跑窗口，14:00 后（含尾盘与晚间兜底）视为当日。
SESSION_SPLIT_HOUR = 14


def _prev_trading_day(d: date) -> date:
    """d 的上一个工作日（跳过周末；节假日无法离线识别，见模块 docstring）。"""
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def target_session(now: datetime) -> date:
    """运行时刻（北京时间）→ 应已产出信号的最近 A 股交易日。"""
    d = now.date()
    if now.hour < SESSION_SPLIT_HOUR:
        return _prev_trading_day(d)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _has_signal(db: Path, day: str) -> bool:
    """读取 signals 表，判断是否存在 date == day 的行。读失败按「无信号」处理。"""
    if not db.exists():
        print("  [INFO] 数据源不存在（视为无信号）: %s" % db)
        return False
    try:
        uri = "file:%s?mode=ro" % db.as_posix()
        con = sqlite3.connect(uri, uri=True)
        try:
            row = con.execute(
                "SELECT COUNT(*) FROM signals WHERE date = ?", (day,)
            ).fetchone()
        finally:
            con.close()
        return bool(row and row[0])
    except Exception as exc:  # 表缺失 / 文件损坏等
        print("  [WARN] 预检读取失败（视为无信号）: %s -> %s" % (db, exc))
        return False


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT).as_posix())
    except ValueError:  # 测试传入的临时目录不在仓库内
        return str(p)


def decide(now: datetime, dbs=DBS) -> tuple[str, date, list[str]]:
    """预检决策（纯函数，便于离线回归）：返回 (run, 目标交易日, 已有信号的数据源)。"""
    target = target_session(now)
    hit = [_rel(p) for p in dbs if _has_signal(p, target.isoformat())]
    run = "false" if hit else "true"
    return run, target, hit


def main(now: datetime | None = None) -> int:
    now = now or datetime.now(BEIJING)
    run, target, hit = decide(now)
    print("预检：北京时刻=%s 目标交易日=%s 已有该日信号的数据源=%s → run=%s" % (
        now.strftime("%Y-%m-%d %H:%M"), target.isoformat(), hit or "无", run))

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write("run=%s\n" % run)
        print("已写入 $GITHUB_OUTPUT: run=%s" % run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
