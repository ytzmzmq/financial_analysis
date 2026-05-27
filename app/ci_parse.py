"""CI 辅助脚本：从 output.txt 解析 alert level 和 score"""
import sys, re

with open("output.txt", "r", encoding="utf-8", errors="replace") as f:
    text = f.read()

# 解析 alert: 找 [SILENT] 或 [YELLOW] 或 [RED]
m = re.search(r'\[(SILENT|YELLOW|RED)\]', text)
alert = m.group(1).lower() if m else "silent"

# 解析 score
m = re.search(r'Score:\s*(\d+)', text)
score = m.group(1) if m else "0"

# 输出给 GitHub Actions
with open("alert_result.txt", "w") as f:
    f.write(f"alert={alert}\nscore={score}\n")
print(f"alert={alert} score={score}")
