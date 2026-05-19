"""
v3.8 워크포워드 — 진짜 OOS (사례 profile도 시점별 재빌드)
=========================================================
v3.7과 동일하지만 각 window의 train 시작 시점보다 buy_date < 시점인
사례만으로 case_profile을 빌드.

사례 12,798개 (마이닝 12,759 + 사용자 39)가 합본되어 있어 2022년부터는
충분한 표본 (~500+) 확보 가능.

사용:
  python src/run_v38_walkforward_oos.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

from data_loader import business_days, get_index_ohlcv, get_ohlcv, get_krx_listing
from engine import metrics
from engine_v3 import ParamsV3, add_signals_v3, backtest_v3
from engine_v3plus import add_market_filter
from case_similarity import build_profile, case_count

ROOT = Path(__file__).resolve().parent.parent

MIN_CASES_FOR_PROFILE = 50          # 사례 50건 미만이면 window skip
TRAIN_DAYS = 252                    # 1년
TEST_DAYS = 63                      # 3개월
STEP_DAYS = 63


def make_combos():
    return [
        {"similarity": s, "hold_days": h}
        for s in [0.5, 0.6, 0.7]
        for h in [10, 30, 60, 90]
    ]


def grid_search(sig_data, bd, p_base, min_trades=10):
    rows = []
    for c in make_combos():
        p = ParamsV3(min_similarity=c["similarity"], top_k_per_day=p_base.top_k_per_day,
                      stop_loss=p_base.stop_loss, cost_per_trade=p_base.cost_per_trade)
        t = backtest_v3(sig_data, bd, p, hold_days=c["hold_days"])
        m = metrics(t)
        if m.get("n", 0) < min_trades:
            continue
        rows.append({**m, **c})
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("expectancy", ascending=False)
    return df.iloc[0].to_dict()


def main():
    print("=== v3.8 진짜 OOS 워크포워드 (시점별 case_profile) ===", flush=True)

    listing = get_krx_listing()
    large_codes = set(listing[listing["Marcap"] >= 5e11]["Code"])

    with open(ROOT / "data" / "universe_final.txt") as f:
        univ = [l.strip() for l in f if l.strip()]
    univ = [t for t in univ if t in large_codes]
    print(f"유니버스: {len(univ)}개 (5천억+)", flush=True)

    print("OHLCV 로드…", flush=True)
    raw = {}
    for t in univ:
        df = get_ohlcv(t, "20200101", "20260517")
        if not df.empty and len(df) >= 80:
            raw[t] = df
    print(f"  → {len(raw)}종목", flush=True)

    kospi = get_index_ohlcv("KS11", "20200101", "20260517")

    bd = business_days("20210101", "20260517")
    windows = []
    start_idx = 0
    while start_idx + TRAIN_DAYS + TEST_DAYS <= len(bd):
        windows.append((bd[start_idx:start_idx + TRAIN_DAYS],
                        bd[start_idx + TRAIN_DAYS:start_idx + TRAIN_DAYS + TEST_DAYS]))
        start_idx += STEP_DAYS
    print(f"윈도우 수: {len(windows)}", flush=True)

    p_base = ParamsV3(min_similarity=0.6, top_k_per_day=5, stop_loss=-0.03)
    all_oos = []
    summary = []

    for wi, (train, test) in enumerate(windows, 1):
        t0 = time.time()
        asof = train[0]                             # train 시작 시점
        nc = case_count(combined=True, asof_date=asof)
        print(f"\n[W{wi}/{len(windows)}] train {train[0]}~{train[-1]} | "
              f"test {test[0]}~{test[-1]} | asof={asof} cases={nc}", flush=True)

        if nc < MIN_CASES_FOR_PROFILE:
            print(f"  skip (사례 {nc}건 < {MIN_CASES_FOR_PROFILE})", flush=True)
            continue

        # 시점별 profile 빌드
        profile_w = build_profile(combined=True, asof_date=asof)

        # 이 윈도우만의 sig_data 재계산
        p_dummy = ParamsV3(min_similarity=0.3)
        sig_data = {t: add_signals_v3(df, profile_w, p_dummy)
                    for t, df in raw.items()}
        sig_data = add_market_filter(sig_data, kospi, ma_window=20)

        best = grid_search(sig_data, train, p_base)
        if best is None:
            print("  skip (학습 거래 부족)", flush=True)
            continue
        sim_b, hold_b = best["similarity"], best["hold_days"]
        print(f"  [best] sim≥{sim_b}, hold={hold_b}일  "
              f"n={int(best['n'])}, expect={best['expectancy']*100:+.2f}%",
              flush=True)
        p_t = ParamsV3(min_similarity=sim_b, top_k_per_day=5, stop_loss=-0.03)
        oos = backtest_v3(sig_data, test, p_t, hold_days=hold_b)
        oos_m = metrics(oos)
        if not oos.empty:
            oos["window"] = wi
            all_oos.append(oos)
        print(f"  [OOS] n={oos_m.get('n',0)}, win={oos_m.get('win_rate',0)*100:.1f}%, "
              f"expect={oos_m.get('expectancy',0)*100:+.2f}%, "
              f"total={oos_m.get('total_ret',0)*100:+.1f}%, "
              f"{time.time()-t0:.0f}s", flush=True)
        summary.append({
            "window": wi,
            "asof_date": asof,
            "n_cases_in_profile": nc,
            "train_start": train[0], "train_end": train[-1],
            "test_start": test[0], "test_end": test[-1],
            "best_similarity": sim_b, "best_hold_days": int(hold_b),
            "train": best, "test": oos_m,
        })

    if all_oos:
        oos_all = pd.concat(all_oos, ignore_index=True)
        oos_m_total = metrics(oos_all)
        oos_all.to_parquet(ROOT / "results" / "v38_wf_oos_trades.parquet")
    else:
        oos_m_total = {"n": 0}

    with open(ROOT / "results" / "v38_wf_summary.json", "w") as f:
        json.dump({"windows": summary, "oos_metrics": oos_m_total},
                  f, indent=2, default=float, ensure_ascii=False)

    print(f"\n=== v3.8 진짜 OOS 통합 ===", flush=True)
    for k in ["n", "win_rate", "mean_ret", "expectancy", "profit_factor",
              "sharpe", "mdd", "total_ret"]:
        v = oos_m_total.get(k, 0)
        if isinstance(v, float) and k in ("win_rate", "mean_ret",
                                             "expectancy", "mdd", "total_ret"):
            print(f"  {k:>15}: {v*100:+8.2f}%", flush=True)
        else:
            print(f"  {k:>15}: {v}", flush=True)


if __name__ == "__main__":
    main()
