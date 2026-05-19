"""
v1 (기존 5대 조건) vs v2 (사례 학습 기반) 비교 백테스트
=====================================================
2021-2026 전체 기간 + 연도별 비교
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from data_loader import business_days, get_ohlcv
from engine import Params, add_signals, backtest, metrics
from engine_v2 import ParamsV2, add_signals_v2, backtest_v2, metrics_v2

ROOT = Path(__file__).resolve().parent.parent


def load_universe() -> list[str]:
    with open(ROOT / "data" / "universe_final.txt") as f:
        return [l.strip() for l in f if l.strip()]


def main():
    print("=== v1 vs v2 비교 백테스트 ===\n")
    univ = load_universe()
    print(f"유니버스: {len(univ)}개 종목")

    # 워밍업 200일 + 2021-2026
    start, end = "20200601", "20260517"

    print("OHLCV 로드…")
    raw = {}
    t0 = time.time()
    for t in univ:
        df = get_ohlcv(t, start, end)
        if not df.empty and len(df) >= 80:
            raw[t] = df
    print(f"  → {len(raw)}종목, {time.time()-t0:.1f}s")

    bd = business_days("20210101", "20260517")
    print(f"영업일: {len(bd)}일\n")

    # ----- v1 (기존) -----
    print("[v1] 기존 5대 조건 (디폴트값)")
    t0 = time.time()
    p1 = Params(
        min_value=5e9, volume_mult=3.0, high_window=60,
        close_to_high=0.97, daily_ret_min=0.05, daily_ret_max=0.25,
        require_score=4, top_k_per_day=5, stop_loss=-0.03,
        cost_per_trade=0.003,
    )
    sig1 = {t: add_signals(df, p1) for t, df in raw.items()}
    trades1 = backtest(sig1, bd, p1)
    m1 = metrics(trades1)
    print(f"  거래수: {m1['n']:,}, 승률: {m1['win_rate']*100:.1f}%, "
          f"기댓값: {m1['expectancy']*100:+.2f}%, "
          f"누적: {m1['total_ret']*100:+.1f}%, MDD: {m1['mdd']*100:.1f}%, "
          f"{time.time()-t0:.1f}s")

    # ----- v2 (사례 학습) -----
    print("\n[v2] 사례 학습 (이평선 + 모멘텀)")
    t0 = time.time()
    p2 = ParamsV2(
        min_value=5e9, volume_mult=3.0,
        close_to_high=0.92, daily_ret_min=0.05, ret_20d_min=0.15,
        require_score=4, top_k_per_day=5, stop_loss=-0.03,
        cost_per_trade=0.003,
    )
    sig2 = {t: add_signals_v2(df, p2) for t, df in raw.items()}
    trades2 = backtest_v2(sig2, bd, p2)
    m2 = metrics_v2(trades2)
    print(f"  거래수: {m2['n']:,}, 승률: {m2['win_rate']*100:.1f}%, "
          f"기댓값: {m2['expectancy']*100:+.2f}%, "
          f"누적: {m2['total_ret']*100:+.1f}%, MDD: {m2['mdd']*100:.1f}%, "
          f"{time.time()-t0:.1f}s")

    # ----- 연도별 비교 -----
    print("\n=== 연도별 누적 수익 ===")
    print(f"{'연도':>6}  {'v1 거래':>8}  {'v1 누적':>10}  {'v2 거래':>8}  {'v2 누적':>10}")

    for tdf, m, label in [(trades1, m1, "v1"), (trades2, m2, "v2")]:
        tdf["entry_date"] = pd.to_datetime(tdf["entry_date"])
        tdf["year"] = tdf["entry_date"].dt.year

    for year in [2021, 2022, 2023, 2024, 2025, 2026]:
        sub1 = trades1[trades1["year"] == year]
        sub2 = trades2[trades2["year"] == year]
        if sub1.empty and sub2.empty: continue
        cum1 = (1 + sub1["net"]).cumprod().iloc[-1] - 1 if len(sub1) else 0
        cum2 = (1 + sub2["net"]).cumprod().iloc[-1] - 1 if len(sub2) else 0
        print(f"  {year}  {len(sub1):>6,}건  {cum1*100:>+8.1f}%   "
              f"{len(sub2):>6,}건  {cum2*100:>+8.1f}%")

    # 저장
    trades2.to_parquet(ROOT / "results" / "v2_trades.parquet")
    with open(ROOT / "results" / "v2_metrics.json", "w") as f:
        json.dump(m2, f, indent=2, default=float)
    print(f"\n저장: results/v2_trades.parquet, v2_metrics.json")


if __name__ == "__main__":
    main()
