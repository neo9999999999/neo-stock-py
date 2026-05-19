"""
사례 종목 분석
==============
사용자 제공 사례(종목명 + 매수일)에 대해:
1. 종목명 → 코드 매핑
2. 매수일 시점 OHLCV 로드
3. 5대 조건 점수 계산
4. 추가 지표 분석 (이동평균 위치, RSI 근사, 직전 추세 등)
5. 공통 패턴 도출 + 우리 5대 조건과 비교
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from data_loader import get_krx_listing, get_ohlcv
from engine import Params, add_signals

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def parse_date(s: str) -> str:
    """25/5/12 → 20250512."""
    parts = s.split("/")
    if len(parts) != 3:
        return None
    y, m, d = parts
    yyyy = f"20{y}" if len(y) == 2 else y
    mm = m.zfill(2)
    dd = d.zfill(2)
    return f"{yyyy}{mm}{dd}"


def load_cases(path: str) -> list[tuple[str, str]]:
    """파일에서 (종목명, YYYYMMDD) 리스트."""
    cases = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 마지막 토큰이 날짜
            parts = line.rsplit(" ", 1)
            if len(parts) != 2:
                continue
            name, date_part = parts
            date = parse_date(date_part)
            if date:
                cases.append((name.strip(), date))
    return cases


def name_to_code(listing: pd.DataFrame) -> dict[str, str]:
    """종목명 → 종목코드. 정확 일치 우선, 다음 부분일치."""
    return {row["Name"]: row["Code"] for _, row in listing.iterrows()}


def find_code(name: str, name_map: dict[str, str], listing: pd.DataFrame) -> str | None:
    # 1. 정확 일치
    if name in name_map:
        return name_map[name]
    # 2. 대소문자 무시
    for k, v in name_map.items():
        if k.lower() == name.lower():
            return v
    # 3. 부분 일치
    matches = [(k, v) for k, v in name_map.items() if name in k or k in name]
    if matches:
        # 가장 짧은 이름 우선
        matches.sort(key=lambda x: len(x[0]))
        return matches[0][1]
    return None


def analyze_one(name: str, code: str, buy_date: str) -> dict | None:
    """매수일 시점 + 직전 60일 데이터로 5대 조건 점수 계산."""
    buy_dt = pd.to_datetime(buy_date)
    start = (buy_dt - pd.Timedelta(days=200)).strftime("%Y%m%d")
    end = (buy_dt + pd.Timedelta(days=60)).strftime("%Y%m%d")
    df = get_ohlcv(code, start, end)
    if df.empty or buy_dt not in df.index:
        return None

    # 매수일 시점 데이터
    hist = df.loc[:buy_dt].iloc[-61:]   # 매수일 포함 직전 60일
    if len(hist) < 60:
        return None
    h60 = hist.iloc[-60:]
    high_60 = h60["high"].max()
    avg_vol = h60["volume"].mean()
    today = df.loc[buy_dt]
    prev_close = hist.iloc[-2]["close"]
    ret_1d = (today["close"] / prev_close) - 1

    # 5대 조건 점수
    c1_high = bool(today["close"] >= high_60)
    c2_vol = bool(today["volume"] >= avg_vol * 3.0)
    c3_value = bool(today["value"] >= 50 * 1e8)         # 50억 기준
    c4_strength = bool(today["close"] >= today["high"] * 0.97)
    c5_ret = bool(0.05 <= ret_1d <= 0.25)
    score_5 = sum([c1_high, c2_vol, c3_value, c4_strength, c5_ret])

    # 완화 기준
    c4_strength_70 = bool(today["close"] >= today["high"] * 0.70)
    c5_ret_wide = bool(0.03 <= ret_1d <= 0.30)
    score_relaxed = sum([c1_high, c2_vol, c3_value, c4_strength_70, c5_ret_wide])

    # 추가 지표
    ma5 = h60["close"].iloc[-5:].mean()
    ma20 = h60["close"].iloc[-20:].mean()
    ma60 = h60["close"].iloc[-60:].mean()
    ma_pos = {
        "above_ma5": bool(today["close"] > ma5),
        "above_ma20": bool(today["close"] > ma20),
        "above_ma60": bool(today["close"] > ma60),
    }

    # 직전 5일 등락률
    ret_5d = (today["close"] / h60["close"].iloc[-6]) - 1 if len(h60) >= 6 else 0
    ret_20d = (today["close"] / h60["close"].iloc[-21]) - 1 if len(h60) >= 21 else 0

    # RSI (간단)
    delta = h60["close"].diff().iloc[-14:]
    gain = delta.where(delta > 0, 0).sum()
    loss = -delta.where(delta < 0, 0).sum()
    rsi = 100 - (100 / (1 + gain / loss)) if loss > 0 else 100

    # 거래대금 60일 평균 대비 비율
    avg_value = h60["value"].mean()
    value_ratio = today["value"] / avg_value if avg_value > 0 else 0

    # 익일 ~ N일 후 수익률 (사후 검증)
    future_perf = {}
    for n_days in [1, 5, 10, 20, 30, 60]:
        future = df.loc[buy_dt:].iloc[1:n_days+1]
        if len(future) == n_days:
            max_close = future["close"].max()
            future_perf[f"after_{n_days}d_max"] = (max_close / today["close"]) - 1
        else:
            future_perf[f"after_{n_days}d_max"] = None

    return {
        "name": name,
        "code": code,
        "buy_date": buy_date,
        "buy_close": int(today["close"]),
        "ret_1d": ret_1d,
        "ret_5d": ret_5d,
        "ret_20d": ret_20d,
        "value_ratio_60d": value_ratio,
        "value_eok": today["value"] / 1e8,
        "volume_ratio_60d": today["volume"] / avg_vol,
        "high_60": int(high_60),
        "close_to_high60": today["close"] / high_60,
        "close_to_day_high": today["close"] / today["high"],
        "rsi_14": rsi,
        **ma_pos,
        # 5대 조건
        "c1_high_break": c1_high,
        "c2_vol_3x": c2_vol,
        "c3_value_50eok": c3_value,
        "c4_strength_97": c4_strength,
        "c5_ret_5_25": c5_ret,
        "score_5_strict": score_5,
        "score_relaxed": score_relaxed,
        # 미래 성과
        **future_perf,
    }


def main():
    cases = load_cases(str(ROOT / "data" / "cases_input.txt"))
    print(f"사례 입력: {len(cases)}개")

    listing = get_krx_listing()
    name_map = name_to_code(listing)

    results = []
    skipped = []
    for name, date in cases:
        code = find_code(name, name_map, listing)
        if not code:
            skipped.append((name, date, "종목코드 찾을 수 없음"))
            continue
        try:
            r = analyze_one(name, code, date)
            if r is None:
                skipped.append((name, date, "데이터 부족 또는 매수일 영업일 아님"))
                continue
            results.append(r)
        except Exception as exc:
            skipped.append((name, date, f"오류: {exc}"))

    print(f"\n분석 성공: {len(results)}개, 실패: {len(skipped)}개")
    if skipped:
        print("\n실패 사례:")
        for s in skipped:
            print(f"  - {s[0]} {s[1]}: {s[2]}")

    # DataFrame 저장
    df = pd.DataFrame(results)
    df.to_parquet(RESULTS / "cases_analysis.parquet")
    df.to_csv(RESULTS / "cases_analysis.csv", index=False, encoding="utf-8-sig")
    print(f"\n저장: {RESULTS / 'cases_analysis.csv'}")

    # 통계 분석
    print("\n" + "=" * 70)
    print("=== 5대 조건 충족률 ===")
    cond_cols = ["c1_high_break", "c2_vol_3x", "c3_value_50eok",
                  "c4_strength_97", "c5_ret_5_25"]
    for c in cond_cols:
        rate = df[c].mean()
        print(f"  {c:<22}: {df[c].sum():>3}/{len(df)} ({rate*100:>5.1f}%)")

    print("\n=== 점수 분포 ===")
    print(f"  5/5 만점 충족: {(df['score_5_strict']==5).sum()}/{len(df)} "
          f"({(df['score_5_strict']==5).mean()*100:.1f}%)")
    print(f"  4/5 이상 충족: {(df['score_5_strict']>=4).sum()}/{len(df)} "
          f"({(df['score_5_strict']>=4).mean()*100:.1f}%)")
    print(f"  3/5 이상 충족: {(df['score_5_strict']>=3).sum()}/{len(df)} "
          f"({(df['score_5_strict']>=3).mean()*100:.1f}%)")
    print(f"\n  완화 점수 (c4≥0.70, ret 3~30%):")
    print(f"  5/5 만점: {(df['score_relaxed']==5).sum()}/{len(df)} "
          f"({(df['score_relaxed']==5).mean()*100:.1f}%)")
    print(f"  4/5 이상: {(df['score_relaxed']>=4).sum()}/{len(df)} "
          f"({(df['score_relaxed']>=4).mean()*100:.1f}%)")

    print("\n=== 통계 (사례 종목 매수일 시점) ===")
    print(f"{'지표':<25}{'평균':>10}{'중간값':>10}{'최소':>10}{'최대':>10}")
    metrics_to_show = [
        ("ret_1d", "당일 등락률 %", 100),
        ("ret_5d", "5일 등락률 %", 100),
        ("ret_20d", "20일 등락률 %", 100),
        ("value_ratio_60d", "거래대금 60일 대비", 1),
        ("value_eok", "거래대금 (억)", 1),
        ("volume_ratio_60d", "거래량 60일 대비", 1),
        ("close_to_day_high", "종가/당일고가", 1),
        ("close_to_high60", "종가/60일 고가", 1),
        ("rsi_14", "RSI(14)", 1),
    ]
    for col, label, mult in metrics_to_show:
        vals = df[col].dropna() * mult
        print(f"  {label:<23}{vals.mean():>10.2f}{vals.median():>10.2f}"
              f"{vals.min():>10.2f}{vals.max():>10.2f}")

    print("\n=== 이동평균 위치 (매수일) ===")
    print(f"  5일선 위:  {df['above_ma5'].sum():>3}/{len(df)} ({df['above_ma5'].mean()*100:.1f}%)")
    print(f"  20일선 위: {df['above_ma20'].sum():>3}/{len(df)} ({df['above_ma20'].mean()*100:.1f}%)")
    print(f"  60일선 위: {df['above_ma60'].sum():>3}/{len(df)} ({df['above_ma60'].mean()*100:.1f}%)")

    print("\n=== 미래 성과 (매수일 기준 최대 수익) ===")
    for n in [1, 5, 10, 20, 30, 60]:
        col = f"after_{n}d_max"
        if col in df.columns:
            vals = df[col].dropna()
            if len(vals):
                print(f"  {n:>3}일 내 최대: 평균 {vals.mean()*100:+6.2f}% / "
                      f"중간 {vals.median()*100:+6.2f}% / "
                      f"양수 {(vals>0).sum()}/{len(vals)} ({(vals>0).mean()*100:.0f}%)")


if __name__ == "__main__":
    main()
