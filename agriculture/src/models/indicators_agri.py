# -*- coding: utf-8 -*-
"""共享技术指标（农业项目本地实现，避免跨项目依赖）。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI。"""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def rolling_skew(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window, min_periods=max(10, window // 2)).skew()


def pct_rank(s: pd.Series, window: int, min_periods: int) -> pd.Series:
    """滚动分位（当前值在过去 window 期内的分位，0~1）。"""
    return s.rolling(window, min_periods=min_periods).apply(
        lambda a: (a[-1] >= a).mean(), raw=True
    )


def pctile_score(s: pd.Series, window: int = 1250, min_periods: int = 500) -> pd.Series:
    """因子 → 0~100 分：当前值在滚动窗口内的百分位 ×100。"""
    return (pct_rank(s, window, min_periods) * 100).round(1)
