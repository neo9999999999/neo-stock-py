"""
Slash/Toss-inspired theme for Streamlit
=======================================
Pretendard font + clean grid + Bento cards + monospace emphasis.
"""

from __future__ import annotations

import streamlit as st


PALETTE_LIGHT = {
    "bg":           "#FFFFFF",
    "bg_alt":       "#F9FAFB",
    "bg_card":      "#FFFFFF",
    "border":       "#E5E8EB",
    "border_soft":  "#F2F4F6",
    "text":         "#191F28",
    "text_sub":     "#4E5968",
    "text_mute":    "#8B95A1",
    "accent":       "#3182F6",
    "accent_dark":  "#1B64DA",
    "success":      "#00C896",
    "danger":       "#F04452",
    "warning":      "#FF9F2E",
    "code_bg":      "#F2F4F6",
}

PALETTE_DARK = {
    "bg":           "#0B0E12",
    "bg_alt":       "#14181D",
    "bg_card":      "#1A1F26",
    "border":       "#2E3540",
    "border_soft":  "#232A33",
    "text":         "#F2F4F6",
    "text_sub":     "#B0B8C1",
    "text_mute":    "#6B7684",
    "accent":       "#4E8FF7",
    "accent_dark":  "#3182F6",
    "success":      "#1DD1A1",
    "danger":       "#FF6B7A",
    "warning":      "#FFB347",
    "code_bg":      "#232A33",
}

# 기본은 light. theme.py 임포트한 곳에서 PALETTE 참조 시 동적 변경.
PALETTE = PALETTE_LIGHT


