# -*- coding: utf-8 -*-
"""离线回归校验：CI 解析层不得把"故障"上报成"常态"，核心取数接口需重试。

不联网、不依赖 akshare/pandas 之外的东西（pandas 仅在伪造数据源里用到）。
用法: python scripts/verify_ci_fix.py
"""
import importlib.util
import io
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = next(p for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]
            if (p / ".github" / "workflows" / "medical_tracker.yml").exists())
PY = sys.executable
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

fails = []


def check(name, got, want):
    ok = got == want
    print(("  [PASS] " if ok else "  [FAIL] ") + f"{name}: got={got!r} want={want!r}")
    if not ok:
        fails.append(name)


def parse_fields(path):
    return dict(l.split("=", 1) for l in
                Path(path).read_text(encoding="utf-8").splitlines() if "=" in l)


def run_medical_parser(text, tmp):
    (Path(tmp) / "output.txt").write_text(text, encoding="utf-8")
    subprocess.run([PY, str(REPO / "app" / "ci_parse.py")], cwd=tmp, capture_output=True)
    return parse_fields(Path(tmp) / "alert_result.txt")


def run_agri_parser(text, tmp):
    (Path(tmp) / "output_agri.txt").write_text(text, encoding="utf-8")
    subprocess.run([PY, str(REPO / "agriculture" / "app" / "ci_parse_agri.py")],
                   cwd=tmp, capture_output=True)
    return parse_fields(Path(tmp) / "alert_result_agri.txt")


print("=" * 66)
print("A. 医药解析 app/ci_parse.py —— 故障不得伪装成 silent")
print("=" * 66)
tmp = tempfile.mkdtemp()
for label, text, want in [
    ("真实 SILENT", "  [SILENT] 常态区间\n  Score: 0\n", ("silent", "0")),
    ("真实 YELLOW", "  [YELLOW] 近触发\n  Score: 2\n", ("yellow", "2")),
    ("真实 RED", "  [RED] ARMED\n  Score: 4\n", ("red", "4")),
    ("取数失败（真实故障场景）",
     "  [ERROR] 数据拉取失败: Expecting value: line 1 column 1 (char 0)\n", ("error", "0")),
    ("非致命 WARN + 正常级别",
     "  [WARN] north_flow 拉取失败(非致命): x\n  [SILENT] 常态\n  Score: 0\n", ("silent", "0")),
    ("输出完全为空", "", ("unknown", "0")),
]:
    d = run_medical_parser(text, tmp)
    check(label, (d["alert"], d["score"]), want)
shutil.rmtree(tmp, ignore_errors=True)

print()
print("=" * 66)
print("B. 农业解析 agriculture/app/ci_parse_agri.py")
print("=" * 66)
tmp = tempfile.mkdtemp()
for label, text, want in [
    ("真实 YELLOW",
     "[YELLOW] Score: 56\n今日建议: 持有\n持仓 是（已 5 天）\n周期 扩张(0.1)\n"
     "猪周期 扩张\n恐慌分 56\n连跌 2 天\n", ("yellow", "56")),
    ("取数失败（原实现打印 [SILENT]）",
     "[ERROR] Score: 0 | 数据获取失败，今日无信号（KeyError）\n", ("error", "0")),
    ("输出为空", "", ("unknown", "0")),
]:
    d = run_agri_parser(text, tmp)
    check(label, (d["alert"], d["score"]), want)
shutil.rmtree(tmp, ignore_errors=True)

print()
print("=" * 66)
print("C. 核心取数重试 src/data_fetcher/akshare_source.py")
print("=" * 66)
spec = importlib.util.spec_from_file_location(
    "ak_src_under_test", REPO / "src" / "data_fetcher" / "akshare_source.py")
aks = importlib.util.module_from_spec(spec)
sys.modules["ak_src_under_test"] = aks
spec.loader.exec_module(aks)
aks.time.sleep = lambda s: None  # 跳过退避等待
aks.fetch_realtime_sw_index = lambda *a, **k: None   # 保持离线
aks.fetch_realtime_price = lambda: None              # 保持离线


