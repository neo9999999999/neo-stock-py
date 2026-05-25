"""
월별 진짜 OOS 검증 (2021-01 ~ 2026-05)
=====================================
각 월에 대해:
  - profile = combined cases with buy_date < 해당 월 1일
  - 그 profile + 시장필터(KOSPI 20MA)로 시그널 계산
  - 그 월에 발생한 시그널들을 매수 → 보유 N일 후 매도 (손절 없음)
  - 30 / 60 / 90 / 120일 보유 성과 각각 기록

목적:
1. 월 단위 커버리지 (시그널 0건인 달이 얼마나 많은가)
2. 어떤 보유기간이 가장 안정적인가
3. 수익이 소수 달에 집중되는가 (outlier 의존도)

손절 없음. 매수 후 정확히 N영업일 후 종가에 청산.
시총 5천억+ 유니버스. 시장필터 ON.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import warnings
warnings.filterwarnings("ignore")

import json
import time
import pandas as pd

from data_loader import get_ohlcv, get_index_ohlcv, get_krx_listing
from engine_v3 import ParamsV3, add_signals_v3
from case_similarity import build_profile, case_count

ROOT = Path(__file__).resolve().parent.parent

MIN_CASES_FOR_PROFILE = 50
SIM_THRESHOLD = 0.5             # 보수적으로 0.5 (v3.8 grid 결과)
HOLDS = [30, 60, 90, 120, 180]
MARKET_CAP_CUTOFF = 5e11
START_MONTH = "2021-01"
END_MONTH = "2026-05"


def main():
    print(f"=== 월별 진짜 OOS 검증 ({START_MONTH} ~ {END_MONTH}, 손절 X) ===", flush=True)

    listing = get_krx_listing()
    large_codes = set(listing[listing["Marcap"] >= MARKET_CAP_CUTOFF]["Code"])
    with open(ROOT / "data" / "universe_final.txt") as f:
        univ = [l.strip() for l in f if l.strip()]
    univ = [t for t in univ if t in large_codes]
    print(f"유니버스: {len(univ)}종목 (5천억+)", flush=True)

    # OHLCV 한 번에 로드
    raw = {}
    for t in univ:
        df = get_ohlcv(t, "20200601", "20260517")
        if not df.empty and len(df) >= 80:
            raw[t] = df
    print(f"  로드: {len(raw)}종목", flush=True)

    # 시장 필터
    kospi = get_index_ohlcv("KS11", "20200101", "20260517")
    kospi["ma20"] = kospi["close"].rolling(20).mean()
    market_above = kospi["close"] > kospi["ma20"]

    # 월 리스트 생성
    months = pd.date_range(start=f"{START_MONTH}-01",
                             end=f"{END_MONTH}-01",
                             freq="MS")
    print(f"검증 월: {len(months)}개", flush=True)

    monthly_records = []
    trade_records = []
    t0 = time.time()

    for mi, month_start in enumerate(months, 1):
        # 다음 달 1일 = 이 달 끝
        next_month = month_start + pd.DateOffset(months=1)
        asof = month_start.strftime("%Y-%m-%d")
        nc = case_count(combined=True, asof_date=asof)

        if nc < MIN_CASES_FOR_PROFILE:
            monthly_records.append({
                "month": month_start.strftime("%Y-%m"),
                "n_in_profile": nc, "n_signals": 0,
                "ret_30": None, "ret_60": None, "ret_90": None, "ret_120": None,
                "win_30": None, "win_60": None, "win_90": None, "win_120": None,
                "note": "profile<50",
            })
            print(f"  [{month_start.strftime('%Y-%m')}] profile={nc} skip", flush=True)
            continue

        profile = build_profile(combined=True, asof_date=asof)
        p_v3 = ParamsV3(min_similarity=SIM_THRESHOLD)

        month_sigs = []
        for code, df in raw.items():
            try:
                sig = add_signals_v3(df, profile, p_v3)
                # 이 달 안에 trigger된 시그널만
                mask = (sig.index >= month_start) & (sig.index < next_month) & sig["signal"]
                # 시장 필터
                above = market_above.reindex(sig.index, method="ffill").fillna(False)
                mask = mask & above
                if not mask.any():
                    continue
                for ts in sig.index[mask]:
                    pos = df.index.get_loc(ts)
                    entry_close = float(df.iloc[pos]["close"])
                    rec = {"month": month_start.strftime("%Y-%m"),
                           "date": ts.strftime("%Y-%m-%d"),
                           "code": code, "entry_close": entry_close,
                           "similarity": float(sig.loc[ts, "similarity"])}
                    for h in HOLDS:
                        if pos + h < len(df):
                            exit_close = float(df.iloc[pos + h]["close"])
                            rec[f"ret_{h}"] = (exit_close - entry_close) / entry_close
                        else:
                            rec[f"ret_{h}"] = None
                    month_sigs.append(rec)
                    trade_records.append(rec)
            except Exception:
                continue

        if not month_sigs:
            monthly_records.append({
                "month": month_start.strftime("%Y-%m"),
                "n_in_profile": nc, "n_signals": 0,
                "ret_30": None, "ret_60": None, "ret_90": None, "ret_120": None,
                "win_30": None, "win_60": None, "win_90": None, "win_120": None,
                "note": "no_signals",
            })
            print(f"  [{month_start.strftime('%Y-%m')}] profile={nc} sigs=0", flush=True)
            continue

        m_df = pd.DataFrame(month_sigs)
        agg = {
            "month": month_start.strftime("%Y-%m"),
            "n_in_profile": nc, "n_signals": len(m_df),
        }
        for h in HOLDS:
            vals = m_df[f"ret_{h}"].dropna()
            if len(vals):
                agg[f"ret_{h}"] = float(vals.mean())
                agg[f"win_{h}"] = float((vals > 0).mean())
            else:
                agg[f"ret_{h}"] = None
                agg[f"win_{h}"] = None
        agg["note"] = ""
        monthly_records.append(agg)

        if mi % 6 == 0:
            print(f"  [{month_start.strftime('%Y-%m')}] sigs={len(m_df)} "
                  f"ret30={agg['ret_30']*100 if agg['ret_30'] is not None else None:+.1f}% "
                  f"({time.time()-t0:.0f}s)", flush=True)

    monthly_df = pd.DataFrame(monthly_records)
    trades_df = pd.DataFrame(trade_records)

    monthly_df.to_csv(ROOT / "results" / "monthly_oos.csv", index=False)
    trades_df.to_parquet(ROOT / "results" / "monthly_oos_trades.parquet")

    print(f"\n=== 커버리지 ===", flush=True)
    n_total = len(monthly_df)
    n_skip_profile = (monthly_df["note"] == "profile<50").sum()
    n_no_sigs = (monthly_df["note"] == "no_signals").sum()
    n_valid = (monthly_df["note"] == "").sum()
    print(f"  총 월: {n_total}", flush=True)
    print(f"  profile 부족 skip: {n_skip_profile}", flush=True)
    print(f"  시그널 0건: {n_no_sigs}", flush=True)
    print(f"  유효 (시그널 ≥1): {n_valid}", flush=True)
    print(f"  총 시그널: {len(trades_df):,}건", flush=True)

    print(f"\n=== 보유 기간별 성과 (전체 시그널 평균) ===", flush=True)
    for h in HOLDS:
        vals = trades_df[f"ret_{h}"].dropna()
        if len(vals) == 0:
            continue
        cumret = ((1 + vals).prod() - 1)
        win = (vals > 0).mean()
        print(f"  {h}일 보유:  n={len(vals):,}  평균 {vals.mean()*100:+.2f}%  "
              f"중앙 {vals.median()*100:+.2f}%  승률 {win*100:.1f}%  "
              f"복리누적 {cumret*100:+.1f}%", flush=True)

    print(f"\n=== Outlier 의존도 (top-3 월 제외 시) ===", flush=True)
    for h in HOLDS:
        ms = monthly_df[monthly_df[f"ret_{h}"].notna()].sort_values(
            f"ret_{h}", ascending=False)
        if len(ms) < 4:
            continue
        all_avg = ms[f"ret_{h}"].mean()
        ex_top3 = ms.iloc[3:][f"ret_{h}"].mean()
        print(f"  {h}일: 전체 월평균 {all_avg*100:+.2f}%  "
              f"top3 제외 {ex_top3*100:+.2f}%  격차 {(all_avg-ex_top3)*100:+.2f}%p", flush=True)


if __name__ == "__main__":
    main()
