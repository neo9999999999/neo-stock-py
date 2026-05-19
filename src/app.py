"""
Streamlit 웹 대시보드 — Slash/Toss 스타일
========================================
실행:
    cd "/Users/neo/Desktop/종가베팅_분석/03_구현"
    source ../.venv/bin/activate
    streamlit run src/app.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

from data_loader import (
    business_days,
    get_index_ohlcv,
    get_krx_listing,
    get_name,
    get_ohlcv,
    get_universe,
)
from engine import Params, add_signals, backtest, backtest_tiered, metrics
from engine_v2 import ParamsV2, add_signals_v2, backtest_v2, metrics_v2
from engine_v3 import ParamsV3, add_signals_v3, backtest_v3
from case_similarity import build_profile, case_count
from theme import (
    PALETTE, inject_css, hero, section_title, bento,
    stock_card_html, theme_card_html, empty_state, code,
)
import theme_scraper as scraper

ROOT = SRC.parent
RESULTS = ROOT / "results"
DATA = ROOT / "data"

st.set_page_config(
    page_title="종가 베팅 · Closing Bet",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded",
)

if "theme" not in st.session_state:
    st.session_state.theme = "light"

inject_css(st.session_state.theme)


# ====================================================================
# 비밀번호 게이트 (Streamlit Cloud secrets.APP_PASSWORD)
# ====================================================================
def _password_gate() -> bool:
    expected = None
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected:
        return True          # 로컬: secrets 없으면 게이트 비활성
    if st.session_state.get("_auth_ok"):
        return True

    st.markdown(
        '<div style="max-width:420px;margin:6rem auto 2rem auto;text-align:center;">'
        '<div style="font-size:2.5rem;margin-bottom:0.5rem;">🔒</div>'
        '<h2 style="margin:0 0 0.25rem 0;color:#191F28;">종가 베팅 대시보드</h2>'
        '<p style="color:#8B95A1;margin:0 0 1.5rem 0;font-size:0.875rem;">'
        '접속 비밀번호를 입력하세요.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        pw = st.text_input("비밀번호", type="password",
                            label_visibility="collapsed",
                            placeholder="비밀번호 입력 후 Enter",
                            key="_auth_input")
        if pw:
            if pw == expected:
                st.session_state._auth_ok = True
                st.rerun()
            else:
                st.error("비밀번호가 일치하지 않습니다.")
    st.stop()


_password_gate()


# ====================================================================
# 페이지 라우팅 (상단 + 사이드바 양쪽)
# ====================================================================
PAGES = [
    ("📌", "오늘의 추천", "today"),
    ("📅", "추천 히스토리", "history"),
    ("🎯", "테마/대장주", "themes"),
    ("📊", "백테스트 결과", "backtest"),
    ("🔄", "워크포워드", "walkforward"),
    ("🎛️", "파라미터 시뮬레이터", "simulator"),
    ("🔍", "사례 검증", "cases"),
    ("📖", "전략 가이드", "guide"),
]

if "page" not in st.session_state:
    st.session_state.page = "today"


# ----- 사이드바 네비 -----
st.sidebar.markdown(
    '<div class="brand-mark"><span class="dot"></span> Closing Bet</div>'
    '<div style="color:#8B95A1;font-size:0.8125rem;margin-top:0.25rem;">'
    '주도주 종가 베팅 분석 시스템</div>',
    unsafe_allow_html=True,
)

# 테마 토글
theme_c1, theme_c2 = st.sidebar.columns(2)
if theme_c1.button("☀️ Light", key="theme_light", use_container_width=True,
                    type="primary" if st.session_state.theme == "light" else "secondary"):
    st.session_state.theme = "light"
    st.rerun()
if theme_c2.button("🌙 Dark", key="theme_dark", use_container_width=True,
                    type="primary" if st.session_state.theme == "dark" else "secondary"):
    st.session_state.theme = "dark"
    st.rerun()

st.sidebar.markdown('<div style="height:1px;background:#E5E8EB;margin:1rem 0;"></div>',
                     unsafe_allow_html=True)

for icon, label, key in PAGES:
    if st.sidebar.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True,
                          type="primary" if st.session_state.page == key else "secondary"):
        st.session_state.page = key
        st.rerun()

st.sidebar.markdown('<div style="height:1px;background:#E5E8EB;margin:1.5rem 0;"></div>', unsafe_allow_html=True)
st.sidebar.markdown(
    '<div style="color:#8B95A1;font-size:0.75rem;line-height:1.6;">'
    f'<b style="color:#191F28;">데이터</b><br>FDR · KRX<br>{dt.date.today()}<br><br>'
    '<b style="color:#191F28;">전략</b><br>5대 조건 종가 베팅<br>익일 종가 청산<br><br>'
    '<b style="color:#191F28;">유니버스</b><br>시총 상위 300<br>2021–2026'
    '</div>',
    unsafe_allow_html=True,
)


# ----- 상단 인라인 네비 (사이드바가 안 보일 때 백업) -----
def render_top_nav():
    """페이지 상단의 가로 탭 네비게이션."""
    current = st.session_state.page
    cols = st.columns(len(PAGES))
    for col, (icon, label, key) in zip(cols, PAGES):
        is_active = key == current
        with col:
            # active 상태 표시
            btn_label = f"{icon} {label}"
            if st.button(btn_label, key=f"topnav_{key}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state.page = key
                st.rerun()


# ====================================================================
# 유틸리티
# ====================================================================
@st.cache_data(show_spinner=False)
def cached_business_days(start: str, end: str) -> list[str]:
    return business_days(start, end)


@st.cache_data(show_spinner=False)
def cached_universe(n: int | None = None) -> list[str]:
    """확장된 유니버스 파일(universe_final.txt) 우선 사용.
    n이 지정되면 시총 상위 N개로 슬라이스."""
    uni_file = ROOT / "data" / "universe_final.txt"
    if uni_file.exists():
        with open(uni_file) as f:
            tickers = [line.strip() for line in f if line.strip()]
        if n is not None and n < len(tickers):
            tickers = tickers[:n]
        return tickers
    return get_universe(n=n or 300)


@st.cache_data(show_spinner=False)
def load_panel(tickers: tuple[str, ...], start: str, end: str) -> dict:
    out = {}
    for t in tickers:
        df = get_ohlcv(t, start, end)
        if not df.empty:
            out[t] = df
    return out


def fmt_pct(x):
    return f"{x*100:+.2f}%" if pd.notna(x) else "-"


EXIT_REASON_KR = {
    "close": "종가청산",
    "open": "시가청산",
    "high": "고가청산",
    "stop": "손절",
    "tp": "익절",
}


def fmt_eok(value_won: float) -> str:
    if value_won >= 1e12:
        return f"{value_won/1e12:.1f}조"
    if value_won >= 1e8:
        return f"{value_won/1e8:.0f}억"
    return f"{value_won:,.0f}"


def fmt_won_kr(won: float) -> str:
    """원화 한국식 표기: 1.23억 / 1,234만원 / 567원."""
    if pd.isna(won):
        return "-"
    sign = "-" if won < 0 else ""
    w = abs(won)
    if w >= 1e8:
        eok = w // 1e8
        man = (w % 1e8) // 1e4
        if man > 0:
            return f"{sign}{int(eok):,}억 {int(man):,}만원"
        return f"{sign}{int(eok):,}억"
    if w >= 1e4:
        return f"{sign}{w/1e4:,.0f}만원"
    return f"{sign}{w:,.0f}원"


def kpi_row(items: list[tuple[str, str, str, str]]):
    """items: (label, value, sub, tone)."""
    cols = st.columns(len(items))
    for col, (label, value, sub, tone) in zip(cols, items):
        with col:
            bento(label, value, sub, tone)


# ====================================================================
# 페이지 1: 오늘의 추천
# ====================================================================
def page_today():
    hero(
        eyebrow="오늘의 스크리닝",
        title="오늘의 종가 베팅 후보",
        lead="v3.7 (대형주) 권장 — 샤프 2.89로 최강. 30일 보유.",
    )

    # 정직 디스클로저: 두 페이지 차이점
    with st.expander("ℹ️ '오늘의 추천' vs '추천 히스토리' 차이점", expanded=False):
        st.markdown(
            "**공통**: 같은 사례 유사도 엔진(`add_signals_v3`), 동일한 39개 사례 profile (2025-01~2026-02).\n\n"
            "**차이**:\n"
            "- **시장 필터(KOSPI 20MA)**: 히스토리는 프리셋에 따라 자동 ON, 오늘 페이지는 적용 안 함.\n"
            "- **유니버스**: 두 페이지 모두 같은 universe + 시총 컷오프 적용.\n"
            "- **OOS 신뢰도**: 오늘(2026-05-19)은 사례 마지막 시점(2026-02-04) 이후라 **진짜 OOS**. "
            "히스토리는 2025년 이전 구간이 in-sample 위험."
        )

    # 전략 프리셋 (셀렉트박스 + 정보 카드)
    PRESETS_TODAY = {
        "⭐ v3.7 — 시총 5천억+ + 시장필터 (추천)": {
            "use_v3": True, "cap": 5e11, "market": True,
            "sharpe": 2.48, "mean": 3.94, "stocks": 565,
            "desc": "균형 잡힌 추천. 종목 다양성 + 우수한 성과",
        },
        "🏆 v3.7 — 시총 1조+ + 시장필터 (대형주 최강)": {
            "use_v3": True, "cap": 1e12, "market": True,
            "sharpe": 2.89, "mean": 4.75, "stocks": 366,
            "desc": "가장 안정적. 외국인/기관 수급 명확한 대형주",
        },
        "📊 v3.1 — 전체 + 시장필터": {
            "use_v3": True, "cap": 0, "market": True,
            "sharpe": 1.47, "mean": 2.40, "stocks": 1534,
            "desc": "중소형주 포함 — KOSPI 20일선 위에서만",
        },
        "🌐 v3.0 — 기본 (전체, 필터 없음)": {
            "use_v3": True, "cap": 0, "market": False,
            "sharpe": 1.02, "mean": 1.70, "stocks": 1534,
            "desc": "시장 필터 없는 기본 사례 유사도",
        },
        "❌ v1 — 기존 5대 조건 (비추)": {
            "use_v3": False, "cap": 0, "market": False,
            "sharpe": 0.40, "mean": 0.17, "stocks": 1534,
            "desc": "사례 95% 놓침 — 참고용",
        },
    }
    preset = st.selectbox(
        "🎯 전략 프리셋", list(PRESETS_TODAY.keys()),
        index=0, key="today_preset",
    )
    cfg = PRESETS_TODAY[preset]

    # 선택된 프리셋 정보 카드
    tone = "success" if cfg["sharpe"] >= 1.5 else (
        "warning" if cfg["sharpe"] >= 1.0 else "danger"
    )
    color = "#00C896" if tone == "success" else ("#FF9F2E" if tone == "warning" else "#F04452")
    st.markdown(
        f'<div style="display:flex;gap:1rem;padding:0.875rem 1.25rem;'
        f'background:rgba(49,130,246,0.06);border-left:4px solid {color};'
        f'border-radius:8px;margin-bottom:1rem;flex-wrap:wrap;">'
        f'<div><b style="font-size:1rem;">샤프 {cfg["sharpe"]:.2f}</b></div>'
        f'<div style="color:#4E5968;">평균 +{cfg["mean"]:.2f}%</div>'
        f'<div style="color:#4E5968;">종목 풀 {cfg["stocks"]:,}개</div>'
        f'<div style="color:#8B95A1;flex:1;text-align:right;">{cfg["desc"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    use_v3_today = cfg["use_v3"]
    size_cutoff = cfg["cap"]
    only_large_cap = size_cutoff > 0
    apply_market_filter = cfg.get("market", False)

    # ===== 기준일 + 유사도 =====
    dc1, dc2 = st.columns([1, 1])
    target_date = dc1.date_input("📅 기준일", value=dt.date.today(),
                                    max_value=dt.date.today(), key="today_date")
    if use_v3_today:
        sim_threshold = dc2.slider("유사도 임계치", 0.3, 0.9, 0.6, 0.05,
                                     key="today_sim",
                                     help="0.6=많이 잡힘, 0.8=빡빡(사례 같은 종목)")
        require_score = 4
    else:
        require_score = dc2.selectbox("최소 충족 조건", [1, 2, 3, 4, 5],
                                        index=3, key="today_minscore")
        sim_threshold = 0.6

    # ===== 추천 설정 (종목 수 + 매수금) — 히스토리와 동일 =====
    st.markdown("##### ⚙️ 추천 설정")
    tc1, tc2 = st.columns(2)
    max_recommend = tc1.slider("추천 종목 수", 1, 30, 5, key="today_topk",
                                 help="유사도 상위 N개만 표시")
    today_buy_man = tc2.number_input("종목당 매수금 (만원)",
                                       value=100, step=10, min_value=10, max_value=100000,
                                       format="%d", key="today_buy_amt",
                                       help="10만원 ~ 10억원. 표시용")
    today_buy_won = today_buy_man * 10000

    # ===== 추가 필터 — 히스토리와 동일 =====
    with st.expander("🔧 추가 필터 — 직접 임계치 조정 (선택)", expanded=False):
        st.caption("프리셋 기본값에 추가 조건. 0 = 필터 미적용.")
        f1, f2, f3 = st.columns(3)
        td_value_min = f1.number_input("최소 거래대금 (억)", value=50, step=10,
                                         min_value=0, format="%d", key="td_val_min",
                                         help="50억 미만 제외 권장")
        td_vol_mult = f2.number_input("거래량 60일 ×배수", value=3.0, step=0.5,
                                        format="%.1f", key="td_vol_mult_f")
        td_close_high = f3.number_input("종가/고가 ≥", value=0.0, step=0.01,
                                          format="%.2f", key="td_close_high_f",
                                          help="0=미적용. 0.97 = 막판 매수세")
        f4, f5, f6 = st.columns(3)
        td_ret_min = f4.number_input("최소 당일 등락 (%)", value=0.0, step=1.0,
                                       format="%.1f", key="td_ret_min_f",
                                       help="예: 7 입력 시 +7% 이상만")
        td_ret_max = f5.number_input("최대 당일 등락 (%)", value=0.0, step=1.0,
                                       format="%.1f", key="td_ret_max_f",
                                       help="0=미적용")
        td_ret20_min = f6.number_input("최소 직전20일 누적 (%)", value=0.0, step=1.0,
                                         format="%.1f", key="td_ret20_min_f")

    # ===== 최종 요약 + 스크리닝 버튼 =====
    extra_filters = []
    if td_value_min > 0: extra_filters.append(f"대금≥{td_value_min}억")
    if td_vol_mult != 3.0: extra_filters.append(f"거래량×{td_vol_mult:.1f}")
    if td_close_high > 0: extra_filters.append(f"종/고≥{td_close_high:.2f}")
    if td_ret_min > 0: extra_filters.append(f"당일≥{td_ret_min:.0f}%")
    if td_ret_max > 0: extra_filters.append(f"당일≤{td_ret_max:.0f}%")
    if td_ret20_min > 0: extra_filters.append(f"20일≥{td_ret20_min:.0f}%")
    extra_str = " · ".join(extra_filters) if extra_filters else "기본값"

    st.markdown(
        f'<div style="padding:0.875rem 1.25rem;background:#F2F4F6;border-radius:8px;'
        f'margin:1rem 0 0.5rem 0;color:#191F28;line-height:1.7;">'
        f'📊 <b>최종 설정 요약</b><br>'
        f'• 기준일: <b>{target_date}</b> · 유사도: <b>≥{sim_threshold:.2f}</b><br>'
        f'• 추천: <b>{max_recommend}개</b> · 매수금: <b>{fmt_won_kr(today_buy_won)}</b><br>'
        f'• 추가 필터: <b>{extra_str}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )
    run = st.button("🔍 스크리닝 — 위 설정으로 조회",
                      type="primary", use_container_width=True, key="today_run")

    # v1 호환 임계치값 사용
    min_value_eok = td_value_min if td_value_min > 0 else 50
    volume_mult = td_vol_mult
    high_window_today = 60
    close_to_high = td_close_high if td_close_high > 0 else 0.70
    ret_min = (td_ret_min / 100) if td_ret_min > 0 else 0.05
    ret_max = (td_ret_max / 100) if td_ret_max > 0 else 0.30

    p = Params(
        min_value=min_value_eok * 1e8,
        volume_mult=volume_mult,
        high_window=int(high_window_today),
        close_to_high=close_to_high,
        daily_ret_min=ret_min,
        daily_ret_max=ret_max,
        require_score=int(require_score),
    )
    top_n_universe = 3000

    if not run:
        empty_state("📊", "스크리닝 대기 중",
                     "위에서 기준일과 조건을 선택하고 [스크리닝] 버튼을 누르세요.")
        return

    date_str = target_date.strftime("%Y%m%d")
    universe = cached_universe(n=int(top_n_universe))

    # 시총 컷오프 적용
    if only_large_cap:
        listing = get_krx_listing()
        large_codes = set(listing[listing["Marcap"] >= size_cutoff]["Code"])
        universe = [t for t in universe if t in large_codes]
        cutoff_label = "5천억" if size_cutoff == 5e11 else "1조"
        st.info(f"🎯 v3.7 프리셋: 시총 {cutoff_label}원 이상 **{len(universe)}종목**만 분석")

    end_dt = dt.datetime.strptime(date_str, "%Y%m%d")
    start_dt = end_dt - dt.timedelta(days=200)
    target_dt = pd.to_datetime(date_str)

    # 시장 필터: KOSPI 20일선 위인지 확인
    kospi_above_ma = True
    if apply_market_filter:
        kospi = get_index_ohlcv("KS11", start_dt.strftime("%Y%m%d"), date_str)
        if not kospi.empty:
            kospi["ma20"] = kospi["close"].rolling(20).mean()
            # 마지막 가용일 기준
            last_row = kospi.iloc[-1]
            kospi_above_ma = bool(last_row["close"] > last_row["ma20"])
            if kospi_above_ma:
                st.success(f"✅ 시장 필터 통과 — KOSPI {last_row['close']:.0f} > "
                            f"20MA {last_row['ma20']:.0f}")
            else:
                st.error(f"❌ 시장 필터 차단 — KOSPI {last_row['close']:.0f} < "
                          f"20MA {last_row['ma20']:.0f}. 이 프리셋은 매수 보류 권장.")
                empty_state("🛑", "시장 필터에 의해 매수 보류",
                             "KOSPI가 20일선 아래라 v3.7 전략 조건을 만족 안 함. "
                             "프리셋을 'v3.0 (필터 없음)'으로 바꾸거나 시장 회복 대기.")
                return

    progress = st.progress(0.0, text="OHLCV 로딩 중…")
    results = []

    # v3 모드: 사례 프로파일 로드 (combined 합본 12,798)
    case_profile = build_profile(combined=True) if use_v3_today else None

    for i, ticker in enumerate(universe):
        progress.progress((i + 1) / max(len(universe), 1),
                          text=f"분석 중 ({i+1}/{len(universe)}) {ticker}")
        try:
            hist = get_ohlcv(ticker, start_dt.strftime("%Y%m%d"), date_str)
            hw = 60   # 신고가/RSI 윈도우 고정
            if hist.empty or len(hist) < hw or target_dt not in hist.index:
                continue

            if use_v3_today:
                # v3 시그널 계산
                p_v3 = ParamsV3(min_similarity=sim_threshold)
                sig = add_signals_v3(hist, case_profile, p_v3)
                if target_dt not in sig.index:
                    continue
                row = sig.loc[target_dt]
                if not bool(row.get("signal", False)):
                    continue
                today = hist.loc[target_dt]
                prev_close = hist.iloc[-2]["close"]
                ret = (today["close"] / prev_close) - 1
                avg_vol = hist.iloc[-60:]["volume"].mean()
                high_n = hist.iloc[-60:]["high"].max()
                results.append({
                    "ticker": ticker,
                    "name": get_name(ticker),
                    "score": int(row["similarity"] * 10),  # 0~10 표시용
                    "similarity": float(row["similarity"]),
                    "close": int(today["close"]),
                    "ret_pct": round(ret * 100, 2),
                    "ret_20d_pct": round(float(row.get("ret_20d", 0)) * 100, 2),
                    "value_eok": today["value"] / 1e8,
                    "vol_ratio": today["volume"] / avg_vol,
                    "close_to_high": today["close"] / today["high"],
                    "rsi": float(row.get("rsi_14", 0)),
                    "high_60": int(high_n),
                    "is_new_high": today["close"] >= high_n,
                })
            else:
                hn = hist.iloc[-hw:]
                high_n = hn["high"].max()
                avg_vol = hn["volume"].mean()
                today = hist.loc[target_dt]
                prev_close = hist.iloc[-2]["close"] if len(hist) > 1 else today["close"]
                ret = (today["close"] / prev_close) - 1

                score = 0
                score += int(today["close"] >= high_n)
                score += int(today["volume"] >= avg_vol * p.volume_mult)
                score += int(today["value"] >= p.min_value)
                score += int(today["close"] >= today["high"] * p.close_to_high)
                score += int(p.daily_ret_min <= ret <= p.daily_ret_max)

                if score >= p.require_score:
                    results.append({
                        "ticker": ticker,
                        "name": get_name(ticker),
                        "score": score,
                        "similarity": 0.0,
                        "close": int(today["close"]),
                        "ret_pct": round(ret * 100, 2),
                        "ret_20d_pct": 0.0,
                        "value_eok": today["value"] / 1e8,
                        "vol_ratio": today["volume"] / avg_vol,
                        "close_to_high": today["close"] / today["high"],
                        "rsi": 0.0,
                        "high_60": int(high_n),
                        "is_new_high": today["close"] >= high_n,
                    })
        except Exception:
            continue
    progress.empty()

    if not results:
        empty_state("🔭", "조건 충족 종목 없음",
                     "임계치를 낮추거나 다른 날짜를 시도해보세요.")
        return

    # v3: 유사도 순 / v1: 거래대금 순, 상위 N개만
    sort_col = "similarity" if use_v3_today else "value_eok"
    df = pd.DataFrame(results).sort_values(sort_col, ascending=False).reset_index(drop=True)
    if len(df) > max_recommend:
        df = df.head(int(max_recommend))

    # 요약 KPI
    section_title("요약")
    if use_v3_today:
        kpi_row([
            ("후보 종목", f"{len(df)}", f"유니버스 {len(universe)}개 중", ""),
            ("유사도 0.8+", f"{(df['similarity']>=0.8).sum()}", "사례와 거의 동일", "success"),
            ("유사도 0.7+", f"{(df['similarity']>=0.7).sum()}", "사례 강한 일치",
             "success" if (df['similarity']>=0.7).sum() > 0 else ""),
            ("최고 유사도", f"{df.iloc[0]['similarity']:.2f}",
             df.iloc[0]['name'][:12], "success"),
        ])
    else:
        kpi_row([
            ("후보 종목", f"{len(df)}", f"유니버스 {len(universe)}개 중", ""),
            ("5점 만점", f"{(df['score']==5).sum()}", "모든 조건 충족", "success"),
            ("4점", f"{(df['score']==4).sum()}", "1개 조건 미달", "warning" if (df['score']==4).sum() > 0 else ""),
            ("대장주", df.iloc[0]['name'][:12] + "..." if len(df.iloc[0]['name']) > 12 else df.iloc[0]['name'],
             f"거래대금 {df.iloc[0]['value_eok']:.0f}억", ""),
        ])

    # 테마/뉴스 enrich
    tc1, tc2 = st.columns(2)
    fetch_extras = tc1.toggle("🎯 테마·뉴스 가져오기 (네이버 금융)", value=True,
                                help="각 종목의 소속 테마와 최신 뉴스 헤드라인을 표시")
    theme_only = tc2.toggle("🔥 주도 테마(상승률 ≥ 0%) 소속 종목만",
                              value=False,
                              help="네이버 금융 등락률 양수 테마에 속한 종목만 표시 — 진짜 종가 베팅 조건")

    enriched = []
    if fetch_extras:
        with st.spinner("테마/뉴스 로딩…"):
            try:
                # 더 많은 테마 확보 (40개)
                top_themes = scraper.fetch_top_themes(limit=40)
                # theme_only 필터를 위해 상승 테마만 따로
                rising_themes = [t for t in top_themes if t.change_pct > 0]
            except Exception:
                top_themes = []
                rising_themes = []
            for _, row in df.iterrows():
                try:
                    themes = scraper.find_themes_for_stock(row["ticker"], themes=top_themes)
                except Exception:
                    themes = []
                try:
                    news_objs = scraper.fetch_stock_news(row["ticker"], limit=2)
                    news = [{"title": n.title, "source": n.source, "url": n.url}
                             for n in news_objs]
                except Exception:
                    news = []
                # 주도 테마 (상승 테마) 소속 여부
                rising_names = {t.name for t in rising_themes}
                is_in_rising = any(name in rising_names for name in themes)
                enriched.append({"themes": themes, "news": news,
                                  "in_rising": is_in_rising})
    else:
        enriched = [{"themes": [], "news": [], "in_rising": False} for _ in range(len(df))]

    # theme_only 필터링
    if theme_only and fetch_extras:
        filtered_idx = [i for i, e in enumerate(enriched) if e["in_rising"]]
        df = df.iloc[filtered_idx].reset_index(drop=True)
        enriched = [enriched[i] for i in filtered_idx]
        st.info(f"🔥 주도 테마 필터 적용: {len(df)}개 종목 (전체 {len(enriched)}개 중)")

    if df.empty:
        empty_state("🔭", "조건 충족 종목 없음", "필터를 해제하거나 임계치를 낮춰보세요.")
        return

    # ====== 테마별 분류 — 대장주/2등주/3등주 + 개별주 ======
    # 1) 각 종목의 primary theme 결정
    df_t = df.copy().reset_index(drop=True)
    df_t["primary_theme"] = [
        (enriched[i]["themes"][0] if (i < len(enriched) and enriched[i]["themes"]) else None)
        for i in range(len(df_t))
    ]
    df_t["themes_all"] = [enriched[i]["themes"] if i < len(enriched) else [] for i in range(len(df_t))]
    df_t["news"] = [enriched[i]["news"] if i < len(enriched) else [] for i in range(len(df_t))]

    # 2) 점수: 거래대금(억) × 등락률(%) - 한 테마 내 대장주 식별용
    df_t["theme_score"] = df_t["value_eok"] * df_t["ret_pct"].clip(lower=0.01)

    # 3) 테마별 정렬 + 개별주
    theme_groups: dict[str, list] = {}
    individual: list = []
    for _, row in df_t.iterrows():
        if row["primary_theme"]:
            theme_groups.setdefault(row["primary_theme"], []).append(row)
        else:
            individual.append(row)

    # 4) 테마 정렬: 평균 점수가 높은 테마 먼저
    sorted_themes = sorted(
        theme_groups.items(),
        key=lambda kv: sum(r["theme_score"] for r in kv[1]) / len(kv[1]),
        reverse=True,
    )

    # 5) 테마별 카드 렌더링
    if sorted_themes:
        section_title(f"🔥 테마별 주도주 (TOP 3)", count=len(sorted_themes))
        for theme_name, rows in sorted_themes:
            # 점수 내림차순 정렬 후 1,2,3위만
            ranked = sorted(rows, key=lambda r: r["theme_score"], reverse=True)[:3]
            tot_count = len(rows)

            st.markdown(
                f'<div style="margin:1.25rem 0 0.5rem 0;display:flex;align-items:baseline;gap:0.75rem;">'
                f'<h4 style="margin:0;font-size:1.05rem;">🔥 {theme_name}</h4>'
                f'<span style="color:#8B95A1;font-size:0.8125rem;">'
                f'시그널 종목 {tot_count}개 · 대장주/2등주/3등주 표시</span></div>',
                unsafe_allow_html=True,
            )
            cards_html = []
            for idx, row in enumerate(ranked):
                # 배지 결정
                if idx == 0:
                    badge = '<span class="tag accent">🏆 대장주</span>'
                elif idx == 1:
                    badge = '<span class="tag warning">🥈 2등주</span>'
                else:
                    badge = '<span class="tag" style="background:rgba(255,159,46,0.08);color:#FF9F2E;border-color:rgba(255,159,46,0.2);">🥉 3등주</span>'
                # themes_all 리스트 + custom badge
                themes_with_badge = [f"##BADGE:{badge}"] + (row["themes_all"] or [])
                cards_html.append(stock_card_html(
                    rank=idx + 1,
                    name=row["name"],
                    ticker=row["ticker"],
                    score=int(row["score"]),
                    close=int(row["close"]),
                    ret_pct=row["ret_pct"],
                    value_eok=row["value_eok"],
                    vol_ratio=row["vol_ratio"],
                    close_to_high=row["close_to_high"],
                    is_new_high=bool(row["is_new_high"]),
                    themes=themes_with_badge,
                    news=row["news"],
                ))
            st.markdown("\n".join(cards_html), unsafe_allow_html=True)

    # 6) 개별주 섹션
    if individual:
        section_title("⚪ 개별주 (테마 미소속)", count=len(individual))
        # 거래대금 순
        individual_sorted = sorted(individual, key=lambda r: r["value_eok"], reverse=True)
        cards_html = []
        for idx, row in enumerate(individual_sorted):
            badge = '<span class="tag" style="background:rgba(139,149,161,0.1);color:#4E5968;">개별주</span>'
            themes_with_badge = [f"##BADGE:{badge}"]
            cards_html.append(stock_card_html(
                rank=idx + 1,
                name=row["name"],
                ticker=row["ticker"],
                score=int(row["score"]),
                close=int(row["close"]),
                ret_pct=row["ret_pct"],
                value_eok=row["value_eok"],
                vol_ratio=row["vol_ratio"],
                close_to_high=row["close_to_high"],
                is_new_high=bool(row["is_new_high"]),
                themes=themes_with_badge,
                news=row["news"],
            ))
        st.markdown("\n".join(cards_html), unsafe_allow_html=True)

    # 다운로드
    csv = df_t.to_csv(index=True).encode("utf-8-sig")
    st.download_button("📥 CSV 다운로드", csv, f"closing_bet_{date_str}.csv",
                       "text/csv", use_container_width=True)
    return

    # (구) 단순 거래대금 순 카드 — 아래는 죽은 코드 (도달 X)
    section_title("추천 종목", count=len(df))
    cards_html = []
    for i, row in df.iterrows():
        ex = enriched[i] if i < len(enriched) else {"themes": [], "news": []}
        cards_html.append(stock_card_html(
            rank=i + 1,
            name=row["name"],
            ticker=row["ticker"],
            score=int(row["score"]),
            close=int(row["close"]),
            ret_pct=row["ret_pct"],
            value_eok=row["value_eok"],
            vol_ratio=row["vol_ratio"],
            close_to_high=row["close_to_high"],
            is_new_high=bool(row["is_new_high"]),
            themes=themes_with_badge,
            news=ex["news"],
        ))
    st.markdown("\n".join(cards_html), unsafe_allow_html=True)

    # 다운로드
    csv = df.to_csv(index=True).encode("utf-8-sig")
    st.download_button("📥 CSV 다운로드", csv, f"closing_bet_{date_str}.csv",
                       "text/csv", use_container_width=True)


# ====================================================================
# 페이지 2: 백테스트 결과 — 연도 필터 + 실시간 파라미터 조정
# ====================================================================
@st.cache_data(show_spinner="OHLCV 패널 로딩…")
def load_full_panel(tickers: tuple[str, ...], start: str, end: str) -> dict:
    out = {}
    for t in tickers:
        df = get_ohlcv(t, start, end)
        if not df.empty and len(df) >= 80:
            out[t] = df
    return out


def _plot_equity(trades: pd.DataFrame, title: str = "",
                  start_date: str | None = None, end_date: str | None = None):
    """누적 수익 곡선. 한국식: 이익=빨강, 손실=파랑.
    기준선 1.0 위는 빨강 영역, 아래는 파랑 영역으로 표시."""
    if trades.empty:
        return None
    daily = trades.groupby("entry_date")["net"].mean()
    equity = (1 + daily).cumprod()

    if start_date and end_date:
        s = pd.to_datetime(start_date)
        e = pd.to_datetime(end_date)
        # 시작점 1.0 강제 삽입 (첫 거래 이전 평평한 구간 보장)
        if s not in equity.index:
            equity = pd.concat([pd.Series([1.0], index=[s]), equity]).sort_index()
        all_days = pd.date_range(s, e, freq="B")
        equity = equity.reindex(all_days).ffill().fillna(1.0)

    # 1.0 위/아래 분리 시리즈
    above = equity.where(equity >= 1.0, 1.0)
    below = equity.where(equity <= 1.0, 1.0)
    final_color = PALETTE["danger"] if equity.iloc[-1] >= 1.0 else PALETTE["accent"]

    fig = go.Figure()
    # 빨강 영역 (이익)
    fig.add_trace(go.Scatter(
        x=above.index, y=above.values, mode="lines",
        line=dict(color="rgba(240,68,82,0)", width=0),
        fill="tonexty", fillcolor="rgba(240,68,82,0.15)",
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[equity.index[0], equity.index[-1]], y=[1.0, 1.0],
        mode="lines", line=dict(color=PALETTE["text_mute"], dash="dash", width=1),
        showlegend=False, hoverinfo="skip",
    ))
    # 파랑 영역 (손실)
    fig.add_trace(go.Scatter(
        x=below.index, y=below.values, mode="lines",
        line=dict(color="rgba(49,130,246,0)", width=0),
        fill="tonexty", fillcolor="rgba(49,130,246,0.15)",
        showlegend=False, hoverinfo="skip",
    ))
    # 메인 라인
    fig.add_trace(go.Scatter(
        x=equity.index, y=equity.values, mode="lines",
        line=dict(color=final_color, width=2.5),
        name="Equity",
    ))
    fig.update_layout(
        height=380, paper_bgcolor=PALETTE["bg"], plot_bgcolor=PALETTE["bg"],
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis=dict(title="누적 배수", gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
        xaxis=dict(gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
        font=dict(family="Pretendard", color=PALETTE["text"]),
        title=title, showlegend=False,
    )
    return fig


def page_backtest():
    hero(
        eyebrow="5년 백테스트",
        title="백테스트 분석",
        lead="2021–2026 · 시총 2,000억 이상 1,057종목. 디폴트값으로 자동 실행. 한국식 색상(빨강=익절, 파랑=손절).",
    )
    # 첫 진입 시 자동 실행 + 캐시 강제 클리어
    if "bt_first_run" not in st.session_state:
        st.session_state.bt_first_run = True
        st.cache_data.clear()  # 1057종목 확장 반영 위해 1회 클리어

    # 한국식 색상 함수 (페이지 전체에서 사용)
    RED = "#F04452"
    BLUE = "#3182F6"

    def _color_pnl_num(v):
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        try:
            if v > 0: return f"color: {RED}; font-weight: 800;"
            if v < 0: return f"color: {BLUE}; font-weight: 800;"
        except TypeError:
            return ""
        return ""

    def _color_won_str(v):
        if not isinstance(v, str): return ""
        if v.startswith("-"): return f"color: {BLUE}; font-weight: 800;"
        if v == "0원" or v == "-": return ""
        return f"color: {RED}; font-weight: 800;"

    def _color_exit_str(v):
        if v == "손절": return f"color: {BLUE}; font-weight: 800;"
        if v == "익절": return f"color: {RED}; font-weight: 800;"
        return ""

    # ----- 시그널 + 유니버스 프리셋 (셀렉트박스 + 정보 카드) -----
    section_title("백테스트 프리셋")
    PRESETS_BT = {
        "⭐ v3.7 — 시총 5천억+ (추천)": (5e11, True, 2.48, 3.94, 565),
        "🏆 v3.7 — 시총 1조+ (샤프 2.89)": (1e12, True, 2.89, 4.75, 366),
        "📊 v3.1 — 시장 필터 (전체)": (0, True, 1.47, 2.40, 1534),
        "🌐 v3.0 — 기본 (전체)": (0, True, 1.02, 1.70, 1534),
        "❌ v1 — 기존 5대 조건": (0, False, 0.40, 0.17, 1534),
    }
    bt_preset = st.selectbox(
        "🎯 백테스트 프리셋", list(PRESETS_BT.keys()),
        index=0, key="bt_preset",
    )
    bt_cap_cutoff, use_v3, bt_sharpe, bt_mean, bt_stocks = PRESETS_BT[bt_preset]
    use_v2 = False
    color = "#00C896" if bt_sharpe >= 1.5 else ("#FF9F2E" if bt_sharpe >= 1.0 else "#F04452")
    st.markdown(
        f'<div style="display:flex;gap:1rem;padding:0.875rem 1.25rem;'
        f'background:rgba(49,130,246,0.06);border-left:4px solid {color};'
        f'border-radius:8px;margin-bottom:1rem;">'
        f'<div><b>샤프 {bt_sharpe:.2f}</b></div>'
        f'<div style="color:#4E5968;">평균 +{bt_mean:.2f}%</div>'
        f'<div style="color:#4E5968;">종목 풀 {bt_stocks:,}개</div>'
        f'<div style="color:#8B95A1;flex:1;text-align:right;">5년 백테스트 검증 결과</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if use_v3:
        st.success("⭐ **v3 (사례 유사도)** — 사례 39개 9개 지표 분포 기반. 익일 청산보다 **30일 보유** 권장. "
                    "거래당 평균 +1.7%, 샤프 1.02 (5년 검증).")
    elif use_v2:
        st.info("📊 **v2 조건**: ① 거래대금 ≥50억  ② 거래량 ×3  ③ 종가 > 20일선 AND > 60일선  "
                 "④ 종가/고가 ≥0.92  ⑤ 당일 ≥5% OR 20일 누적 ≥15%")
    else:
        st.warning("⚠️ **v1 조건** (사례 39개 중 단 1개만 5/5 충족 — 95% 놓침): "
                    "① 60일 신고가 돌파  ② 거래량 ×3  ③ 거래대금 ≥50억  ④ 종가/고가 ≥0.97  ⑤ 등락률 5~25%")

    # v3 전용 파라미터
    if use_v3:
        with st.expander("⚙️ v3 사례 유사도 파라미터", expanded=True):
            v3_sim_threshold = st.slider(
                "사례 유사도 임계치", 0.3, 0.9, 0.6, 0.05,
                help="0.6 = 9개 지표 평균 0.6점 이상 (사례 Q25~Q75 영역 충족 비율). 높을수록 빡빡."
            )
            st.caption(f"임계치 {v3_sim_threshold} 기준 5년 누적 시그널 수 예상: "
                        f"{['58,421(0.5)', '23,180(0.6)', '8,455(0.7)', '2,518(0.8)'][int((v3_sim_threshold-0.5)/0.1)] if v3_sim_threshold >= 0.5 else '많음'}")
    else:
        v3_sim_threshold = 0.6

    # ----- 파라미터 입력 (모든 값 자유 커스텀) -----
    section_title("파라미터 · 자유 커스텀")
    st.caption("디폴트값: 코스닥 포함 완화 셋업. 모든 입력 하한 제약 없음. 손절 0% = 손절 없음.")
    with st.container():
        c1, c2, c3, c4, c5 = st.columns(5)
        year = c1.selectbox("연도", ["2026", "2025", "2024", "2023", "2022", "2021", "전체"], index=0)
        min_value_eok = c2.number_input("거래대금 (억원 ≥)",
                                          value=50, step=10, format="%d",
                                          help="0 이상 어떤 값도 가능. 코스닥 포함하려면 100억 이하 권장.")
        volume_mult = c3.number_input("거래량 배수 (60일 평균 ×)",
                                       value=3.0, step=0.5, format="%.2f",
                                       help="1.0 미만도 가능.")
        high_window = c4.number_input("신고가 기간 (일)",
                                       value=60, step=5, min_value=2, format="%d")
        require_score = c5.selectbox("최소 충족 조건 수",
                                      [1, 2, 3, 4, 5], index=3,
                                      help="1=하나라도, 5=전부 충족")

        c1, c2, c3, c4, c5 = st.columns(5)
        close_to_high = c1.number_input("종가/고가 비율 ≥",
                                          value=0.70, step=0.01, format="%.3f",
                                          help="낮을수록 조건 완화.")
        ret_min = c2.number_input("최소 등락률 (%)",
                                    value=7.0, step=0.5, format="%.2f")
        ret_max = c3.number_input("최대 등락률 (%)",
                                    value=28.0, step=1.0, format="%.2f")
        top_k = c4.number_input("일별 매수 종목 수",
                                 value=5, step=1, min_value=1, format="%d")
        stop_pct = c5.number_input("손절 (%, 0=없음)",
                                     value=0.0, step=0.5, format="%.2f",
                                     help="0 또는 양수는 손절 없음으로 처리.")
        stop_loss = (stop_pct / 100) if stop_pct < 0 else None

        c1, c2, c3 = st.columns([1, 1, 2])
        cost = c1.number_input("거래 비용 (%, 왕복)",
                                 value=0.3, step=0.1, format="%.2f")
        capital_man = c2.number_input("종목당 투입금 (만원)",
                                       value=100, step=10, min_value=10, max_value=100000,
                                       format="%d")
        run = c3.button("⚡ 백테스트 실행", type="primary", use_container_width=True)
    capital_won = capital_man * 10000

    # ----- 청산 전략 (항상 4가지 보유 기간 비교) -----
    section_title("청산 전략 · 보유 기간 비교 (1/30/60/90일)")
    st.caption("4가지 보유 기간 자동 비교. 메인 분석은 선택된 기간 결과. "
                "TP 활성화 시 도달하면 분할 청산, 미도달 시 만기일 시초가 청산.")

    cc1, cc2, cc3 = st.columns([1, 1, 2])
    main_period = cc1.selectbox("메인 분석 기간",
                                  ["1일 (익일 종가)", "30일", "60일", "90일"],
                                  index=0, key="main_period")
    enable_tp = cc2.toggle("TP1/TP2 분할 청산", value=False,
                            help="활성화 시 보유 기간 중 TP1/TP2 도달하면 분할 청산.")
    cc3.empty()

    tp1_pct, tp2_pct, tp1_size, tp2_size = 1.0, 2.0, 0.5, 0.5
    if enable_tp:
        tc1, tc2, tc3, tc4 = st.columns(4)
        tp1_pct = tc1.number_input("TP1 (%)", value=100.0, step=10.0, format="%.1f") / 100
        tp2_pct = tc2.number_input("TP2 (%)", value=200.0, step=10.0, format="%.1f") / 100
        tp1_size = tc3.number_input("TP1 청산 비중 (%)", value=50.0, step=5.0, format="%.0f") / 100
        tp2_size = tc4.number_input("TP2 청산 비중 (%)", value=50.0, step=5.0, format="%.0f") / 100

    PERIOD_MAP = {"1일 (익일 종가)": 1, "30일": 30, "60일": 60, "90일": 90}
    main_hold_days = PERIOD_MAP[main_period]
    # v3 권장: 30일 보유. v1/v2 권장: 1일 보유.
    if use_v3 and main_hold_days == 1:
        st.warning("⚠️ v3는 30일 보유가 권장입니다 (1일은 익일 청산 손실 큼). "
                    "메인 분석 기간을 '30일'로 변경하세요.")

    # 첫 진입 시 디폴트값으로 자동 실행
    if st.session_state.bt_first_run:
        st.session_state.bt_first_run = False
        run = True

    # ----- 기간 결정 -----
    if year == "전체":
        start, end = "20210101", "20260517"
        period_label = "2021-01 ~ 2026-05"
    else:
        start, end = f"{year}0101", f"{year}1231"
        period_label = f"{year}년 전체"

    # ----- 백테스트 실행 -----
    if use_v3:
        p = ParamsV3(
            min_similarity=v3_sim_threshold,
            top_k_per_day=int(top_k),
            stop_loss=stop_loss,
            cost_per_trade=cost / 100,
        )
        case_profile = build_profile()
    elif use_v2:
        p = ParamsV2(
            min_value=min_value_eok * 1e8,
            volume_mult=volume_mult,
            close_to_high=close_to_high,
            daily_ret_min=ret_min / 100,
            ret_20d_min=0.15,
            ma_window_short=20,
            ma_window_long=60,
            require_score=int(require_score),
            top_k_per_day=int(top_k),
            stop_loss=stop_loss,
            cost_per_trade=cost / 100,
        )
    else:
        p = Params(
            min_value=min_value_eok * 1e8,
            volume_mult=volume_mult,
            high_window=int(high_window),
            close_to_high=close_to_high,
            daily_ret_min=ret_min / 100,
            daily_ret_max=ret_max / 100,
            require_score=int(require_score),
            top_k_per_day=int(top_k),
            stop_loss=stop_loss,
            cost_per_trade=cost / 100,
        )

    universe = cached_universe()
    # 시총 컷오프 적용 (백테스트 프리셋)
    if bt_cap_cutoff > 0:
        listing = get_krx_listing()
        eligible = set(listing[listing["Marcap"] >= bt_cap_cutoff]["Code"])
        universe = [t for t in universe if t in eligible]
        cutoff_lbl = "5천억" if bt_cap_cutoff == 5e11 else "1조"
        st.info(f"🎯 시총 {cutoff_lbl}원 이상 **{len(universe)}종목**만 백테스트")
    warmup_start = (pd.to_datetime(start, format="%Y%m%d")
                     - pd.Timedelta(days=200)).strftime("%Y%m%d")
    raw = load_full_panel(tuple(universe), warmup_start, end)

    ver_label = "v3" if use_v3 else ("v2" if use_v2 else "v1")
    with st.spinner(f"시그널 계산 + 백테스트 ({period_label}, {ver_label})…"):
        if use_v3:
            sig_data = {t: add_signals_v3(df, case_profile, p) for t, df in raw.items()}
        elif use_v2:
            sig_data = {t: add_signals_v2(df, p) for t, df in raw.items()}
        else:
            sig_data = {t: add_signals(df, p) for t, df in raw.items()}
        bd = cached_business_days(start, end)

        # 항상 4가지 보유 기간 다 실행
        periods = [1, 30, 60, 90]
        tiered_results = {}
        # 1일 보유는 기존 backtest 함수 (익일 종가 청산)
        # 30/60/90일은 backtest_tiered (TP1/TP2 + 만기 시초가)
        for h in periods:
            if h == 1 and not enable_tp:
                # 1일 = 익일 종가 청산
                if use_v3:
                    t_df = backtest_v3(sig_data, bd, p, hold_days=1)
                elif use_v2:
                    t_df = backtest_v2(sig_data, bd, p)
                else:
                    t_df = backtest(sig_data, bd, p)
            else:
                # 30/60/90일 또는 TP 활성 — backtest_tiered만 지원 (v2도 호환되도록 Params 어댑트)
                tp1 = tp1_pct if enable_tp else 99.0
                tp2 = tp2_pct if enable_tp else 99.0
                if use_v3:
                    # v3는 backtest_v3 (보유 기간 N일)
                    t_df = backtest_v3(sig_data, bd, p, hold_days=h)
                elif use_v2:
                    p_compat = Params(
                        min_value=p.min_value, volume_mult=p.volume_mult,
                        high_window=60, close_to_high=p.close_to_high,
                        daily_ret_min=p.daily_ret_min, daily_ret_max=0.30,
                        require_score=p.require_score, top_k_per_day=p.top_k_per_day,
                        stop_loss=p.stop_loss, cost_per_trade=p.cost_per_trade,
                    )
                    t_df = backtest_tiered(sig_data, bd, p_compat, hold_days=h,
                                            tp1_pct=tp1, tp2_pct=tp2,
                                            tp1_size=tp1_size, tp2_size=tp2_size)
                else:
                    t_df = backtest_tiered(sig_data, bd, p, hold_days=h,
                                            tp1_pct=tp1, tp2_pct=tp2,
                                            tp1_size=tp1_size, tp2_size=tp2_size)
            tiered_results[h] = (t_df, metrics(t_df))

        # 메인 분석은 사용자가 선택한 기간
        trades = tiered_results[main_hold_days][0]
        m = tiered_results[main_hold_days][1]

    # ----- 청산 전략 비교 표 (항상 표시) -----
    if tiered_results is not None:
        section_title("📊 보유 기간 비교 — 1일 / 30일 / 60일 / 90일")
        if enable_tp:
            st.caption(f"TP1 +{tp1_pct*100:.0f}% 도달 시 {tp1_size*100:.0f}% 청산 / "
                        f"TP2 +{tp2_pct*100:.0f}% 도달 시 추가 {tp2_size*100:.0f}% 청산 / "
                        f"잔량 만기일 시초가 청산")
        else:
            st.caption("1일=익일 종가 청산 / 30·60·90일=만기일 시초가 청산 (TP 비활성)")

        comp_rows = []
        for h, (tdf, mh) in tiered_results.items():
            if tdf.empty:
                comp_rows.append({
                    "보유일": f"{h}일", "거래수": 0,
                    "TP1 도달률": 0, "TP2 도달률": 0,
                    "승률": 0, "평균 순수익": 0, "누적": 0, "샤프": 0, "MDD": 0,
                    "총 손익(원)": "-",
                })
                continue
            row = {
                "보유일": f"{h}일",
                "거래수": mh["n"],
                "TP1 도달률": tdf["tp1_hit"].mean() if "tp1_hit" in tdf.columns else 0,
                "TP2 도달률": tdf["tp2_hit"].mean() if "tp2_hit" in tdf.columns else 0,
                "승률": mh["win_rate"],
                "평균 순수익": mh["mean_ret"],
                "누적": mh["total_ret"],
                "샤프": mh["sharpe"],
                "MDD": mh["mdd"],
                "총 손익(원)": fmt_won_kr(tdf["net"].sum() * capital_won),
            }
            # 메인 선택 표시
            if h == main_hold_days:
                row["보유일"] = f"⭐ {row['보유일']}"
            comp_rows.append(row)
        comp_df = pd.DataFrame(comp_rows)

        comp_styler = comp_df.style.format({
            "TP1 도달률": "{:.1%}", "TP2 도달률": "{:.1%}",
            "승률": "{:.1%}", "평균 순수익": "{:+.2%}",
            "누적": "{:+.2%}", "샤프": "{:.2f}", "MDD": "{:.2%}",
        })
        for c in ["평균 순수익", "누적"]:
            comp_styler = comp_styler.applymap(_color_pnl_num, subset=[c])
        comp_styler = comp_styler.applymap(_color_won_str, subset=["총 손익(원)"])
        st.dataframe(comp_styler, use_container_width=True, hide_index=True)

        # 보유 기간별 누적 곡선 비교
        section_title("보유 기간별 누적 수익 곡선")
        fig_cmp = go.Figure()
        colors = ["#F04452", "#FF9F2E", "#00C896", "#3182F6"]
        for (h, (tdf, _)), col in zip(tiered_results.items(), colors):
            if tdf.empty: continue
            tdf2 = tdf.copy()
            tdf2["entry_date"] = pd.to_datetime(tdf2["entry_date"])
            daily = tdf2.groupby("entry_date")["net"].mean()
            eq = (1 + daily).cumprod()
            fig_cmp.add_trace(go.Scatter(
                x=eq.index, y=eq.values, mode="lines", name=f"{h}일 보유",
                line=dict(color=col, width=2),
            ))
        fig_cmp.add_hline(y=1.0, line_dash="dash", line_color=PALETTE["text_mute"])
        fig_cmp.update_layout(
            height=400, paper_bgcolor=PALETTE["bg"], plot_bgcolor=PALETTE["bg"],
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis=dict(title="누적 배수", gridcolor=PALETTE["border_soft"]),
            xaxis=dict(gridcolor=PALETTE["border_soft"]),
            font=dict(family="Pretendard", color=PALETTE["text"]),
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        )
        st.plotly_chart(fig_cmp, use_container_width=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown(f"##### 아래 상세 분석은 **{main_period} 보유 기준** 결과입니다 "
                     f"(다른 기간은 위 비교표 참조). 메인 분석 기간은 상단 셀렉터에서 변경.")

    if m.get("n", 0) == 0:
        empty_state("🔭", f"{period_label} 거래 0건",
                     "조건이 너무 까다롭습니다. 임계치를 낮춰보세요.")
        return

    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    # entry_date 오름차순 정렬 보장 (1월부터 12월까지 순서대로 표시)
    trades = trades.sort_values("entry_date").reset_index(drop=True)
    # 원화 손익 계산
    trades["profit_won"] = trades["net"] * capital_won
    total_profit_won = trades["profit_won"].sum()
    avg_profit_won = trades["profit_won"].mean()

    # ----- KPI -----
    st.markdown(f'<div style="color:#8B95A1;font-size:0.875rem;margin-bottom:0.5rem;">'
                f'📅 {period_label} · 거래 {m["n"]:,}건 · 종목당 {fmt_won_kr(capital_won)} 투입</div>',
                unsafe_allow_html=True)

    section_title("성과 지표")
    tone_ret = "success" if m["total_ret"] > 0 else "danger"
    tone_win = "success" if m["win_rate"] > 0.55 else ("danger" if m["win_rate"] < 0.45 else "")
    kpi_row([
        ("총 거래", f"{m['n']:,}", period_label, ""),
        ("승률", f"{m['win_rate']*100:.1f}%", "이익 거래", tone_win),
        ("기댓값", fmt_pct(m["expectancy"]), "거래당", tone_ret),
        ("PF", f"{m['profit_factor']:.2f}", "이익/손실", ""),
        ("샤프", f"{m['sharpe']:.2f}", "연환산", ""),
        ("MDD", fmt_pct(m["mdd"]), "최대 낙폭", "danger"),
    ])

    # ----- 원화 손익 KPI -----
    section_title("원화 손익 (종목당 " + fmt_won_kr(capital_won) + " 가정)")
    tone_won = "success" if total_profit_won > 0 else "danger"
    kpi_row([
        ("총 손익", fmt_won_kr(total_profit_won), f"{m['n']:,}건 합산", tone_won),
        ("거래당 평균", fmt_won_kr(avg_profit_won), "비용 차감", tone_won),
        ("최대 1회 이익", fmt_won_kr(trades["profit_won"].max()), "단일 거래", "success"),
        ("최대 1회 손실", fmt_won_kr(trades["profit_won"].min()), "단일 거래", "danger"),
        ("이익 거래 합", fmt_won_kr(trades.loc[trades["profit_won"]>0, "profit_won"].sum()),
         f"{(trades['profit_won']>0).sum()}건", "success"),
        ("손실 거래 합", fmt_won_kr(trades.loc[trades["profit_won"]<=0, "profit_won"].sum()),
         f"{(trades['profit_won']<=0).sum()}건", "danger"),
    ])

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ----- 누적 곡선 (기간 시작일부터 표시) -----
    section_title("누적 수익 곡선")
    fig = _plot_equity(trades,
                       start_date=f"{start[:4]}-{start[4:6]}-{start[6:]}",
                       end_date=f"{end[:4]}-{end[4:6]}-{end[6:]}")
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    # 월별 거래수 (1월부터 12월까지 잘 보이게)
    section_title("월별 거래 분포")
    # 디버그: 거래 분포 요약
    first_d = trades["entry_date"].min().strftime("%Y-%m-%d")
    last_d = trades["entry_date"].max().strftime("%Y-%m-%d")
    st.caption(f"전체 거래 기간: **{first_d} ~ {last_d}** · 총 {len(trades):,}건")

    trades["월"] = trades["entry_date"].dt.to_period("M").astype(str)
    monthly = trades.groupby("월").agg(
        거래수=("net", "size"),
        평균수익=("net", "mean"),
        승률=("net", lambda x: (x > 0).mean()),
    ).reset_index()
    fig_m = go.Figure(go.Bar(
        x=monthly["월"], y=monthly["거래수"],
        marker=dict(color=[PALETTE["danger"] if r > 0 else PALETTE["accent"]
                            for r in monthly["평균수익"]]),
        text=[f"{w*100:.0f}% · {r:+.1%}" for w, r in zip(monthly["승률"], monthly["평균수익"])],
        textposition="outside",
    ))
    fig_m.update_layout(
        height=280, paper_bgcolor=PALETTE["bg"], plot_bgcolor=PALETTE["bg"],
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis=dict(title="거래 수", gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
        xaxis=dict(gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
        font=dict(family="Pretendard", color=PALETTE["text"]),
    )
    st.plotly_chart(fig_m, use_container_width=True)

    # ----- 연도별 비교 (전체 보기일 때) -----
    if year == "전체":
        section_title("연도별 성과")
        trades["year"] = trades["entry_date"].dt.year
        yearly = trades.groupby("year").agg(
            n=("net", "size"),
            win_rate=("net", lambda x: (x > 0).mean()),
            mean_ret=("net", "mean"),
            total_ret=("net", lambda x: (1 + x).prod() - 1),
        ).reset_index()

        fig_y = go.Figure()
        fig_y.add_trace(go.Bar(
            x=yearly["year"], y=yearly["total_ret"],
            marker=dict(color=[PALETTE["danger"] if r > 0 else PALETTE["accent"]
                                for r in yearly["total_ret"]]),
            text=[f"n={n} · 승률 {w*100:.0f}%" for n, w in zip(yearly["n"], yearly["win_rate"])],
            textposition="outside",
        ))
        fig_y.update_layout(
            height=320, paper_bgcolor=PALETTE["bg"], plot_bgcolor=PALETTE["bg"],
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis=dict(title="연 수익률", tickformat=".0%",
                       gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
            xaxis=dict(gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
            font=dict(family="Pretendard", color=PALETTE["text"]),
        )
        st.plotly_chart(fig_y, use_container_width=True)

        st.dataframe(
            yearly.style.format({
                "win_rate": "{:.1%}",
                "mean_ret": "{:+.2%}",
                "total_ret": "{:+.2%}",
            }),
            use_container_width=True,
        )

    # ----- 분포 & 랭크 -----
    col_l, col_r = st.columns(2)

    with col_l:
        section_title("수익률 분포")
        # 양/음 분리 히스토그램 (이익=빨강, 손실=파랑)
        wins = trades[trades["net"] > 0]["net"]
        losses = trades[trades["net"] <= 0]["net"]
        fig2 = go.Figure()
        fig2.add_trace(go.Histogram(
            x=losses, nbinsx=40, name=f"손실 ({len(losses)}건)",
            marker=dict(color=PALETTE["accent"], opacity=0.85),
        ))
        fig2.add_trace(go.Histogram(
            x=wins, nbinsx=40, name=f"이익 ({len(wins)}건)",
            marker=dict(color=PALETTE["danger"], opacity=0.85),
        ))
        fig2.update_layout(
            height=320, paper_bgcolor=PALETTE["bg"], plot_bgcolor=PALETTE["bg"],
            margin=dict(l=20, r=20, t=10, b=20),
            xaxis=dict(title="수익률", tickformat=".1%",
                       gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
            yaxis=dict(title="빈도", gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
            font=dict(family="Pretendard", color=PALETTE["text"]),
            barmode="overlay",
            legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col_r:
        section_title("랭크별 성과 (1=대장주)")
        if "rank" in trades.columns and not trades["rank"].isna().all():
            rank_perf = trades.groupby("rank").agg(
                win_rate=("net", lambda x: (x > 0).mean()),
                mean_ret=("net", "mean"),
                n=("net", "size"),
            ).reset_index()
            fig3 = go.Figure(go.Bar(
                x=rank_perf["rank"], y=rank_perf["mean_ret"],
                marker=dict(color=[PALETTE["danger"] if r > 0 else PALETTE["accent"]
                                    for r in rank_perf["mean_ret"]]),
                text=[f"{w*100:.0f}% · n={n}" for w, n in zip(rank_perf["win_rate"], rank_perf["n"])],
                textposition="outside",
            ))
            fig3.update_layout(
                height=320, paper_bgcolor=PALETTE["bg"], plot_bgcolor=PALETTE["bg"],
                margin=dict(l=20, r=20, t=10, b=20),
                xaxis=dict(title="랭크 (1=대장주)",
                           gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
                yaxis=dict(title="평균 수익", tickformat=".2%",
                           gridcolor=PALETTE["border_soft"], color=PALETTE["text_sub"]),
                font=dict(family="Pretendard", color=PALETTE["text"]),
            )
            st.plotly_chart(fig3, use_container_width=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ----- 거래 내역 -----
    section_title("거래 내역", count=len(trades))

    # 시장(코스피/코스닥) 정보 가져오기
    @st.cache_data(show_spinner=False)
    def _market_map() -> dict[str, str]:
        listing = get_krx_listing()
        return dict(zip(listing["Code"], listing["Market"]))

    market_map = _market_map()
    show = trades.copy()
    entry_dt = pd.to_datetime(show["entry_date"])
    exit_dt = pd.to_datetime(show["exit_date"])
    show["보유일"] = (exit_dt - entry_dt).dt.days
    show["entry_date"] = entry_dt.dt.strftime("%Y-%m-%d")
    show["exit_date"] = exit_dt.dt.strftime("%Y-%m-%d")
    show["name"] = show["ticker"].map(get_name)
    show["market"] = show["ticker"].map(lambda c: market_map.get(c, "-"))
    show["exit_reason"] = show["exit_reason"].map(lambda x: EXIT_REASON_KR.get(x, x))
    show["profit_won_kr"] = show["profit_won"].apply(fmt_won_kr)
    show_kr = show.rename(columns={
        "entry_date": "진입일", "exit_date": "청산일",
        "name": "종목명", "ticker": "코드", "market": "시장",
        "rank": "랭크", "score": "점수",
        "entry": "진입가", "exit": "청산가",
        "gross": "총수익", "net": "순수익",
        "gap": "갭수익", "max_gain": "최고가수익",
        "exit_reason": "청산사유",
        "profit_won_kr": "손익(원)",
    })

    # 시장별 통계 (코스피/코스닥 분리)
    if "시장" in show_kr.columns:
        mkt_stats = show_kr.groupby("시장").agg(
            거래수=("순수익", "size"),
            승률=("순수익", lambda x: (x > 0).mean()),
            평균수익=("순수익", "mean"),
        ).reset_index()
        st.markdown(
            '<div style="color:#8B95A1;font-size:0.8125rem;margin-bottom:0.5rem;">시장별 분포</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            mkt_stats.style.format({"승률": "{:.1%}", "평균수익": "{:+.2%}"}),
            use_container_width=True, hide_index=True,
        )

    # 거래 내역 — 스크롤 없이 한번에 보이도록 동적 높이
    cols_order = ["종목명", "코드", "시장",
                   "진입일", "청산일", "보유일",
                   "진입가", "청산가",
                   "순수익", "손익(원)", "청산사유",
                   "랭크", "점수", "갭수익", "최고가수익"]
    cols_order = [c for c in cols_order if c in show_kr.columns]

    # 행당 약 35px + 헤더 40px, 최대 2000px로 제한
    row_h = 35
    header_h = 40
    dyn_height = min(header_h + row_h * len(show_kr), 2000)

    # 보기 모드: 전체 / 월별 분할
    view_mode = st.radio("보기 모드", ["전체 한번에", "월별로 나누기"],
                          horizontal=True, key="trade_view_mode")

    def _styled(df_in: pd.DataFrame, height: int):
        styler = df_in.style.format({
            "진입가": "{:,.0f}", "청산가": "{:,.0f}",
            "보유일": "{:.0f}일",
            "순수익": "{:+.2%}",
            "갭수익": "{:+.2%}", "최고가수익": "{:+.2%}",
        })
        pnl_cols = [c for c in ["순수익", "갭수익", "최고가수익"] if c in df_in.columns]
        for c in pnl_cols:
            styler = styler.applymap(_color_pnl_num, subset=[c])
        if "손익(원)" in df_in.columns:
            styler = styler.applymap(_color_won_str, subset=["손익(원)"])
        if "청산사유" in df_in.columns:
            styler = styler.applymap(_color_exit_str, subset=["청산사유"])
        return styler, height

    if view_mode == "전체 한번에":
        df_view = show_kr[cols_order].copy()
        styler, h = _styled(df_view, dyn_height)
        st.dataframe(styler, use_container_width=True, height=h, hide_index=True)
    else:
        # 월별 expander로 분할 (진입월 기준)
        show_kr["_월"] = pd.to_datetime(show_kr["진입일"]).dt.to_period("M").astype(str)
        months = sorted(show_kr["_월"].unique())

        # 월 요약 표 먼저
        summary_rows = []
        for mo in months:
            g = show_kr[show_kr["_월"] == mo]
            n = len(g)
            wins = (g["순수익"] > 0).sum()
            wr = wins / n if n else 0
            tot_won = (g["순수익"] * capital_won).sum()
            avg_ret = g["순수익"].mean()
            best = g["순수익"].max()
            worst = g["순수익"].min()
            summary_rows.append({
                "월": mo, "거래수": n, "승률": wr,
                "평균 수익": avg_ret, "최대 이익": best, "최대 손실": worst,
                "총 손익(원)": fmt_won_kr(tot_won),
            })
        summary_df = pd.DataFrame(summary_rows)

        st.markdown('<div style="color:#8B95A1;font-size:0.875rem;margin-bottom:0.5rem;">'
                     '월별 요약</div>', unsafe_allow_html=True)
        sum_styler = summary_df.style.format({
            "승률": "{:.1%}",
            "평균 수익": "{:+.2%}",
            "최대 이익": "{:+.2%}",
            "최대 손실": "{:+.2%}",
        })
        sum_styler = sum_styler.applymap(_color_pnl_num,
                                          subset=["평균 수익", "최대 이익", "최대 손실"])
        sum_styler = sum_styler.applymap(_color_won_str, subset=["총 손익(원)"])
        st.dataframe(sum_styler, use_container_width=True, hide_index=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

        # 각 월별 expander — 종목별 집계 (1종목 = 1행)
        for mo in months:
            g = show_kr[show_kr["_월"] == mo].copy()
            n = len(g)
            wins = (g["순수익"] > 0).sum()
            wr = wins / n if n else 0
            tot_won = (g["순수익"] * capital_won).sum()
            uniq_n = g["코드"].nunique()
            label = (f"📅 {mo} · 종목 {uniq_n}개 · 거래 {n}건 · "
                     f"승률 {wr*100:.0f}% · 손익 {fmt_won_kr(tot_won)}")

            with st.expander(label):
                # 진입일 오름차순 정렬 (매수일 기준 순서대로)
                g_sorted = g.sort_values(["진입일", "종목명"]).copy()
                # 의미 있는 컬럼만, 진입일을 앞으로
                day_cols = ["진입일", "청산일", "보유일", "종목명", "코드", "시장",
                              "진입가", "청산가", "순수익", "손익(원)", "청산사유"]
                day_cols = [c for c in day_cols if c in g_sorted.columns]
                day_view = g_sorted[day_cols]

                inner_h = min(40 + 35 * n, 1500)
                styler_in, _ = _styled(day_view, inner_h)
                st.dataframe(styler_in, use_container_width=True,
                              height=inner_h, hide_index=True)

    csv = show_kr.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 거래 내역 CSV 다운로드", csv, f"trades_{year}.csv", "text/csv",
                       use_container_width=True)


# ====================================================================
# 페이지 3: 워크포워드
# ====================================================================
def page_walkforward():
    hero(
        eyebrow="워크포워드 검증 · v1 vs v3",
        title="워크포워드 OOS 비교",
        lead="학습 1년 → 검증 3개월 슬라이딩. 16 윈도우 v1과 v3 결과 비교.",
    )

    # 시그널 버전 선택
    WF_FILES = {
        "🧪 v3.8 진짜 OOS (시점별 case_profile)": ("v38_wf_summary.json", "v38_wf_oos_trades.parquet"),
        "🏆 v3.7 (in-sample, 시총 5천억+ 시장필터)": ("v37_wf_summary.json", "v37_wf_oos_trades.parquet"),
        "⭐ v3 (in-sample, 사례 유사도)": ("v3_wf_summary.json", "v3_wf_oos_trades.parquet"),
        "v1 (기존 5대 조건)": ("wf_summary.json", "wf_oos_trades.parquet"),
    }
    wf_ver = st.selectbox(
        "보고싶은 결과", list(WF_FILES.keys()),
        index=0, key="wf_version",
    )
    sum_file, trades_file = WF_FILES[wf_ver]
    wf_summary = RESULTS / sum_file
    wf_trades = RESULTS / trades_file

    # 4개 비교 통합 표
    v1_path = RESULTS / "wf_summary.json"
    v3_path = RESULTS / "v3_wf_summary.json"
    v37_path = RESULTS / "v37_wf_summary.json"
    v38_path = RESULTS / "v38_wf_summary.json"

    rows = []
    for label, path in [("v1 (기존)", v1_path),
                         ("v3 (in-sample, 사례 학습)", v3_path),
                         ("🏆 v3.7 (in-sample, 5천억+ 시장)", v37_path),
                         ("🧪 v3.8 진짜 OOS (시점별 profile)", v38_path)]:
        if path.exists():
            with open(path) as f:
                m = json.load(f)["oos_metrics"]
            rows.append({
                "시그널": label,
                "OOS 거래": int(m.get("n", 0)),
                "승률": m.get("win_rate", 0),
                "기댓값": m.get("expectancy", 0),
                "PF": m.get("profit_factor", 0),
                "샤프": m.get("sharpe", 0),
                "MDD": m.get("mdd", 0),
                "누적": m.get("total_ret", 0),
            })
    if rows:
        section_title("📊 v1 vs v3 vs v3.7 OOS 비교")
        cmp_df = pd.DataFrame(rows)
        st.dataframe(
            cmp_df.style.format({
                "OOS 거래": "{:,}",
                "승률": "{:.1%}", "기댓값": "{:+.2%}",
                "PF": "{:.2f}", "샤프": "{:.2f}",
                "MDD": "{:.1%}", "누적": "{:+.1f}%",
            }).apply(lambda x: ["background-color: rgba(0,200,150,0.1); font-weight:700;"
                                  if "v3.8" in str(x.iloc[0]) else "" for _ in x],
                      axis=1),
            use_container_width=True, hide_index=True,
        )
        st.markdown(
            '<div style="background:rgba(49,130,246,0.06);border-left:4px solid #3182F6;'
            'padding:0.875rem 1.125rem;border-radius:8px;margin-top:0.5rem;font-size:0.875rem;line-height:1.5;">'
            '<b>해석</b>: v3.7 결과(샤프 3.08, 누적 +175,160%)는 '
            '<b style="color:#F04452;">in-sample look-ahead bias</b>가 포함된 값입니다 — '
            '사례 39개가 모두 2025년 이후라 2021-2024 시그널 정의에 미래 정보가 들어감.<br>'
            '<b>v3.8 진짜 OOS</b>는 각 윈도우 시작 시점보다 buy_date가 앞선 사례만으로 '
            'profile을 빌드 (마이닝 12,759 + 사용자 39 합본 사용). '
            '결과 <b>샤프 2.13, 누적 +628%</b> — v3.7 대비 크게 낮지만 이게 정직한 숫자.'
            '</div>',
            unsafe_allow_html=True,
        )

    if not wf_summary.exists():
        empty_state("⏳", "워크포워드 미완료",
                     "백테스트 파이프라인이 끝나면 자동 표시됩니다.")
        return

    with open(wf_summary) as f:
        summary = json.load(f)
    oos = summary["oos_metrics"]

    section_title("OOS 검증 성과")
    tone_ret = "success" if oos.get("expectancy", 0) > 0 else "danger"
    kpi_row([
        ("OOS 거래", f"{int(oos.get('n', 0)):,}", "검증 구간 누적", ""),
        ("승률", f"{oos.get('win_rate', 0)*100:.1f}%", "이익 비율",
         "success" if oos.get("win_rate", 0) > 0.55 else ""),
        ("기댓값", fmt_pct(oos.get("expectancy", 0)), "거래당", tone_ret),
        ("PF", f"{oos.get('profit_factor', 0):.2f}", "총이익/총손실", ""),
        ("샤프", f"{oos.get('sharpe', 0):.2f}", "연환산", ""),
        ("MDD", fmt_pct(oos.get("mdd", 0)), "최대 낙폭", "danger"),
    ])

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # OOS 곡선
    if wf_trades.exists():
        section_title("OOS 누적 수익")
        oos_df = pd.read_parquet(wf_trades)
        oos_df["entry_date"] = pd.to_datetime(oos_df["entry_date"])
        daily = oos_df.groupby("entry_date")["net"].mean()
        equity = (1 + daily).cumprod()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=equity.index, y=equity.values, mode="lines",
            line=dict(color=PALETTE["accent"], width=2),
            fill="tozeroy", fillcolor="rgba(49,130,246,0.06)",
        ))
        fig.add_hline(y=1.0, line_dash="dash", line_color=PALETTE["text_mute"])
        fig.update_layout(
            height=380, paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=20, r=20, t=10, b=20),
            font=dict(family="Pretendard"),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 윈도우 별
    section_title("윈도우별 결과", count=len(summary["windows"]))
    PARAM_KR = {
        "p_min_value": "최소거래대금",
        "p_volume_mult": "거래량배수",
        "p_high_window": "신고가일수",
        "p_close_to_high": "종가/고가",
        "p_daily_ret_min": "최소등락률",
        "p_daily_ret_max": "최대등락률",
        "p_require_score": "최소조건",
        "p_top_k_per_day": "일별K",
        "p_stop_loss": "손절",
        "p_cost_per_trade": "비용",
        "p_take_profit": "익절",
        "p_exit_at": "청산시점",
    }

    rows = []
    for w in summary["windows"]:
        # v3 형식: train, test, best_similarity, best_hold_days
        # v1 형식: train_metrics, test_metrics, best_params
        train_m = w.get("train_metrics") or w.get("train", {})
        test_m = w.get("test_metrics") or w.get("test", {})
        row = {
            "학습 구간": f"{w['train_start'][:6]}~{w['train_end'][:6]}",
            "검증 구간": f"{w['test_start'][:6]}~{w['test_end'][:6]}",
            "학습 PF": train_m.get("profit_factor", 0),
            "검증 거래수": test_m.get("n", 0),
            "검증 승률": test_m.get("win_rate", 0),
            "검증 기댓값": test_m.get("expectancy", 0),
            "검증 누적": test_m.get("total_ret", 0),
        }
        # v3 형식
        if "best_similarity" in w:
            row["유사도"] = w.get("best_similarity")
            row["보유일"] = w.get("best_hold_days")
        # v1 형식
        elif "best_params" in w:
            for k, v in w["best_params"].items():
                kr = PARAM_KR.get(f"p_{k}", k)
                if v is None:
                    row[kr] = "없음" if "stop" in k or "take" in k else "-"
                elif k == "stop_loss" and isinstance(v, (int, float)):
                    row[kr] = f"{v*100:+.0f}%"
                elif k == "min_value" and isinstance(v, (int, float)):
                    row[kr] = f"{v/1e8:.0f}억"
                else:
                    row[kr] = v
        rows.append(row)
    wf_df = pd.DataFrame(rows)

    # styler 없이 사전 문자열 변환 (None 안전)
    def _fmt(v, kind="num", decimals=2):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "-"
        if not isinstance(v, (int, float)):
            return str(v)
        if kind == "pct1":
            return f"{v*100:.1f}%"
        if kind == "pct2":
            return f"{v*100:+.2f}%"
        if kind == "num":
            return f"{v:.{decimals}f}"
        return str(v)

    display_df = wf_df.copy()
    fmt_map = {
        "학습 PF": ("num", 2),
        "검증 승률": ("pct1", 0),
        "검증 기댓값": ("pct2", 0),
        "검증 누적": ("pct2", 0),
        "종가/고가": ("num", 2),
        "최소등락률": ("num", 2),
        "최대등락률": ("num", 2),
    }
    for col, (kind, dec) in fmt_map.items():
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: _fmt(x, kind, dec))
    # 모든 컬럼 None을 "-"로
    for col in display_df.columns:
        display_df[col] = display_df[col].apply(lambda x: "-" if x is None else x)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # 파라미터 안정성
    section_title("파라미터 안정성")
    st.caption("윈도우마다 최적 파라미터가 일관되면 견고한 전략. 들쭉날쭉하면 과적합.")
    # PARAM_KR 매핑된 컬럼 + 숫자 컬럼만
    numeric_cols = [c for c in wf_df.columns
                     if c in PARAM_KR.values() and pd.api.types.is_numeric_dtype(wf_df[c])]
    if numeric_cols:
        param_summary = wf_df[numeric_cols].describe().T
        st.dataframe(param_summary.style.format("{:.3f}"), use_container_width=True)


# ====================================================================
# 페이지 4: 파라미터 시뮬레이터
# ====================================================================
def page_simulator():
    hero(
        eyebrow="가상 시나리오",
        title="파라미터 시뮬레이터",
        lead="임계치를 직접 조정하며 5년치 백테스트를 즉시 실행.",
    )

    universe = cached_universe()  # universe_final.txt 전체 (1057종목)
    if not universe:
        empty_state("⚠️", "유니버스 없음", "먼저 download_data.py 를 실행하세요.")
        return

    with st.form("sim_form"):
        st.caption("모든 입력 자유 커스텀. 하한 제약 없음. 손절 0% = 손절 없음.")

        section_title("기간 및 샘플")
        c1, c2, c3 = st.columns(3)
        start = c1.text_input("시작일 (YYYYMMDD)", "20210101")
        end = c2.text_input("종료일 (YYYYMMDD)", "20260517")
        sample_n = c3.number_input("샘플 종목 수 (랜덤)",
                                     value=200, step=10, min_value=1, format="%d")

        section_title("5대 조건 임계치")
        c1, c2, c3, c4 = st.columns(4)
        min_value_eok = c1.number_input("거래대금 (억)",
                                          value=500, step=50, format="%d", key="sim_v")
        volume_mult = c2.number_input("거래량 배수",
                                       value=3.0, step=0.5, format="%.2f", key="sim_vm")
        high_window = c3.number_input("신고가 윈도우 (일)",
                                       value=60, step=5, min_value=2, format="%d", key="sim_hw")
        close_to_high = c4.number_input("종가/고가 ≥",
                                         value=0.97, step=0.01, format="%.3f", key="sim_ch")

        c1, c2, c3, c4 = st.columns(4)
        ret_min = c1.number_input("최소 등락률 (%)",
                                    value=5.0, step=0.5, format="%.2f", key="sim_rmin")
        ret_max = c2.number_input("최대 등락률 (%)",
                                    value=25.0, step=1.0, format="%.2f", key="sim_rmax")
        require_score = c3.selectbox("최소 충족 조건 수",
                                      [1, 2, 3, 4, 5], index=4, key="sim_rs")
        top_k = c4.number_input("일별 매수 종목 수",
                                 value=5, step=1, min_value=1, format="%d", key="sim_k")

        section_title("청산 및 비용")
        c1, c2, c3, c4 = st.columns(4)
        stop_pct = c1.number_input("손절 (%, 0=없음)",
                                     value=-3.0, step=0.5, format="%.2f", key="sim_stop")
        stop_loss = (stop_pct / 100) if stop_pct < 0 else None
        cost = c2.number_input("거래 비용 (%)",
                                 value=0.3, step=0.1, format="%.2f", key="sim_cost") / 100
        exit_at_kr = c3.selectbox("청산 시점",
                                    ["익일 종가", "익일 시가", "익일 고가"], index=0, key="sim_exit")
        exit_at = {"익일 종가": "close", "익일 시가": "open", "익일 고가": "high"}[exit_at_kr]
        capital_man = c4.number_input("종목당 투입금 (만원)",
                                        value=100, step=10, min_value=10, max_value=100000,
                                        format="%d", key="sim_cap",
                                        help="10만원~10억원")

        submitted = st.form_submit_button("🚀 백테스트 실행", use_container_width=True)
    capital_won_sim = capital_man * 10000

    if not submitted:
        empty_state("🎛️", "파라미터를 조정하세요",
                     "위 폼에서 값을 변경하고 [백테스트 실행] 버튼을 누르세요.")
        return

    p = Params(
        min_value=min_value_eok * 1e8,
        volume_mult=volume_mult,
        high_window=int(high_window),
        close_to_high=close_to_high,
        daily_ret_min=ret_min / 100,
        daily_ret_max=ret_max / 100,
        require_score=int(require_score),
        top_k_per_day=int(top_k),
        stop_loss=stop_loss,    # None or float (e.g. -0.03)
        cost_per_trade=cost,
        exit_at=exit_at,
    )

    import random
    random.seed(42)
    sample = random.sample(universe, min(sample_n, len(universe)))
    with st.spinner(f"{len(sample)}종목 시그널 + 백테스트…"):
        raw = load_panel(tuple(sample), start, end)
        sig_data = {t: add_signals(df, p) for t, df in raw.items()}
        bd = cached_business_days(start, end)
        trades = backtest(sig_data, bd, p)
        m = metrics(trades)

    section_title("결과")
    tone_ret = "success" if m.get("total_ret", 0) > 0 else "danger"
    kpi_row([
        ("거래수", f"{m.get('n', 0):,}", "", ""),
        ("승률", f"{m.get('win_rate', 0)*100:.1f}%", "", ""),
        ("기댓값", fmt_pct(m.get("expectancy", 0)), "거래당", tone_ret),
        ("PF", f"{m.get('profit_factor', 0):.2f}", "", ""),
        ("샤프", f"{m.get('sharpe', 0):.2f}", "연환산", ""),
        ("누적", fmt_pct(m.get("total_ret", 0)), "전체 기간", tone_ret),
    ])

    if not trades.empty:
        # 원화 손익
        trades["profit_won"] = trades["net"] * capital_won_sim
        total_won = trades["profit_won"].sum()
        section_title("원화 손익 (종목당 " + fmt_won_kr(capital_won_sim) + " 가정)")
        kpi_row([
            ("총 손익", fmt_won_kr(total_won), f"{len(trades):,}건",
             "success" if total_won > 0 else "danger"),
            ("거래당 평균", fmt_won_kr(trades["profit_won"].mean()), "",
             "success" if total_won > 0 else "danger"),
            ("최대 1회 이익", fmt_won_kr(trades["profit_won"].max()), "", "success"),
            ("최대 1회 손실", fmt_won_kr(trades["profit_won"].min()), "", "danger"),
        ])

        trades["entry_date"] = pd.to_datetime(trades["entry_date"])
        daily = trades.groupby("entry_date")["net"].mean()
        equity = (1 + daily).cumprod()
        fig = go.Figure(go.Scatter(
            x=equity.index, y=equity.values, mode="lines",
            line=dict(color=PALETTE["accent"], width=2),
            fill="tozeroy", fillcolor="rgba(49,130,246,0.06)",
        ))
        fig.add_hline(y=1.0, line_dash="dash", line_color=PALETTE["text_mute"])
        fig.update_layout(
            height=380, paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=20, r=20, t=10, b=20),
            font=dict(family="Pretendard"),
        )
        st.plotly_chart(fig, use_container_width=True)


# ====================================================================
# 페이지 5: 사례 검증
# ====================================================================
def page_cases():
    hero(
        eyebrow="사례 검증 · v3 학습 분석",
        title="사례 39개 학습 분석",
        lead="사용자 제공 사례 39개의 매수일 시점 패턴 분석 + 9개 지표 통계. v3 시그널의 학습 기반.",
    )

    cases_csv = ROOT / "results" / "cases_analysis.csv"
    if cases_csv.exists():
        cases_df = pd.read_csv(cases_csv, dtype={"code": str})
        cases_df["code"] = cases_df["code"].str.zfill(6)

        section_title("사례 39개 통계 요약")
        kpi_row([
            ("사례 수", f"{len(cases_df)}", "분석 성공", ""),
            ("당일 등락률", f"{cases_df['ret_1d'].median()*100:+.1f}%", "중간값", "success"),
            ("20일 누적", f"{cases_df['ret_20d'].median()*100:+.1f}%", "추세 형성", "success"),
            ("RSI(14)", f"{cases_df['rsi_14'].median():.0f}", "과매수 영역", "warning"),
        ])

        section_title("9개 지표 — Q25 ~ Q75 핵심 영역")
        cols_meta = [
            ("ret_1d", "당일 등락률 %", 100),
            ("ret_5d", "5일 누적 %", 100),
            ("ret_20d", "20일 누적 %", 100),
            ("value_eok", "거래대금 (억)", 1),
            ("value_ratio_60d", "거래대금 60일 ×배수", 1),
            ("volume_ratio_60d", "거래량 60일 ×배수", 1),
            ("close_to_day_high", "종가/당일고가", 1),
            ("close_to_high60", "종가/60일 고가", 1),
            ("rsi_14", "RSI(14)", 1),
        ]
        stats = []
        for col, label, mult in cols_meta:
            vals = cases_df[col].dropna() * mult
            stats.append({
                "지표": label,
                "Q25": vals.quantile(0.25),
                "중간값": vals.median(),
                "Q75": vals.quantile(0.75),
                "최소": vals.min(),
                "최대": vals.max(),
            })
        st.dataframe(pd.DataFrame(stats).style.format({
            "Q25": "{:,.2f}", "중간값": "{:,.2f}", "Q75": "{:,.2f}",
            "최소": "{:,.2f}", "최대": "{:,.2f}",
        }), use_container_width=True, hide_index=True)

        section_title("이동평균 위치 (사례 100% 충족)")
        kpi_row([
            ("5일선 위", f"{cases_df['above_ma5'].sum()}/{len(cases_df)}",
             f"{cases_df['above_ma5'].mean()*100:.0f}%", "success"),
            ("20일선 위", f"{cases_df['above_ma20'].sum()}/{len(cases_df)}",
             f"{cases_df['above_ma20'].mean()*100:.0f}% ✅", "success"),
            ("60일선 위", f"{cases_df['above_ma60'].sum()}/{len(cases_df)}",
             f"{cases_df['above_ma60'].mean()*100:.0f}% ✅", "success"),
            ("종가/고가 ≥0.96", f"{(cases_df['close_to_day_high']>=0.96).sum()}/{len(cases_df)}",
             f"{(cases_df['close_to_day_high']>=0.96).mean()*100:.0f}%", "success"),
        ])

        section_title("미래 성과 (매수일 기준 최대 수익)")
        future_rows = []
        for n in [1, 5, 10, 20, 30, 60]:
            col = f"after_{n}d_max"
            if col in cases_df.columns:
                v = cases_df[col].dropna()
                if len(v):
                    future_rows.append({
                        "보유일": f"{n}일",
                        "평균 최대수익": v.mean(),
                        "중간값": v.median(),
                        "양수 비율": (v > 0).mean(),
                    })
        st.dataframe(pd.DataFrame(future_rows).style.format({
            "평균 최대수익": "{:+.2%}",
            "중간값": "{:+.2%}",
            "양수 비율": "{:.0%}",
        }), use_container_width=True, hide_index=True)

        section_title("사례 종목 리스트 (39개)")
        show_cases = cases_df[[
            "name", "code", "buy_date", "buy_close",
            "ret_1d", "ret_20d", "value_eok", "rsi_14",
            "after_1d_max", "after_30d_max",
        ]].rename(columns={
            "name": "종목명", "code": "코드",
            "buy_date": "매수일", "buy_close": "매수가",
            "ret_1d": "당일등락", "ret_20d": "20일누적",
            "value_eok": "거래대금(억)", "rsi_14": "RSI",
            "after_1d_max": "익일최대", "after_30d_max": "30일최대",
        })
        st.dataframe(show_cases.style.format({
            "매수가": "{:,.0f}",
            "당일등락": "{:+.2%}", "20일누적": "{:+.2%}",
            "거래대금(억)": "{:,.0f}", "RSI": "{:.1f}",
            "익일최대": "{:+.2%}", "30일최대": "{:+.2%}",
        }), use_container_width=True, hide_index=True)
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ---------- 기존 보고서 원본 사례 (4개) ----------
    section_title("보고서 원본 사례 — 외부 데이터 대조 (4개)")

    cases = [
        {"name": "LG CNS", "ticker": "064400", "date": "20260514",
         "claim": "신고가 대량거래 장대양봉 · +18.91%",
         "tag": "success", "verdict": "정합"},
        {"name": "현대차", "ticker": "005380", "date": "20260513",
         "claim": "52주 신고가 · +9.91% · 71만원",
         "tag": "warning", "verdict": "부분 정합"},
        {"name": "현대오토에버", "ticker": "307950", "date": "20260508",
         "claim": "상한가 +29.97% · 피지컬 AI",
         "tag": "success", "verdict": "정합"},
        {"name": "삼성전자", "ticker": "005930", "date": "20260506",
         "claim": "유리기판/반도체 대장 (외부데이터 불일치)",
         "tag": "danger", "verdict": "불일치"},
    ]

    section_title("사례")
    cards = []
    for c in cases:
        tag_cls = c["tag"]
        cards.append(f"""
        <div class="bento" style="margin-bottom:0.75rem;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <div class="label">{c['date'][:4]}-{c['date'][4:6]}-{c['date'][6:]}</div>
                    <h4 style="margin:0.25rem 0;">{c['name']}</h4>
                    <div style="color:#4E5968;font-size:0.875rem;">{c['claim']}</div>
                </div>
                <span class="tag {tag_cls}">{c['verdict']}</span>
            </div>
            <div class="code-snippet" style="margin-top:0.75rem;">ticker: {c['ticker']}</div>
        </div>
        """)
    st.markdown("\n".join(cards), unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    section_title("차트 보기")
    selected_name = st.selectbox("종목 선택", [c["name"] for c in cases])
    sel = next(c for c in cases if c["name"] == selected_name)
    date_str = sel["date"]

    end_dt = dt.datetime.strptime(date_str, "%Y%m%d")
    start_dt = end_dt - dt.timedelta(days=120)

    with st.spinner("차트 로딩…"):
        hist = get_ohlcv(sel["ticker"], start_dt.strftime("%Y%m%d"),
                         (end_dt + dt.timedelta(days=10)).strftime("%Y%m%d"))

    if hist.empty:
        empty_state("📭", "데이터 없음")
        return

    fig = go.Figure(go.Candlestick(
        x=hist.index, open=hist["open"], high=hist["high"],
        low=hist["low"], close=hist["close"],
        increasing=dict(line=dict(color=PALETTE["danger"]),
                        fillcolor=PALETTE["danger"]),
        decreasing=dict(line=dict(color=PALETTE["accent"]),
                        fillcolor=PALETTE["accent"]),
        name=sel["name"],
    ))
    target_dt = pd.to_datetime(date_str)
    if target_dt in hist.index:
        target_row = hist.loc[target_dt]
        fig.add_annotation(
            x=target_dt, y=target_row["high"],
            text=f"📍 {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
            showarrow=True, arrowhead=2, arrowcolor=PALETTE["accent"],
            font=dict(color=PALETTE["accent"], size=12),
        )
    fig.update_layout(
        height=500, paper_bgcolor="white", plot_bgcolor="white",
        xaxis=dict(rangeslider=dict(visible=False), gridcolor=PALETTE["border_soft"]),
        yaxis=dict(gridcolor=PALETTE["border_soft"]),
        margin=dict(l=20, r=20, t=20, b=20),
        font=dict(family="Pretendard"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 거래량
    fig_v = go.Figure(go.Bar(
        x=hist.index, y=hist["volume"],
        marker=dict(color=PALETTE["text_mute"]),
    ))
    fig_v.update_layout(
        height=180, paper_bgcolor="white", plot_bgcolor="white",
        xaxis=dict(gridcolor=PALETTE["border_soft"]),
        yaxis=dict(title="거래량", gridcolor=PALETTE["border_soft"]),
        margin=dict(l=20, r=20, t=10, b=20),
        font=dict(family="Pretendard"),
    )
    st.plotly_chart(fig_v, use_container_width=True)


# ====================================================================
# 페이지 6: 전략 가이드
# ====================================================================
def page_guide():
    hero(
        eyebrow="전략 가이드 · 쉬운 비교",
        title="어떤 전략을 써야 하나?",
        lead="3가지 전략을 한눈에 비교. 가장 우수한 v3.7 (대형주) 권장.",
    )

    # ===== 한눈에 비교 =====
    st.markdown("""
