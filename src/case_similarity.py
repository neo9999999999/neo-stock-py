"""
사례 유사도 기반 시그널 엔진 (v3)
==============================
사례 39개의 통계적 프로파일을 추출하고,
신규 시그널 후보를 사례 프로파일과의 유사도로 점수화.

핵심:
- 사례의 25~75% 분위수를 "핵심 영역"으로 정의
- 신규 종목이 사례의 평균 ± σ 내에 있는 지표 개수 카운트
- 사례 유사도 점수 > 임계치인 종목만 추천
"""


from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Dict

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CaseProfile:
    """사례 39개의 통계적 프로파일."""
    # 각 지표의 (평균, 표준편차, 25분위, 75분위, 10분위, 90분위)
    indicators: Dict = field(default_factory=dict)

    @classmethod
    def from_cases(cls, cases_df: pd.DataFrame) -> "CaseProfile":
        ind_cols = [
            "ret_1d", "ret_5d", "ret_20d",
            "value_eok", "value_ratio_60d",
            "volume_ratio_60d",
            "close_to_day_high", "close_to_high60",
            "rsi_14",
        ]
        indicators = {}
        for col in ind_cols:
            if col not in cases_df.columns:
                continue
            vals = cases_df[col].dropna()
            indicators[col] = {
                "mean": float(vals.mean()),
                "median": float(vals.median()),
                "std": float(vals.std()),
                "q10": float(vals.quantile(0.10)),
                "q25": float(vals.quantile(0.25)),
                "q75": float(vals.quantile(0.75)),
                "q90": float(vals.quantile(0.90)),
                "min": float(vals.min()),
                "max": float(vals.max()),
            }
        return cls(indicators=indicators)


def compute_similarity(row, profile, strict=False):
    """신규 시그널 row가 사례 프로파일과 얼마나 유사한가.

    각 지표가 사례의 [q25, q75] 핵심 영역에 들면 1점,
    [q10, q90] 영역에 들면 0.5점, 그 외 0점.
    strict=True면 [q25, q75]만 인정.

    반환: (총점, 지표별 점수 dict)
    """
    scores = {}
    total = 0
    n_indicators = len(profile.indicators)

    for col, prof in profile.indicators.items():
        val = row.get(col)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            scores[col] = 0
            continue
        if prof["q25"] <= val <= prof["q75"]:
            scores[col] = 1.0
        elif not strict and prof["q10"] <= val <= prof["q90"]:
            scores[col] = 0.5
        else:
            scores[col] = 0.0
        total += scores[col]

    return total / n_indicators if n_indicators else 0, scores


def _load_cases(combined: bool = True) -> pd.DataFrame:
    """combined=True: 사용자 39개 + 마이닝 12,759개 (cases_combined.csv).
    combined=False: 사용자 큐레이션 39개만 (cases_analysis.csv).
    """
    if combined:
        f = ROOT / "results" / "cases_combined.csv"
        if f.exists():
            return pd.read_csv(f, dtype={"code": str})
    return pd.read_csv(ROOT / "results" / "cases_analysis.csv",
                        dtype={"code": str})


def build_profile(combined: bool = True,
                   asof_date: Optional[str] = None) -> CaseProfile:
    """사례 프로파일 빌드.

    Args:
        combined: True면 39개 + 마이닝 12,759개 합본 사용.
        asof_date: 'YYYY-MM-DD' 형식. 이 날짜 이전 buy_date 사례만 사용.
                   walkforward OOS용 — 시그널 일자 시점에 알 수 없는 미래 사례
                   를 profile 빌드에 쓰지 않음.
    """
    cases_df = _load_cases(combined=combined)
    if asof_date is not None and "buy_date" in cases_df.columns:
        cutoff = pd.to_datetime(asof_date)
        bd = pd.to_datetime(cases_df["buy_date"].astype(str), format="%Y%m%d")
        cases_df = cases_df[bd < cutoff].copy()
    return CaseProfile.from_cases(cases_df)


def case_count(combined: bool = True, asof_date: Optional[str] = None) -> int:
    """현 시점 사례 개수 — UI에 노출."""
    cases_df = _load_cases(combined=combined)
    if asof_date is not None and "buy_date" in cases_df.columns:
        cutoff = pd.to_datetime(asof_date)
        bd = pd.to_datetime(cases_df["buy_date"].astype(str), format="%Y%m%d")
        cases_df = cases_df[bd < cutoff]
    return len(cases_df)


if __name__ == "__main__":
    profile = build_profile()
    print("=== 사례 프로파일 (39개 종목 통계) ===\n")
    for col, prof in profile.indicators.items():
        print(f"\n{col}:")
        for k, v in prof.items():
            if col.startswith("ret_") or "ratio" in col or col.startswith("close_to"):
                print(f"  {k}: {v*100:+.2f}%" if abs(v) < 10 else f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v:.2f}")
