"""本地准点触发器：调用 GitHub workflow_dispatch 启动每日流水线。

背景
----
GitHub 对公共仓库的 `schedule` 触发是 best-effort 排队，本仓库实测被延迟
5.5~8.5 小时（cron 06:45 UTC = 北京 14:45，实际落在北京 20:00~23:20），
做不到「14:45 出结果」。而 `workflow_dispatch` 走 REST API 触发约 20 秒内启动，
所以由本脚本在本地按时调 dispatch。

设计要点
--------
- 令牌从本机 Windows 凭据管理器（Git Credential Manager）**实时读取**，
  不落盘、不写进任何配置文件。
- **不传 force** ⇒ 流水线里的「当日去重」预检仍然生效：若当天已出结果会自动跳过，
  不会重复微信推送；若当天还没结果则正常执行（这正是我们要的）。
- 网络：优先直连 api.github.com；失败则回退本机 Clash 代理 127.0.0.1:7890。
- 日志：%LOCALAPPDATA%\\financial_analysis_ci\\trigger_ci.log

用法
----
    python scripts/trigger_ci.py            # 准点用（含北京时间窗口判断）
    python scripts/trigger_ci.py --force    # 忽略窗口判断，立即触发（人工排查）
    python scripts/trigger_ci.py --check    # 只验证令牌可用，不触发

关于时区（重要）
----------------
本机 Windows 时区是**美西（Pacific）**，而目标时刻是**北京时间 14:45（A股尾盘）**。
因此计划任务注册了两个触发时刻 —— 当地 22:52 与 23:52（周日~周四），分别覆盖
夏令时 PST(UTC-8) 与 PDT(UTC-7)：两者之中永远只有一个会落在北京 14:52。
本脚本的窗口判断（北京 14:45~15:30，工作日）负责把另一个挡掉，
这样即使系统时区或夏令时变化，也只会触发一次、且落在正确时刻。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 北京时间窗口：只有落在这个区间才真正触发（覆盖 14:45 目标 + 迟到的补跑）
BEIJING = dt.timezone(dt.timedelta(hours=8))
WIN_START = (14, 45)
WIN_END = (15, 30)

OWNER = "ytzmzmq"
REPO = "financial_analysis"
WORKFLOW = "medical_tracker.yml"
BRANCH = "main"
API = "https://api.github.com"
DISPATCH_URL = "%s/repos/%s/%s/actions/workflows/%s/dispatches" % (API, OWNER, REPO, WORKFLOW)
PROXY = "http://127.0.0.1:7890"

GIT_CANDIDATES = (
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
    "git",
)

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "financial_analysis_ci"
LOG_FILE = LOG_DIR / "trigger_ci.log"

# 计划任务里没有真实控制台，避免中文输出触发 UnicodeEncodeError 而中断脚本
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(msg: str) -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[%s] %s" % (stamp, msg)
    print(line)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def read_token() -> str | None:
    """从 Windows 凭据管理器（GCM）读取 github.com 的令牌。"""
    env = dict(os.environ)
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_TERMINAL_PROMPT"] = "0"
    for git in GIT_CANDIDATES:
        try:
            proc = subprocess.run(
                [git, "-c", "credential.helper=manager", "credential", "fill"],
                input="protocol=https\nhost=github.com\n\n",
                capture_output=True,
                text=True,
                timeout=40,
                env=env,
            )
        except Exception as exc:
            log("  读取令牌失败（%s）：%s" % (git, exc))
            continue
        for raw in proc.stdout.splitlines():
            if raw.startswith("password="):
                tok = raw[len("password="):].strip()
                if tok:
                    return tok
    return None


def _post(url: str, token: str, proxy: str | None) -> int:
    data = json.dumps({"ref": BRANCH}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    handlers = [urllib.request.ProxyHandler({} if not proxy else {"https": proxy, "http": proxy})]
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=60) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        log("  HTTP %s：%s" % (exc.code, body))
        return exc.code


def in_beijing_window(now: dt.datetime | None = None) -> tuple[bool, str]:
    """判断此刻是否落在「北京工作日 14:45~15:30」窗口内。"""
    now = now or dt.datetime.now(BEIJING)
    desc = "北京 %s 周%s %02d:%02d" % (
        now.strftime("%Y-%m-%d"),
        "一二三四五六日"[now.weekday()],
        now.hour,
        now.minute,
    )
    if now.weekday() >= 5:
        return False, desc + "（周末，跳过）"
    cur = now.hour * 60 + now.minute
    if not (WIN_START[0] * 60 + WIN_START[1] <= cur <= WIN_END[0] * 60 + WIN_END[1]):
        return False, desc + "（不在 %02d:%02d~%02d:%02d 窗口，跳过）" % (
            WIN_START[0], WIN_START[1], WIN_END[0], WIN_END[1])
    return True, desc + "（在窗口内）"


def main() -> int:
    check_only = "--check" in sys.argv
    forced = "--force" in sys.argv
    log("--- trigger_ci 启动%s%s ---" % ("（仅检查）" if check_only else "", "（--force）" if forced else ""))

    if not (check_only or forced):
        ok, desc = in_beijing_window()
        log("窗口判断：%s" % desc)
        if not ok:
            return 0

    token = read_token()
    if not token:
        log("失败：未能从凭据管理器取到 github.com 令牌。请确认已用系统 Git 登录过 GitHub。")
        return 2
    log("令牌读取成功（%s..., %d 位）" % (token[:4], len(token)))

    if check_only:
        return 0

    for label, proxy in (("直连", None), ("代理 %s" % PROXY, PROXY)):
        code = _post(DISPATCH_URL, token, proxy)
        if code in (204, 201, 200):
            log("触发成功（%s，HTTP %s）：已请求运行 %s" % (label, code, WORKFLOW))
            return 0
        log("  %s 失败（HTTP %s），尝试下一条通道" % (label, code))

    log("失败：直连与代理均未触发成功。")
    return 4


if __name__ == "__main__":
    sys.exit(main())
