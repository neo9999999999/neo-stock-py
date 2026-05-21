"""
디자인 시스템 통합 테마 — Dashboard Design System v1.0 기반.

기존 코드 호환성:
- PALETTE, PALETTE_LIGHT, PALETTE_DARK (구버전 키 → 새 토큰 매핑)
- inject_css(theme="light"|"dark")
- hero, section_title, bento, stock_card_html, theme_card_html, empty_state, code
"""

import streamlit as st

# ----- 구버전 호환 PALETTE (코드에서 직접 참조하는 곳들 위해) -----

PALETTE_LIGHT = {
    "bg":           "#F7F8FA",
    "bg_alt":       "#FFFFFF",
    "bg_card":      "#FFFFFF",
    "border":       "#E2E5EC",
    "border_soft":  "#EEF0F4",
    "text":         "#14182A",
    "text_sub":     "#343A4A",
    "text_mute":    "#6B7385",
    "accent":       "#4F5DE8",
    "accent_dark":  "#3E48C7",
    "success":      "#1FAB6B",
    "danger":       "#E5484D",
    "warning":      "#F5A623",
    "code_bg":      "#EEF0F4",
}

PALETTE_DARK = {
    "bg":           "#0B0E1A",
    "bg_alt":       "#151A2B",
    "bg_card":      "#151A2B",
    "border":       "rgba(255,255,255,0.09)",
    "border_soft":  "rgba(255,255,255,0.05)",
    "text":         "#ECEEF5",
    "text_sub":     "#C3C8D6",
    "text_mute":    "#8C93A6",
    "accent":       "#8E9FFF",
    "accent_dark":  "#6B7CF6",
    "success":      "#5CD9A0",
    "danger":       "#FF8B8E",
    "warning":      "#FFC15C",
    "code_bg":      "#1A1F32",
}

PALETTE = PALETTE_LIGHT


# ----- 디자인 시스템 CSS (tokens + 커스텀 컴포넌트 + Streamlit 매핑) -----

