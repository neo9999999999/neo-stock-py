"""
보조지표 효과 검증 (전체 기간 OOS)
==================================
기존 v3.8 OOS 시그널 (history_signals_combined.parquet)에 보조지표를 합쳐,
각 지표 값별 30/60/90/120일 보유 수익률을 비교한다.

테스트 지표:
  - RSI(14): 이미 사용 중. 추가 가치 확인.
  - Stochastic %K %D
  - Bollinger Bands position (%b) — 가격이 BB 어디쯤
  - Envelope position — 가격이 MA 대비 어디쯤
  - Ichimoku 전환선/기준선 위치
  - MACD signal vs line
  - ADX(14) — 추세 강도

각 지표를 시그널 발생 시점에 측정하고, 시그널들을 그 지표값으로 5분위
(quintile) 버킷 → 각 버킷의 30/60/90/120일 평균/중앙/승률 측정.
최적 지표 = top-bottom 격차 큰 지표.

결과: results/indicator_validation.csv + results/indicator_buckets.parquet
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import warnings
warnings.filterwarnings("ignore")

import time
import numpy as np
import pandas as pd

from data_loader import get_ohlcv

ROOT = Path(__file__).resolve().parent.parent


# ----- 지표 계산 -----------------------------------------------------------

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV → 보조지표들."""
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]

    # RSI(14) — Wilder
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["rsi"] = 100 - 100 / (1 + rs)

    # Stochastic %K(14) %D(3)
    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    pct_k = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
    out["stoch_k"] = pct_k
    out["stoch_d"] = pct_k.rolling(3).mean()

    # Bollinger Bands (20, 2)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_up = bb_mid + 2 * bb_std
    bb_lo = bb_mid - 2 * bb_std
    out["bb_pct_b"] = (close - bb_lo) / (bb_up - bb_lo).replace(0, np.nan)
    out["bb_width"] = (bb_up - bb_lo) / bb_mid.replace(0, np.nan)

    # Envelope: close / MA20 - 1 (이격도)
    ma20 = close.rolling(20).mean()
    out["env_ma20"] = close / ma20 - 1
    ma60 = close.rolling(60).mean()
    out["env_ma60"] = close / ma60 - 1

    # Ichimoku 전환선(9), 기준선(26)
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    out["ichi_tenkan"] = close / tenkan - 1
    out["ichi_kijun"] = close / kijun - 1
    # 구름대: senkou A,B (전형적 26일 forward shift, 여기선 단순 비교)
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (high.rolling(52).max() + low.rolling(52).min()) / 2
    cloud_top = np.maximum(senkou_a, senkou_b)
    cloud_bot = np.minimum(senkou_a, senkou_b)
    out["ichi_above_cloud"] = (close > cloud_top).astype(int)

    # MACD (12,26,9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_sig = macd_line.ewm(span=9, adjust=False).mean()
    out["macd_hist"] = macd_line - macd_sig
    out["macd_hist_norm"] = out["macd_hist"] / close      # 가격 대비 정규화

    # ADX(14) — Wilder
    up_move = high.diff()
    dn_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > dn_move) & (up_move > 0), up_move, 0),
                          index=df.index)
    minus_dm = pd.Series(np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0),
                           index=df.index)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    out["adx"] = dx.ewm(alpha=1/14, adjust=False).mean()

    return out


# ----- 메인 ---------------------------------------------------------------

