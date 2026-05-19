"""
KRX 전체 종목 OHLCV 캐시 확장
============================
시총 무관 모든 상장 종목 5년 데이터 다운로드.
"""

from __future__ import annotations

import time
from pathlib import Path

from tqdm import tqdm

from data_loader import get_krx_listing, get_ohlcv

ROOT = Path(__file__).resolve().parent.parent
UNIV_FILE = ROOT / "data" / "universe_final.txt"
START = "20210101"
END = "20260517"


def main():
    print("KRX 전체 상장 종목 다운로드 시작")
    listing = get_krx_listing(force=True)
    print(f"전체 상장: {len(listing):,}개")

    # 시총 내림차순 정렬 후 모든 종목
    listing = listing.dropna(subset=["Marcap"]).sort_values("Marcap", ascending=False)
    tickers = listing["Code"].tolist()
    print(f"다운로드 대상: {len(tickers):,}개")

    # 기존 캐시된 것 스킵
    existing = set()
    if UNIV_FILE.exists():
        with open(UNIV_FILE) as f:
            existing = {l.strip() for l in f if l.strip()}
    print(f"기존 캐시: {len(existing):,}개")

    new = [t for t in tickers if t not in existing]
    print(f"신규 다운로드: {len(new):,}개")

    failures = []
    for t in tqdm(new, desc="ohlcv"):
        try:
            df = get_ohlcv(t, START, END)
            if df.empty:
                failures.append((t, "empty"))
        except Exception as exc:
            failures.append((t, str(exc)[:50]))
        time.sleep(0.05)

    print(f"\n실패: {len(failures)}건")

    # 유니버스 파일 갱신 (모든 종목)
    with open(UNIV_FILE, "w") as f:
        for t in tickers:
            f.write(t + "\n")
    print(f"유니버스 저장: {UNIV_FILE} ({len(tickers):,}개)")


if __name__ == "__main__":
    main()