CSS = """
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet" />
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet" />

<style>
/* ============================================================================
   DESIGN TOKENS — Dashboard Design System v1.0
   ============================================================================ */
:root {
  /* Brand */
  --blue-50:#EEF2FF; --blue-100:#DCE3FF; --blue-200:#B8C5FF; --blue-300:#8E9FFF;
  --blue-400:#6B7CF6; --blue-500:#4F5DE8; --blue-600:#3E48C7; --blue-700:#2F359E;
  --blue-800:#232879; --blue-900:#181C57;

  /* Neutral */
  --slate-0:#FFFFFF; --slate-50:#F7F8FA; --slate-100:#EEF0F4; --slate-200:#E2E5EC;
  --slate-300:#CACFD9; --slate-400:#9AA1B1; --slate-500:#6B7385; --slate-600:#4A5163;
  --slate-700:#343A4A; --slate-800:#232838; --slate-900:#14182A; --slate-950:#0A0D1A;

  /* Status palette */
  --green-50:#E6F8EF; --green-100:#C6F0D8; --green-500:#1FAB6B; --green-600:#0E8A53; --green-700:#0A6B41;
  --amber-50:#FFF6E0; --amber-100:#FFE7B2; --amber-500:#F5A623; --amber-600:#D08612; --amber-700:#9C610A;
  --red-50:#FDECEC;   --red-100:#FACBCB;   --red-500:#E5484D;   --red-600:#C12B30;   --red-700:#931E22;
  --sky-50:#E6F4FE;   --sky-100:#C2E2FC;   --sky-500:#2E96E7;   --sky-600:#1B79C2;
  --violet-50:#F0EBFE; --violet-100:#DCD0FC; --violet-500:#7B5CE6; --violet-600:#5E3FCC;

  /* Typography */
  --font-sans:"Pretendard",-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;
  --font-mono:"JetBrains Mono","SF Mono",ui-monospace,Menlo,Consolas,monospace;
  --fs-2xs:10px; --fs-xs:11px; --fs-sm:12px; --fs-md:13px; --fs-base:14px;
  --fs-lg:16px;  --fs-xl:18px; --fs-2xl:22px; --fs-3xl:28px; --fs-4xl:36px;
  --fw-regular:400; --fw-medium:500; --fw-semibold:600; --fw-bold:700;
  --lh-tight:1.2; --lh-snug:1.35; --lh-base:1.5; --lh-loose:1.65;

  /* Spacing */
  --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-5:20px;
  --space-6:24px; --space-7:32px; --space-8:40px; --space-9:48px;

  /* Radii */
  --radius-xs:2px; --radius-sm:4px; --radius-md:6px; --radius-lg:8px;
  --radius-xl:12px; --radius-2xl:16px; --radius-pill:999px;

  /* Shadows */
  --shadow-xs:0 1px 2px rgba(20,24,42,.04);
  --shadow-1: 0 1px 2px rgba(20,24,42,.05),0 1px 1px rgba(20,24,42,.04);
  --shadow-2: 0 4px 12px rgba(20,24,42,.08),0 1px 2px rgba(20,24,42,.04);
  --shadow-3: 0 12px 32px rgba(20,24,42,.12),0 2px 4px rgba(20,24,42,.06);
  --shadow-focus:0 0 0 3px rgba(79,93,232,.24);

  /* Motion */
  --dur-fast:140ms; --dur-base:220ms; --dur-slow:360ms;
  --ease-standard:cubic-bezier(0.2,0,0,1);
  --ease-out:cubic-bezier(0,0,0.2,1);

  /* Chart palette */
  --chart-1:#4F5DE8; --chart-2:#2E96E7; --chart-3:#1FAB6B; --chart-4:#F5A623;
  --chart-5:#E5484D; --chart-6:#7B5CE6; --chart-7:#14B8A6; --chart-8:#EC4899;
}

/* SEMANTIC — LIGHT (default) */
:root,
[data-theme="light"] {
  --bg-page:var(--slate-50);
  --bg-surface:var(--slate-0);
  --bg-elevated:var(--slate-0);
  --bg-muted:var(--slate-100);
  --bg-subtle:var(--slate-50);
  --bg-hover:rgba(20,24,42,.04);
  --bg-active:rgba(20,24,42,.07);
  --bg-selected:var(--blue-50);

  --fg-1:var(--slate-900);
  --fg-2:var(--slate-700);
  --fg-3:var(--slate-500);
  --fg-muted:var(--slate-400);
  --fg-disabled:var(--slate-300);
  --fg-link:var(--blue-600);
  --fg-brand:var(--blue-600);
  --fg-onbrand:var(--slate-0);

  --border-subtle:var(--slate-100);
  --border-default:var(--slate-200);
  --border-strong:var(--slate-300);
  --border-focus:var(--blue-500);

  --accent-bg:var(--blue-500);
  --accent-bg-hover:var(--blue-600);
  --accent-fg:var(--slate-0);
  --accent-subtle:var(--blue-50);
  --accent-strong:var(--blue-700);

  --success-bg:var(--green-500); --success-fg:var(--slate-0);
  --success-subtle:var(--green-50); --success-text:var(--green-700); --success-border:var(--green-100);
  --warning-bg:var(--amber-500); --warning-fg:var(--slate-900);
  --warning-subtle:var(--amber-50); --warning-text:var(--amber-700); --warning-border:var(--amber-100);
  --danger-bg:var(--red-500); --danger-fg:var(--slate-0);
  --danger-subtle:var(--red-50); --danger-text:var(--red-700); --danger-border:var(--red-100);
  --info-bg:var(--sky-500); --info-fg:var(--slate-0);
  --info-subtle:var(--sky-50); --info-text:var(--sky-600); --info-border:var(--sky-100);

  /* Korean market color (red = up, blue = down) — 한국식 가격 변동 */
  --price-up:var(--red-500);     /* +가 빨강 */
  --price-down:var(--blue-500);  /* -가 파랑 */
}

[data-theme="dark"] {
  --bg-page:#0B0E1A; --bg-surface:#151A2B; --bg-elevated:#1C2238;
  --bg-muted:#1A1F32; --bg-subtle:#131727;
  --bg-hover:rgba(255,255,255,.05); --bg-active:rgba(255,255,255,.08);
  --bg-selected:rgba(79,93,232,.18);

  --fg-1:#ECEEF5; --fg-2:#C3C8D6; --fg-3:#8C93A6;
  --fg-muted:#5F667A; --fg-disabled:#3D4358;
  --fg-link:#8E9FFF; --fg-brand:#8E9FFF; --fg-onbrand:var(--slate-0);

  --border-subtle:rgba(255,255,255,.05);
  --border-default:rgba(255,255,255,.09);
  --border-strong:rgba(255,255,255,.15);
  --border-focus:#6B7CF6;

  --accent-bg:#4F5DE8; --accent-bg-hover:#6B7CF6; --accent-fg:var(--slate-0);
  --accent-subtle:rgba(79,93,232,.16); --accent-strong:#8E9FFF;

  --success-bg:#1FAB6B; --success-fg:var(--slate-0);
  --success-subtle:rgba(31,171,107,.16); --success-text:#5CD9A0; --success-border:rgba(31,171,107,.32);
  --warning-bg:#F5A623; --warning-fg:var(--slate-900);
  --warning-subtle:rgba(245,166,35,.16); --warning-text:#FFC15C; --warning-border:rgba(245,166,35,.32);
  --danger-bg:#E5484D; --danger-fg:var(--slate-0);
  --danger-subtle:rgba(229,72,77,.16); --danger-text:#FF8B8E; --danger-border:rgba(229,72,77,.32);
  --info-bg:#2E96E7; --info-fg:var(--slate-0);
  --info-subtle:rgba(46,150,231,.16); --info-text:#6ABEF2; --info-border:rgba(46,150,231,.32);

  --price-up:#FF8B8E; --price-down:#8E9FFF;

  --shadow-xs:0 1px 2px rgba(0,0,0,.4);
  --shadow-1:0 1px 2px rgba(0,0,0,.5),0 1px 1px rgba(0,0,0,.3);
  --shadow-2:0 4px 12px rgba(0,0,0,.5),0 1px 2px rgba(0,0,0,.3);
  --shadow-3:0 12px 32px rgba(0,0,0,.55),0 2px 4px rgba(0,0,0,.3);
  --shadow-focus:0 0 0 3px rgba(142,159,255,.32);
}

/* ============================================================================
   GLOBAL RESETS
   ============================================================================ */
*,*::before,*::after{box-sizing:border-box;}
html,body{
  margin:0;padding:0;
  font-family:var(--font-sans);
  font-size:var(--fs-base);
  color:var(--fg-2);
  background:var(--bg-page);
  -webkit-font-smoothing:antialiased;
  font-feature-settings:"ss01","ss02","tnum";
}
h1,h2,h3,h4,h5,h6{margin:0;color:var(--fg-1);font-weight:var(--fw-semibold);line-height:var(--lh-snug);}
p{margin:0;}
a{color:var(--fg-link);text-decoration:none;}
a:hover{text-decoration:underline;}
.mono,.tabular{font-family:var(--font-mono);font-variant-numeric:tabular-nums;}

/* ============================================================================
   STREAMLIT 컨테이너 매핑 (Streamlit 기본 클래스에 우리 토큰 강제)
   ============================================================================ */
.stApp{background:var(--bg-page);}
[data-testid="stMain"],section.main{background:var(--bg-page);color:var(--fg-2);}
.block-container{padding-top:1.5rem !important;padding-bottom:2rem !important;max-width:1280px;}

/* Sidebar */
section[data-testid="stSidebar"]{
  background:var(--bg-surface);
  border-right:1px solid var(--border-subtle);
}
section[data-testid="stSidebar"] *{color:var(--fg-2);}

/* Buttons — Streamlit 기본 버튼 */
.stButton > button, .stDownloadButton > button{
  font-family:var(--font-sans);
  font-size:var(--fs-md);
  font-weight:var(--fw-medium);
  border-radius:var(--radius-md);
  border:1px solid var(--border-default);
  background:var(--bg-surface);
  color:var(--fg-1);
  padding:0.5rem 1rem;
  transition:all var(--dur-fast) var(--ease-standard);
  box-shadow:var(--shadow-xs);
}
.stButton > button:hover{
  background:var(--bg-hover);
  border-color:var(--border-strong);
  box-shadow:var(--shadow-1);
}
.stButton > button:focus{
  box-shadow:var(--shadow-focus);
  outline:none;
}
.stButton > button[kind="primary"],
.stButton > button[data-baseweb="button"][kind="primary"]{
  background:var(--accent-bg) !important;
  color:var(--accent-fg) !important;
  border-color:var(--accent-bg) !important;
}
.stButton > button[kind="primary"]:hover{background:var(--accent-bg-hover) !important;}

/* Inputs / Select */
.stTextInput input, .stNumberInput input,
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea{
  background:var(--bg-surface) !important;
  border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important;
  color:var(--fg-1) !important;
  font-family:var(--font-sans);
  font-size:var(--fs-base);
}
.stTextInput input:focus, .stNumberInput input:focus{
  border-color:var(--border-focus) !important;
  box-shadow:var(--shadow-focus) !important;
  outline:none;
}
[data-baseweb="select"]{
  background:var(--bg-surface) !important;
  border-radius:var(--radius-md) !important;
}
[data-baseweb="select"] > div{
  background:var(--bg-surface) !important;
  border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important;
  color:var(--fg-1) !important;
}

/* Slider */
.stSlider [data-baseweb="slider"] [role="slider"]{
  background:var(--accent-bg) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom:1px solid var(--border-default);}
.stTabs [data-baseweb="tab"]{
  color:var(--fg-3);font-weight:var(--fw-medium);font-size:var(--fs-base);
  padding:0.625rem 1rem;border-radius:0;
}
.stTabs [aria-selected="true"]{color:var(--fg-brand);}

/* Dataframe */
[data-testid="stDataFrame"]{
  border:1px solid var(--border-default);
  border-radius:var(--radius-lg);
  overflow:hidden;
}

/* Expander */
[data-testid="stExpander"]{
  border:1px solid var(--border-default);
  border-radius:var(--radius-lg);
  background:var(--bg-surface);
}
[data-testid="stExpander"] summary{
  font-weight:var(--fw-medium);
  color:var(--fg-1);
}

/* Info / Success / Warning / Error alerts */
[data-testid="stAlert"]{
  border-radius:var(--radius-lg) !important;
  border:1px solid var(--border-default);
  padding:0.875rem 1rem;
}

/* Divider — section 구분 */
.divider{
  height:1px;background:var(--border-subtle);
  margin:1.5rem 0;width:100%;
}

/* ============================================================================
   CUSTOM COMPONENTS — 우리 앱 전용
   ============================================================================ */

/* Brand mark in sidebar */
.brand-mark{
  display:flex;align-items:center;gap:8px;
  font-weight:var(--fw-bold);font-size:1rem;
  color:var(--fg-1);margin-bottom:1.25rem;
}
.brand-mark .dot{
  width:8px;height:8px;border-radius:50%;
  background:var(--accent-bg);
  box-shadow:0 0 0 4px var(--accent-subtle);
}

/* Hero */
.hero{margin-bottom:1.5rem;}
.hero .eyebrow{
  font-size:var(--fs-xs);
  font-weight:var(--fw-semibold);
  color:var(--fg-brand);
  text-transform:uppercase;
  letter-spacing:var(--tracking-wide,0.04em);
  margin-bottom:0.375rem;
}
.hero h1{
  font-size:var(--fs-3xl);
  font-weight:var(--fw-bold);
  color:var(--fg-1);
  letter-spacing:var(--tracking-tight,-0.02em);
  line-height:var(--lh-tight);
  margin:0 0 0.5rem 0;
}
.hero .lead{
  font-size:var(--fs-base);
  color:var(--fg-3);
  line-height:var(--lh-base);
  max-width:64ch;
}

/* Section title */
.section-title{
  display:flex;align-items:baseline;gap:0.5rem;
  margin:1.5rem 0 0.75rem 0;
}
.section-title h2{
  font-size:var(--fs-xl);
  font-weight:var(--fw-semibold);
  color:var(--fg-1);
  margin:0;
}
.section-title .count{
  font-family:var(--font-mono);
  font-size:var(--fs-sm);
  color:var(--fg-3);
  background:var(--bg-muted);
  padding:2px 8px;
  border-radius:var(--radius-pill);
}

/* KPI Bento */
.bento{
  background:var(--bg-surface);
  border:1px solid var(--border-default);
  border-radius:var(--radius-xl);
  padding:1rem 1.125rem;
  box-shadow:var(--shadow-xs);
  display:flex;flex-direction:column;gap:4px;
}
.bento .label{
  font-size:var(--fs-xs);
  color:var(--fg-3);
  font-weight:var(--fw-medium);
  text-transform:uppercase;
  letter-spacing:var(--tracking-wide,0.04em);
}
.bento .value{
  font-family:var(--font-mono);
  font-size:var(--fs-2xl);
  font-weight:var(--fw-bold);
  color:var(--fg-1);
  font-variant-numeric:tabular-nums;
  letter-spacing:var(--tracking-tight,-0.01em);
}
.bento .value.success{color:var(--success-text);}
.bento .value.danger{color:var(--danger-text);}
.bento .value.warning{color:var(--warning-text);}
.bento .sub{font-size:var(--fs-xs);color:var(--fg-muted);}

/* Stock card — 종목 카드 */
.stock-card{
  background:var(--bg-surface);
  border:1px solid var(--border-default);
  border-radius:var(--radius-xl);
  padding:1rem 1.125rem;
  margin-bottom:0.625rem;
  box-shadow:var(--shadow-xs);
  display:flex;
  align-items:center;
  gap:0.875rem;
  transition:all var(--dur-fast) var(--ease-standard);
}
.stock-card:hover{
  border-color:var(--border-strong);
  box-shadow:var(--shadow-1);
}
.stock-card .rank{
  flex:0 0 44px;
  font-family:var(--font-mono);
  font-size:var(--fs-xl);
  font-weight:var(--fw-bold);
  color:var(--fg-muted);
  text-align:center;
}
.stock-card .rank.leader{color:var(--accent-bg);}
.stock-card .info{flex:1 1 auto;min-width:0;}
.stock-card .info .name{
  font-size:var(--fs-lg);
  font-weight:var(--fw-semibold);
  color:var(--fg-1);
  margin:0 0 0.25rem 0;
  word-break:keep-all;
  overflow-wrap:break-word;
}
.stock-card .info .meta{
  font-size:var(--fs-xs);
  color:var(--fg-3);
  font-family:var(--font-mono);
  word-break:keep-all;
  line-height:var(--lh-snug);
}
.stock-card .badges{
  display:flex;flex-wrap:wrap;gap:4px;
  margin-top:6px;
}
.stock-card .themes{
  margin-top:6px;
  display:flex;flex-wrap:wrap;align-items:center;gap:4px;
}
.stock-card .themes .label{
  font-size:var(--fs-2xs);
  color:var(--fg-muted);
  font-weight:var(--fw-semibold);
  text-transform:uppercase;
  letter-spacing:0.04em;
  margin-right:2px;
}
.stock-card .themes .chip{
  display:inline-block;
  padding:2px 8px;
  background:var(--accent-subtle);
  color:var(--fg-brand);
  border-radius:var(--radius-pill);
  font-size:var(--fs-xs);
  font-weight:var(--fw-medium);
}
.stock-card .news{
  margin-top:8px;
  padding-top:8px;
  border-top:1px dashed var(--border-subtle);
}
.stock-card .news-item{
  font-size:var(--fs-xs);
  color:var(--fg-3);
  line-height:var(--lh-snug);
  margin-bottom:3px;
}
.stock-card .news-item .source{
  color:var(--fg-muted);
  font-size:var(--fs-2xs);
  font-weight:var(--fw-semibold);
  margin-right:5px;
}
.stock-card .news-item a{color:var(--fg-3);}
.stock-card .news-item a:hover{color:var(--fg-link);}
.stock-card .stats{
  flex:0 0 auto;
  text-align:right;
  font-family:var(--font-mono);
  min-width:100px;
}
.stock-card .stats .price{
  font-size:var(--fs-lg);
  font-weight:var(--fw-bold);
  color:var(--fg-1);
  font-variant-numeric:tabular-nums;
}
.stock-card .stats .change{
  font-size:var(--fs-sm);
  font-weight:var(--fw-semibold);
  margin-top:2px;
  font-variant-numeric:tabular-nums;
}
.stock-card .stats .change.up{color:var(--price-up);}
.stock-card .stats .change.down{color:var(--price-down);}

/* Badges (tags) */
.tag{
  display:inline-flex;align-items:center;gap:2px;
  padding:2px 8px;
  font-size:var(--fs-2xs);
  font-weight:var(--fw-semibold);
  border-radius:var(--radius-pill);
  background:var(--bg-muted);
  color:var(--fg-2);
  border:1px solid transparent;
  line-height:var(--lh-tight);
}
.tag.accent{background:var(--accent-subtle);color:var(--accent-strong);}
.tag.success{background:var(--success-subtle);color:var(--success-text);}
.tag.warning{background:var(--warning-subtle);color:var(--warning-text);}
.tag.danger{background:var(--danger-subtle);color:var(--danger-text);}
.score-pill{
  display:inline-flex;align-items:center;gap:2px;
  padding:2px 8px;
  font-size:var(--fs-2xs);
  font-weight:var(--fw-bold);
  border-radius:var(--radius-pill);
  background:var(--accent-subtle);
  color:var(--accent-strong);
  font-family:var(--font-mono);
}
.score-pill.s5{background:var(--success-subtle);color:var(--success-text);}
.score-pill.s4{background:var(--success-subtle);color:var(--success-text);}
.score-pill.s3{background:var(--warning-subtle);color:var(--warning-text);}
.score-pill.s2,.score-pill.s1{background:var(--danger-subtle);color:var(--danger-text);}

/* Theme card */
.theme-card{
  background:var(--bg-surface);
  border:1px solid var(--border-default);
  border-radius:var(--radius-xl);
  padding:0.875rem 1rem;
  margin-bottom:0.5rem;
  box-shadow:var(--shadow-xs);
  display:flex;align-items:center;gap:0.875rem;
  transition:all var(--dur-fast) var(--ease-standard);
}
.theme-card:hover{border-color:var(--border-strong);box-shadow:var(--shadow-1);}
.theme-card .rank{
  flex:0 0 36px;font-family:var(--font-mono);
  font-size:var(--fs-lg);font-weight:var(--fw-bold);
  color:var(--fg-muted);text-align:center;
}
.theme-card .body{flex:1 1 auto;min-width:0;}
.theme-card .body .name{
  font-size:var(--fs-base);font-weight:var(--fw-semibold);
  color:var(--fg-1);
}
.theme-card .body .meta{
  font-size:var(--fs-xs);color:var(--fg-3);font-family:var(--font-mono);
}
.theme-card .change{
  flex:0 0 auto;
  font-family:var(--font-mono);
  font-size:var(--fs-lg);font-weight:var(--fw-bold);
  font-variant-numeric:tabular-nums;
}
.theme-card .change.up{color:var(--price-up);}
.theme-card .change.down{color:var(--price-down);}

/* Empty state */
.empty-state{
  background:var(--bg-surface);
  border:1px dashed var(--border-default);
  border-radius:var(--radius-xl);
  padding:2.5rem 1.5rem;
  text-align:center;
  margin:1rem 0;
}
.empty-state .icon{font-size:2.5rem;margin-bottom:0.5rem;}
.empty-state h3{
  color:var(--fg-1);margin:0 0 0.375rem 0;
  font-size:var(--fs-lg);font-weight:var(--fw-semibold);
}
.empty-state p{color:var(--fg-3);font-size:var(--fs-sm);margin:0;}

/* Inline code */
.inline-code{
  font-family:var(--font-mono);
  background:var(--bg-muted);
  color:var(--fg-1);
  padding:2px 6px;
  border-radius:var(--radius-sm);
  font-size:0.92em;
}

/* ============================================================================
   모바일 반응형 (≤768px) — 핵심
   ============================================================================ */
@media (max-width: 768px) {
  /* 페이지 패딩 줄임 */
  .block-container{padding-left:0.875rem !important;padding-right:0.875rem !important;padding-top:0.875rem !important;}

  /* Streamlit columns 가로 유지 (자동 stack 방지) */
  [data-testid="stHorizontalBlock"]{
    flex-direction:row !important;
    flex-wrap:wrap !important;
    gap:0.25rem !important;
  }
  [data-testid="stHorizontalBlock"] > [data-testid="column"]{
    min-width:0 !important;
    flex:1 1 calc(50% - 0.25rem) !important;
  }

  /* Hero 축소 */
  .hero h1{font-size:var(--fs-xl) !important;}
  .hero .eyebrow{font-size:var(--fs-2xs) !important;}
  .hero .lead{font-size:var(--fs-sm) !important;}

  /* Section title 축소 */
  .section-title{margin:1rem 0 0.5rem 0;}
  .section-title h2{font-size:var(--fs-base) !important;}

  /* Bento KPI 모바일 컴팩트 */
  .bento{padding:0.625rem 0.75rem;}
  .bento .label{font-size:var(--fs-2xs);}
  .bento .value{font-size:var(--fs-lg);}
  .bento .sub{font-size:var(--fs-2xs);}

  /* Stock card 모바일 핵심 */
  .stock-card{
    padding:0.75rem !important;
    gap:0.5rem !important;
    align-items:center !important;
    flex-wrap:nowrap !important;
  }
  .stock-card .rank{
    flex:0 0 28px !important;
    font-size:var(--fs-base) !important;
  }
  .stock-card .info{flex:1 1 auto;min-width:0;overflow:hidden;}
  .stock-card .info .name{
    font-size:var(--fs-base) !important;
    margin-bottom:2px !important;
    line-height:var(--lh-snug);
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
  }
  .stock-card .info .meta{
    font-size:var(--fs-2xs) !important;
    line-height:var(--lh-snug);
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
  }
  .stock-card .badges{gap:3px !important;margin-top:3px !important;}
  .stock-card .badges .tag,
  .stock-card .badges .score-pill{
    font-size:var(--fs-2xs) !important;
    padding:1px 5px !important;
  }
  .stock-card .themes{margin-top:3px !important;}
  .stock-card .themes .label{display:none !important;}
  .stock-card .themes .chip{
    font-size:var(--fs-2xs) !important;
    padding:1px 5px !important;
  }
  /* 모바일에선 뉴스 숨김 — 공간 절약 */
  .stock-card .news{display:none !important;}
  .stock-card .stats{
    flex:0 0 auto;
    min-width:72px !important;
  }
  .stock-card .stats .price{font-size:var(--fs-base) !important;}
  .stock-card .stats .change{font-size:var(--fs-xs) !important;}

  /* Theme card 모바일 */
  .theme-card{padding:0.625rem 0.75rem;gap:0.5rem;}
  .theme-card .rank{flex:0 0 28px;font-size:var(--fs-base);}
  .theme-card .body .name{font-size:var(--fs-sm);}
  .theme-card .body .meta{font-size:var(--fs-2xs);}
  .theme-card .change{font-size:var(--fs-base);}

  /* Streamlit 컴포넌트 폰트 축소 */
  .stButton > button, .stDownloadButton > button{
    font-size:var(--fs-sm) !important;
    padding:0.45rem 0.625rem !important;
  }
  label, .stTextInput label, .stNumberInput label{
    font-size:var(--fs-sm) !important;
  }
  [data-baseweb="select"] *{font-size:var(--fs-sm) !important;}

  /* DataFrame 가로 스크롤 + 폰트 축소 */
  [data-testid="stDataFrame"]{
    overflow-x:auto !important;
  }
  [data-testid="stDataFrame"] *{font-size:var(--fs-xs) !important;}

  /* Sidebar 너비 모바일에서 더 좁게 (drawer로 동작) */
  section[data-testid="stSidebar"]{
    min-width:240px !important;
    max-width:280px !important;
  }
}

/* ============================================================================
   초소형 모바일 (≤480px) — 더 강한 축소
   ============================================================================ */
@media (max-width: 480px) {
  .block-container{padding-left:0.5rem !important;padding-right:0.5rem !important;}

  /* Stock card 가장 컴팩트 */
  .stock-card{padding:0.625rem !important;gap:0.4rem !important;}
  .stock-card .rank{flex:0 0 22px !important;font-size:var(--fs-sm) !important;}
  .stock-card .info .name{font-size:var(--fs-sm) !important;}
  .stock-card .info .meta{display:none !important;}   /* 메타 라인 완전 숨김 */
  .stock-card .themes{display:none !important;}        /* 테마 칩 숨김 */
  .stock-card .stats{min-width:60px !important;}
  .stock-card .stats .price{font-size:var(--fs-sm) !important;}

  /* 1열 그리드 — columns 한 줄에 다 못 들어가면 wrap */
  [data-testid="stHorizontalBlock"] > [data-testid="column"]{
    flex:1 1 100% !important;
  }
}

/* ============================================================================
   터치 영역 보장 (모바일 hit target 44px+)
   ============================================================================ */
@media (hover: none) and (pointer: coarse) {
  .stButton > button, .stDownloadButton > button{min-height:40px;}
  [role="button"], button[type="submit"]{min-height:40px;}
}
</style>
"""


