"""
종가 베팅 — 당일 스크리너
=========================
오후 14:30 이후 실행하여 5대 조건을 만족하는 종목을 출력.

요구:
  pip install pykrx pandas numpy tabulate
"""

import datetime as dt
import sys

import pandas as pd

try:
    from pykrx import stock
except ImportError as exc:
    raise SystemExit("pip install pykrx pandas numpy tabulate") from exc

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None  # 선택


# ----- 파라미터 -------------------------------------------------------------

MIN_TRADING_VALUE = 5e10     # 거래대금 500억 이상
VOLUME_MULTIPLIER = 3.0      # 60일 평균 거래량의 3배 이상
HIGH_WINDOW = 60             # 60일 신고가
CLOSE_TO_HIGH = 0.97         # 종가/고가 ≥ 0.97
DAILY_RET_MIN = 0.05         # 최소 +5%
DAILY_RET_MAX = 0.25         # 최대 +25%
UNIVERSE_SIZE = 300          # 시총 상위 300


# ----- 데이터 -------------------------------------------------------------

def fetch_today_snapshot(date: str) -> pd.DataFrame:
    """해당일 전체 종목의 OHLCV + 시총 + 거래대금."""
    ohlcv = stock.get_market_ohlcv_by_ticker(date, market="ALL")
    cap = stock.get_market_cap_by_ticker(date, market="ALL")
    df = ohlcv.join(cap[["시가총액"]], how="inner")
    df = df.rename(columns={
        "시가": "open", "고가": "high", "저가": "low",
        "종가": "close", "거래량": "volume", "거래대금": "value",
        "등락률": "ret_pct", "시가총액": "mkt_cap",
    })
    return df


def fetch_60d_history(ticker: str, end: str, days: int = 90) -> pd.DataFrame:
    """60일 신고가/평균거래량 계산용 과거 데이터."""
    end_dt = dt.datetime.strptime(end, "%Y%m%d")
    start_dt = end_dt - dt.timedelta(days=days * 2)  # 영업일 보정
    start = start_dt.strftime("%Y%m%d")
    df = stock.get_market_ohlcv_by_date(start, end, ticker)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={
        "시가": "open", "고가": "high", "저가": "low",
        "종가": "close", "거래량": "volume", "거래대금": "value",
    })
    return df


# ----- 스크리닝 -----------------------------------------------------------

def screen(date: str) -> pd.DataFrame:
    snap = fetch_today_snapshot(date)
    snap = snap.sort_values("mkt_cap", ascending=False).head(UNIVERSE_SIZE)

    # 1차 필터 (스냅샷만으로 빠르게 거르기)
    f1 = snap[
        (snap["value"] >= MIN_TRADING_VALUE)
        & (snap["close"] >= snap["high"] * CLOSE_TO_HIGH)
        & (snap["ret_pct"] / 100 >= DAILY_RET_MIN)
        & (snap["ret_pct"] / 100 <= DAILY_RET_MAX)
    ]
    print(f"[1차] 거래대금/종가강도/등락폭 통과: {len(f1)} 종목")

    # 2차: 신고가 + 거래량 폭증
    results = []
    for ticker in f1.index:
        hist = fetch_60d_history(ticker, date, days=120)
        if hist.empty or len(hist) < HIGH_WINDOW:
            continue
        hist_60 = hist.iloc[-HIGH_WINDOW:]
        high_60 = hist_60["high"].max()
        avg_vol_60 = hist_60["volume"].mean()
        today = hist.iloc[-1]

        cond_high = today["close"] >= high_60
        cond_vol = today["volume"] >= avg_vol_60 * VOLUME_MULTIPLIER

        if cond_high and cond_vol:
            results.append({
                "ticker": ticker,
                "name": stock.get_market_ticker_name(ticker),
                "close": int(today["close"]),
                "high": int(today["high"]),
                "ret_pct": round(today["close"] / hist.iloc[-2]["close"] * 100 - 100, 2),
                "value_억": round(today["value"] / 1e8, 0),
                "vol_ratio": round(today["volume"] / avg_vol_60, 2),
                "close_to_high": round(today["close"] / today["high"], 3),
                "high_60": int(high_60),
                "is_high_break": today["close"] >= high_60,
            })

    out = pd.DataFrame(results)
    if out.empty:
        return out
    out = out.sort_values("value_억", ascending=False).reset_index(drop=True)
    return out


def main():
    today = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().strftime("%Y%m%d")
    print(f"\n=== 종가 베팅 스크리너 ({today}) ===\n")
    result = screen(today)
    if result.empty:
        print("조건 충족 종목 없음.")
        return

    print(f"\n>> 5대 조건 충족 종목 {len(result)}개 <<\n")
    if tabulate:
        print(tabulate(result, headers="keys", tablefmt="pretty", showindex=False))
    else:
        print(result.to_string(index=False))

    # 거래대금 1위 = 대장주 후보
    print(f"\n>> 대장주 후보 (거래대금 1위): {result.iloc[0]['name']} "
          f"({result.iloc[0]['ticker']}, {result.iloc[0]['value_억']:.0f}억) <<")

    out_path = f"screen_{today}.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
