# -*- coding: utf-8 -*-
"""L-C 因子库：因子定义（单一来源）+ 打分合成。

预注册因子池（docs/strategy_proposal.md §4 L-C，方向 = 因子值越高越看多）。
全部基于 align_daily 的日频表计算，只用截至当日的可得信息（防前视）。
入选因子由 scripts/screen_factors.py 三漏斗在训练段筛出，写入冻结配置
src/models/model_config_agri.json；Score = 入选因子滚动分位打分的等权平均。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.indicators_agri import pctile_score, rsi_wilder, rolling_skew

# 因子名 → (方向系数, 描述)。方向系数 +1：值越高越看多；-1：值越低越看多。
FACTOR_DEFS: dict[str, tuple[int, str]] = {
    # 反转（主力）
    "rev_10d":       (-1, "10日累计跌幅（超跌为正贡献）"),
    "rev_20d":       (-1, "20日累计跌幅"),
    "rsi_14":        (-1, "RSI(14) 超卖"),
    "dist_low_20d":  (-1, "距 20 日新低的距离"),
    "skew_13w":      (-1, "13 周收益偏度（左尾恐慌）"),
    # 趋势（辅助/卖出）
    "ma20_bias":     (+1, "20 日均线乖离"),
    "ma60_bias":     (+1, "60 日均线乖离"),
    "mom_120d":      (+1, "120 日动量"),
    # 估值/分位
    "px_pctile_5y":  (-1, "价格 5 年分位（冰点为正贡献）"),
    "rel_strength_60d": (-1, "相对沪深300 60 日强弱（弱势反转）"),
    # 波动/风险
    "vol_pctile_20d": (+1, "20 日波动率 500 日分位（恐慌期反转溢价）"),
    "vol_ratio":     (+1, "短/长波动率比"),
    # 行为/资金
    "amount_pctile_120d": (-1, "成交额 120 日分位（低换手溢价，CH-3 PMO 思想）"),
    "margin_chg_20d": (+1, "融资余额 20 日变化分位"),
    "margin_diverge_13w": (+1, "价格 13 周新低 + 融资 4 周逆势加仓（0/1）"),
    # 商品/基本面
    "hog_mom_60d":   (+1, "猪价指数 60 日动量（景气改善）"),
    "corn_mom_60d":  (-1, "玉米期货 60 日动量（饲料成本，越高越利空）"),
    "meal_mom_60d":  (-1, "豆粕期货 60 日动量"),
    "hog_fut_mom_60d": (+1, "生猪期货 60 日动量（2021 起）"),
    # 宏观
    "cpi_ppi_gap":   (+1, "CPI-PPI 剪刀差"),
    "m1_m2_gap":     (+1, "M1-M2 剪刀差（流动性活化）"),
    "rate_chg_60d":  (-1, "10Y 国债收益率 60 日变化（利率上行利空）"),
    # 季节性
    "halloween":     (+1, "Halloween：11-4 月为 1（Bouman-Jacobsen 2002）"),
    # 大盘环境
    "hs300_ma200":   (+1, "沪深300 在 200 日均线上（1/0）"),
    # 气候/外生（Atems 等 2020：ENSO 对农业股有非对称影响）
    "enso_nino":     (+1, "厄尔尼诺活跃（ONI≥+0.5，农产品涨价预期）"),
    "enso_nina":     (+1, "拉尼娜活跃（ONI≤−0.5，全球减产预期）"),
    # 生猪产业链（蛛网逻辑：猪粮比低=深亏=周期谷）
    "hog_corn_ratio": (-1, "猪粮比代理（生猪指数/玉米期货，越低越接近周期谷）"),
}


def compute_factors(daily: pd.DataFrame) -> pd.DataFrame:
    """计算全部预注册因子。返回与 daily 同索引的因子矩阵。"""
    px = daily["close"]
    ret = px.pct_change()
    f = pd.DataFrame(index=daily.index)

    # 反转
    f["rev_10d"] = px.pct_change(10)
    f["rev_20d"] = px.pct_change(20)
    f["rsi_14"] = rsi_wilder(px, 14)
    low20 = px.rolling(20).min()
    f["dist_low_20d"] = px / low20 - 1.0
    wk = px.resample("W-FRI").last().dropna()
    wk_ret = wk.pct_change()
    skew_w = rolling_skew(wk_ret, 13)
    skew_w.index = skew_w.index + pd.Timedelta(days=3)  # 周五→下周一，防前视
    f["skew_13w"] = skew_w.reindex(daily.index).ffill()

    # 趋势
    f["ma20_bias"] = px / px.rolling(20).mean() - 1.0
    f["ma60_bias"] = px / px.rolling(60).mean() - 1.0
    f["mom_120d"] = px.pct_change(120)

    # 估值/分位
    f["px_pctile_5y"] = px.rolling(1250, min_periods=500).rank(pct=True)
    ra = ret
    rm = daily["hs300_close"].pct_change()
    f["rel_strength_60d"] = (1 + ra).rolling(60).apply(np.prod, raw=True) / (
        (1 + rm).rolling(60).apply(np.prod, raw=True)
    ) - 1.0

    # 波动/风险
    vol20 = ra.rolling(20).std()
    f["vol_pctile_20d"] = vol20.rolling(500, min_periods=250).rank(pct=True)
    f["vol_ratio"] = vol20 / ra.rolling(120).std()

    # 行为/资金
    f["amount_pctile_120d"] = daily["amount"].rolling(120, min_periods=60).rank(pct=True)
    mg_chg = daily["margin_balance"].pct_change(20)
    f["margin_chg_20d"] = mg_chg.rolling(500, min_periods=250).rank(pct=True)
    px_13w_low = px.rolling(65).min()
    mg_4w_up = daily["margin_balance"] > daily["margin_balance"].shift(20)
    f["margin_diverge_13w"] = ((px <= px_13w_low * 1.001) & mg_4w_up).astype(float)

    # 商品/基本面
    hog = daily["hog_week"]
    f["hog_mom_60d"] = hog.pct_change(60)
    f["corn_mom_60d"] = daily["corn_close"].pct_change(60)
    f["meal_mom_60d"] = daily["meal_close"].pct_change(60)
    f["hog_fut_mom_60d"] = daily["hog_fut_close"].pct_change(60)

    # 宏观
    f["cpi_ppi_gap"] = daily["cpi_yoy"] - daily["ppi_yoy"]
    f["m1_m2_gap"] = daily["m1_yoy"] - daily["m2_yoy"]
    f["rate_chg_60d"] = daily["rate_10y"].diff(60)

    # 季节性 / 大盘环境
    f["halloween"] = daily.index.month.isin([11, 12, 1, 2, 3, 4]).astype(float)
    hs = daily["hs300_close"]
    f["hs300_ma200"] = (hs > hs.rolling(200).mean()).astype(float).where(hs.notna())

    # 气候/外生（NOAA ONI，按可得日对齐）
    oni = daily["oni"]
    f["enso_nino"] = (oni >= 0.5).astype(float).where(oni.notna())
    f["enso_nina"] = (oni <= -0.5).astype(float).where(oni.notna())

    # 生猪产业链（猪粮比代理；2015 起有生猪指数，样本量由漏斗1把关）
    f["hog_corn_ratio"] = daily["hog_week"] / daily["corn_close"]

    # 方向统一：值越大越看多
    for name, (direction, _) in FACTOR_DEFS.items():
        f[name] = f[name] * direction
    return f


def composite_score(factors: pd.DataFrame, selected: list[str],
                    weights: dict[str, float] | None = None) -> pd.Series:
    """入选因子 → 滚动分位打分（0-100）→ 等权/权重平均。缺失因子按剩余因子均值。"""
    scores = []
    w = weights or {}
    for name in selected:
        s = factors[name]
        sc = pctile_score(s, window=1250, min_periods=500)
        scores.append((sc, w.get(name, 1.0)))
    total_w = sum(weight for _, weight in scores)
    if not scores or total_w == 0:
        return pd.Series(np.nan, index=factors.index)
    acc = sum(sc.fillna(50.0) * weight for sc, weight in scores)
    return (acc / total_w).round(1)
