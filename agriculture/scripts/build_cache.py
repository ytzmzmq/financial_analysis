# -*- coding: utf-8 -*-
"""M1：构建本地数据缓存（数据源可用性 + 覆盖区间报告）。

用法: python scripts/build_cache.py   （在 agriculture/ 目录下）
输出: data/raw/cache/*.csv + 覆盖区间摘要（stdout）
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # agriculture/
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.data_fetcher.akshare_source import load_core_data, align_daily  # noqa: E402


def main() -> None:
    data = load_core_data(use_cache_days=None)
    print(f"{'名称':<10}{'行数':>8}  起止")
    for name, df in data.items():
        print(f"{name:<10}{len(df):>8}  {df.index.min().date()} → {df.index.max().date()}")

    cal = data["agri"].index
    daily = align_daily(data, cal)
    print(f"\n对齐后主表: {len(daily)} 行 × {daily.shape[1]} 列")
    print("NaN 占比（前 3 年内应为 0 或接近 0，早于数据源起点的高属于正常）:")
    na = daily.isna().mean().round(3).sort_values(ascending=False)
    print(na.head(8).to_string())


if __name__ == "__main__":
    main()