# DARK_OVERRIDE은 더 이상 필요 없음 — data-theme로 자동 전환
DARK_OVERRIDE = ""


def inject_css(theme: str = "light"):
    """Streamlit 페이지 상단에서 호출. CSS 주입 + data-theme 속성 설정."""
    global PALETTE
    PALETTE = PALETTE_DARK if theme == "dark" else PALETTE_LIGHT
    st.markdown(CSS, unsafe_allow_html=True)
    # data-theme 속성을 html에 설정 (디자인 시스템의 [data-theme="dark"] 토큰 활성화)
    st.markdown(
        f'<script>document.documentElement.setAttribute("data-theme", "{theme}");</script>',
        unsafe_allow_html=True,
    )


def current_palette():
    return PALETTE


# ----- 컴포넌트 헬퍼 함수 ----------------------------------------------

def hero(eyebrow: str, title: str, lead: str = ""):
    """페이지 상단 hero 섹션."""
    lead_html = f'<p class="lead">{lead}</p>' if lead else ""
    html = (
        f'<div class="hero">'
        f'<div class="eyebrow">{eyebrow}</div>'
        f'<h1>{title}</h1>'
        f'{lead_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def section_title(title: str, count=None):
    cnt = f'<span class="count">{count}</span>' if count is not None else ''
    st.markdown(
        f'<div class="section-title"><h2>{title}</h2>{cnt}</div>',
        unsafe_allow_html=True,
    )


def bento(label: str, value: str, sub: str = "", tone: str = ""):
    """Bento 스타일 KPI 카드. tone: 'success' | 'danger' | 'warning' | ''."""
    tone_cls = f" {tone}" if tone else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="bento"><div class="label">{label}</div>'
        f'<div class="value{tone_cls}">{value}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def stock_card_html(rank: int, name: str, ticker: str, score: int,
                    close: int, ret_pct: float, value_eok: float,
                    vol_ratio: float, close_to_high: float, is_new_high: bool,
                    themes=None,
                    news=None,
                    current_price: int = 0,
                    current_change_pct: float = 0.0) -> str:
    is_leader = rank == 1
    rank_cls = " leader" if is_leader else ""
    score_cls = f"s{min(score, 5)}"
    change_cls = "up" if ret_pct > 0 else "down"

    badges = []
    custom_badge = None
    if themes and isinstance(themes, list) and themes and themes[0].startswith("##BADGE:"):
        custom_badge = themes[0].replace("##BADGE:", "")
        themes = themes[1:]
    if custom_badge:
        badges.append(custom_badge)
    elif is_leader:
        badges.append('<span class="tag accent">대장주</span>')
    if is_new_high:
        badges.append('<span class="tag success">신고가</span>')
    if score > 0:
        badges.append(f'<span class="score-pill {score_cls}">⚡ {score}/5</span>')

    # 테마 칩
    theme_html = ""
    if themes:
        chips = "".join(f'<span class="chip">{t}</span>' for t in themes[:3])
        theme_html = f'<div class="themes"><span class="label">테마</span>{chips}</div>'

    # 뉴스
    news_html = ""
    if news:
        items = []
        for n in news[:2]:
            items.append(
                f'<div class="news-item">'
                f'<span class="source">{n.get("source","")}</span>'
                f'<a href="{n.get("url","#")}" target="_blank">{n.get("title","")}</a>'
                f'</div>'
            )
        news_html = f'<div class="news">{"".join(items)}</div>'

    # 메타 라인 — 의미있는 값만
    meta_parts = [ticker]
    if value_eok > 0:
        meta_parts.append(f"대금 {value_eok:,.0f}억")
    if vol_ratio > 0:
        meta_parts.append(f"거래량 ×{vol_ratio:.1f}")
    if close_to_high > 0:
        meta_parts.append(f"종/고 {close_to_high:.3f}")
    meta_line = " · ".join(meta_parts)

    html = (
        f'<div class="stock-card">'
        f'<div class="rank{rank_cls}">{rank:02d}</div>'
        f'<div class="info">'
        f'<div class="name">{name}</div>'
        f'<div class="meta">{meta_line}</div>'
        f'<div class="badges">{"".join(badges)}</div>'
        f'{theme_html}{news_html}'
        f'</div>'
        f'<div class="stats">'
    )
    # 현재가가 있고 시그널일 종가와 다르면 현재가 메인 / 시그널일 작게
    if current_price > 0 and current_price != close:
        cur_cls = "up" if current_change_pct > 0 else "down"
        cur_sign = "+" if current_change_pct >= 0 else ""
        html += (
            f'<div class="price">{current_price:,}원</div>'
            f'<div class="change {cur_cls}">{cur_sign}{current_change_pct:.2f}%</div>'
            f'<div style="font-size:var(--fs-2xs);color:var(--fg-muted);margin-top:3px;">'
            f'시그널일 {close:,}원 · {"+" if ret_pct >= 0 else ""}{ret_pct:.2f}%</div>'
        )
    else:
        html += (
            f'<div class="price">{close:,}원</div>'
            f'<div class="change {change_cls}">{"+" if ret_pct >= 0 else ""}{ret_pct:.2f}%</div>'
        )
    html += '</div></div>'
    return html


