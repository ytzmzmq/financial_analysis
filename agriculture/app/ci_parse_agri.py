"""CI 辅助：从 output_agri.txt 解析警报级别、分数与可读快照（供提交标题/issue 使用）。"""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "output_agri.txt"
with open(path, encoding="utf-8", errors="replace") as f:
    text = f.read()

m = re.search(r"\[(SILENT|YELLOW|RED)\]", text)
alert = m.group(1).lower() if m else "silent"
m = re.search(r"Score:\s*(\d+)", text)
score = m.group(1) if m else "0"

event_m = re.search(r"今日建议[:：]\s*(.+)", text)
event = (event_m.group(1).strip() if event_m else "").replace("|", "/")
hold_m = re.search(r"持仓 (是（已 (\d+) 天）|是|否)", text)
holding = "否" if (hold_m and hold_m.group(1) == "否") else ("是" if hold_m else "")
hold_days = hold_m.group(2) if (hold_m and hold_m.lastindex and hold_m.lastindex >= 2 and hold_m.group(2)) else ""
cycle_m = re.search(r"周期 (\S+?)\(", text)
cycle = cycle_m.group(1) if cycle_m else ""
hog_m = re.search(r"猪周期 (\S+)", text)
hog = hog_m.group(1) if hog_m else ""
panic_m = re.search(r"恐慌分 (\d+)", text)
panic = panic_m.group(1) if panic_m else score
streak_m = re.search(r"连跌 (\d+) 天", text)
streak = streak_m.group(1) if streak_m else "0"

parts = []
if event:
    parts.append(event)
if holding:
    parts.append(f"持仓{holding}{hold_days + '天' if hold_days else ''}")
if cycle:
    parts.append(f"周期{cycle}")
if hog:
    parts.append(f"猪{hog}")
parts.append(f"恐慌{panic}")
parts.append(f"连跌{streak}天")
summary = " | ".join(parts)

with open("alert_result_agri.txt", "w", encoding="utf-8") as f:
    f.write(f"alert={alert}\nscore={score}\nsummary={summary}\n")
print(f"agri alert={alert} score={score} summary={summary}")
