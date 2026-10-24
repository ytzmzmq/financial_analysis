# -*- coding: utf-8 -*-
"""特征流水线：数据 → 日频主表 → 条件变量 → 因子矩阵（训练与追踪共用）。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data_fetcher.akshare_source import align_daily, load_core_data
from src.models.cycle_regime import (
    cycle_phase_asof, expand_phase_to_daily, fit_weekly_regime, regime_recession_prob,
)


def _completed_months(monthly: pd.Series) -> pd.Series:
    """剔除进行中的当月（月末戳 > 今天），保证"当月内只用最近已实现月份"。

    旧实现把当月部分数据也喂进 HP，月内值随每日行情漂移且其全样本口径构成前视；
    见 MODEL_AUDIT_2026-10-24.md。月末日当天（收盘后）当月即视为已实现。
    """
    return monthly[monthly.index <= pd.Timestamp.now().normalize()]


def build_features(data: dict[str, pd.DataFrame],
                   regime_params: dict | None = None) -> dict:
    """从 load_core_data 的输出构建全部特征。

    regime_params 为空时在训练段重新拟合（仅校准脚本使用）；
    tracker 传入冻结参数（model_config_agri.json）以保证与校准一致。
    """
    calendar = data["agri"].index
    daily = align_daily(data, calendar)

    if regime_params is None:
        regime_params = fit_weekly_regime(data["agri"]["close"])
    recession = regime_recession_prob(data["agri"]["close"], regime_params)

    monthly_log = _completed_months(np.log(data["agri"]["close"]).resample("ME").last().dropna())
    agri_phase = cycle_phase_asof(monthly_log)
    agri_phase_daily = expand_phase_to_daily(agri_phase, calendar)

    hog_monthly = _completed_months(np.log(data["hog_week"]["value"]).resample("ME").last().dropna())
    hog_phase = cycle_phase_asof(hog_monthly, train_end=pd.Timestamp("2021-12-31"))
    hog_phase_daily = expand_phase_to_daily(hog_phase, calendar)

    from src.models.streak_stats import build_conditions
    cond = build_conditions(daily, recession, agri_phase_daily, hog_phase_daily)
    factors = None
    try:
        from src.models.factor_library import compute_factors
        factors = compute_factors(daily)
    except Exception as e:  # noqa: BLE001
        # 因子计算失败不阻断周期层输出（tracker 降级运行）
        import warnings
        warnings.warn(f"factor compute failed: {e}")

    return {
        "daily": daily,
        "cond": cond,
        "factors": factors,
        "recession_prob": recession,
        "agri_phase": agri_phase,
        "agri_phase_daily": agri_phase_daily,
        "hog_phase": hog_phase,
        "hog_phase_daily": hog_phase_daily,
        "regime_params": regime_params,
    }


def load_local_features(use_cache_days: int | None = None) -> dict:
    """便捷入口：在线/缓存拉数 → 特征。"""
    return build_features(load_core_data(use_cache_days))
