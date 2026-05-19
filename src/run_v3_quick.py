"""v3 변종 빠른 비교."""
import sys, time, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(Path(__file__).resolve().parent.parent)
import pandas as pd
from data_loader import business_days, get_index_ohlcv, get_ohlcv
from engine import metrics
from engine_v3 import ParamsV3, add_signals_v3, backtest_v3
from engine_v3plus import add_market_filter, add_overheating_filter
from case_similarity import build_profile

profile = build_profile()
with open("data/universe_final.txt") as f:
    univ = [l.strip() for l in f if l.strip()]
print(f"유니버스: {len(univ)}", flush=True)

raw = {}
t0 = time.time()
for t in univ:
    df = get_ohlcv(t, "20200101", "20260517")
    if not df.empty and len(df) >= 80:
        raw[t] = df
print(f"로드: {len(raw)}종목 ({time.time()-t0:.1f}s)", flush=True)

kospi = get_index_ohlcv("KS11", "20200101", "20260517")
print(f"KOSPI: {len(kospi)}일", flush=True)

t0 = time.time()
p = ParamsV3(min_similarity=0.6, top_k_per_day=5, stop_loss=-0.03)
sig_v3 = {t: add_signals_v3(df, profile, p) for t, df in raw.items()}
print(f"v3 시그널 ({time.time()-t0:.1f}s)", flush=True)

sig_v31 = add_market_filter(sig_v3, kospi, ma_window=20)
sig_v32 = add_overheating_filter(sig_v31, 0.30)
sig_v36 = add_market_filter(sig_v3, kospi, ma_window=60)
print("변종 적용 완료", flush=True)

bd = business_days("20210101", "20260517")

variants = {
    "v3.0 기준": sig_v3,
    "v3.1 +KOSPI 20일선": sig_v31,
    "v3.2 +시장+과열회피": sig_v32,
    "v3.6 +KOSPI 60일선": sig_v36,
}

rows = []
print(f"\n{'변종':<22}{'보유':>5}{'거래':>7}{'승률':>7}{'평균':>8}{'PF':>5}{'샤프':>6}{'누적':>14}",
      flush=True)
print("=" * 80, flush=True)
for name, sig in variants.items():
    for hold in [10, 30, 60, 90]:
        t = backtest_v3(sig, bd, p, hold_days=hold)
        m = metrics(t)
        if m["n"] == 0: continue
        print(f"  {name:<20}{hold:>4}일{m['n']:>7,}"
              f"{m['win_rate']*100:>6.1f}%{m['mean_ret']*100:>+7.2f}%"
              f"{m['profit_factor']:>5.2f}{m['sharpe']:>6.2f}"
              f"{m['total_ret']*100:>+13.1f}%", flush=True)
        rows.append({"variant": name, "hold": hold, **m})

df = pd.DataFrame(rows)
df.to_csv("results/v3_variants.csv", index=False, encoding="utf-8-sig")
print(flush=True)

best = df.nlargest(1, "sharpe").iloc[0]
print(f"★ 샤프 1위: {best['variant']} / {best['hold']}일", flush=True)
print(f"  승률 {best['win_rate']*100:.1f}%, 평균 {best['mean_ret']*100:+.2f}%, "
      f"PF {best['profit_factor']:.2f}, 샤프 {best['sharpe']:.2f}", flush=True)
