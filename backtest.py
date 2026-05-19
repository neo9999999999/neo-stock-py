"""
종가 베팅 전략 백테스트 스크립트
=================================
주도주 종가 베팅 전략의 통계적 검증.

5대 조건:
  1) 핵심 테마 (외부 입력 필요 — 본 스크립트에서는 거래대금 상위로 근사)
  2) 거래대금 상위 + 60일 평균의 3배 이상
  3) 신고가 (60일 신고가)
  4) 장 막판 매수세 (종가 ≥ 당일고가 × 0.97)
  5) 대장주 (테마 내 1등 — 거래대금 1위로 근사)

진입: 당일 종가 / 청산: 익일 종가 (또는 -3% 손절)

요구 사항:
  pip install pykrx pandas numpy matplotlib
"""

import argparse
import datetime as dt
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

try:
    from pykrx import stock
except ImportError as exc:
    raise SystemExit(
        "pykrx 가 필요합니다. 설치: pip install pykrx pandas numpy matplotlib"
    ) from exc


# ----- 파라미터 ---------------------------------------------------------------

@dataclass
class Params:
    start: str = "20250101"
    end: str = "20260517"
    market: str = "KOSPI"
    min_trading_value: float = 5e10        # 500억원
    volume_multiplier: float = 3.0         # 60일 평균 대비
    high_window: int = 60                  # 신고가 윈도우
    close_to_high_ratio: float = 0.97      # 종가 ≥ 고가×0.97
    daily_return_min: float = 0.05         # 최소 일 등락률 5%
    daily_return_max: float = 0.25         # 최대 일 등락률 25% (이격 과대 제외)
    stop_loss: float = -0.03               # -3% 손절
    top_n_by_value: int = 10               # 거래대금 상위 N
    universe_size: int = 200               # 시총 상위 N개로 유니버스 한정


# ----- 데이터 로더 -----------------------------------------------------------

def get_universe(date: str, n: int) -> list[str]:
    """해당 날짜의 시가총액 상위 n개 종목 코드."""
    cap = stock.get_market_cap_by_ticker(date, market="ALL")
    cap = cap.sort_values("시가총액", ascending=False).head(n)
    return cap.index.tolist()


def load_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """일별 OHLCV + 거래대금."""
    df = stock.get_market_ohlcv_by_date(start, end, ticker)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={"시가": "open", "고가": "high", "저가": "low",
                            "종가": "close", "거래량": "volume", "거래대금": "value"})
    df.index = pd.to_datetime(df.index)
    return df


# ----- 시그널 계산 -----------------------------------------------------------

