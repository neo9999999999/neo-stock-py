"""
사례 학습 기반 v2 시그널 엔진
=============================
40개 사례 분석 결과 도출된 새 시그널 로직:

1. 거래대금 ≥ 50억
2. 거래량 ≥ 60일 평균 × 3배
3. 종가가 20일선 · 60일선 위 (추세 종목)
4. 종가/고가 ≥ 0.92 (장 후반 매수세)
5. 당일 등락률 ≥ 5% OR 20일 누적 ≥ 15% (강한 추세)
"""


from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class ParamsV2:
    min_value: float = 5e9                  # 거래대금 50억
    volume_mult: float = 3.0                # 거래량 60일 ×3
    close_to_high: float = 0.92             # 종가/고가
    daily_ret_min: float = 0.05             # 당일 등락률
    ret_20d_min: float = 0.15               # 20일 누적 등락률 (OR 조건)
    ma_window_short: int = 20
    ma_window_long: int = 60
    require_score: int = 4

    stop_loss: Optional[float] = -0.03
    take_profit: Optional[float] = None
    exit_at: str = "close"
    top_k_per_day: int = 5
    cost_per_trade: float = 0.003


def add_signals_v2(df: pd.DataFrame, p: ParamsV2) -> pd.DataFrame:
    if df.empty or len(df) < p.ma_window_long + 2:
        return df.iloc[0:0]
    out = df.copy()

    # 이동평균
    out["ma20"] = out["close"].rolling(p.ma_window_short).mean()
    out["ma60"] = out["close"].rolling(p.ma_window_long).mean()
    out["vol_avg_60"] = out["volume"].rolling(60).mean()

    # 등락률
    out["ret_1d"] = out["close"].pct_change()
    out["ret_20d"] = out["close"].pct_change(p.ma_window_short)

    # 5대 조건 (v2)
    out["c1_value"] = out["value"] >= p.min_value
    out["c2_vol"] = out["volume"] >= out["vol_avg_60"] * p.volume_mult
    out["c3_above_ma"] = (out["close"] > out["ma20"]) & (out["close"] > out["ma60"])
    out["c4_close_strength"] = out["close"] >= out["high"] * p.close_to_high
    # 강한 추세: 당일 큰 상승 OR 20일 누적 큰 상승
    out["c5_momentum"] = (out["ret_1d"] >= p.daily_ret_min) | (out["ret_20d"] >= p.ret_20d_min)

    out["score"] = (
        out["c1_value"].astype(int)
        + out["c2_vol"].astype(int)
        + out["c3_above_ma"].astype(int)
        + out["c4_close_strength"].astype(int)
        + out["c5_momentum"].astype(int)
    )
    out["signal"] = out["score"] >= p.require_score

    # 시장 환경 필터를 위해 high 별도 컬럼 유지
    out["high_n"] = out["close"]  # 호환용
    out["vol_avg_n"] = out["vol_avg_60"]

    return out


def backtest_v2(
    data: dict[str, pd.DataFrame],
    business_days: list[str],
    p: ParamsV2,
) -> pd.DataFrame:
    """v2 시그널로 백테스트. 익일 종가 청산."""
    bd = pd.to_datetime(business_days)
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

            use_stop = p.stop_loss is not None and p.stop_loss < 0
            stop_price = entry * (1 + p.stop_loss) if use_stop else None
            tp_price = entry * (1 + p.take_profit) if p.take_profit else None

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
                "rank": rank + 1,
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


def metrics_v2(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"n": 0}
    n = len(trades)
    wins = trades["net"] > 0
    win_rate = wins.mean()
    mean_ret = trades["net"].mean()
    std_ret = trades["net"].std()
    avg_win = trades.loc[wins, "net"].mean() if wins.any() else 0.0
    avg_loss = trades.loc[~wins, "net"].mean() if (~wins).any() else 0.0
    pf = (trades.loc[wins, "net"].sum() / -trades.loc[~wins, "net"].sum()) if (~wins).any() else float("inf")
    expectancy = win_rate * (avg_win or 0) + (1 - win_rate) * (avg_loss or 0)
    sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0.0

    daily = trades.groupby("entry_date")["net"].mean()
    equity = (1 + daily).cumprod()
    mdd = (equity / equity.cummax() - 1).min() if not equity.empty else 0.0
    total_ret = equity.iloc[-1] - 1 if not equity.empty else 0.0

    return {
        "n": n, "win_rate": float(win_rate),
        "mean_ret": float(mean_ret), "expectancy": float(expectancy),
        "profit_factor": float(pf) if pf != float("inf") else 999.0,
        "sharpe": float(sharpe), "mdd": float(mdd),
        "total_ret": float(total_ret),
    }
