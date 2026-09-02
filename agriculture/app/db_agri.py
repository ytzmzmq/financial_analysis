# -*- coding: utf-8 -*-
"""农业信号 SQLite 存储（独立于医药项目 signals.db）。

表：
- signals：每日信号快照（date 主键，INSERT OR REPLACE 幂等）
- system_log：错误/警告日志（source/level/message）
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

_AGRI_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = _AGRI_ROOT / "data" / "processed" / "signals.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            date TEXT PRIMARY KEY,
            score REAL,
            action TEXT,
            alert_level TEXT,
            price REAL,
            holding INTEGER,
            cycle_score REAL,
            cycle_phase TEXT,
            hog_phase TEXT,
            recession_prob REAL,
            streak_days INTEGER,
            p_up_tomorrow REAL,
            panic_score REAL,
            buy_date TEXT,
            model_version TEXT,
            factor_snapshot TEXT,
            is_live INTEGER
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
    return conn


def save_signal(date: str, score: float, action: str, alert_level: str, price: float,
                holding: bool, cycle_score: float, cycle_phase: str, hog_phase: str,
                recession_prob: float, streak_days: int, p_up_tomorrow: float | None,
                panic_score: float, buy_date: str | None, model_version: str,
                factor_snapshot: dict | None = None, is_live: bool = True) -> None:
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO signals
        (date, score, action, alert_level, price, holding, cycle_score, cycle_phase,
         hog_phase, recession_prob, streak_days, p_up_tomorrow, panic_score,
         buy_date, model_version, factor_snapshot, is_live)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(date), round(float(score), 1), action, alert_level, round(float(price), 2),
        int(holding), round(float(cycle_score), 3), cycle_phase, hog_phase,
        round(float(recession_prob), 3), int(streak_days),
        round(float(p_up_tomorrow), 3) if p_up_tomorrow is not None else None,
        round(float(panic_score), 1), buy_date, model_version,
        json.dumps(factor_snapshot or {}, ensure_ascii=False), int(is_live),
    ))
    conn.commit()
    conn.close()


def get_history(limit: int = 300) -> list[dict]:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM signals ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_position_before(date: str) -> dict | None:
    """date（不含）之前最近一条信号的持仓状态。"""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT holding, buy_date, action FROM signals WHERE date < ? ORDER BY date DESC LIMIT 1",
        (str(date),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def log_error(source: str, message: str, level: str = "error") -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO system_log (timestamp, source, level, message) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), source, level, message[:2000]),
    )
    conn.commit()
    conn.close()