def theme_card_html(rank: int, name: str, change_pct: float, top_name: str,
                     theme_url: str = "",
                     rise_count: int = 0, fall_count: int = 0,
                     total_count: int = 0,
                     strength=None) -> str:
    change_cls = "up" if change_pct > 0 else "down"
    sign = "+" if change_pct >= 0 else ""

    meta_parts = []
    if total_count > 0:
        meta_parts.append(f"↑{rise_count}/↓{fall_count} ({total_count})")
    if top_name:
        meta_parts.append(f"대장: {top_name}")
    meta_line = " · ".join(meta_parts)

    name_html = name
    if theme_url:
        name_html = f'<a href="{theme_url}" target="_blank">{name}</a>'

    return (
        f'<div class="theme-card">'
        f'<div class="rank">{rank:02d}</div>'
        f'<div class="body">'
        f'<div class="name">{name_html}</div>'
        f'<div class="meta">{meta_line}</div>'
        f'</div>'
        f'<div class="change {change_cls}">{sign}{change_pct:.2f}%</div>'
        f'</div>'
    )


def empty_state(icon: str, title: str, hint: str = ""):
    hint_html = f'<p>{hint}</p>' if hint else ""
    st.markdown(
        f'<div class="empty-state">'
        f'<div class="icon">{icon}</div>'
        f'<h3>{title}</h3>{hint_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def code(text: str):
    st.markdown(f'<span class="inline-code">{text}</span>', unsafe_allow_html=True)
