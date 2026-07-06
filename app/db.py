"""
信号数据库 — SQLite 持久化存储

用法:
    from app.db import save_signal, get_history, get_latest_score, log_error

V5.2 新增:
    - model_version / signal_tier / n_factors / is_live_signal / factor_snapshot / l1_triggered
    - 幂等迁移 _ensure_column()
    - get_latest_score() 修复为返回 float
"""
import json
import math
import sqlite3
from pathlib import Path

# 数据库文件固定在 data/processed/signals.db（相对于项目根目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _PROJECT_ROOT / "data" / "processed" / "signals.db"


# ═══════════════════════════════════════════
# 幂等迁移
# ═══════════════════════════════════════════

def _ensure_column(conn, table, column, col_type, default=None):
    """如果列不存在则添加（幂等迁移，重复执行不报错）。"""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        default_clause = f"DEFAULT {json.dumps(default)}" if default is not None else ""
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type} {default_clause}")
        conn.commit()
        print(f"[db] 迁移: 新增 {table}.{column} ({col_type})")


def _get_conn():
    """获取数据库连接，首次调用时自动建表 + 迁移旧 CSV 数据 + 幂等扩列"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))

    # 原始建表（V5.1 schema）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            date TEXT PRIMARY KEY,
            score REAL,
            armed INTEGER,
            alert_level TEXT,
            price REAL,
            rsi REAL,
            drawdown_13w REAL,
            val_pct_5y REAL,
            m1_triggered INTEGER,
            s3_triggered INTEGER,
            v1_triggered INTEGER,
            s3_trigger_price REAL,
            v1_trigger_price REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            source TEXT,
            level TEXT,
            message TEXT
        )
    """)
    conn.commit()

    # V5.2 幂等扩列（重复执行安全）
    _ensure_column(conn, "signals", "model_version", "TEXT", "'V5.1'")
    _ensure_column(conn, "signals", "signal_tier", "TEXT", "''")
    _ensure_column(conn, "signals", "n_factors", "INTEGER", "0")
    _ensure_column(conn, "signals", "is_live_signal", "INTEGER", "1")
    _ensure_column(conn, "signals", "factor_snapshot", "TEXT", "'{}'")
    _ensure_column(conn, "signals", "l1_triggered", "INTEGER", "0")

    _migrate_csv(conn)
    return conn


def _migrate_csv(conn):
    """首次运行时，将旧 signal_history.csv 数据导入 SQLite（一次性）"""
    csv_path = DB_PATH.parent / "signal_history.csv"
    if not csv_path.exists():
        return
    try:
        import csv as csv_mod
        with open(csv_path, encoding="utf-8") as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                try:
                    score = float(row.get("score", 0))
                except (ValueError, TypeError):
                    continue
                if math.isnan(score):
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO signals (date, score) VALUES (?, ?)",
                    (row["date"], score),
                )
        conn.commit()
        print(f"[db] 已从 signal_history.csv 迁移历史数据")
    except Exception as e:
        print(f"[db] CSV 迁移跳过: {e}")


# ═══════════════════════════════════════════
# 信号读写
# ═══════════════════════════════════════════

def save_signal(date, score, armed, alert_level, price, rsi,
                drawdown_13w, val_pct_5y, rules_status, distance_to_trigger,
                # V5.2 新增参数（带默认值，向后兼容）
                model_version="V5.1",
                signal_tier="",
                n_factors=0,
                is_live_signal=True,
                factor_snapshot=None,
                l1_triggered=False):
    """
    保存一条信号记录（INSERT OR REPLACE，按日期去重）。

    V5.2 新增参数:
        model_version: "V5.1" 或 "V5.2"
        signal_tier: "hold" / "weak_armed" / "standard_armed" / "strong_armed"
        n_factors: 触发因子数
        is_live_signal: True=tracker 实时运行, False=月审回算
        factor_snapshot: JSON 可序列化 dict
        l1_triggered: L1 是否触发
    """
    conn = _get_conn()

    m1 = next((r["triggered"] for r in rules_status if "M1" in r["name"]), False)
    s3 = next((r["triggered"] for r in rules_status if "S3" in r["name"]), False)
    v1 = next((r["triggered"] for r in rules_status if "V1" in r["name"]), False)

    s3_tp = distance_to_trigger.get("S3", {}).get("trigger_price")
    v1_tp = distance_to_trigger.get("V1", {}).get("trigger_price")

    # NaN → None（SQLite 不接受 NaN）
    if s3_tp is not None and (isinstance(s3_tp, float) and math.isnan(s3_tp)):
        s3_tp = None
    if v1_tp is not None and (isinstance(v1_tp, float) and math.isnan(v1_tp)):
        v1_tp = None

    # factor_snapshot 序列化
    snapshot_json = json.dumps(factor_snapshot, ensure_ascii=False) if factor_snapshot else "{}"

    conn.execute("""
        INSERT OR REPLACE INTO signals
        (date, score, armed, alert_level, price, rsi, drawdown_13w, val_pct_5y,
         m1_triggered, s3_triggered, v1_triggered, s3_trigger_price, v1_trigger_price,
         model_version, signal_tier, n_factors, is_live_signal, factor_snapshot, l1_triggered)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(date),
        round(score, 1),
        int(armed),
        alert_level,
        round(price, 2),
        round(rsi, 1),
        round(drawdown_13w, 1),
        round(val_pct_5y, 1),
        int(m1),
        int(s3),
        int(v1),
        round(s3_tp, 0) if s3_tp else None,
        round(v1_tp, 0) if v1_tp else None,
        model_version,
        signal_tier,
        int(n_factors),
        int(is_live_signal),
        snapshot_json,
        int(l1_triggered),
    ))
    conn.commit()
    conn.close()


def get_history(limit=100):
    """获取历史信号列表（按日期倒序）"""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM signals ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_score():
    """获取最近一条记录的 score（用于 prev_score 计算），无记录返回 0.0"""
    conn = _get_conn()
    row = conn.execute(
        "SELECT score FROM signals ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        return float(row[0])
    return 0.0


def get_live_signals(limit=200):
    """获取 live 信号列表（is_live_signal=1，按日期倒序）"""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM signals WHERE is_live_signal = 1 ORDER BY date DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
# 系统日志
# ═══════════════════════════════════════════

def log_error(source, message, level="error"):
    """写入一条系统日志（error/warning/info）"""
    from datetime import datetime as _dt
    conn = _get_conn()
    conn.execute(
        "INSERT INTO system_log (timestamp, source, level, message) VALUES (?, ?, ?, ?)",
        (_dt.now().strftime("%Y-%m-%d %H:%M:%S"), source, level, message)
    )
    conn.commit()
    conn.close()


def get_recent_errors(hours=24):
    """获取最近 N 小时内的错误/警告日志"""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM system_log WHERE level != 'info' "
        "AND timestamp >= datetime('now', ? || ' hours') "
        "ORDER BY timestamp DESC LIMIT 20",
        (f"-{hours}",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
