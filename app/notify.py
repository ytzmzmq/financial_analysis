"""
推送通知模块 — Windows 桌面通知 + 远程推送

渠道优先级: Windows Toast (本地) → Server酱 / PushDeer / Webhook (远程, 可选)

用法:
    python app/notify.py                    # 运行 tracker 并在有警报时推送
    python app/notify.py --dry-run          # 仅打印，不实际推送
    python app/notify.py --test             # 发送测试通知

远程推送环境变量 (可选, 不设置则仅桌面通知):
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


def push_toast(title: str, content: str) -> bool:
    """Windows 桌面通知 (通过 plyer, 无需任何 API Key)"""
    try:
        from plyer import notification
        notification.notify(
            title=title[:100],
            message=content[:256],
            app_name="医药板块监控器",
            timeout=10,
        )
        return True
    except Exception as e:
        print(f"  [Toast] Failed: {e}")
        return False


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
    """尝试所有渠道: 桌面通知优先，再尝试远程推送"""
    sent = False
    for fn in [push_toast, push_serverchan, push_pushdeer, push_webhook]:
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

    # Windows 控制台可能使用 GBK，无法打印 emoji，强制切 UTF-8
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # 测试模式：强制发送测试推送
    if test_push:
        title = "测试推送 — 医药板块监控器"
        content = f"如果你收到这条消息，说明推送配置成功！\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"  测试模式: 强制推送")
        if not dry_run:
            sent = push(title, content)
            if sent:
                print("  测试推送已发送！请检查是否收到桌面通知或手机推送。")
            else:
                print("  推送失败！请检查系统通知设置或 PUSH_KEY 是否正确。")
        else:
            print(f"  [dry-run] 标题: {title}\n  内容: {content}")
        return

    now = datetime.now()
    weekday_cn = "一二三四五六日"[now.weekday()]
    print(f"[{now.strftime('%Y-%m-%d')} 周{weekday_cn} {now.strftime('%H:%M:%S')}] 运行监控...")

    from app.db import log_error

    # 分步执行：数据拉取 → 信号计算，分别记录错误
    try:
        data = _load_data()
    except Exception as e:
        err_msg = f"数据拉取失败: {e}"
        print(f"  [ERROR] {err_msg}")
        log_error("data_fetch", err_msg, "error")
        return

    try:
        sig = _compute(data)
    except Exception as e:
        err_msg = f"信号计算失败: {e}"
        print(f"  [ERROR] {err_msg}")
        log_error("compute", err_msg, "error")
        return
    alert = sig["alert"]
    score = sig["score"]
    tier = sig.get("signal_tier", "")
    n_factors = sig.get("n_factors", 0)
    max_score = sig.get("max_score", 5)
    model_ver = sig.get("model_version", "")

    # 构建推送内容 (V5.2 增强格式)
    lines = [
        f"日期: {sig['date']}",
        f"指数: {sig['price']:.0f}",
        f"Score: {score}/{max_score}  ({n_factors}个因子触发)",
        f"分级: {tier}  模型: {model_ver}",
        f"警报: [{alert['level'].upper()}] {alert['message']}",
    ]

    # 底部概率
    bp = sig.get("bottom_prob", {})
    if bp and bp.get("components"):
        lines.insert(3, f"底部概率: {bp['score']:.0f}/100")

    # 市场环境
    rg = sig.get("regime", {})
    if rg and rg.get("label"):
        lines.insert(4, f"环境: {rg.get('emoji', '')} {rg['label']}")

    lines.append("")
    lines.append("--- 距离触发 ---")
    for key, d in sig["distance_to_trigger"].items():
        if d["triggered"]:
            lines.append(f"{d['name']}: 已触发")
        elif d.get("trigger_price") is not None:
            lines.append(f"{d['name']}: 触发价 {d['trigger_price']:.0f} (距当前 {d['pct_away']:+.1f}%)")

    # 历史 Armed 信号表现
    hp = sig.get("hist_perf", {})
    if hp and hp.get("n_signals", 0) > 0:
        lines.append("")
        lines.append(f"--- 历史信号 ({hp['n_signals']}次, 近3年) ---")
        lines.append(f"13周后: 均值{hp['mean']:+.1f}% 胜率{hp['win_rate']:.0%}")

    content = "\n".join(lines)

    # 根据警报级别决定是否推送
    level = alert["level"]
    if level == "silent":
        print(f"  Score={score:.1f} [{tier}] [{level}] — 静默, 不推送")
        return

    # YELLOW 或 RED: 推送
    emoji = "🔴" if level == "red" else "🟡"
    tier_label = tier.replace("_", " ").title()
    title = f"{emoji} 医药板块{'ARMED!' if level == 'red' else '近触发预警'} [{tier_label}] (Score={score:.1f})"

    print(f"  [{level.upper()}] {alert['message']}")
    print(f"  推送标题: {title}")

    if not dry_run:
        sent = push(title, content)
        if sent:
            print("  推送已发送")
        else:
            print("  未配置推送渠道 (桌面通知需要 plyer, 远程推送需设置 PUSH_KEY 等环境变量)")
    else:
        print("  [dry-run] 跳过推送")
        print(content)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    test = "--test" in sys.argv
    run(dry_run=dry, test_push=test)
