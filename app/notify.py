"""
推送通知模块 — 支持多种推送渠道

用法:
    python app/notify.py                    # 运行 tracker 并在有警报时推送
    python app/notify.py --dry-run          # 仅打印，不实际推送

环境变量 (可选, 不设置则仅打印):
    PUSH_KEY       Server酱 SendKey (https://sct.ftqq.com/)
    PUSHDEER_KEY   PushDeer pushkey
    WEBHOOK_URL    自定义 Webhook URL (POST JSON)
"""
import sys
import os
import json
import urllib.request
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def push_serverchan(title: str, content: str, push_key: str = None) -> bool:
    """Server酱 (微信推送)"""
    key = push_key or os.environ.get("PUSH_KEY", "")
    if not key:
        return False
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = json.dumps({"title": title, "desp": content}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [ServerChan] Failed: {e}")
        return False


def push_pushdeer(title: str, content: str, push_key: str = None) -> bool:
    """PushDeer"""
    key = push_key or os.environ.get("PUSHDEER_KEY", "")
    if not key:
        return False
    try:
        url = f"https://api2.pushdeer.com/message/push?pushkey={key}&text={urllib.parse.quote(title)}&desp={urllib.parse.quote(content)}"
        urllib.request.urlopen(url, timeout=10)
        return True
    except Exception as e:
        print(f"  [PushDeer] Failed: {e}")
        return False


def push_webhook(title: str, content: str, webhook_url: str = None) -> bool:
    """自定义 Webhook"""
    url = webhook_url or os.environ.get("WEBHOOK_URL", "")
    if not url:
        return False
    try:
        data = json.dumps({"title": title, "content": content, "time": datetime.now().isoformat()}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [Webhook] Failed: {e}")
        return False


def push(title: str, content: str) -> bool:
    """尝试所有渠道"""
    sent = False
    for fn in [push_serverchan, push_pushdeer, push_webhook]:
        if fn(title, content):
            sent = True
    # GitHub Actions: 输出到 workflow summary
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"## {title}\n\n{content}\n")
        sent = True
    return sent


def run(dry_run: bool = False, test_push: bool = False):
    """主入口：计算信号 + 按需推送"""
    from app.tracker import _compute, _load_data

    # 测试模式：强制发送测试推送
    if test_push:
        title = "测试推送 — 医药板块监控器"
        content = f"如果你收到这条消息，说明推送配置成功！\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"  测试模式: 强制推送")
        if not dry_run:
            sent = push(title, content)
            if sent:
                print("  测试推送已发送！请检查微信/手机是否收到。")
            else:
                print("  推送失败！请检查 PUSH_KEY 是否正确设置。")
                print(f"  当前 PUSH_KEY: {'已设置' if os.environ.get('PUSH_KEY') else '未设置'}")
        else:
            print(f"  [dry-run] 标题: {title}\n  内容: {content}")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 运行监控...")
    sig = _compute(_load_data())
    alert = sig["alert"]
    score = sig["score"]

    # 构建推送内容
    lines = [
        f"日期: {sig['date']}",
        f"指数: {sig['price']:.0f}",
        f"Score: {score}/5",
        f"警报: [{alert['level'].upper()}] {alert['message']}",
        "",
        "--- 距离触发 ---",
    ]
    for key in ["D", "C"]:
        d = sig["distance_to_trigger"][key]
        if d["triggered"]:
            lines.append(f"{d['name']}: 已触发")
        elif d.get("trigger_price"):
            lines.append(f"{d['name']}: 触发价 {d['trigger_price']:.0f} (距当前 {d['pct_away']:+.1f}%)")
    content = "\n".join(lines)

    # 根据警报级别决定是否推送
    level = alert["level"]
    if level == "silent":
        print(f"  Score={score} [{level}] — 静默, 不推送")
        return

    # YELLOW 或 RED: 推送
    emoji = "🔴" if level == "red" else "🟡"
    title = f"{emoji} 医药板块{'ARMED!' if level == 'red' else '近触发预警'} (Score={score})"

    print(f"  [{level.upper()}] {alert['message']}")
    print(f"  推送标题: {title}")

    if not dry_run:
        sent = push(title, content)
        if sent:
            print("  推送已发送")
        else:
            print("  未配置推送渠道 (设置 PUSH_KEY / PUSHDEER_KEY / WEBHOOK_URL 环境变量)")
    else:
        print("  [dry-run] 跳过推送")
        print(content)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    test = "--test" in sys.argv
    run(dry_run=dry, test_push=test)
