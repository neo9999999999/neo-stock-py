"""
FDR 기반 5년치 데이터 다운로드
=============================
시총 상위 300종목의 일별 OHLCV를 parquet 캐시.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from tqdm import tqdm

from data_loader import (
    business_days,
    get_index_ohlcv,
    get_krx_listing,
    get_ohlcv,
    get_universe,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20210101")
    ap.add_argument("--end", default="20260517")
    ap.add_argument("--top_n", type=int, default=300)
    ap.add_argument("--sleep", type=float, default=0.05)
    args = ap.parse_args()

    print(f"기간: {args.start} ~ {args.end}")
    print(f"시총 상위 N: {args.top_n}")

    # 영업일
    bd = business_days(args.start, args.end)
    print(f"영업일: {len(bd)}일 ({bd[0]} ~ {bd[-1]})")

    # 상장 리스팅 (전체) — 강제 재다운로드
    print("\nKRX 리스팅 로드…")
    listing = get_krx_listing(force=True)
    print(f"  → 전체 {len(listing)}종목")

    # 시총 상위 N
    tickers = get_universe(n=args.top_n)
    print(f"  → 시총 상위 {len(tickers)}: {tickers[:5]} ...")

    # 지수 캐시
    print("\n지수 캐시…")
    get_index_ohlcv("KS11", args.start, args.end, force=True)   # KOSPI
    get_index_ohlcv("KQ11", args.start, args.end, force=True)   # KOSDAQ
    print("  KOSPI/KOSDAQ OK")

    # OHLCV 다운로드
    print(f"\nOHLCV 다운로드 ({len(tickers)} 종목)…")
    failures = []
    for t in tqdm(tickers, desc="ohlcv"):
        try:
            df = get_ohlcv(t, args.start, args.end, force=False)
            if df.empty:
                failures.append((t, "empty"))
        except Exception as exc:
            failures.append((t, str(exc)[:50]))
        if args.sleep > 0:
            time.sleep(args.sleep)

    print(f"\n완료. 실패 {len(failures)}건")
    if failures[:5]:
        print("샘플 실패:", failures[:5])

    # 유니버스 저장
    Path("data").mkdir(exist_ok=True)
    with open("data/universe_final.txt", "w") as f:
        for t in tickers:
            f.write(t + "\n")
    print("저장: data/universe_final.txt")


if __name__ == "__main__":
    main()
