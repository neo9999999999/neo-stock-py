"""
네이버 금융 모바일 API 기반 테마/뉴스 스크래퍼
===========================================
finance.naver.com HTML이 IP/캐시 문제로 지연 데이터를 반환하므로,
m.stock.naver.com JSON API를 사용해 실시간 데이터를 가져옴.

엔드포인트:
- 테마 리스트: m.stock.naver.com/api/stocks/theme?sortType=changeRate&order=desc
- 테마 종목: m.stock.naver.com/api/stocks/theme/{no}
- 종목 뉴스: finance.naver.com/item/news_news.naver?code={code} (HTML)
"""


import copy
import datetime as dt
import time
from dataclasses import dataclass
from typing import Optional, List

import requests
from bs4 import BeautifulSoup

API_BASE = "https://m.stock.naver.com/api/stocks"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://m.stock.naver.com/",
}

# 메모리 캐시 (TTL 5분 — 실시간성 위해 짧게)
_CACHE: dict[str, tuple[float, object]] = {}
TTL = 300


def _cached(key: str):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    return None


def _put(key: str, val):
    _CACHE[key] = (time.time(), val)


# ----- 데이터 모델 ---------------------------------------------------------

@dataclass
class Theme:
    no: int
    name: str
    change_pct: float           # 평균 등락률
    rise_count: int             # 상승 종목 수
    fall_count: int             # 하락 종목 수
    total_count: int            # 전체 종목 수
    top_name: str = ""          # 대장주
    url: str = ""               # 데스크탑 URL


@dataclass
class ThemeStock:
    code: str
    name: str
    price: int
    change_pct: float
    volume: int                 # 누적 거래량
    value: int                  # 누적 거래대금 (백만원 단위)
    market_cap: int = 0         # 시가총액 (원 단위)


@dataclass
class News:
    title: str
    source: str
    date: str
    url: str


# ----- 테마 리스트 (등락률 순) --------------------------------------------

def fetch_top_themes(limit: int = 100, order: str = "desc") -> list[Theme]:
    """등락률 순 테마.

    order='desc' → 상승 상위
    order='asc'  → 하락 상위
    """
    cache_key = f"themes_{limit}_{order}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    url = f"{API_BASE}/theme"
    params = {"page": 1, "pageSize": limit,
               "sortType": "changeRate", "order": order}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        data = r.json()
    except Exception as exc:
        print(f"theme API err: {exc}")
        return []

    themes: list[Theme] = []
    for g in data.get("groups", []):
        try:
            change = float(g.get("changeRate", "0"))
        except (TypeError, ValueError):
            change = 0.0
        no = g.get("no", 0)
        themes.append(Theme(
            no=no,
            name=g.get("name", ""),
            change_pct=change,
            rise_count=int(g.get("riseCount", 0)),
            fall_count=int(g.get("fallCount", 0)),
            total_count=int(g.get("totalCount", 0)),
            url=f"https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no={no}",
        ))

    # 대장주 정보는 종목 상세 API 1번만 추가 호출 (top 5)
    for t in themes[:5]:
        stocks = fetch_theme_stocks_quick(t.no, top=1)
        if stocks:
            t.top_name = stocks[0].name

    _put(cache_key, themes)
    return themes


# ----- 테마 상세 종목 -----------------------------------------------------

def fetch_theme_stocks_quick(theme_no: int, top: int = 5) -> list[ThemeStock]:
    """간략 — top n개만."""
    return fetch_theme_stocks(theme_no, limit=top)


def fetch_theme_stocks(theme_no: int, limit: int = 30) -> list[ThemeStock]:
    """테마 내 종목 — 등락률 순."""
    cache_key = f"theme_stocks_{theme_no}_{limit}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    url = f"{API_BASE}/theme/{theme_no}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
    except Exception as exc:
        print(f"theme stocks API err: {exc}")
        return []

    out: list[ThemeStock] = []
    for s in data.get("stocks", []):
        try:
            ratio = float(s.get("fluctuationsRatio", "0"))
            price = int(s.get("closePrice", "0").replace(",", ""))
            vol = int(s.get("accumulatedTradingVolume", "0").replace(",", ""))
            val = int(s.get("accumulatedTradingValue", "0").replace(",", ""))
            mcap = int(s.get("marketValueRaw", 0) or 0)
        except (TypeError, ValueError, AttributeError):
            continue
        out.append(ThemeStock(
            code=s.get("itemCode", ""),
            name=s.get("stockName", ""),
            price=price,
            change_pct=ratio,
            volume=vol,
            value=val,                  # 백만원 단위
            market_cap=mcap,            # 원 단위
        ))
        if len(out) >= limit:
            break

    out.sort(key=lambda x: x.change_pct, reverse=True)
    _put(cache_key, out)
    return out


# ----- 시총 가중 / 대장주 평균 테마 (FINUP 스타일) -----------------------

