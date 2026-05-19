"""
사례 39개 reproduction test
============================
v3.8 정직 OOS 모드에서, 사용자 큐레이션 39개 case 중 몇 개를 시그널이
실제로 잡았는가 (hit rate)?

각 사례:
  - buy_date(t0) 시점의 OOS profile = combined cases with buy_date < t0
  - signal_v3 (sim≥0.5) at t0 → triggered? → match
  - 또는 t0±5영업일 범위에서 triggered → near-match

진짜 OOS는 strict — t0 시점에 사례 자체가 profile에 없는 상태에서도 잡는가.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import warnings
warnings.filterwarnings("ignore")

import pandas as pd

from data_loader import get_ohlcv
from engine_v3 import ParamsV3, add_signals_v3
from case_similarity import build_profile, case_count

ROOT = Path(__file__).resolve().parent.parent


def main():
    cases = pd.read_csv(ROOT / "results" / "cases_analysis.csv", dtype={"code": str})
    cases["buy_date_ts"] = pd.to_datetime(cases["buy_date"].astype(str), format="%Y%m%d")
    cases = cases.sort_values("buy_date_ts").reset_index(drop=True)
    print(f"=== 사례 39개 reproduction test (진짜 OOS) ===\n")
    print(f"사례 분포: {cases['buy_date_ts'].min().date()} ~ {cases['buy_date_ts'].max().date()}\n")

    results = []
    p_base = ParamsV3(min_similarity=0.5)

    for _, c in cases.iterrows():
        code = c["code"]
        buy_dt = c["buy_date_ts"]
        asof = buy_dt.strftime("%Y-%m-%d")
        n_in_profile = case_count(combined=True, asof_date=asof)
        if n_in_profile < 50:
            results.append({
                "code": code, "name": c["name"], "buy_date": buy_dt.date(),
                "n_in_profile": n_in_profile, "sim_at_t0": None,
                "hit_t0": False, "hit_t0_5d": False, "max_sim_pm5d": None,
                "note": "profile<50",
            })
            continue

        profile = build_profile(combined=True, asof_date=asof)

        # 시그널 계산 윈도우: buy_date 전 60일 ~ +5영업일
        start = (buy_dt - pd.Timedelta(days=120)).strftime("%Y%m%d")
        end = (buy_dt + pd.Timedelta(days=20)).strftime("%Y%m%d")
        df = get_ohlcv(code, start, end)
        if df.empty or buy_dt not in df.index:
            results.append({
                "code": code, "name": c["name"], "buy_date": buy_dt.date(),
                "n_in_profile": n_in_profile, "sim_at_t0": None,
                "hit_t0": False, "hit_t0_5d": False, "max_sim_pm5d": None,
                "note": "no data",
            })
            continue
        sig = add_signals_v3(df, profile, p_base)

        # t0 시점
        if buy_dt not in sig.index:
            results.append({
                "code": code, "name": c["name"], "buy_date": buy_dt.date(),
                "n_in_profile": n_in_profile, "sim_at_t0": None,
                "hit_t0": False, "hit_t0_5d": False, "max_sim_pm5d": None,
                "note": "buy_dt not in sig",
            })
            continue

        sim_t0 = float(sig.loc[buy_dt, "similarity"])
        hit_t0 = bool(sig.loc[buy_dt, "signal"])

        # ±5영업일 (10영업일 윈도우)
        pos = sig.index.get_loc(buy_dt)
        window = sig.iloc[max(0, pos - 5):min(len(sig), pos + 6)]
        hit_t0_5d = bool(window["signal"].any())
        max_sim = float(window["similarity"].max())

        results.append({
            "code": code, "name": c["name"], "buy_date": buy_dt.date(),
            "n_in_profile": n_in_profile, "sim_at_t0": round(sim_t0, 3),
            "hit_t0": hit_t0, "hit_t0_5d": hit_t0_5d,
            "max_sim_pm5d": round(max_sim, 3),
            "note": "",
        })

    res_df = pd.DataFrame(results)
    res_df.to_csv(ROOT / "results" / "case_reproduction.csv", index=False)
    print(res_df.to_string(index=False))
    print()
    valid = res_df[res_df["note"] == ""]
    hit_t0 = valid["hit_t0"].sum()
    hit_5d = valid["hit_t0_5d"].sum()
    print(f"=== 통계 ({len(valid)}/{len(res_df)} valid) ===")
    print(f"  t0 정확히 hit: {hit_t0}/{len(valid)} ({hit_t0/len(valid)*100:.1f}%)")
    print(f"  ±5영업일 hit: {hit_5d}/{len(valid)} ({hit_5d/len(valid)*100:.1f}%)")
    print(f"  평균 t0 similarity: {valid['sim_at_t0'].mean():.3f}")
    print(f"  평균 ±5d max sim: {valid['max_sim_pm5d'].mean():.3f}")


if __name__ == "__main__":
    main()
