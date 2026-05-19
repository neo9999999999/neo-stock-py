"""
v2 + 다양한 보유 기간 비교
=========================
사례 학습 결과는 1일 보유로는 살아나지 않음.
1/5/10/20/30/60일 보유 결과 비교.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from data_loader import business_days, get_ohlcv
from engine import Params, backtest_tiered, metrics
from engine_v2 import ParamsV2, add_signals_v2

ROOT = Path(__file__).resolve().parent.parent


def main():
    print("=== v2 + 보유 기간 비교 ===\n")
    with open(ROOT / "data" / "universe_final.txt") as f:
        univ = [l.strip() for l in f if l.strip()]
    print(f"유니버스: {len(univ)}개 (시총 500억+)")

    start, end = "20200601", "20260517"
    print("OHLCV 로드…")
    raw = {}
    t0 = time.time()
    for t in univ:
        df = get_ohlcv(t, start, end)
        if not df.empty and len(df) >= 80:
            raw[t] = df
    print(f"  → {len(raw)}종목, {time.time()-t0:.1f}s")

    # v2 시그널 계산
    p2 = ParamsV2(
        min_value=5e9, volume_mult=3.0,
        close_to_high=0.92, daily_ret_min=0.05, ret_20d_min=0.15,
        require_score=4, top_k_per_day=5, stop_loss=-0.03,
        cost_per_trade=0.003,
    )
    print("\nv2 시그널 계산…")
    t0 = time.time()
    sig_data = {t: add_signals_v2(df, p2) for t, df in raw.items()}
    print(f"  → {time.time()-t0:.1f}s")

    bd = business_days("20210101", "20260517")

    # Params 호환 (backtest_tiered용)
    p_compat = Params(
        min_value=p2.min_value, volume_mult=p2.volume_mult,
        high_window=60, close_to_high=p2.close_to_high,
        daily_ret_min=p2.daily_ret_min, daily_ret_max=0.30,
        require_score=p2.require_score, top_k_per_day=p2.top_k_per_day,
        stop_loss=p2.stop_loss, cost_per_trade=p2.cost_per_trade,
    )

    # 다양한 보유 기간 — TP 비활성 (단순 만기 시초가 청산)
    print("\n=== v2 + 보유 기간별 비교 (만기 시초가 청산) ===")
    print(f"{'보유':>4}  {'거래수':>6}  {'승률':>6}  {'기댓값':>8}  "
          f"{'평균수익':>9}  {'누적':>12}  {'MDD':>8}  {'시간':>5}")

    results = {}
    for hold in [1, 5, 10, 20, 30, 60, 90]:
        t0 = time.time()
        t_df = backtest_tiered(sig_data, bd, p_compat, hold_days=hold,
                                tp1_pct=99.0, tp2_pct=99.0)
        m = metrics(t_df)
        results[hold] = (t_df, m)
        print(f"  {hold:>2}일  {m['n']:>6,}  {m['win_rate']*100:>5.1f}%  "
              f"{m['expectancy']*100:>+7.2f}%  {m['mean_ret']*100:>+8.2f}%  "
              f"{m['total_ret']*100:>+11.1f}%  {m['mdd']*100:>+6.1f}%  "
              f"{time.time()-t0:>4.0f}s")

    # 추가: TP1/TP2 분할 청산 (사례의 진짜 활용)
    print("\n=== v2 + TP1/TP2 분할 청산 (TP1 +30% / TP2 +50%, 만기 시초가) ===")
    print(f"{'보유':>4}  {'거래수':>6}  {'승률':>6}  {'기댓값':>8}  "
          f"{'TP1 도달':>8}  {'TP2 도달':>8}  {'누적':>12}")

    for hold in [10, 20, 30, 60]:
        t_df = backtest_tiered(sig_data, bd, p_compat, hold_days=hold,
                                tp1_pct=0.30, tp2_pct=0.50,
                                tp1_size=0.5, tp2_size=0.5)
        m = metrics(t_df)
        tp1_rate = t_df["tp1_hit"].mean() if "tp1_hit" in t_df.columns else 0
        tp2_rate = t_df["tp2_hit"].mean() if "tp2_hit" in t_df.columns else 0
        print(f"  {hold:>2}일  {m['n']:>6,}  {m['win_rate']*100:>5.1f}%  "
              f"{m['expectancy']*100:>+7.2f}%  {tp1_rate*100:>7.1f}%  "
              f"{tp2_rate*100:>7.1f}%  {m['total_ret']*100:>+11.1f}%")

    # 저장
    best_hold = max(results.keys(), key=lambda h: results[h][1]["expectancy"])
    best_trades, best_m = results[best_hold]
    best_trades.to_parquet(ROOT / "results" / "v2_best_trades.parquet")
    with open(ROOT / "results" / "v2_best_metrics.json", "w") as f:
        json.dump({"best_hold_days": best_hold, **best_m}, f, indent=2, default=float)
    print(f"\n★ 최고 보유 기간: {best_hold}일, 기댓값 {best_m['expectancy']*100:+.2f}%")


if __name__ == "__main__":
    main()
