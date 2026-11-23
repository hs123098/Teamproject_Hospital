"""
MediNow · 실시간 병원·응급실·약국 조회 시스템
Streamlit + Supabase (URL + anon key)
"""
import html
import re
from datetime import datetime, time
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from supabase import create_client

BRAND = "MediNow"
KST = ZoneInfo("Asia/Seoul")
STALE_MIN = 60          # 병상 정보가 이 시간(분) 이상 갱신 안 되면 경고
BED_BAR_MAX = 12        # 병상 막대그래프 100% 기준

st.set_page_config(
    page_title=f"{BRAND} · 병원·응급실·약국 찾기",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =====================================================================
# 스타일
# =====================================================================
CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

:root { color-scheme: light; --blue:#0f5fc2; --blue-d:#0a3f8f; --blue-l:#eaf3ff; --teal:#0aa5a0;
  --ink:#14213d; --sub:#4a5a73; --mute:#66758c; --line:#dde5ef; }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  color-scheme: light; background:#f4f7fb !important; color:var(--ink); }
.stApp { font-family:'Pretendard',-apple-system,'Noto Sans KR','Malgun Gothic',sans-serif; -webkit-font-smoothing:antialiased; }
.stApp, .stMarkdown, .stApp p, .stApp label, .stApp button, .stApp input, .stApp textarea, .stApp h1, .stApp h2, .stApp h3 {
  font-family:'Pretendard',-apple-system,'Noto Sans KR','Malgun Gothic',sans-serif; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], header[data-testid="stHeader"] { display:none !important; }
.block-container { max-width:1180px; padding:0 1rem 4rem; }

[data-testid="stMarkdownContainer"] p { color:var(--ink); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:var(--sub) !important; font-size:.86rem; }
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p, .stApp label, .stApp label p { color:#2b3a55 !important; font-weight:600; }
.stApp [data-testid="stToggle"] p, .stApp [data-testid="stToggle"] label { color:#2b3a55 !important; font-weight:600; }

/* ---------- 상단 안내줄 + 헤더 ---------- */
.topbar { background:var(--blue-d); color:#fff; font-size:.8rem; padding:8px 18px; display:flex; justify-content:space-between;
  gap:10px; flex-wrap:wrap; margin:0 -1rem; }
.topbar b { color:#ffd166; }
.topbar a { color:#fff !important; text-decoration:none !important; margin-left:16px; opacity:.92; }
.topbar a:hover { text-decoration:underline !important; opacity:1; }
.gnb { background:#fff; border-bottom:1px solid var(--line); margin:0 -1rem 18px; padding:14px 18px; display:flex;
  align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.logo { display:flex; align-items:center; gap:10px; font-weight:800; font-size:1.3rem; color:var(--blue-d); letter-spacing:-.5px; }
.logo .mk { width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,var(--blue),var(--teal));
  color:#fff; display:flex; align-items:center; justify-content:center; font-size:1.2rem; font-weight:800; }
.logo small { display:block; font-size:.68rem; font-weight:600; color:var(--mute); letter-spacing:0; margin-top:-2px; }
.live { display:inline-flex; align-items:center; gap:8px; background:#ecfdf3; color:#067647; padding:6px 14px;
  border-radius:999px; font-size:.8rem; font-weight:700; border:1px solid #abefc6; }
.live i { width:8px; height:8px; border-radius:50%; background:#12b76a; animation:pulse 1.8s infinite; }
@keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(18,183,106,.6)} 70%{box-shadow:0 0 0 9px rgba(18,183,106,0)} 100%{box-shadow:0 0 0 0 rgba(18,183,106,0)} }

/* ---------- Hero ---------- */
.hero { background:linear-gradient(120deg,#e6f1ff 0%,#f2f9ff 55%,#e3f7f5 100%); border:1px solid var(--line);
  border-radius:20px; padding:30px 32px; margin-bottom:16px; }
.hero-in { display:grid; grid-template-columns:1.5fr 1fr; gap:24px; align-items:center; }
.eyebrow { display:inline-block; font-size:.78rem; font-weight:700; color:var(--blue); background:#fff; border:1px solid #c9dcf5;
  padding:5px 12px; border-radius:999px; margin-bottom:14px; }
.hero .h1 { font-size:2.05rem; line-height:1.3; font-weight:800; letter-spacing:-.8px; margin:0 0 10px; color:var(--blue-d); }
.hero .sub { color:var(--sub); font-size:1rem; margin:0 0 20px; line-height:1.6; }
.hero-actions { display:flex; flex-wrap:wrap; gap:10px; }
.btn { display:inline-flex; align-items:center; gap:7px; padding:12px 20px; border-radius:12px; font-weight:700; font-size:.93rem;
  text-decoration:none !important; transition:transform .12s ease; }
.btn:hover { transform:translateY(-1px); }
.btn-red { background:#e5383b; color:#fff !important; box-shadow:0 6px 14px rgba(229,56,59,.3); }
.btn-ghost { background:#fff; color:var(--blue-d) !important; border:1px solid #c9dcf5; }
.stat-card { background:#fff; border:1px solid var(--line); border-radius:16px; padding:20px 22px; box-shadow:0 8px 24px rgba(15,95,194,.10); }
.stat-card .t { font-size:.82rem; font-weight:700; color:var(--sub); }
.stat-card .big { font-size:2.8rem; font-weight:800; color:var(--blue); letter-spacing:-1.5px; line-height:1.15; }
.stat-card .big small { font-size:1rem; color:var(--mute); font-weight:600; letter-spacing:0; }
.stat-card .d { font-size:.84rem; color:var(--sub); border-top:1px dashed var(--line); margin-top:10px; padding-top:10px; }
.stat-card .d b { color:var(--ink); }

/* ---------- KPI ---------- */
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:0 0 18px; }
.kpi { background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px 16px 12px; position:relative; }
.kpi:before { content:""; position:absolute; left:0; top:14px; bottom:14px; width:4px; border-radius:0 4px 4px 0; background:#b6c2d4; }
.kpi.green:before { background:#12b76a; } .kpi.red:before { background:#e5383b; } .kpi.blue:before { background:var(--blue); }
.kpi .kl { font-size:.8rem; color:var(--sub); font-weight:700; }
.kpi .kv { font-size:1.75rem; font-weight:800; color:var(--ink); letter-spacing:-.6px; line-height:1.25; }
.kpi .kv small { font-size:.88rem; color:var(--mute); font-weight:600; letter-spacing:0; }
.kpi .ks { font-size:.76rem; color:var(--mute); }
.kpi.red .kv { color:#c92a2d; } .kpi.green .kv { color:#039855; } .kpi.blue .kv { color:var(--blue); }

/* ---------- Tabs (병원 사이트 메뉴 스타일) ---------- */
.stTabs [data-baseweb="tab-list"] { gap:2px; background:#fff !important; padding:0 8px; border-radius:14px 14px 0 0; margin-bottom:14px;
  overflow-x:auto; border:1px solid var(--line) !important; }
.stTabs [data-baseweb="tab"] { height:52px; padding:0 18px; background:transparent !important; white-space:nowrap; color:var(--sub) !important; border-radius:0; }
.stTabs [data-baseweb="tab"] p { color:inherit !important; font-weight:700; font-size:.96rem; }
.stTabs [data-baseweb="tab"]:hover { color:var(--blue) !important; background:#f4f8ff !important; }
.stTabs [aria-selected="true"] { color:var(--blue) !important; box-shadow:inset 0 -3px 0 var(--blue); }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none !important; height:0 !important; background:transparent !important; }

/* ---------- 필터 패널 ---------- */
div[class*="st-key-panel"] { background:#fff; border:1px solid var(--line); border-radius:16px; padding:16px 18px 10px; margin-bottom:14px; }
.flabel { font-size:.8rem; font-weight:700; color:var(--sub); margin:2px 0 6px; }

[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"], button[kind="pills"], button[kind="pillsActive"] {
  border-radius:999px !important; padding:6px 16px !important; transition:all .12s ease; }
[data-testid="stBaseButton-pills"], button[kind="pills"] { background:#fff !important; color:#2b3a55 !important; border:1px solid #c7d2e2 !important; }
[data-testid="stBaseButton-pills"] *, button[kind="pills"] * { color:#2b3a55 !important; font-weight:700 !important; }
[data-testid="stBaseButton-pills"]:hover, button[kind="pills"]:hover { background:var(--blue-l) !important; border-color:var(--blue) !important; }
[data-testid="stBaseButton-pillsActive"], button[kind="pillsActive"] { background:var(--blue) !important; border:1px solid var(--blue) !important; }
[data-testid="stBaseButton-pillsActive"] *, button[kind="pillsActive"] * { color:#fff !important; font-weight:700 !important; }

.stButton > button { border-radius:10px; font-weight:700; border:1px solid #c7d2e2; background:#fff !important; color:#2b3a55 !important; }
.stButton > button p { color:inherit !important; }
.stButton > button:hover { border-color:var(--blue); color:var(--blue) !important; background:var(--blue-l) !important; }

[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div { background:#fff !important; border-color:#c7d2e2 !important; border-radius:10px !important; }
.stTextInput input, .stNumberInput input { background:#fff !important; color:var(--ink) !important; -webkit-text-fill-color:var(--ink); }
input::placeholder { color:#8a97ab !important; opacity:1; -webkit-text-fill-color:#8a97ab; }
[data-baseweb="select"] * { color:var(--ink); }
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] ul, [data-baseweb="popover"] li { background:#fff !important; color:var(--ink) !important; }
[data-baseweb="popover"] li:hover { background:var(--blue-l) !important; }
[data-testid="stExpander"] { background:#fff; border:1px solid var(--line) !important; border-radius:14px; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p { color:var(--ink) !important; font-weight:700; }
div[role="dialog"] { background:#fff !important; color:var(--ink); border-radius:18px !important; }
div[role="dialog"] h2, div[role="dialog"] p { color:var(--ink); }

/* ---------- 카드 ---------- */
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; margin:6px 0 18px; }
.card, div[class*="st-key-hc_"] { background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px 18px 16px;
  box-shadow:0 1px 3px rgba(20,33,61,.05); transition:transform .15s ease, box-shadow .15s ease, border-color .15s ease; }
.card:hover, div[class*="st-key-hc_"]:hover { transform:translateY(-3px); box-shadow:0 14px 30px rgba(15,95,194,.14); border-color:#b9d0ef; }
.card.lv-ok { border-top:4px solid #12b76a; } .card.lv-low { border-top:4px solid #f79009; } .card.lv-full { border-top:4px solid #e5383b; }
.c-head { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.c-name { font-weight:800; font-size:1.06rem; color:var(--ink); letter-spacing:-.3px; line-height:1.3; }
.c-sub { font-size:.82rem; color:var(--sub); margin-top:3px; }
.pill { display:inline-flex; align-items:center; gap:6px; font-size:.75rem; font-weight:700; padding:5px 11px; border-radius:999px; white-space:nowrap; }
.pill i { width:7px; height:7px; border-radius:50%; background:currentColor; }
.p-ok { background:#ecfdf3; color:#067647; } .p-ok i { animation:blink 1.6s infinite; }
.p-low { background:#fffaeb; color:#b54708; } .p-full { background:#fef3f2; color:#b42318; }
.p-off { background:#f2f4f7; color:#475467; } .p-blue { background:var(--blue-l); color:var(--blue); }
@keyframes blink { 50% { opacity:.25 } }
.beds { display:flex; align-items:center; gap:14px; margin:14px 0 8px; }
.beds .n { font-size:2.4rem; font-weight:800; line-height:1; letter-spacing:-1px; min-width:58px; font-variant-numeric:tabular-nums; }
.n-ok { color:#039855; } .n-low { color:#dc6803; } .n-full { color:#d92d20; }
.beds .bw { flex:1; }
.beds .l { font-size:.76rem; color:var(--sub); font-weight:700; margin-bottom:6px; }
.bar { height:9px; background:#e7ecf3; border-radius:99px; overflow:hidden; }
.bar span { display:block; height:100%; border-radius:99px; }
.f-ok { background:#12b76a; } .f-low { background:#f79009; } .f-full { background:#e5383b; }
.meta { font-size:.86rem; color:#2b3a55; margin:6px 0; line-height:1.55; }
.chips { display:flex; flex-wrap:wrap; gap:5px; margin:9px 0 4px; }
.chip { font-size:.75rem; font-weight:600; padding:4px 10px; border-radius:8px; background:#eef2f7; color:#2b3a55; }
.chip.hl { background:var(--blue-l); color:var(--blue); } .chip.am { background:#fffaeb; color:#b54708; }
.acts { display:flex; gap:8px; margin-top:14px; }
.act { flex:1; text-align:center; padding:11px 0; border-radius:10px; font-size:.86rem; font-weight:700; text-decoration:none !important;
  background:#eef2f7; color:#2b3a55 !important; transition:filter .12s ease; }
.act:hover { filter:brightness(.95); }
.act.p { background:var(--blue); color:#fff !important; } .act.r { background:#e5383b; color:#fff !important; }
.act.off { background:#eef2f7; color:var(--mute) !important; }
.foot { font-size:.75rem; color:var(--mute); margin-top:10px; }
.stale { color:#b54708; font-weight:700; }
.sec { font-weight:800; font-size:1.1rem; margin:14px 0 6px; color:var(--ink); letter-spacing:-.3px; }
.count { font-size:.92rem; color:var(--sub); margin:4px 0 6px; } .count b { color:var(--ink); }
.empty { text-align:center; padding:46px 10px; background:#fff; border:1px dashed #c7d2e2; border-radius:16px; color:var(--sub); }
.empty b { color:var(--ink); } .empty .ei { font-size:2rem; }
.dl { display:grid; grid-template-columns:90px 1fr; gap:9px 12px; font-size:.92rem; margin:6px 0 12px; }
.dl .k { color:var(--sub); font-weight:600; } .dl .v { color:var(--ink); }
.box { background:#f8fafc; border:1px solid var(--line); border-radius:14px; padding:14px 16px; }
.box .meta, .box .foot { color:#2b3a55; }
.disc { font-size:.78rem; color:var(--mute); text-align:center; margin-top:26px; line-height:1.6; padding-top:18px; border-top:1px solid var(--line); }

@media (max-width: 760px) {
  .hero-in { grid-template-columns:1fr; } .hero { padding:22px 18px; } .hero .h1 { font-size:1.55rem; }
  .block-container { padding:0 .6rem 3rem; } .topbar, .gnb { margin:0 -.6rem; }
  .kpi .kv { font-size:1.4rem; } .stTabs [data-baseweb="tab"] { padding:0 12px; }
}
@media (prefers-reduced-motion: reduce) { .card, .btn, .act, .live i, .p-ok i { transition:none !important; animation:none !important; } }
</style>
"""

# =====================================================================
# Supabase 연결 / 데이터 로드
# =====================================================================
@st.cache_resource
def client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


@st.cache_data(ttl=20, show_spinner=False)
def fetch(table: str) -> list:
    """뷰/테이블 전체 조회 (20초 캐시 → 병상 변동이 거의 실시간 반영)"""
    return client().table(table).select("*").execute().data or []


def to_time(s):
    if not s:
        return None
    p = str(s).split(":")
    return time(int(p[0]), int(p[1]))


def to_dt(s):
    if not s:
        return None
    return pd.to_datetime(s, utc=True).tz_convert(KST).to_pydatetime()


def er_data() -> list:
    rows = fetch("v_er_status")
    for r in rows:
        r["update_time"] = to_dt(r.get("update_time"))
        r["available_beds"] = int(r.get("available_beds") or 0)
    return rows


def hospital_data() -> list:
    rows = fetch("v_hospital_full")
    for r in rows:
        r["open_time"] = to_time(r.get("open_time"))
        r["close_time"] = to_time(r.get("close_time"))
        r["update_time"] = to_dt(r.get("update_time"))
        r["available_beds"] = int(r.get("available_beds") or 0)
        r["dept_list"] = r.get("dept_list") or []
        r["has_er"] = r.get("er_id") is not None
    return rows


def pharmacy_data() -> list:
    rows = fetch("pharmacy")
    for r in rows:
        r["open_time"] = to_time(r.get("open_time"))
        r["close_time"] = to_time(r.get("close_time"))
    return rows


# =====================================================================
# 헬퍼
# =====================================================================
def esc(v) -> str:
    return "" if v is None else html.escape(str(v))


def digits(p) -> str:
    return re.sub(r"[^0-9+]", "", p or "")


def map_link(addr) -> str:
    return "https://map.naver.com/p/search/" + quote(addr or "")


def hhmm(t) -> str:
    return "-" if t is None else t.strftime("%H:%M")


def ago(ts, now):
    if ts is None:
        return "-", False
    mins = max(int((now - ts).total_seconds() // 60), 0)
    if mins < 1:
        label = "방금 전"
    elif mins < 60:
        label = f"{mins}분 전"
    elif mins < 1440:
        label = f"{mins // 60}시간 전"
    else:
        label = f"{mins // 1440}일 전"
    return label, mins >= STALE_MIN


def is_open(o, c, hol, now, is_holiday) -> bool:
    if o is None or c is None:
        return False
    if is_holiday and hol != "Y":
        return False
    return o <= now.time().replace(second=0, microsecond=0) < c


def minutes_left(c, now) -> int:
    return (c.hour * 60 + c.minute) - (now.hour * 60 + now.minute)


def fmt_left(m: int) -> str:
    h, mm = divmod(m, 60)
    if h and mm:
        return f"{h}시간 {mm}분"
    if h:
        return f"{h}시간"
    return f"{mm}분"


def bed_level(r) -> str:
    if r.get("status", r.get("er_status")) != "운영중" or r["available_beds"] <= 0:
        return "full"
    return "low" if r["available_beds"] <= 3 else "ok"


LEVEL_TXT = {"ok": "수용 가능", "low": "여유 적음", "full": "포화"}


def act(label, href, kind="", blank=False) -> str:
    tgt = ' target="_blank" rel="noopener"' if blank else ""
    return f'<a class="act {kind}" href="{href}"{tgt}>{label}</a>'


def call_btn(phone, label="📞 전화", kind="p") -> str:
    d = digits(phone)
    return act(label, "tel:" + d, kind) if d else '<span class="act off">번호 없음</span>'


def md(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def grid(cards: list) -> None:
    if not cards:
        empty()
        return
    md('<div class="grid">' + "".join(cards) + "</div>")


def empty(msg="조건에 맞는 결과가 없어요") -> None:
    md(f'<div class="empty"><div class="ei">🔍</div><b>{msg}</b><br>필터를 조정해 보세요</div>')


def in_region(r, city, dist) -> bool:
    if dist != "전체":
        return r["region"] == dist
    if city != "전체":
        return r["region"].startswith(city + " ")
    return True


def region_ui(rows: list, key: str):
    cities = sorted({r["region"].split()[0] for r in rows})
    md('<div class="flabel">지역</div>')
    city = st.pills("시·도", ["전체"] + cities, selection_mode="single", default="전체",
                    key=f"{key}_city", label_visibility="collapsed") or "전체"
    dist = "전체"
    if city != "전체":
        dists = sorted({r["region"] for r in rows if r["region"].startswith(city + " ")})
        dist = st.pills("시·군·구", ["전체"] + dists, selection_mode="single", default="전체",
                        key=f"{key}_dist_{city}", label_visibility="collapsed",
                        format_func=lambda v: v if v == "전체" else v.split(" ", 1)[1]) or "전체"
    return city, dist


# =====================================================================
# 카드 HTML
# =====================================================================
def er_card(r, now) -> str:
    lv = bed_level(r)
    beds = r["available_beds"]
    when, stale = ago(r["update_time"], now)
    pct = min(beds / BED_BAR_MAX * 100, 100)
    funeral = '<span class="chip">장례식장</span>' if r.get("funeral_hall") == "Y" else ""
    foot = ("⚠ " if stale else "") + f"{when} 갱신" + (" · 전화로 꼭 확인하세요" if stale else "")
    foot_cls = "foot stale" if stale else "foot"
    return (
        f'<div class="card lv-{lv}">'
        '<div class="c-head"><div>'
        f'<div class="c-name">{esc(r["hospital_name"])}</div>'
        f'<div class="c-sub">{esc(r["region"])} · {esc(r["hospital_type"])}</div>'
        '</div>'
        f'<span class="pill p-{lv}"><i></i>{LEVEL_TXT[lv]}</span></div>'
        '<div class="beds">'
        f'<div class="n n-{lv}">{beds}</div>'
        '<div class="bw"><div class="l">가용 병상</div>'
        f'<div class="bar"><span class="f-{lv}" style="width:{pct:.0f}%"></span></div></div>'
        '</div>'
        f'<div class="meta">📍 {esc(r["address"])}</div>'
        f'<div class="chips">{funeral}</div>'
        '<div class="acts">'
        + call_btn(r["er_phone"], "🚑 응급실 전화", "r")
        + act("🗺 길찾기", map_link(r["address"]), "", True)
        + '</div>'
        f'<div class="{foot_cls}">{foot}</div>'
        '</div>'
    )


def hospital_inner(r, now, is_holiday) -> str:
    if r["has_er"]:
        lv = bed_level(r)
        er_pill = f'<span class="pill p-{lv}"><i></i>응급실 {LEVEL_TXT[lv]}</span>'
    else:
        er_pill = '<span class="pill p-off">응급실 없음</span>'
    opened = is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday)
    out_chip = ('<span class="chip hl">외래 진료중</span>' if opened
                else '<span class="chip">외래 종료</span>')
    hol_chip = '<span class="chip hl">휴일 외래</span>' if r["holiday_open"] == "Y" else ""
    fun_chip = '<span class="chip">장례식장</span>' if r["funeral_hall"] == "Y" else ""
    depts = "".join(f'<span class="chip">{esc(d)}</span>' for d in r["dept_list"])
    beds_line = f' · 병상 {r["available_beds"]}개' if r["has_er"] else ""
    return (
        '<div class="c-head"><div>'
        f'<div class="c-name">{esc(r["hospital_name"])}</div>'
        f'<div class="c-sub">{esc(r["region"])} · {esc(r["hospital_type"])}</div>'
        f'</div>{er_pill}</div>'
        f'<div class="chips">{out_chip}{hol_chip}{fun_chip}</div>'
        f'<div class="chips">{depts}</div>'
        f'<div class="meta">🕘 외래 {hhmm(r["open_time"])} – {hhmm(r["close_time"])}{beds_line}</div>'
        '<div class="acts">'
        + call_btn(r["phone"], "📞 대표전화", "p")
        + act("🗺 길찾기", map_link(r["address"]), "", True)
        + '</div>'
    )


def pharmacy_card(r, now, is_holiday) -> str:
    opened = is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday)
    if opened:
        left = minutes_left(r["close_time"], now)
        if left <= 60:
            pill = '<span class="pill p-low"><i></i>곧 마감</span>'
        else:
            pill = '<span class="pill p-ok"><i></i>영업중</span>'
        sub = f"마감까지 {fmt_left(left)}"
    else:
        pill = '<span class="pill p-off">영업 종료</span>'
        sub = "지금은 영업시간이 아니에요" if not is_holiday or r["holiday_open"] == "Y" else "휴일에는 쉬어요"
    hol = ('<span class="chip hl">휴일 운영</span>' if r["holiday_open"] == "Y"
           else '<span class="chip">휴일 휴무</span>')
    night = ('<span class="chip am">🌙 야간 영업</span>'
             if r["close_time"] is not None and r["close_time"] >= time(22, 0) else "")
    return (
        '<div class="card">'
        '<div class="c-head"><div>'
        f'<div class="c-name">{esc(r["pharmacy_name"])}</div>'
        f'<div class="c-sub">{esc(r["region"])}</div></div>{pill}</div>'
        f'<div class="beds"><div class="n n-ok" style="font-size:1.35rem;min-width:0">'
        f'{hhmm(r["open_time"])} – {hhmm(r["close_time"])}</div></div>'
        f'<div class="meta">{sub}</div>'
        f'<div class="chips">{hol}{night}</div>'
        f'<div class="meta">📍 {esc(r["address"])}</div>'
        '<div class="acts">'
        + call_btn(r["phone"], "📞 전화", "p")
        + act("🗺 길찾기", map_link(r["address"]), "", True)
        + '</div></div>'
    )


# =====================================================================
# 병원 상세 팝업
# =====================================================================
def hospital_dialog(r, now, is_holiday):
    @st.dialog(r["hospital_name"], width="large")
    def _show():
        opened = is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday)
        out = ('<span class="pill p-blue">외래 진료중</span>' if opened
               else '<span class="pill p-off">외래 종료</span>')
        md(f'<div class="c-sub" style="margin-bottom:8px">{esc(r["hospital_type"])} · {esc(r["region"])} &nbsp; {out}</div>')

        left, right = st.columns(2)
        with left:
            depts = "".join(f'<span class="chip hl">{esc(d)}</span>' for d in r["dept_list"]) or "-"
            md(
                '<div class="box"><div class="sec" style="margin-top:0">기본 정보</div><div class="dl">'
                f'<div class="k">주소</div><div class="v">{esc(r["address"])}</div>'
                f'<div class="k">대표전화</div><div class="v">{esc(r["phone"]) or "-"}</div>'
                f'<div class="k">평일 외래</div><div class="v">{hhmm(r["open_time"])} – {hhmm(r["close_time"])}</div>'
                f'<div class="k">휴일 외래</div><div class="v">{"진료" if r["holiday_open"] == "Y" else "휴진"}</div>'
                f'<div class="k">장례식장</div><div class="v">{"있음" if r["funeral_hall"] == "Y" else "없음"}</div>'
                f'</div><div class="flabel">진료과목</div><div class="chips">{depts}</div></div>'
            )
        with right:
            if r["has_er"]:
                lv = bed_level(r)
                when, stale = ago(r["update_time"], now)
                warn = '<div class="foot stale">⚠ 오래된 정보예요. 전화로 확인하세요.</div>' if stale else ""
                pct = min(r["available_beds"] / BED_BAR_MAX * 100, 100)
                md(
                    '<div class="box"><div class="sec" style="margin-top:0">🚑 응급실 현황</div>'
                    f'<span class="pill p-{lv}"><i></i>{LEVEL_TXT[lv]}</span>'
                    '<div class="beds">'
                    f'<div class="n n-{lv}">{r["available_beds"]}</div>'
                    f'<div class="bw"><div class="l">가용 병상</div><div class="bar"><span class="f-{lv}" style="width:{pct:.0f}%"></span></div></div></div>'
                    f'<div class="meta">응급실 직통 <b>{esc(r["er_phone"]) or "-"}</b></div>'
                    f'<div class="foot">{when} 갱신</div>{warn}'
                    '<div class="acts">' + call_btn(r["er_phone"], "🚑 응급실 전화", "r") + '</div></div>'
                )
            else:
                md('<div class="box"><div class="sec" style="margin-top:0">🚑 응급실 현황</div>'
                   '<div class="meta">이 병원은 응급실을 운영하지 않아요.<br>'
                   '야간·휴일에는 응급실 운영 병원을 이용하세요.</div></div>')
        md('<div class="acts">' + call_btn(r["phone"], "📞 대표전화", "p")
           + act("🗺 네이버 지도에서 보기", map_link(r["address"]), "", True) + '</div>')

    _show()


# =====================================================================
# 히어로 + KPI (30초마다 자동 갱신)
# =====================================================================
@st.fragment(run_every=30)
def hero():
    now = datetime.now(KST)
    is_holiday = st.session_state.get("is_holiday", now.weekday() >= 5)
    ers = er_data()
    pharm = pharmacy_data()

    ok_n = sum(1 for r in ers if bed_level(r) in ("ok", "low"))
    full_n = sum(1 for r in ers if bed_level(r) == "full")
    beds = sum(r["available_beds"] for r in ers)
    ph_open = sum(1 for r in pharm if is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday))
    wd = "월화수목금토일"[now.weekday()]

    md(
        '<div class="topbar"><span>🚨 응급 상황이면 망설이지 말고 <b>119</b>로 연락하세요</span>'
        '<span><a href="tel:1339">📞 1339 응급의료정보센터</a>'
        '<a href="https://www.e-gen.or.kr" target="_blank" rel="noopener">응급의료포털</a></span></div>'
        '<div class="gnb">'
        f'<div class="logo"><div class="mk">✚</div><div>{BRAND}<small>실시간 병원·응급실·약국 안내</small></div></div>'
        f'<div class="live"><i></i>실시간 · {now.month}월 {now.day}일 ({wd}) {now:%H:%M} 기준</div></div>'
        '<div class="hero"><div class="hero-in"><div>'
        '<div class="eyebrow">24시간 응급실 · 야간·휴일 약국까지</div>'
        '<div class="h1">가까운 병원·응급실·약국,<br>지금 바로 확인하세요</div>'
        '<div class="sub">병상 현황과 진료·영업 시간을 한 곳에서 확인하고,<br>전화와 길찾기까지 바로 연결해 드려요.</div>'
        '<div class="hero-actions">'
        '<a class="btn btn-red" href="tel:119">🚨 119 응급신고</a>'
        '<a class="btn btn-ghost" href="tel:1339">📞 1339 응급의료정보센터</a>'
        '</div></div>'
        '<div class="stat-card"><div class="t">지금 수용 가능한 응급실</div>'
        f'<div class="big">{ok_n}<small> / {len(ers)}곳</small></div>'
        f'<div class="d">가용 병상 <b>{beds}개</b> · 포화 <b>{full_n}곳</b><br>방문 전 응급실 직통 전화로 꼭 확인하세요</div></div>'
        '</div></div>'
        '<div class="kpis">'
        f'<div class="kpi green"><div class="kl">수용 가능 응급실</div><div class="kv">{ok_n}<small> / {len(ers)}곳</small></div><div class="ks">병상이 남아 있는 곳</div></div>'
        f'<div class="kpi blue"><div class="kl">가용 병상 합계</div><div class="kv">{beds}<small> 개</small></div><div class="ks">전체 응급실 기준</div></div>'
        f'<div class="kpi red"><div class="kl">포화 응급실</div><div class="kv">{full_n}<small> 곳</small></div><div class="ks">방문 전 전화 필수</div></div>'
        f'<div class="kpi"><div class="kl">지금 영업중 약국</div><div class="kv">{ph_open}<small> / {len(pharm)}곳</small></div><div class="ks">{"휴일" if is_holiday else "평일"} 기준</div></div>'
        '</div>'
    )


# =====================================================================
# 탭 1: 응급실 (30초마다 자동 갱신)
# =====================================================================
@st.fragment(run_every=30)
def tab_er():
    now = datetime.now(KST)
    rows = er_data()

    with st.container(key="panel_er"):
        city, dist = region_ui(rows, "er")
        c1, c2 = st.columns([1, 1])
        only_ok = c1.toggle("수용 가능한 응급실만 보기", value=True, key="er_ok")
        sort = c2.selectbox("정렬", ["가용 병상 많은 순", "최근 갱신 순", "병원명 순"],
                            key="er_sort", label_visibility="collapsed")

    view = [r for r in rows if in_region(r, city, dist)
            and (not only_ok or bed_level(r) in ("ok", "low"))]
    if sort == "가용 병상 많은 순":
        view.sort(key=lambda r: (-r["available_beds"], r["hospital_name"]))
    elif sort == "최근 갱신 순":
        view.sort(key=lambda r: r["update_time"] or now, reverse=True)
    else:
        view.sort(key=lambda r: r["hospital_name"])

    md(f'<div class="count"><b>{len(view)}곳</b> · 가용 병상 합계 <b>{sum(r["available_beds"] for r in view)}개</b> '
       '· 30초마다 자동 갱신</div>')
    grid([er_card(r, now) for r in view])

    if view:
        with st.expander("📋 표로 보기 (INNER JOIN 결과)"):
            df = pd.DataFrame([{
                "병원": r["hospital_name"], "지역": r["region"], "상태": r["status"],
                "가용 병상": r["available_beds"], "응급실 전화": r["er_phone"],
                "갱신": ago(r["update_time"], now)[0],
            } for r in view])
            st.dataframe(df, hide_index=True, use_container_width=True,
                         column_config={"가용 병상": st.column_config.ProgressColumn(
                             "가용 병상", min_value=0, max_value=BED_BAR_MAX, format="%d")})
    st.caption("병상 수는 수시로 변동돼요. 방문 전 응급실 직통 전화로 꼭 확인하세요.")


# =====================================================================
# 탭 2: 병원 찾기
# =====================================================================
def tab_hospital(now, is_holiday):
    rows = hospital_data()
    all_depts = sorted({d for r in rows for d in r["dept_list"]})

    with st.container(key="panel_hos"):
        kw = st.text_input("병원명 검색", placeholder="🔍 병원 이름으로 검색 (예: 서울대, 성모)",
                           key="hos_kw", label_visibility="collapsed")
        city, dist = region_ui(rows, "hos")
        md('<div class="flabel">진료과목 (선택한 과목을 모두 진료하는 병원)</div>')
        depts = st.pills("진료과목", all_depts, selection_mode="multi", key="hos_dept",
                         label_visibility="collapsed") or []
        t1, t2, t3, t4 = st.columns(4)
        night = t1.toggle("🌙 야간·휴일 진료", key="hos_night",
                          help="24시간 응급실이 있거나 휴일 외래를 진료하는 병원")
        open_now = t2.toggle("지금 외래 진료중", key="hos_open")
        er_only = t3.toggle("응급실 있는 곳", key="hos_er")
        funeral = t4.toggle("장례식장 보유", key="hos_fun")

    view = []
    for r in rows:
        if not in_region(r, city, dist):
            continue
        if kw.strip() and kw.strip().lower() not in r["hospital_name"].lower():
            continue
        if depts and not set(depts) <= set(r["dept_list"]):
            continue
        if night and not (r["has_er"] or r["holiday_open"] == "Y"):
            continue
        if er_only and not r["has_er"]:
            continue
        if funeral and r["funeral_hall"] != "Y":
            continue
        if open_now and not is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday):
            continue
        view.append(r)
    view.sort(key=lambda r: (bed_level(r) == "full" if r["has_er"] else True, r["region"], r["hospital_name"]))

    md(f'<div class="count">검색 결과 <b>{len(view)}곳</b></div>')
    if not view:
        empty()
        return

    per_row = 3
    for i in range(0, len(view), per_row):
        cols = st.columns(per_row)
        for col, r in zip(cols, view[i:i + per_row]):
            with col:
                with st.container(key=f"hc_{r['hospital_id']}"):
                    md(hospital_inner(r, now, is_holiday))
                    if st.button("상세 정보 보기", key=f"hb_{r['hospital_id']}", use_container_width=True):
                        hospital_dialog(r, now, is_holiday)


# =====================================================================
# 탭 3: 약국
# =====================================================================
def tab_pharmacy(now, is_holiday):
    rows = pharmacy_data()
    with st.container(key="panel_ph"):
        kw = st.text_input("약국명 검색", placeholder="🔍 약국 이름으로 검색",
                           key="ph_kw", label_visibility="collapsed")
        city, dist = region_ui(rows, "ph")
        t1, t2, t3 = st.columns(3)
        open_now = t1.toggle("지금 영업중", key="ph_open")
        night = t2.toggle("🌙 야간 영업 (22시 이후)", key="ph_night")
        hol_only = t3.toggle("휴일 운영", value=is_holiday, key="ph_hol")

    view = []
    for r in rows:
        if not in_region(r, city, dist):
            continue
        if kw.strip() and kw.strip().lower() not in r["pharmacy_name"].lower():
            continue
        if night and not (r["close_time"] is not None and r["close_time"] >= time(22, 0)):
            continue
        if hol_only and r["holiday_open"] != "Y":
            continue
        if open_now and not is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday):
            continue
        view.append(r)
    view.sort(key=lambda r: (not is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday),
                             r["region"], r["pharmacy_name"]))

    md(f'<div class="count">검색 결과 <b>{len(view)}곳</b> · 영업중인 약국이 먼저 보여요</div>')
    grid([pharmacy_card(r, now, is_holiday) for r in view])
    st.caption("영업시간은 변동될 수 있어요. 방문 전 전화로 확인하세요.")


# =====================================================================
# 탭 4: 병상 관리 (UPDATE 시연)
# =====================================================================
def tab_admin():
    md('<div class="sec">병상 관리 (시연용)</div>'
       '<div class="meta">병상 수를 바꾸면 DB에 즉시 반영되고, 응급실 탭에 실시간으로 보여요.</div>')
    pw = st.text_input("관리자 비밀번호", type="password", key="adm_pw")
    if not pw:
        st.info("비밀번호는 supabase_api_setup.sql 의 update_er_beds 함수에 설정한 값이에요.")
        return

    rows = sorted(er_data(), key=lambda r: r["hospital_id"])
    pick = st.selectbox("응급실 선택", rows, key="adm_pick",
                        format_func=lambda r: f'{r["hospital_name"]} · 현재 {r["available_beds"]}병상 ({r["status"]})')

    def save(beds: int):
        try:
            client().rpc("update_er_beds", {"p_hospital_id": int(pick["hospital_id"]),
                                            "p_beds": int(max(beds, 0)), "p_pw": pw}).execute()
        except Exception as e:  # noqa: BLE001
            st.error("저장에 실패했어요. 비밀번호가 맞는지 확인하세요.")
            st.caption(str(e)[:200])
            return False
        st.cache_data.clear()
        return True

    c1, c2, c3 = st.columns(3)
    done = False
    if c1.button("➖ 환자 입실 (병상 -1)", use_container_width=True):
        done = save(pick["available_beds"] - 1)
    if c2.button("➕ 환자 퇴실 (병상 +1)", use_container_width=True):
        done = save(pick["available_beds"] + 1)
    with c3:
        new_beds = st.number_input("병상 수", min_value=0, max_value=200, value=pick["available_beds"],
                                   label_visibility="collapsed", key=f"adm_beds_{pick['hospital_id']}")
        if st.button("💾 이 값으로 저장", use_container_width=True):
            done = save(new_beds)
    if done:
        st.toast("저장했어요 ✅")
        st.rerun()


# =====================================================================
# 탭 5: 서비스 정보
# =====================================================================
def tab_info():
    md('<div class="sec">이 서비스는 이렇게 동작해요</div>'
       '<div class="meta">Streamlit 화면 → Supabase API(URL + anon key) → PostgreSQL. '
       'JOIN은 DB의 VIEW로 만들어 두고 화면에서 불러와요.</div>')
    st.code("""-- 응급실 현황: INNER JOIN
CREATE VIEW v_er_status AS
SELECT h.*, e.status, e.available_beds, e.er_phone, e.update_time
FROM Hospital h INNER JOIN EmergencyRoom e ON h.hospital_id = e.hospital_id;

-- 병원 전체: LEFT JOIN + N:M 다중 JOIN(진료과목 집계)
CREATE VIEW v_hospital_full AS
SELECT h.*, COALESCE(e.status,'응급실 미운영') AS er_status, dl.dept_list
FROM Hospital h
LEFT JOIN EmergencyRoom e ON h.hospital_id = e.hospital_id
LEFT JOIN LATERAL (
  SELECT array_agg(d.dept_name) AS dept_list
  FROM Hospital_Department hd JOIN Department d ON d.dept_id = hd.dept_id
  WHERE hd.hospital_id = h.hospital_id) dl ON TRUE;""", language="sql")
    md('<div class="meta"><b>테이블</b> Hospital · EmergencyRoom(1:1) · Department · '
       'Hospital_Department(N:M) · Pharmacy</div>')


# =====================================================================
# 메인
# =====================================================================
def main():
    md(CSS)
    now = datetime.now(KST)
    st.session_state.setdefault("is_holiday", now.weekday() >= 5)

    try:
        fetch("v_er_status")
    except Exception as e:  # noqa: BLE001
        st.error("데이터를 불러오지 못했어요.")
        st.markdown(
            "- Streamlit **Secrets**에 `SUPABASE_URL`, `SUPABASE_KEY`가 있는지 확인하세요.\n"
            "- Supabase SQL Editor에서 `supabase_schema.sql` → `supabase_api_setup.sql` 순서로 실행했는지 확인하세요.\n"
            "- `Invalid API key` 오류면 Project Settings → API Keys의 **legacy anon key**(eyJ...)를 써 보세요."
        )
        st.code(str(e)[:600])
        st.stop()

    hero()

    c1, c2 = st.columns([3, 2])
    c1.caption("📍 공휴일은 자동으로 알 수 없어서, 아래 스위치로 직접 켜 주세요. (주말은 자동)")
    is_holiday = c2.toggle("오늘은 휴일(공휴일 포함)", key="is_holiday")

    t1, t2, t3, t4, t5 = st.tabs(["🚑 응급실", "🏥 병원 찾기", "💊 약국", "🔧 병상 관리", "ℹ️ 정보"])
    with t1:
        tab_er()
    with t2:
        tab_hospital(now, is_holiday)
    with t3:
        tab_pharmacy(now, is_holiday)
    with t4:
        tab_admin()
    with t5:
        tab_info()

    md('<div class="disc">※ 학습(PBL)용 샘플 데이터 기반 서비스이며 실제 의료 판단을 대체하지 않아요.<br>'
       '실제 응급 상황에서는 즉시 119에 연락하고, 응급실 정보는 응급의료포털(e-gen.or.kr)에서도 확인하세요.</div>')


main()