class FlakyAK:
    """前 fail_times 次抛非 JSON 错误（模拟 AKShare 限流页面），之后成功。"""

    def __init__(self, fail_times):
        self.calls = 0
        self.fail_times = fail_times

    def index_hist_sw(self, symbol="801150", period="day"):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        import pandas as pd
        return pd.DataFrame({
            "日期": pd.date_range("2026-01-01", periods=5, freq="D"),
            "开盘": [1.0] * 5, "收盘": [2.0] * 5, "最高": [3.0] * 5,
            "最低": [0.5] * 5, "成交量": [10] * 5, "成交额": [100] * 5,
        })

    def index_min_sw(self, symbol="801150"):
        return None


aks.ak = FlakyAK(fail_times=1)
df = aks.AKShareSource().fetch_sw_medical("20200101")
check("抖动 1 次后成功（重试生效）", (len(df) > 0, aks.ak.calls), (True, 2))

aks.ak = FlakyAK(fail_times=99)
try:
    aks.AKShareSource().fetch_sw_medical("20200101")
    check("连续失败应抛 RuntimeError", "no-raise", "RuntimeError")
except RuntimeError as e:
    check("异常信息含接口名（可定位）", "index_hist_sw(801150)" in str(e), True)
except Exception as e:  # noqa: BLE001
    check("异常类型", type(e).__name__, "RuntimeError")

print()
print("=" * 66)
print("D. 预检闸门 scripts/should_run_today.py —— 按「最近交易日」去重")
print("=" * 66)
spec2 = importlib.util.spec_from_file_location(
    "preflight_under_test", REPO / "scripts" / "should_run_today.py")
srt = importlib.util.module_from_spec(spec2)
sys.modules["preflight_under_test"] = srt
spec2.loader.exec_module(srt)
from datetime import datetime, timedelta  # noqa: E402


def make_db(tmp, dates):
    """建一个含指定日期行的最小 signals.db，模拟真实数据源。"""
    db = Path(tmp) / "signals.db"
    db.unlink(missing_ok=True)  # 每个 case 重建，避免表已存在
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE signals (date TEXT PRIMARY KEY, score REAL)")
    con.executemany("INSERT INTO signals VALUES (?, 0)", [(d,) for d in dates])
    con.commit()
    con.close()
    return db


def gate(tmp, dates, now_str):
    """带一个数据源的预检决策：返回 (run, 目标日)。"""
    db = make_db(tmp, dates)
    run, target, _ = srt.decide(datetime.fromisoformat(now_str).replace(tzinfo=srt.BEIJING), (db,))
    return run, target.isoformat()


tmp = tempfile.mkdtemp()
MON_1012, TUE_1013 = "2026-10-12", "2026-10-13"
check("尾盘时刻（周三 14:52）当日无信号 → 运行",
      gate(tmp, ["2026-10-09"], "2026-10-14T14:52:00")[0], "true")
check("尾盘时刻当日已有信号 → 跳过",
      gate(tmp, ["2026-10-14"], "2026-10-14T14:52:00")[0], "false")
check("晚间兜底（22:36）当日已有信号 → 跳过",
      gate(tmp, ["2026-10-14"], "2026-10-14T22:36:00")[0], "false")
# 2026-10-12 实际事故：schedule 跨过北京午夜（10-13 00:11 运行），10-12 已有尾盘信号
check("跨午夜补跑（10-13 00:11）上一交易日已有信号 → 跳过（10-12 事故回归）",
      gate(tmp, [MON_1012], "2026-10-13T00:11:00"), ("false", MON_1012))
check("跨午夜补跑上一交易日无信号（当日 dispatch 失败/未推送）→ 放行自愈",
      gate(tmp, ["2026-10-09"], "2026-10-13T00:11:00"), ("true", MON_1012))
check("周六午后运行 → 目标日回退到周五，已有信号则跳过",
      gate(tmp, ["2026-10-23"], "2026-10-24T15:00:00"), ("false", "2026-10-23"))
check("周日清晨运行 → 目标日为上周五",
      gate(tmp, ["2026-10-16"], "2026-10-18T09:00:00"), ("false", "2026-10-16"))
shutil.rmtree(tmp, ignore_errors=True)

print()
print("=" * 66)
print("失败项:", fails if fails else "无 — 全部通过")
print("=" * 66)
sys.exit(1 if fails else 0)
