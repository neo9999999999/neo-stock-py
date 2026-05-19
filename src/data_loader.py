"""
KRX 데이터 로더 — FDR 기반, parquet 캐싱
=======================================
pykrx의 cross-sectional 엔드포인트가 깨져있어 FinanceDataReader 사용.
거래대금은 Close × Volume 근사 (실제 거래대금과 ~5% 오차 내).
"""

from __future__ import annotations

import datetime as dt
import time
import warnings
from pathlib import Path

import pandas as pd
import FinanceDataReader as fdr

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OHLCV_DIR = DATA_DIR / "ohlcv"
LISTING_DIR = DATA_DIR / "listing"
INDEX_DIR = DATA_DIR / "index"
for d in (OHLCV_DIR, LISTING_DIR, INDEX_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ----- 영업일 -------------------------------------------------------------

def business_days(start: str, end: str) -> list[str]:
    """KOSPI 지수 데이터를 이용한 영업일 리스트 (YYYYMMDD)."""
    start_iso = f"{start[:4]}-{start[4:6]}-{start[6:]}"
    end_iso = f"{end[:4]}-{end[4:6]}-{end[6:]}"
    df = fdr.DataReader("KS11", start_iso, end_iso)
    return df.index.strftime("%Y%m%d").tolist()


# ----- 상장 종목 리스팅 ----------------------------------------------------

def get_krx_listing(force: bool = False) -> pd.DataFrame:
    """KRX 전체 상장 종목 (현재 시점). Marcap·Stocks 포함."""
    cache = LISTING_DIR / "krx_listing.parquet"
    if cache.exists() and not force:
        return pd.read_parquet(cache)
    df = fdr.StockListing("KRX")
    df.to_parquet(cache)
    return df


def get_universe(n: int = 300, market: str | None = None) -> list[str]:
    """현재 시총 상위 N 종목 코드."""
    listing = get_krx_listing()
    if market and "Market" in listing.columns:
        listing = listing[listing["Market"].str.contains(market, na=False, case=False)]
    listing = listing.dropna(subset=["Marcap"])
    listing = listing.sort_values("Marcap", ascending=False).head(n)
    return listing["Code"].tolist()


def get_name(ticker: str) -> str:
    listing = get_krx_listing()
    hit = listing[listing["Code"] == ticker]
    return hit["Name"].iloc[0] if not hit.empty else ticker


# ----- 종목 OHLCV ---------------------------------------------------------

_MASTER_RANGES = ("20210101_20260517", "20200601_20260517", "20200101_20260517")


def _try_master_slice(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    """번들된 master 캐시(2021-2026 등)에서 요청 구간만 슬라이스해서 반환."""
    target_start = pd.to_datetime(f"{start[:4]}-{start[4:6]}-{start[6:]}")
    target_end = pd.to_datetime(f"{end[:4]}-{end[4:6]}-{end[6:]}")
    for rng in _MASTER_RANGES:
        mf = OHLCV_DIR / f"{ticker}_{rng}.parquet"
        if not mf.exists():
            continue
        try:
            df = pd.read_parquet(mf)
        except Exception:
            continue
        if df.empty:
            continue
        if df.index.min() <= target_start and df.index.max() >= min(target_end, df.index.max()):
            return df.loc[(df.index >= target_start) & (df.index <= target_end)]
    return None


def get_ohlcv(ticker: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    """일별 OHLCV. value = close * volume 근사."""
    cache_file = OHLCV_DIR / f"{ticker}_{start}_{end}.parquet"
    if cache_file.exists() and not force:
        return pd.read_parquet(cache_file)
    # 번들된 master 캐시 슬라이스 시도 (Cloud에서 FDR 콜드스타트 회피)
    if not force:
        sliced = _try_master_slice(ticker, start, end)
        if sliced is not None:
            try:
                sliced.to_parquet(cache_file)
            except Exception:
                pass
            return sliced
    start_iso = f"{start[:4]}-{start[4:6]}-{start[6:]}"
    end_iso = f"{end[:4]}-{end[4:6]}-{end[6:]}"
    df = fdr.DataReader(ticker, start_iso, end_iso)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume", "Change": "ret_pct",
    })
    df["value"] = df["close"] * df["volume"]  # 거래대금 근사
    df.index = pd.to_datetime(df.index)
    df.to_parquet(cache_file)
    return df


def bulk_load_ohlcv(tickers: list[str], start: str, end: str,
                    sleep_sec: float = 0.05, verbose: bool = True) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    n = len(tickers)
    for i, t in enumerate(tickers, 1):
        try:
            df = get_ohlcv(t, start, end)
            if not df.empty:
                out[t] = df
        except Exception as exc:
            if verbose and i < 5:
                print(f"  [skip] {t}: {exc}")
        if verbose and i % 50 == 0:
            print(f"  ohlcv {i}/{n}")
        if sleep_sec > 0:
            time.sleep(sleep_sec)
    return out


# ----- 지수 ---------------------------------------------------------------

def get_index_ohlcv(idx_code: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    """KS11=KOSPI, KQ11=KOSDAQ."""
    cache_file = INDEX_DIR / f"idx_{idx_code}_{start}_{end}.parquet"
    if cache_file.exists() and not force:
        return pd.read_parquet(cache_file)
    # 번들된 master 인덱스 슬라이스 시도
    if not force:
        target_start = pd.to_datetime(f"{start[:4]}-{start[4:6]}-{start[6:]}")
        target_end = pd.to_datetime(f"{end[:4]}-{end[4:6]}-{end[6:]}")
        for rng in _MASTER_RANGES:
            mf = INDEX_DIR / f"idx_{idx_code}_{rng}.parquet"
            if not mf.exists():
                continue
            try:
                mdf = pd.read_parquet(mf)
            except Exception:
                continue
            if not mdf.empty and mdf.index.min() <= target_start:
                sliced = mdf.loc[(mdf.index >= target_start) & (mdf.index <= target_end)]
                try:
                    sliced.to_parquet(cache_file)
                except Exception:
                    pass
                return sliced
    start_iso = f"{start[:4]}-{start[4:6]}-{start[6:]}"
    end_iso = f"{end[:4]}-{end[4:6]}-{end[6:]}"
    df = fdr.DataReader(idx_code, start_iso, end_iso)
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume", "Change": "ret_pct",
    })
    df.index = pd.to_datetime(df.index)
    df.to_parquet(cache_file)
    return df


# ----- 일별 스냅샷 (lazy) -------------------------------------------------

def build_snapshot(tickers: list[str], date: str, data_cache: dict | None = None,
                   start: str = "20210101", end: str = "20260517") -> pd.DataFrame:
    """주어진 날짜의 모든 종목 단일행. data_cache가 있으면 그것 사용."""
    target = pd.to_datetime(date)
    rows = []
    for t in tickers:
        df = data_cache.get(t) if data_cache else get_ohlcv(t, start, end)
        if df is None or df.empty or target not in df.index:
            continue
        row = df.loc[target].to_dict()
        row["ticker"] = t
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("ticker")


if __name__ == "__main__":
    days = business_days("20260501", "20260517")
    print("영업일:", len(days), days[:3], "...", days[-1])
    univ = get_universe(n=10)
    print("Top 10:", univ)
    df = get_ohlcv("005930", "20210101", "20260517")
    print("Samsung shape:", df.shape, "cols:", df.columns.tolist())
    print(df.tail(2))
