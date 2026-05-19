"""
v3 워크포워드 분석
=================
사례 유사도 ≥0.6 + 30일 보유 고정.
17 윈도우 (학습 1년 / 검증 3개월 슬라이딩) 진행하며
각 검증 구간 OOS 성과 측정.

학습 구간에서는 유사도 임계치(0.5/0.6/0.7/0.8)와 보유일(10/30/60/90)
8 조합 그리드 서치 후 best 파라미터로 검증.
"""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from data_loader import business_days, get_ohlcv
from engine import metrics
from engine_v3 import ParamsV3, add_signals_v3, backtest_v3
from case_similarity import build_profile

ROOT = Path(__file__).resolve().parent.parent


def make_combos():
    """그리드: 유사도 × 보유일."""
    combos = []
    for sim in [0.5, 0.6, 0.7, 0.8]:
        for hold in [10, 30, 60, 90]:
            combos.append({"similarity": sim, "hold_days": hold})
    return combos


def grid_search_v3(sig_data, bd, p_base, objective="expectancy", min_trades=20):
    rows = []
    for combo in make_combos():
        p = ParamsV3(
            min_similarity=combo["similarity"],
            top_k_per_day=p_base.top_k_per_day,
            stop_loss=p_base.stop_loss,
            cost_per_trade=p_base.cost_per_trade,
        )
        # 시그널 다시 계산 (임계치만 바뀜 — signal 컬럼만)
        # 실제로는 similarity 이미 있으면 그것만 비교
        t_df = backtest_v3(sig_data, bd, p, hold_days=combo["hold_days"])
        m = metrics(t_df)
        if m.get("n", 0) < min_trades:
            continue
        rows.append({**m, **combo})
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values(objective, ascending=False)
    return df.iloc[0].to_dict()


def main():
    profile = build_profile()
    print("=== v3 워크포워드 시작 ===\n")

    with open(ROOT / "data" / "universe_final.txt") as f:
        univ = [l.strip() for l in f if l.strip()]
    print(f"유니버스: {len(univ)}개")

    # 데이터 로드 (워밍업 포함)
    print("OHLCV 로드…")
    t0 = time.time()
    raw = {}
    for t in univ:
        df = get_ohlcv(t, "20200101", "20260517")
        if not df.empty and len(df) >= 80:
            raw[t] = df
    print(f"  → {len(raw)}종목, {time.time()-t0:.1f}s")

    # v3 시그널을 한 번만 계산 (임계치만 윈도우별로 바뀜)
    print("\nv3 시그널 계산 (전체 기간, 한 번만)…")
    t0 = time.time()
    # 시그널 계산을 위한 dummy params (최저 임계치로 계산 — similarity 컬럼만 필요)
    p_dummy = ParamsV3(min_similarity=0.3)
    sig_data = {t: add_signals_v3(df, profile, p_dummy) for t, df in raw.items()}
    print(f"  → {time.time()-t0:.1f}s")

    bd = business_days("20210101", "20260517")
    print(f"영업일: {len(bd)}일")

    # 워크포워드 윈도우
    train_days = 252   # 1년
    test_days = 63     # 3개월
    step_days = 63

    bd_ts = pd.to_datetime(bd)
    windows = []
    start_idx = 0
    while start_idx + train_days + test_days <= len(bd):
        train_dates = bd[start_idx : start_idx + train_days]
        test_dates = bd[start_idx + train_days : start_idx + train_days + test_days]
        windows.append((train_dates, test_dates))
        start_idx += step_days
    print(f"윈도우 수: {len(windows)}")

    # 각 윈도우
    all_oos_trades = []
    summary = []
    p_base = ParamsV3(min_similarity=0.6, top_k_per_day=5, stop_loss=-0.03)

    for wi, (train, test) in enumerate(windows, 1):
        print(f"\n[Window {wi}/{len(windows)}] "
              f"train {train[0]}~{train[-1]} | test {test[0]}~{test[-1]}")
        t0 = time.time()

        # 학습 구간 그리드 서치
        best = grid_search_v3(sig_data, train, p_base, "expectancy", min_trades=20)
        if best is None:
            print(f"  [skip] 학습 거래 < 20")
            continue
        sim_b, hold_b = best["similarity"], best["hold_days"]
        print(f"  [best] sim≥{sim_b}, hold={hold_b}일, train: "
              f"n={int(best['n'])}, win={best['win_rate']*100:.1f}%, "
              f"expect={best['expectancy']*100:+.2f}%, total={best['total_ret']*100:+.1f}%")

        # 검증 구간 적용
        p_test = ParamsV3(min_similarity=sim_b, top_k_per_day=5, stop_loss=-0.03)
        oos = backtest_v3(sig_data, test, p_test, hold_days=hold_b)
        oos_m = metrics(oos)
        if not oos.empty:
            oos["window"] = wi
            all_oos_trades.append(oos)

        print(f"  [OOS]  n={oos_m.get('n',0)}, win={oos_m.get('win_rate',0)*100:.1f}%, "
              f"expect={oos_m.get('expectancy',0)*100:+.2f}%, "
              f"total={oos_m.get('total_ret',0)*100:+.1f}%, {time.time()-t0:.0f}s")

        summary.append({
            "window": wi,
            "train_start": train[0], "train_end": train[-1],
            "test_start": test[0], "test_end": test[-1],
            "best_similarity": sim_b,
            "best_hold_days": int(hold_b),
            "train": best,
            "test": oos_m,
        })

    # 통합 OOS
    if all_oos_trades:
        oos_all = pd.concat(all_oos_trades, ignore_index=True)
        oos_metrics = metrics(oos_all)
        oos_all.to_parquet(ROOT / "results" / "v3_wf_oos_trades.parquet")
    else:
        oos_metrics = {"n": 0}

    out = {"windows": summary, "oos_metrics": oos_metrics}
    with open(ROOT / "results" / "v3_wf_summary.json", "w") as f:
        json.dump(out, f, indent=2, default=float, ensure_ascii=False)

    print(f"\n=== v3 OOS 통합 ===")
    for k, v in oos_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v*100:+.2f}%" if k in ("win_rate","mean_ret","expectancy","mdd","total_ret") else f"  {k}: {v:.2f}")
        else:
            print(f"  {k}: {v}")
    print(f"\n저장: results/v3_wf_summary.json, v3_wf_oos_trades.parquet")


if __name__ == "__main__":
    main()
