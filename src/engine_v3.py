"""
사례 유사도 기반 시그널 엔진 v3
============================
사례 39개의 Q25~Q75 핵심 영역에 들어가는 종목만 추천.
양보다 질 — 5년에 100~500건 정도만 잡히는 빡빡한 필터.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from case_similarity import build_profile, CaseProfile

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ParamsV3:
    min_similarity: float = 0.6     # 사례 유사도 임계치 (0~1)
    top_k_per_day: int = 5
    stop_loss: float | None = -0.03
    take_profit: float | None = None
    exit_at: str = "close"
    cost_per_trade: float = 0.003


def add_signals_v3(df: pd.DataFrame, profile: CaseProfile,
                    p: ParamsV3) -> pd.DataFrame:
    """사례 프로파일 기반 시그널.

    각 행마다 9개 지표(당일/5일/20일 수익률, 거래대금, 거래대금배수, 거래량배수,
    종가/고가, 종가/60일고가, RSI) 계산 후 사례 Q25~Q75에 들면 1점,
    Q10~Q90에 들면 0.5점, 평균 점수 ≥ min_similarity면 signal=True.
    """
    if df.empty or len(df) < 62:
        return df.iloc[0:0]
    out = df.copy()

    # 지표 계산
    out["ret_1d"] = out["close"].pct_change()
    out["ret_5d"] = out["close"].pct_change(5)
    out["ret_20d"] = out["close"].pct_change(20)

    out["vol_avg_60"] = out["volume"].rolling(60).mean()
    out["value_avg_60"] = out["value"].rolling(60).mean()
    out["high_60"] = out["high"].rolling(60).max()

    out["value_eok"] = out["value"] / 1e8
    out["volume_ratio_60d"] = out["volume"] / out["vol_avg_60"]
    out["value_ratio_60d"] = out["value"] / out["value_avg_60"]
    out["close_to_day_high"] = out["close"] / out["high"]
    out["close_to_high60"] = out["close"] / out["high_60"]

    # RSI (14)
    delta = out["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi_14"] = 100 - (100 / (1 + rs))

    # 각 지표별 점수 (벡터화)
    ind_cols = list(profile.indicators.keys())
    score_total = pd.Series(0.0, index=out.index)
    score_count = pd.Series(0, index=out.index)

    for col in ind_cols:
        if col not in out.columns:
            continue
        prof = profile.indicators[col]
        vals = out[col]
        is_core = (vals >= prof["q25"]) & (vals <= prof["q75"])
        is_wide = (vals >= prof["q10"]) & (vals <= prof["q90"])
        col_score = pd.Series(0.0, index=out.index)
        col_score[is_wide] = 0.5
        col_score[is_core] = 1.0
        score_total += col_score.fillna(0)
        score_count += vals.notna().astype(int)
        out[f"sim_{col}"] = col_score

    # 정규화 (지표 개수로 나눔)
    out["similarity"] = score_total / score_count.clip(lower=1)
    out["signal"] = out["similarity"] >= p.min_similarity

    return out


def backtest_v3(
    data: dict[str, pd.DataFrame],
    business_days: list[str],
    p: ParamsV3,
    hold_days: int = 1,
) -> pd.DataFrame:
    """v3 시그널 + 보유 기간 N일."""
    bd = pd.to_datetime(business_days)
    trades = []

    for i, day in enumerate(bd):
        if hold_days == 1:
            if i + 1 >= len(bd): continue
            exit_day = bd[i + 1]
        else:
            target = day + pd.Timedelta(days=hold_days)
            future = bd[bd >= target]
            if len(future) == 0: continue
            exit_day = future[0]

        # 시그널 후보
        candidates = []
        for t, df in data.items():
            if day not in df.index or exit_day not in df.index:
                continue
            row = df.loc[day]
            if row.get("signal", False):
                candidates.append((t, row["similarity"], row))
        if not candidates:
            continue
        # 유사도 높은 순
        candidates.sort(key=lambda x: x[1], reverse=True)
        chosen = candidates[: p.top_k_per_day]

        for rank, (t, sim, row) in enumerate(chosen):
            df = data[t]
            entry = float(row["close"])
            nxt = df.loc[exit_day]
            next_open = float(nxt["open"])
            next_low = float(nxt["low"])
            next_high = float(nxt["high"])
            next_close = float(nxt["close"])

            use_stop = p.stop_loss is not None and p.stop_loss < 0
            stop_price = entry * (1 + p.stop_loss) if use_stop else None
            tp_price = entry * (1 + p.take_profit) if p.take_profit else None

            if use_stop and hold_days == 1 and next_low <= stop_price:
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
                "exit_date": exit_day,
                "ticker": t,
                "rank": rank + 1,
                "entry": entry,
                "exit": exit_price,
                "gross": gross,
                "net": net,
                "similarity": float(sim),
                "exit_reason": exit_reason,
                "score": int(row.get("similarity", 0) * 10),
                "gap": (next_open - entry) / entry,
                "max_gain": (next_high - entry) / entry,
            })

    return pd.DataFrame(trades)


if __name__ == "__main__":
    import json, time
    from data_loader import business_days, get_ohlcv
    from engine import metrics

    profile = build_profile()
    print(f"=== v3 사례 유사도 시그널 백테스트 ===")
    print(f"사례 프로파일: {len(profile.indicators)}개 지표")

    with open(ROOT / "data" / "universe_final.txt") as f:
        univ = [l.strip() for l in f if l.strip()]
    print(f"유니버스: {len(univ)}개")

    raw = {}
    t0 = time.time()
    for t in univ:
        df = get_ohlcv(t, "20200601", "20260517")
        if not df.empty and len(df) >= 80:
            raw[t] = df
    print(f"로드: {len(raw)}종목, {time.time()-t0:.1f}s")

    # 다양한 임계치 + 보유 기간
    bd = business_days("20210101", "20260517")
    print(f"\n=== 임계치별 시그널 개수 ===")
    for thr in [0.5, 0.6, 0.7, 0.8]:
        p = ParamsV3(min_similarity=thr, top_k_per_day=5)
        sig_data = {t: add_signals_v3(df, profile, p) for t, df in raw.items()}
        total_sig = sum(d["signal"].sum() for d in sig_data.values())
        print(f"  유사도 ≥{thr}: 총 {total_sig:,}개 시그널 (5년)")

    # 메인 백테스트: 유사도 0.6, 1일 보유
    print(f"\n=== v3 (유사도 ≥0.6) + 보유 기간별 ===")
    p = ParamsV3(min_similarity=0.6, top_k_per_day=5, stop_loss=-0.03)
    sig_data = {t: add_signals_v3(df, profile, p) for t, df in raw.items()}

    for hold in [1, 5, 10, 20, 30]:
        t_df = backtest_v3(sig_data, bd, p, hold_days=hold)
        m = metrics(t_df)
        if m.get("n", 0) == 0:
            print(f"  {hold:>2}일: 거래 0건")
            continue
        print(f"  {hold:>2}일: 거래 {m['n']:>4}건  승률 {m['win_rate']*100:>5.1f}%  "
              f"평균 {m['mean_ret']*100:>+6.2f}%  PF {m['profit_factor']:>4.2f}  "
              f"샤프 {m['sharpe']:>4.2f}  누적 {m['total_ret']*100:>+8.1f}%")