def main():
    print("=== 보조지표 검증 — combined parquet 기준 ===", flush=True)
    sig = pd.read_parquet(ROOT / "results" / "history_signals_combined.parquet")
    print(f"전체 시그널: {len(sig):,}", flush=True)
    sig["date"] = pd.to_datetime(sig["date"])

    # 시총 5천억+ + 시장필터 (실전 조건)
    sig = sig[(sig["marcap"] >= 5e11) & sig["kospi_above"]].copy()
    print(f"5천억+ + 시장필터: {len(sig):,}", flush=True)

    indicator_cols = ["rsi", "stoch_k", "stoch_d", "bb_pct_b", "bb_width",
                       "env_ma20", "env_ma60", "ichi_tenkan", "ichi_kijun",
                       "ichi_above_cloud", "macd_hist_norm", "adx"]

    # ticker별로 처리
    tickers = sig["ticker"].unique()
    print(f"고유 종목: {len(tickers):,}", flush=True)

    enriched = []
    t0 = time.time()
    for i, code in enumerate(tickers, 1):
        if i % 50 == 0:
            print(f"  {i}/{len(tickers)}  enriched={len(enriched):,}  ({time.time()-t0:.0f}s)",
                  flush=True)
        try:
            df = get_ohlcv(code, "20200601", "20260520")
        except Exception:
            continue
        if df.empty or len(df) < 60:
            continue
        ind = compute_indicators(df)
        # 이 종목의 시그널들
        s = sig[sig["ticker"] == code].copy()
        for _, row in s.iterrows():
            if row["date"] not in ind.index:
                continue
            r = ind.loc[row["date"]]
            rec = {
                "date": row["date"],
                "ticker": code,
                "name": row["name"],
                "similarity": row["similarity"],
                "ret_d30": row.get("ret_d30"),
                "ret_d60": row.get("ret_d60"),
                "ret_d90": row.get("ret_d90"),
                "ret_d120": row.get("ret_d120"),
            }
            for col in indicator_cols:
                rec[col] = float(r.get(col, np.nan))
            enriched.append(rec)

    enriched_df = pd.DataFrame(enriched)
    enriched_df.to_parquet(ROOT / "results" / "indicator_buckets.parquet")
    print(f"\n저장: indicator_buckets.parquet ({len(enriched_df):,} rows)", flush=True)

    # ----- 5분위 버킷 분석 -----
    print(f"\n=== 보조지표별 5분위 (Q1=최저, Q5=최고) ===", flush=True)
    summary_rows = []
    for col in indicator_cols:
        valid = enriched_df[enriched_df[col].notna()].copy()
        if len(valid) < 100:
            continue
        # ichi_above_cloud는 0/1이므로 2버킷
        try:
            if col == "ichi_above_cloud":
                valid["bucket"] = valid[col].astype(int)
                buckets = sorted(valid["bucket"].unique())
            else:
                valid["bucket"] = pd.qcut(valid[col], 5, labels=[1, 2, 3, 4, 5], duplicates="drop")
                buckets = [1, 2, 3, 4, 5]
        except Exception:
            continue
        for hold in [30, 60, 90, 120]:
            rcol = f"ret_d{hold}"
            for b in buckets:
                sub = valid[valid["bucket"] == b]
                vals = sub[rcol].dropna()
                if len(vals) == 0:
                    continue
                summary_rows.append({
                    "indicator": col,
                    "bucket": int(b) if not pd.isna(b) else None,
                    "hold_days": hold,
                    "n": len(vals),
                    "mean_ret": float(vals.mean()),
                    "median_ret": float(vals.median()),
                    "win_rate": float((vals > 0).mean()),
                })

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(ROOT / "results" / "indicator_validation.csv", index=False)
    print(f"저장: indicator_validation.csv ({len(summary)} rows)", flush=True)

    # ----- 결과 출력 (90일 보유 기준) -----
    print(f"\n=== 90일 보유 기준 — Q1 vs Q5 격차 ===", flush=True)
    print(f"{'지표':<20}{'Q1 평균':>10}{'Q5 평균':>10}{'격차':>10}"
          f"{'Q1 승률':>10}{'Q5 승률':>10}", flush=True)
    h90 = summary[summary["hold_days"] == 90]
    indicator_summary = []
    for col in indicator_cols:
        rows = h90[h90["indicator"] == col]
        if rows.empty:
            continue
        q1 = rows[rows["bucket"] == 1]
        q5 = rows[rows["bucket"] == rows["bucket"].max()]
        if q1.empty or q5.empty:
            continue
        q1_m = q1["mean_ret"].iloc[0]
        q5_m = q5["mean_ret"].iloc[0]
        q1_w = q1["win_rate"].iloc[0]
        q5_w = q5["win_rate"].iloc[0]
        diff = q5_m - q1_m
        indicator_summary.append({
            "indicator": col,
            "q1_mean": q1_m, "q5_mean": q5_m, "diff": diff,
            "q1_win": q1_w, "q5_win": q5_w,
        })
        print(f"{col:<20}{q1_m*100:>+9.2f}%{q5_m*100:>+9.2f}%"
              f"{diff*100:>+9.2f}%{q1_w*100:>+9.1f}%{q5_w*100:>+9.1f}%", flush=True)

    # 차이 큰 순으로 정렬
    ranked = sorted(indicator_summary, key=lambda x: abs(x["diff"]), reverse=True)
    print(f"\n=== TOP 5 보조지표 (90일 Q5-Q1 격차 절대값) ===", flush=True)
    for r in ranked[:5]:
        direction = "Q5↑" if r["diff"] > 0 else "Q1↑ (역지표)"
        print(f"  {r['indicator']:<20} diff={r['diff']*100:+.2f}%  {direction}", flush=True)


if __name__ == "__main__":
    main()