def fetch_themes_weighted(
    limit: int = 100,
    method: str = "mcap",       # "mcap" 시총 가중, "leaders" 시총 상위 5
    leader_n: int = 5,
    enrich_top: int = 30,       # 상위 N개 테마만 재계산 (속도)
) -> list[Theme]:
    """네이버 테마 리스트를 가져온 뒤 종목 단위로 재계산.
    - 'mcap': 테마 내 모든 종목을 시총 가중 평균
    - 'leaders': 시총 상위 leader_n개만 등가중 평균 (FINUP 트리맵에 더 가까움)
    """
    cache_key = f"themes_w_{limit}_{method}_{leader_n}_{enrich_top}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    base_src = fetch_top_themes(limit=limit, order="desc")
    if not base_src:
        return []
    base = [copy.copy(t) for t in base_src]      # 캐시 mutation 방지

    for t in base[:enrich_top]:
        stocks = fetch_theme_stocks(t.no, limit=100)
        if not stocks:
            continue
        if method == "leaders":
            sorted_by_mcap = sorted(stocks, key=lambda s: s.market_cap, reverse=True)
            picks = [s for s in sorted_by_mcap if s.market_cap > 0][:leader_n]
            if picks:
                t.change_pct = sum(s.change_pct for s in picks) / len(picks)
                t.top_name = picks[0].name
        else:                          # mcap weighted
            total_cap = sum(s.market_cap for s in stocks if s.market_cap > 0)
            if total_cap > 0:
                t.change_pct = sum(
                    s.change_pct * s.market_cap for s in stocks if s.market_cap > 0
                ) / total_cap
                top = max(stocks, key=lambda s: s.market_cap)
                t.top_name = top.name

    base[:enrich_top] = sorted(base[:enrich_top], key=lambda x: x.change_pct, reverse=True)
    _put(cache_key, base)
    return base


# ----- 종목 현재가 (네이버 모바일 단일 종목 API) ----------------------------

def fetch_stock_current(code: str) -> dict:
    """종목 현재가 + 등락률 (실시간). 시그널 기준일 이후 가격 변화를 보여주기 위해 사용."""
    cache_key = f"current_{code}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    url = f"{API_BASE.replace('/stocks','/stock')}/{code}/basic"
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        data = r.json()
    except Exception:
        return {}

    try:
        result = {
            "code": code,
            "name": data.get("stockName", ""),
            "current_price": int(data.get("closePrice", "0").replace(",", "")),
            "change_pct": float(data.get("fluctuationsRatio", "0")),
            "market_status": data.get("marketStatus", ""),
            "traded_at": data.get("localTradedAt", ""),
        }
    except (TypeError, ValueError, AttributeError):
        return {}
    _put(cache_key, result)
    return result


# ----- 종목별 뉴스 (네이버 금융 HTML) ---------------------------------------

def fetch_stock_news(code: str, limit: int = 5) -> list[News]:
    cache_key = f"news_{code}_{limit}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1&sm=title_entity_id.basic"
    headers = {**HEADERS, "Accept": "text/html"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = "euc-kr"
        soup = BeautifulSoup(r.text, "lxml")
    except Exception:
        return []

    news_items: list[News] = []
    rows = soup.select("table.type5 tr")
    for tr in rows:
        title_a = tr.find("a")
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        if not title:
            continue
        href = title_a.get("href", "")
        news_url = "https://finance.naver.com" + href if href.startswith("/") else href
        source_td = tr.find("td", class_="info")
        date_td = tr.find("td", class_="date")
        source = source_td.get_text(strip=True) if source_td else ""
        date = date_td.get_text(strip=True) if date_td else ""
        if title and source:
            news_items.append(News(title=title, source=source, date=date, url=news_url))
            if len(news_items) >= limit:
                break
    _put(cache_key, news_items)
    return news_items


# ----- 종목 → 테마 매핑 ----------------------------------------------------

def find_themes_for_stock(code: str, themes: Optional[List[Theme]] = None) -> list[str]:
    cache_key = f"stock_themes_{code}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    if themes is None:
        themes = fetch_top_themes(limit=30)

    matches = []
    for t in themes:
        stocks = fetch_theme_stocks(t.no, limit=50)
        if any(s.code == code for s in stocks):
            matches.append(t.name)
        if len(matches) >= 3:
            break

    _put(cache_key, matches)
    return matches


# ----- 기준 시각 ----------------------------------------------------------

def fetch_basis_info() -> dict:
    """네이버 데이터 기준 영업일 추정.
    - 평일 9~16시: 오늘 (실시간)
    - 평일 16시 이후: 오늘 (종가 확정)
    - 평일 9시 이전: 어제 (직전 영업일)
    - 토요일: 금요일
    - 일요일: 금요일
    - 월요일 9시 이전: 금요일
    공휴일은 별도 처리 안 함.
    """
    now = dt.datetime.now()
    today = now.date()
    weekday = today.weekday()  # 월=0, 일=6

    if weekday == 5:                              # 토 → 금
        ref = today - dt.timedelta(days=1)
        market_status = "🔴 휴장 (주말)"
    elif weekday == 6:                            # 일 → 금
        ref = today - dt.timedelta(days=2)
        market_status = "🔴 휴장 (주말)"
    elif weekday == 0 and now.hour < 9:           # 월요일 9시 전 → 금
        ref = today - dt.timedelta(days=3)
        market_status = "⚪ 개장 전 (월요일 오전)"
    elif 1 <= weekday <= 4 and now.hour < 9:      # 화~금 9시 전 → 어제
        ref = today - dt.timedelta(days=1)
        market_status = "⚪ 개장 전"
    elif weekday < 5 and 9 <= now.hour < 16:      # 평일 9~16시 = 장중
        ref = today
        market_status = "🟢 장중 (실시간)"
    else:                                          # 평일 16시 이후
        ref = today
        market_status = "🔵 정규장 종료 (종가 확정)"

    is_market_open = (weekday < 5) and (9 <= now.hour < 16)
    return {
        "ref_date": ref.strftime("%Y-%m-%d"),
        "weekday": ["월", "화", "수", "목", "금", "토", "일"][ref.weekday()],
        "is_market_open": is_market_open,
        "market_status": market_status,
        "now": now.strftime("%Y-%m-%d %H:%M"),
    }


# ----- 빠른 동작 확인 -----------------------------------------------------

if __name__ == "__main__":
    print("상위 테마 5개 (등락률 순):")
    for t in fetch_top_themes(limit=5):
        print(f"  {t.name:<35} {t.change_pct:+.2f}%  "
              f"({t.rise_count}↑/{t.fall_count}↓)  대장: {t.top_name}")
