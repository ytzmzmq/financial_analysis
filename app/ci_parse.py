"""CI 辅助脚本：从 output.txt 解析 alert level 和 score"""
import sys, re

with open("output.txt", "r", encoding="utf-8", errors="replace") as f:
    text = f.read()

# 解析 alert: 找 [SILENT] 或 [YELLOW] 或 [RED]
# 注意：取数/计算失败时 notify.py 会在打印级别之前就 return（只留下 [ERROR]），
# 旧逻辑把"没有级别"默认成 silent，等于把故障上报成"常态区间"。
# 这里显式区分三种情况，故障一律标 error，绝不伪装成正常信号。
m = re.search(r'\[(SILENT|YELLOW|RED)\]', text)
if m:
    alert = m.group(1).lower()
elif re.search(r'\[(ERROR|WARN)\]|Traceback', text):
    alert = "error"
else:
    alert = "unknown"

# 解析 score
m = re.search(r'Score:\s*(\d+)', text)
score = m.group(1) if m else "0"

# 输出给 GitHub Actions
with open("alert_result.txt", "w") as f:
    f.write(f"alert={alert}\nscore={score}\n")
print(f"alert={alert} score={score}")
