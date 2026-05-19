"""
종가 베팅 시그널 엔진 & 백테스트
==============================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional

import numpy as np
import pandas as pd


# ----- 파라미터 -----------------------------------------------------------

@dataclass
class Params:
    # 5대 조건 임계치
    min_value: float = 5e10               # 거래대금 (원)
    volume_mult: float = 3.0              # 60일 평균 거래량 배수
    high_window: int = 60                 # 신고가 윈도우 (영업일)
    close_to_high: float = 0.97           # 종가/고가 비율
    daily_ret_min: float = 0.05           # 최소 일 등락률
    daily_ret_max: float = 0.25           # 최대 일 등락률 (이격 과대 제외)
    require_score: int = 5                # 최소 충족 조건 개수 (1~5)

    # 청산 규칙
    stop_loss: Optional[float] = -0.03    # 손절 (-3%). None 또는 0이면 손절 없음.
    take_profit: Optional[float] = None   # 익절 (None=익일 종가 청산)
    exit_at: str = "close"                # "open", "close", "high"

    # 유니버스
    top_n_by_cap: int = 300               # 시총 상위 N (Universe)
    top_k_per_day: int = 5                # 일별 시그널 종목 중 거래대금 상위 K개만 거래

    # 거래 비용 (라운드 트립)
    cost_per_trade: float = 0.003         # 0.3% (수수료+세금+슬리피지 추정)


# ----- 시그널 계산 --------------------------------------------------------

def add_signals(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    if df.empty or len(df) < p.high_window + 2:
        return df.iloc[0:0]
    out = df.copy()
    out["high_n"] = out["high"].rolling(p.high_window).max()
    out["vol_avg_n"] = out["volume"].rolling(p.high_window).mean()
    out["ret_1d"] = out["close"].pct_change()

    out["c1_high"] = out["close"] >= out["high_n"]
    out["c2_vol"] = out["volume"] >= out["vol_avg_n"] * p.volume_mult
    out["c3_value"] = out["value"] >= p.min_value
    out["c4_close_strength"] = out["close"] >= out["high"] * p.close_to_high
    out["c5_ret_band"] = (out["ret_1d"] >= p.daily_ret_min) & (out["ret_1d"] <= p.daily_ret_max)

    out["score"] = (
        out["c1_high"].astype(int)
        + out["c2_vol"].astype(int)
        + out["c3_value"].astype(int)
        + out["c4_close_strength"].astype(int)
        + out["c5_ret_band"].astype(int)
    )
    out["signal"] = out["score"] >= p.require_score
    return out


# ----- 백테스트 -----------------------------------------------------------

def backtest(
    data: dict[str, pd.DataFrame],
    business_days: list[str],
    p: Params,
) -> pd.DataFrame:
    """data: ticker -> OHLCV DataFrame (with signal columns)."""

    bd = pd.to_datetime(business_days)

    # 일별 시그널 후보 수집
    trades = []
    for i, day in enumerate(bd[:-1]):
        next_day = bd[i + 1]
        candidates = []
        for t, df in data.items():
            if day not in df.index or next_day not in df.index:
                continue
            row = df.loc[day]
            if row.get("signal", False):
                candidates.append((t, row["value"], row))
        if not candidates:
            continue

        # 거래대금 상위 K개 선택
        candidates.sort(key=lambda x: x[1], reverse=True)
        chosen = candidates[: p.top_k_per_day]

        for rank, (t, _v, row) in enumerate(chosen):
            df = data[t]
            nxt = df.loc[next_day]
            entry = float(row["close"])
            next_open = float(nxt["open"])
            next_low = float(nxt["low"])
            next_high = float(nxt["high"])
            next_close = float(nxt["close"])

            # 손절 없음 처리: stop_loss가 None 또는 0이면 손절 미적용
            use_stop = p.stop_loss is not None and p.stop_loss < 0
            stop_price = entry * (1 + p.stop_loss) if use_stop else None
            tp_price = entry * (1 + p.take_profit) if p.take_profit else None

            # 청산 순위: stop > tp > exit_at
            if use_stop and next_low <= stop_price:
                exit_price = stop_price
                exit_reason = "stop"
            elif tp_price is not None and next_high >= tp_price:
                exit_price = tp_price
                exit_reason = "tp"
            else:
                exit_price = {"open": next_open, "close": next_close, "high": next_high}[p.exit_at]
                exit_reason = p.exit_at

            gross = (exit_price - entry) / entry
            net = gross - p.cost_per_trade

            trades.append({
                "entry_date": day,
                "exit_date": next_day,
                "ticker": t,
                "rank": rank + 1,          # 1=대장주
                "entry": entry,
                "exit": exit_price,
                "gross": gross,
                "net": net,
                "gap": (next_open - entry) / entry,
                "max_gain": (next_high - entry) / entry,
                "exit_reason": exit_reason,
                "score": int(row["score"]),
            })

    return pd.DataFrame(trades)


# ----- TP1/TP2 분할 청산 (신규) ------------------------------------------

def backtest_tiered(
    data: dict[str, pd.DataFrame],
    business_days: list[str],
    p: Params,
    hold_days: int = 30,
    tp1_pct: float = 1.0,      # +100%
    tp2_pct: float = 2.0,      # +200%
    tp1_size: float = 0.5,
    tp2_size: float = 0.5,
) -> pd.DataFrame:
    """TP1/TP2 분할 청산 + 만기일 시초가 청산.

    절차:
      1) 진입 = 시그널 발생일 종가
      2) 보유 기간 (hold_days = 달력일 기준) 동안 매일 고가 체크
         예) hold_days=30 → 진입일 + 30 달력일 후 청산 (해당일이 휴장이면 다음 영업일)
      3) 고가 >= TP1_price → tp1_size 청산 at TP1
      4) 추가로 고가 >= TP2_price → tp2_size 청산 at TP2
      5) 만기일 시초가에 남은 잔량 청산
    """
    bd = pd.to_datetime(business_days)
    trades = []

    for i, day in enumerate(bd):
        # 달력일 기준 청산일: day + hold_days 달력일
        if hold_days == 1:
            # 익일 = 다음 영업일
            if i + 1 >= len(bd):
                continue
            exit_day = bd[i + 1]
        else:
            target = day + pd.Timedelta(days=hold_days)
            # target 이후 첫 영업일
            future_bd = bd[bd >= target]
            if len(future_bd) == 0:
                continue
            exit_day = future_bd[0]

        # 시그널 후보 수집
        candidates = []
        for t, df in data.items():
            if day not in df.index or exit_day not in df.index:
                continue
            row = df.loc[day]
            if row.get("signal", False):
                candidates.append((t, row["value"], row))
        if not candidates:
            continue
        candidates.sort(key=lambda x: x[1], reverse=True)
        chosen = candidates[: p.top_k_per_day]

        for rank, (t, _v, row) in enumerate(chosen):
            df = data[t]
            entry = float(row["close"])
            tp1_price = entry * (1 + tp1_pct)
            tp2_price = entry * (1 + tp2_pct)

            hold_window = df.loc[day:exit_day]
            if len(hold_window) < 2:
                continue

            tp1_hit = False
            tp2_hit = False
            tp1_date = None
            tp2_date = None

            # 진입일 다음 날부터 만기일까지 일별 고가 체크
            for idx, bar in hold_window.iloc[1:].iterrows():
                if not tp1_hit and bar["high"] >= tp1_price:
                    tp1_hit = True
                    tp1_date = idx
                if tp1_hit and not tp2_hit and bar["high"] >= tp2_price:
                    tp2_hit = True
                    tp2_date = idx
                    break

            # 만기일 시초가
            exit_open = float(df.loc[exit_day, "open"])
            exit_open_ret = (exit_open - entry) / entry

            # 가중 평균 수익
            remaining = 1.0
            total_gross = 0.0
            if tp1_hit:
                total_gross += tp1_size * tp1_pct
                remaining -= tp1_size
                if tp2_hit:
                    total_gross += tp2_size * tp2_pct
                    remaining -= tp2_size
            if remaining > 0:
                total_gross += remaining * exit_open_ret

            net = total_gross - p.cost_per_trade

            # 청산 사유
            if tp2_hit:
                reason = "TP1+TP2+잔량 시초"
            elif tp1_hit:
                reason = "TP1+잔량 시초"
            else:
                reason = "만기 시초가"

            trades.append({
                "entry_date": day,
                "exit_date": exit_day,
                "ticker": t,
                "rank": rank + 1,
                "entry": entry,
                "exit": exit_open,
                "exit_open_ret": exit_open_ret,
                "tp1_hit": tp1_hit,
                "tp2_hit": tp2_hit,
                "tp1_date": tp1_date,
                "tp2_date": tp2_date,
                "gross": total_gross,
                "net": net,
                "hold_days": hold_days,
                "exit_reason": reason,
                "score": int(row["score"]),
                # 비교용 — 익일 종가 청산 시 net (참고치)
                "gap": (float(df.loc[exit_day, "open"]) - entry) / entry,
                "max_gain": ((hold_window["high"].max() - entry) / entry),
            })

    return pd.DataFrame(trades)


# ----- 성과 지표 ---------------------------------------------------------

def metrics(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {"n": 0}
    n = len(trades)
    wins = trades["net"] > 0
    win_rate = wins.mean()
    mean_ret = trades["net"].mean()
    median_ret = trades["net"].median()
    std_ret = trades["net"].std()
    avg_win = trades.loc[wins, "net"].mean() if wins.any() else 0.0
    avg_loss = trades.loc[~wins, "net"].mean() if (~wins).any() else 0.0
    pf = (trades.loc[wins, "net"].sum() / -trades.loc[~wins, "net"].sum()) if (~wins).any() else float("inf")
    expectancy = win_rate * (avg_win or 0) + (1 - win_rate) * (avg_loss or 0)
    sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0.0

    # 누적 수익 (일별 equal-weight)
    daily = trades.groupby("entry_date")["net"].mean()
    equity = (1 + daily).cumprod()
    mdd = (equity / equity.cummax() - 1).min() if not equity.empty else 0.0
    total_ret = equity.iloc[-1] - 1 if not equity.empty else 0.0

    return {
        "n": n,
        "win_rate": float(win_rate),
        "mean_ret": float(mean_ret),
        "median_ret": float(median_ret),
        "std_ret": float(std_ret),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "profit_factor": float(pf) if pf != float("inf") else 999.0,
        "expectancy": float(expectancy),
        "sharpe": float(sharpe),
        "mdd": float(mdd),
        "total_ret": float(total_ret),
    }
