# -*- coding: utf-8 -*-
"""补充探测：生猪现货族 + 板块估值 PE/PB（补 2026-09-02 首轮探测缺口）。"""
from __future__ import annotations

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import akshare as ak

REPORT = r"D:\Program\claudecode_data\financial_analysis\agriculture\data\raw\data_probe_20260902.md"
lines: list[str] = ["\n\n---\n\n# 补充探测（生猪现货族 + 估值）\n"]


def probe(name: str, fn, *args, **kwargs):
    lines.append(f"\n## {name}\n")
    try:
        df = fn(*args, **kwargs)
        if df is None or len(df) == 0:
            lines.append("- ❌ 返回空\n")
            return None
        lines.append(f"- ✅ 成功，{len(df)} 行，列：{list(df.columns)[:14]}\n")
        for col in df.columns[:2]:
            lines.append(f"  - `{col}`: {str(df[col].iloc[0])[:14]} → {str(df[col].iloc[-1])[:14]}\n")
        return df
    except Exception as e:  # noqa: BLE001
        lines.append(f"- ❌ 失败：`{type(e).__name__}: {str(e)[:180]}`\n".replace("\n", " "))
        return None


probe("生猪现货价格指数 index_hog_spot_price()", ak.index_hog_spot_price)
probe("生猪现货-搜猪网 spot_hog_soozhu()", ak.spot_hog_soozhu)
probe("三元生猪现货-搜猪网 spot_hog_three_way_soozhu()", ak.spot_hog_three_way_soozhu)
probe("生猪年度趋势-搜猪网 spot_hog_year_trend_soozhu()", ak.spot_hog_year_trend_soozhu)
probe("混合饲料价-搜猪网 spot_mixed_feed_soozhu()", ak.spot_mixed_feed_soozhu)
probe("玉米现货-搜猪网 spot_corn_price_soozhu()", ak.spot_corn_price_soozhu)
probe("生猪核心产能 futures_hog_core()", ak.futures_hog_core)
probe("生猪养殖成本 futures_hog_cost()", ak.futures_hog_cost)
probe("生猪理论出栏供给 futures_hog_supply()", ak.futures_hog_supply)
for sym in ["农林牧渔", "申万农林牧渔"]:
    if probe(f"申万农林牧渔 PE（stock_index_pe_lg symbol={sym}）", ak.stock_index_pe_lg, symbol=sym) is not None:
        break
for sym in ["农林牧渔", "申万农林牧渔"]:
    if probe(f"申万农林牧渔 PB（stock_index_pb_lg symbol={sym}）", ak.stock_index_pb_lg, symbol=sym) is not None:
        break

with open(REPORT, "a", encoding="utf-8") as f:
    f.writelines(lines)
print("\n".join(lines))
