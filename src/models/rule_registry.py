"""
中央规则注册表 — 因子定义、模型配置、统一信号判定入口。

所有跟规则有关的东西（因子定义、权重、阈值、层级逻辑、展示文案）
都集中在这里。消费方（tracker / server / monthly_audit）调用
evaluate_signal() 拿到统一结果，不再自己理解模型。

用法:
    from src.models.rule_registry import (
        evaluate_signal, evaluate_signal_history,
        MODEL_CONFIGS, RULE_DEFS, ACTIVE_MODEL_VERSION, SignalResult
    )
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════
# 1. RULE_DEFS — 因子定义（单一来源）
# ═══════════════════════════════════════════

RULE_DEFS: dict[str, dict] = {
    "L1_rsi_30": {
        "dimension": "Liquidity",
        "indicator": "rsi_wilder",
        "params": {"period": 14},
        "condition": "rsi < 30",
        "pool_column": "L1_rsi_30",
        "display_text": "L1:RSI超卖({weight}分)",
        "description": "RSI(14) < 30, 量价冰点",
        "threshold_display": "< 30",
        "raw_value_key": "rsi",
    },
    "M1_skew_neg": {
        "dimension": "Momentum",
        "indicator": "skew_13w",
        "params": {"window": 13},
        "condition": "skew < -1.5",
        "pool_column": "M1_skew_neg",
        "display_text": "M1:偏度异常({weight}分)",
        "description": "13周偏度 < -1.5, 极端左尾恐慌",
        "threshold_display": "< -1.5",
        "raw_value_key": "skew_13w",
    },
    "S3_margin_diverge": {
        "dimension": "SmartMoney",
        "indicator": "margin_diverge",
        "params": {"price_window": 13, "margin_window": 4},
        "condition": "price_13w_low AND margin_4w_up",
        "pool_column": "S3_margin_diverge",
        "display_text": "S3:融资背离({weight}分)",
        "description": "价格13周新低 + 融资4周逆势加仓",
        "threshold_display": "价新低+融资增",
        "raw_value_key": None,
    },
    "V1_price_5y_low": {
        "dimension": "Valuation",
        "indicator": "price_pct_rank",
        "params": {"window": 260, "min_periods": 52, "threshold": 0.15},
        "condition": "pct_rank < 15%",
        "pool_column": "V1_price_5y_low",
        "display_text": "V1:估值冰点({weight}分)",
        "description": "5年价格分位 < 15%",
        "threshold_display": "< 15%分位",
        "raw_value_key": "val_pct_5y",
    },
    "S4_north_diverge": {
        "dimension": "SmartMoney",
        "indicator": "north_diverge",
        "params": {"price_window": 13, "north_window": 4},
        "condition": "price_13w_low AND north_4w_net_positive",
        "pool_column": "S4_north_diverge",
        "display_text": "S4:北向背离({weight}分)",
        "description": "价格13周新低 + 北向4周净流入",
        "threshold_display": "价新低+北向流入",
        "raw_value_key": None,
    },
    "E1_market_bear": {
        "dimension": "External",
        "indicator": "market_regime",
        "params": {"ma_window": 200},
        "condition": "HS300 < 200日均线",
        "pool_column": "E1_market_bear",
        "display_text": "E1:大盘熊市({weight}分)",
        "description": "沪深300低于200日均线, 系统性恐慌",
        "threshold_display": "< MA200",
        "raw_value_key": None,
    },
    "E2_m2_accel": {
        "dimension": "External",
        "indicator": "m2_growth",
        "params": {"ma_window": 13},
        "condition": "M2增速 > 13周均值",
        "pool_column": "E2_m2_accel",
        "display_text": "E2:M2加速({weight}分)",
        "description": "M2同比增速超过近13周均值, 货币宽松",
        "threshold_display": "> MA13",
        "raw_value_key": None,
    },
}


# ═══════════════════════════════════════════
# 2. MODEL_CONFIGS — 版本化模型配置
# ═══════════════════════════════════════════

MODEL_CONFIGS: dict[str, dict] = {
    "V5.1": {
        "factors": {
            "M1_skew_neg": 4.5,
            "S3_margin_diverge": 3.0,
            "V1_price_5y_low": 2.5,
        },
        "armed_rule": "score_threshold",
        "score_threshold": 3.5,
        "n_factors_min": None,
        "max_score": 10.0,
        "tier_rule": None,
        "description": "3因子评分卡, 阈值3.5",
    },
    "V5.2": {
        "factors": {
            "L1_rsi_30": 3.0,
            "M1_skew_neg": 2.5,
            "S3_margin_diverge": 2.0,
            "V1_price_5y_low": 2.0,
        },
        "armed_rule": "n_factors_tier",
        "score_threshold": None,
        "n_factors_min": 2,
        "max_score": 9.5,
        "tier_rule": "v52_tiers",
        "tier_definitions": {
            "strong_armed": "n_factors >= 3",
            "standard_armed": "n_factors >= 2 AND (L1 OR M1)",
            "weak_armed": "n_factors >= 2 AND only S3+V1",
            "hold": "n_factors < 2",
        },
        "description": "4因子+n_factors>=2准入+分级, 总分9.5",
    },
}

# 切换模型版本：只改这一行
ACTIVE_MODEL_VERSION: str = "V5.2"


# ═══════════════════════════════════════════
# 3. SignalResult — 统一结果对象
# ═══════════════════════════════════════════

@dataclass
class SignalResult:
    """evaluate_signal() 的统一返回值。消费方只用这个。"""
    model_version: str
    date: str
    score: float
    max_score: float
    n_factors_triggered: int
    factors: dict             # {"M1_skew_neg": {"triggered": True, "weight": 2.5, "raw_value": -1.8}, ...}
    is_armed: bool
    signal_tier: str          # "hold" | "weak_armed" | "standard_armed" | "strong_armed"
    l1_triggered: bool
    rules_status: list        # 兼容当前 tracker/server 的展示格式
    factor_snapshot: dict     # JSON 可序列化快照，供 DB 存储
    # 以下字段用于 display_df 构建
    price: float = 0.0
    rsi: float = 0.0
    drawdown_13w: float = 0.0
    val_pct_5y: float = 0.0
    skew_13w: float = 0.0
    vol_annual: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════
# 4. evaluate_signal() — 单一判定入口
# ═══════════════════════════════════════════

def evaluate_signal(
    model_version: str,
    med_w: pd.Series,
    margin_w: Optional[pd.Series] = None,
    vol_w: Optional[pd.Series] = None,
    pool: Optional[pd.DataFrame] = None,
    north_w: Optional[pd.Series] = None,
    hs300_w: Optional[pd.Series] = None,
    m2_w: Optional[pd.Series] = None,
) -> SignalResult:
    """
    统一信号判定入口。所有地方都不要自己算 Armed，统一走这个函数。

    Args:
        model_version: "V5.1" 或 "V5.2"
        med_w: 周频收盘价 (DatetimeIndex)
        margin_w: 周频融资余额 (T+1 已 shift)
        vol_w: 周频成交量 (可选)
        pool: 预计算的因子池 (可选，不传则内部构建)

    Returns:
        SignalResult — 包含 score, armed, tier, rules_status, factor_snapshot 等全部字段
    """
    from src.models.factor_optimizer import build_factor_pool
    from src.models.indicators import rsi_wilder, macd_histogram

    config = MODEL_CONFIGS[model_version]
    factors_config = config["factors"]

    # 构建或复用因子池
    if pool is None:
        pool = build_factor_pool(med_w, vol_w=vol_w, margin_w=margin_w,
                                 north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)

    latest = med_w.iloc[-1]
    date_str = str(med_w.index[-1].date())

    # 计算原始指标（用于展示和 snapshot）
    rsi_val = float(rsi_wilder(med_w, 14).iloc[-1])
    skew_val = float(med_w.pct_change().rolling(13).skew().iloc[-1])
    val_pct = float(med_w.rolling(260, min_periods=52).rank(pct=True).iloc[-1] * 100)
    drawdown = float((med_w.iloc[-1] / med_w.rolling(13).max().iloc[-1] - 1) * 100)
    vol_ann = float(med_w.pct_change().rolling(13).std().iloc[-1] * np.sqrt(52) * 100)

    # 计算 score + 因子触发状态
    score = 0.0
    n_factors = 0
    triggered_list = []
    factors_detail = {}
    factor_snapshot = {}

    raw_values = {
        "rsi": rsi_val,
        "skew_13w": skew_val,
        "val_pct_5y": val_pct,
    }

    for factor_name, weight in factors_config.items():
        pool_col = RULE_DEFS[factor_name]["pool_column"]
        if pool_col in pool.columns:
            is_triggered = bool(pool[factor_name].iloc[-1] == 1)
        else:
            is_triggered = False

        raw_key = RULE_DEFS[factor_name].get("raw_value_key")
        raw_val = raw_values.get(raw_key) if raw_key else None

        if is_triggered:
            score += weight
            n_factors += 1
            triggered_list.append(factor_name)

        factors_detail[factor_name] = {
            "triggered": is_triggered,
            "weight": weight,
            "raw_value": round(raw_val, 2) if raw_val is not None else None,
        }
        factor_snapshot[factor_name] = {
            "triggered": is_triggered,
            "weight": weight,
            "raw_value": round(raw_val, 2) if raw_val is not None else None,
        }

    score = round(score, 1)

    # 判定 Armed + Tier
    armed_rule = config["armed_rule"]
    if armed_rule == "score_threshold":
        is_armed = score >= config["score_threshold"]
        signal_tier = "armed" if is_armed else "hold"
    elif armed_rule == "n_factors_tier":
        is_armed = n_factors >= config["n_factors_min"]
        signal_tier = _compute_tier(triggered_list, config)
    else:
        is_armed = False
        signal_tier = "hold"

    l1_triggered = "L1_rsi_30" in triggered_list

    # 构建展示用 rules_status（兼容当前 tracker/server 格式）
    rules_status = _build_rules_status(factors_config, factors_detail)

    return SignalResult(
        model_version=model_version,
        date=date_str,
        score=score,
        max_score=config["max_score"],
        n_factors_triggered=n_factors,
        factors=factors_detail,
        is_armed=is_armed,
        signal_tier=signal_tier,
        l1_triggered=l1_triggered,
        rules_status=rules_status,
        factor_snapshot=factor_snapshot,
        price=round(float(latest), 2),
        rsi=round(rsi_val, 1),
        drawdown_13w=round(drawdown, 1),
        val_pct_5y=round(val_pct, 1),
        skew_13w=round(skew_val, 2),
        vol_annual=round(vol_ann, 1),
    )


# ═══════════════════════════════════════════
# 5. evaluate_signal_history() — 历史全量判定
# ═══════════════════════════════════════════

def evaluate_signal_history(
    model_version: str,
    med_w: pd.Series,
    margin_w: Optional[pd.Series] = None,
    vol_w: Optional[pd.Series] = None,
    north_w: Optional[pd.Series] = None,
    hs300_w: Optional[pd.Series] = None,
    m2_w: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    对历史每一周执行 evaluate_signal，返回完整 DataFrame。

    列: price, score, armed, signal_tier, n_factors,
        rule_L1, rule_M1, rule_S3, rule_V1,
        rsi, drawdown_13w, val_pct_5y, skew_13w, vol_annual

    供 monthly_audit 使用。
    """
    from src.models.factor_optimizer import build_factor_pool
    from src.models.indicators import rsi_wilder, macd_histogram

    config = MODEL_CONFIGS[model_version]
    factors_config = config["factors"]

    pool = build_factor_pool(med_w, vol_w=vol_w, margin_w=margin_w,
                             north_w=north_w, hs300_w=hs300_w, m2_w=m2_w)

    df = pd.DataFrame(index=med_w.index)
    df["price"] = med_w
    df["rsi"] = rsi_wilder(med_w, 14)
    df["drawdown_13w"] = (med_w / med_w.rolling(13).max() - 1) * 100
    df["skew_13w"] = med_w.pct_change().rolling(13).skew()
    df["val_pct_5y"] = med_w.rolling(260, min_periods=52).rank(pct=True) * 100
    df["vol_annual"] = med_w.pct_change().rolling(13).std() * np.sqrt(52) * 100

    # 计算 score
    df["score"] = 0.0
    for factor_name, weight in factors_config.items():
        pool_col = RULE_DEFS[factor_name]["pool_column"]
        if pool_col in pool.columns:
            df["score"] += pool[factor_name] * weight
    df["score"] = df["score"].round(1)

    # 每个因子的触发列
    for factor_name in factors_config:
        pool_col = RULE_DEFS[factor_name]["pool_column"]
        col_name = "rule_" + factor_name.split("_")[0]  # rule_L1, rule_M1, rule_S3, rule_V1
        if pool_col in pool.columns:
            df[col_name] = pool[factor_name]
        else:
            df[col_name] = 0

    # n_factors
    rule_cols = [c for c in df.columns if c.startswith("rule_")]
    df["n_factors"] = df[rule_cols].sum(axis=1).astype(int)

    # Armed + Tier 判定
    armed_rule = config["armed_rule"]
    if armed_rule == "score_threshold":
        df["armed"] = (df["score"] >= config["score_threshold"]).astype(int)
        df["signal_tier"] = df["armed"].map({1: "armed", 0: "hold"})
    elif armed_rule == "n_factors_tier":
        df["armed"] = (df["n_factors"] >= config["n_factors_min"]).astype(int)
        # 逐行计算 tier
        tiers = []
        for i in range(len(df)):
            triggered = [
                factor_name for factor_name in factors_config
                if df[f"rule_{factor_name.split('_')[0]}"].iloc[i] == 1
            ]
            tiers.append(_compute_tier(triggered, config))
        df["signal_tier"] = tiers
    else:
        df["armed"] = 0
        df["signal_tier"] = "hold"

    # MACD / 右侧确认（兼容旧代码）
    df["macd_hist"] = macd_histogram(med_w)
    df["macd_stable"] = (df["macd_hist"] >= df["macd_hist"].shift(1)).astype(int)
    df["above_ma2"] = (med_w > med_w.rolling(2).mean()).astype(int)
    df["right_confirm"] = ((df["macd_stable"] == 1) | (df["above_ma2"] == 1)).astype(int)
    df["buy_signal"] = ((df["armed"] == 1) & (df["right_confirm"] == 1)).astype(int)

    return df


