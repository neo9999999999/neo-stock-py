"""
워크포워드 분석 + 파라미터 최적화
================================
시계열을 학습/검증 구간으로 슬라이딩하며 최적 파라미터를 찾고,
out-of-sample 성과를 집계한다.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from engine import Params, add_signals, backtest, metrics


# ----- 파라미터 그리드 -----------------------------------------------------

DEFAULT_GRID: dict[str, list] = {
    "min_value": [3e10, 5e10, 1e11],
    "volume_mult": [2.0, 3.0, 4.0],
    "high_window": [40, 60, 90],
    "close_to_high": [0.95, 0.97, 0.99],
    "daily_ret_min": [0.03, 0.05, 0.07],
    "require_score": [4, 5],
    "top_k_per_day": [3, 5, 10],
    "stop_loss": [-0.02, -0.03, -0.05],
}


def make_grid(grid: dict | None = None) -> list[Params]:
    grid = grid or DEFAULT_GRID
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    out = []
    for combo in combos:
        kwargs = dict(zip(keys, combo))
        out.append(Params(**kwargs))
    return out


# ----- 단일 백테스트 (캐시된 신호 데이터로) -------------------------------

def run_with_params(
    raw_data: dict[str, pd.DataFrame],
    business_days: list[str],
    p: Params,
) -> tuple[pd.DataFrame, dict]:
    """raw_data: ticker -> 원시 OHLCV. 시그널은 매번 재계산 (조건 임계치가 다르므로)."""
    sig_data: dict[str, pd.DataFrame] = {}
    for t, df in raw_data.items():
        sig_data[t] = add_signals(df, p)
    trades = backtest(sig_data, business_days, p)
    return trades, metrics(trades)


# ----- 그리드 서치 (단일 구간) --------------------------------------------

def grid_search(
    raw_data: dict[str, pd.DataFrame],
    business_days: list[str],
    grid: dict | None = None,
    objective: str = "expectancy",
    min_trades: int = 30,
    verbose: bool = True,
) -> pd.DataFrame:
    """objective로 최고 파라미터 선정. expectancy / sharpe / mean_ret 권장."""
    combos = make_grid(grid)
    rows = []
    n = len(combos)
    if verbose:
        print(f"  [grid] {n} combos on {len(business_days)} days")
    for i, p in enumerate(combos, 1):
        try:
            _, m = run_with_params(raw_data, business_days, p)
        except Exception as exc:
            if verbose:
                print(f"  [{i}/{n}] error: {exc}")
            continue
        if m.get("n", 0) < min_trades:
            continue
        row = {**m, **{f"p_{k}": v for k, v in p.__dict__.items()}}
        rows.append(row)
        if verbose and i % 50 == 0:
            print(f"  [{i}/{n}] tested")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values(objective, ascending=False).reset_index(drop=True)
    return df


# ----- 워크포워드 ---------------------------------------------------------

def walk_forward(
    raw_data: dict[str, pd.DataFrame],
    business_days: list[str],
    train_days: int = 252,        # 학습 1년
    test_days: int = 63,           # 검증 3개월
    step_days: int = 63,           # 슬라이딩 3개월씩
    grid: dict | None = None,
    objective: str = "expectancy",
    min_trades: int = 20,
    verbose: bool = True,
) -> dict:
    """결과: {windows: [...], oos_trades: DataFrame, oos_metrics: {...}}"""
    n = len(business_days)
    windows = []
    all_oos_trades = []

    start_idx = 0
    while start_idx + train_days + test_days <= n:
        train = business_days[start_idx : start_idx + train_days]
        test = business_days[start_idx + train_days : start_idx + train_days + test_days]

        if verbose:
            print(f"\n[WF window] train {train[0]}~{train[-1]} | test {test[0]}~{test[-1]}")

        # 학습 구간 그리드 서치
        gs = grid_search(raw_data, train, grid=grid, objective=objective,
                         min_trades=min_trades, verbose=False)
        if gs.empty:
            if verbose:
                print("  [skip] no valid combos in train")
            start_idx += step_days
            continue
        best = gs.iloc[0]
        best_params = Params(**{k[2:]: best[k] for k in best.index if k.startswith("p_")})
        if verbose:
            print(f"  [best] expectancy={best['expectancy']:.4f}  win={best['win_rate']:.2%}  n={int(best['n'])}")
            print(f"         params: value≥{best_params.min_value/1e8:.0f}억, vol×{best_params.volume_mult}, "
                  f"high={best_params.high_window}d, c/h≥{best_params.close_to_high}, "
                  f"ret∈[{best_params.daily_ret_min},{best_params.daily_ret_max}], "
                  f"score≥{best_params.require_score}, k={best_params.top_k_per_day}, "
                  f"stop={best_params.stop_loss}")

        # 검증 구간 적용 (Out-of-sample)
        oos_trades, oos_m = run_with_params(raw_data, test, best_params)
        oos_trades["window"] = f"{train[0]}~{test[-1]}"
        all_oos_trades.append(oos_trades)

        windows.append({
            "train_start": train[0],
            "train_end": train[-1],
            "test_start": test[0],
            "test_end": test[-1],
            "best_params": {k: v for k, v in best_params.__dict__.items()},
            "train_metrics": {k: best[k] for k in ["n", "win_rate", "mean_ret", "expectancy",
                                                    "profit_factor", "sharpe", "mdd"]},
            "test_metrics": oos_m,
        })
        if verbose:
            print(f"  [OOS] n={oos_m.get('n', 0)}, win={oos_m.get('win_rate', 0):.2%}, "
                  f"expect={oos_m.get('expectancy', 0):.4f}, "
                  f"total={oos_m.get('total_ret', 0):.2%}")

        start_idx += step_days

    # 통합 OOS 결과
    oos_df = pd.concat(all_oos_trades, ignore_index=True) if all_oos_trades else pd.DataFrame()
    oos_metrics_all = metrics(oos_df) if not oos_df.empty else {}

    return {
        "windows": windows,
        "oos_trades": oos_df,
        "oos_metrics": oos_metrics_all,
    }


def save_results(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if "oos_trades" in result and not result["oos_trades"].empty:
        result["oos_trades"].to_parquet(out_dir / "wf_oos_trades.parquet")
    # windows / oos_metrics를 JSON으로
    json_safe = {
        "windows": [
            {
                **{k: v for k, v in w.items() if k != "best_params" and k not in ("train_metrics", "test_metrics")},
                "best_params": w["best_params"],
                "train_metrics": w["train_metrics"],
                "test_metrics": w["test_metrics"],
            }
            for w in result["windows"]
        ],
        "oos_metrics": result["oos_metrics"],
    }
    with open(out_dir / "wf_summary.json", "w", encoding="utf-8") as f:
        json.dump(json_safe, f, indent=2, ensure_ascii=False, default=float)
