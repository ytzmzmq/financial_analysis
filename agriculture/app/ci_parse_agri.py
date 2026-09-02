"""CI 辅助：从 output_agri.txt 解析 alert level 和 score（与医药 ci_parse.py 同构）。"""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "output_agri.txt"
with open(path, encoding="utf-8", errors="replace") as f:
    text = f.read()

m = re.search(r"\[(SILENT|YELLOW|RED)\]", text)
alert = m.group(1).lower() if m else "silent"
m = re.search(r"Score:\s*(\d+)", text)
score = m.group(1) if m else "0"

with open("alert_result_agri.txt", "w", encoding="utf-8") as f:
    f.write(f"alert={alert}\nscore={score}\n")
print(f"agri alert={alert} score={score}")
