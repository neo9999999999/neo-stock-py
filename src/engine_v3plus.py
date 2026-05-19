"""
v3+ 개선 변종들
==============
v3.1: v3 + 시장 환경 필터 (KOSPI 20일선 위만)
v3.2: v3 + 시장 환경 필터 + 코스피만 (대형주 한정)
v3.3: v3 + 가중 유사도 (사례 표준편차 작은 지표에 가중치)
v3.4: v3 + 이격도 필터 (60일선 대비 +30% 미만 — 과열 회피)
v3.5: v3 + 거래대금 회전율 (시총 대비 거래대금 ≥ 5%)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from case_similarity import build_profile, CaseProfile
from engine_v3 import ParamsV3, add_signals_v3, backtest_v3

ROOT = Path(__file__).resolve().parent.parent


def add_market_filter(sig_data: dict[str, pd.DataFrame],
                       market_df: pd.DataFrame,
                       ma_window: int = 20) -> dict[str, pd.DataFrame]:
    """시장 지수(KOSPI 등)의 N일선 위에서만 signal=True 유지."""
    m = market_df.copy()
    m["market_ma"] = m["close"].rolling(ma_window).mean()
    m["market_above"] = m["close"] > m["market_ma"]
    market_above = m["market_above"]

    out = {}
    for t, df in sig_data.items():
        df2 = df.copy()
        above = market_above.reindex(df2.index, method="ffill")
        df2["signal"] = df2["signal"] & above.fillna(False)
        out[t] = df2
    return out


def add_overheating_filter(sig_data: dict, max_deviation_pct: float = 0.30) -> dict:
    """60일 이평 대비 +max_deviation% 이상은 과열 회피."""
    out = {}
    for t, df in sig_data.items():
        df2 = df.copy()
        if "ma60" not in df2.columns:
            df2["ma60"] = df2["close"].rolling(60).mean()
        deviation = (df2["close"] / df2["ma60"]) - 1
        df2["signal"] = df2["signal"] & (deviation <= max_deviation_pct)
        out[t] = df2
    return out


def add_weighted_similarity(sig_data: dict, profile: CaseProfile,
                              p: ParamsV3) -> dict:
    """가중 유사도: 사례 표준편차 작은(일관성 큰) 지표에 가중치."""
    weights = {}
    for col, prof in profile.indicators.items():
        # CV (변동계수)가 낮을수록 일관성 큼 → 가중치 ↑
        cv = abs(prof["std"]) / (abs(prof["mean"]) + 1e-9)
        weights[col] = 1.0 / (cv + 0.5)   # 0.5 보정
    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    out = {}
    for t, df in sig_data.items():
        df2 = df.copy()
        # 기존 sim_* 컬럼에 가중치 적용
        w_score = pd.Series(0.0, index=df2.index)
        for col, w in weights.items():
            sim_col = f"sim_{col}"
            if sim_col in df2.columns:
                w_score += df2[sim_col].fillna(0) * w
        df2["weighted_similarity"] = w_score
        df2["signal"] = w_score >= p.min_similarity
        out[t] = df2
    return out