## 🥇 추천 순위 — 5년 백테스트 검증

| 순위 | 전략 | 종목 풀 | 일평균 신호 | 샤프 | 거래당 평균 | 승률 |
|---|---|---|---|---|---|---|
| 🥇 | **v3.7 (5천억+)** ★ 추천 | 565개 | 2.5건 | **2.48** | **+3.94%** | 47.2% |
| 🥈 | v3.7 대형주 (1조+) | 366개 | 2.2건 | 2.89 | +4.75% | 47.9% |
| 🥉 | v3.1 시장필터 (전체) | 1,534개 | 2.7건 | 1.47 | +2.40% | 43.1% |
| ❌ | v1 옛 60일신고가 | 전체 | - | 0.40 OOS | +0.17% | 43.4% |

**왜 5천억+가 추천?**
- 1조+ 와 샤프 차이 작음 (2.48 vs 2.89)
- 종목 풀 565개로 더 다양 (1조+는 366개)
- 일평균 신호 2.5건 > 2.2건 — 매수 기회 더 많음

---

## 🎯 v3.7 — 가장 쉽게 따라하기

```
📌 대상 종목: 시가총액 5천억원 이상 (565개)
📌 시장 조건: KOSPI 20일선 위 (장중에 확인)
📌 매수 신호: 사례 유사도 ≥ 0.6 (9개 지표 중 60% 충족)
📌 보유 기간: 30일 (장기 60~90일 더 우수)
📌 손절: -3%
📌 매수 개수: 일별 1~3종목
```

