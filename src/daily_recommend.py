"""
일일 종가 추천 — 콘솔 + CSV 출력
=================================
장 마감 후 또는 임의 시점에 실행하여 5대 조건 충족 종목을 출력.

사용:
    python src/daily_recommend.py                # 가장 최신 영업일
    python src/daily_recommend.py 20260514       # 특정 일자
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

from data_loader import business_days, get_name, get_ohlcv, get_universe
from engine import Params, add_signals

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def recommend(date: str, params: Params, universe_n: int = 300) -> pd.DataFrame:
    """주어진 날짜의 5대 조건 충족 종목 반환."""
    universe = get_universe(n=universe_n)

    target = pd.to_datetime(date)
    end_dt = dt.datetime.strptime(date, "%Y%m%d")
    start_dt = end_dt - dt.timedelta(days=200)
    start_str = start_dt.strftime("%Y%m%d")

    rows = []
    for t in universe:
        df = get_ohlcv(t, start_str, date)
        if df.empty or len(df) < params.high_window + 2 or target not in df.index:
            continue
        sig = add_signals(df, params)
        if target not in sig.index:
            continue
        r = sig.loc[target]
        if not bool(r.get("signal", False)):
            continue
        rows.append({
            "ticker": t,
            "name": get_name(t),
            "score": int(r["score"]),
            "close": int(r["close"]),
            "ret_pct": round(r["ret_1d"] * 100, 2),
            "value_억": round(r["value"] / 1e8, 0),
            "vol_ratio": round(r["volume"] / r["vol_avg_n"], 2),
            "close/high": round(r["close"] / r["high"], 3),
            "high_n": int(r["high_n"]),
            "c1_high": bool(r["c1_high"]),
            "c2_vol": bool(r["c2_vol"]),
            "c3_value": bool(r["c3_value"]),
            "c4_strength": bool(r["c4_close_strength"]),
            "c5_ret": bool(r["c5_ret_band"]),
        })

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("value_억", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "rank"
    return df


def main():
    # 날짜 결정
    if len(sys.argv) > 1:
        date = sys.argv[1].replace("-", "")
    else:
        end = dt.date.today().strftime("%Y%m%d")
        start = (dt.date.today() - dt.timedelta(days=20)).strftime("%Y%m%d")
        bd = business_days(start, end)
        date = bd[-1]

    print(f"\n=== {date} 종가 베팅 추천 ===\n")

    # 보고서 권장 파라미터
    p = Params(
        min_value=5e10,
        volume_mult=3.0,
        high_window=60,
        close_to_high=0.97,
        daily_ret_min=0.05,
        daily_ret_max=0.25,
        require_score=5,
    )

    df = recommend(date, p)
    if df.empty:
        print("조건 충족 종목 없음.")
        # 완화 조건(4점 이상)으로 재시도
        p2 = Params(require_score=4, **{k: v for k, v in p.__dict__.items() if k != "require_score"})
        df = recommend(date, p2)
        if not df.empty:
            print(f"\n[참고] 4점 이상 종목 {len(df)}개:\n")

    if df.empty:
        return

    print(f"5점 만점 종목: {(df['score']==5).sum()}개")
    print(f"4점 종목: {(df['score']==4).sum()}개")
    print(f"대장주 (거래대금 1위): {df.iloc[0]['name']} ({df.iloc[0]['ticker']})")
    print()

    # 출력
    show_cols = ["name", "ticker", "score", "close", "ret_pct", "value_억",
                 "vol_ratio", "close/high", "high_n"]
    print(df[show_cols].to_string())

    # CSV 저장
    out = RESULTS / f"daily_{date}.csv"
    df.to_csv(out, encoding="utf-8-sig")
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
