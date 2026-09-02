# -*- coding: utf-8 -*-
"""一次性诊断脚本：探测农业项目所需 akshare 数据源的本地可用性。
结果写入 data_probe_20260902.md。属 M1 里程碑（数据管道）的前置步骤。"""
from __future__ import annotations

import io
import re
import sys
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import akshare as ak
import pandas as pd

REPORT = r"D:\Program\claudecode_data\financial_analysis\agriculture\data\raw\data_probe_20260902.md"
lines: list[str] = ["# akshare 数据源探测报告（2026-09-02）\n"]


def probe(name: str, fn, *args, **kwargs):
    lines.append(f"\n## {name}\n")
    try:
        df = fn(*args, **kwargs)
        if df is None or len(df) == 0:
            lines.append("- ❌ 返回空\n")
            return None
        lines.append(f"- ✅ 成功，{len(df)} 行，列：{list(df.columns)[:12]}\n")
        for col in df.columns[:3]:
            if df[col].dtype == object:
                first = str(df[col].iloc[0])[:12]
                last = str(df[col].iloc[-1])[:12]
                lines.append(f"  - `{col}`: {first} → {last}\n")
                break
        return df
    except Exception as e:  # noqa: BLE001
        msg = str(e)[:200].replace("\n", " ")
        lines.append(f"- ❌ 失败：`{type(e).__name__}: {msg}`\n")
        return None


# 1. 主标的：申万农林牧渔 801010
sw = probe("申万农林牧渔 801010（index_hist_sw）", ak.index_hist_sw, symbol="801010", period="day")
if sw is not None:
    probe("申万农林牧渔 801010 对照：申万医药 801150", ak.index_hist_sw, symbol="801150", period="day")

# 2. 中证农业 000122（基金对应指数）
probe("中证农业 000122（stock_zh_index_daily sh000122）", ak.stock_zh_index_daily, symbol="sh000122")
probe("中证农业 000122（index_zh_a_hist）", ak.index_zh_a_hist, symbol="000122", period="daily")

# 3. 大盘基准
probe("沪深300（stock_zh_index_daily sh000300）", ak.stock_zh_index_daily, symbol="sh000300")

# 4. 生猪相关：动态发现可用函数
lines.append("\n## 生猪/畜牧相关函数发现\n")
pig_funcs = sorted(n for n in dir(ak) if re.search(r"hog|pig|zhu|livestock|pork|nong", n, re.I))
lines.append(f"- 候选：{pig_funcs}\n")

# 5. 生猪期货主力（LH 2021-01 上市）
probe("生猪期货主力 LH0（futures_main_sina）", ak.futures_main_sina, symbol="LH0",
      start_date="20210108", end_date="20260902")

# 6. 饲料：玉米/豆粕期货主力
probe("玉米期货主力 C0（futures_main_sina）", ak.futures_main_sina, symbol="C0",
      start_date="20050104", end_date="20260902")
probe("豆粕期货主力 M0（futures_main_sina）", ak.futures_main_sina, symbol="M0",
      start_date="20050104", end_date="20260902")

# 7. 板块估值（PB/PE 历史分位用）：动态发现
lines.append("\n## 估值相关函数发现\n")
val_funcs = sorted(n for n in dir(ak) if re.search(r"value|pe_lg|pb_lg|legu|danjuan|funddb", n, re.I))
lines.append(f"- 候选：{val_funcs}\n")
for fname in [n for n in val_funcs if "hist" in n][:3]:
    fn = getattr(ak, fname)
    df = None
    try:
        df = fn(symbol="农林牧渔", indicator="市盈率")
    except Exception:
        try:
            df = fn(symbol="农林牧渔")
        except Exception:
            df = None
    if df is not None and len(df):
        lines.append(f"\n### {fname}(农林牧渔) 成功\n")
        lines.append(f"- {len(df)} 行，列：{list(df.columns)[:12]}\n")
        break
    else:
        lines.append(f"- {fname} 不可用\n")

# 8. 宏观（医药项目已验证，确认仍可用）
probe("CPI（macro_china_cpi）", ak.macro_china_cpi)
probe("PPI（macro_china_ppi）", ak.macro_china_ppi)
probe("货币供应 M1/M2（macro_china_money_supply）", ak.macro_china_money_supply)

# 9. 两融（医药 S3 同源）
probe("融资融券汇总（macro_china_market_margin_sh）", ak.macro_china_market_margin_sh)

with open(REPORT, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("\n".join(lines))
print(f"\n[saved] {REPORT}")