---
""")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.success("⭐ **v3 (사례 유사도) — 권장 전략**\n\n"
                "사용자 제공 39개 성공 사례를 학습. 9개 지표(당일/5일/20일 등락률, 거래대금, 거래대금 60일 배수, "
                "거래량 60일 배수, 종가/고가, 종가/60일 고가, RSI)의 Q25~Q75 핵심 영역에 들어가는 종목만 매수. "
                "**30일 보유**가 최적 (1일 청산은 -0.18% 손실, 30일 청산은 +1.70% 평균 수익).")

    section_title("v3 검증 결과 (1057종목 × 5년)")
    st.markdown("""
| 보유일 | 거래수 | 승률 | 거래당 평균 | PF | 샤프 |
|---|---|---|---|---|---|
| 1일 | 6,355 | 34.0% | -0.18% | 0.90 | -0.56 |
| 5일 | 6,335 | 44.3% | +0.36% | 1.10 | 0.51 |
| 10일 | 6,320 | 44.3% | +0.77% | 1.16 | 0.79 |
| 20일 | 6,295 | 42.7% | +1.02% | 1.16 | 0.79 |
| **30일** | **6,260** | **41.3%** | **+1.70%** | **1.23** | **1.02** |
| 60일 | 6,153 | 40.7% | +3.25% | 1.34 | 1.38 |
| **90일** | **6,073** | **41.2%** | **+4.19%** | **1.38** | **1.51** |
""")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    section_title("v3 9대 지표 (사례 39개 통계)")
    conditions = [
        ("01", "당일 등락률 +13~21%", "강한 상승", "사례 평균 +17%, Q25~Q75 영역"),
        ("02", "20일 누적 +19~41%", "추세 종목", "이미 상승 중인 종목 — 사례 100%"),
        ("03", "거래대금 341~2,549억", "자금 집중", "시총 상위 + 거래 집중"),
        ("04", "거래대금 60일 ×6~19", "자금 폭증", "평소 대비 6배 이상 거래대금"),
        ("05", "거래량 60일 ×5~17", "거래량 급등", "평균 대비 5배 이상"),
        ("06", "종가/고가 ≥0.96", "막판 매수세", "당일 고가의 96% 이상에서 마감"),
        ("07", "종가 > 20일선", "단기 추세", "사례 100% 충족"),
        ("08", "종가 > 60일선", "중기 추세", "사례 100% 충족 — 필수"),
        ("09", "RSI(14) 68~82", "모멘텀", "과매수 영역 (추세 강함)"),
    ]
    cards = []
    for num, name, why, how in conditions:
        cards.append(f"""
        <div class="bento" style="margin-bottom:0.75rem;display:grid;grid-template-columns:60px 1fr;gap:1rem;align-items:center;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:1.5rem;font-weight:800;color:#3182F6;">{num}</div>
            <div>
                <div style="font-weight:700;font-size:1.0625rem;">{name}</div>
                <div style="color:#8B95A1;font-size:0.8125rem;margin-top:0.125rem;">{why}</div>
                <div style="color:#4E5968;font-size:0.9375rem;margin-top:0.5rem;">{how}</div>
            </div>
        </div>
        """)
    st.markdown("\n".join(cards), unsafe_allow_html=True)

    section_title("v3 운영 가이드")
    tactic_cols = st.columns(3)
    tactics = [
        ("느슨한 후보 추출", "조건 0.6 기준 일 15~20건 — 1차 후보"),
        ("빡빡한 매수 선별", "조건 0.8 기준 일 2건 — 사례와 거의 동일"),
        ("30일 보유 + 분할 익절", "TP1 +20%/50% 청산 → TP2 +40%/잔량"),
    ]
    for col, (title, desc) in zip(tactic_cols, tactics):
        col.markdown(
            f'<div class="bento" style="height:100%;"><h4>{title}</h4>'
            f'<div style="color:#4E5968;font-size:0.9375rem;">{desc}</div></div>',
            unsafe_allow_html=True,
        )

    section_title("리스크 관리")
    risk_cards = [
        ("권장 보유", "30일 (사례 학습 기반)"),
        ("손절", "−3% (필수)"),
        ("시장 환경", "KOSPI 20일선 위에서만"),
        ("종목당 투입", "자본 5~10% 분산"),
    ]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, risk_cards):
        with col:
            bento(label, value)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    section_title("⭐ v3.7 대형주 전략 — 최강 조합")
    st.success(
        "**대형주(시총 1조+) + KOSPI 20일선 위 + v3 유사도 ≥0.6 + 30일 보유 + 손절 -3%**\n\n"
        "✨ **5년 백테스트 결과**: 승률 **47.9%**, 거래당 평균 **+4.75%**, "
        "PF **1.84**, **샤프 2.89** (매우 우수)\n\n"
        "📂 상세 가이드: `04_검증_분석/07_키움_조건검색식_v3.7_대형주.md`"
    )

    st.markdown("""