CSS = """
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" rel="stylesheet" />
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />

<style>
:root {
    --bg: #FFFFFF;
    --bg-alt: #F9FAFB;
    --bg-card: #FFFFFF;
    --border: #E5E8EB;
    --border-soft: #F2F4F6;
    --text: #191F28;
    --text-sub: #4E5968;
    --text-mute: #8B95A1;
    --accent: #3182F6;
    --accent-dark: #1B64DA;
    --success: #00C896;
    --danger: #F04452;
    --warning: #FF9F2E;
    --code-bg: #F2F4F6;
    --radius-sm: 8px;
    --radius: 12px;
    --radius-lg: 16px;
    --radius-xl: 24px;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.06);
    --shadow-lg: 0 8px 24px rgba(0,0,0,0.08);
}

* { box-sizing: border-box; }

html, body, [class*="css"]  {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: var(--text);
    -webkit-font-smoothing: antialiased;
}

code, pre, .mono {
    font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace !important;
}

/* hide streamlit chrome but keep sidebar toggle visible */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stToolbar"] { z-index: 999; }
[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
}
/* keep the sidebar collapse/expand button visible */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[kind="header"] {
    visibility: visible !important;
    display: flex !important;
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    box-shadow: var(--shadow-sm) !important;
    color: var(--text) !important;
    width: 40px;
    height: 40px;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}

/* main container */
.main .block-container {
    padding: 2rem 3rem 4rem !important;
    max-width: 1400px !important;
}

/* st.columns gap fix — give breathing room between column cards */
[data-testid="stHorizontalBlock"] {
    gap: 1rem !important;
}
[data-testid="column"] {
    padding: 0 !important;
}

/* sidebar */
[data-testid="stSidebar"] {
    background: var(--bg-alt) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text); }
[data-testid="stSidebar"] .block-container {
    padding-top: 2rem;
}
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: var(--text) !important;
    border: 1px solid transparent !important;
    text-align: left !important;
    padding: 0.625rem 0.875rem !important;
    box-shadow: none !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #FFFFFF !important;
    border-color: var(--border) !important;
    transform: none !important;
    color: var(--accent) !important;
}

/* headings */
h1 {
    font-size: 2.25rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em;
    line-height: 1.2;
    color: var(--text);
    margin-bottom: 0.5rem !important;
}
h2 {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em;
    margin-top: 2rem !important;
}
h3 {
    font-size: 1.125rem !important;
    font-weight: 600 !important;
    color: var(--text-sub);
}

/* buttons — secondary는 가벼운 라이트 톤 */
.stButton > button {
    background: var(--bg-alt) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 0.5rem 1rem !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    transition: all 0.15s;
    box-shadow: none !important;
}
.stButton > button:hover {
    background: #FFFFFF !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    transform: none !important;
}
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: white !important;
    border-color: var(--accent) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--accent-dark) !important;
    color: white !important;
    border-color: var(--accent-dark) !important;
}

/* form submit */
.stFormSubmitButton > button {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius) !important;
    padding: 0.75rem 1.5rem !important;
    font-weight: 600 !important;
    width: 100%;
}

/* inputs — force light style regardless of OS theme */
.stTextInput input, .stNumberInput input, .stDateInput input,
.stTextArea textarea {
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--border) !important;
    background-color: #FFFFFF !important;
    color: var(--text) !important;
    padding: 0.625rem 0.875rem !important;
    font-family: 'Pretendard', sans-serif !important;
    caret-color: var(--accent);
}
.stTextInput input::placeholder,
.stNumberInput input::placeholder,
.stDateInput input::placeholder {
    color: var(--text-mute) !important;
    opacity: 1;
}
.stTextInput input:focus, .stNumberInput input:focus,
.stDateInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(49,130,246,0.12) !important;
    outline: none !important;
}

/* number input +/- step buttons */
.stNumberInput button {
    background: var(--bg-alt) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-left: none !important;
}
.stNumberInput button:hover {
    background: var(--border-soft) !important;
}
[data-testid="stNumberInputContainer"] {
    background: #FFFFFF !important;
    border-radius: var(--radius-sm);
}

/* selectbox / multiselect */
[data-baseweb="select"] > div {
    border-radius: var(--radius-sm) !important;
    border-color: var(--border) !important;
    background-color: #FFFFFF !important;
    color: var(--text) !important;
    min-height: 44px;
}
[data-baseweb="select"] [class*="placeholder"] { color: var(--text-mute) !important; }
[data-baseweb="select"] [class*="singleValue"] { color: var(--text) !important; }
[data-baseweb="popover"] { background: #FFFFFF !important; }
[data-baseweb="menu"] li { color: var(--text) !important; }
[data-baseweb="menu"] li:hover { background: var(--bg-alt) !important; }

/* date picker calendar (light default) */
[data-baseweb="calendar"], [data-baseweb="datepicker"] {
    background: #FFFFFF !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow-md) !important;
}
[data-baseweb="calendar"] * { color: var(--text); }
[data-baseweb="calendar"] [aria-selected="true"] {
    background: var(--accent) !important;
    color: white !important;
    border-radius: 999px !important;
}

/* label color for ALL form controls */
[data-testid="stWidgetLabel"],
.stTextInput label, .stNumberInput label, .stDateInput label,
.stSelectbox label, .stSlider label, .stRadio label {
    color: var(--text) !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
}

/* force light app background everywhere */
.stApp, .main, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
}
[data-testid="stHeader"] { background: transparent !important; }

/* slider */
.stSlider [data-baseweb="slider"] > div > div > div {
    background: var(--accent) !important;
}

/* dataframe */
.stDataFrame, [data-testid="stDataFrame"] {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    overflow: hidden;
}

/* radio */
.stRadio > div {
    gap: 0.5rem;
}

/* tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    border-bottom: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    padding: 0.625rem 1rem !important;
    font-weight: 600;
    color: var(--text-mute);
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
}

/* metric */
[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem;
    transition: all 0.2s;
}
[data-testid="stMetric"]:hover {
    border-color: var(--text-mute);
    box-shadow: var(--shadow-md);
}
[data-testid="stMetricLabel"] {
    font-size: 0.8125rem !important;
    color: var(--text-mute) !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
[data-testid="stMetricValue"] {
    font-size: 1.75rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
    color: var(--text) !important;
}

/* expander */
.streamlit-expanderHeader {
    background: var(--bg-alt) !important;
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--border) !important;
    font-weight: 600 !important;
}

/* alerts */
.stAlert {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    padding: 1rem 1.25rem !important;
}
.stAlert[data-baseweb="notification"] {
    background: var(--bg-alt) !important;
}

/* progress */
.stProgress > div > div > div {
    background: var(--accent) !important;
    border-radius: 999px;
}

/* radio horizontal style */
[data-testid="stRadio"] [role="radiogroup"] {
    flex-direction: column;
    gap: 4px;
}
[data-testid="stRadio"] [role="radiogroup"] > label {
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    background: transparent;
    transition: all 0.15s;
    font-weight: 500;
    color: var(--text-sub);
}
[data-testid="stRadio"] [role="radiogroup"] > label:hover {
    background: var(--border-soft);
}
[data-testid="stRadio"] [role="radiogroup"] > label[data-checked="true"] {
    background: var(--text);
    color: white;
}

/* plotly */
.js-plotly-plot {
    border-radius: var(--radius) !important;
}

/* help tooltip icon — light default */
[data-testid="stTooltipIcon"] svg,
[data-testid="tooltipHoverTarget"] svg {
    fill: var(--text-mute) !important;
    color: var(--text-mute) !important;
}
[data-testid="stTooltipIcon"]:hover svg { fill: var(--accent) !important; }
[role="tooltip"], [data-baseweb="tooltip"] {
    background: var(--text) !important;
    color: var(--bg) !important;
    border-radius: 8px !important;
    padding: 6px 10px !important;
}

/* form */
[data-testid="stForm"] {
    background: var(--bg-alt) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}

/* multiselect chips */
[data-baseweb="tag"] {
    background: var(--border-soft) !important;
    color: var(--text) !important;
    border-radius: 6px !important;
}

/* custom utility classes */
.brand-mark {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 800;
    font-size: 1.125rem;
    color: var(--text);
    text-decoration: none;
}
.brand-mark .dot {
    width: 8px;
    height: 8px;
    background: var(--accent);
    border-radius: 50%;
}

.tag {
    display: inline-block;
    padding: 0.25rem 0.625rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    background: var(--bg-alt);
    color: var(--text-sub);
    border: 1px solid var(--border);
}
.tag.accent { background: rgba(49,130,246,0.08); color: var(--accent); border-color: rgba(49,130,246,0.2); }
.tag.success { background: rgba(0,200,150,0.08); color: var(--success); border-color: rgba(0,200,150,0.2); }
.tag.danger { background: rgba(240,68,82,0.08); color: var(--danger); border-color: rgba(240,68,82,0.2); }
.tag.warning { background: rgba(255,159,46,0.08); color: var(--warning); border-color: rgba(255,159,46,0.2); }

.bento {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    transition: all 0.2s;
}
.bento:hover {
    border-color: var(--text-mute);
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}
.bento h4 {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
}
.bento .label {
    font-size: 0.75rem;
    color: var(--text-mute);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.25rem;
}
.bento .value {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--text);
}
.bento .value.success { color: var(--success); }
.bento .value.danger { color: var(--danger); }
.bento .sub {
    font-size: 0.8125rem;
    color: var(--text-mute);
    margin-top: 0.25rem;
}

.hero {
    padding: 2.5rem 0 1.5rem;
    border-bottom: 1px solid var(--border-soft);
    margin-bottom: 2rem;
}
.hero .eyebrow {
    color: var(--accent);
    font-weight: 700;
    font-size: 0.8125rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.5rem;
}
.hero h1 {
    margin: 0 0 0.75rem 0 !important;
}
.hero .lead {
    font-size: 1.0625rem;
    color: var(--text-sub);
    line-height: 1.6;
    max-width: 60ch;
}

.stock-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.75rem;
    transition: all 0.2s;
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    flex-wrap: nowrap;
}
.stock-card:hover {
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
}
.stock-card .rank {
    flex: 0 0 56px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-mute);
    line-height: 1.5;
}
.stock-card .rank.leader { color: var(--accent); }
.stock-card .info {
    flex: 1 1 auto;
    min-width: 0;
}
.stock-card .info .name {
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text);
    margin: 0 0 0.25rem 0;
}
.stock-card .info .meta {
    font-size: 0.8125rem;
    color: var(--text-mute);
    font-family: 'JetBrains Mono', monospace;
    word-break: break-all;
}
.stock-card .badges {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 8px;
}
.stock-card .themes {
    margin-top: 8px;
    font-size: 0.75rem;
    color: var(--text-sub);
}
.stock-card .themes .label {
    display: inline-block;
    color: var(--text-mute);
    margin-right: 6px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.stock-card .themes .chip {
    display: inline-block;
    padding: 2px 8px;
    margin-right: 4px;
    margin-bottom: 4px;
    background: rgba(49,130,246,0.08);
    color: var(--accent);
    border-radius: 999px;
    font-weight: 600;
}
.stock-card .news {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px dashed var(--border-soft);
}
.stock-card .news-item {
    font-size: 0.8125rem;
    color: var(--text-sub);
    line-height: 1.5;
    margin-bottom: 4px;
}
.stock-card .news-item .source {
    color: var(--text-mute);
    font-size: 0.6875rem;
    font-weight: 600;
    margin-right: 6px;
}
.stock-card .news-item a {
    color: var(--text-sub);
    text-decoration: none;
}
.stock-card .news-item a:hover { color: var(--accent); }

.stock-card .stats {
    flex: 0 0 auto;
    text-align: right;
    font-family: 'JetBrains Mono', monospace;
    min-width: 120px;
}
.stock-card .stats .price {
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text);
}
.stock-card .stats .change {
    font-size: 0.875rem;
    font-weight: 600;
    margin-top: 2px;
}
.stock-card .stats .change.up { color: var(--danger); }
.stock-card .stats .change.down { color: var(--accent); }

/* 테마 카드 (테마 분석 페이지용) */
.theme-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.75rem;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 1.25rem;
}
.theme-card:hover {
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}
.theme-card .rank {
    flex: 0 0 44px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-mute);
}
.theme-card .body {
    flex: 1 1 auto;
    min-width: 0;
}
.theme-card .name {
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 0.25rem;
}
.theme-card .leader {
    font-size: 0.875rem;
    color: var(--text-sub);
}
.theme-card .leader .label {
    color: var(--text-mute);
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-right: 6px;
}
.theme-card .change {
    flex: 0 0 auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.25rem;
    font-weight: 800;
    min-width: 80px;
    text-align: right;
}
.theme-card .change.up { color: var(--danger); }
.theme-card .change.down { color: var(--accent); }

.score-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-radius: 999px;
    background: var(--bg-alt);
    border: 1px solid var(--border);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
}
.score-pill.s5 { background: rgba(0,200,150,0.1); color: var(--success); border-color: transparent; }
.score-pill.s4 { background: rgba(255,159,46,0.1); color: var(--warning); border-color: transparent; }
.score-pill.s3 { background: var(--bg-alt); color: var(--text-sub); }

.code-snippet {
    background: var(--code-bg);
    border-radius: var(--radius-sm);
    padding: 0.75rem 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.875rem;
    color: var(--text);
    overflow-x: auto;
}

.divider {
    height: 1px;
    background: var(--border-soft);
    margin: 2rem 0;
}

.section-title {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin: 2rem 0 1rem;
}
.section-title h2 {
    margin: 0 !important;
}
.section-title .count {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1rem;
    color: var(--text-mute);
    font-weight: 600;
}

.empty-state {
    text-align: center;
    padding: 4rem 2rem;
    background: var(--bg-alt);
    border-radius: var(--radius-lg);
    border: 1px dashed var(--border);
}
.empty-state .icon { font-size: 2.5rem; margin-bottom: 1rem; }
.empty-state h3 { color: var(--text); margin: 0 0 0.5rem 0; }
.empty-state p { color: var(--text-sub); margin: 0; }
</style>
"""


