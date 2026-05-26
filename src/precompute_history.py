"""
추천 히스토리 사전 계산 (offline)
================================
1534종목 × 5년 × 3가지 profile mode 사전 계산 → parquet 저장.
Streamlit Cloud에서 페이지 로드 시 그냥 parquet 읽기만.

저장 파일:
  results/history_signals_combined.parquet
  results/history_signals_user39.parquet
  results/history_signals_oos.parquet

각 row:
  date, ticker, name, similarity, close, ret_1d, ret_20d, value_eok,
  vol_ratio, rsi, close_to_high,
  ret_d1, ret_d10, ret_d30, ret_d60, ret_d90, ret_d120,
  marcap (시총), kospi_above (시장필터 통과 여부)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import warnings
warnings.filterwarnings("ignore")

import time
import pandas as pd

from data_loader import get_ohlcv, get_index_ohlcv, get_krx_listing, get_name
from engine_v3 import ParamsV3, add_signals_v3
from case_similarity import build_profile, case_count

ROOT = Path(__file__).resolve().parent.parent
SIM_THRESHOLD = 0.6            # 앱 기본값과 동일. 필요 시 UI에서 필터링 가능


def compute_with_profile(profile_name: str, profile_func, market_above):
    print(f"\n=== {profile_name} ===", flush=True)
    p = ParamsV3(min_similarity=SIM_THRESHOLD)

    listing = get_krx_listing()
    code_to_marcap = dict(zip(listing["Code"], listing["Marcap"]))
    code_to_name = dict(zip(listing["Code"], listing["Name"]))

    with open(ROOT / "data" / "universe_final.txt") as f:
        univ = [l.strip() for l in f if l.strip()]

    rows = []
    t0 = time.time()

    if profile_name == "oos_yearly":
        profile_by_year = {}
        for y in range(2020, 2027):
            n = case_count(combined=True, asof_date=f"{y}-01-01")
            if n >= 50:
                profile_by_year[y] = build_profile(combined=True, asof_date=f"{y}-01-01")
            else:
                profile_by_year[y] = None
    else:
        single_profile = profile_func()

    for i, code in enumerate(univ, 1):
        if i % 200 == 0:
            print(f"  {i}/{len(univ)}  rows={len(rows):,}  ({time.time()-t0:.0f}s)",
                  flush=True)

        try:
            df = get_ohlcv(code, "20191001", "20260522")
        except Exception:
            continue
        if df.empty or len(df) < 80:
            continue

        if profile_name == "oos_yearly":
            triggered_dfs = []
            for y in range(2020, 2027):
                prof = profile_by_year.get(y)
                if prof is None:
                    continue
                sig_y = add_signals_v3(df, prof, p)
                mask = (sig_y["signal"]
                         & (sig_y.index >= f"{y}-01-01")
                         & (sig_y.index < f"{y+1}-01-01"))
                triggered_dfs.append(sig_y[mask])
            if not triggered_dfs:
                continue
            triggered = pd.concat(triggered_dfs)
        else:
            sig = add_signals_v3(df, single_profile, p)
            triggered = sig[sig["signal"] & (sig.index >= "2020-01-01")]

        if triggered.empty:
            continue

        # 보조지표 계산 (시그널 시점에 사용할 bb_width, env_ma60, env_ma20)
        bb_mid = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        bb_width = (4 * bb_std) / bb_mid.replace(0, float("nan"))   # 2σ × 2 / mid
        ma60 = df["close"].rolling(60).mean()
        env_ma60_series = df["close"] / ma60 - 1
        env_ma20_series = df["close"] / bb_mid - 1

        marcap = code_to_marcap.get(code, 0)
        name = code_to_name.get(code, code)

        for date_ts, row in triggered.iterrows():
            entry_price = float(row["close"])
            future_returns = {}
            pos = df.index.get_loc(date_ts)
            for n_label, n_days in [("ret_d1", 1), ("ret_d10", 10),
                                     ("ret_d30", 30), ("ret_d60", 60),
                                     ("ret_d90", 90), ("ret_d120", 120), ("ret_d180", 180)]:
                if pos + n_days < len(df):
                    fut_close = float(df.iloc[pos + n_days]["close"])
                    future_returns[n_label] = (fut_close - entry_price) / entry_price
                else:
                    future_returns[n_label] = None

            # 시장필터 통과 여부
            try:
                kospi_above = bool(market_above.loc[
                    market_above.index.asof(date_ts)])
            except (KeyError, ValueError):
                kospi_above = False

            # 시그널 시점 보조지표 값
            try:
                bb_w_val = float(bb_width.iloc[pos]) if not pd.isna(bb_width.iloc[pos]) else 0.0
                env60_val = float(env_ma60_series.iloc[pos]) if not pd.isna(env_ma60_series.iloc[pos]) else 0.0
                env20_val = float(env_ma20_series.iloc[pos]) if not pd.isna(env_ma20_series.iloc[pos]) else 0.0
            except (IndexError, KeyError):
                bb_w_val, env60_val, env20_val = 0.0, 0.0, 0.0

            rows.append({
                "date": date_ts.strftime("%Y-%m-%d"),
                "year": date_ts.year, "month": date_ts.month,
                "ticker": code, "name": name,
                "marcap": int(marcap) if pd.notna(marcap) else 0,
                "kospi_above": kospi_above,
                "similarity": float(row["similarity"]),
                "close": int(entry_price),
                "ret_1d": float(row.get("ret_1d", 0)),
                "ret_20d": float(row.get("ret_20d", 0)),
                "value_eok": float(row.get("value", 0)) / 1e8,
                "vol_ratio": float(row.get("volume_ratio_60d", 0)),
                "rsi": float(row.get("rsi_14", 0)),
                "bb_width": bb_w_val,
                "env_ma20": env20_val,
                "env_ma60": env60_val,
                "close_to_high": float(row.get("close_to_day_high", 0)),
                **future_returns,
            })

    df_out = pd.DataFrame(rows)
    # dtype 최적화로 파일 크기 줄이기 (단, marcap은 int64 유지 — 조 단위 overflow 방지)
    for c in ("year", "month"):
        if c in df_out.columns:
            df_out[c] = df_out[c].astype("int32")
    for c in ("close",):
        if c in df_out.columns:
            df_out[c] = df_out[c].astype("int32")
    if "marcap" in df_out.columns:
        df_out["marcap"] = df_out["marcap"].astype("int64")
    for c in ("similarity", "ret_1d", "ret_20d", "value_eok", "vol_ratio",
               "rsi", "close_to_high", "bb_width", "env_ma20", "env_ma60",
               "ret_d1", "ret_d10", "ret_d30", "ret_d60", "ret_d90", "ret_d120", "ret_d180"):
        if c in df_out.columns:
            df_out[c] = df_out[c].astype("float32")
    if "kospi_above" in df_out.columns:
        df_out["kospi_above"] = df_out["kospi_above"].astype("bool")

    out_path = ROOT / "results" / f"history_signals_{profile_name}.parquet"
    df_out.to_parquet(out_path, compression="zstd")
    print(f"  → {out_path} ({len(df_out):,} rows, {time.time()-t0:.0f}s)", flush=True)
    return df_out


def main():
    # 시장필터 인덱스
    kospi = get_index_ohlcv("KS11", "20200101", "20260522")
    kospi["ma20"] = kospi["close"].rolling(20).mean()
    market_above = kospi["close"] > kospi["ma20"]

    # 3가지 모드 다 사전 계산
    compute_with_profile("combined",
                          lambda: build_profile(combined=True),
                          market_above)
    compute_with_profile("user39",
                          lambda: build_profile(combined=False),
                          market_above)
    compute_with_profile("oos_yearly", None, market_above)


if __name__ == "__main__":
    main()
