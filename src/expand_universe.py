"""
시총 2000억 이상 종목으로 유니버스 확장
=====================================
"""

from __future__ import annotations

import time
from pathlib import Path

from tqdm import tqdm

from data_loader import (
    business_days,
    get_index_ohlcv,
    get_krx_listing,
    get_ohlcv,
)

ROOT = Path(__file__).resolve().parent.parent
UNIV_FILE = ROOT / "data" / "universe_final.txt"
CAP_THRESHOLD = 2000 * 1e8  # 2000억원
START = "20210101"
END = "20260517"


def main():
    print(f"기준: 시총 {CAP_THRESHOLD/1e8:.0f}억원 이상")

    listing = get_krx_listing(force=True)
    print(f"전체 상장: {len(listing):,}개")

    # 시총 필터
    filt = listing[listing["Marcap"] >= CAP_THRESHOLD].copy()
    filt = filt.sort_values("Marcap", ascending=False)
    tickers = filt["Code"].tolist()
    print(f"시총 {CAP_THRESHOLD/1e8:.0f}억 이상: {len(tickers):,}개")
    print(f"  최저 시총: {filt.iloc[-1]['Marcap']/1e8:,.0f}억 ({filt.iloc[-1]['Name']})")

    # 기존 다운로드 종목 확인
    existing = set()
    if UNIV_FILE.exists():
        with open(UNIV_FILE) as f:
            existing = {l.strip() for l in f if l.strip()}
    print(f"기존 다운로드: {len(existing):,}개")

    new_tickers = [t for t in tickers if t not in existing]
    print(f"새로 다운로드: {len(new_tickers):,}개")

    # 지수는 이미 캐시됨
    print("\nOHLCV 다운로드 시작...")
    failures = []
    for t in tqdm(new_tickers, desc="ohlcv"):
        try:
            df = get_ohlcv(t, START, END)
            if df.empty:
                failures.append((t, "empty"))
        except Exception as exc:
            failures.append((t, str(exc)[:50]))
        time.sleep(0.05)

    print(f"\n실패: {len(failures)}건")
    if failures[:5]:
        print(f"샘플: {failures[:5]}")

    # 유니버스 파일 업데이트
    with open(UNIV_FILE, "w") as f:
        for t in tickers:
            f.write(t + "\n")
    print(f"\n유니버스 저장: {UNIV_FILE}")
    print(f"최종 유니버스 크기: {len(tickers):,}개")


if __name__ == "__main__":
    main()