DARK_OVERRIDE = """
<style>
/* override CSS variables */
:root, html, body {
    --bg: #0B0E12 !important;
    --bg-alt: #14181D !important;
    --bg-card: #1A1F26 !important;
    --border: #2E3540 !important;
    --border-soft: #232A33 !important;
    --text: #F2F4F6 !important;
    --text-sub: #B0B8C1 !important;
    --text-mute: #6B7684 !important;
    --accent: #4E8FF7 !important;
    --accent-dark: #3182F6 !important;
    --success: #1DD1A1 !important;
    --danger: #FF6B7A !important;
    --warning: #FFB347 !important;
    --code-bg: #232A33 !important;
}

/* base layers */
.stApp, .main, [data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background-color: #0B0E12 !important;
    color: #F2F4F6 !important;
}
body { background-color: #0B0E12 !important; color: #F2F4F6 !important; }

/* text */
h1, h2, h3, h4, h5, h6, p, span, div, label, li, a {
    color: #F2F4F6;
}
.hero .lead, .meta, .empty-state p, .stCaption,
[data-testid="stCaptionContainer"] { color: #B0B8C1 !important; }

/* sidebar */
[data-testid="stSidebar"] {
    background: #14181D !important;
    border-right-color: #2E3540 !important;
}
[data-testid="stSidebar"] * { color: #F2F4F6 !important; }
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #F2F4F6 !important;
    border-color: transparent !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #1A1F26 !important;
    color: #4E8FF7 !important;
    border-color: #2E3540 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #4E8FF7 !important;
    color: #0B0E12 !important;
}

/* inputs — text fields */
.stTextInput input, .stNumberInput input, .stDateInput input,
.stTextArea textarea,
input[type="text"], input[type="number"], input[type="date"] {
    background-color: #1A1F26 !important;
    color: #F2F4F6 !important;
    border-color: #2E3540 !important;
}
.stTextInput input::placeholder,
.stNumberInput input::placeholder,
.stDateInput input::placeholder { color: #6B7684 !important; }
[data-testid="stNumberInputContainer"] { background: #1A1F26 !important; }
.stNumberInput button {
    background: #232A33 !important;
    color: #F2F4F6 !important;
    border-color: #2E3540 !important;
}
.stNumberInput button:hover { background: #2E3540 !important; }

/* selectbox/multiselect (BaseWeb) */
[data-baseweb="select"] > div {
    background-color: #1A1F26 !important;
    border-color: #2E3540 !important;
    color: #F2F4F6 !important;
}
[data-baseweb="select"] [class*="placeholder"] { color: #6B7684 !important; }
[data-baseweb="select"] [class*="singleValue"],
[data-baseweb="select"] [class*="ValueContainer"] { color: #F2F4F6 !important; }
[data-baseweb="select"] svg { fill: #B0B8C1 !important; }

/* dropdown options popover */
[data-baseweb="popover"], [data-baseweb="popover"] > div {
    background: #1A1F26 !important;
}
[data-baseweb="menu"], [data-baseweb="menu"] ul {
    background: #1A1F26 !important;
}
[data-baseweb="menu"] li,
[role="option"] {
    background: #1A1F26 !important;
    color: #F2F4F6 !important;
}
[data-baseweb="menu"] li:hover,
[role="option"]:hover,
[role="option"][aria-selected="true"] {
    background: #232A33 !important;
}

/* datepicker calendar — strong dark override */
[data-baseweb="calendar"],
[data-baseweb="calendar"] > *,
[data-baseweb="datepicker"],
[data-baseweb="datepicker"] > *,
[role="dialog"][aria-label*="alendar"],
[data-baseweb="popover"] [data-baseweb="calendar"] {
    background: #1A1F26 !important;
    color: #F2F4F6 !important;
    border-color: #2E3540 !important;
}
[data-baseweb="calendar"] *,
[data-baseweb="datepicker"] * {
    color: #F2F4F6 !important;
    background-color: transparent !important;
}
[data-baseweb="calendar"] button {
    background: transparent !important;
    border-color: #2E3540 !important;
}
[data-baseweb="calendar"] button:hover {
    background: #232A33 !important;
}
[data-baseweb="calendar"] [aria-selected="true"],
[role="gridcell"][aria-selected="true"] > div {
    background: #4E8FF7 !important;
    color: #0B0E12 !important;
    border-radius: 999px !important;
}
[data-baseweb="calendar"] [aria-disabled="true"] {
    color: #4E5968 !important;
}
/* month/year select inside calendar header */
[data-baseweb="calendar"] [data-baseweb="select"] > div {
    background: #232A33 !important;
    color: #F2F4F6 !important;
}
/* calendar header bg fix (was white in user screenshot) */
[data-baseweb="calendar"] [class*="MonthHeader"],
[data-baseweb="calendar"] [class*="WeekdayHeader"],
[data-baseweb="calendar"] [class*="Day"] {
    background: #1A1F26 !important;
    color: #F2F4F6 !important;
}

/* checkbox / toggle */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] *,
[data-baseweb="checkbox"] *,
[data-testid="stToggle"] label,
[data-testid="stToggle"] * { color: #F2F4F6 !important; }

/* labels */
[data-testid="stWidgetLabel"],
.stTextInput label, .stNumberInput label, .stDateInput label,
.stSelectbox label, .stSlider label, .stRadio label,
.stCheckbox label, .stToggle label,
.stForm label, label { color: #F2F4F6 !important; }

/* radio buttons in dark */
[data-testid="stRadio"] [role="radiogroup"] > label { color: #F2F4F6 !important; }
[data-testid="stRadio"] [role="radiogroup"] > label:hover { background: #1A1F26 !important; }
[data-testid="stRadio"] [role="radiogroup"] > label[data-checked="true"] {
    background: #F2F4F6 !important;
    color: #0B0E12 !important;
}

/* slider */
.stSlider [data-baseweb="slider"] > div > div > div { background: #4E8FF7 !important; }

/* metric & bento */
[data-testid="stMetric"] {
    background: #1A1F26 !important;
    border-color: #2E3540 !important;
}
[data-testid="stMetricLabel"] { color: #6B7684 !important; }
[data-testid="stMetricValue"] { color: #F2F4F6 !important; }
[data-testid="stMetricDelta"] { color: #B0B8C1 !important; }
.bento {
    background: #1A1F26 !important;
    border-color: #2E3540 !important;
}
.bento h4, .bento .value { color: #F2F4F6 !important; }
.bento .label, .bento .sub { color: #6B7684 !important; }

/* cards */
.stock-card, .theme-card {
    background: #1A1F26 !important;
    border-color: #2E3540 !important;
}
.stock-card .info .name,
.theme-card .name { color: #F2F4F6 !important; }
.stock-card .info .meta,
.stock-card .themes,
.stock-card .news-item,
.stock-card .news-item a,
.theme-card .leader { color: #B0B8C1 !important; }
.stock-card .rank,
.theme-card .rank { color: #B0B8C1 !important; }
.stock-card .rank.leader { color: #4E8FF7 !important; }
.stock-card .themes .label,
.theme-card .leader .label { color: #6B7684 !important; }
.stock-card .themes .chip {
    background: rgba(78,143,247,0.15) !important;
    color: #6BA5FF !important;
}
.stock-card .news-item .source { color: #6B7684 !important; }

/* tags */
.tag {
    background: #232A33 !important;
    color: #B0B8C1 !important;
    border-color: #2E3540 !important;
}

/* code & snippet */
code, .code-snippet, pre {
    background: #232A33 !important;
    color: #F2F4F6 !important;
}

/* brand */
.brand-mark { color: #F2F4F6 !important; }

/* buttons — secondary readable in dark */
.stButton > button {
    background: #232A33 !important;
    color: #F2F4F6 !important;
    border: 1px solid #2E3540 !important;
    box-shadow: none !important;
}
.stButton > button:hover {
    background: #2E3540 !important;
    border-color: #4E8FF7 !important;
    color: #4E8FF7 !important;
    transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    background: #4E8FF7 !important;
    color: #0B0E12 !important;
    border: none !important;
}
.stButton > button[kind="primary"]:hover {
    background: #6BA5FF !important;
    color: #0B0E12 !important;
}
.stFormSubmitButton > button {
    background: #4E8FF7 !important;
    color: #0B0E12 !important;
    border: none !important;
}
.stFormSubmitButton > button:hover {
    background: #6BA5FF !important;
}
[data-testid="stDownloadButton"] button {
    background: #232A33 !important;
    color: #F2F4F6 !important;
    border: 1px solid #2E3540 !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: #2E3540 !important;
    color: #4E8FF7 !important;
    border-color: #4E8FF7 !important;
}

/* tabs */
.stTabs [data-baseweb="tab-list"] { border-bottom-color: #2E3540 !important; }
.stTabs [data-baseweb="tab"] { color: #6B7684 !important; }
.stTabs [aria-selected="true"] {
    color: #4E8FF7 !important;
    border-bottom-color: #4E8FF7 !important;
}

/* alerts */
.stAlert {
    background: #14181D !important;
    border-color: #2E3540 !important;
    color: #F2F4F6 !important;
}

/* expander */
.streamlit-expanderHeader,
[data-testid="stExpander"] details summary {
    background: #14181D !important;
    border-color: #2E3540 !important;
    color: #F2F4F6 !important;
}

/* empty state */
.empty-state {
    background: #14181D !important;
    border-color: #2E3540 !important;
}
.empty-state h3 { color: #F2F4F6 !important; }
.empty-state p { color: #B0B8C1 !important; }

/* DataFrame — most important fix */
.stDataFrame, [data-testid="stDataFrame"],
[data-testid="stDataFrame"] > div,
.stDataFrame iframe {
    background: #1A1F26 !important;
    border-color: #2E3540 !important;
}
[data-testid="stDataFrame"] table { background: #1A1F26 !important; }
[data-testid="stDataFrame"] thead tr,
[data-testid="stDataFrame"] thead tr th {
    background: #232A33 !important;
    color: #F2F4F6 !important;
    border-color: #2E3540 !important;
}
[data-testid="stDataFrame"] tbody tr td,
[data-testid="stDataFrame"] tbody tr th {
    background: #1A1F26 !important;
    color: #F2F4F6 !important;
    border-color: #232A33 !important;
}
[data-testid="stDataFrame"] tbody tr:hover td {
    background: #232A33 !important;
}

/* divider */
.divider { background: #232A33 !important; }

/* progress */
.stProgress > div > div > div { background: #4E8FF7 !important; }
.stProgress { background: #14181D !important; }

/* sidebar collapse button */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[kind="header"] {
    background: #1A1F26 !important;
    border-color: #2E3540 !important;
    color: #F2F4F6 !important;
}

/* help tooltip "?" icon */
[data-testid="stTooltipIcon"] svg,
[data-testid="tooltipHoverTarget"] svg,
[data-testid="stWidgetLabel"] svg {
    fill: #6B7684 !important;
    color: #6B7684 !important;
}
[data-testid="stTooltipIcon"]:hover svg { fill: #4E8FF7 !important; }

/* tooltip content */
[role="tooltip"], [data-baseweb="tooltip"] {
    background: #232A33 !important;
    color: #F2F4F6 !important;
    border: 1px solid #2E3540 !important;
}

/* spinner */
.stSpinner > div { color: #4E8FF7 !important; }

/* table styler inline (gradient/highlight) safety */
[data-testid="stDataFrame"] [data-baseweb="table"] {
    background: #1A1F26 !important;
}

/* form border */
[data-testid="stForm"] {
    background: transparent !important;
    border: 1px solid #2E3540 !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}

/* multiselect chips */
[data-baseweb="tag"] {
    background: #2E3540 !important;
    color: #F2F4F6 !important;
}

/* number input value text — extra safety */
[data-testid="stNumberInput"] input,
[data-testid="stNumberInput"] [data-baseweb="input"] input {
    color: #F2F4F6 !important;
    background: #1A1F26 !important;
}

/* selectbox displayed value */
[data-baseweb="select"] [class*="ValueContainer"] *,
[data-baseweb="select"] [class*="Selection"] * {
    color: #F2F4F6 !important;
}
</style>
"""