def compute_signals(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """5대 조건 점검 (대장주 조건은 cross-sectional이라 별도 처리)."""
    if df.empty:
        return df

    out = df.copy()
    out["high_60"] = out["high"].rolling(p.high_window).max()
    out["volume_avg_60"] = out["volume"].rolling(p.high_window).mean()
    out["return_1d"] = out["close"].pct_change()

    out["cond_high_break"] = out["close"] >= out["high_60"]
    out["cond_volume_surge"] = out["volume"] >= out["volume_avg_60"] * p.volume_multiplier
    out["cond_value"] = out["value"] >= p.min_trading_value
    out["cond_close_strength"] = out["close"] >= out["high"] * p.close_to_high_ratio
    out["cond_return_band"] = (
        (out["return_1d"] >= p.daily_return_min)
        & (out["return_1d"] <= p.daily_return_max)
    )

    out["signal_score"] = (
        out["cond_high_break"].astype(int)
        + out["cond_volume_surge"].astype(int)
        + out["cond_value"].astype(int)
        + out["cond_close_strength"].astype(int)
        + out["cond_return_band"].astype(int)
    )
    return out


# ----- 백테스트 -------------------------------------------------------------

def backtest(p: Params) -> pd.DataFrame:
    """각 영업일마다 시그널 종목을 찾고 익일 종가까지 보유."""
    # 영업일 리스트 (KOSPI 인덱스 기준)
    kospi = stock.get_index_ohlcv_by_date(p.start, p.end, "1001")
    business_days = kospi.index.strftime("%Y%m%d").tolist()

    # 유니버스를 시작일 기준으로 한 번만 잡고 사용 (단순화)
    universe = get_universe(business_days[0], p.universe_size)

    # 종목별 데이터 사전 로딩
    print(f"로딩 중: {len(universe)} 종목 × {len(business_days)} 영업일")
    data: dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(universe, 1):
        if i % 25 == 0:
            print(f"  진행률 {i}/{len(universe)}")
        df = load_ohlcv(ticker, p.start, p.end)
        if not df.empty:
            data[ticker] = compute_signals(df, p)

    # 매일 시그널 점검
    trades = []
    for i, day in enumerate(business_days[:-1]):
        next_day = business_days[i + 1]
        candidates = []
        for ticker, df in data.items():
            day_ts = pd.Timestamp(day)
            if day_ts not in df.index:
                continue
            row = df.loc[day_ts]
            if row["signal_score"] >= 5:
                candidates.append((ticker, row["value"], row))

        if not candidates:
            continue

        # 거래대금 상위 N개만 선택 + 1위는 "대장주"로 가중
        candidates.sort(key=lambda x: x[1], reverse=True)
        chosen = candidates[: p.top_n_by_value]

        for ticker, value, row in chosen:
            df = data[ticker]
            next_ts = pd.Timestamp(next_day)
            if next_ts not in df.index:
                continue
            entry = row["close"]
            nxt = df.loc[next_ts]
            next_open = nxt["open"]
            next_low = nxt["low"]
            next_close = nxt["close"]
            next_high = nxt["high"]

            # 손절 시뮬레이션: 익일 저가가 손절가 이탈 시 손절가 청산
            stop_price = entry * (1 + p.stop_loss)
            if next_low <= stop_price:
                exit_price = stop_price
                exit_reason = "stop_loss"
            else:
                exit_price = next_close
                exit_reason = "close"

            ret = (exit_price - entry) / entry
            gap_ret = (next_open - entry) / entry
            high_ret = (next_high - entry) / entry

            trades.append({
                "entry_date": day,
                "exit_date": next_day,
                "ticker": ticker,
                "entry": entry,
                "exit": exit_price,
                "ret": ret,
                "gap_ret": gap_ret,
                "high_ret": high_ret,
                "exit_reason": exit_reason,
                "is_leader": ticker == chosen[0][0],
            })

    return pd.DataFrame(trades)


# ----- 성과 분석 ------------------------------------------------------------

def summarize(trades: pd.DataFrame) -> None:
    if trades.empty:
        print("거래 없음.")
        return

    n = len(trades)
    win_rate = (trades["ret"] > 0).mean()
    avg_ret = trades["ret"].mean()
    median_ret = trades["ret"].median()
    avg_win = trades.loc[trades["ret"] > 0, "ret"].mean()
    avg_loss = trades.loc[trades["ret"] <= 0, "ret"].mean()
    profit_factor = abs(
        trades.loc[trades["ret"] > 0, "ret"].sum()
        / trades.loc[trades["ret"] <= 0, "ret"].sum()
    ) if (trades["ret"] <= 0).any() else float("inf")
    expectancy = win_rate * (avg_win or 0) + (1 - win_rate) * (avg_loss or 0)

    print("\n===== 전체 결과 =====")
    print(f"총 거래 수:       {n}")
    print(f"승률:             {win_rate:.2%}")
    print(f"평균 수익률:      {avg_ret:.2%}")
    print(f"중앙값 수익률:    {median_ret:.2%}")
    print(f"평균 이익:        {avg_win:.2%}")
    print(f"평균 손실:        {avg_loss:.2%}")
    print(f"수익비(PF):       {profit_factor:.2f}")
    print(f"기댓값:           {expectancy:.2%}")
    print(f"갭상승 평균:      {trades['gap_ret'].mean():.2%}")
    print(f"당일 최고 평균:   {trades['high_ret'].mean():.2%}")

    print("\n===== 대장주(거래대금 1위) vs 비대장주 =====")
    for is_leader, label in [(True, "대장주"), (False, "비대장주")]:
        sub = trades[trades["is_leader"] == is_leader]
        if sub.empty:
            continue
        print(f"[{label}] 거래수 {len(sub)}, "
              f"승률 {(sub['ret']>0).mean():.2%}, "
              f"평균 {sub['ret'].mean():.2%}")


# ----- 메인 ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20250101")
    ap.add_argument("--end", default="20260517")
    ap.add_argument("--out", default="trades.csv")
    args = ap.parse_args()

    p = Params(start=args.start, end=args.end)
    trades = backtest(p)
    trades.to_csv(args.out, index=False, encoding="utf-8-sig")
    summarize(trades)
    print(f"\n거래 내역 저장: {args.out}")


if __name__ == "__main__":
    main()
