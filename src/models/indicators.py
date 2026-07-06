"""
共享技术指标 — 单一来源，消除重复实现。

所有 RSI / MACD 计算统一从这里导入，
factor_optimizer.py 和 turning_points.py 不再各自维护副本。
"""
import pandas as pd
import numpy as np


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI（指数移动平均变体）。

    使用 EWM alpha=1/period 实现 Wilder 原始平滑方式。
    与 ta-lib 的 RSI(period, type=wilder) 口径一致。
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd_histogram(close: pd.Series, fast: int = 12,
                   slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD 柱状图（双 EMA 差值减去信号线）。

    histogram = EMA(fast) - EMA(slow) - EMA(EMA(fast) - EMA(slow), signal)
    """
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    return (ef - es) - (ef - es).ewm(span=signal, adjust=False).mean()
