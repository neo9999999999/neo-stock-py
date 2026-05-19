"""
v3 변종 비교 — 자동 최적 조합 탐색
================================
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from data_loader import business_days, get_index_ohlcv, get_ohlcv
from engine import metrics
from engine_v3 import ParamsV3, add_signals_v3, backtest_v3
from engine_v3plus import (
    add_market_filter, add_overheating_filter, add_weighted_similarity,
)
from case_similarity import build_profile

ROOT = Path(__file__).resolve().parent.parent


def main():
    print("=== v3 변종 비교 ===\n")
    profile = build_profile()

    with open(ROOT / "data" / "universe_final.txt") as f:
        univ = [l.strip() for l in f if l.strip()]

    print(f"유니버스: {len(univ)}개")
    print("OHLCV 로드…")
    t0 = time.time()
    raw = {}
    for t in univ:
        df = get_ohlcv(t, "20200101", "20260517")
        if not df.empty and len(df) >= 80:
            raw[t] = df
    print(f"  → {len(raw)}종목, {time.time()-t0:.1f}s")

    # KOSPI 지수
    print("KOSPI 지수 로드…")
    kospi = get_index_ohlcv("KS11", "20200101", "20260517")
    print(f"  → {len(kospi)}일")

    # 기본 v3 시그널 (한번만)
    print("v3 기본 시그널 계산…")
    t0 = time.time()
    p_base = ParamsV3(min_similarity=0.6, top_k_per_day=5, stop_loss=-0.03)
    sig_v3 = {t: add_signals_v3(df, profile, p_base) for t, df in raw.items()}
    print(f"  → {time.time()-t0:.1f}s")

    bd = business_days("20210101", "20260517")

    # ===== 변종 정의 =====
    variants = {}

    # v3.0 baseline
    variants["v3.0 (기준)"] = sig_v3

    # v3.1 + KOSPI 20일선 필터
    variants["v3.1 (+시장필터)"] = add_market_filter(sig_v3, kospi, ma_window=20)

    # v3.2 + 시장필터 + 과열회피 (60일선 대비 +30% 미만)
    sig_v32 = add_overheating_filter(variants["v3.1 (+시장필터)"], 0.30)
    variants["v3.2 (+시장+과열회피)"] = sig_v32

    # v3.3 + 과열 회피만 (시장 필터 없이)
    variants["v3.3 (+과열회피)"] = add_overheating_filter(sig_v3, 0.30)

    # v3.4 + 가중 유사도
    variants["v3.4 (가중유사도)"] = add_weighted_similarity(sig_v3, profile, p_base)

    # v3.5 + 가중유사도 + 시장필터
    sig_v35 = add_weighted_similarity(sig_v3, profile, p_base)
    sig_v35 = add_market_filter(sig_v35, kospi, ma_window=20)
    variants["v3.5 (가중+시장)"] = sig_v35

    # v3.6 시장필터(60일선)
    variants["v3.6 (시장60일선)"] = add_market_filter(sig_v3, kospi, ma_window=60)

    # ===== 백테스트 + 비교 =====
    print(f"\n{'변종':<28}{'보유':>4}{'거래':>6}{'승률':>7}{'평균':>8}"
          f"{'PF':>5}{'샤프':>6}{'MDD':>8}{'누적(참고)':>14}")
    print("=" * 100)

    results = []
    for var_name, sig in variants.items():
        for hold in [1, 10, 30, 60, 90]:
            t_df = backtest_v3(sig, bd, p_base, hold_days=hold)
            m = metrics(t_df)
            if m.get("n", 0) == 0:
                continue
            print(f"  {var_name:<26}{hold:>3}일{m['n']:>6,}"
                  f"{m['win_rate']*100:>6.1f}%{m['mean_ret']*100:>+7.2f}%"
                  f"{m['profit_factor']:>5.2f}{m['sharpe']:>6.2f}"
                  f"{m['mdd']*100:>+7.1f}%{m['total_ret']*100:>+13.1f}%")
            results.append({
                "variant": var_name, "hold_days": hold, **m,
            })

    df = pd.DataFrame(results)
    df.to_csv(ROOT / "results" / "v3_variants.csv", index=False, encoding="utf-8-sig")
    df.to_parquet(ROOT / "results" / "v3_variants.parquet")

    # ===== 최고 조합 =====
    print(f"\n{'=' * 60}")
    print("=== 변종별 BEST 보유 기간 (샤프 기준) ===")
    best_per_variant = df.loc[df.groupby("variant")["sharpe"].idxmax()]
    for _, r in best_per_variant.sort_values("sharpe", ascending=False).iterrows():
        print(f"  {r['variant']:<28} {r['hold_days']:>2}일  "
              f"승률 {r['win_rate']*100:>5.1f}%  "
              f"평균 {r['mean_ret']*100:>+6.2f}%  "
              f"PF {r['profit_factor']:>4.2f}  "
              f"샤프 {r['sharpe']:>4.2f}  "
              f"MDD {r['mdd']*100:>+6.1f}%")

    print(f"\n★ 최종 BEST (샤프 1위)")
    best = df.loc[df["sharpe"].idxmax()]
    print(f"  {best['variant']} / {best['hold_days']}일 보유")
    print(f"  승률 {best['win_rate']*100:.1f}%, 평균 {best['mean_ret']*100:+.2f}%, "
          f"PF {best['profit_factor']:.2f}, 샤프 {best['sharpe']:.2f}, "
          f"MDD {best['mdd']*100:+.1f}%, n={int(best['n'])}")


if __name__ == "__main__":
    main()