def inject_css(theme: str = "light"):
    """Streamlit 페이지 상단에서 호출. CSS 주입.
    theme: 'light' | 'dark'
    """
    global PALETTE
    PALETTE = PALETTE_DARK if theme == "dark" else PALETTE_LIGHT
    st.markdown(CSS, unsafe_allow_html=True)
    if theme == "dark":
        st.markdown(DARK_OVERRIDE, unsafe_allow_html=True)


def current_palette():
    return PALETTE


def hero(eyebrow: str, title: str, lead: str = ""):
    """페이지 상단 hero 섹션."""
    html = f"""
    <div class="hero">
        <div class="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {f'<p class="lead">{lead}</p>' if lead else ''}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def section_title(title: str, count: str | int = None):
    cnt = f'<span class="count">({count})</span>' if count is not None else ''
    st.markdown(
        f'<div class="section-title"><h2>{title}</h2>{cnt}</div>',
        unsafe_allow_html=True,
    )


def bento(label: str, value: str, sub: str = "", tone: str = ""):
    """Bento 스타일 KPI 카드. tone: 'success' | 'danger' | ''."""
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
    # rank_label 우선 (테마 내 순위: 대장주/2등주/3등주/개별주)
    # _badge_override 변수가 themes 인자에 [TAG]로 전달되면 사용
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

    # 메타 라인은 의미있는 값만 표시
    meta_parts = [ticker]
    if value_eok > 0:
        meta_parts.append(f"대금 {value_eok:,.0f}억")
    if vol_ratio > 0:
        meta_parts.append(f"거래량 ×{vol_ratio:.1f}")
    if close_to_high > 0:
        meta_parts.append(f"종/고 {close_to_high:.3f}")
    meta_line = " · ".join(meta_parts)

    # 줄바꿈/들여쓰기 제거 — Streamlit 마크다운 파서가 4스페이스를 코드블록으로 인식하는 문제 회피
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
    # 현재가가 있으면 메인으로 표시, 시그널일 종가는 작게
    if current_price > 0 and current_price != close:
        cur_cls = "up" if current_change_pct > 0 else "down"
        cur_sign = "+" if current_change_pct >= 0 else ""
        html += (
            f'<div class="price">{current_price:,}원</div>'
            f'<div class="change {cur_cls}">{cur_sign}{current_change_pct:.2f}%</div>'
            f'<div style="font-size:0.7rem;color:#8B95A1;margin-top:0.25rem;">'
            f'시그널일 {close:,}원 · {"+" if ret_pct >= 0 else ""}{ret_pct:.2f}%</div>'
        )
    else:
        html += (
            f'<div class="price">{close:,}원</div>'
            f'<div class="change {change_cls}">{"+" if ret_pct >= 0 else ""}{ret_pct:.2f}%</div>'
        )
    html += (
        f'</div>'
        f'</div>'
    )
    return html


def theme_card_html(rank: int, name: str, change_pct: float, top_name: str,
                     theme_url: str = "",
                     rise_count: int = 0, fall_count: int = 0,
                     total_count: int = 0,
                     strength=None) -> str:
    change_cls = "up" if change_pct > 0 else "down"
    sign = "+" if change_pct >= 0 else ""

    # 상승 비율 막대
    if total_count > 0:
        rise_ratio = rise_count / total_count
        ratio_pct = int(rise_ratio * 100)
    else:
        rise_ratio = 0
        ratio_pct = 0

    # 강도 점수 배지 (선택적)
    strength_html = ""
    if strength is not None:
        s_color = "#F04452" if strength >= 1.5 else ("#FF9F2E" if strength >= 0.5 else "#8B95A1")
        strength_html = (
            f'<span style="display:inline-block;padding:2px 8px;margin-right:6px;'
            f'background:rgba(240,68,82,0.08);color:{s_color};'
            f'border-radius:999px;font-size:0.75rem;font-weight:700;">'
            f'⚡ 강도 {strength:.2f}</span>'
        )

    # 상승/하락 칩
    breadth_html = (
        f'<span style="display:inline-block;padding:2px 8px;margin-right:6px;'
        f'background:rgba(240,68,82,0.08);color:#F04452;border-radius:999px;'
        f'font-size:0.75rem;font-weight:700;">↑ {rise_count}</span>'
        f'<span style="display:inline-block;padding:2px 8px;margin-right:6px;'
        f'background:rgba(49,130,246,0.08);color:#3182F6;border-radius:999px;'
        f'font-size:0.75rem;font-weight:700;">↓ {fall_count}</span>'
    )

    # 상승률 막대 (시각적)
    bar_html = (
        f'<div style="height:4px;background:rgba(49,130,246,0.15);border-radius:2px;'
        f'overflow:hidden;margin-top:4px;width:100%;">'
        f'<div style="height:100%;width:{ratio_pct}%;background:#F04452;"></div>'
        f'</div>'
        f'<div style="font-size:0.7rem;color:#8B95A1;margin-top:2px;">'
        f'테마 내 상승률 {ratio_pct}%</div>'
    )

    return (
        f'<a href="{theme_url}" target="_blank" style="text-decoration:none;color:inherit;">'
        f'<div class="theme-card" style="display:block;padding:1rem 1.25rem;">'
        f'<div style="display:flex;align-items:center;gap:1rem;">'
        f'<div class="rank">{rank:02d}</div>'
        f'<div style="flex:1;min-width:0;">'
        f'<div class="name">{name}</div>'
        f'<div style="margin-top:6px;">{strength_html}{breadth_html}</div>'
        f'<div class="leader" style="margin-top:4px;"><span class="label">대표</span>{top_name or "—"}</div>'
        f'</div>'
        f'<div class="change {change_cls}" style="font-size:1.5rem;">{sign}{change_pct:.2f}%</div>'
        f'</div>'
        f'{bar_html}'
        f'</div></a>'
    )


def _theme_card_html_unused(rank: int, name: str, change_pct: float, top_name: str,
                              theme_url: str = "") -> str:
    """deprecated — kept to avoid editing risk."""
    change_cls = "up" if change_pct > 0 else "down"
    return f"""
    <a href="{theme_url}" target="_blank" style="text-decoration:none;color:inherit;">
        <div class="theme-card">
            <div class="rank">{rank:02d}</div>
            <div class="body">
                <div class="name">{name}</div>
                <div class="leader"><span class="label">대표</span>{top_name or '—'}</div>
            </div>
            <div class="change {change_cls}">{'+' if change_pct >= 0 else ''}{change_pct:.2f}%</div>
        </div>
    </a>
    """


def empty_state(icon: str, title: str, hint: str = ""):
    st.markdown(
        f'<div class="empty-state"><div class="icon">{icon}</div>'
        f'<h3>{title}</h3>{f"<p>{hint}</p>" if hint else ""}</div>',
        unsafe_allow_html=True,
    )


def code(text: str):
    st.markdown(f'<div class="code-snippet">{text}</div>', unsafe_allow_html=True)
