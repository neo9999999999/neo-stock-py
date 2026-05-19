"""
최종 보고서 생성
================
백테스트 + 워크포워드 결과를 마크다운 보고서로 정리.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
REPORT_DIR = ROOT.parent / "04_검증_분석"


def fmt_pct(x):
    return f"{x*100:+.2f}%" if pd.notna(x) else "-"


def main():
    base_m = json.loads((RESULTS / "base_metrics.json").read_text())
    base_trades = pd.read_parquet(RESULTS / "base_trades.parquet")

    grid_file = RESULTS / "grid_search.parquet"
    grid = pd.read_parquet(grid_file) if grid_file.exists() else pd.DataFrame()

    wf_file = RESULTS / "wf_summary.json"
    wf = json.loads(wf_file.read_text()) if wf_file.exists() else {"windows": [], "oos_metrics": {}}

    md = []
    md.append("# 5년치 백테스트 + 최적화 결과 보고서\n")
    md.append("**대상**: 시총 상위 300종목 · 2021-01-01 ~ 2026-05-17\n")
    md.append("**전략**: 5대 조건 종가 베팅 (익일 종가 청산, 손절 -3%)\n")
    md.append("**거래 비용**: 라운드 트립 0.3%\n")
    md.append("\n---\n")

    # 1. 기본 파라미터 결과
    md.append("\n## 1. 기본 파라미터 (보고서 원안)\n")
    md.append("`min_value=500억, volume×3, high_60d, close/high≥0.97, ret∈[5%,25%], score≥5, k=5`\n")
    md.append("\n| 지표 | 값 |\n|---|---|")
    md.append(f"\n| 총 거래수 | {base_m['n']:,} |")
    md.append(f"\n| 승률 | {base_m['win_rate']*100:.2f}% |")
    md.append(f"\n| 평균 수익 | {fmt_pct(base_m['mean_ret'])} |")
    md.append(f"\n| 기댓값 | {fmt_pct(base_m['expectancy'])} |")
    md.append(f"\n| Profit Factor | {base_m['profit_factor']:.2f} |")
    md.append(f"\n| 샤프 지수 (연환산) | {base_m['sharpe']:.2f} |")
    md.append(f"\n| 누적 수익 | {fmt_pct(base_m['total_ret'])} |")
    md.append(f"\n| 최대 낙폭 (MDD) | {fmt_pct(base_m['mdd'])} |")

    # 대장주 vs 비대장주
    md.append("\n\n### 1-1. 랭크별 (대장주 vs 후순위)\n")
    md.append("| 랭크 | 거래수 | 승률 | 평균 수익 |\n|---|---|---|---|")
    for rank in sorted(base_trades["rank"].unique()):
        sub = base_trades[base_trades["rank"] == rank]
        wr = (sub["net"] > 0).mean()
        mr = sub["net"].mean()
        md.append(f"\n| {rank} | {len(sub):,} | {wr*100:.1f}% | {fmt_pct(mr)} |")

    # 2. 그리드 서치 결과
    if not grid.empty:
        md.append("\n\n## 2. 그리드 서치 (전체기간 최적 조합)\n")
        md.append(f"테스트 조합 수: {len(grid)}\n")
        md.append("\n### 2-1. 상위 10 조합 (기댓값 기준)\n")
        top = grid.head(10).copy()
        cols = ["win_rate", "expectancy", "sharpe", "total_ret", "n",
                "p_min_value", "p_volume_mult", "p_close_to_high",
                "p_daily_ret_min", "p_require_score", "p_top_k_per_day", "p_stop_loss"]
        avail = [c for c in cols if c in top.columns]
        md.append("\n| " + " | ".join(avail) + " |")
        md.append("\n|" + "---|" * len(avail))
        for _, r in top[avail].iterrows():
            vals = []
            for c in avail:
                v = r[c]
                if c == "win_rate":
                    vals.append(f"{v*100:.1f}%")
                elif c in ("expectancy", "total_ret"):
                    vals.append(f"{v*100:+.2f}%")
                elif c == "p_min_value":
                    vals.append(f"{v/1e8:.0f}억")
                elif c == "n":
                    vals.append(f"{int(v):,}")
                else:
                    vals.append(f"{v:.3f}" if isinstance(v, float) else str(v))
            md.append("\n| " + " | ".join(vals) + " |")

        # 최적 단일 조합
        best = grid.iloc[0]
        md.append(f"\n\n### 2-2. 최적 조합 (1위)\n")
        md.append(f"- 거래대금: ≥ {best['p_min_value']/1e8:.0f}억\n")
        md.append(f"- 거래량 배수: × {best['p_volume_mult']}\n")
        md.append(f"- 신고가 윈도우: {int(best['p_high_window'])}일\n")
        md.append(f"- 종가/고가: ≥ {best['p_close_to_high']:.2f}\n")
        md.append(f"- 등락률: {best['p_daily_ret_min']:.0%} ~ 25%\n")
        md.append(f"- 최소 조건: {int(best['p_require_score'])}개\n")
        md.append(f"- 일별 K: {int(best['p_top_k_per_day'])}\n")
        md.append(f"- 손절: {best['p_stop_loss']:.0%}\n")
        md.append(f"\n→ 승률 **{best['win_rate']*100:.1f}%**, 기댓값 **{best['expectancy']*100:+.2f}%**, "
                  f"PF **{best['profit_factor']:.2f}**, 누적 **{best['total_ret']*100:+.1f}%**\n")

    # 3. 워크포워드
    md.append("\n## 3. 워크포워드 분석 (Out-of-Sample)\n")
    md.append("학습 1년 / 검증 3개월 슬라이딩, 학습구간에서 그리드 서치 후 검증구간 적용.\n")
    md.append("**과적합을 통제한 진짜 성과 지표**.\n\n")
    oos = wf.get("oos_metrics", {})
    if oos.get("n", 0) > 0:
        md.append("| 지표 | 값 |\n|---|---|")
        md.append(f"\n| OOS 거래수 | {oos['n']:,} |")
        md.append(f"\n| OOS 승률 | {oos.get('win_rate', 0)*100:.2f}% |")
        md.append(f"\n| OOS 기댓값 | {fmt_pct(oos.get('expectancy', 0))} |")
        md.append(f"\n| OOS PF | {oos.get('profit_factor', 0):.2f} |")
        md.append(f"\n| OOS 샤프 | {oos.get('sharpe', 0):.2f} |")
        md.append(f"\n| OOS 누적 | {fmt_pct(oos.get('total_ret', 0))} |")
        md.append(f"\n| OOS MDD | {fmt_pct(oos.get('mdd', 0))} |")

        md.append("\n\n### 3-1. 윈도우별 결과\n")
        md.append("| 학습 구간 | 검증 구간 | Train PF | Test 승률 | Test 기댓값 | Test 누적 |\n")
        md.append("|---|---|---|---|---|---|")
        for w in wf["windows"]:
            md.append(f"\n| {w['train_start']}~{w['train_end']} "
                      f"| {w['test_start']}~{w['test_end']} "
                      f"| {w['train_metrics'].get('profit_factor', 0):.2f} "
                      f"| {w['test_metrics'].get('win_rate', 0)*100:.1f}% "
                      f"| {fmt_pct(w['test_metrics'].get('expectancy', 0))} "
                      f"| {fmt_pct(w['test_metrics'].get('total_ret', 0))} |")

    # 4. 권고
    md.append("\n\n## 4. 결론 및 권고\n")
    bm = base_m
    if bm["expectancy"] > 0.005 and bm["win_rate"] > 0.50:
        md.append("✅ **기본 파라미터로 통계적 우위 확인**. 거래 비용 차감 후에도 양의 기댓값.\n")
    elif bm["expectancy"] > 0:
        md.append("⚠️ **마진 얇음**. 기댓값은 양수이나 비용 충격에 취약. 조건 강화 필요.\n")
    else:
        md.append("❌ **기댓값 음수**. 기본 파라미터는 실거래에 부적합. 최적화된 파라미터 사용 권장.\n")

    if not grid.empty:
        best = grid.iloc[0]
        if best["expectancy"] > bm["expectancy"]:
            improve = (best["expectancy"] - bm["expectancy"]) * 100
            md.append(f"\n그리드 서치 최적 조합은 기댓값을 +{improve:.2f}%p 개선.\n")

    if oos.get("expectancy", 0) > 0 and oos.get("n", 0) >= 30:
        md.append(f"\n워크포워드 OOS 기댓값 {fmt_pct(oos['expectancy'])} — **과적합 위험 통제된 결과**.\n")
    elif oos.get("n", 0) > 0:
        md.append("\n워크포워드 OOS 성과가 학습 구간 대비 크게 떨어지면 과적합 가능성. 보수적 운영 권장.\n")

    md.append("\n---\n")
    md.append(f"\n*생성: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*\n")

    out_path = REPORT_DIR / "05_백테스트_결과보고서.md"
    out_path.write_text("".join(md), encoding="utf-8")
    print(f"보고서 저장: {out_path}")


if __name__ == "__main__":
    main()