# ═══════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════

def _compute_tier(triggered_factors: list[str], config: dict) -> str:
    """
    根据模型配置计算信号层级。

    返回: "hold" | "weak_armed" | "standard_armed" | "strong_armed"

    V5.2 层级规则:
      n_factors >= 3              → strong_armed
      n_factors >= 2 且含 L1/M1  → standard_armed
      n_factors >= 2 且仅 S3+V1  → weak_armed
      n_factors < 2               → hold
    """
    n = len(triggered_factors)
    n_min = config.get("n_factors_min", 2)

    if n < n_min:
        return "hold"
    if n >= 3:
        return "strong_armed"
    # n == 2: 检查是否包含高权重因子
    has_high_weight = any(
        f in ("L1_rsi_30", "M1_skew_neg") for f in triggered_factors
    )
    if has_high_weight:
        return "standard_armed"
    return "weak_armed"


def _build_rules_status(factors_config: dict, factors_detail: dict) -> list[dict]:
    """
    构建兼容当前 tracker/server 展示格式的 rules_status 列表。

    每项: {
        "name": str,        # 如 "L1:RSI超卖(3.0分)"
        "triggered": bool,
        "value": str,       # 当前值（如 "RSI 27.3" 或 "已触发"/"未触发"）
        "threshold": str,   # 阈值描述（如 "< 30"）
        "description": str, # 含义说明
    }
    """
    status = []
    for factor_name, weight in factors_config.items():
        defn = RULE_DEFS[factor_name]
        detail = factors_detail.get(factor_name, {})
        triggered = detail.get("triggered", False)
        raw_val = detail.get("raw_value")

        # 构建显示名
        name = defn["display_text"].replace("{weight}", str(weight))

        # 构建当前值显示
        if raw_val is not None:
            if factor_name == "L1_rsi_30":
                value_str = f"RSI {raw_val:.1f}"
            elif factor_name == "M1_skew_neg":
                value_str = f"偏度{raw_val:.2f}"
            elif factor_name == "V1_price_5y_low":
                value_str = f"{raw_val:.0f}%"
            else:
                value_str = str(raw_val)
        else:
            value_str = "已触发" if triggered else "未触发"

        status.append({
            "name": name,
            "triggered": triggered,
            "value": value_str,
            "threshold": defn["threshold_display"],
            "description": defn["description"],
        })

    return status
