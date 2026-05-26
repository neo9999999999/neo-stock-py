"""
2021~2024 사례 자동 마이닝
========================
사용자의 39개 큐레이션 사례는 모두 2025년 이후라 case_profile에 look-ahead bias가
들어가있다. 이 스크립트는 2021-01-01 ~ 2024-12-31 기간에서 동일한 '강한 종가 베팅
승자' 패턴을 데이터로 마이닝해 profile을 비편향 표본으로 다시 만든다.

기준 (사용자 39개와 동일한 분포):
  - 일간 등락률 5% ~ 25%
  - 매수 후 30일 안에 max 가격이 +20% 이상 (= "winner")
  - 60일 평균 대비 거래대금 1.5배 이상 (선택)
  - 60일 신고가 0.93배 이상 (선택)

사용:
  python -m mine_cases   # results/cases_mined_2020_2024.csv 생성
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import warnings
warnings.filterwarnings("ignore")

import time
from typing import Optional
import pandas as pd

from data_loader import get_ohlcv

ROOT = Path(__file__).resolve().parent.parent

# 마이닝 파라미터
MINE_START = "20200601"
MINE_END = "20241231"
DAILY_RET_MIN = 0.05            # 일간 등락률 하한
DAILY_RET_MAX = 0.25            # 일간 등락률 상한
WIN_THRESHOLD = 0.20            # 30일 안에 +20% 이상 = 승자
WIN_HORIZON = 30                # 영업일 30일
LOOKBACK_DAYS = 60              # 60일 통계 윈도우
LOOKBACK_NEED = 80              # 데이터 최소 영업일


def extract_features(df: pd.DataFrame, idx: int, code: str, name: str) -> Optional[dict]:
    """df[idx] 시점을 매수일로 보고 사용자 사례와 같은 피처를 추출."""
    if idx < LOOKBACK_NEED:
        return None
    if idx + WIN_HORIZON >= len(df):
        return None

    today = df.iloc[idx]
    hist = df.iloc[idx - LOOKBACK_DAYS:idx + 1]
    h60 = df.iloc[idx - LOOKBACK_DAYS:idx]
    prev_close = h60.iloc[-1]["close"]

    if prev_close <= 0:
        return None
    ret_1d = (today["close"] / prev_close) - 1
    if not (DAILY_RET_MIN <= ret_1d <= DAILY_RET_MAX):
        return None

    # 미래 30일 최고가
    future = df.iloc[idx + 1:idx + 1 + WIN_HORIZON]
    if len(future) < WIN_HORIZON:
        return None
    after_30d_max = (future["close"].max() / today["close"]) - 1
    if after_30d_max < WIN_THRESHOLD:
        return None

    # 사례 피처
    high_60 = h60["high"].max()
    avg_vol = h60["volume"].mean()
    avg_value = h60["value"].mean() if "value" in h60.columns else (h60["close"] * h60["volume"]).mean()

    if avg_vol <= 0 or avg_value <= 0:
        return None

    ma5 = h60["close"].iloc[-5:].mean()
    ma20 = h60["close"].iloc[-20:].mean()
    ma60 = h60["close"].mean()

    ret_5d = (today["close"] / h60["close"].iloc[-5]) - 1 if len(h60) >= 5 else 0
    ret_20d = (today["close"] / h60["close"].iloc[-20]) - 1 if len(h60) >= 20 else 0

    delta = h60["close"].diff().iloc[-14:]
    gain = delta.where(delta > 0, 0).sum()
    loss = -delta.where(delta < 0, 0).sum()
    rsi = 100 - (100 / (1 + gain / loss)) if loss > 0 else 100

    val = today.get("value", today["close"] * today["volume"])
    value_ratio = val / avg_value
    volume_ratio = today["volume"] / avg_vol
    close_to_high60 = today["close"] / high_60 if high_60 > 0 else 0
    close_to_day_high = today["close"] / today["high"] if today["high"] > 0 else 0

    # 추가 30일/60일 forward
    perf = {"after_1d_max": (df.iloc[idx + 1]["close"] / today["close"]) - 1
            if idx + 1 < len(df) else None}
    for n in [5, 10, 20, 30, 60]:
        if idx + n < len(df):
            fut = df.iloc[idx + 1:idx + 1 + n]
            perf[f"after_{n}d_max"] = (fut["close"].max() / today["close"]) - 1
        else:
            perf[f"after_{n}d_max"] = None

    return {
        "name": name,
        "code": code,
        "buy_date": today.name.strftime("%Y%m%d"),
        "buy_close": int(today["close"]),
        "ret_1d": ret_1d,
        "ret_5d": ret_5d,
        "ret_20d": ret_20d,
        "value_ratio_60d": value_ratio,
        "value_eok": val / 1e8,
        "volume_ratio_60d": volume_ratio,
        "high_60": int(high_60),
        "close_to_high60": close_to_high60,
        "close_to_day_high": close_to_day_high,
        "rsi_14": rsi,
        "above_ma5": bool(today["close"] > ma5),
        "above_ma20": bool(today["close"] > ma20),
        "above_ma60": bool(today["close"] > ma60),
        # 5대 조건 (대략)
        "c1_high_break": bool(today["close"] >= high_60),
        "c2_vol_3x": bool(today["volume"] >= avg_vol * 3.0),
        "c3_value_50eok": bool(val >= 50 * 1e8),
        "c4_strength_97": bool(today["close"] >= today["high"] * 0.97),
        "c5_ret_5_25": bool(0.05 <= ret_1d <= 0.25),
        "score_5_strict": sum([
            bool(today["close"] >= high_60),
            bool(today["volume"] >= avg_vol * 3.0),
            bool(val >= 50 * 1e8),
            bool(today["close"] >= today["high"] * 0.97),
            bool(0.05 <= ret_1d <= 0.25),
        ]),
        "score_relaxed": None,
        **perf,
    }


def main():
    print(f"=== 사례 마이닝 {MINE_START} ~ {MINE_END} ===", flush=True)

    with open(ROOT / "data" / "universe_final.txt") as f:
        universe = [l.strip() for l in f if l.strip()]
    print(f"유니버스: {len(universe)}종목", flush=True)

    mine_start_ts = pd.to_datetime(MINE_START)
    mine_end_ts = pd.to_datetime(MINE_END)

    cases = []
    t0 = time.time()
    for i, code in enumerate(universe, 1):
        if i % 100 == 0:
            print(f"  {i}/{len(universe)}  cases so far: {len(cases)}  "
                  f"({time.time()-t0:.0f}s)", flush=True)
        try:
            # 마이닝 윈도우 + 30일 forward + 80일 룩백
            df = get_ohlcv(code, "20200101", "20260520")
            if df.empty or len(df) < LOOKBACK_NEED + WIN_HORIZON:
                continue
            # value 컬럼 보장
            if "value" not in df.columns:
                df["value"] = df["close"] * df["volume"]
        except Exception:
            continue

        # 종목명: get_name 호출 비싸므로 skip, 코드만 — 나중에 join 가능
        name = code
        for j, ts in enumerate(df.index):
            if ts < mine_start_ts or ts > mine_end_ts:
                continue
            feat = extract_features(df, j, code, name)
            if feat is not None:
                cases.append(feat)

    df_cases = pd.DataFrame(cases)
    print(f"\n총 마이닝 사례: {len(df_cases):,}건", flush=True)

    if len(df_cases) == 0:
        print("⚠️  사례 없음 - 기준이 너무 빡빡한지 확인", flush=True)
        return

    # 종목명 채우기
    try:
        from data_loader import get_krx_listing
        listing = get_krx_listing()
        code_to_name = dict(zip(listing["Code"], listing["Name"]))
        df_cases["name"] = df_cases["code"].map(lambda c: code_to_name.get(c, c))
    except Exception:
        pass

    out_path = ROOT / "results" / "cases_mined_2020_2024.csv"
    df_cases.to_csv(out_path, index=False)
    print(f"저장: {out_path}", flush=True)
    print(f"\n=== 분포 ===", flush=True)
    for col in ["ret_1d", "ret_20d", "value_ratio_60d", "volume_ratio_60d",
                "close_to_high60", "rsi_14", "after_30d_max"]:
        if col in df_cases.columns:
            v = df_cases[col].dropna()
            print(f"  {col:<25} Q25={v.quantile(0.25):.3f}  "
                  f"Q50={v.quantile(0.5):.3f}  Q75={v.quantile(0.75):.3f}",
                  flush=True)


if __name__ == "__main__":
    main()
