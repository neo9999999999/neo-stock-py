"""
v3 고도화 — 대형주 분리 + 종목 압축 + 시장 필터
"""
import sys, time, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(Path(__file__).resolve().parent.parent)

import pandas as pd
from data_loader import business_days, get_index_ohlcv, get_ohlcv, get_krx_listing
from engine import metrics
from engine_v3 import ParamsV3, add_signals_v3, backtest_v3
from engine_v3plus import add_market_filter
from case_similarity import build_profile

profile = build_profile()
listing = get_krx_listing()

# 시총 구간 분류
cap_groups = {
    "대형 (1조+)":     set(listing[listing["Marcap"] >= 1e12]["Code"]),
    "중대형 (5천억~1조)": set(listing[(listing["Marcap"] >= 5e11) & (listing["Marcap"] < 1e12)]["Code"]),
    "중형 (1천억~5천억)":  set(listing[(listing["Marcap"] >= 1e11) & (listing["Marcap"] < 5e11)]["Code"]),
}
print("시총 구간별 종목 수:", flush=True)
for k, v in cap_groups.items():
    print(f"  {k}: {len(v)}", flush=True)

with open("data/universe_final.txt") as f:
    univ = [l.strip() for l in f if l.strip()]

raw = {}
t0 = time.time()
for t in univ:
    df = get_ohlcv(t, "20200101", "20260517")
    if not df.empty and len(df) >= 80:
        raw[t] = df
print(f"\n로드: {len(raw)}종목 ({time.time()-t0:.1f}s)", flush=True)

kospi = get_index_ohlcv("KS11", "20200101", "20260517")

p = ParamsV3(min_similarity=0.6, top_k_per_day=5, stop_loss=-0.03)
t0 = time.time()
sig_v3 = {t: add_signals_v3(df, profile, p) for t, df in raw.items()}
print(f"v3 시그널 ({time.time()-t0:.1f}s)", flush=True)

sig_v3_market = add_market_filter(sig_v3, kospi, ma_window=20)
print("시장 필터 적용\n", flush=True)

bd = business_days("20210101", "20260517")

# ====== 1. 시총 구간별 백테스트 ======
print("="*90)
print("【시총 구간별 v3.1 (시장필터) 30일 보유】")
print("="*90)
print(f"{'그룹':<22}{'거래':>7}{'승률':>7}{'평균':>8}{'PF':>5}{'샤프':>6}{'누적':>14}", flush=True)

results_size = []
for group_name, codes in cap_groups.items():
    sig_filtered = {t: df for t, df in sig_v3_market.items() if t in codes}
    if not sig_filtered: continue
    t_df = backtest_v3(sig_filtered, bd, p, hold_days=30)
    m = metrics(t_df)
    print(f"  {group_name:<20}{m['n']:>7,}{m['win_rate']*100:>6.1f}%"
          f"{m['mean_ret']*100:>+7.2f}%{m['profit_factor']:>5.2f}"
          f"{m['sharpe']:>6.2f}{m['total_ret']*100:>+13.1f}%", flush=True)
    results_size.append({"group": group_name, **m})

# ====== 2. 종목 압축 (K=1, 3, 5) ======
print()
print("="*90)
print("【K (일별 매수 종목 수) 비교 — 대형주만, 시장필터, 30일 보유】")
print("="*90)
print(f"{'K':>3}{'거래':>7}{'승률':>7}{'평균':>8}{'PF':>5}{'샤프':>6}{'누적':>14}", flush=True)

large_codes = cap_groups["대형 (1조+)"]
sig_large = {t: df for t, df in sig_v3_market.items() if t in large_codes}

for k in [1, 3, 5, 10]:
    p_k = ParamsV3(min_similarity=0.6, top_k_per_day=k, stop_loss=-0.03)
    t_df = backtest_v3(sig_large, bd, p_k, hold_days=30)
    m = metrics(t_df)
    print(f"  {k:>2}{m['n']:>7,}{m['win_rate']*100:>6.1f}%"
          f"{m['mean_ret']*100:>+7.2f}%{m['profit_factor']:>5.2f}"
          f"{m['sharpe']:>6.2f}{m['total_ret']*100:>+13.1f}%", flush=True)

# ====== 3. 최강 조합 — 대형주 + 시장필터 + K=3 + 다양한 보유 ======
print()
print("="*90)
print("【최강 조합 — 대형주 + 시장필터 + K=3, 보유일 비교】")
print("="*90)
print(f"{'보유':>4}{'거래':>7}{'승률':>7}{'평균':>8}{'PF':>5}{'샤프':>6}{'누적':>14}", flush=True)

p_best = ParamsV3(min_similarity=0.6, top_k_per_day=3, stop_loss=-0.03)
for hold in [10, 20, 30, 60, 90]:
    t_df = backtest_v3(sig_large, bd, p_best, hold_days=hold)
    m = metrics(t_df)
    print(f"  {hold:>2}일{m['n']:>7,}{m['win_rate']*100:>6.1f}%"
          f"{m['mean_ret']*100:>+7.2f}%{m['profit_factor']:>5.2f}"
          f"{m['sharpe']:>6.2f}{m['total_ret']*100:>+13.1f}%", flush=True)

# ====== 4. 시총별 차등 손절 ======
print()
print("="*90)
print("【대형주 손절 차등 (-2% vs -3% vs -5%) — 30일 보유, K=3】")
print("="*90)
print(f"{'손절':>5}{'거래':>7}{'승률':>7}{'평균':>8}{'PF':>5}{'샤프':>6}{'누적':>14}", flush=True)

for stop in [-0.02, -0.03, -0.05, -0.10]:
    p_s = ParamsV3(min_similarity=0.6, top_k_per_day=3, stop_loss=stop)
    t_df = backtest_v3(sig_large, bd, p_s, hold_days=30)
    m = metrics(t_df)
    print(f"  {stop*100:>+3.0f}%{m['n']:>7,}{m['win_rate']*100:>6.1f}%"
          f"{m['mean_ret']*100:>+7.2f}%{m['profit_factor']:>5.2f}"
          f"{m['sharpe']:>6.2f}{m['total_ret']*100:>+13.1f}%", flush=True)

print("\n=== 완료 ===", flush=True)