**시총 구간별 5년 검증 결과** (v3.1 시장필터 + 30일 보유):

| 그룹 | 거래수 | 승률 | 평균 | 샤프 |
|---|---|---|---|---|
| 🏆 **대형 (1조+)** | 2,809 | **47.9%** | **+4.75%** | **2.89** |
| 중대형 (5천억~1조) | 1,746 | 43.3% | +2.01% | 1.35 |
| 중형 (1천억~5천억) | 3,350 | 38.0% | +0.19% | 0.11 |

→ **대형주가 압도적**. 중소형주는 v3 시그널로 무수익.
""")

    section_title("키움증권 영웅문 조건검색식")
    st.info("💡 영웅문 조건검색에 입력할 수 있는 v3 조건검색식 가이드: "
             "[04_검증_분석/06_키움_조건검색식_v3.md](04_검증_분석/06_키움_조건검색식_v3.md)\n\n"
             "**0.6 (느슨, 일 15~20건)**: 등락률 7~25%, 거래대금 ≥100억, 거래량 ×3, 종가/고가 ≥0.94, "
             "20일선·60일선 위, RSI ≥60, 20일 누적 ≥10%\n\n"
             "**0.8 (빡빡, 일 2건)**: 등락률 13~22%, 거래대금 340~2500억, 거래량 ×5, 종가/고가 ≥0.96, "
             "20일선·60일선 위, RSI 68~82, 20일 누적 19~41%\n\n"
             "**v3.7 (대형주 한정, 샤프 2.89)**: 위 조건 + 시총 1조+ + KOSPI 20일선 위")


# ====================================================================
# 페이지 7: 테마/대장주 분석
# ====================================================================
def page_themes():
    hero(
        eyebrow="테마 레이더",
        title="시장 주도 테마 & 대장주",
        lead="네이버 금융 테마 데이터. 계산 방식 3가지(대장주 평균/시총 가중/단순)를 토글해 비교할 수 있습니다.",
    )

    # 기준일 안내
    basis = scraper.fetch_basis_info()
    st.markdown(
        f'<div style="display:flex;gap:1rem;align-items:center;margin-bottom:1rem;'
        f'padding:0.75rem 1rem;background:rgba(49,130,246,0.08);border-radius:8px;'
        f'border:1px solid rgba(49,130,246,0.2);flex-wrap:wrap;">'
        f'<span style="font-weight:700;color:#3182F6;">{basis["market_status"]}</span>'
        f'<span style="color:#4E5968;font-size:0.875rem;">데이터 기준일: '
        f'<b style="color:#191F28;">{basis["ref_date"]} ({basis["weekday"]})</b> · '
        f'현재 {basis["now"]}</span>'
        f'<span style="color:#8B95A1;font-size:0.75rem;">'
        f'※ 정규장 종료(16시) 후엔 종가 확정값. 시간외 단일가는 미반영.</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    sc_l, sc_r = st.columns([2, 1])
    src_mode = sc_l.radio(
        "테마 등락률 계산 방식",
        ["🏆 대장주 5개 평균 (FINUP 스타일)",
         "⚖️ 시총 가중 평균",
         "🟰 단순 평균 (네이버 기본)"],
        index=0, horizontal=True, key="theme_src_mode",
        help=(
            "**대장주 5개 평균**: 테마 내 시총 상위 5종목만 등가중. "
            "잡주 영향을 줄여 시장 체감과 가장 가까움 (FINUP 트리맵 방식).\n\n"
            "**시총 가중**: 모든 종목을 시총 비례로 가중. 대형주 영향이 큼.\n\n"
            "**단순 평균**: 네이버 mobile API 기본값. 잡주가 평균을 끌어내림."
        ),
    )
    refresh = sc_r.button("🔄 새로고침", use_container_width=True)
    if refresh:
        scraper._CACHE.clear()
        st.rerun()

    with st.spinner("네이버 금융 테마 시세 로딩…"):
        if src_mode.startswith("🏆"):
            themes_all = scraper.fetch_themes_weighted(
                limit=100, method="leaders", leader_n=5, enrich_top=50)
            calc_label = "대장주 5개 평균"
        elif src_mode.startswith("⚖️"):
            themes_all = scraper.fetch_themes_weighted(
                limit=100, method="mcap", enrich_top=50)
            calc_label = "시총 가중 평균"
        else:
            themes_all = scraper.fetch_top_themes(limit=100)
            calc_label = "단순 평균"

    if not themes_all:
        empty_state("📭", "테마 데이터 없음",
                     "네트워크 또는 네이버 API 오류. [🔄 새로고침] 또는 잠시 후 재시도.")
        return

    # 정렬 기준 + 검색
    sc1, sc2 = st.columns([1, 2])
    sort_mode = sc1.selectbox(
        "정렬 기준",
        ["등락률 순 (디폴트)", "강도 순 (등락률×상승비율)",
         "상승 종목수 순", "테마 종목수 순"],
        index=0, key="theme_sort",
    )
    search_q = sc2.text_input("🔎 테마 검색 (예: 화장품, 통신, 반도체, AI)",
                                 value="", key="theme_search",
                                 placeholder="검색어 입력 시 필터")

    themes = list(themes_all)
    if search_q.strip():
        themes = [t for t in themes if search_q.strip() in t.name]
        st.caption(f"🔎 '{search_q}' 검색 결과: {len(themes)}개 테마")
        if not themes:
            empty_state("🔍", "검색 결과 없음", "다른 검색어로 시도하세요.")
            return

    # 강도 점수 계산: 평균 등락률 × 상승 비율
    for t in themes:
        rise_ratio = t.rise_count / max(t.total_count, 1)
        t.strength = t.change_pct * rise_ratio
        t.rise_ratio = rise_ratio

    # 정렬
    if sort_mode.startswith("등락률"):
        themes.sort(key=lambda x: x.change_pct, reverse=True)
    elif sort_mode.startswith("강도"):
        themes.sort(key=lambda x: x.strength, reverse=True)
    elif sort_mode.startswith("상승 종목수"):
        themes.sort(key=lambda x: x.rise_count, reverse=True)
    else:
        themes.sort(key=lambda x: x.total_count, reverse=True)

    up = [t for t in themes_all if t.change_pct > 0]
    down = [t for t in themes_all if t.change_pct <= 0]

    # 시장 폭 (전체 테마 중 상승 비율)
    market_breadth = len(up) / max(len(themes_all), 1)
    breadth_label = (
        "🔥 강세장" if market_breadth >= 0.6 else
        "📈 우호적" if market_breadth >= 0.4 else
        "⚠️ 약세장" if market_breadth >= 0.2 else "🔻 폭락장"
    )

    # 요약 KPI
    section_title("시장 환경 요약")
    kpi_row([
        ("시장 폭", f"{market_breadth*100:.0f}%",
         f"전체 {len(themes_all)}개 중 상승 {len(up)}개",
         "success" if market_breadth >= 0.5 else "danger"),
        ("시장 분위기", breadth_label,
         f"평균 {sum(t.change_pct for t in themes_all)/max(len(themes_all),1):+.2f}%",
         "success" if market_breadth >= 0.5 else "warning"),
        ("최강 테마", up[0].name[:14] if up else "없음",
         f"{up[0].change_pct:+.2f}%" if up else "-", "success" if up else "danger"),
        ("최약 테마", down[-1].name[:14] if down else "없음",
         f"{down[-1].change_pct:+.2f}%" if down else "-", "danger" if down else ""),
    ])

    # 정렬된 테마 리스트 표시
    section_title(f"📊 테마 리스트 · {calc_label} ({sort_mode})", count=len(themes))

    TOP_EXPAND = 10
    expand_themes = themes[:TOP_EXPAND]

    if expand_themes and len(expand_themes) > 0:
        # 정렬된 테마 중 상위 10개는 expander로 1·2·3등주 표시
        for i, t in enumerate(expand_themes):
            sign = "+" if t.change_pct >= 0 else ""
            label = (f"🔥 {i+1:02d}  {t.name}  ·  {sign}{t.change_pct:.2f}%  "
                     f"·  ↑{t.rise_count} / ↓{t.fall_count}  ·  대표: {t.top_name or '—'}")
            with st.expander(label, expanded=(i < 3)):
                try:
                    stocks = scraper.fetch_theme_stocks(t.no, limit=10)
                except Exception:
                    stocks = []
                if not stocks:
                    st.caption("종목 데이터 없음")
                    continue
                # 거래대금 × 등락률로 점수 매겨서 1·2·3등 선정
                ranked = sorted(stocks,
                                 key=lambda s: s.value * max(s.change_pct, 0.01),
                                 reverse=True)[:3]
                cards_html = []
                for idx, s in enumerate(ranked):
                    if idx == 0:
                        badge = '<span class="tag accent">🏆 대장주</span>'
                    elif idx == 1:
                        badge = '<span class="tag warning">🥈 2등주</span>'
                    else:
                        badge = '<span class="tag" style="background:rgba(255,159,46,0.08);color:#FF9F2E;">🥉 3등주</span>'
                    cards_html.append(stock_card_html(
                        rank=idx + 1, name=s.name, ticker=s.code,
                        score=0, close=s.price, ret_pct=s.change_pct,
                        value_eok=s.value / 100,   # 백만원 → 억
                        vol_ratio=0, close_to_high=0,
                        is_new_high=False,
                        themes=[f"##BADGE:{badge}", t.name],
                        news=[],
                    ))
                st.markdown("\n".join(cards_html), unsafe_allow_html=True)
                # 더보기: 나머지 종목 모두
                if len(stocks) > 3:
                    with st.expander(f"전체 {len(stocks)}개 종목 모두 보기"):
                        all_html = []
                        for idx, s in enumerate(sorted(stocks, key=lambda x: x.change_pct, reverse=True)):
                            all_html.append(stock_card_html(
                                rank=idx + 1, name=s.name, ticker=s.code,
                                score=0, close=s.price, ret_pct=s.change_pct,
                                value_eok=s.value / 100,
                                vol_ratio=0, close_to_high=0,
                                is_new_high=False, themes=[t.name], news=[],
                            ))
                        st.markdown("\n".join(all_html), unsafe_allow_html=True)

        # 나머지 테마는 카드만 (검색/정렬 적용된 결과의 나머지)
        if len(themes) > TOP_EXPAND:
            with st.expander(f"📋 그 외 테마 보기 ({len(themes) - TOP_EXPAND}개)"):
                cards = []
                for i, t in enumerate(themes[TOP_EXPAND:], start=TOP_EXPAND):
                    cards.append(theme_card_html(
                        rank=i + 1, name=t.name, change_pct=t.change_pct,
                        top_name=t.top_name, theme_url=t.url,
                        rise_count=t.rise_count, fall_count=t.fall_count,
                        total_count=t.total_count,
                        strength=getattr(t, "strength", None),
                    ))
                st.markdown("\n".join(cards), unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 테마 선택 → 종목 + 뉴스
    section_title("테마 내 종목 분석")
    theme_names = [t.name for t in themes]
    selected = st.selectbox("테마 선택", theme_names, index=0)
    sel_theme = next(t for t in themes if t.name == selected)

    with st.spinner(f"'{selected}' 테마 종목 로딩…"):
        stocks = scraper.fetch_theme_stocks(sel_theme.no, limit=30)

    if not stocks:
        empty_state("📭", "종목 정보 없음")
        return

    # 대장주 식별: 등락률 1위
    stocks_sorted = sorted(stocks, key=lambda s: s.change_pct, reverse=True)
    leader = stocks_sorted[0]

    # KPI
    section_title(f"{selected} · 평균 {sel_theme.change_pct:+.2f}%")
    kpi_row([
        ("종목 수", f"{len(stocks)}", "테마 내", ""),
        ("대장주", leader.name, f"+{leader.change_pct:.2f}%", "success"),
        ("상승 종목", f"{sum(1 for s in stocks if s.change_pct > 0)}",
         f"전체 {len(stocks)}개 중", ""),
        ("최고가", f"{max(s.change_pct for s in stocks):+.2f}%", "등락률 1위", "success"),
    ])

    # 종목 카드
    section_title("종목 리스트")
    fetch_news = st.checkbox("📰 종목별 최신 뉴스 함께 보기", value=False)
    cards = []
    for i, s in enumerate(stocks_sorted):
        news = []
        if fetch_news:
            try:
                news_objs = scraper.fetch_stock_news(s.code, limit=2)
                news = [{"title": n.title, "source": n.source, "url": n.url}
                         for n in news_objs]
            except Exception:
                pass
        is_new_high = False  # 테마 페이지에선 신고가 확인 안 함 (성능)
        cards.append(stock_card_html(
            rank=i + 1,
            name=s.name,
            ticker=s.code,
            score=0,                # 점수 없음 (테마 뷰)
            close=s.price,
            ret_pct=s.change_pct,
            value_eok=s.value / 100,   # 백만원 → 억원
            vol_ratio=0,
            close_to_high=0,
            is_new_high=is_new_high,
            themes=[selected],
            news=news,
        ))
    st.markdown("\n".join(cards), unsafe_allow_html=True)


# ====================================================================
# 페이지: 추천 히스토리 (일자별 v3 시그널)
# ====================================================================
@st.cache_data(show_spinner="📅 시그널 사전 계산 중 (2~4분, 1회만)…")
def precompute_v3_signals(universe_tuple: tuple[str, ...],
                            sim_threshold: float = 0.6,
                            market_filter: bool = True,
                            profile_mode: str = "combined") -> pd.DataFrame:
    """전 기간(2021~2026) v3 시그널 + 익일/10/30/60/90/120일 미래 수익률.

    profile_mode:
        - 'user39': 사용자 큐레이션 39개만 (기존, 2025~ 편향)
        - 'combined': 사용자 39 + 마이닝 12,759 합본 (전 기간 평균)
        - 'oos_yearly': 시그널 일자보다 이전 사례만으로 profile 빌드 (진짜 OOS)
    """
    p = ParamsV3(min_similarity=sim_threshold)

    if market_filter:
        kospi = get_index_ohlcv("KS11", "20200101", "20260517")
        kospi["ma20"] = kospi["close"].rolling(20).mean()
        kospi["above"] = kospi["close"] > kospi["ma20"]
        market_above = kospi["above"]
    else:
        market_above = None

    # 프로파일 준비
    if profile_mode == "user39":
        profile_by_year = {y: build_profile(combined=False) for y in range(2021, 2027)}
    elif profile_mode == "combined":
        profile_by_year = {y: build_profile(combined=True) for y in range(2021, 2027)}
    else:                  # 'oos_yearly' — 각 연도 시작 시점 이전 사례만
        profile_by_year = {}
        for y in range(2021, 2027):
            try:
                profile_by_year[y] = build_profile(
                    combined=True, asof_date=f"{y}-01-01")
            except Exception:
                profile_by_year[y] = None
            # 진짜 OOS인데 사례 너무 적으면 skip
            if profile_by_year[y] is not None:
                n = case_count(combined=True, asof_date=f"{y}-01-01")
                if n < 50:                        # 50건 미만이면 신뢰 어려움
                    profile_by_year[y] = None

    rows = []
    for ticker in universe_tuple:
        try:
            df = get_ohlcv(ticker, "20200601", "20260517")
            if df.empty or len(df) < 80:
                continue

            # 연도별로 시그널 따로 계산 (OOS 모드일 때 profile이 다르므로)
            triggered_dfs = []
            for y in range(2021, 2027):
                prof = profile_by_year.get(y)
                if prof is None:
                    continue
                sig_y = add_signals_v3(df, prof, p)
                if market_above is not None:
                    above = market_above.reindex(sig_y.index, method="ffill").fillna(False)
                    sig_y = sig_y.copy()
                    sig_y["signal"] = sig_y["signal"] & above
                mask = (sig_y["signal"]
                         & (sig_y.index >= f"{y}-01-01")
                         & (sig_y.index < f"{y+1}-01-01"))
                triggered_dfs.append(sig_y[mask])

            if not triggered_dfs:
                continue
            triggered = pd.concat(triggered_dfs)

            # 미래 가격 — 일별 인덱스 (df 활용)
            for date_ts, row in triggered.iterrows():
                entry_price = float(row["close"])
                # 익일, 10, 30, 60, 90 영업일 후
                future_returns = {}
                pos = df.index.get_loc(date_ts)
                for n_label, n_days in [("ret_d1", 1), ("ret_d10", 10),
                                         ("ret_d30", 30), ("ret_d60", 60),
                                         ("ret_d90", 90), ("ret_d120", 120)]:
                    if pos + n_days < len(df):
                        fut_close = float(df.iloc[pos + n_days]["close"])
                        future_returns[n_label] = (fut_close - entry_price) / entry_price
                    else:
                        future_returns[n_label] = None

                rows.append({
                    "date": date_ts.strftime("%Y-%m-%d"),
                    "year": date_ts.year,
                    "month": date_ts.month,
                    "ticker": ticker,
                    "name": get_name(ticker),
                    "similarity": float(row["similarity"]),
                    "close": int(entry_price),
                    "ret_1d": float(row.get("ret_1d", 0)),
                    "ret_20d": float(row.get("ret_20d", 0)),
                    "value_eok": float(row.get("value", 0)) / 1e8,
                    "vol_ratio": float(row.get("volume_ratio_60d", 0)),
                    "rsi": float(row.get("rsi_14", 0)),
                    "close_to_high": float(row.get("close_to_day_high", 0)),
                    **future_returns,
                })
        except Exception:
            continue
    return pd.DataFrame(rows)


def page_history():
    hero(
        eyebrow="추천 히스토리",
        title="📅 월별 v3 추천 종목 리스트",
        lead="연·월을 토글 버튼으로 선택 후 [조회]를 누르면 그때 데이터 조회.",
    )

    # ⚠️ 정직한 경고: 사례 39개가 모두 2025-01-02~2026-02-04 사이라
    #    그 이전 시그널은 미래 정보로 만든 사례 profile이 들어가 있음 = IN-SAMPLE.
    st.markdown(
        '<div style="background:rgba(240,68,82,0.08);border-left:4px solid #F04452;'
        'padding:0.875rem 1.125rem;border-radius:8px;margin-bottom:1rem;">'
        '<div style="font-weight:800;color:#F04452;margin-bottom:0.25rem;">⚠️ '
        '검증 신뢰도 주의 — 사례 profile에 look-ahead bias 있음</div>'
        '<div style="color:#4E5968;font-size:0.875rem;line-height:1.5;">'
        '사례 39개가 모두 <b>2025-01-02 ~ 2026-02-04</b> 사이에 매수된 종목으로 만들어졌습니다. '
        '이 profile을 그 이전 시점(2021~2024)에 적용하면 <b>미래 정보가 과거 신호에 새는 in-sample 평가</b>가 됩니다. '
        '진짜 OOS(out-of-sample)를 보려면 아래 토글을 <b>ON</b>으로 두고 <b>2026-02-05 이후</b> 결과만 보세요.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    oos_only = st.toggle(
        "✅ OOS only — 사례 profile 마지막 시점(2026-02-04) 이후 시그널만 표시",
        value=False, key="hist_oos_only",
        help="ON: 진짜 OOS (사례 데이터에 포함되지 않는 시점). "
             "OFF: 전체 (2021~2026). 단 profile_mode='user39'면 2025년 이전은 in-sample.",
    )

    # 사례 profile 모드 선택
    PROFILE_MODES = {
        "🎯 합본 (사용자 39 + 마이닝 12,759) — 전 기간 평균": "combined",
        "🧪 진짜 OOS — 시그널 일자 이전 사례만 (연도별)": "oos_yearly",
        "📌 사용자 큐레이션 39개만 (구버전, 2025~ 편향)": "user39",
    }
    profile_label = st.selectbox(
        "사례 profile 모드", list(PROFILE_MODES.keys()),
        index=0, key="hist_profile_mode",
        help=(
            "합본: 2021~2024년 데이터로 12,759개 winner 마이닝 → 큰 표본, 편향 줄임. "
            "OOS: 각 시그널 일자보다 이전 사례만 사용 → 진짜 walk-forward 검증. "
            "user39: 기존 버전 호환."
        ),
    )
    profile_mode = PROFILE_MODES[profile_label]

    # 현재 모드의 사례 개수 표시
    if profile_mode == "combined":
        nc = case_count(combined=True)
    elif profile_mode == "user39":
        nc = case_count(combined=False)
    else:
        nc = case_count(combined=True, asof_date="2024-01-01")   # 2024 시점 기준 예시
    st.caption(f"📊 현 모드 사례 수: {nc:,}개 "
                + ("(연도별 변동)" if profile_mode == "oos_yearly" else ""))

    # session_state 초기화
    if "hist_sel_years" not in st.session_state:
        st.session_state.hist_sel_years = {2026}
    if "hist_sel_months" not in st.session_state:
        st.session_state.hist_sel_months = {3, 4, 5}

    # ===== 1) 프리셋 =====
    PRESETS_HIST = {
        "⭐ v3.7 (5천억+ + 시장필터, 추천)": (5e11, True, 2.48),
        "🏆 v3.7 대형주 (1조+ + 시장필터)": (1e12, True, 2.89),
        "📊 v3.1 (전체 + 시장필터)": (0, True, 1.47),
        "🌐 v3.0 (전체, 시장필터 X)": (0, False, 1.02),
    }
    pc1, pc2 = st.columns([2, 1])
    hist_preset = pc1.selectbox("🎯 프리셋", list(PRESETS_HIST.keys()),
                                  index=0, key="hist_preset")
    cap_cutoff, market_filter_on, hist_sharpe = PRESETS_HIST[hist_preset]
    sim_threshold = pc2.slider("유사도", 0.3, 0.9, 0.6, 0.05, key="hist_sim")
    color = "#00C896" if hist_sharpe >= 1.5 else ("#FF9F2E" if hist_sharpe >= 1.0 else "#F04452")
    st.markdown(
        f'<div style="display:flex;gap:1rem;padding:0.625rem 1rem;'
        f'background:rgba(49,130,246,0.06);border-left:4px solid {color};'
        f'border-radius:8px;margin-bottom:0.75rem;font-size:0.875rem;">'
        f'<div><b>샤프 {hist_sharpe:.2f}</b></div>'
        f'<div style="color:#4E5968;">{ "시장필터 ON" if market_filter_on else "시장필터 OFF" }</div>'
        f'<div style="color:#4E5968;">데이터: 2021~2026 전체</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ===== 2) 연도 토글 =====
    st.markdown("##### 📅 연도")
    years = [2021, 2022, 2023, 2024, 2025, 2026]
    ycols = st.columns(len(years))
    for col, y in zip(ycols, years):
        is_on = y in st.session_state.hist_sel_years
        if col.button(str(y), key=f"hist_y_{y}",
                       type="primary" if is_on else "secondary",
                       use_container_width=True):
            (st.session_state.hist_sel_years.discard(y) if is_on
             else st.session_state.hist_sel_years.add(y))
            st.rerun()

    # ===== 3) 월 토글 (6개씩 2줄) =====
    st.markdown("##### 📅 월")
    for row_start in [1, 7]:
        cols = st.columns(6)
        for col, m in zip(cols, range(row_start, row_start + 6)):
            is_on = m in st.session_state.hist_sel_months
            if col.button(f"{m}월", key=f"hist_m_{m}",
                           type="primary" if is_on else "secondary",
                           use_container_width=True):
                (st.session_state.hist_sel_months.discard(m) if is_on
                 else st.session_state.hist_sel_months.add(m))
                st.rerun()

    # 빠른 선택 헬퍼
    qc1, qc2, qc3, qc4, qc5 = st.columns(5)
    if qc1.button("전체", use_container_width=True, key="hist_all_m"):
        st.session_state.hist_sel_months = set(range(1, 13)); st.rerun()
    if qc2.button("1Q", use_container_width=True, key="hist_q1"):
        st.session_state.hist_sel_months = {1, 2, 3}; st.rerun()
    if qc3.button("2Q", use_container_width=True, key="hist_q2"):
        st.session_state.hist_sel_months = {4, 5, 6}; st.rerun()
    if qc4.button("최근 3개월", use_container_width=True, key="hist_recent"):
        from datetime import date
        m = date.today().month
        st.session_state.hist_sel_months = {((m - i - 1) % 12) + 1 for i in range(3)}
        st.rerun()
    if qc5.button("해제", use_container_width=True, key="hist_clr_m"):
        st.session_state.hist_sel_months = set(); st.rerun()

    # ===== 4) 추천 설정 (종목 수 + 매수금) =====
    st.markdown("##### ⚙️ 추천 설정")
    tc1, tc2 = st.columns(2)
    daily_topk = tc1.slider("일별 추천 종목 수", 1, 10, 3,
                              key="hist_daily_topk",
                              help="각 영업일 유사도 상위 N개. 1=대장주만, 3=1·2·3순위")
    buy_man = tc2.number_input("종목당 매수금 (만원)",
                                 value=100, step=10, min_value=10, max_value=100000,
                                 format="%d", key="hist_buy_amt",
                                 help="10만원 ~ 10억원. 손익금 계산용")
    buy_won = buy_man * 10000

    # ===== 5) 추가 필터 (선택) =====
    with st.expander("🔧 추가 필터 — 직접 임계치 조정 (선택)", expanded=False):
        st.caption("프리셋 기본값에 추가 조건. 0 = 필터 미적용.")
        f1, f2, f3 = st.columns(3)
        f_value_min = f1.number_input("최소 거래대금 (억)", value=0, step=50,
                                        min_value=0, format="%d", key="hf_val")
        f_ret_min = f2.number_input("최소 당일 등락 (%)", value=0.0, step=1.0,
                                      format="%.1f", key="hf_rmin",
                                      help="예: 7% 이상만 보고 싶으면 7 입력")
        f_ret_max = f3.number_input("최대 당일 등락 (%)", value=0.0, step=1.0,
                                      format="%.1f", key="hf_rmax",
                                      help="0이면 미적용")
        f4, f5, f6 = st.columns(3)
        f_ret20_min = f4.number_input("최소 직전20일 누적 (%)",
                                        value=0.0, step=1.0, format="%.1f", key="hf_r20")
        f_rsi_min = f5.number_input("최소 RSI", value=0, step=5,
                                      min_value=0, max_value=100, format="%d", key="hf_rsim")
        f_rsi_max = f6.number_input("최대 RSI", value=0, step=5,
                                      min_value=0, max_value=100, format="%d", key="hf_rsiM")

    # ===== 6) 최종 요약 + 조회 버튼 (맨 아래) =====
    sel_years = sorted(st.session_state.hist_sel_years)
    sel_months = sorted(st.session_state.hist_sel_months)

    extra_filters = []
    if f_value_min > 0: extra_filters.append(f"대금≥{f_value_min}억")
    if f_ret_min > 0: extra_filters.append(f"당일≥{f_ret_min:.0f}%")
    if f_ret_max > 0: extra_filters.append(f"당일≤{f_ret_max:.0f}%")
    if f_ret20_min > 0: extra_filters.append(f"20일≥{f_ret20_min:.0f}%")
    if f_rsi_min > 0: extra_filters.append(f"RSI≥{f_rsi_min}")
    if f_rsi_max > 0: extra_filters.append(f"RSI≤{f_rsi_max}")
    extra_str = " · ".join(extra_filters) if extra_filters else "없음"

    st.markdown(
        f'<div style="padding:0.875rem 1.25rem;background:#F2F4F6;border-radius:8px;'
        f'margin:1.5rem 0 0.5rem 0;color:#191F28;line-height:1.7;">'
        f'📊 <b>최종 설정 요약</b><br>'
        f'• 연도: <b>{sel_years or "❌ 선택 안 됨"}</b> · 월: <b>{sel_months or "❌ 선택 안 됨"}</b><br>'
        f'• 일별 추천: <b>{daily_topk}개</b> · 매수금: <b>{fmt_won_kr(buy_won)}</b><br>'
        f'• 추가 필터: <b>{extra_str}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )
    run_query = st.button("🔍 시그널 조회 — 위 설정으로 가져오기",
                            type="primary", use_container_width=True,
                            key="hist_run")
    if not run_query:
        empty_state("🎯", "조회 대기 중",
                     "위에서 모든 설정을 마치고 [시그널 조회] 버튼을 누르세요.")
        return

    if not sel_years or not sel_months:
        empty_state("⚠️", "연도와 월을 1개 이상 선택하세요")
        return

    # ===== 5) 유니버스 + 데이터 조회 =====
    universe = cached_universe()
    if cap_cutoff > 0:
        listing = get_krx_listing()
        eligible = set(listing[listing["Marcap"] >= cap_cutoff]["Code"])
        universe = [t for t in universe if t in eligible]

    df_all = precompute_v3_signals(tuple(universe), sim_threshold, market_filter_on,
                                      profile_mode=profile_mode)
    if df_all.empty:
        empty_state("🔭", "시그널 없음", "임계치를 낮춰보세요.")
        return

    # OOS only: 사례 마지막 시점 이후만
    if oos_only:
        df_all = df_all[df_all["date"] > "2026-02-04"].copy()
        if df_all.empty:
            empty_state("🧪", "OOS 시그널 없음 (2026-02-05 이후)",
                         "OOS 모드는 정직하지만 표본이 작습니다. 토글 OFF로 전체 보기.")
            return

    month_df = df_all[df_all["year"].isin(sel_years) &
                      df_all["month"].isin(sel_months)].copy()

    # 추가 필터 적용
    before_n = len(month_df)
    if f_value_min > 0:
        month_df = month_df[month_df["value_eok"] >= f_value_min]
    if f_ret_min > 0:
        month_df = month_df[month_df["ret_1d"] >= f_ret_min / 100]
    if f_ret_max > 0:
        month_df = month_df[month_df["ret_1d"] <= f_ret_max / 100]
    if f_ret20_min > 0:
        month_df = month_df[month_df["ret_20d"] >= f_ret20_min / 100]
    if f_rsi_min > 0:
        month_df = month_df[month_df["rsi"] >= f_rsi_min]
    if f_rsi_max > 0:
        month_df = month_df[month_df["rsi"] <= f_rsi_max]
    after_n = len(month_df)
    if before_n != after_n:
        st.caption(f"🔧 추가 필터로 {before_n}건 → {after_n}건 ({before_n-after_n}건 제외)")

    if month_df.empty:
        empty_state("🔭", "선택한 조건에 맞는 시그널 없음",
                     "추가 필터를 완화하거나 기간을 변경하세요.")
        return

    # 시장 정보 매핑 (KOSDAQ GLOBAL/KONEX → KOSDAQ 통합)
    listing = get_krx_listing()
    market_map = dict(zip(listing["Code"], listing["Market"]))
    month_df["시장"] = month_df["ticker"].map(market_map).fillna("-")
    # 시장명 정규화
    market_normalize = {
        "KOSDAQ GLOBAL": "KOSDAQ",
        "KONEX": "KOSDAQ",
    }
    month_df["시장"] = month_df["시장"].replace(market_normalize)

    # 일별 상위 K개만 (유사도 순)
    month_df = (month_df.sort_values(["date", "similarity"], ascending=[True, False])
                  .groupby("date").head(daily_topk).reset_index(drop=True))
    # 일별 순위
    month_df["day_rank"] = (month_df.sort_values("similarity", ascending=False)
                              .groupby("date").cumcount() + 1)

    # 요약 KPI
    unique_stocks = month_df["ticker"].nunique()
    trading_days = month_df["date"].nunique()
    yr_str = "·".join(str(y) for y in sel_years)
    mo_str = "·".join(str(m) for m in sel_months)
    period_label = f"{yr_str}년 {mo_str}월"
    kpi_row([
        ("총 시그널", f"{len(month_df)}", period_label, ""),
        ("종목 수", f"{unique_stocks}", "중복 제외", "success"),
        ("거래일 수", f"{trading_days}", "시그널 발생일", ""),
        ("일평균 시그널",
         f"{len(month_df)/max(trading_days,1):.1f}", "건/일", "success"),
    ])

    # ===== 추천 사유 컬럼 생성 (왜 이 종목이 잡혔는지) =====
    def _reason(row):
        reasons = []
        if row.get("ret_20d", 0) >= 0.20:
            reasons.append(f"20일+{row['ret_20d']*100:.0f}%")
        if row.get("rsi", 0) >= 70:
            reasons.append(f"RSI{row['rsi']:.0f}(과매수)")
        if row.get("vol_ratio", 0) >= 8:
            reasons.append(f"거래량×{row['vol_ratio']:.0f}")
        if row.get("value_eok", 0) >= 500:
            reasons.append(f"대금{row['value_eok']:.0f}억")
        if row.get("close_to_high", 0) >= 0.97:
            reasons.append("막판매수")
        if row.get("ret_1d", 0) >= 0.10:
            reasons.append(f"당일+{row['ret_1d']*100:.0f}%")
        return " · ".join(reasons[:4]) if reasons else "-"

    month_df["추천사유"] = month_df.apply(_reason, axis=1)

    # 순위 라벨
    def _rank_label(r):
        if r == 1: return "🏆 대장주"
        if r == 2: return "🥈 2순위"
        if r == 3: return "🥉 3순위"
        return f"{int(r)}순위"
    month_df["순위"] = month_df["day_rank"].apply(_rank_label)

    # 기간별 수익률+손익 한 셀에 합치기
    def _combine(ret):
        if pd.isna(ret): return "-"
        won = ret * buy_won
        sign = "+" if ret >= 0 else ""
        return f"{sign}{ret*100:.1f}% ({fmt_won_kr(won)})"

    for src, dst in [("ret_d1", "익일"), ("ret_d10", "10일"),
                      ("ret_d30", "30일"), ("ret_d60", "60일"),
                      ("ret_d90", "90일"), ("ret_d120", "120일")]:
        month_df[dst] = month_df[src].apply(_combine)

    # 전체 리스트
    # 이 section_title은 월별 손익 표가 위로 가면서 이중 출력 — 제거 (아래에서 다시 출력)

    # 한국식 색상
    RED = "#F04452"; BLUE = "#3182F6"
    def _color_pct(v):
        if v is None or pd.isna(v): return ""
        try:
            if v > 0: return f"color: {RED}; font-weight: 800;"
            if v < 0: return f"color: {BLUE}; font-weight: 800;"
        except TypeError: return ""
        return ""
    def _color_sim(v):
        if v >= 0.8: return f"color: {RED}; font-weight: 800;"
        if v >= 0.7: return "color: #FF9F2E; font-weight: 700;"
        return ""

    def _color_rank(v):
        if "대장주" in str(v): return f"color: {RED}; font-weight: 800;"
        if "2순위" in str(v): return "color: #FF9F2E; font-weight: 700;"
        if "3순위" in str(v): return "color: #FF9F2E; font-weight: 600;"
        return ""

    def _color_won_str(v):
        if not isinstance(v, str) or v == "-": return ""
        if v.startswith("-"): return f"color: {BLUE}; font-weight: 700;"
        return f"color: {RED}; font-weight: 700;"

    # ===== 월별 손익 + 전체 손익 (시그널 리스트 위로 이동) =====
    section_title("💰 월별 손익 + 전체 손익")
    st.caption(f"종목당 매수금 {fmt_won_kr(buy_won)} 기준. 모든 시그널 평균 수익률 × 매수금.")

    period_cols = [("ret_d1", "익일"), ("ret_d10", "10일"),
                    ("ret_d30", "30일"), ("ret_d60", "60일"),
                    ("ret_d90", "90일"), ("ret_d120", "120일")]

    month_df["yyyymm"] = (month_df["year"].astype(str) + "-"
                            + month_df["month"].astype(str).str.zfill(2))
    monthly_rows = []
    for ym, g in month_df.groupby("yyyymm"):
        row = {"월": ym, "시그널수": len(g)}
        for col, lbl in period_cols:
            vals = g[col].dropna()
            if len(vals) > 0:
                row[f"{lbl} 평균"] = vals.mean()
                row[f"{lbl} 손익"] = fmt_won_kr(vals.sum() * buy_won)
            else:
                row[f"{lbl} 평균"] = None
                row[f"{lbl} 손익"] = "-"
        monthly_rows.append(row)

    total_row = {"월": "🏆 합계", "시그널수": len(month_df)}
    for col, lbl in period_cols:
        vals = month_df[col].dropna()
        if len(vals) > 0:
            total_row[f"{lbl} 평균"] = vals.mean()
            total_row[f"{lbl} 손익"] = fmt_won_kr(vals.sum() * buy_won)
        else:
            total_row[f"{lbl} 평균"] = None
            total_row[f"{lbl} 손익"] = "-"
    monthly_rows.append(total_row)

    monthly_df = pd.DataFrame(monthly_rows)

    fmt_dict_m = {}
    pct_cols_m = []
    won_cols_m = []
    for col, lbl in period_cols:
        fmt_dict_m[f"{lbl} 평균"] = "{:+.2%}"
        pct_cols_m.append(f"{lbl} 평균")
        won_cols_m.append(f"{lbl} 손익")

    monthly_styler = monthly_df.style.format(fmt_dict_m, na_rep="-")
    for c in pct_cols_m:
        monthly_styler = monthly_styler.applymap(_color_pct, subset=[c])
    for c in won_cols_m:
        monthly_styler = monthly_styler.applymap(_color_won_str, subset=[c])

    def _highlight_total(row):
        if str(row.iloc[0]).startswith("🏆"):
            return ["background-color: rgba(49,130,246,0.1); font-weight: 800;" for _ in row]
        return ["" for _ in row]
    monthly_styler = monthly_styler.apply(_highlight_total, axis=1)
    st.dataframe(monthly_styler, use_container_width=True, hide_index=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    section_title(f"📋 {period_label} 일자별 시그널 (일별 상위 {daily_topk}개)",
                   count=len(month_df))

    # 일자별 분기 표시
    for date, g in month_df.groupby("date"):
        g_show = g[[
            "순위", "name", "ticker", "시장",
            "similarity", "추천사유", "close",
            "ret_1d", "ret_20d", "value_eok",
            "익일", "10일", "30일", "60일", "90일",
        ]].rename(columns={
            "name": "종목명", "ticker": "코드",
            "similarity": "유사도", "close": "매수가",
            "ret_1d": "당일등락", "ret_20d": "직전20일(상승추세)",
            "value_eok": "거래대금(억)",
        })

        date_dt = pd.to_datetime(date)
        weekday = ["월","화","수","목","금","토","일"][date_dt.weekday()]
        st.markdown(
            f'<div style="margin:1rem 0 0.25rem 0;padding:0.5rem 0.875rem;'
            f'background:rgba(49,130,246,0.08);border-left:3px solid #3182F6;'
            f'border-radius:6px;font-size:0.9375rem;">'
            f'<b>📅 {date} ({weekday})</b> · {len(g_show)}종목</div>',
            unsafe_allow_html=True,
        )

        def _color_combined(v):
            if not isinstance(v, str) or v == "-": return ""
            if v.startswith("-"): return f"color: {BLUE}; font-weight: 700;"
            if v.startswith("+"): return f"color: {RED}; font-weight: 700;"
            return ""

        g_styler = g_show.style.format({
            "매수가": "{:,.0f}", "유사도": "{:.2f}",
            "당일등락": "{:+.2%}", "직전20일(상승추세)": "{:+.2%}",
            "거래대금(억)": "{:,.0f}",
        }, na_rep="-")
        for c in ["당일등락", "직전20일(상승추세)"]:
            g_styler = g_styler.applymap(_color_pct, subset=[c])
        for c in ["익일", "10일", "30일", "60일", "90일"]:
            g_styler = g_styler.applymap(_color_combined, subset=[c])
        g_styler = g_styler.applymap(_color_sim, subset=["유사도"])
        g_styler = g_styler.applymap(_color_rank, subset=["순위"])

        h = 40 + 38 * len(g_show)
        st.dataframe(g_styler, use_container_width=True,
                      height=h, hide_index=True)

    show_df = month_df  # 다운로드용

    # 종목별 집계 (월 내 같은 종목 여러 번 시그널 = 추세 강함)
    section_title("📊 종목별 집계 (월 내 다회 시그널)")
    stock_summary = (month_df.groupby(["name", "ticker", "시장"])
                       .agg(시그널수=("date", "count"),
                              평균유사도=("similarity", "mean"),
                              최대유사도=("similarity", "max"),
                              첫시그널=("date", "min"),
                              마지막시그널=("date", "max"))
                       .reset_index()
                       .sort_values(["시그널수", "평균유사도"], ascending=[False, False]))
    repeat = stock_summary[stock_summary["시그널수"] >= 2]
    if not repeat.empty:
        st.caption(f"⚡ 같은 달에 2회 이상 시그널 발생 종목 — {len(repeat)}개 (강한 추세)")
        st.dataframe(repeat.style.format({
            "평균유사도": "{:.2f}", "최대유사도": "{:.2f}",
        }), use_container_width=True, hide_index=True)
    else:
        st.caption("이 달에 2회 이상 시그널 발생한 종목 없음.")

    # ===== 매수 시뮬레이션 =====
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    section_title("💰 나의 매매 시뮬레이션 (매수가 직접 입력)")
    st.caption("실제 매수한 종목·매수가를 입력하면 익일~90일 보유 시 수익금 자동 계산.")

    sc1, sc2, sc3, sc4 = st.columns([1, 1, 1, 1])
    sim_code = sc1.text_input("종목 코드 (6자리)", value="", key="sim_code",
                                placeholder="예: 005930")
    sim_buy_date = sc2.text_input("매수일 (YYYY-MM-DD)", value="",
                                   key="sim_buy_date", placeholder="예: 2026-04-01")
    sim_buy_price = sc3.number_input("매수가 (원)", value=0, step=100,
                                       key="sim_buy_price", format="%d")
    sim_qty = sc4.number_input("수량 (주)", value=10, step=1, min_value=1,
                                key="sim_qty", format="%d")

    if sim_code and sim_buy_date and sim_buy_price > 0:
        try:
            code = sim_code.zfill(6)
            df_stock = get_ohlcv(code, "20210101", "20260517")
            buy_dt = pd.to_datetime(sim_buy_date)
            if buy_dt not in df_stock.index:
                # 다음 영업일
                future = df_stock.index[df_stock.index >= buy_dt]
                buy_dt = future[0] if len(future) else None
            if buy_dt is None:
                st.warning("매수일 이후 영업일 데이터 없음.")
            else:
                pos = df_stock.index.get_loc(buy_dt)
                sim_rows = []
                for n_days, lbl in [(1, "익일"), (10, "10일"), (30, "30일"),
                                      (60, "60일"), (90, "90일")]:
                    if pos + n_days < len(df_stock):
                        fut_close = float(df_stock.iloc[pos + n_days]["close"])
                        ret = (fut_close - sim_buy_price) / sim_buy_price
                        profit_won = (fut_close - sim_buy_price) * sim_qty
                        sim_rows.append({
                            "보유": lbl,
                            "청산일": df_stock.index[pos + n_days].strftime("%Y-%m-%d"),
                            "청산가": int(fut_close),
                            "수익률": ret,
                            "수익금(원)": profit_won,
                        })
                if sim_rows:
                    sim_df = pd.DataFrame(sim_rows)
                    sim_df["수익금(원)"] = sim_df["수익금(원)"].apply(fmt_won_kr)
                    sim_styler = sim_df.style.format({
                        "청산가": "{:,.0f}",
                        "수익률": "{:+.2%}",
                    })
                    sim_styler = sim_styler.applymap(_color_pct, subset=["수익률"])
                    st.dataframe(sim_styler, use_container_width=True, hide_index=True)
                    name_str = get_name(code)
                    total_invest = sim_buy_price * sim_qty
                    st.caption(f"📌 {name_str}({code}) · 매수일 {buy_dt.strftime('%Y-%m-%d')} · "
                                f"투자금 {fmt_won_kr(total_invest)} ({sim_qty}주 × {sim_buy_price:,}원)")
        except Exception as e:
            st.error(f"오류: {e}")

    # 다운로드
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    csv = show_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        f"📥 {period_label} 시그널 리스트 CSV",
        csv,
        f"history_{'_'.join(str(y) for y in sel_years)}_{'_'.join(str(m) for m in sel_months)}.csv",
        "text/csv",
        use_container_width=True,
    )


# ====================================================================
# 라우팅
# ====================================================================
PAGE_FN = {
    "today": page_today,
    "history": page_history,
    "themes": page_themes,
    "backtest": page_backtest,
    "walkforward": page_walkforward,
    "simulator": page_simulator,
    "cases": page_cases,
    "guide": page_guide,
}

PAGE_FN[st.session_state.page]()
