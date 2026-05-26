"""
상승 vs 하락 종목 OOS 패턴 분석
==============================
parquet 시그널에서 90일 보유 winner (+10% 이상) vs loser (-5% 이하)
를 분리하고, 각 그룹의 시그널 시점 지표 분포 차이를 본다.

목표: winner를 더 잘 잡고 loser를 회피하는 차별화 지표 발견.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def main():
    df = pd.read_parquet(ROOT / "results" / "history_signals_combined.parquet")
    # 시총 500위 + 시장필터 + 디폴트 필터
    f = df[
        (df["marcap"] >= 5.466e11) & df["kospi_above"] &
        (df["value_eok"] >= 50) &
        (df["ret_1d"] >= 0.07) & (df["ret_1d"] <= 0.29) &
        (df["ret_20d"] >= 0.10) &
        (df["bb_width"] >= 0.15) & (df["env_ma60"] >= 0.05)
    ].copy()
    f = f[f["ret_d90"].notna()]
    print(f"디폴트 필터 통과 시그널 (90일 forward 있는 것만): {len(f):,}건\n")

    # 90일 보유 결과로 분류
    winners = f[f["ret_d90"] >= 0.10]       # +10%+
    losers = f[f["ret_d90"] <= -0.05]        # -5%-
    neutral = f[(f["ret_d90"] > -0.05) & (f["ret_d90"] < 0.10)]
    print(f"  Winner (90일 +10%↑): {len(winners):,} ({len(winners)/len(f)*100:.1f}%)")
    print(f"  Neutral: {len(neutral):,} ({len(neutral)/len(f)*100:.1f}%)")
    print(f"  Loser (90일 -5%↓): {len(losers):,} ({len(losers)/len(f)*100:.1f}%)")
    print()

    # 지표별 winner vs loser 평균 비교
    indicators = ["similarity", "ret_1d", "ret_20d", "value_eok", "vol_ratio",
                   "rsi", "bb_width", "env_ma20", "env_ma60", "close_to_high"]

    print(f"{'지표':<18}{'Winner 평균':>14}{'Loser 평균':>14}{'격차':>12}{'권장 방향':>14}")
    print("-" * 75)
    findings = []
    for col in indicators:
        w_mean = winners[col].mean()
        l_mean = losers[col].mean()
        diff = w_mean - l_mean
        pct_diff = (diff / abs(l_mean) * 100) if l_mean != 0 else 0
        direction = "↑ 높을수록 winner" if diff > 0 else "↓ 낮을수록 winner"
        findings.append({
            "indicator": col,
            "winner_mean": float(w_mean),
            "loser_mean": float(l_mean),
            "diff": float(diff),
            "pct_diff": float(pct_diff),
            "direction": direction,
        })
        print(f"{col:<18}{w_mean:>14.3f}{l_mean:>14.3f}{diff:>+11.3f}  {direction:>12}")

    # 차이 큰 순으로 — 유의미한 지표
    print(f"\n=== 차별화 강한 지표 top 5 (|격차/loser_mean| 큰 순) ===")
    findings_sorted = sorted(findings, key=lambda x: abs(x["pct_diff"]), reverse=True)
    for r in findings_sorted[:5]:
        print(f"  {r['indicator']:<18} winner={r['winner_mean']:.3f}, "
              f"loser={r['loser_mean']:.3f}, {r['direction']} (격차 {r['pct_diff']:+.0f}%)")

    pd.DataFrame(findings_sorted).to_csv(
        ROOT / "results" / "winners_losers_analysis.csv", index=False)

    # 추가: 5분위 cut으로 winner rate 측정
    print(f"\n=== 각 지표 5분위(Q5=상위)별 winner 비율 ===")
    print(f"{'지표':<18}{'Q1 winner%':>12}{'Q5 winner%':>12}{'Q5-Q1':>10}")
    print("-" * 65)
    bucket_rows = []
    for col in indicators:
        try:
            f["bucket"] = pd.qcut(f[col], 5, labels=[1,2,3,4,5], duplicates="drop")
            q1 = f[f["bucket"] == 1]
            q5 = f[f["bucket"] == 5]
            q1_rate = (q1["ret_d90"] >= 0.10).mean() * 100
            q5_rate = (q5["ret_d90"] >= 0.10).mean() * 100
            print(f"{col:<18}{q1_rate:>11.1f}%{q5_rate:>11.1f}%{q5_rate-q1_rate:>+9.1f}%")
            bucket_rows.append({"indicator": col, "q1_win": q1_rate, "q5_win": q5_rate,
                               "diff": q5_rate - q1_rate})
        except Exception as e:
            print(f"{col:<18} err: {e}")
    pd.DataFrame(bucket_rows).to_csv(
        ROOT / "results" / "winner_rate_by_quintile.csv", index=False)

    # 손실 회피 시뮬: 특정 지표 threshold 적용 시 loser 비율 감소량
    print(f"\n=== 손실 회피 시뮬레이션 (90일 -5%↓ loser 비율 줄이기) ===")
    base_loser_rate = (f["ret_d90"] <= -0.05).mean() * 100
    base_winner_rate = (f["ret_d90"] >= 0.10).mean() * 100
    print(f"  베이스 (필터 없음): loser {base_loser_rate:.1f}% / winner {base_winner_rate:.1f}%")

    # 시도: 차별화 강한 지표로 cut
    for col, threshold_pct in [("similarity", 0.7), ("env_ma60", 0.15),
                                  ("bb_width", 0.25), ("ret_20d", 0.2),
                                  ("value_eok", 100)]:
        sub = f[f[col] >= threshold_pct]
        if len(sub) < 100:
            continue
        l = (sub["ret_d90"] <= -0.05).mean() * 100
        w = (sub["ret_d90"] >= 0.10).mean() * 100
        print(f"  {col} ≥ {threshold_pct}: n={len(sub):,}, "
              f"loser {l:.1f}% (Δ{l-base_loser_rate:+.1f}%p), "
              f"winner {w:.1f}% (Δ{w-base_winner_rate:+.1f}%p)")


if __name__ == "__main__":
    main()
