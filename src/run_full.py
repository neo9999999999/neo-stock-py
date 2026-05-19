"""
풀 파이프라인 실행
==================
1) 캐시된 데이터 로드
2) 기본 파라미터 단일 백테스트
3) 그리드 서치
4) 워크포워드 분석
5) 결과 저장 (results/)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from data_loader import business_days, get_ohlcv, get_index_ohlcv
from engine import Params, add_signals, backtest, metrics
from walk_forward import grid_search, walk_forward, save_results, DEFAULT_GRID


ROOT = Path(__file__).resolve().parent.parent  # 03_구현/


def load_universe(path: str | None = None) -> list[str]:
    p = Path(path) if path else (ROOT / "data" / "universe_final.txt")
    with open(p) as f:
        return [line.strip() for line in f if line.strip()]


def load_all(tickers: list[str], start: str, end: str) -> dict:
    """워밍업 200일 포함해서 데이터 로드. 백테스트 시 실제 거래는 start 이후만."""
    import pandas as pd
    warmup = (pd.to_datetime(start, format="%Y%m%d") - pd.Timedelta(days=200)).strftime("%Y%m%d")
    raw = {}
    for t in tickers:
        df = get_ohlcv(t, warmup, end)
        if df.empty or len(df) < 80:
            continue
        raw[t] = df
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20210101")
    ap.add_argument("--end", default="20260517")
    ap.add_argument("--out", default="results")
    ap.add_argument("--skip_grid", action="store_true")
    ap.add_argument("--skip_wf", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== 풀 파이프라인 {args.start}~{args.end} ===\n")

    tickers = load_universe()
    print(f"유니버스 로딩: {len(tickers)} 종목")

    print("OHLCV 로딩 (캐시)...")
    t0 = time.time()
    raw = load_all(tickers, args.start, args.end)
    print(f"  → {len(raw)} 종목 로드, {time.time()-t0:.1f}s")

    bd = business_days(args.start, args.end)
    print(f"영업일: {len(bd)}일")

    # --- 1. 기본 파라미터 백테스트 ---
    print("\n[1/3] 기본 파라미터 백테스트")
    base = Params()
    sig_data = {t: add_signals(df, base) for t, df in raw.items()}
    base_trades = backtest(sig_data, bd, base)
    base_m = metrics(base_trades)
    print(f"  거래수: {base_m.get('n', 0)}, 승률: {base_m.get('win_rate', 0):.2%}, "
          f"기댓값: {base_m.get('expectancy', 0):.4f}, "
          f"누적: {base_m.get('total_ret', 0):.2%}")
    base_trades.to_parquet(out_dir / "base_trades.parquet")
    with open(out_dir / "base_metrics.json", "w") as f:
        json.dump(base_m, f, indent=2, default=float)

    # --- 2. 그리드 서치 (전체 기간) — 가벼운 32조합 ---
    if not args.skip_grid:
        print("\n[2/3] 그리드 서치 (전체 기간) — 32 조합")
        t0 = time.time()
        full_grid = {
            "min_value": [5e9, 5e10, 1e11],          # 50억 / 500억 / 1000억
            "volume_mult": [3.0],
            "high_window": [60],
            "close_to_high": [0.70, 0.97],           # 완화 / 빡빡
            "daily_ret_min": [0.05, 0.07],
            "daily_ret_max": [0.25],
            "require_score": [3, 4, 5],              # 완화~빡빡
            "top_k_per_day": [3, 5],
            "stop_loss": [-0.03, None],              # 손절 / 없음
        }
        gs = grid_search(raw, bd, grid=full_grid, objective="expectancy",
                          min_trades=30, verbose=True)
        print(f"  → {len(gs)} 유효 조합, {time.time()-t0:.1f}s")
        if not gs.empty:
            gs.to_parquet(out_dir / "grid_search.parquet")
            top = gs.head(10)
            print("\n  ★ 상위 10 조합:")
            print(top[["win_rate", "expectancy", "sharpe", "total_ret", "n",
                       "p_min_value", "p_volume_mult", "p_high_window", "p_close_to_high",
                       "p_daily_ret_min", "p_require_score", "p_top_k_per_day", "p_stop_loss"]]
                  .to_string())

    # --- 3. 워크포워드 (가벼운 그리드로 속도 우선) ---
    if not args.skip_wf:
        print("\n[3/3] 워크포워드 분석 — 윈도우별 8조합")
        t0 = time.time()
        wf_grid = {
            "min_value": [5e9, 1e11],
            "volume_mult": [3.0],
            "high_window": [60],
            "close_to_high": [0.70, 0.97],
            "daily_ret_min": [0.05],
            "require_score": [4],
            "top_k_per_day": [5],
            "stop_loss": [None],
        }
        # 총 8조합 × 17윈도우 = 136 백테스트
        result = walk_forward(raw, bd, train_days=252, test_days=63, step_days=63,
                              grid=wf_grid, objective="expectancy", verbose=True)
        save_results(result, out_dir)
        print(f"  → OOS 거래수: {result['oos_metrics'].get('n', 0)}, "
              f"승률: {result['oos_metrics'].get('win_rate', 0):.2%}, "
              f"누적: {result['oos_metrics'].get('total_ret', 0):.2%}, "
              f"{time.time()-t0:.1f}s")

    print("\n=== 완료. results/ 폴더 확인 ===")


if __name__ == "__main__":
    main()
